"""Checks for ADR 0020's team-play reward. Run with the other tests:

    python -m pytest -q tests rl/test_team_play.py

Kept in rl/ because it imports the training environment.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.game.engine import EAST, WEST, Rng, new_game, step  # noqa: E402
from env import team_play_reward, team_potentials  # noqa: E402

SWAP = {0: 0, 1: 1, 2: 2, EAST: WEST, WEST: EAST}


def _rollout(seed: int, k: int, turns: int, bias: int):
    """A game and its mirror image (flipped left to right, teams swapped),
    played with the same moves mirrored. Moves lean towards the enemy so
    flags get picked up and carried. Yields both states' team-play reward
    inputs every turn."""
    a, b = new_game(seed, k), new_game(seed, k)
    mirror = lambda i: (i + k) % (2 * k)  # noqa: E731
    rng = Rng(seed * 7 + bias)
    for _ in range(turns):
        if a.done:
            return
        before_a = [team_potentials(a, t) for t in (0, 1)]
        before_b = [team_potentials(b, t) for t in (0, 1)]
        acts = []
        for i, p in enumerate(a.players):
            r = rng.below(8)
            towards = EAST if p.team == 0 else WEST
            home = WEST if p.team == 0 else EAST
            acts.append((home if p.carrying else towards) if r >= 5 else r)
        mirrored = [0] * (2 * k)
        for i, act in enumerate(acts):
            mirrored[mirror(i)] = SWAP[act]
        ev_a = step(a, acts)
        ev_b = step(b, mirrored)
        after_a = [team_potentials(a, t) for t in (0, 1)]
        after_b = [team_potentials(b, t) for t in (0, 1)]
        yield a, b, mirror, before_a, after_a, ev_a, before_b, after_b, ev_b


def test_team_play_reward_is_mirrored_for_red():
    # A blue seat in a game must get exactly the reward the matching red seat
    # gets in the mirror game, including teammates' captures.
    caps = 0
    for seed in range(8):
        for k in (2, 3):
            for a, b, mirror, ba, aa, ea, bb, ab, eb in _rollout(seed, k, 500, 1):
                caps += sum(ev == "capture" for ev, _ in ea)
                for i, p in enumerate(a.players):
                    t = p.team
                    ra = team_play_reward(i, ba[t], aa[t], ea, 0.99, 0.5, 0.3)
                    j = mirror(i)
                    rb = team_play_reward(j, bb[1 - t], ab[1 - t], eb, 0.99, 0.5, 0.3)  # eb names b's seats
                    assert abs(ra - rb) < 1e-9, (seed, k, a.tick, i)
    assert caps > 0, "the rollouts should include captures, or the bonus is untested"


def test_teammate_shaping_telescopes():
    # With gamma = 1 and no bonus, the shaping over a game sums to the change
    # in the teammates' mean potential: walking somewhere and back earns 0, so
    # it can't be farmed (Ng et al. 1999).
    for seed in range(4):
        for k in (2, 3):
            total, first, last = 0.0, None, None
            for a, _, _, ba, aa, ea, *_ in _rollout(seed, k, 300, 2):
                seat = 0
                total += team_play_reward(seat, ba[0], aa[0], [], 1.0, 1.0, 0.0)
                mates = [i for i in ba[0] if i != seat]
                if first is None:
                    first = sum(ba[0][i] for i in mates) / len(mates)
                last = sum(aa[0][i] for i in mates) / len(mates)
            assert abs(total - (last - first)) < 1e-9


def test_own_capture_earns_no_teammate_bonus():
    before = {0: -0.1, 1: -0.5}
    assert team_play_reward(0, before, before, [("capture", 0)], 1.0, 0.0, 0.3) == 0.0
    assert team_play_reward(0, before, before, [("capture", 1)], 1.0, 0.0, 0.3) == 0.3
    assert team_play_reward(0, before, before, [("capture", 2)], 1.0, 0.0, 0.3) == 0.0  # the other team

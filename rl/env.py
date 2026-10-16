"""Many games at once, as a batch the learner can step (ADR 0013).

The learning team's seats are played by the network; the other team by the
scripted bots, softened by a curriculum: each turn an opponent plays its
scripted move with probability `level`, otherwise a random one. Level 0 is an
opponent that wanders; level 1 is the full scripted bot. Half the game slots are 2v2 and half 3v3, fixed, so the batch
always has the same number of rows; each new game picks blue or red for the
learner and a map from the training seed range. Every learner seat is a row.

Rewards per learner seat, each turn:
- team: +1 for each capture by its team, -1 for each capture against it;
- shaping: shaping_weight * (gamma * phi(after) - phi(before)), where phi is
  minus the shortest-path distance to what the seat should go for, scaled by
  the map's size. Potential-based, so it can't change which policy is best.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.game import bots, engine  # noqa: E402
from app.game.obs import HEIGHT, PLANES, SCALARS, WIDTH, observe, to_engine  # noqa: E402

TRAIN_SEEDS = (0, 1_000_000)  # evaluation uses seeds at or above 1_000_000


def objective(state: engine.State, seat: int) -> list[tuple[int, int]]:
    p = state.players[seat]
    m = state.map
    if p.carrying:
        return list(m.bases[p.team])
    return [m.flags[1 - p.team]]


def potential(state: engine.State, seat: int) -> float:
    """Minus the path still to walk before this seat could score, scaled.

    Without the flag that is the distance to the enemy flag plus the distance
    from there to home; with it, the distance home. So picking the flag up
    doesn't change the potential at all. A first version used only the
    distance to the current objective, which dropped by half the map the moment
    a bot picked the flag up: an immediate penalty for the one move it most
    needed to learn, and the first runs learned to defend and never to score.
    A seat off the board waits in its base, so it gets the base's potential:
    being caught costs the ground it had covered."""
    p = state.players[seat]
    m = state.map
    scale = 2 * (m.width + m.height)
    x, y = (p.x, p.y) if p.active else m.bases[p.team][0]
    home = bots.distances(state, p.team, list(m.bases[p.team]))
    if p.carrying:
        remaining = home.get((x, y), scale)
    else:
        flag = m.flags[1 - p.team]
        to_flag = bots.distances(state, p.team, [flag]).get((x, y), scale)
        remaining = to_flag + home.get(flag, scale)
    return -remaining / scale


def team_potentials(state: engine.State, team: int) -> dict[int, float]:
    """`potential` for every seat of one team."""
    return {i: potential(state, i) for i, p in enumerate(state.players) if p.team == team}


def team_play_reward(seat: int, phi_before: dict[int, float], phi_after: dict[int, float], events: list[tuple[str, int]],
                     gamma: float, mate_weight: float, mate_bonus: float) -> float:
    """The team-play terms of ADR 0020 for one learner seat, on top of the
    team reward.

    - mate_weight * mean over its teammates of (gamma * phi(after) - phi(before)):
      potential-based shaping on the teammates' progress towards scoring
      (Ng et al. 1999), so it can't be farmed and leaves the best policy for
      the team reward unchanged;
    - mate_bonus for each capture by a teammate (not by this seat): not
      potential-based, so it is annealed to 0 during training.

    phi_* map every seat of the team (this one included) to its potential.
    Seats, not directions: the same for blue and red (a test checks it)."""
    mates = [i for i in phi_before if i != seat]
    if not mates:
        return 0.0
    shaped = sum(gamma * phi_after[i] - phi_before[i] for i in mates) / len(mates)
    caps = sum(1 for ev, who in events if ev == "capture" and who in phi_before and who != seat)
    return mate_weight * shaped + mate_bonus * caps


class Game:
    def __init__(self, rng: random.Random, team_size: int):
        self.rng = rng
        self.team_size = team_size
        self.reset()

    def reset(self) -> None:
        self.state = engine.new_game(self.rng.randrange(*TRAIN_SEEDS), self.team_size)
        self.team = self.rng.choice((0, 1))
        self.seats = [i for i, p in enumerate(self.state.players) if p.team == self.team]
        self.phi = [potential(self.state, i) for i in self.seats]

    def observe(self) -> list[tuple[np.ndarray, np.ndarray]]:
        return [observe(self.state, i) for i in self.seats]

    def step(self, actions: list[int], gamma: float, shaping_weight: float, level: float = 1.0) -> tuple[list[float], bool, dict]:
        s = self.state
        full = [0] * len(s.players)
        for seat, a in zip(self.seats, actions):
            full[seat] = to_engine(self.team, a)  # the network chose in its flipped view
        for i, p in enumerate(s.players):
            if p.team != self.team:
                full[i] = bots.scripted_action(s, i) if self.rng.random() < level else self.rng.randrange(5)
        before = list(s.score)
        engine.step(s, full)
        team_reward = (s.score[self.team] - before[self.team]) - (s.score[1 - self.team] - before[1 - self.team])
        rewards = []
        for j, seat in enumerate(self.seats):
            phi_after = potential(s, seat)
            shaped = gamma * phi_after - self.phi[j]
            self.phi[j] = phi_after
            rewards.append(float(team_reward) + shaping_weight * shaped)
        info = {}
        if s.done:
            mine, theirs = s.score[self.team], s.score[1 - self.team]
            info = {"result": 1 if mine > theirs else -1 if mine < theirs else 0, "captures": mine}
        return rewards, s.done, info


class Batch:
    """N games stepped together. Rows are learner seats, in a fixed order per
    game; a game's rows stay in place for the whole episode."""

    def __init__(self, n_games: int, seed: int):
        self.rng = random.Random(seed)
        self.games = [Game(self.rng, 2 if g % 2 == 0 else 3) for g in range(n_games)]

    def observe(self) -> tuple[np.ndarray, np.ndarray, list[int]]:
        planes, scalars, owner = [], [], []
        for g, game in enumerate(self.games):
            for p, sc in game.observe():
                planes.append(p)
                scalars.append(sc)
                owner.append(g)
        return np.stack(planes), np.stack(scalars), owner

    def step(self, actions: np.ndarray, owner: list[int], gamma: float, shaping_weight: float, level: float = 1.0):
        rewards = np.zeros(len(actions), dtype=np.float32)
        dones = np.zeros(len(actions), dtype=np.float32)
        finished = []
        row = 0
        for g, game in enumerate(self.games):
            n = len(game.seats)
            r, done, info = game.step([int(a) for a in actions[row : row + n]], gamma, shaping_weight, level)
            rewards[row : row + n] = r
            dones[row : row + n] = float(done)
            if done:
                finished.append(info)
                game.reset()
            row += n
        return rewards, dones, finished


class FcpGame(Game):
    """One FCP-lite game (ADR 0018). The learner plays `n_learn` seats of its
    team, chosen at random each game (so a scripted partner's role, which
    depends on its seat, varies); one partner drawn from the pool plays the
    rest of the team; the other team is the full scripted bot, or with
    probability `p_pool_opp` one pool member for the whole team."""

    def __init__(self, rng: random.Random, team_size: int, n_learn: int, pool: list, p_pool_opp: float, gid: int):
        self.n_learn, self.pool, self.p_pool_opp, self.gid = n_learn, pool, p_pool_opp, gid
        super().__init__(rng, team_size)

    def reset(self) -> None:
        self.state = engine.new_game(self.rng.randrange(*TRAIN_SEEDS), self.team_size)
        self.team = self.rng.choice((0, 1))
        mates = [i for i, p in enumerate(self.state.players) if p.team == self.team]
        self.seats = sorted(self.rng.sample(mates, self.n_learn))
        self.partner_seats = [i for i in mates if i not in self.seats]
        self.enemy_seats = [i for i, p in enumerate(self.state.players) if p.team != self.team]
        self.partner = self.rng.choice(self.pool)
        self.opponent = self.rng.choice(self.pool) if self.rng.random() < self.p_pool_opp else None  # None: full scripted
        self.phi = [potential(self.state, i) for i in self.seats]
        self.team_phi = team_potentials(self.state, self.team)
        self.caps_learner = self.caps_partner = 0

    def finish(self, actions: list[int], others: dict[int, int], gamma: float, shaping_weight: float,
               mate_weight: float = 0.0, mate_bonus: float = 0.0):
        """Step the game with the learner's view actions and everyone else's
        engine actions. mate_weight and mate_bonus are ADR 0020's team-play
        terms (0 gives FCP-lite as in ADR 0018)."""
        s = self.state
        full = [0] * len(s.players)
        for seat, a in zip(self.seats, actions):
            full[seat] = to_engine(self.team, a)  # the network chose in its flipped view
        for seat, a in others.items():
            full[seat] = a
        before = list(s.score)
        events = engine.step(s, full)
        for ev, seat in events:
            if ev == "capture" and s.players[seat].team == self.team:
                if seat in self.seats:
                    self.caps_learner += 1
                else:
                    self.caps_partner += 1
        team_reward = (s.score[self.team] - before[self.team]) - (s.score[1 - self.team] - before[1 - self.team])
        team_phi = team_potentials(s, self.team)
        rewards = []
        for j, seat in enumerate(self.seats):
            phi_after = team_phi[seat]
            shaped = gamma * phi_after - self.phi[j]
            self.phi[j] = phi_after
            mate = team_play_reward(seat, self.team_phi, team_phi, events, gamma, mate_weight, mate_bonus)
            rewards.append(float(team_reward) + shaping_weight * shaped + mate)
        self.team_phi = team_phi
        info = {}
        if s.done:
            mine, theirs = s.score[self.team], s.score[1 - self.team]
            info = {"result": 1 if mine > theirs else -1 if mine < theirs else 0, "captures": mine,
                    "learner_caps": self.caps_learner, "partner_caps": self.caps_partner,
                    "partner": self.partner.name, "opponent": self.opponent.name if self.opponent else "scripted-full"}
        return rewards, s.done, info


class FcpBatch(Batch):
    """N FCP-lite games stepped together (ADR 0018). Game slots cycle through
    (2v2, 1 learner seat), (3v3, 1 learner seat), (3v3, 2 learner seats), fixed
    per slot, so the number of rows never changes. Partners' moves are batched:
    one forward pass per network per turn, across every game it plays in."""

    SLOTS = ((2, 1), (3, 1), (3, 2))

    def __init__(self, n_games: int, seed: int, pool: list, p_pool_opp: float = 0.4):
        self.rng = random.Random(seed)
        self.pool = pool
        self.games = [FcpGame(self.rng, *self.SLOTS[g % len(self.SLOTS)], pool, p_pool_opp, g) for g in range(n_games)]

    def step(self, actions: np.ndarray, owner: list[int], gamma: float, shaping_weight: float, level: float = 1.0,
             mate_weight: float = 0.0, mate_bonus: float = 0.0):
        # 1. everyone who isn't the learner, grouped by who plays them
        jobs: dict[int, list] = {}  # id(partner) -> [(state, seat, game id)]
        who: dict[int, object] = {}
        scripted_full = []
        for g, game in enumerate(self.games):
            s = game.state
            for seat in game.partner_seats:
                jobs.setdefault(id(game.partner), []).append((s, seat, g))
                who[id(game.partner)] = game.partner
            for seat in game.enemy_seats:
                if game.opponent is None:
                    scripted_full.append((g, seat))
                else:
                    jobs.setdefault(id(game.opponent), []).append((s, seat, g))
                    who[id(game.opponent)] = game.opponent
        others: list[dict[int, int]] = [{} for _ in self.games]
        for key, js in jobs.items():
            for (_, seat, g), a in zip(js, who[key].act_many(js, self.rng)):
                others[g][seat] = a
        for g, seat in scripted_full:
            others[g][seat] = bots.scripted_action(self.games[g].state, seat)
        # 2. step every game
        rewards = np.zeros(len(actions), dtype=np.float32)
        dones = np.zeros(len(actions), dtype=np.float32)
        finished = []
        row = 0
        for g, game in enumerate(self.games):
            n = len(game.seats)
            r, done, info = game.finish([int(a) for a in actions[row : row + n]], others[g], gamma, shaping_weight,
                                        mate_weight, mate_bonus)
            rewards[row : row + n] = r
            dones[row : row + n] = float(done)
            if done:
                finished.append(info)
                game.reset()
            row += n
        return rewards, dones, finished


OBS_SHAPE = (len(PLANES), HEIGHT, WIDTH)
N_SCALARS = len(SCALARS)

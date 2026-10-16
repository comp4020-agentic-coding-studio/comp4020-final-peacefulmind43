"""Partners for FCP-lite training and the teammate evaluation (ADR 0018).

A partner plays some seats of a game. Every partner sees only what a bot may
see: the state and its seat (CLAUDE.md), through `app/game/obs.py` for the
networks, and every partner is mirrored for red, the same as the bots.

Kinds, written as a spec string:
- `scripted`           the full scripted bot (app/game/bots.py, 10% noise);
- `scripted:E`         the scripted bot, but with probability E a random move
                       instead (so E=0.5 is about 55% random in total);
- `random:S`           a random walker that repeats its last move with
                       probability S, else picks a new one;
- `net:PATH`           a past network, from a training checkpoint (.pt) or an
                       export (.npz), sampling its move like the server does.

Training (`act_many`) batches the networks' forward passes, one per network
per turn. Evaluation (`act`) runs one seat at a time with NumPy and seeded
randomness, exactly as the server would, so matches replay.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.game import bots, engine  # noqa: E402
from app.game.engine import Rng  # noqa: E402
from app.game.obs import observe, to_engine  # noqa: E402

HERE = Path(__file__).resolve().parent
POOL_DIR = HERE / "runs" / "pool"  # filled by rl/make_pool.sh; gitignored

# The training pool (ADR 0018): stages of the cur runs from early to final,
# two pure defenders and two attackers who never come home, the scripted bot
# at two noise levels, and a random walker. Each training game draws one.
TRAIN_POOL = {
    "cur1": f"net:{POOL_DIR / 'cur1.pt'}",          # 2M samples, before it learned to attack
    "cur2": f"net:{POOL_DIR / 'cur2.npz'}",         # attacks, never defends, never gets home past a defender
    "cur4snap": f"net:{POOL_DIR / 'cur4snap.npz'}",  # mid cur4, about even with the scripted bot
    "cur4": f"net:{POOL_DIR / 'cur4.pt'}",          # the deployed bot: the old self-play partner
    "phi2": f"net:{POOL_DIR / 'phi2.npz'}",         # never leaves its own half
    "scripted": "scripted",
    "scripted50": "scripted:0.5",
    "random": "random:0.5",
}

# The team-play pool (ADR 0020): ADR 0018's pool plus fcp1, the deployed
# bot (strong, but scores nearly everything itself). cur4 is already in it.
TEAM_POOL = {**TRAIN_POOL, "fcp1": f"net:{POOL_DIR / 'fcp1.pt'}"}
POOLS = {"fcp": TRAIN_POOL, "team": TEAM_POOL}

# Held out: never a partner or an opponent in training.
HELD_OUT = {
    "scripted30": "scripted:0.3",                  # a noise level not in the pool
    "cur3": f"net:{POOL_DIR / 'cur3.pt'}",          # a run left out (attacker, another seed and stage)
    "lr1e3": f"net:{POOL_DIR / 'lr1e3.npz'}",       # a run left out (defender)
}


def load_weights(path: Path) -> dict[str, np.ndarray]:
    """Policy weights as NumPy, from a .pt checkpoint or an .npz export."""
    if path.suffix == ".npz":
        data = np.load(path)
        return {k: data[k] for k in data.files if not k.startswith("check_") and not k.startswith("v.")}
    import torch

    sd = torch.load(path, map_location="cpu")
    return {k: v.numpy() for k, v in sd.items() if not k.startswith("v.")}


class Partner:
    """One kind of player. `act` for one seat (evaluation, deterministic per
    match); `act_many` for many (state, seat) pairs at once (training)."""

    def __init__(self, name: str, spec: str):
        self.name, self.spec = name, spec
        kind, _, arg = spec.partition(":")
        self.kind = kind
        self.noise = float(arg) if kind == "scripted" and arg else 0.0
        self.stick = float(arg) if kind == "random" else 0.0
        self.last: dict[tuple[int, int], int] = {}  # random walker: (game id, seat) -> last view action
        self.policy = None
        self.torch_net = None
        if kind == "net":
            from app.game.policy import Policy

            path = Path(arg)
            self.policy = Policy.__new__(Policy)
            self.policy.w = load_weights(path)
            self.policy.name = name
        elif kind not in ("scripted", "random"):
            raise ValueError(f"unknown partner kind in {spec!r}")

    # --- evaluation: one seat, seeded by the match, as on the server -------
    def act(self, state: engine.State, seat: int) -> int:
        if self.kind == "net":
            return self.policy.action(state, seat)
        team = state.players[seat].team
        r = Rng((state.tick * 2654435761 + seat * 40503 + state.seed * 2246822519 + 4242) & 0xFFFFFFFF)
        if self.kind == "scripted":
            if r.next() < self.noise:
                return to_engine(team, r.below(5))  # chosen in its own view, so mirrored for red
            return bots.scripted_action(state, seat)
        key = (state.seed, seat)
        if state.tick == 0 or key not in self.last or r.next() >= self.stick:
            self.last[key] = r.below(5)
        return to_engine(team, self.last[key])

    # --- training: many seats at once ---------------------------------------
    def act_many(self, jobs: list[tuple[engine.State, int, int]], rng: random.Random) -> list[int]:
        """jobs: (state, seat, game id). Returns engine actions."""
        if self.kind == "scripted":
            return [to_engine(s.players[i].team, rng.randrange(5)) if rng.random() < self.noise else bots.scripted_action(s, i)
                    for s, i, _ in jobs]
        if self.kind == "random":
            out = []
            for s, i, g in jobs:
                key = (g, i)
                if s.tick == 0 or key not in self.last or rng.random() >= self.stick:
                    self.last[key] = rng.randrange(5)
                out.append(to_engine(s.players[i].team, self.last[key]))
            return out
        import torch

        if self.torch_net is None:
            from model import Net

            self.torch_net = Net()
            self.torch_net.load_state_dict({k: torch.from_numpy(v) for k, v in self.policy.w.items()}, strict=False)
            self.torch_net.eval()
        obs = [observe(s, i) for s, i, _ in jobs]
        planes = torch.from_numpy(np.stack([o[0] for o in obs]))
        scalars = torch.from_numpy(np.stack([o[1] for o in obs]))
        with torch.no_grad():
            logits, _ = self.torch_net(planes, scalars)
            choice = torch.distributions.Categorical(logits=logits).sample().numpy()
        return [to_engine(s.players[i].team, int(a)) for (s, i, _), a in zip(jobs, choice)]


def make(pool: dict[str, str]) -> list[Partner]:
    return [Partner(name, spec) for name, spec in pool.items()]

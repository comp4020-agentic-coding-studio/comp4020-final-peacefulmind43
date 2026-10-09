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


OBS_SHAPE = (len(PLANES), HEIGHT, WIDTH)
N_SCALARS = len(SCALARS)

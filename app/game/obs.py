"""What the RL bot sees (ADR 0013): the whole map from its own side.

Used by training (rl/) and by the server, so the two can't see different
things. Every map is drawn into planes of the largest size (12 x 20), with a
plane marking cells outside the real map, and red's view is flipped left to
right so every bot sees itself attacking to the right. A bot sees exactly the
board a person sees, and nothing about anyone's choices.
"""

from __future__ import annotations

import numpy as np

from .engine import EAST, RESPAWN_TICKS, SIZES, WEST, WIN_SCORE, State

HEIGHT = max(h for _, h in SIZES.values())
WIDTH = max(w for w, _ in SIZES.values())

PLANES = (
    "wall",
    "outside",
    "own_half",
    "own_base",
    "enemy_base",
    "self",
    "teammates",
    "enemies",
    "own_flag",
    "enemy_flag",
    "carriers",
)
SCALARS = ("turns_left", "score_difference", "carrying", "respawn", "three_a_side", "own_flag_taken")
P = {name: i for i, name in enumerate(PLANES)}


def observe(state: State, seat: int) -> tuple[np.ndarray, np.ndarray]:
    """(planes [11, 12, 20], scalars [6]) for `seat`, from its own side."""
    m = state.map
    me = state.players[seat]
    team, enemy = me.team, 1 - me.team

    def fx(x: int) -> int:  # flip so this team always attacks to the right
        return x if team == 0 else m.width - 1 - x

    planes = np.zeros((len(PLANES), HEIGHT, WIDTH), dtype=np.float32)
    planes[P["outside"]] = 1.0
    planes[P["outside"], : m.height, : m.width] = 0.0
    planes[P["own_half"], : m.height, : m.width // 2] = 1.0
    for x, y in m.walls:
        planes[P["wall"], y, fx(x)] = 1.0
    for x, y in m.bases[team]:
        planes[P["own_base"], y, fx(x)] = 1.0
    for x, y in m.bases[enemy]:
        planes[P["enemy_base"], y, fx(x)] = 1.0

    for i, p in enumerate(state.players):
        if not p.active:
            continue
        x = fx(p.x)
        if i == seat:
            planes[P["self"], p.y, x] = 1.0
        elif p.team == team:
            planes[P["teammates"], p.y, x] = 1.0
        else:
            planes[P["enemies"], p.y, x] = 1.0
        if p.carrying:
            planes[P["carriers"], p.y, x] = 1.0

    for which, flag_team in (("own_flag", team), ("enemy_flag", enemy)):
        holder = state.carrier[flag_team]
        if holder is not None and state.players[holder].active:
            hx, hy = state.players[holder].x, state.players[holder].y
        else:
            hx, hy = m.flags[flag_team]
        planes[P[which], hy, fx(hx)] = 1.0

    scalars = np.array(
        [
            (state.max_ticks - state.tick) / state.max_ticks,
            (state.score[team] - state.score[enemy]) / WIN_SCORE,
            float(me.carrying),
            me.respawn / RESPAWN_TICKS,
            float(len(state.players) == 6),
            float(state.carrier[team] is not None),
        ],
        dtype=np.float32,
    )
    return planes, scalars


def to_engine(team: int, action: int) -> int:
    """The bot's action, chosen in its own flipped view, as a move on the real
    board. Red sees the map mirrored, so its east is the board's west.

    The first training runs flipped the view but not the action: for red, the
    network's "towards the enemy" moved it home. Half of every batch taught
    the opposite of the other half, and the bot barely learned. A test now
    plays a game and its mirror with the same view-to-action rule and checks
    they stay mirrored."""
    if team == 1 and action in (EAST, WEST):
        return WEST if action == EAST else EAST
    return action

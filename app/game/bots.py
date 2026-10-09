"""Scripted bots: the fallback that always fills an empty seat (ADR 0011).

A bot sees only the game state, which is what everyone was shown at the
previous tick, never what people have just pressed: the signature takes no
inputs, so it can't. Roles alternate within a team: attackers go for the
enemy flag and bring it home; defenders chase intruders on their own half
and otherwise guard beside their flag.

Three things here came from playing bots against each other on many maps
before trusting them: everything that refers to a direction is mirrored for
red, so ties favour neither team; defenders guard on the side of the flag that
faces the middle; and one move in ten is random (seeded by the match, so it
replays), because two mirror-image deterministic bots can wait for each other
at the middle line forever.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache

from .engine import EAST, MOVES, NORTH, SOUTH, STAY, WEST, Map, Rng, State

NOISE = 0.1


def distances(state: State, team: int, targets: list[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """Steps from every cell this team can stand on to the nearest target.
    Don't modify the result: it is shared through a cache."""
    return _distances(state.map, team, tuple(sorted(targets)))


@lru_cache(maxsize=8192)
def _distances(m: Map, team: int, targets: tuple[tuple[int, int], ...]) -> dict[tuple[int, int], int]:
    # Depends only on the map, the team and the targets, which mostly stay the
    # same for a whole match (a flag, a base), so most calls are cache hits.
    # Profiling the RL environment found these searches were 92% of its time.
    dist = {t: 0 for t in targets if m.open(*t)}
    queue = deque(dist)
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
            nxt = (x + dx, y + dy)
            if nxt not in dist and m.open_for(team, *nxt):
                dist[nxt] = dist[(x, y)] + 1
                queue.append(nxt)
    return dist


def role(state: State, seat: int) -> str:
    team = state.players[seat].team
    mates = [i for i, p in enumerate(state.players) if p.team == team]
    return "attack" if mates.index(seat) % 2 == 0 else "defend"


def scripted_action(state: State, seat: int) -> int:
    p = state.players[seat]
    if not p.active:
        return STAY
    rng = Rng((state.tick * 2654435761 + seat * 40503 + state.seed * 2246822519 + 12345) & 0xFFFFFFFF)
    if rng.next() < NOISE:
        return rng.below(5)

    m = state.map
    own, enemy = p.team, 1 - p.team
    ahead = 1 if own == 0 else -1  # towards the middle
    enemies = [q for q in state.players if q.team == enemy and q.active]

    if p.carrying:
        targets = list(m.bases[own])
    elif role(state, seat) == "attack":
        carrier = state.carrier[enemy]
        if carrier is not None and carrier != seat:
            c = state.players[carrier]  # a teammate has their flag: stay with them
            targets = [(c.x, c.y)]
        else:
            targets = [m.flags[enemy]]
    else:
        holder = state.carrier[own]
        intruders = [(q.x, q.y) for q in enemies if m.half(q.x) == own]
        if holder is not None and state.players[holder].active:
            h = state.players[holder]
            targets = [(h.x, h.y)]  # whoever has our flag comes first
        elif intruders:
            targets = intruders
        else:
            fx, fy = m.flags[own]
            targets = [(fx + dx, fy + dy) for dx, dy in ((ahead, 0), (0, -1), (0, 1)) if m.open(fx + dx, fy + dy)]

    dist = distances(state, own, targets)
    danger = {(q.x + dx, q.y + dy) for q in enemies for dx, dy in MOVES.values()}

    def cost(action: int) -> float:
        dx, dy = MOVES[action]
        nx, ny = p.x + dx, p.y + dy
        cell = (nx, ny) if m.open_for(own, nx, ny) else (p.x, p.y)
        c = dist.get(cell, 999)
        if m.half(cell[0]) != own and cell in danger:
            c += 3  # on their half, keep out of an enemy's reach
        return c

    order = (NORTH, SOUTH, EAST, WEST, STAY) if own == 0 else (NORTH, SOUTH, WEST, EAST, STAY)
    return min(order, key=cost)

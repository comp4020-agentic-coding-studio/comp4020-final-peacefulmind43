"""The rules of capture the flag (ADR 0010), as a pure, deterministic function.

`step(state, actions)` is the whole game: no clock, no I/O, no randomness except
the map generator, which draws from a seeded generator that the TypeScript
reference engine in spec/engine.ts reproduces bit for bit. The server and the
RL training code both run this file, so they can't disagree about the rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

RULES_VERSION = 2  # 2: a team can't enter its own flag's cell; carriers skip 1 tick in 4, not 3

SIZES = {2: (16, 10), 3: (20, 12)}  # team size -> (width, height)
WALL_FRACTION = 0.18
RESPAWN_TICKS = 8
CARRIER_SKIP = 4  # a carrier doesn't move on every CARRIER_SKIP-th tick (rules v2; was 3)
MAX_TICKS = 720
WIN_SCORE = 3

STAY, NORTH, SOUTH, EAST, WEST = range(5)
MOVES = {STAY: (0, 0), NORTH: (0, -1), SOUTH: (0, 1), EAST: (1, 0), WEST: (-1, 0)}

# Base cells around a team's flag, in the order players spawn into them. Red's
# are the mirror image (dx -> -dx).
BASE_OFFSETS = [(0, -1), (0, 1), (1, 0), (1, -1), (1, 1), (-1, 0), (-1, -1), (-1, 1), (0, 0)]

MASK = 0xFFFFFFFF


class Rng:
    """mulberry32: small, fast, and easy to reproduce exactly in TypeScript."""

    def __init__(self, seed: int):
        self.a = seed & MASK

    def next(self) -> float:
        self.a = (self.a + 0x6D2B79F5) & MASK
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & MASK
        t = (t ^ ((t + (((t ^ (t >> 7)) * (t | 61)) & MASK)) & MASK)) & MASK
        return ((t ^ (t >> 14)) & MASK) / 4294967296

    def below(self, n: int) -> int:
        return int(self.next() * n)


@dataclass(frozen=True)
class Map:
    width: int
    height: int
    walls: frozenset[tuple[int, int]]
    flags: tuple[tuple[int, int], tuple[int, int]]  # home cell of blue's, red's flag
    bases: tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]  # spawn order

    def half(self, x: int) -> int:
        """0 for blue's half (left), 1 for red's."""
        return 0 if x < self.width // 2 else 1

    def open(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height and (x, y) not in self.walls

    def open_for(self, team: int, x: int, y: int) -> bool:
        """Open, and not this team's own flag cell, which is a wall to them
        (rules version 2: otherwise standing on your flag makes it untakeable)."""
        return self.open(x, y) and (x, y) != self.flags[team]


def make_map(seed: int, team_size: int) -> Map:
    """A random map, mirror-symmetric left to right, with every open cell
    reachable. The same seed always gives the same map."""
    width, height = SIZES[team_size]
    flags = ((1, height // 2), (width - 2, height // 2))
    bases = (
        tuple((flags[0][0] + dx, flags[0][1] + dy) for dx, dy in BASE_OFFSETS),
        tuple((flags[1][0] - dx, flags[1][1] + dy) for dx, dy in BASE_OFFSETS),
    )
    in_base = set(bases[0])
    half_cells = [(x, y) for y in range(height) for x in range(width // 2)]
    candidates = [c for c in half_cells if c not in in_base]
    n_walls = round(WALL_FRACTION * len(half_cells))

    rng = Rng(seed)
    for _ in range(100):
        pool = list(candidates)
        chosen = []
        for i in range(n_walls):  # partial Fisher-Yates
            j = i + rng.below(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
            chosen.append(pool[i])
        walls = frozenset(chosen) | frozenset((width - 1 - x, y) for x, y in chosen)
        candidate = Map(width, height, walls, flags, bases)
        if _connected(candidate):
            return candidate
    return Map(width, height, frozenset(), flags, bases)  # never seen in practice


def _connected(m: Map) -> bool:
    start = m.flags[0]
    seen = {start}
    frontier = [start]
    while frontier:
        x, y = frontier.pop()
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0)):
            nxt = (x + dx, y + dy)
            if nxt not in seen and m.open(*nxt):
                seen.add(nxt)
                frontier.append(nxt)
    return len(seen) == m.width * m.height - len(m.walls)


@dataclass
class Player:
    team: int
    x: int = -1  # -1 while off the board, waiting to respawn
    y: int = -1
    respawn: int = 0  # ticks left off the board
    carrying: bool = False

    @property
    def active(self) -> bool:
        return self.respawn == 0


@dataclass
class State:
    map: Map
    players: list[Player]
    score: list[int] = field(default_factory=lambda: [0, 0])
    carrier: list[int | None] = field(default_factory=lambda: [None, None])  # who holds blue's, red's flag
    tick: int = 0
    max_ticks: int = MAX_TICKS  # shorter only in private test arenas
    seed: int = 0  # the match seed, so bots' randomness replays too

    @property
    def done(self) -> bool:
        return max(self.score) >= WIN_SCORE or self.tick >= self.max_ticks


def new_game(seed: int, team_size: int) -> State:
    """Seats 0..k-1 are blue, k..2k-1 red, each spawning in base order."""
    m = make_map(seed, team_size)
    players = []
    for seat in range(2 * team_size):
        team = 0 if seat < team_size else 1
        x, y = m.bases[team][seat % team_size]
        players.append(Player(team, x, y))
    return State(m, players, seed=seed)


def step(state: State, actions: list[int]) -> list[tuple[str, int]]:
    """Advance one tick in place. Returns what happened, as (event, seat)."""
    if state.done:
        return []
    m, players = state.map, state.players
    events: list[tuple[str, int]] = []

    # 1. where everyone is trying to go
    target: dict[int, tuple[int, int]] = {}
    for i, p in enumerate(players):
        if not p.active:
            continue
        action = actions[i] if 0 <= actions[i] <= 4 else STAY
        if p.carrying and state.tick % CARRIER_SKIP == CARRIER_SKIP - 1:  # carriers are slower
            action = STAY
        dx, dy = MOVES[action]
        nx, ny = p.x + dx, p.y + dy
        target[i] = (nx, ny) if m.open_for(p.team, nx, ny) else (p.x, p.y)

    # 2. contact between enemies: same destination, or swapping cells
    tagged: set[int] = set()
    active = sorted(target)
    for a_i, i in enumerate(active):
        for j in active[a_i + 1 :]:
            if players[i].team == players[j].team:
                continue
            same = target[i] == target[j]
            swap = target[i] == (players[j].x, players[j].y) and target[j] == (players[i].x, players[i].y)
            if same or swap:
                for k in (i, j):
                    if m.half(target[k][0]) != players[k].team:
                        tagged.add(k)

    # 3. tagged players leave the board; a carried flag goes home
    for i in sorted(tagged):
        p = players[i]
        if p.carrying:
            state.carrier[1 - p.team] = None
            p.carrying = False
        p.x, p.y, p.respawn = -1, -1, RESPAWN_TICKS
        events.append(("tag", i))

    # 4. everyone else moves
    for i, (x, y) in target.items():
        if i not in tagged:
            players[i].x, players[i].y = x, y

    # respawns: count down, then return on the first free base cell
    for i, p in enumerate(players):
        if p.respawn and i not in tagged:
            p.respawn -= 1
            if p.respawn == 0:
                taken = {(q.x, q.y) for q in players if q.active and q is not p}
                free = [c for c in m.bases[p.team] if c not in taken and c != m.flags[p.team]]
                if free:
                    p.x, p.y = free[0]
                    events.append(("respawn", i))
                else:
                    p.respawn = 1  # base full: try again next tick

    # 5. pickup: standing on the enemy flag while it is home
    for team in (0, 1):
        enemy = 1 - team
        if state.carrier[enemy] is not None:
            continue
        on_flag = [i for i, p in enumerate(players) if p.team == team and p.active and (p.x, p.y) == m.flags[enemy]]
        if on_flag:
            i = min(on_flag)
            players[i].carrying = True
            state.carrier[enemy] = i
            events.append(("pickup", i))

    # 6. capture: a carrier in their own base scores
    for i, p in enumerate(players):
        if p.carrying and p.active and (p.x, p.y) in m.bases[p.team]:
            state.score[p.team] += 1
            p.carrying = False
            state.carrier[1 - p.team] = None
            events.append(("capture", i))

    state.tick += 1
    return events


def fingerprint(state: State) -> str:
    """A canonical text form of the state, identical to spec/engine.ts's."""
    parts = [f"{state.tick}|{state.score[0]},{state.score[1]}|"]
    for p in state.players:
        parts.append(f"{p.team},{p.x},{p.y},{p.respawn},{int(p.carrying)};")
    return "".join(parts)


def state_hash(state: State) -> int:
    """FNV-1a over the fingerprint: short, and cheap to compute in both languages."""
    h = 0x811C9DC5
    for ch in fingerprint(state).encode():
        h = ((h ^ ch) * 0x01000193) & MASK
    return h

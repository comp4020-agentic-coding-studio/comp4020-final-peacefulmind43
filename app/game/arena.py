"""Arenas: where matches run, people take seats, and bots cover the rest (ADR 0011).

One ticker drives every arena at 4 Hz on a fixed clock. Inside a tick nothing
touches the database or the log: people's inputs are read from their seats,
bots choose from the state everyone saw at the previous tick, the engine
steps, and the new state is offered to every open page, which keeps only the
newest. Saving a finished match happens off the tick, in a thread.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field

from ..activity import visitor_label as label
from . import bots, engine

TICK_HZ = 4
PERIOD = 1 / TICK_HZ
GRACE_SECONDS = 5  # a closed page keeps its seat this long before a bot covers it
IDLE_SECONDS = 60  # an open page with no input for this long is covered too
BREAK_SECONDS = 10  # between matches
MAX_PEOPLE = 6  # in one shared arena: 3v3
MAX_ARENAS = 20  # private arenas are operator-only, so this guards memory, not abuse
PRIVATE_IDLE_SECONDS = 20  # a private arena with nobody in it closes


@dataclass
class Seat:
    team: int
    owner: str | None = None  # the visitor who holds this seat, if any
    held: int = engine.STAY  # direction being held down
    tap: int | None = None  # a one-shot direction, used once by the next tick
    seq: int = 0  # the newest input number seen
    pages: int = 0  # open pages of the owner
    left_at: float = 0.0  # when the owner's last page closed
    last_input: float = 0.0
    covering: bool = False  # the owner is away and a bot plays for them
    since_tick: int = 0  # when the current owner took the seat

    @property
    def human(self) -> bool:
        return self.owner is not None and not self.covering


class Page:
    """One open page's view of an arena. Messages that matter (a snapshot, a seat
    change, a capture) queue in order; tick states don't queue: a newer one
    replaces an older one, so a slow connection sees the newest state."""

    def __init__(self, visitor_id: str):
        self.visitor_id = visitor_id
        self.messages: list[tuple[str, dict]] = []
        self.latest_tick: dict | None = None
        self.wake = asyncio.Event()

    def send(self, event: str, data: dict) -> None:
        self.messages.append((event, data))
        self.wake.set()

    def offer_tick(self, data: dict) -> None:
        self.latest_tick = data
        self.wake.set()

    def drain(self) -> list[tuple[str, dict]]:
        out, self.messages = self.messages, []
        if self.latest_tick is not None:
            out.append(("tick", self.latest_tick))
            self.latest_tick = None
        self.wake.clear()
        return out


@dataclass
class Arena:
    id: str
    kind: str  # "shared" or "private"
    team_size: int
    seed: int
    max_ticks: int = engine.MAX_TICKS
    break_seconds: float = BREAK_SECONDS
    seats: list[Seat] = field(default_factory=list)
    bench: list[str] = field(default_factory=list)  # people waiting for the next match
    pages: list[Page] = field(default_factory=list)
    state: engine.State | None = None
    match_id: int | None = None
    matches_played: int = 0
    break_until: float = 0.0  # > 0 while between matches
    empty_since: float = 0.0
    spans: list[tuple[int, str, int, int]] = field(default_factory=list)  # seat, visitor, from, to

    # --- what pages are told -------------------------------------------------

    def seat_view(self) -> list[dict]:
        out = []
        for i, s in enumerate(self.seats):
            out.append(
                {
                    "seat": i,
                    "team": "blue" if s.team == 0 else "red",
                    "kind": "human" if s.human else "bot",
                    "label": label(s.owner) if s.human else "Bot",
                    "covering": label(s.owner) if s.owner and s.covering else None,
                }
            )
        return out

    def match_view(self) -> dict:
        m = self.state.map
        return {
            "id": self.match_id,
            "seed": self.state.seed,
            "team_size": self.team_size,
            "rules_version": engine.RULES_VERSION,
            "tick_hz": TICK_HZ,
            "max_ticks": self.state.max_ticks,
            "map": {
                "width": m.width,
                "height": m.height,
                "walls": sorted([x, y] for x, y in m.walls),
                "flags": [list(f) for f in m.flags],
                "bases": [[list(c) for c in base] for base in m.bases],
            },
        }

    def tick_view(self) -> dict:
        s = self.state
        return {
            "match_id": self.match_id,
            "tick": s.tick,
            "score": list(s.score),
            "players": [{"x": p.x, "y": p.y, "respawn": p.respawn, "carrying": p.carrying} for p in s.players],
            "break": max(0.0, round(self.break_until - time.monotonic(), 1)) if self.break_until else 0,
        }

    def seat_of(self, visitor_id: str) -> int | None:
        for i, s in enumerate(self.seats):
            if s.owner == visitor_id:
                return i
        return None

    def snapshot(self, visitor_id: str) -> dict:
        return {
            "arena": self.id,
            "match": self.match_view(),
            "seats": self.seat_view(),
            "you": self.seat_of(visitor_id),
            "bench": visitor_id in self.bench,
            "tick": self.tick_view(),
        }

    def tell_all(self, event: str, data: dict) -> None:
        for page in self.pages:
            page.send(event, data)

    def seats_changed(self) -> None:
        self.tell_all("seats", {"seats": self.seat_view()})

    def people(self) -> list[str]:
        """Everyone who belongs to this arena now: seat owners and the bench."""
        return [s.owner for s in self.seats if s.owner] + list(self.bench)


class Hall:
    """All the arenas, the ticker, and the rules for who sits where."""

    def __init__(self, store):
        self.arenas: dict[str, Arena] = {}
        self.store = store  # saves matches off the tick (see app/game/store.py)
        self.on_log = None  # set by the app: (kind, visitor_id, detail) for the activity log

    # --- arenas and matches --------------------------------------------------

    def shared(self) -> Arena:
        return self.arenas.get("main") or self.open_arena("main", "shared", 2, secrets.randbelow(2**32))

    def open_arena(self, arena_id: str, kind: str, team_size: int, seed: int, **options) -> Arena:
        if len(self.arenas) >= MAX_ARENAS and arena_id not in self.arenas:
            raise RuntimeError("too many arenas")
        arena = Arena(arena_id, kind, team_size, seed, **options)
        self.arenas[arena_id] = arena
        self.start_match(arena, people=[])
        return arena

    def start_match(self, arena: Arena, people: list[str]) -> None:
        if arena.kind == "shared":
            arena.team_size = 2 if len(people) <= 4 else 3
        seed = arena.seed + arena.matches_played if arena.kind == "private" else secrets.randbelow(2**32)
        arena.state = engine.new_game(seed, arena.team_size)
        arena.state.max_ticks = arena.max_ticks
        arena.matches_played += 1
        arena.seats = [Seat(team=0 if i < arena.team_size else 1) for i in range(2 * arena.team_size)]
        arena.bench = []
        arena.spans = []
        arena.break_until = 0.0
        arena.match_id = self.store.start(arena)
        for visitor_id in people:
            self.seat_person(arena, visitor_id, announce=False)
        for page in arena.pages:
            page.send("match", arena.snapshot(page.visitor_id))

    def end_match(self, arena: Arena, now: float) -> None:
        s = arena.state
        for i, seat in enumerate(arena.seats):
            if seat.owner:
                arena.spans.append((i, seat.owner, seat.since_tick, s.tick))
        self.store.finish(arena.match_id, s, list(arena.spans))
        arena.tell_all("over", {"match_id": arena.match_id, "score": list(s.score)})
        if self.on_log:
            self.on_log("match_end", None, {"arena": arena.id, "score": f"{s.score[0]}-{s.score[1]}"})
        arena.break_until = now + arena.break_seconds

    # --- people --------------------------------------------------------------

    def find(self, visitor_id: str) -> Arena | None:
        for arena in self.arenas.values():
            if visitor_id in arena.people():
                return arena
        return None

    def seat_person(self, arena: Arena, visitor_id: str, announce: bool = True) -> int | None:
        """Give a newcomer a bot's seat on the team with fewer people, or the
        bench if every seat is a person (ADR 0011)."""
        humans = [sum(1 for s in arena.seats if s.owner and s.team == t) for t in (0, 1)]
        order = (0, 1) if humans[0] <= humans[1] else (1, 0)
        for team in order:
            free = [i for i, s in enumerate(arena.seats) if s.team == team and s.owner is None]
            # a seat whose owner has gone (no open page) can be taken too
            free += [i for i, s in enumerate(arena.seats) if s.team == team and s.owner and s.pages == 0]
            if free:
                i = free[0]
                seat = arena.seats[i]
                if seat.owner:
                    arena.spans.append((i, seat.owner, seat.since_tick, arena.state.tick))
                arena.seats[i] = Seat(team=team, owner=visitor_id, last_input=time.monotonic(), since_tick=arena.state.tick)
                if announce:
                    arena.seats_changed()
                    arena.tell_all("moment", {"kind": "join", "seat": i, "label": label(visitor_id)})
                if self.on_log:
                    self.on_log("join", visitor_id, {"arena": arena.id, "team": "blue" if team == 0 else "red"})
                return i
        arena.bench.append(visitor_id)
        return None

    def arrive(self, visitor_id: str, arena_id: str | None) -> tuple[Arena, Page]:
        """A page opened. Reattach to the person's seat, or find them one."""
        arena = self.find(visitor_id)
        if arena is not None and arena_id and arena.id != arena_id:
            self.release(arena, visitor_id)  # moving to another arena
            arena = None
        if arena is None:
            if arena_id:
                arena = self.arenas.get(arena_id)
                if arena is None:
                    raise KeyError(arena_id)
            else:
                arena = self.place_in_shared(visitor_id)
            if visitor_id not in arena.people():
                self.seat_person(arena, visitor_id)
        page = Page(visitor_id)
        arena.pages.append(page)
        i = arena.seat_of(visitor_id)
        if i is not None:
            seat = arena.seats[i]
            seat.pages += 1
            if seat.covering:
                seat.covering = False
                seat.last_input = time.monotonic()
                arena.seats_changed()
                arena.tell_all("moment", {"kind": "reclaim", "seat": i, "label": label(visitor_id)})
                if self.on_log:
                    self.on_log("reclaim", visitor_id, {"arena": arena.id})
        page.send("snapshot", arena.snapshot(visitor_id))
        return arena, page

    def place_in_shared(self, visitor_id: str) -> Arena:
        """The shared arena, or a second one once the first has six people."""
        for arena in self.arenas.values():
            if arena.kind == "shared" and len(arena.people()) < MAX_PEOPLE:
                return arena
        if "main" not in self.arenas:
            return self.shared()
        n = sum(1 for a in self.arenas.values() if a.kind == "shared") + 1
        return self.open_arena(f"shared-{n}", "shared", 2, secrets.randbelow(2**32))

    def release(self, arena: Arena, visitor_id: str) -> None:
        i = arena.seat_of(visitor_id)
        if i is not None:
            seat = arena.seats[i]
            arena.spans.append((i, visitor_id, seat.since_tick, arena.state.tick))
            arena.seats[i] = Seat(team=seat.team)
            arena.seats_changed()
        if visitor_id in arena.bench:
            arena.bench.remove(visitor_id)

    def depart(self, arena: Arena, page: Page) -> None:
        if page in arena.pages:
            arena.pages.remove(page)
        i = arena.seat_of(page.visitor_id)
        if i is not None:
            seat = arena.seats[i]
            seat.pages = max(0, seat.pages - 1)
            if seat.pages == 0:
                seat.left_at = time.monotonic()
        elif page.visitor_id in arena.bench and not any(p.visitor_id == page.visitor_id for p in arena.pages):
            arena.bench.remove(page.visitor_id)

    def input(self, visitor_id: str, direction: int, held: bool, seq: int) -> bool:
        """Record an input. Returns False if the visitor has no seat."""
        arena = self.find(visitor_id)
        i = arena.seat_of(visitor_id) if arena else None
        if i is None:
            return False
        seat = arena.seats[i]
        if seq <= seat.seq:
            return True  # an older input arriving late: ignored
        seat.seq = seq
        seat.last_input = time.monotonic()
        if held:
            seat.held = direction
            if direction != engine.STAY:
                seat.tap = direction  # a press shorter than a tick still moves once
        else:
            seat.tap = direction
        if seat.covering and seat.pages > 0:  # back from being idle
            seat.covering = False
            arena.seats_changed()
            arena.tell_all("moment", {"kind": "reclaim", "seat": i, "label": label(visitor_id)})
        return True

    # --- the ticker ----------------------------------------------------------

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        start = loop.time()
        n = 0
        while True:
            n += 1
            due = start + n * PERIOD  # a fixed clock: ticks never drift
            await asyncio.sleep(max(0.0, due - loop.time()))
            late = loop.time() - due
            if late > PERIOD:  # fell more than a tick behind: skip, don't burst
                n += int(late / PERIOD)
            began = time.perf_counter()
            for arena in list(self.arenas.values()):
                try:
                    self.tick(arena, time.monotonic())
                except Exception as err:  # one broken arena must not stop the others
                    print(json.dumps({"event": "tick_error", "arena": arena.id, "error": repr(err)}), flush=True)
            spent = time.perf_counter() - began
            if spent > PERIOD / 2:
                print(json.dumps({"event": "slow_tick", "ms": round(spent * 1000), "late_ms": round(late * 1000)}), flush=True)

    def tick(self, arena: Arena, now: float) -> None:
        if arena.break_until:
            if now >= arena.break_until:
                present = [v for v in arena.people() if any(p.visitor_id == v for p in arena.pages)]
                self.start_match(arena, present)
            return

        # who has gone: a closed page after the grace period, an idle one after a minute
        changed = False
        for i, seat in enumerate(arena.seats):
            if not seat.owner or seat.covering:
                continue
            gone = seat.pages == 0 and now - seat.left_at >= GRACE_SECONDS
            idle = seat.pages > 0 and now - seat.last_input >= IDLE_SECONDS
            if gone or idle:
                seat.covering = True
                seat.held, seat.tap = engine.STAY, None
                changed = True
                arena.tell_all("moment", {"kind": "takeover", "seat": i, "label": label(seat.owner)})
                if self.on_log:
                    self.on_log("takeover", seat.owner, {"arena": arena.id, "why": "left" if gone else "idle"})
        if changed:
            arena.seats_changed()

        # this tick's actions: people from their seats, bots from the state as it
        # stands, which is the state everyone was shown after the previous tick
        s = arena.state
        actions = []
        for i, seat in enumerate(arena.seats):
            if seat.human:
                actions.append(seat.tap if seat.tap is not None else seat.held)
                seat.tap = None
            else:
                actions.append(bots.scripted_action(s, i))
        events = engine.step(s, actions)

        for name, i in events:
            if name in ("tag", "pickup", "capture"):
                seat = arena.seats[i]
                arena.tell_all("moment", {"kind": name, "seat": i, "label": label(seat.owner) if seat.human else "Bot"})
        view = arena.tick_view()
        for page in arena.pages:
            page.offer_tick(view)
        if s.done:
            self.end_match(arena, now)

        if arena.kind == "private":
            if arena.pages:
                arena.empty_since = 0.0
            elif not arena.empty_since:
                arena.empty_since = now
            elif now - arena.empty_since > PRIVATE_IDLE_SECONDS:
                self.arenas.pop(arena.id, None)

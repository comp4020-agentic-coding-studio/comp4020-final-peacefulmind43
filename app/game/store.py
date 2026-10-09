"""Saving matches (ADR 0011: never inside a tick).

Starting a match inserts its row at once, because pages need its id; that
happens between matches, not during one. Finishing a match is saved in a
thread, so a slow disk can't delay the next tick.
"""

import asyncio
import time

from .. import db
from . import engine


class Store:
    def start(self, arena) -> int:
        s = arena.state
        with db.connect() as conn:
            cur = conn.execute(
                """INSERT INTO matches (arena, seed, team_size, rules_version, tick_hz, max_ticks, started_at, turn_deadline)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
                (arena.id, s.seed, arena.team_size, engine.RULES_VERSION, s.max_ticks, int(time.time()), arena.deadline),
            )
            return cur.lastrowid

    def finish(self, match_id: int, state: engine.State, spans: list) -> None:
        score, ticks = list(state.score), state.tick
        try:
            asyncio.get_running_loop().run_in_executor(None, self._finish, match_id, score, ticks, spans)
        except RuntimeError:  # no event loop (tests, scripts): save directly
            self._finish(match_id, score, ticks, spans)

    @staticmethod
    def _finish(match_id: int, score: list[int], ticks: int, spans: list) -> None:
        with db.connect() as conn:
            conn.execute(
                """UPDATE matches SET status = 'finished', score_blue = ?, score_red = ?, ticks = ?, ended_at = ?
                   WHERE id = ? AND status = 'live'""",
                (score[0], score[1], ticks, int(time.time()), match_id),
            )
            conn.executemany(
                "INSERT INTO seat_spans (match_id, seat, visitor_id, from_tick, to_tick) VALUES (?, ?, ?, ?, ?)",
                [(match_id, seat, visitor, start, end) for seat, visitor, start, end in spans if start <= end],
            )

    @staticmethod
    def interrupt_leftovers() -> int:
        """On start-up: matches still live were cut off by a restart."""
        with db.connect() as conn:
            return conn.execute("UPDATE matches SET status = 'interrupted', ended_at = ? WHERE status = 'live'", (int(time.time()),)).rowcount

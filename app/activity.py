"""What visitors do: one log line per action, kept and shown live (ADR 0006).

Every action goes to stdout as a JSON line, in full, and into the events
table. The live view applies ADR 0003's rule: a visitor who hasn't tested in
the current round sees that things happened, not what the tests were.
"""

import asyncio
import hashlib
import json
import time

subscribers: set[tuple[asyncio.Queue, str | None]] = set()

KINDS = {"visit", "test", "refused", "watch_start", "watch_end", "readme", "reveal", "pick"}
# What these say about a rule is hidden from visitors who haven't tested this
# round (ADR 0003); the rest only says that something happened.
SENSITIVE = {"test", "pick"}


def visitor_label(visitor_id: str | None) -> str:
    """A short public name for an anonymous visitor. The cookie itself is never
    shown or logged, since anyone holding it could act as that visitor."""
    if not visitor_id:
        return "A new visitor"
    return "Visitor " + hashlib.sha256(visitor_id.encode()).hexdigest()[:6]


def record(conn, kind: str, visitor_id: str | None, round_id: int | None, detail: dict | None = None) -> int:
    """Log one action: stdout, the events table, and every open log view."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind of event: {kind}")
    detail = detail or {}
    at = int(time.time())
    cur = conn.execute(
        "INSERT INTO events (at, visitor_id, round_id, kind, detail) VALUES (?, ?, ?, ?, ?)",
        (at, visitor_id, round_id, kind, json.dumps(detail)),
    )
    print(json.dumps({"event": kind, "visitor": visitor_label(visitor_id), "at": at, **detail}), flush=True)
    event_id = cur.lastrowid
    if subscribers:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        stats = counts(conn)
        for queue, viewer in list(subscribers):
            queue.put_nowait({**view(row, viewer, unlocked(conn, viewer)), "counts": stats})
    return event_id


def unlocked(conn, viewer: str | None) -> int | None:
    """The open round's id if this viewer has tested in it (ADR 0003)."""
    if not viewer:
        return None
    row = conn.execute(
        """SELECT r.id FROM rounds r JOIN trials t ON t.round_id = r.id
           WHERE r.revealed_at IS NULL AND r.closed_at IS NULL AND t.visitor_id = ? LIMIT 1""",
        (viewer,),
    ).fetchone()
    return row[0] if row else None


def describe(kind: str, detail: dict, full: bool) -> str:
    if kind == "pick":
        if not full:
            return "backed a rule"
        text = f"backed “{detail['rule']['label']}”"
        if detail.get("changed_from"):
            text += f" (instead of “{detail['changed_from']['label']}”)"
        return text
    if kind == "test":
        if not full:
            return "ran a test"
        text = f"tested “{detail['rule']['label']}”: {detail['cagr'] * 100:.1f}% a year, Sharpe {detail['sharpe']:.2f}"
        if detail.get("confidence") is not None:
            text += f", chance the timing helps {detail['confidence'] * 100:.0f}%"
        return text
    return {
        "visit": "opened the room" + (" (others' tests hidden)" if detail.get("locked") else ""),
        "refused": "tried a rule that isn't on the menu",
        "watch_start": "came into the room",
        "watch_end": f"left the room after {detail.get('seconds', 0)} s",
        "readme": "read the About page",
        "reveal": (
            "revealed the round early (operator key)" if detail.get("early") else "revealed the round on schedule"
        ),
    }[kind]


def view(row, viewer: str | None, viewer_round: int | None) -> dict:
    """One event as `viewer` may see it."""
    detail = json.loads(row["detail"])
    mine = viewer is not None and row["visitor_id"] == viewer
    full = mine or row["kind"] not in SENSITIVE or (viewer_round is not None and row["round_id"] == viewer_round)
    out = {
        "id": row["id"],
        "at": row["at"],
        "visitor": "The room" if row["kind"] == "reveal" else visitor_label(row["visitor_id"]),
        "event": row["kind"],
        "text": describe(row["kind"], detail, full),
    }
    if full:
        out["detail"] = {**detail, "mine": mine}
    return out


def counts(conn) -> dict:
    hour_ago = int(time.time()) - 3600
    tests, visitors = conn.execute(
        "SELECT count(*) FILTER (WHERE kind = 'test'), count(DISTINCT visitor_id) FROM events WHERE at >= ?",
        (hour_ago,),
    ).fetchone()
    return {"watching": watching(), "tests_last_hour": tests, "visitors_last_hour": visitors}


# Who has the room open right now: set by the room's event stream in main.py.
_watchers: dict[int, str | None] = {}


def watching() -> int:
    named = {v for v in _watchers.values() if v}
    return len(named) + sum(1 for v in _watchers.values() if not v)


def watch(token: int, visitor_id: str | None) -> None:
    _watchers[token] = visitor_id


def unwatch(token: int) -> None:
    _watchers.pop(token, None)

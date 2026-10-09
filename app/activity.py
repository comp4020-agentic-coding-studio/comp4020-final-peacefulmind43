"""What visitors do, kept and shown live (ADR 0006, carried over to the game).

Every action goes to stdout as one JSON line and into the events table, and
out to every open /log page. This is for actions people take now and then
(arriving, joining a seat, leaving): moves within a match happen several times
a second and are kept with the match instead (ADR 0011: nothing is written to
the database inside a tick).
"""

import asyncio
import hashlib
import json
import time

subscribers: set[asyncio.Queue] = set()

KINDS = {"visit", "readme", "join", "leave", "takeover", "reclaim", "match_end", "watch_start", "watch_end",
         "tag", "pickup", "capture"}


def visitor_label(visitor_id: str | None) -> str:
    """A short public name for an anonymous visitor. The cookie itself is never
    shown or logged, since anyone holding it could act as that visitor."""
    if not visitor_id:
        return "A new visitor"
    return "Visitor " + hashlib.sha256(visitor_id.encode()).hexdigest()[:6]


def record(conn, kind: str, visitor_id: str | None, detail: dict | None = None) -> int:
    """Log one action: stdout, the events table, and every open log view."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind of event: {kind}")
    detail = detail or {}
    at = int(time.time())
    cur = conn.execute(
        "INSERT INTO events (at, visitor_id, round_id, kind, detail) VALUES (?, ?, NULL, ?, ?)",
        (at, visitor_id, kind, json.dumps(detail)),
    )
    print(json.dumps({"event": kind, "visitor": visitor_label(visitor_id), "at": at, **detail}), flush=True)
    if subscribers:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone()
        entry = view(row)
        for queue in list(subscribers):
            queue.put_nowait(entry)
    return cur.lastrowid


def describe(kind: str, detail: dict) -> str:
    return {
        "visit": "opened the game",
        "readme": "read the About page",
        "join": f"took a seat on {detail.get('team', 'a team')}",
        "leave": "left their seat",
        "takeover": "went quiet; a bot is covering their seat",
        "reclaim": "came back and took their seat back",
        "match_end": f"finished a match {detail.get('score', '')}".strip(),
        "watch_start": "started watching",
        "watch_end": f"stopped watching after {detail.get('seconds', 0)} s",
        "tag": "got caught",
        "pickup": "picked up the flag",
        "capture": "scored!",
    }.get(kind, kind)


def view(row) -> dict:
    detail = json.loads(row["detail"])
    return {
        "id": row["id"],
        "at": row["at"],
        "visitor": visitor_label(row["visitor_id"]) if row["visitor_id"] or row["kind"] not in ("tag", "pickup", "capture")
        else f"A bot ({detail.get('bot') or 'scripted'})",
        "event": row["kind"],
        "text": describe(row["kind"], detail),
        "detail": detail,
    }

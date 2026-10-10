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
         "tag", "pickup", "capture", "pause", "resume"}


def visitor_label(visitor_id: str | None) -> str:
    """A short public name for an anonymous visitor. The cookie itself is never
    shown or logged, since anyone holding it could act as that visitor."""
    if not visitor_id:
        return "A new visitor"
    return "Visitor " + hashlib.sha256(visitor_id.encode()).hexdigest()[:6]


MOMENTS = ("tag", "pickup", "capture")


def who(kind: str, visitor_id: str | None, detail: dict) -> str:
    """Who did it, as the log shows it: a person's public label, a bot's name,
    or the arena for a match that ended."""
    if visitor_id:
        return visitor_label(visitor_id)
    if kind in MOMENTS:
        return f"A bot ({detail.get('bot') or 'scripted'})"
    if kind == "match_end":
        return f"Arena {detail.get('arena', '?')}"
    return "A new visitor"


def record(conn, kind: str, visitor_id: str | None, detail: dict | None = None) -> int:
    """Log one action: stdout, the events table, and every open log view.
    The stdout line ends with `text`, the same sentence /log shows."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind of event: {kind}")
    detail = detail or {}
    at = int(time.time())
    cur = conn.execute(
        "INSERT INTO events (at, visitor_id, round_id, kind, detail) VALUES (?, ?, NULL, ?, ?)",
        (at, visitor_id, kind, json.dumps(detail)),
    )
    name = who(kind, visitor_id, detail)
    line = {"event": kind, "visitor": name, "at": at, **detail, "text": f"{name} {describe(kind, detail)}"}
    print(json.dumps(line), flush=True)
    if subscribers:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone()
        entry = view(row)
        for queue in list(subscribers):
            queue.put_nowait(entry)
    return cur.lastrowid


def describe(kind: str, detail: dict) -> str:
    seat = detail.get("seat")
    player = f"player {seat + 1}" if isinstance(seat, int) else "their seat"
    on = f"{player}, {detail['team']}" if "team" in detail and isinstance(seat, int) else player
    at = f" ({on})" if isinstance(seat, int) else ""  # older lines have no seat
    match = f"match {detail['match']}" if detail.get("match") is not None else "the match"
    return {
        "visit": "opened the game",
        "readme": "read the About page",
        "join": f"joined {detail.get('team', 'a team')}" + (f" as {player}" if isinstance(seat, int) else "")
        + (f" in {match}" if detail.get("match") is not None else ""),
        "leave": "left the bench" if detail.get("bench") else f"closed the game page{at}",
        "takeover": f"{'has gone' if detail.get('why') == 'left' else 'went quiet'}; a bot now plays {player} for them",
        "reclaim": f"came back to {player}",
        "match_end": f"finished {match}, blue {detail.get('score', '?').replace('-', ', red ', 1)}",
        "watch_start": "started watching",
        "watch_end": f"stopped watching after {detail.get('seconds', 0)} s",
        "tag": f"got caught{at}",
        "pickup": f"picked up the flag{at}",
        "capture": f"scored!{at}",
        "pause": f"paused {match}{at}",
        "resume": f"resumed {match}{at}",
    }.get(kind, kind)


def view(row) -> dict:
    detail = json.loads(row["detail"])
    return {
        "id": row["id"],
        "at": row["at"],
        "visitor": who(row["kind"], row["visitor_id"], detail),
        "event": row["kind"],
        "text": describe(row["kind"], detail),
        "detail": detail,
    }

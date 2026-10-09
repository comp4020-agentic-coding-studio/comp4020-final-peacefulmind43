"""Capture the flag with bot teammates (ADR 0009)."""

import asyncio
import hmac
import html
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import markdown
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import activity, db
from .game import engine
from .game.arena import Hall
from .game.store import Store

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
COOKIE = "visitor"


from .game import policy  # noqa: E402

hall = Hall(Store(), bot=policy.deployed())
hall.watch_bot = policy.on_show()


def log_soon(kind: str, visitor_id: str | None, detail: dict) -> None:
    """The arena reports things worth logging during a tick; they are written
    just after it, so the tick itself never touches the database."""

    def write():
        with db.connect() as conn:
            activity.record(conn, kind, visitor_id, detail)

    asyncio.get_running_loop().call_soon(write)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    interrupted = Store.interrupt_leftovers()
    if interrupted:
        print(json.dumps({"event": "matches_interrupted", "count": interrupted}), flush=True)
    hall.on_log = log_soon
    hall.shared()  # idle until someone arrives
    ticker = asyncio.create_task(hall.run())
    yield
    ticker.cancel()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


def visitor(request: Request) -> tuple[str, bool]:
    """The visitor's id from their cookie, or a new one (and whether it's new)."""
    existing = request.cookies.get(COOKIE)
    return (existing, False) if existing else (secrets.token_urlsafe(18), True)


def remember(response, visitor_id: str, new: bool):
    if new:
        response.set_cookie(COOKIE, visitor_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
    return response


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# --- pages ------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    me, new = visitor(request)
    with db.connect() as conn:
        activity.record(conn, "visit", me)
    return remember(templates.TemplateResponse(request, "game.html", {}), me, new)


@app.get("/readme/", response_class=HTMLResponse)
async def readme(request: Request):
    body = markdown.markdown((ROOT / "README.md").read_text(), extensions=["fenced_code", "tables"])
    with db.connect() as conn:
        activity.record(conn, "readme", request.cookies.get(COOKIE))
    return templates.TemplateResponse(request, "readme.html", {"body": body})


# --- the arena (ADR 0011) ---------------------------------------------------


@app.get("/arena/events")
async def arena_events(request: Request, arena: str | None = None):
    me, new = visitor(request)
    try:
        room, page = hall.arrive(me, arena)
    except KeyError:
        raise HTTPException(404, "No such arena.")

    async def stream():
        try:
            while True:
                try:
                    await asyncio.wait_for(page.wake.wait(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                for event, data in page.drain():
                    yield sse(event, data)
        finally:
            hall.depart(room, page)

    response = StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
    return remember(response, me, new)


@app.post("/arena/input", status_code=204)
async def arena_input(request: Request):
    me = request.cookies.get(COOKIE)
    body = await request.json()
    direction, seq, turn = body.get("dir"), body.get("seq"), body.get("turn")
    if direction not in range(5) or not isinstance(seq, int) or not (turn is None or isinstance(turn, int)):
        raise HTTPException(400, "Send dir (0-4), seq (an increasing number) and turn (the turn you're choosing for).")
    if not me or not hall.choose(me, direction, seq, turn):
        raise HTTPException(409, "You don't have a seat. Open the game first.")


def operator(request: Request) -> None:
    """Private arenas need the operator key (for the spec and for demos)."""
    expected = os.environ.get("OPERATOR_KEY")
    if not expected:
        raise HTTPException(404, "Not found.")
    if not hmac.compare_digest(request.headers.get("x-operator-key", "").encode(), expected.encode()):
        raise HTTPException(403, "That key doesn't open anything.")


@app.post("/api/arenas")
async def create_arena(request: Request):
    operator(request)
    body = await request.json()
    team_size, seed = body.get("team_size"), body.get("seed")
    max_ticks, break_seconds = body.get("max_ticks", engine.MAX_TICKS), body.get("break_seconds", 10)
    deadline = body.get("deadline_seconds", 2.0)
    if team_size not in engine.SIZES or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise HTTPException(400, "Send team_size (2 or 3) and seed (0 to 2^32 - 1).")
    if not isinstance(max_ticks, int) or not 1 <= max_ticks <= engine.MAX_TICKS or not 0 <= break_seconds <= 60:
        raise HTTPException(400, f"max_ticks must be 1-{engine.MAX_TICKS} and break_seconds 0-60.")
    if not isinstance(deadline, (int, float)) or not 0.15 <= deadline <= 10:
        raise HTTPException(400, "deadline_seconds must be 0.15-10.")
    try:
        arena = hall.open_arena(
            f"p-{secrets.token_urlsafe(6)}", "private", team_size, seed,
            max_ticks=max_ticks, break_seconds=break_seconds, deadline=float(deadline),
        )
    except RuntimeError:
        raise HTTPException(503, "Too many arenas are open. Try again in a minute.")
    return {"id": arena.id}


@app.get("/api/matches/recent")
async def api_recent_matches():
    """The last 20 finished matches, with how many people played in each."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT m.id, m.arena, m.score_blue, m.score_red, m.ticks, m.team_size, m.ended_at,
                      (SELECT count(DISTINCT visitor_id) FROM seat_spans s WHERE s.match_id = m.id) AS people
               FROM matches m WHERE m.status = 'finished' ORDER BY m.id DESC LIMIT 20"""
        ).fetchall()
    return [
        {"id": r["id"], "arena": r["arena"], "score": [r["score_blue"], r["score_red"]], "ticks": r["ticks"],
         "team_size": r["team_size"], "people": r["people"], "ended_at": r["ended_at"]}
        for r in rows
    ]


@app.get("/api/matches/{match_id}")
async def api_match(match_id: int):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such match.")
    return {
        "id": row["id"],
        "arena": row["arena"],
        "status": row["status"],
        "score": [row["score_blue"], row["score_red"]],
        "ticks": row["ticks"],
        "team_size": row["team_size"],
        "seed": row["seed"],
        "rules_version": row["rules_version"],
    }


# --- the log (ADR 0006) -----------------------------------------------------


def log_snapshot(conn, limit: int = 100) -> dict:
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"events": [activity.view(r) for r in rows]}


@app.get("/log", response_class=HTMLResponse)
async def log_page(request: Request):
    with db.connect() as conn:
        snap = log_snapshot(conn)
    return templates.TemplateResponse(request, "log.html", {"log": snap})


@app.get("/api/log")
async def api_log():
    with db.connect() as conn:
        return log_snapshot(conn)


@app.get("/log/events")
async def log_events():
    queue: asyncio.Queue = asyncio.Queue()
    activity.subscribers.add(queue)

    async def stream():
        try:
            yield sse("snapshot", {})
            while True:
                try:
                    yield sse("log", await asyncio.wait_for(queue.get(), timeout=15))
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            activity.subscribers.discard(queue)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# --- the engine, for checking (ADR 0010) -------------------------------------


@app.post("/api/engine/simulate")
async def api_simulate(request: Request):
    """Run the game engine on given inputs and return every tick's fingerprint,
    so the spec can check it against an independent engine. Pure computation:
    nothing is stored."""
    body = await request.json()
    seed, team_size, actions = body.get("seed"), body.get("team_size"), body.get("actions")
    if not isinstance(seed, int) or team_size not in engine.SIZES or not isinstance(actions, list):
        raise HTTPException(400, "Send seed (int), team_size (2 or 3) and actions (a list of ticks).")
    if len(actions) > engine.MAX_TICKS or any(
        not isinstance(t, list) or len(t) != 2 * team_size or any(not isinstance(a, int) for a in t) for t in actions
    ):
        raise HTTPException(400, f"Each tick needs {2 * team_size} integer actions, at most {engine.MAX_TICKS} ticks.")
    state = engine.new_game(seed, team_size)
    fingerprints, events = [], []
    for tick_actions in actions:
        for name, seat in engine.step(state, tick_actions):
            events.append([state.tick, name, seat])
        fingerprints.append(engine.fingerprint(state))
    m = state.map
    return {
        "rules_version": engine.RULES_VERSION,
        "map": {"width": m.width, "height": m.height, "walls": sorted([x, y] for x, y in m.walls)},
        "fingerprints": fingerprints,
        "events": events,
        "hash": engine.state_hash(state),
    }


@app.exception_handler(HTTPException)
async def plain_errors(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    return HTMLResponse(
        # the detail can echo what the visitor sent, so it is escaped
        f'<!doctype html><html lang="en"><title>Error</title><p>{html.escape(str(exc.detail))}</p>'
        '<p><a href="/">Back to the game</a></p></html>',
        status_code=exc.status_code,
        headers=exc.headers,
    )

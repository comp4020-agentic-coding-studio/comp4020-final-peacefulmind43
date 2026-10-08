"""Capture the flag with bot teammates (ADR 0009)."""

import asyncio
import html
import json
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

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
COOKIE = "visitor"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    yield


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

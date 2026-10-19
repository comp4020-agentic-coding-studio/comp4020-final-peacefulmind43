"""Capture the flag with bot teammates (ADR 0009)."""

import asyncio
import functools
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

import markdown
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import activity, db, requestlog
from .game import engine, study, teammate_eval
from .game.arena import Hall
from .game.store import Store

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
COOKIE = "visitor"


from .game import policy  # noqa: E402

hall = Hall(Store(), bot=policy.deployed(), balanced=policy.balanced())
hall.watch_bot = policy.on_show()

# Choices arrive several times a second during a crit: each is printed at once,
# and written to the database in batches, in a thread (ADR 0014).
choice_buffer: list[tuple] = []


def flush_choices() -> None:
    if not choice_buffer:
        return
    batch, choice_buffer[:] = list(choice_buffer), []
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO game_events (at, match_id, arena, visitor_id, seat, turn, dir) VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch,
        )


async def flush_choices_forever() -> None:
    while True:
        await asyncio.sleep(2)
        try:
            await asyncio.to_thread(flush_choices)
        except Exception as err:  # never lose the server over a log write
            print(json.dumps({"event": "log_error", "error": repr(err)}), flush=True)


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
    flusher = asyncio.create_task(flush_choices_forever())
    yield
    ticker.cancel()
    flusher.cancel()
    flush_choices()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
# one line per request, with an id that also tags the events it logs (week 10)
app.add_middleware(requestlog.RequestLog, cookie=COOKIE, label=activity.visitor_label)
templates = Jinja2Templates(directory=HERE / "templates")


@functools.cache
def asset(name: str) -> str:
    """A static file's URL with a hash of its contents, so a browser never runs
    an old script against a new page after a deploy."""
    digest = hashlib.sha256((HERE / "static" / name).read_bytes()).hexdigest()[:10]
    return f"/static/{name}?v={digest}"


templates.env.globals["asset"] = asset


def visitor(request: Request) -> tuple[str, bool]:
    """The visitor's id from their cookie, or a new one (and whether it's new)."""
    existing = request.cookies.get(COOKIE)
    return (existing, False) if existing else (secrets.token_urlsafe(18), True)


def served_over_https(request: Request) -> bool:
    """Fly ends TLS and passes the request on over http, saying so in
    x-forwarded-proto; uvicorn's --proxy-headers also puts it in the scheme."""
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def remember(request: Request, response, visitor_id: str, new: bool):
    """Set the visitor cookie: HttpOnly (no script reads it), SameSite=Lax (not
    sent by other sites' forms), and Secure when the page came over https, so
    it never travels in the clear. Over plain http, as on a laptop, Secure
    would stop the browser sending it back, so it is left off there. Over
    https an older cookie is set again, so cookies made before Secure get it."""
    secure = served_over_https(request)
    if new or secure:
        response.set_cookie(COOKIE, visitor_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax", secure=secure)
    return response


async def json_object(request: Request) -> dict:
    """A POST's body as a JSON object; an empty body is an empty object.
    Anything else is the sender's mistake, so it gets a 400, never a 500."""
    raw = await request.body()
    if not raw.strip():
        return {}
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError):  # not JSON, or not UTF-8
        body = None
    if not isinstance(body, dict):
        raise HTTPException(400, "Send a JSON object.")
    return body


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# --- pages ------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    me, new = visitor(request)
    with db.connect() as conn:
        activity.record(conn, "visit", me)
    return remember(request, templates.TemplateResponse(request, "game.html", {}), me, new)


REPO = "https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/blob/main/"


def repo_links(html_text: str) -> str:
    """The README links to files in the repo (doc/adr/...). Those files are on
    GitHub, not on this site, so on /readme/ the links point there."""
    return re.sub(r'href="(?![a-z]+:|/|#)([^"]+)"', lambda m: f'href="{REPO}{m.group(1)}"', html_text)


@app.get("/readme/", response_class=HTMLResponse)
async def readme(request: Request):
    body = repo_links(markdown.markdown((ROOT / "README.md").read_text(), extensions=["fenced_code", "tables"]))
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
    return remember(request, response, me, new)


MOVES = ("stay", "up", "down", "right", "left")  # engine actions 0-4, as the page's buttons name them


@app.post("/arena/input", status_code=204)
async def arena_input(request: Request):
    me = request.cookies.get(COOKIE)
    body = await json_object(request)
    direction, seq, turn = body.get("dir"), body.get("seq"), body.get("turn")
    if direction not in range(5) or not isinstance(seq, int) or not (turn is None or isinstance(turn, int)):
        raise HTTPException(400, "Send dir (0-4), seq (an increasing number) and turn (the turn you're choosing for).")
    info = hall.choose(me, direction, seq, turn) if me else None
    if info is None:
        raise HTTPException(409, "You don't have a seat. Open the game first.")
    if info["accepted"]:
        at = int(time.time())
        name, move = activity.visitor_label(me), MOVES[direction]
        print(json.dumps({"event": "choice", "request": requestlog.request_id.get(), "visitor": name, "at": at, "arena": info["arena"], "match": info["match"],
                          "turn": info["turn"], "seat": info["seat"], "dir": direction, "move": move,
                          "text": f"{name} chose {move} for player {info['seat'] + 1}, turn {info['turn']}"}), flush=True)
        if info["match"] is not None:
            choice_buffer.append((at, info["match"], info["arena"], me, info["seat"], info["turn"], direction))


@app.post("/arena/pause")
async def arena_pause(request: Request):
    """Pause your match or let it run (ADR 0015). The request says which, so two
    people asking for the same thing at once agree instead of undoing each
    other (ADR 0022)."""
    wanted = (await json_object(request)).get("paused")
    if not isinstance(wanted, bool):
        raise HTTPException(400, "Send paused: true to pause the match, or false to let it run.")
    me = request.cookies.get(COOKIE)
    result = hall.set_pause(me, wanted) if me else None
    if result is None:
        raise HTTPException(409, "Only someone with a seat in a match, and the page open, can pause it.")
    return result


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
    body = await json_object(request)
    team_size, seed = body.get("team_size"), body.get("seed")
    max_ticks, break_seconds = body.get("max_ticks", engine.MAX_TICKS), body.get("break_seconds", 10)
    deadline = body.get("deadline_seconds", 2.0)
    study_draw = body.get("study", False)  # draw named teammate bots at random, as the shared arena does (ADR 0019)
    if not isinstance(study_draw, bool):
        raise HTTPException(400, "study must be true or false.")
    if team_size not in engine.SIZES or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise HTTPException(400, "Send team_size (2 or 3) and seed (0 to 2^32 - 1).")
    if not isinstance(max_ticks, int) or not 1 <= max_ticks <= engine.MAX_TICKS or not 0 <= break_seconds <= 60:
        raise HTTPException(400, f"max_ticks must be 1-{engine.MAX_TICKS} and break_seconds 0-60.")
    if not isinstance(deadline, (int, float)) or not 0.15 <= deadline <= 10:
        raise HTTPException(400, "deadline_seconds must be 0.15-10.")
    try:
        arena = hall.open_arena(
            f"p-{secrets.token_urlsafe(6)}", "private", team_size, seed,
            max_ticks=max_ticks, break_seconds=break_seconds, deadline=float(deadline), study=study_draw,
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


@app.get("/api/matches/{match_id}/replay")
async def api_replay(match_id: int):
    """Everything needed to play a finished match again (ADR 0014)."""
    with db.connect() as conn:
        row = conn.execute(
            """SELECT m.seed, m.team_size, m.rules_version, m.max_ticks, m.score_blue, m.score_red, r.actions, r.hash
               FROM matches m JOIN replays r ON r.match_id = m.id WHERE m.id = ?""",
            (match_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "No replay for that match.")
    return {
        "seed": row["seed"], "team_size": row["team_size"], "rules_version": row["rules_version"],
        "max_ticks": row["max_ticks"], "score": [row["score_blue"], row["score_red"]],
        "actions": json.loads(row["actions"]), "hash": row["hash"],
    }


@app.get("/api/matches/{match_id}/frames")
async def api_frames(match_id: int):
    """A finished match turn by turn, for the replay page: the map, who sat
    where (labels, and each bot's name), and every turn's board and moments,
    rebuilt from the saved replay by the engine. spec/replay.test.ts checks
    every frame against the independent engine."""
    with db.connect() as conn:
        row = conn.execute(
            """SELECT m.seed, m.team_size, m.rules_version, m.max_ticks, m.score_blue, m.score_red, m.ended_at, r.actions
               FROM matches m JOIN replays r ON r.match_id = m.id WHERE m.id = ? AND m.status = 'finished'""",
            (match_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "No replay for that match.")
        spans = conn.execute("SELECT seat, visitor_id, from_tick, to_tick FROM seat_spans WHERE match_id = ? ORDER BY from_tick",
                             (match_id,)).fetchall()
    if row["rules_version"] != engine.RULES_VERSION:
        raise HTTPException(404, "That match was played under older rules, so it can't be replayed.")
    state = engine.new_game(row["seed"], row["team_size"])
    state.max_ticks = row["max_ticks"]
    view = lambda: [{"x": p.x, "y": p.y, "respawn": p.respawn, "carrying": p.carrying} for p in state.players]
    frames = [{"tick": 0, "score": [0, 0], "players": view(), "events": []}]
    for actions in json.loads(row["actions"]):
        events = engine.step(state, actions)
        frames.append({"tick": state.tick, "score": list(state.score), "players": view(),
                       "events": [[name, seat] for name, seat in events if name in ("tag", "pickup", "capture")]})
    m = state.map
    seats = [{"seat": i, "team": "blue" if i < row["team_size"] else "red",
              "people": [{"label": activity.visitor_label(s["visitor_id"]), "from": s["from_tick"], "to": s["to_tick"]}
                         for s in spans if s["seat"] == i]}
             for i in range(2 * row["team_size"])]
    return {
        "id": match_id, "team_size": row["team_size"], "score": [row["score_blue"], row["score_red"]],
        "ended_at": row["ended_at"], "seats": seats,
        "map": {"width": m.width, "height": m.height, "walls": sorted([x, y] for x, y in m.walls),
                "flags": [list(f) for f in m.flags], "bases": [[list(c) for c in base] for base in m.bases]},
        "frames": frames,
    }


@app.get("/matches/{match_id}", response_class=HTMLResponse)
async def match_page(request: Request, match_id: int):
    with db.connect() as conn:
        row = conn.execute("SELECT id, status FROM matches WHERE id = ?", (match_id,)).fetchone()
    if row is None or row["status"] != "finished":
        raise HTTPException(404, "No finished match with that number.")
    return templates.TemplateResponse(request, "match.html", {"match_id": match_id})


@app.get("/api/matches/{match_id}/choices")
async def api_choices(match_id: int):
    """Every person's choice in a match: who (public label), seat, turn, move, when.
    Only once the match is over: while it is live, others may learn that you
    have chosen, never what (ADR 0012, 0016)."""
    with db.connect() as conn:
        status = conn.execute("SELECT status FROM matches WHERE id = ?", (match_id,)).fetchone()
        if status is None or status["status"] == "live":
            raise HTTPException(404, "No choices to show: the match doesn't exist or isn't over yet.")
        rows = conn.execute(
            "SELECT at, visitor_id, seat, turn, dir FROM game_events WHERE match_id = ? ORDER BY id", (match_id,)
        ).fetchall()
    return [{"visitor": activity.visitor_label(r["visitor_id"]), "seat": r["seat"], "turn": r["turn"],
             "dir": r["dir"], "at": r["at"]} for r in rows]


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


# --- which bot is the better teammate (ADR 0017, 0019) ------------------------


def played_on(conn, match_id: int, visitor_id: str) -> int | None:
    """The team the visitor held a seat on in a finished match, or None."""
    row = conn.execute(
        """SELECT s.seat, m.team_size FROM seat_spans s JOIN matches m ON m.id = s.match_id
           WHERE s.match_id = ? AND s.visitor_id = ? ORDER BY s.to_tick - s.from_tick DESC LIMIT 1""",
        (match_id, visitor_id),
    ).fetchone()
    return None if row is None else (0 if row["seat"] < row["team_size"] else 1)


def study_captures(conn) -> list:
    """Every capture in a match with a drawn bot teammate: match, team, and
    who scored (a visitor, or None for a bot), from the activity log."""
    return conn.execute(
        """SELECT json_extract(detail, '$.match') AS match_id,
                  CASE json_extract(detail, '$.team') WHEN 'blue' THEN 0 ELSE 1 END AS team, visitor_id
           FROM events WHERE kind = 'capture' AND json_extract(detail, '$.match') IN (SELECT match_id FROM match_study)"""
    ).fetchall()


def study_results(conn) -> dict:
    """Behaviour only (ADR 0019): for each teammate bot, how many matches and
    people, and who scored on those teams; and for each person, their own
    captures against their bot teammate's."""
    caps = study_captures(conn)
    teams = conn.execute(
        """SELECT st.match_id, st.team, st.bot, s.visitor_id
           FROM match_study st JOIN matches m ON m.id = st.match_id
           JOIN seat_spans s ON s.match_id = st.match_id
             AND (CASE WHEN s.seat < m.team_size THEN 0 ELSE 1 END) = st.team
           GROUP BY st.match_id, st.team, s.visitor_id"""
    ).fetchall()
    bots_out = []
    for name in study.TEAMMATE_BOTS:
        mine = conn.execute("SELECT match_id, team FROM match_study WHERE bot = ?", (name,)).fetchall()
        keys = {(t["match_id"], t["team"]) for t in mine}
        people = sum(1 for c in caps if (c["match_id"], c["team"]) in keys and c["visitor_id"])
        bots_ = sum(1 for c in caps if (c["match_id"], c["team"]) in keys and not c["visitor_id"])
        visitors = {t["visitor_id"] for t in teams if t["bot"] == name}
        bots_out.append({"bot": name, "text": study.describe(name), "matches": len(keys), "people": len(visitors),
                         "captures": {"people": people, "bots": bots_}})
    per_person: dict[tuple[str, str], dict] = {}
    for t in teams:
        row = per_person.setdefault((t["visitor_id"], t["bot"]), {"matches": 0, "own_captures": 0, "bot_captures": 0})
        row["matches"] += 1
        row["own_captures"] += sum(1 for c in caps if (c["match_id"], c["team"], c["visitor_id"]) == (t["match_id"], t["team"], t["visitor_id"]))
        row["bot_captures"] += sum(1 for c in caps if (c["match_id"], c["team"]) == (t["match_id"], t["team"]) and not c["visitor_id"])
    people_out = sorted(
        ({"label": activity.visitor_label(v), "bot": b, **row} for (v, b), row in per_person.items()),
        key=lambda r: (-r["matches"], r["label"], r["bot"]),
    )
    return {"bots": bots_out, "people": people_out}


@app.get("/api/study")
async def api_study():
    with db.connect() as conn:
        return study_results(conn)


@app.get("/study", response_class=HTMLResponse)
async def study_page(request: Request):
    with db.connect() as conn:
        results = study_results(conn)
    return templates.TemplateResponse(request, "study.html", {"results": results, "evaluation": teammate_eval})


# --- your matches -------------------------------------------------------------


def my_matches(conn, visitor_id: str, limit: int = 50) -> list[dict]:
    """The visitor's own finished matches, newest first: when, team, score,
    who else played (labels only), their bot teammate, and the replay."""
    rows = conn.execute(
        """SELECT m.id, m.ended_at, m.score_blue, m.score_red, m.team_size, m.status,
                  min(s.seat) AS seat, sum(s.to_tick - s.from_tick) AS turns
           FROM seat_spans s JOIN matches m ON m.id = s.match_id
           WHERE s.visitor_id = ? AND m.status = 'finished'
           GROUP BY m.id ORDER BY m.id DESC LIMIT ?""",
        (visitor_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        team = played_on(conn, r["id"], visitor_id)
        others = conn.execute(
            """SELECT DISTINCT s.visitor_id, s.seat FROM seat_spans s
               WHERE s.match_id = ? AND s.visitor_id != ? ORDER BY s.seat""", (r["id"], visitor_id)
        ).fetchall()
        mates = sorted({activity.visitor_label(o["visitor_id"]) for o in others if (o["seat"] < r["team_size"]) == (team == 0)})
        rivals = sorted({activity.visitor_label(o["visitor_id"]) for o in others if (o["seat"] < r["team_size"]) != (team == 0)})
        study_row = conn.execute("SELECT bot FROM match_study WHERE match_id = ? AND team = ?", (r["id"], team)).fetchone()
        mine, theirs = (r["score_blue"], r["score_red"]) if team == 0 else (r["score_red"], r["score_blue"])
        out.append({
            "id": r["id"], "ended_at": r["ended_at"], "team": "blue" if team == 0 else "red",
            "score": [r["score_blue"], r["score_red"]],
            "result": "won" if mine > theirs else "lost" if mine < theirs else "drew",
            "teammates": mates, "opponents": rivals,
            # the bot drawn for your team (ADR 0017, 0019), named as it was during the match
            "bot_teammate": None if study_row is None else study_row["bot"],
            "replay": f"/matches/{r['id']}",
        })
    return out


@app.get("/api/me/matches")
async def api_my_matches(request: Request):
    me = request.cookies.get(COOKIE)
    if not me:
        return {"label": None, "matches": []}
    with db.connect() as conn:
        return {"label": activity.visitor_label(me), "matches": my_matches(conn, me)}


@app.get("/me", response_class=HTMLResponse)
async def me_page(request: Request):
    me, new = visitor(request)
    with db.connect() as conn:
        matches = [] if new else my_matches(conn, me)
    for m in matches:
        m["date"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(m["ended_at"] or 0))
    return remember(request, templates.TemplateResponse(
        request, "me.html", {"label": activity.visitor_label(me), "matches": matches}), me, new)


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


@app.get("/api/now")
async def api_now():
    """Every arena right now: seats, activity in the last minute, pickups and
    captures this match. The live view for crit 10's demo."""
    return hall.now()


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
    body = await json_object(request)
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

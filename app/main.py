"""The research room: run a test, watch the room's luck bar move, and see
everyone's tests once you've run your own."""

import asyncio
import hashlib
import html
import json
import math
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

import markdown
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .backtest import LEVERAGES, TREND_MONTHS, VOL_LOOKBACKS, VOL_TARGETS, Rule, backtest, load_months, parse_rule
from .luck import deflated_sharpe, luck_bar, sample_variance

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
COOKIE = "visitor"

# Every round tests on 1927-2015 and keeps 2016 onwards (roughly the years SPMO
# has existed) locked until the reveal (doc/adr/0002).
IN_SAMPLE = ("1927-01", "2015-12")

MONTHS = load_months()


def ensure_open_round() -> None:
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM rounds WHERE revealed_at IS NULL AND closed_at IS NULL").fetchone():
            return
        n = conn.execute("SELECT count(*) FROM rounds").fetchone()[0] + 1
        conn.execute(
            "INSERT INTO rounds (name, in_sample_start, in_sample_end, hold_out_end, created_at) VALUES (?, ?, ?, ?, ?)",
            (f"Round {n}", *IN_SAMPLE, MONTHS[-1].month, int(time.time())),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    ensure_open_round()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


# --- people -----------------------------------------------------------------


def visitor_label(visitor_id: str) -> str:
    """A short public name for an anonymous visitor. The cookie itself is never
    shown, since anyone holding it could act as that visitor."""
    return "Visitor " + hashlib.sha256(visitor_id.encode()).hexdigest()[:6]


def has_tested(conn, round_id: int, visitor_id: str | None) -> bool:
    """ADR 0003: other people's results unlock after your own first test."""
    if not visitor_id:
        return False
    row = conn.execute("SELECT 1 FROM trials WHERE round_id = ? AND visitor_id = ? LIMIT 1", (round_id, visitor_id))
    return row.fetchone() is not None


# --- the round and its luck discount ------------------------------------------


def current_round(conn) -> dict:
    row = conn.execute(
        "SELECT * FROM rounds WHERE revealed_at IS NULL AND closed_at IS NULL ORDER BY id LIMIT 1"
    ).fetchone()
    if row is None:
        raise HTTPException(503, "There is no open round.")
    count = conn.execute("SELECT count(*) FROM trials WHERE round_id = ?", (row["id"],)).fetchone()[0]
    visitors = conn.execute("SELECT count(DISTINCT visitor_id) FROM trials WHERE round_id = ?", (row["id"],)).fetchone()[0]
    # one Sharpe ratio per distinct rule: repeats of a rule give the same figure
    srs = [
        r[0]
        for r in conn.execute(
            "SELECT min(sr_monthly) FROM trials WHERE round_id = ? GROUP BY rule_key", (row["id"],)
        )
    ]
    bar = luck_bar(len(srs), sample_variance(srs))
    return {
        "id": row["id"],
        "name": row["name"],
        "in_sample_start": row["in_sample_start"],
        "in_sample_end": row["in_sample_end"],
        "trial_count": count,
        "visitor_count": visitors,
        "distinct_rules": len(srs),
        "luck_bar": bar * math.sqrt(12) if bar is not None else None,
        "revealed": row["revealed_at"] is not None,
        "_luck_bar_monthly": bar,
    }


def public_round(rnd: dict) -> dict:
    return {k: v for k, v in rnd.items() if not k.startswith("_")}


def trial_summary(row, rnd: dict) -> dict:
    rule = Rule(**json.loads(row["rule_params"]))
    bar = rnd["_luck_bar_monthly"]
    confidence = (
        deflated_sharpe(row["sr_monthly"], bar, row["n_months"], row["skewness"], row["kurtosis"])
        if bar is not None
        else None
    )
    return {
        "id": row["id"],
        "round_id": row["round_id"],
        "visitor": visitor_label(row["visitor_id"]),
        "rule": {**rule.params(), "key": rule.key, "label": rule.label},
        "leverage": row["leverage"],
        "stats": {
            "cagr": row["cagr"],
            "volatility": row["volatility"],
            "sharpe": row["sharpe"],
            "max_drawdown": row["max_drawdown"],
        },
        "confidence": confidence,
        # seconds since the epoch: a calendar date here would look like a month
        # to anyone checking for hold-out leaks
        "created_at": row["created_at"],
    }


def visible_trials(conn, rnd: dict, visitor_id: str | None) -> tuple[list, int]:
    """The round's trials this visitor may see, and how many are hidden."""
    rows = conn.execute("SELECT * FROM trials WHERE round_id = ? ORDER BY id DESC", (rnd["id"],)).fetchall()
    if has_tested(conn, rnd["id"], visitor_id):
        return rows, 0
    mine = [r for r in rows if r["visitor_id"] == visitor_id]
    return mine, len(rows) - len(mine)


# --- live updates (doc/adr/0001: server-sent events, one process) -------------

subscribers: set[tuple[asyncio.Queue, str | None]] = set()


def broadcast(trial_id: int) -> None:
    """Tell every open page that a test ran. Everyone hears the count and the
    luck bar; only visitors who have tested this round hear what it was."""
    with db.connect() as conn:
        rnd = current_round(conn)
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (trial_id,)).fetchone()
        summary = trial_summary(row, rnd)
        for queue, visitor_id in list(subscribers):
            data = public_round(rnd)
            if visitor_id == row["visitor_id"] or has_tested(conn, rnd["id"], visitor_id):
                data = {**data, "trial": summary}
            queue.put_nowait(data)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/events")
async def events(request: Request):
    visitor_id = request.cookies.get(COOKIE)
    queue: asyncio.Queue = asyncio.Queue()
    with db.connect() as conn:
        snapshot = public_round(current_round(conn))
    entry = (queue, visitor_id)
    subscribers.add(entry)

    async def stream():
        try:
            yield sse("snapshot", snapshot)
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    yield sse("update", data)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"  # stops proxies closing a quiet stream
        finally:
            subscribers.discard(entry)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- pages ------------------------------------------------------------------


def ago(created_at: int) -> str:
    seconds = max(int(time.time()) - created_at, 0)
    for unit, size in (("day", 86400), ("hour", 3600), ("min", 60)):
        if seconds >= size:
            n = seconds // size
            return f"{n} {unit}{'s' if n > 1 and unit != 'min' else ''} ago"
    return "just now"


def sparkline(curve: list[list], width: int = 640, height: int = 160) -> dict:
    """An SVG path of the curve on a log scale, so a crash early on is as
    visible as one late on."""
    logs = [math.log10(max(v, 1e-6)) for _, v in curve]
    lo, hi = min(logs + [0.0]), max(logs + [0.0])
    span = (hi - lo) or 1.0
    step = width / max(len(logs) - 1, 1)
    y = lambda v: height - (v - lo) / span * height  # noqa: E731
    points = " ".join(f"{i * step:.1f},{y(v):.1f}" for i, v in enumerate(logs))
    return {"points": points, "baseline": f"{y(0.0):.1f}", "width": width, "height": height}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, trial: int | None = None):
    me = request.cookies.get(COOKIE)
    with db.connect() as conn:
        rnd = current_round(conn)
        rows, hidden = visible_trials(conn, rnd, me)
        unlocked = has_tested(conn, rnd["id"], me)
        mine = None
        if trial is not None:
            row = conn.execute(
                "SELECT * FROM trials WHERE id = ? AND round_id = ? AND visitor_id = ?", (trial, rnd["id"], me)
            ).fetchone()
            if row is not None:
                curve = json.loads(row["curve"])
                mine = {**trial_summary(row, rnd), "final": curve[-1][1], "chart": sparkline(curve)}
    trials = [
        {**trial_summary(r, rnd), "ago": ago(r["created_at"]), "is_me": me is not None and r["visitor_id"] == me}
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "round": public_round(rnd),
            "start_year": rnd["in_sample_start"][:4],
            "end_year": rnd["in_sample_end"][:4],
            "trials": trials,
            "hidden": hidden,
            "unlocked": unlocked,
            "mine": mine,
            "menu": {
                "leverages": LEVERAGES,
                "vol_targets": VOL_TARGETS,
                "vol_lookbacks": VOL_LOOKBACKS,
                "trend_months": TREND_MONTHS,
            },
        },
    )


@app.post("/trials")
async def run_trial(request: Request):
    form = await request.form()
    try:
        rule = parse_rule({k: str(v) for k, v in form.items()})
    except ValueError as err:
        raise HTTPException(400, f"Pick a rule from the menu ({err}).")

    me = request.cookies.get(COOKIE) or secrets.token_urlsafe(18)
    with db.connect() as conn:
        rnd = current_round(conn)
        result = backtest(rule, MONTHS, rnd["in_sample_start"], rnd["in_sample_end"])
        cur = conn.execute(
            """INSERT INTO trials (round_id, visitor_id, leverage, cagr, volatility, sharpe, max_drawdown, curve,
                                   created_at, rule_type, rule_key, rule_params, sr_monthly, skewness, kurtosis, n_months)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rnd["id"],
                me,
                rule.leverage,
                result.cagr,
                result.volatility,
                result.sharpe,
                result.max_drawdown,
                json.dumps(result.curve),
                int(time.time()),
                rule.type,
                rule.key,
                json.dumps(rule.params()),
                result.sr_monthly,
                result.skewness,
                result.kurtosis,
                len(result.curve),
            ),
        )
        trial_id = cur.lastrowid
    broadcast(trial_id)

    resp = RedirectResponse(f"/?trial={trial_id}#result", status_code=303)
    resp.set_cookie(COOKIE, me, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
    return resp


@app.get("/readme/", response_class=HTMLResponse)
def readme(request: Request):
    body = markdown.markdown((ROOT / "README.md").read_text(), extensions=["fenced_code", "tables"])
    return templates.TemplateResponse(request, "readme.html", {"body": body})


# --- API --------------------------------------------------------------------


@app.get("/api/rounds/current")
def api_current_round():
    with db.connect() as conn:
        return public_round(current_round(conn))


@app.get("/api/rounds/current/trials")
def api_round_trials(request: Request):
    me = request.cookies.get(COOKIE)
    with db.connect() as conn:
        rnd = current_round(conn)
        rows, hidden = visible_trials(conn, rnd, me)
        return {
            "unlocked": has_tested(conn, rnd["id"], me),
            "hidden": hidden,
            "trials": [{**trial_summary(r, rnd), "is_me": me is not None and r["visitor_id"] == me} for r in rows],
        }


@app.get("/api/trials/{trial_id}")
def api_trial(request: Request, trial_id: int):
    me = request.cookies.get(COOKIE)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (trial_id,)).fetchone()
        if row is None or row["rule_params"] is None:
            raise HTTPException(404, "No such trial.")
        rnd = current_round(conn)
        if row["round_id"] != rnd["id"]:
            raise HTTPException(404, "That trial is from an earlier round.")
        if row["visitor_id"] != me and not has_tested(conn, rnd["id"], me):
            raise HTTPException(403, "Run a test of your own in this round to see other people's.")
        summary = trial_summary(row, rnd)
    curve = [{"month": m, "value": v} for m, v in json.loads(row["curve"])]
    return {**summary, "curve": curve}


@app.exception_handler(HTTPException)
async def plain_errors(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    return HTMLResponse(
        # the detail can echo what the visitor sent, so it is escaped
        f'<!doctype html><html lang="en"><title>Error</title><p>{html.escape(str(exc.detail))}</p>'
        '<p><a href="/">Back to the room</a></p></html>',
        status_code=exc.status_code,
        headers=exc.headers,
    )

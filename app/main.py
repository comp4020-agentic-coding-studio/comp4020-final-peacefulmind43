"""The research room: run a trial, see everyone's trials in the current round."""

import hashlib
import json
import math
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

import markdown
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .backtest import LEVERAGES, leverage_backtest, load_months

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
COOKIE = "visitor"

# The first round: test on 1927-2015, keep 2016 onwards (roughly the years SPMO
# has existed) locked until the reveal (doc/adr/0002).
FIRST_ROUND = {"name": "Round 1", "in_sample_start": "1927-01", "in_sample_end": "2015-12"}

MONTHS = load_months()


def ensure_first_round() -> None:
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM rounds LIMIT 1").fetchone():
            return
        conn.execute(
            "INSERT INTO rounds (name, in_sample_start, in_sample_end, hold_out_end, created_at) VALUES (?, ?, ?, ?, ?)",
            (*FIRST_ROUND.values(), MONTHS[-1].month, int(time.time())),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    ensure_first_round()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


# --- people -----------------------------------------------------------------


def visitor_label(visitor_id: str) -> str:
    """A short public name for an anonymous visitor. The cookie itself is never
    shown, since anyone holding it could act as that visitor."""
    return "Visitor " + hashlib.sha256(visitor_id.encode()).hexdigest()[:6]


# --- reading ----------------------------------------------------------------


def current_round(conn) -> dict:
    row = conn.execute("SELECT * FROM rounds WHERE revealed_at IS NULL ORDER BY id LIMIT 1").fetchone()
    if row is None:
        raise HTTPException(503, "no open round")
    count = conn.execute("SELECT count(*) FROM trials WHERE round_id = ?", (row["id"],)).fetchone()[0]
    return {
        "id": row["id"],
        "name": row["name"],
        "in_sample_start": row["in_sample_start"],
        "in_sample_end": row["in_sample_end"],
        "trial_count": count,
        "revealed": row["revealed_at"] is not None,
    }


def trial_summary(row) -> dict:
    return {
        "id": row["id"],
        "round_id": row["round_id"],
        "visitor": visitor_label(row["visitor_id"]),
        "leverage": row["leverage"],
        "stats": {
            "cagr": row["cagr"],
            "volatility": row["volatility"],
            "sharpe": row["sharpe"],
            "max_drawdown": row["max_drawdown"],
        },
        # seconds since the epoch: a calendar date here would look like a month
        # to anyone checking for hold-out leaks
        "created_at": row["created_at"],
    }


def round_trials(conn, round_id: int) -> list:
    return conn.execute("SELECT * FROM trials WHERE round_id = ? ORDER BY id DESC", (round_id,)).fetchall()


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
        rows = round_trials(conn, rnd["id"])
        mine = None
        if trial is not None:
            row = conn.execute("SELECT * FROM trials WHERE id = ? AND round_id = ?", (trial, rnd["id"])).fetchone()
            if row is not None:
                curve = json.loads(row["curve"])
                mine = {**trial_summary(row), "final": curve[-1][1], "chart": sparkline(curve)}
    trials = [
        {**trial_summary(r), "ago": ago(r["created_at"]), "is_me": me is not None and r["visitor_id"] == me}
        for r in rows
    ]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "round": rnd,
            "start_year": rnd["in_sample_start"][:4],
            "end_year": rnd["in_sample_end"][:4],
            "trials": trials,
            "mine": mine,
            "leverages": LEVERAGES,
        },
    )


@app.post("/trials")
def run_trial(request: Request, leverage: str = Form("")):
    try:
        lev = float(leverage)
    except ValueError:
        raise HTTPException(400, "Pick a leverage from the menu.")
    if lev not in LEVERAGES:
        raise HTTPException(400, "Pick a leverage from the menu.")

    me = request.cookies.get(COOKIE) or secrets.token_urlsafe(18)
    with db.connect() as conn:
        rnd = current_round(conn)
        months = [m for m in MONTHS if rnd["in_sample_start"] <= m.month <= rnd["in_sample_end"]]
        result = leverage_backtest(months, lev)
        cur = conn.execute(
            """INSERT INTO trials (round_id, visitor_id, leverage, cagr, volatility, sharpe, max_drawdown, curve, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rnd["id"],
                me,
                lev,
                result.cagr,
                result.volatility,
                result.sharpe,
                result.max_drawdown,
                json.dumps(result.curve),
                int(time.time()),
            ),
        )
        trial_id = cur.lastrowid

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
        return current_round(conn)


@app.get("/api/rounds/current/trials")
def api_round_trials():
    with db.connect() as conn:
        rnd = current_round(conn)
        return [trial_summary(r) for r in round_trials(conn, rnd["id"])]


@app.get("/api/trials/{trial_id}")
def api_trial(trial_id: int):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (trial_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such trial.")
    curve = [{"month": m, "value": v} for m, v in json.loads(row["curve"])]
    return {**trial_summary(row), "curve": curve}


@app.exception_handler(HTTPException)
async def plain_errors(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    return HTMLResponse(
        f'<!doctype html><title>Error</title><p>{exc.detail}</p><p><a href="/">Back to the room</a></p>',
        status_code=exc.status_code,
        headers=exc.headers,
    )

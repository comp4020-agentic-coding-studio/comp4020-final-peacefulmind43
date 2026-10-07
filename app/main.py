"""The research room: run a test, watch the room's luck bar move, and see
everyone's tests once you've run your own."""

import asyncio
import hmac
import html
import json
import math
import os
import secrets
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

import markdown
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import activity, db, reveal
from .activity import visitor_label
from .backtest import (
    LEVERAGES,
    TREND_MONTHS,
    VOL_LOOKBACKS,
    VOL_TARGETS,
    Rule,
    backtest,
    load_months,
    parse_rule,
    timing,
)
from .luck import deflated_sharpe, luck_bar, sample_variance

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
COOKIE = "visitor"

# Every round tests on 1927-2015 and keeps 2016 onwards (roughly the years SPMO
# has existed) locked until the reveal (doc/adr/0002).
IN_SAMPLE = ("1927-01", "2015-12")

MONTHS = load_months()


@lru_cache(maxsize=8)
def baseline_excess(start: str, end: str) -> tuple[float, ...]:
    """Monthly excess returns of always holding 1x: what timing is judged
    against (ADR 0005)."""
    return tuple(backtest(Rule("fixed", 1.0), MONTHS, start, end).excess)


def ensure_open_round(conn) -> None:
    """There is always exactly one open round, with its reveal time set when
    it opens (ADR 0007)."""
    now = int(time.time())
    open_row = conn.execute("SELECT * FROM rounds WHERE revealed_at IS NULL AND closed_at IS NULL").fetchone()
    if open_row is not None:
        if open_row["reveal_at"] is None:  # a round opened before reveals existed
            conn.execute("UPDATE rounds SET reveal_at = ? WHERE id = ?", (reveal.next_reveal(now), open_row["id"]))
        return
    n = conn.execute("SELECT count(*) FROM rounds").fetchone()[0] + 1
    conn.execute(
        """INSERT INTO rounds (name, in_sample_start, in_sample_end, hold_out_end, created_at, reveal_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (f"Round {n}", *IN_SAMPLE, MONTHS[-1].month, now, reveal.next_reveal(now)),
    )


def reveal_round(conn, round_id: int, early: bool) -> dict:
    """Reveal a round, open the next one, and tell every open page."""
    conn.execute("UPDATE rounds SET revealed_at = ? WHERE id = ? AND revealed_at IS NULL", (int(time.time()), round_id))
    ensure_open_round(conn)
    activity.record(conn, "reveal", None, round_id, {"round_id": round_id, "early": early})
    new_round = public_round(current_round(conn))
    for queue, _ in list(subscribers):
        queue.put_nowait({"__event": "reveal", "revealed_round_id": round_id, "round": new_round})
    return new_round


def reveal_if_due() -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM rounds WHERE revealed_at IS NULL AND closed_at IS NULL AND reveal_at <= ?",
            (int(time.time()),),
        ).fetchone()
        if row is not None:
            reveal_round(conn, row["id"], early=False)


async def reveal_on_schedule() -> None:
    while True:
        try:
            reveal_if_due()
        except Exception as err:  # keep the room running; the next pass retries
            print(json.dumps({"event": "reveal_error", "error": str(err)}), flush=True)
        await asyncio.sleep(20)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.migrate()
    with db.connect() as conn:
        ensure_open_round(conn)
    reveal_if_due()  # a machine that slept through a reveal catches up first
    task = asyncio.create_task(reveal_on_schedule())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


# --- people -----------------------------------------------------------------


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
    return round_info(conn, row)


def round_info(conn, row) -> dict:
    count = conn.execute("SELECT count(*) FROM trials WHERE round_id = ?", (row["id"],)).fetchone()[0]
    visitors = conn.execute("SELECT count(DISTINCT visitor_id) FROM trials WHERE round_id = ?", (row["id"],)).fetchone()[0]
    rules = conn.execute("SELECT count(DISTINCT rule_key) FROM trials WHERE round_id = ?", (row["id"],)).fetchone()[0]
    # one timing figure per distinct timing rule: repeats give the same figure,
    # and fixed leverage has no timing to judge (ADR 0005)
    srs = [
        r[0]
        for r in conn.execute(
            "SELECT min(timing_sr) FROM trials WHERE round_id = ? AND rule_type IN ('vol', 'trend') GROUP BY rule_key",
            (row["id"],),
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
        "distinct_rules": rules,
        "timing_rules": len(srs),
        "luck_bar": bar * math.sqrt(12) if bar is not None else None,
        "revealed": row["revealed_at"] is not None,
        "picks_total": conn.execute("SELECT count(*) FROM picks WHERE round_id = ?", (row["id"],)).fetchone()[0],
        "reveal_at": row["reveal_at"],
        "reveal_text": reveal.reveal_text(row["reveal_at"]) if row["reveal_at"] else None,
        "_luck_bar_monthly": bar,
    }


def public_round(rnd: dict) -> dict:
    return {k: v for k, v in rnd.items() if not k.startswith("_")}


def trial_summary(row, rnd: dict) -> dict:
    rule = Rule(**json.loads(row["rule_params"]))
    bar = rnd["_luck_bar_monthly"]
    confidence = (
        deflated_sharpe(row["timing_sr"], bar, row["n_months"], row["timing_skewness"], row["timing_kurtosis"])
        if bar is not None and rule.type != "fixed"
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


def broadcast(trial_id: int | None = None) -> None:
    """Tell every open page that the room changed (a test, a pick). Everyone
    hears the counts and the luck bar; only visitors who have tested this round
    hear what a test was."""
    with db.connect() as conn:
        rnd = current_round(conn)
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (trial_id,)).fetchone() if trial_id else None
        summary = trial_summary(row, rnd) if row else None
        for queue, visitor_id in list(subscribers):
            data = public_round(rnd)
            if summary and (visitor_id == row["visitor_id"] or has_tested(conn, rnd["id"], visitor_id)):
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
    token = id(entry)
    activity.watch(token, visitor_id)
    with db.connect() as conn:
        activity.record(conn, "watch_start", visitor_id, snapshot["id"])
    opened = time.monotonic()

    async def stream():
        try:
            yield sse("snapshot", snapshot)
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    kind = data.pop("__event", "update")
                    yield sse(kind, data)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"  # stops proxies closing a quiet stream
        finally:
            subscribers.discard(entry)
            activity.unwatch(token)
            with db.connect() as conn:
                activity.record(
                    conn, "watch_end", visitor_id, snapshot["id"], {"seconds": round(time.monotonic() - opened)}
                )

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
async def home(request: Request, trial: int | None = None):
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
        last = conn.execute("SELECT id, name FROM rounds WHERE revealed_at IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
        picks = picks_view(conn, rnd, me)
        activity.record(conn, "visit", me, rnd["id"], {"locked": not unlocked, "hidden": hidden})
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
            "last_revealed": dict(last) if last else None,
            "picks": picks,
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
    me = request.cookies.get(COOKIE)
    try:
        rule = parse_rule({k: str(v) for k, v in form.items()})
    except ValueError as err:
        with db.connect() as conn:
            activity.record(conn, "refused", me, None, {"reason": str(err)})
        raise HTTPException(400, f"Pick a rule from the menu ({err}).")

    me = me or secrets.token_urlsafe(18)
    with db.connect() as conn:
        rnd = current_round(conn)
        first_test = not has_tested(conn, rnd["id"], me)
        others = conn.execute(
            "SELECT count(*) FROM trials WHERE round_id = ? AND visitor_id != ?", (rnd["id"], me)
        ).fetchone()[0]
        repeat = (
            conn.execute(
                "SELECT 1 FROM trials WHERE round_id = ? AND rule_key = ? LIMIT 1", (rnd["id"], rule.key)
            ).fetchone()
            is not None
        )
        result = backtest(rule, MONTHS, rnd["in_sample_start"], rnd["in_sample_end"])
        t = (
            timing(result.excess, list(baseline_excess(rnd["in_sample_start"], rnd["in_sample_end"])))
            if rule.type != "fixed"
            else None
        )
        cur = conn.execute(
            """INSERT INTO trials (round_id, visitor_id, leverage, cagr, volatility, sharpe, max_drawdown, curve,
                                   created_at, rule_type, rule_key, rule_params, sr_monthly, skewness, kurtosis, n_months,
                                   timing_sr, timing_skewness, timing_kurtosis, timing_beta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                t.sr_monthly if t else None,
                t.skewness if t else None,
                t.kurtosis if t else None,
                t.beta if t else None,
            ),
        )
        trial_id = cur.lastrowid
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (trial_id,)).fetchone()
        summary = trial_summary(row, current_round(conn))
        activity.record(
            conn,
            "test",
            me,
            rnd["id"],
            {
                "trial_id": trial_id,
                "rule": summary["rule"],
                "cagr": summary["stats"]["cagr"],
                "sharpe": summary["stats"]["sharpe"],
                "confidence": summary["confidence"],
                "first_test": first_test,
                # ADR 0003: could they see anyone else's results when they chose?
                "had_seen_others": not first_test and others > 0,
                "others_visible": 0 if first_test else others,
                "repeat": repeat,
            },
        )
    broadcast(trial_id)

    resp = RedirectResponse(f"/?trial={trial_id}#result", status_code=303)
    resp.set_cookie(COOKIE, me, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax")
    return resp


@app.get("/readme/", response_class=HTMLResponse)
async def readme(request: Request):
    body = markdown.markdown((ROOT / "README.md").read_text(), extensions=["fenced_code", "tables"])
    with db.connect() as conn:
        activity.record(conn, "readme", request.cookies.get(COOKIE), None)
    return templates.TemplateResponse(request, "readme.html", {"body": body})


# --- picks (ADR 0008) -------------------------------------------------------


def picks_view(conn, rnd: dict, viewer: str | None) -> dict:
    """The round's picks as `viewer` may see them: the total for everyone,
    which rules and who for visitors who have tested (ADR 0003)."""
    unlocked = has_tested(conn, rnd["id"], viewer)
    mine = conn.execute(
        "SELECT rule_key FROM picks WHERE round_id = ? AND visitor_id = ?", (rnd["id"], viewer or "")
    ).fetchone()
    rules = []
    if unlocked:
        tested = conn.execute(
            "SELECT rule_key, min(rule_params) AS params FROM trials WHERE round_id = ? GROUP BY rule_key",
            (rnd["id"],),
        ).fetchall()
        backers: dict[str, list[str]] = {}
        for p in conn.execute("SELECT rule_key, visitor_id FROM picks WHERE round_id = ? ORDER BY picked_at", (rnd["id"],)):
            backers.setdefault(p["rule_key"], []).append(visitor_label(p["visitor_id"]))
        for t in tested:
            rule = Rule(**json.loads(t["params"]))
            names = backers.get(rule.key, [])
            rules.append({"key": rule.key, "label": rule.label, "backers": len(names), "visitors": names})
        rules.sort(key=lambda r: (-r["backers"], r["label"]))
    return {"total": rnd["picks_total"], "unlocked": unlocked, "mine": mine["rule_key"] if mine else None, "rules": rules}


@app.post("/picks")
async def back_a_rule(request: Request):
    me = request.cookies.get(COOKIE)
    form = await request.form()
    rule_key = str(form.get("rule_key", ""))
    with db.connect() as conn:
        rnd = current_round(conn)
        if not has_tested(conn, rnd["id"], me):
            raise HTTPException(403, "Run a test of your own in this round before backing a rule.")
        tested = conn.execute(
            "SELECT rule_params FROM trials WHERE round_id = ? AND rule_key = ? LIMIT 1", (rnd["id"], rule_key)
        ).fetchone()
        if tested is None:
            raise HTTPException(400, "You can only back a rule someone has tested in this round.")
        rule = Rule(**json.loads(tested["rule_params"]))
        old = conn.execute(
            "SELECT rule_params FROM picks WHERE round_id = ? AND visitor_id = ?", (rnd["id"], me)
        ).fetchone()
        conn.execute(
            """INSERT INTO picks (round_id, visitor_id, rule_key, rule_params, picked_at) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (round_id, visitor_id)
               DO UPDATE SET rule_key = excluded.rule_key, rule_params = excluded.rule_params, picked_at = excluded.picked_at""",
            (rnd["id"], me, rule.key, json.dumps(rule.params()), int(time.time())),
        )
        detail = {"rule": {"key": rule.key, "label": rule.label}}
        if old is not None:
            before = Rule(**json.loads(old["rule_params"]))
            detail["changed_from"] = {"key": before.key, "label": before.label}
        activity.record(conn, "pick", me, rnd["id"], detail)
    broadcast()
    return RedirectResponse("/#picks", status_code=303)


@app.get("/api/rounds/current/picks")
def api_picks(request: Request):
    with db.connect() as conn:
        return picks_view(conn, current_round(conn), request.cookies.get(COOKIE))


# --- the log (ADR 0006) ------------------------------------------------------


def log_snapshot(conn, viewer: str | None, limit: int = 100) -> dict:
    viewer_round = activity.unlocked(conn, viewer)
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {**activity.counts(conn), "events": [activity.view(r, viewer, viewer_round) for r in rows]}


@app.get("/log", response_class=HTMLResponse)
async def log_page(request: Request):
    with db.connect() as conn:
        snap = log_snapshot(conn, request.cookies.get(COOKIE))
    for e in snap["events"]:
        e["ago"] = ago(e["at"])
    return templates.TemplateResponse(request, "log.html", {"log": snap})


@app.get("/api/log")
async def api_log(request: Request):
    with db.connect() as conn:
        return log_snapshot(conn, request.cookies.get(COOKIE))


@app.get("/log/events")
async def log_events(request: Request):
    viewer = request.cookies.get(COOKIE)
    queue: asyncio.Queue = asyncio.Queue()
    with db.connect() as conn:
        counts = activity.counts(conn)
    entry = (queue, viewer)
    activity.subscribers.add(entry)

    async def stream():
        try:
            yield sse("snapshot", counts)
            while True:
                try:
                    yield sse("log", await asyncio.wait_for(queue.get(), timeout=15))
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            activity.subscribers.discard(entry)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


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


def revealed_round(conn, round_id: int) -> dict:
    row = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
    if row is None or row["revealed_at"] is None:
        raise HTTPException(404, "That round hasn't been revealed.")
    info = round_info(conn, row)
    trials = conn.execute(
        "SELECT * FROM trials WHERE round_id = ? AND rule_params IS NOT NULL ORDER BY id", (round_id,)
    ).fetchall()
    picks = conn.execute("SELECT * FROM picks WHERE round_id = ? ORDER BY picked_at", (round_id,)).fetchall()
    out = reveal.results(trials, lambda r: trial_summary(r, info)["confidence"], MONTHS, row, picks)
    return {**public_round(info), **out, "revealed_at": row["revealed_at"]}


def revealed_rounds(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM rounds WHERE revealed_at IS NOT NULL ORDER BY id DESC").fetchall()
    return [public_round(round_info(conn, r)) for r in rows]


@app.post("/api/rounds/current/reveal")
def api_reveal_now(request: Request):
    """Reveal the open round early (ADR 0007). Exists only when REVEAL_KEY is
    set, and every use is logged publicly."""
    expected = os.environ.get("REVEAL_KEY")
    if not expected:
        raise HTTPException(404, "Not found.")
    given = request.headers.get("x-reveal-key", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(403, "That key doesn't reveal anything.")
    with db.connect() as conn:
        old = current_round(conn)
        new_round = reveal_round(conn, old["id"], early=True)
    return {"revealed_round_id": old["id"], "round": new_round}


@app.get("/api/rounds/{round_id}")
def api_round(round_id: int):
    with db.connect() as conn:
        return revealed_round(conn, round_id)


@app.get("/rounds", response_class=HTMLResponse)
async def rounds_page(request: Request):
    with db.connect() as conn:
        past = revealed_rounds(conn)
    return templates.TemplateResponse(request, "rounds.html", {"rounds": past})


@app.get("/rounds/{round_id}", response_class=HTMLResponse)
async def round_page(request: Request, round_id: int):
    with db.connect() as conn:
        rnd = revealed_round(conn, round_id)
    return templates.TemplateResponse(
        request,
        "round.html",
        {"r": rnd, "start_year": rnd["in_sample_start"][:4], "end_year": rnd["in_sample_end"][:4],
         "hold_start_year": rnd["hold_out_start"][:4], "hold_end_year": rnd["hold_out_end"][:4]},
    )


@app.get("/api/trials/{trial_id}")
def api_trial(request: Request, trial_id: int):
    me = request.cookies.get(COOKIE)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM trials WHERE id = ?", (trial_id,)).fetchone()
        if row is None or row["rule_params"] is None:
            raise HTTPException(404, "No such trial.")
        round_row = conn.execute("SELECT * FROM rounds WHERE id = ?", (row["round_id"],)).fetchone()
        rnd = round_info(conn, round_row)
        if round_row["revealed_at"] is None:
            if round_row["closed_at"] is not None:
                raise HTTPException(404, "That trial is from a closed round.")
            # an open round: ADR 0003
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

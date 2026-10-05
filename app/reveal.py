"""When rounds reveal, and what a revealed round shows (ADR 0007)."""

import datetime as dt
import json
import math
from zoneinfo import ZoneInfo

from .backtest import Month, Rule, backtest, timing

CANBERRA = ZoneInfo("Australia/Sydney")  # Canberra keeps Sydney time
REVEAL_WEEKDAY = 2  # Wednesday
REVEAL_HOUR = 11
MIN_DAYS = 3


def next_reveal(now: float) -> int:
    """The first Wednesday at 11:00 Canberra time at least three days away."""
    earliest = dt.datetime.fromtimestamp(now, CANBERRA) + dt.timedelta(days=MIN_DAYS)
    day = earliest.date()
    while True:
        at = dt.datetime.combine(day, dt.time(REVEAL_HOUR), CANBERRA)
        if day.weekday() == REVEAL_WEEKDAY and at >= earliest:
            return int(at.timestamp())
        day += dt.timedelta(days=1)


def reveal_text(at: int) -> str:
    """The reveal time in words. Never a year-month: during a round, nothing
    sent may look like a locked month (ADR 0002)."""
    t = dt.datetime.fromtimestamp(at, CANBERRA)
    return f"{t:%A} {t.day} {t:%B}, {t:%H:%M} Canberra time"


def next_month(month: str) -> str:
    year, mm = int(month[:4]), int(month[5:])
    return f"{year + mm // 12}-{mm % 12 + 1:02d}"


def _period(rule: Rule, months: list[Month], start: str, end: str, baseline: list[float] | None) -> dict:
    result = backtest(rule, months, start, end)
    out = {
        "cagr": result.cagr,
        "sharpe": result.sharpe,
        "max_drawdown": result.max_drawdown,
        "final": result.curve[-1][1],
        "timing_added": None,
        "timing_sharpe": None,
    }
    if rule.type != "fixed" and baseline is not None:
        t = timing(result.excess, baseline)
        # the mean of x - beta*b is the regression's intercept: what the timing
        # added per month, beyond holding beta times the portfolio
        series_mean = sum(x - t.beta * b for x, b in zip(result.excess, baseline)) / len(baseline)
        out["timing_added"] = series_mean * 12 / 100
        out["timing_sharpe"] = t.sr_monthly * math.sqrt(12)
    return out


def results(trials: list, confidence_of, months: list[Month], round_row) -> dict:
    """Every distinct rule tried in a revealed round, on the in-sample years
    and on the locked years, plus always-1x as the baseline."""
    start, end = round_row["in_sample_start"], round_row["in_sample_end"]
    hold_start, hold_end = next_month(end), round_row["hold_out_end"]
    base_rule = Rule("fixed", 1.0)
    base_in = backtest(base_rule, months, start, end).excess
    base_out = backtest(base_rule, months, hold_start, hold_end).excess

    by_key: dict[str, dict] = {}
    for row in trials:
        rule = Rule(**json.loads(row["rule_params"]))
        entry = by_key.setdefault(
            rule.key,
            {
                "rule": {**rule.params(), "key": rule.key, "label": rule.label},
                "tests": 0,
                "visitors": set(),
                "confidence": confidence_of(row),
                "in_sample": _period(rule, months, start, end, base_in),
                "hold_out": _period(rule, months, hold_start, hold_end, base_out),
            },
        )
        entry["tests"] += 1
        entry["visitors"].add(row["visitor_id"])

    rules = []
    for entry in by_key.values():
        entry["visitors"] = len(entry["visitors"])
        rules.append(entry)
    # the room's favourites first: highest chance the timing helps, then growth
    rules.sort(key=lambda r: (-(r["confidence"] if r["confidence"] is not None else -1), -r["in_sample"]["cagr"]))

    return {
        "hold_out_start": hold_start,
        "hold_out_end": hold_end,
        "rules": rules,
        "baseline": {
            "rule": {**base_rule.params(), "key": base_rule.key, "label": base_rule.label},
            "in_sample": _period(base_rule, months, start, end, None),
            "hold_out": _period(base_rule, months, hold_start, hold_end, None),
        },
    }

"""The momentum data, the overlay rules, and backtests of them (ADR 0004).

Every figure here is pinned by spec/backtest.test.ts, which recomputes it from
data/momentum.csv with an independent model of ADR 0004.
"""

import csv
import math
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "momentum.csv"

BORROW_SPREAD = 1.5  # % a year over the T-bill, on borrowed money (ADR 0002)
HOLDING_COST = 1.0  # % a year on the amount held in the portfolio
SWITCHING_COST = 0.1  # % of the amount moved when the holding changes

# The menu. Anything else is refused.
LEVERAGES = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
VOL_TARGETS = (10, 15, 20, 25)  # % a year
VOL_LOOKBACKS = (6, 12)  # months
TREND_MONTHS = (6, 10, 12)


@dataclass(frozen=True)
class Month:
    month: str  # YYYY-MM
    momentum: float  # percent
    market: float  # percent
    rf: float  # percent


def load_months() -> list[Month]:
    with DATA.open() as f:
        return [
            Month(r["month"], float(r["momentum"]), float(r["market"]), float(r["rf"]))
            for r in csv.DictReader(f)
        ]


@dataclass(frozen=True)
class Rule:
    type: str  # "fixed", "vol" or "trend"
    leverage: float  # the cap
    target: int | None = None  # vol: % a year
    lookback: int | None = None  # vol: months
    months: int | None = None  # trend: months

    @property
    def key(self) -> str:
        """The same rule always has the same key; repeats share it (ADR 0004)."""
        if self.type == "vol":
            return f"vol:L={self.leverage:g}:T={self.target}:K={self.lookback}"
        if self.type == "trend":
            return f"trend:L={self.leverage:g}:N={self.months}"
        return f"fixed:L={self.leverage:g}"

    @property
    def label(self) -> str:
        if self.type == "vol":
            return f"Aim for {self.target}% volatility ({self.lookback}-month view), up to {self.leverage:g}×"
        if self.type == "trend":
            return f"{self.leverage:g}× while the market is above its {self.months}-month average"
        return f"Always {self.leverage:g}×"

    def params(self) -> dict:
        out: dict = {"type": self.type, "leverage": self.leverage}
        if self.type == "vol":
            out |= {"target": self.target, "lookback": self.lookback}
        if self.type == "trend":
            out["months"] = self.months
        return out


def parse_rule(form: dict[str, str]) -> Rule:
    """A rule from the page's form fields. Raises ValueError for anything not
    on the menu."""

    def number(name: str, cast, allowed):
        raw = form.get(name, "")
        try:
            value = cast(raw)
        except ValueError:
            raise ValueError(f"{name} is missing or not a number")
        if value not in allowed:
            raise ValueError(f"{name} {raw} is not on the menu")
        return value

    kind = form.get("rule", "fixed")
    leverage = number("leverage", float, LEVERAGES)
    if kind == "fixed":
        return Rule("fixed", leverage)
    if kind == "vol":
        return Rule("vol", leverage, target=number("target", int, VOL_TARGETS), lookback=number("lookback", int, VOL_LOOKBACKS))
    if kind == "trend":
        return Rule("trend", leverage, months=number("months", int, TREND_MONTHS))
    raise ValueError(f"rule {kind!r} is not on the menu")


def weights(rule: Rule, months: list[Month]) -> list[float]:
    """How much of your money the rule holds in each month, decided with data
    up to the month before. In the first month every rule holds the cap."""
    out: list[float] = []
    level = 1.0
    levels: list[float] = []  # market index at the end of each earlier month
    for t, _ in enumerate(months):
        if t > 0:
            level *= 1 + months[t - 1].market / 100
            levels.append(level)
        if rule.type == "fixed" or t == 0:
            w = rule.leverage
        elif rule.type == "vol":
            past = [m.momentum for m in months[max(0, t - rule.lookback) : t]]
            if len(past) < 2:
                w = rule.leverage
            else:
                annual_vol = _sd(past) * math.sqrt(12) / 100
                w = min(rule.leverage, rule.target / 100 / annual_vol)
        else:  # trend
            recent = levels[-rule.months :]
            w = rule.leverage if levels[-1] >= sum(recent) / len(recent) else 0.0
        out.append(w)
    return out


@dataclass(frozen=True)
class Result:
    curve: list[tuple[str, float]]  # (month, value of 1 unit of starting money)
    cagr: float
    volatility: float
    sharpe: float  # annualised
    max_drawdown: float
    sr_monthly: float  # per-month Sharpe ratio
    skewness: float
    kurtosis: float  # not excess: 3 for a normal distribution
    excess: list[float]  # monthly return over the T-bill, percent


def backtest(rule: Rule, months: list[Month], start: str, end: str) -> Result:
    """Run `rule` over the months from `start` to `end`. Earlier months may be
    used by the rule's signals; later months are never read."""
    history = [m for m in months if m.month <= end]
    held = weights(rule, history)

    value = 1.0
    peak = 1.0
    max_drawdown = 0.0
    previous_w = 0.0
    curve: list[tuple[str, float]] = []
    returns: list[float] = []  # monthly, percent
    excess: list[float] = []  # monthly over the T-bill, percent

    for m, w in zip(history, held):
        if m.month < start:
            continue
        monthly = (
            w * m.momentum
            + (1 - w) * m.rf
            - max(w - 1, 0) * BORROW_SPREAD / 12
            - w * HOLDING_COST / 12
            - SWITCHING_COST * abs(w - previous_w)
        )
        previous_w = w
        before = value
        value = max(value * (1 + monthly / 100), 0.0)  # wiped out stays wiped out
        realised = (value / before - 1) * 100 if before > 0 else 0.0
        returns.append(realised)
        excess.append(realised - m.rf)
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
        curve.append((m.month, value))

    if not curve:
        raise ValueError("no months to test")

    years = len(curve) / 12
    cagr = value ** (1 / years) - 1 if value > 0 else -1.0
    sd = _sd(excess)
    sr_monthly = _mean(excess) / sd if sd > 0 else 0.0
    skewness, kurtosis = _shape(excess)
    return Result(
        curve=curve,
        cagr=cagr,
        volatility=_sd(returns) * math.sqrt(12) / 100,
        sharpe=sr_monthly * math.sqrt(12),
        max_drawdown=max_drawdown,
        sr_monthly=sr_monthly,
        skewness=skewness,
        kurtosis=kurtosis,
        excess=excess,
    )


@dataclass(frozen=True)
class Timing:
    """What a rule adds over always holding 1x (ADR 0005)."""

    sr_monthly: float
    skewness: float
    kurtosis: float
    beta: float


def timing(excess: list[float], baseline: list[float]) -> Timing:
    """Regress the rule's monthly excess returns on the baseline's and judge
    what is left: the series x - beta * b."""
    if len(excess) != len(baseline) or len(excess) < 3:
        raise ValueError("timing needs the rule and the baseline over the same months")
    mx, mb = _mean(excess), _mean(baseline)
    var_b = sum((b - mb) ** 2 for b in baseline)
    beta = sum((b - mb) * (x - mx) for x, b in zip(excess, baseline)) / var_b
    series = [x - beta * b for x, b in zip(excess, baseline)]
    sd = _sd(series)
    skewness, kurtosis = _shape(series)
    return Timing(_mean(series) / sd if sd > 0 else 0.0, skewness, kurtosis, beta)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _sd(xs: list[float]) -> float:
    """Sample standard deviation (n - 1)."""
    if len(xs) < 2:
        return 0.0
    mean = _mean(xs)
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


def _shape(xs: list[float]) -> tuple[float, float]:
    """Skewness and (non-excess) kurtosis, from population moments."""
    mean = _mean(xs)
    m2 = sum((x - mean) ** 2 for x in xs) / len(xs)
    if m2 == 0:
        return 0.0, 3.0
    m3 = sum((x - mean) ** 3 for x in xs) / len(xs)
    m4 = sum((x - mean) ** 4 for x in xs) / len(xs)
    return m3 / m2**1.5, m4 / m2**2

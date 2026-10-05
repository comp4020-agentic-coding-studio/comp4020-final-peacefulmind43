"""The momentum data, and backtests of overlay rules on it.

Every figure here is pinned by spec/backtest.test.ts, which recomputes it from
data/momentum.csv independently.
"""

import csv
import math
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "momentum.csv"

# Borrowing above 1x costs the T-bill rate plus this, per year (doc/adr/0002).
BORROW_SPREAD = 1.5

# The leverage levels on the page's menu. Anything else is refused.
LEVERAGES = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0)


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
class Result:
    curve: list[tuple[str, float]]  # (month, value of 1 unit of starting money)
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float


def leverage_backtest(months: list[Month], leverage: float) -> Result:
    """Hold `leverage` times your money in the momentum portfolio, rebalanced
    monthly. The borrowed part pays the T-bill rate plus the spread."""
    if not months:
        raise ValueError("no months to test")

    value = 1.0
    peak = 1.0
    max_drawdown = 0.0
    curve: list[tuple[str, float]] = []
    returns: list[float] = []  # monthly return, in percent
    excess: list[float] = []  # monthly return over the T-bill, in percent

    for m in months:
        borrow_cost = (leverage - 1) * (m.rf + BORROW_SPREAD / 12)
        monthly = leverage * m.momentum - borrow_cost  # percent
        previous = value
        value = max(value * (1 + monthly / 100), 0.0)  # wiped out stays wiped out
        realised = (value / previous - 1) * 100 if previous > 0 else 0.0
        returns.append(realised)
        excess.append(realised - m.rf)
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
        curve.append((m.month, value))

    years = len(months) / 12
    cagr = value ** (1 / years) - 1 if value > 0 else -1.0
    excess_sd = _sd(excess)
    sharpe = _mean(excess) / excess_sd * math.sqrt(12) if excess_sd > 0 else 0.0
    volatility = _sd(returns) * math.sqrt(12) / 100

    return Result(curve, cagr, volatility, sharpe, max_drawdown)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _sd(xs: list[float]) -> float:
    """Sample standard deviation (n - 1)."""
    if len(xs) < 2:
        return 0.0
    mean = _mean(xs)
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))

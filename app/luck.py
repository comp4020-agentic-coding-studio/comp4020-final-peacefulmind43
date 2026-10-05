"""The luck discount: the deflated Sharpe ratio (Bailey and López de Prado,
2014), over the distinct rules tested in a round (ADR 0004).

spec/discount.test.ts pins the formula against the paper's worked example and
recomputes the app's figures independently.
"""

import math
from statistics import NormalDist

EULER_GAMMA = 0.5772156649015329
_normal = NormalDist()


def luck_bar(n: int, variance: float) -> float | None:
    """The per-period Sharpe ratio expected from the best of `n` rules with no
    skill, given the variance of their Sharpe ratios. None below two rules."""
    if n < 2 or variance <= 0:
        return None
    z = (1 - EULER_GAMMA) * _normal.inv_cdf(1 - 1 / n) + EULER_GAMMA * _normal.inv_cdf(1 - 1 / (n * math.e))
    return math.sqrt(variance) * z


def deflated_sharpe(sr: float, sr_zero: float, months: int, skewness: float, kurtosis: float) -> float | None:
    """The probability that the true Sharpe ratio is above zero, given that the
    best of the room's rules is expected to reach `sr_zero` by luck alone."""
    spread = 1 - skewness * sr + (kurtosis - 1) / 4 * sr * sr
    if months < 2 or spread <= 0:
        return None
    return _normal.cdf((sr - sr_zero) * math.sqrt(months - 1) / math.sqrt(spread))


def sample_variance(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    return sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)

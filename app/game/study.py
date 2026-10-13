"""The blind teammate study (ADR 0017).

In the shared arena, each match draws, for each team, which bot fills that
team's empty seats while the team has a person in it. The bot is shown as
"Bot A" or "Bot B" until the match is over and the person has rated it or
skipped. A team with no person in it gets the deployed bot, as before.

The study changes only which bot plays a seat, never what a bot sees: every
bot still chooses from the board shown when the turn opened (CLAUDE.md).
"""

from __future__ import annotations

import random
import string
from functools import cache

from . import policy

# Bots a person may get as a teammate. Add a name here to put a new bot in
# the study; it must be a "scripted" or an exported bot in app/game/bots/.
TEAMMATE_BOTS = ["scripted", "cur4"]


def draw(seed: int, bots: list[str] | None = None) -> dict:
    """One match's assignment: a bot type per team, and a random letter per
    type, so a letter never tells which bot it is."""
    bots = list(bots or TEAMMATE_BOTS)
    rng = random.Random(seed)
    letters = list(string.ascii_uppercase[: len(bots)])
    rng.shuffle(letters)
    return {"seed": seed, "bots": [rng.choice(bots), rng.choice(bots)], "letters": dict(zip(bots, letters))}


@cache
def player(name: str) -> "policy.Policy | None":
    """The bot that plays a type: None means the scripted bot."""
    if name == "scripted":
        return None
    bot = policy.load(name)
    if bot is None:
        raise ValueError(f"teammate bot {name} isn't in {policy.BOT_DIR}")
    return bot


def describe(name: str) -> str:
    return "the scripted bot" if name == "scripted" else f"the trained bot ({name})"


MIN_N = 10  # below this many ratings, the page shows counts, not a mean and interval


def mean_interval(scores: list[int]) -> dict:
    """The mean rating and a 95% interval, by the normal approximation. At
    small n that interval is too narrow, so the page shows only counts below
    MIN_N."""
    n = len(scores)
    if n < 2:
        return {"mean": float(scores[0]) if scores else None, "low": None, "high": None}
    mean = sum(scores) / n
    sd = (sum((x - mean) ** 2 for x in scores) / (n - 1)) ** 0.5
    half = 1.96 * sd / n**0.5
    return {"mean": round(mean, 2), "low": round(max(1.0, mean - half), 2), "high": round(min(5.0, mean + half), 2)}

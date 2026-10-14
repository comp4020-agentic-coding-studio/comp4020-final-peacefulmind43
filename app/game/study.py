"""Which bot is the better teammate (ADR 0017, changed by ADR 0019).

In the shared arena, each match draws, for each team, which bot fills that
team's empty seats while the team has a person in it. The bot is always shown
by its name: nobody is blinded and nobody is asked to rate it (ADR 0019). The
evidence is behaviour: who scores on teams that had each bot.
A team with no person in it gets the deployed bot, as before.

The draw changes only which bot plays a seat, never what a bot sees: every
bot still chooses from the board shown when the turn opened (CLAUDE.md).
"""

from __future__ import annotations

import random
from functools import cache

from . import policy

# Bots a person may get as a teammate. Add a name here to put a new bot in
# the study; it must be a "scripted" or an exported bot in app/game/bots/.
TEAMMATE_BOTS = ["scripted", "cur4", "fcp1"]


def draw(seed: int, bots: list[str] | None = None) -> dict:
    """One match's assignment: a bot type per team, from a seed that is saved."""
    bots = list(bots or TEAMMATE_BOTS)
    rng = random.Random(seed)
    return {"seed": seed, "bots": [rng.choice(bots), rng.choice(bots)]}


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

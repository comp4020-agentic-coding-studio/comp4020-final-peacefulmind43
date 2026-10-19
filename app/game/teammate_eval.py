"""The teammate evaluation from doc/rl/fcp1-eval.txt (ADR 0018), for /study.

Bots beside other bots, not people: one seat is the named bot, the rest of its
team is a partner it never trained with, against the full scripted team, 400
unseen maps each. tests/test_study.py checks that every number here is in the
evaluation file, so the page can't drift from it. The deployed image has no
doc/ folder, which is why the numbers are copied here.
"""

SOURCE = "doc/rl/fcp1-eval.txt"
GAMES = 400

# partner, bot, loss rate with its 95% interval, captures a game by the bot and by its partners
ROWS = [
    {"partner": "scripted30", "about": "the scripted bot with 30% random moves",
     "bot": "fcp1", "loss": "22.2% [18.4%, 26.6%]", "by_bot": "1.31", "by_partners": "0.02"},
    {"partner": "scripted30", "about": "the scripted bot with 30% random moves",
     "bot": "cur4", "loss": "53.0% [48.1%, 57.8%]", "by_bot": "0.93", "by_partners": "0.01"},
    {"partner": "cur3", "about": "an older trained bot",
     "bot": "fcp1", "loss": "32.2% [27.9%, 37.0%]", "by_bot": "1.20", "by_partners": "0.05"},
    {"partner": "cur3", "about": "an older trained bot",
     "bot": "cur4", "loss": "77.8% [73.4%, 81.6%]", "by_bot": "0.53", "by_partners": "0.05"},
    {"partner": "lr1e3", "about": "a trained bot that only defends",
     "bot": "fcp1", "loss": "14.0% [10.9%, 17.7%]", "by_bot": "1.45", "by_partners": "0.00"},
    {"partner": "lr1e3", "about": "a trained bot that only defends",
     "bot": "cur4", "loss": "28.5% [24.3%, 33.1%]", "by_bot": "1.36", "by_partners": "0.00"},
]

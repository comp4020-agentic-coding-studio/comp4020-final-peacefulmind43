"""The blind teammate study's draw and summary (ADR 0017)."""

from app.game import study


def test_the_same_seed_draws_the_same_bots_and_letters():
    assert study.draw(42) == study.draw(42)


def test_every_bot_gets_its_own_letter_and_both_kinds_are_drawn():
    seen_bots, seen_letters = set(), set()
    for seed in range(200):
        d = study.draw(seed)
        assert sorted(d["letters"].values()) == ["A", "B"]
        assert all(b in study.TEAMMATE_BOTS for b in d["bots"])
        seen_bots.update(d["bots"])
        seen_letters.add(d["letters"]["scripted"])
    assert seen_bots == set(study.TEAMMATE_BOTS)
    assert seen_letters == {"A", "B"}, "a letter must not tell which bot it is"


def test_a_new_bot_can_join_the_study():
    d = study.draw(7, ["scripted", "cur4", "cur5"])
    assert sorted(d["letters"].values()) == ["A", "B", "C"]


def test_every_teammate_bot_can_play():
    for name in study.TEAMMATE_BOTS:
        study.player(name)  # raises if a named bot is missing


def test_mean_and_interval():
    assert study.mean_interval([]) == {"mean": None, "low": None, "high": None}
    r = study.mean_interval([3, 4, 5, 4, 4])
    assert r["mean"] == 4.0 and r["low"] < 4 < r["high"] and r["high"] <= 5

"""The teammate draw (ADR 0017, with ADR 0019: no ratings, no blinding)."""

from app.game import study
from app.game.arena import Hall


class NoStore:
    def start(self, arena):
        return 1

    def finish(self, *args):
        pass


def test_the_same_seed_draws_the_same_bots():
    assert study.draw(42) == study.draw(42)


def test_both_bots_are_drawn_for_both_teams():
    seen = [set(), set()]
    for seed in range(200):
        d = study.draw(seed)
        assert all(b in study.TEAMMATE_BOTS for b in d["bots"])
        for t in (0, 1):
            seen[t].add(d["bots"][t])
    assert seen == [set(study.TEAMMATE_BOTS), set(study.TEAMMATE_BOTS)]


def test_a_new_bot_can_join_the_study():
    drawn = {b for seed in range(100) for b in study.draw(seed, ["scripted", "cur4", "cur5"])["bots"]}
    assert drawn == {"scripted", "cur4", "cur5"}


def test_every_teammate_bot_can_play():
    for name in study.TEAMMATE_BOTS:
        study.player(name)  # raises if a named bot is missing


def test_a_teammate_bot_is_always_named_and_its_draw_is_recorded():
    hall = Hall(NoStore())
    arena = hall.open_arena("p-test", "private", 2, 5, study=True)
    hall.start_match(arena, ["someone"])
    team = arena.seats[arena.seat_of("someone")].team
    drawn = arena.draw["bots"][team]
    for seat in arena.seat_view():
        if seat["kind"] == "bot":
            assert seat["bot"] and not seat["bot"].startswith("Bot "), "a bot seat shows its real name"
            assert "blind" not in seat
    mates = [s for s in arena.seat_view() if s["kind"] == "bot" and s["team"] == ("blue" if team == 0 else "red")]
    assert mates and all(s["bot"] == drawn for s in mates)
    hall.tick(arena, arena.turn_opened + 10)  # one turn with the bot beside the person
    assert arena.study_rows() == [(team, drawn, arena.draw["seed"])]

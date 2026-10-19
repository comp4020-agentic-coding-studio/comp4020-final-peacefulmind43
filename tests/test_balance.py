"""Which bot plays which seat when people play (ADR 0023)."""

from app.game import policy
from app.game.arena import Hall


class NoStore:
    def start(self, arena):
        return 1

    def finish(self, *args):
        pass


def names(arena, team: str) -> set[str]:
    return {s["bot"] for s in arena.seat_view() if s["kind"] == "bot" and s["team"] == team}


def hall() -> Hall:
    return Hall(NoStore(), bot=policy.load("fcp1"), balanced=policy.load("cur4snap"))


def test_a_team_with_no_person_gets_the_balanced_bot_and_a_team_with_one_keeps_its_teammate():
    h = hall()
    arena = h.open_arena("p-one", "private", 2, 11)
    h.arrive("someone", "p-one")
    mine = "blue" if arena.seats[arena.seat_of("someone")].team == 0 else "red"
    other = "red" if mine == "blue" else "blue"
    assert names(arena, mine) == {"fcp1"}
    assert names(arena, other) == {"cur4snap"}


def test_when_both_teams_have_people_every_bot_is_the_same_bot():
    h = hall()
    arena = h.open_arena("p-two", "private", 2, 12)
    h.arrive("first", "p-two")
    h.arrive("second", "p-two")
    teams = {arena.seats[arena.seat_of(v)].team for v in ("first", "second")}
    assert teams == {0, 1}
    assert names(arena, "blue") == names(arena, "red") == {"fcp1"}


def test_in_a_study_match_both_teams_with_people_get_the_same_drawn_bot():
    h = hall()
    for seed in range(20):
        arena = h.open_arena(f"p-s{seed}", "private", 2, seed, study=True)
        h.arrive(f"a{seed}", arena.id)
        h.arrive(f"b{seed}", arena.id)
        assert names(arena, "blue") == names(arena, "red")
        assert arena.draw["bots"][0] == arena.draw["bots"][1]
        h.arenas.pop(arena.id)


def test_the_watch_arena_is_unchanged():
    h = hall()
    h.watch_bot = policy.load("fcp1")
    arena = h.watch()
    h.start_match(arena, [])
    assert names(arena, "blue") == {"fcp1"} and names(arena, "red") == {"scripted"}


def test_without_a_balanced_bot_every_seat_is_the_deployed_bot():
    h = Hall(NoStore(), bot=policy.load("fcp1"))
    arena = h.open_arena("p-old", "private", 2, 13)
    h.arrive("someone", "p-old")
    assert names(arena, "blue") == names(arena, "red") == {"fcp1"}


def test_the_balanced_bot_is_a_checked_export_and_not_the_deployed_bot():
    bot = policy.balanced()
    assert bot is not None and (policy.BOT_DIR / f"{bot.name}.npz").exists()
    assert bot.name != policy.deployed().name


def test_the_balanced_bot_moves_the_same_whatever_the_person_chose():
    # the fairness rule (CLAUDE.md) for the new bot: it sees the board, not choices
    for seed in range(10):
        moves = set()
        for choice in range(5):
            h = hall()
            arena = h.open_arena("p-fair", "private", 2, seed)
            h.arrive("someone", "p-fair")
            me = arena.seat_of("someone")
            h.choose("someone", choice, 1, arena.state.tick)
            h.tick(arena, arena.turn_opened + 10)
            moves.add(tuple(a for i, a in enumerate(arena.replay[0]) if i != me))
        assert len(moves) == 1

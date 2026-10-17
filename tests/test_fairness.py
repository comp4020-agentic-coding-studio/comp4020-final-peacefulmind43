"""Bots never see people's choices (CLAUDE.md, README "Bots are fair").

A bot chooses from the board as it was when the turn opened. So whatever a
person chooses in a turn, every bot in that match makes the same move in that
turn."""

from app.game import engine, policy
from app.game.arena import Hall


class NoStore:
    def start(self, arena):
        return 1

    def finish(self, *args):
        pass


def first_turn_bot_moves(seed: int, person_choice: int, bot) -> list[int]:
    hall = Hall(NoStore(), bot=bot)
    arena = hall.open_arena("p-fair", "private", 2, seed)
    hall.arrive("someone", "p-fair")  # a page opens: the match starts with this person in it
    me = arena.seat_of("someone")
    assert hall.choose("someone", person_choice, 1, arena.state.tick)["accepted"]
    hall.tick(arena, arena.turn_opened + 10)
    assert len(arena.replay) == 1 and arena.replay[0][me] == person_choice
    return [a for i, a in enumerate(arena.replay[0]) if i != me]


def test_a_bot_moves_the_same_whatever_the_person_chose():
    choices = (engine.STAY, engine.NORTH, engine.SOUTH, engine.EAST, engine.WEST)
    for bot in (None, policy.deployed()):  # the scripted bot, and the bot that fills seats
        for seed in range(20):
            moves = {tuple(first_turn_bot_moves(seed, c, bot)) for c in choices}
            assert len(moves) == 1, f"seed {seed}: the bots' moves changed with the person's choice"

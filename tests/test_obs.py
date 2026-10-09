"""The RL bot's view (ADR 0013)."""

import numpy as np

from app.game.engine import EAST, WEST, Rng, new_game, step
from app.game.obs import HEIGHT, P, PLANES, SCALARS, WIDTH, observe


def test_shapes_and_the_outside_plane():
    for k, (w, h) in ((2, (16, 10)), (3, (20, 12))):
        s = new_game(5, k)
        planes, scalars = observe(s, 0)
        assert planes.shape == (len(PLANES), HEIGHT, WIDTH) and scalars.shape == (len(SCALARS),)
        assert planes[P["outside"], :h, :w].sum() == 0
        assert planes[P["outside"]].sum() == HEIGHT * WIDTH - w * h


def test_you_are_exactly_one_cell_when_on_the_board():
    s = new_game(5, 2)
    planes, _ = observe(s, 1)
    assert planes[P["self"]].sum() == 1
    assert planes[P["teammates"]].sum() == 1 and planes[P["enemies"]].sum() == 2


def test_both_teams_see_themselves_attacking_right():
    s = new_game(9, 2)
    for seat in (0, 2):  # one blue, one red
        planes, _ = observe(s, seat)
        own_base_x = np.argwhere(planes[P["own_base"]])[:, 1]
        enemy_base_x = np.argwhere(planes[P["enemy_base"]])[:, 1]
        assert own_base_x.max() < enemy_base_x.min()


def test_mirror_games_look_the_same_to_mirrored_players():
    # Flip a whole game left to right and swap the teams: a blue player in the
    # original must see exactly what the matching red player sees in the mirror.
    # This is what lets one network play both sides.
    swap = {0: 0, 1: 1, 2: 2, EAST: WEST, WEST: EAST}
    for seed in range(10):
        for k in (2, 3):
            a, b = new_game(seed, k), new_game(seed, k)
            mirror = lambda i: (i + k) % (2 * k)  # noqa: E731
            rng = Rng(seed + 3)
            for _ in range(150):
                for i in range(2 * k):
                    pa, sa = observe(a, i)
                    pb, sb = observe(b, mirror(i))
                    assert np.array_equal(pa, pb) and np.array_equal(sa, sb)
                acts = [rng.below(5) for _ in range(2 * k)]
                mirrored = [0] * (2 * k)
                for i, act in enumerate(acts):
                    mirrored[mirror(i)] = swap[act]
                step(a, acts)
                step(b, mirrored)

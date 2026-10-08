"""Each rule in ADR 0010, as a small hand-built situation."""

from app.game.engine import (
    EAST,
    MAX_TICKS,
    RESPAWN_TICKS,
    STAY,
    WEST,
    Map,
    Player,
    State,
    make_map,
    new_game,
    state_hash,
    step,
)


def empty_map(width=16, height=10) -> Map:
    flags = ((1, height // 2), (width - 2, height // 2))
    offsets = [(0, -1), (0, 1), (1, 0), (1, -1), (1, 1), (-1, 0), (-1, -1), (-1, 1), (0, 0)]
    bases = (
        tuple((flags[0][0] + dx, flags[0][1] + dy) for dx, dy in offsets),
        tuple((flags[1][0] - dx, flags[1][1] + dy) for dx, dy in offsets),
    )
    return Map(width, height, frozenset(), flags, bases)


def game(*players: Player, m: Map | None = None) -> State:
    return State(m or empty_map(), list(players))


# --- maps -------------------------------------------------------------------


def test_same_seed_same_map_different_seed_different_map():
    assert make_map(7, 2) == make_map(7, 2)
    assert make_map(7, 2) != make_map(8, 2)


def test_maps_are_mirror_symmetric_and_keep_bases_clear():
    for seed in range(50):
        for k in (2, 3):
            m = make_map(seed, k)
            assert all((m.width - 1 - x, y) in m.walls for x, y in m.walls)
            assert not set(m.bases[0]) & m.walls and not set(m.bases[1]) & m.walls


def test_every_open_cell_is_reachable():
    from app.game.engine import _connected

    for seed in range(50):
        assert _connected(make_map(seed, 2)) and _connected(make_map(seed, 3))


def test_a_new_game_spawns_teams_in_their_bases():
    s = new_game(3, 3)
    assert [p.team for p in s.players] == [0, 0, 0, 1, 1, 1]
    for p in s.players:
        assert (p.x, p.y) in s.map.bases[p.team]


# --- movement and contact ---------------------------------------------------


def test_walls_and_edges_block_movement():
    m = empty_map()
    m = Map(m.width, m.height, frozenset({(4, 2)}), m.flags, m.bases)
    s = game(Player(0, 3, 2), Player(1, 15, 0), m=m)
    step(s, [EAST, EAST])
    assert (s.players[0].x, s.players[0].y) == (3, 2)  # wall
    assert (s.players[1].x, s.players[1].y) == (15, 0)  # edge


def test_meeting_on_your_own_half_tags_the_intruder():
    # blue at x=5 (blue half); red walks into the same cell from x=6
    s = game(Player(0, 5, 2), Player(1, 6, 2))
    events = step(s, [STAY, WEST])
    assert ("tag", 1) in events and ("tag", 0) not in events
    assert s.players[1].respawn == RESPAWN_TICKS and s.players[0].x == 5


def test_meeting_on_the_enemy_half_tags_you():
    s = game(Player(0, 9, 2), Player(1, 10, 2))  # x=9 and 10 are red's half
    events = step(s, [EAST, STAY])
    assert ("tag", 0) in events and ("tag", 1) not in events


def test_swapping_across_the_middle_tags_both():
    s = game(Player(0, 7, 2), Player(1, 8, 2))  # the middle line is between 7 and 8
    events = step(s, [EAST, WEST])
    assert {("tag", 0), ("tag", 1)} <= set(events)


def test_teammates_can_share_a_cell():
    s = game(Player(0, 4, 2), Player(0, 5, 2))
    assert step(s, [EAST, STAY]) == []
    assert (s.players[0].x, s.players[1].x) == (5, 5)


def test_tagged_players_return_after_the_respawn_time():
    s = game(Player(0, 5, 2), Player(1, 6, 2))
    step(s, [STAY, WEST])
    for _ in range(RESPAWN_TICKS - 1):
        step(s, [STAY, STAY])
        assert not s.players[1].active
    events = step(s, [STAY, STAY])
    assert ("respawn", 1) in events
    assert (s.players[1].x, s.players[1].y) == s.map.bases[1][0]


# --- flags ------------------------------------------------------------------


def test_a_team_cannot_stand_on_its_own_flag():
    # rules version 2: guarding the flag cell itself made it untakeable
    m = empty_map()
    fx, fy = m.flags[0]
    s = game(Player(0, fx + 1, fy), Player(1, 15, 9), m=m)
    step(s, [WEST, STAY])
    assert (s.players[0].x, s.players[0].y) == (fx + 1, fy)


def test_the_enemy_can_still_step_onto_your_flag():
    m = empty_map()
    fx, fy = m.flags[0]
    s = game(Player(1, fx + 1, fy), Player(0, 0, 0), m=m)
    events = step(s, [WEST, STAY])
    assert ("pickup", 0) in events


def test_respawn_never_lands_on_your_own_flag():
    m = empty_map()
    s = game(Player(0, 5, 2), Player(1, 6, 2), m=m)
    # fill every red base cell but the flag with red players already standing
    others = [Player(1, x, y) for x, y in m.bases[1][:8]]
    s.players.extend(others)
    step(s, [STAY, WEST] + [STAY] * len(others))  # red seat 1 is tagged on blue's half
    for _ in range(RESPAWN_TICKS + 2):
        step(s, [STAY] * len(s.players))
    assert (s.players[1].x, s.players[1].y) != m.flags[1]


def test_standing_on_the_enemy_flag_picks_it_up_lowest_seat_first():
    m = empty_map()
    fx, fy = m.flags[1]
    s = game(Player(0, fx - 1, fy), Player(0, fx - 1, fy), Player(1, 0, 0), m=m)
    events = step(s, [EAST, EAST, STAY])
    assert ("pickup", 0) in events and s.carrier[1] == 0 and not s.players[1].carrying


def test_carriers_skip_one_tick_in_four():
    s = game(Player(0, 3, 0, carrying=True), Player(1, 15, 9))
    s.carrier[1] = 0
    xs = []
    for _ in range(6):
        step(s, [EAST, STAY])
        xs.append(s.players[0].x)
    assert xs == [4, 5, 6, 6, 7, 8]  # no move on tick 3


def test_tagging_a_carrier_sends_the_flag_home():
    s = game(Player(0, 13, 2, carrying=True), Player(1, 14, 2))
    s.carrier[1] = 0
    step(s, [EAST, STAY])
    assert s.carrier[1] is None and not s.players[0].carrying


def test_bringing_the_flag_home_scores():
    m = empty_map()
    bx, by = m.bases[0][2]  # a base cell east of blue's flag
    s = game(Player(0, bx + 1, by, carrying=True), Player(1, 15, 9), m=m)
    s.carrier[1] = 0
    events = step(s, [WEST, STAY])
    assert ("capture", 0) in events and s.score == [1, 0] and s.carrier[1] is None


def test_a_match_ends_at_three_or_at_the_time_limit():
    s = game(Player(0, 0, 0), Player(1, 15, 9))
    s.score = [3, 1]
    assert s.done and step(s, [EAST, WEST]) == []
    t = game(Player(0, 0, 0), Player(1, 15, 9))
    for _ in range(MAX_TICKS):
        step(t, [STAY, STAY])
    assert t.done and t.tick == MAX_TICKS


# --- determinism and fairness -----------------------------------------------


def test_the_same_inputs_give_the_same_game():
    def play():
        s = new_game(11, 2)
        for t in range(300):
            step(s, [(t * 7 + i * 3) % 5 for i in range(4)])
        return state_hash(s)

    assert play() == play()


def test_the_rules_are_the_same_for_both_teams():
    # a blue move on blue's half mirrors a red move on red's half
    s = game(Player(0, 5, 2), Player(1, 6, 2))
    step(s, [STAY, WEST])
    t = game(Player(1, 10, 2), Player(0, 9, 2))
    step(t, [STAY, EAST])
    assert s.players[1].respawn == t.players[1].respawn == RESPAWN_TICKS


def test_the_engine_is_mirror_symmetric_between_teams():
    # Mirror a whole game (flip left-right, swap the teams, swap east and west):
    # every tick must be the mirror image of the original. A balance check
    # once looked unfair; this showed the engine wasn't the cause.
    from app.game.engine import Rng

    swap = {0: 0, 1: 1, 2: 2, EAST: WEST, WEST: EAST}
    for seed in range(20):
        for k in (2, 3):
            a, b = new_game(seed, k), new_game(seed, k)
            width = a.map.width
            mirror = lambda i: (i + k) % (2 * k)  # noqa: E731  blue seat i <-> red seat k+i
            rng = Rng(seed + 7)
            for _ in range(300):
                acts = [rng.below(5) for _ in range(2 * k)]
                mirrored = [0] * (2 * k)
                for i, act in enumerate(acts):
                    mirrored[mirror(i)] = swap[act]
                step(a, acts)
                step(b, mirrored)
                assert a.score[::-1] == b.score
                for i, p in enumerate(a.players):
                    q = b.players[mirror(i)]
                    x = p.x if p.x < 0 else width - 1 - p.x
                    assert (x, p.y, p.respawn, p.carrying) == (q.x, q.y, q.respawn, q.carrying)

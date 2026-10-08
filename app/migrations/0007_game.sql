-- Capture the flag (ADR 0009, 0011). The Overlay Room's tables stay as they
-- were; nothing here touches them.

CREATE TABLE matches (
    id             INTEGER PRIMARY KEY,
    arena          TEXT    NOT NULL,
    seed           INTEGER NOT NULL,
    team_size      INTEGER NOT NULL CHECK (team_size IN (2, 3)),
    rules_version  INTEGER NOT NULL,
    tick_hz        INTEGER NOT NULL,
    max_ticks      INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'live' CHECK (status IN ('live', 'finished', 'interrupted')),
    score_blue     INTEGER NOT NULL DEFAULT 0,
    score_red      INTEGER NOT NULL DEFAULT 0,
    ticks          INTEGER NOT NULL DEFAULT 0,
    started_at     INTEGER NOT NULL,
    ended_at       INTEGER
);

-- Who played which seat for which ticks, so a record only counts ticks the
-- person actually played (ADR 0011: you may join a match already under way).
CREATE TABLE seat_spans (
    match_id    INTEGER NOT NULL REFERENCES matches (id),
    seat        INTEGER NOT NULL,
    visitor_id  TEXT    NOT NULL,
    from_tick   INTEGER NOT NULL,
    to_tick     INTEGER NOT NULL,
    CHECK (from_tick <= to_tick)
);

CREATE INDEX seat_spans_by_visitor ON seat_spans (visitor_id);

-- A match that has ended is a record: it never changes again.
CREATE TRIGGER matches_frozen BEFORE UPDATE ON matches
WHEN OLD.status != 'live'
BEGIN
    SELECT RAISE(ABORT, 'a finished match is a record and cannot change');
END;

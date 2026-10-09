-- Every finished match replayable, every choice logged (ADR 0014).

CREATE TABLE replays (
    match_id  INTEGER PRIMARY KEY REFERENCES matches (id),
    actions   TEXT    NOT NULL,  -- JSON: one list of actions per turn, a number per seat
    hash      INTEGER NOT NULL   -- FNV-1a of the final state, as spec/engine.ts computes it
);

CREATE TABLE game_events (
    id          INTEGER PRIMARY KEY,
    at          INTEGER NOT NULL,
    match_id    INTEGER REFERENCES matches (id),
    arena       TEXT    NOT NULL,
    visitor_id  TEXT    NOT NULL,
    seat        INTEGER NOT NULL,
    turn        INTEGER NOT NULL,
    dir         INTEGER NOT NULL CHECK (dir BETWEEN 0 AND 4)
);

CREATE INDEX game_events_by_match ON game_events (match_id);

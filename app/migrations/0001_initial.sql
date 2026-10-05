-- A round is one research period: trials run on the in-sample months, and the
-- hold-out months stay locked until the round is revealed (doc/adr/0002).
CREATE TABLE rounds (
    id               INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL UNIQUE,
    in_sample_start  TEXT    NOT NULL CHECK (in_sample_start GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    in_sample_end    TEXT    NOT NULL CHECK (in_sample_end GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    hold_out_end     TEXT    NOT NULL CHECK (hold_out_end GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    revealed_at      INTEGER,
    created_at       INTEGER NOT NULL,
    CHECK (in_sample_start <= in_sample_end AND in_sample_end < hold_out_end)
);

-- Every trial counts against the whole room, so a trial can never be changed
-- or removed once it exists (CLAUDE.md). The triggers enforce that whatever
-- code is written later.
CREATE TABLE trials (
    id            INTEGER PRIMARY KEY,
    round_id      INTEGER NOT NULL REFERENCES rounds (id),
    visitor_id    TEXT    NOT NULL CHECK (length(visitor_id) >= 16),
    leverage      REAL    NOT NULL CHECK (leverage >= 1 AND leverage <= 3),
    cagr          REAL    NOT NULL,
    volatility    REAL    NOT NULL,
    sharpe        REAL    NOT NULL,
    max_drawdown  REAL    NOT NULL CHECK (max_drawdown <= 0 AND max_drawdown >= -1),
    curve         TEXT    NOT NULL,
    created_at    INTEGER NOT NULL
);

CREATE INDEX trials_by_round ON trials (round_id, id);

CREATE TRIGGER trials_never_change BEFORE UPDATE ON trials
BEGIN
    SELECT RAISE(ABORT, 'trials are permanent: they cannot be changed');
END;

CREATE TRIGGER trials_never_go BEFORE DELETE ON trials
BEGIN
    SELECT RAISE(ABORT, 'trials are permanent: they cannot be deleted');
END;

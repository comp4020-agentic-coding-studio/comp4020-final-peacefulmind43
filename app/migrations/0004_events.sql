-- One row per thing a visitor does (ADR 0006). The same events go to stdout
-- as JSON lines; this copy survives restarts so the README can be checked
-- against what people actually did.
CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    at          INTEGER NOT NULL,
    visitor_id  TEXT,                         -- NULL for a visitor with no cookie yet
    round_id    INTEGER REFERENCES rounds (id),
    kind        TEXT    NOT NULL CHECK (kind IN ('visit', 'test', 'refused', 'watch_start', 'watch_end', 'readme')),
    detail      TEXT    NOT NULL DEFAULT '{}'  -- JSON
);

CREATE INDEX events_by_time ON events (at);

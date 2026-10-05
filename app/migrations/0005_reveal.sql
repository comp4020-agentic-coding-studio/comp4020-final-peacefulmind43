-- Rounds reveal on a published schedule (ADR 0007).

ALTER TABLE rounds ADD COLUMN reveal_at INTEGER;

-- A reveal is logged as an event too. SQLite can't widen a CHECK in place, so
-- the events table is rebuilt with the same rows. (Events, unlike trials,
-- carry no promise never to change; their content is copied as it is.)
CREATE TABLE events_new (
    id          INTEGER PRIMARY KEY,
    at          INTEGER NOT NULL,
    visitor_id  TEXT,
    round_id    INTEGER REFERENCES rounds (id),
    kind        TEXT    NOT NULL CHECK (kind IN ('visit', 'test', 'refused', 'watch_start', 'watch_end', 'readme', 'reveal')),
    detail      TEXT    NOT NULL DEFAULT '{}'
);
INSERT INTO events_new (id, at, visitor_id, round_id, kind, detail)
    SELECT id, at, visitor_id, round_id, kind, detail FROM events;
DROP TABLE events;
ALTER TABLE events_new RENAME TO events;
CREATE INDEX events_by_time ON events (at);

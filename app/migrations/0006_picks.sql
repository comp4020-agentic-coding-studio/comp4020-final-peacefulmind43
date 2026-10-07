-- Each person backs one rule before the reveal (ADR 0008).

CREATE TABLE picks (
    round_id     INTEGER NOT NULL REFERENCES rounds (id),
    visitor_id   TEXT    NOT NULL CHECK (length(visitor_id) >= 16),
    rule_key     TEXT    NOT NULL,
    rule_params  TEXT    NOT NULL,
    picked_at    INTEGER NOT NULL,
    PRIMARY KEY (round_id, visitor_id)  -- one pick per person per round
);

-- A pick can change until the reveal, and never after: the revealed round's
-- scores are public. The database holds that line whatever code runs.
CREATE TRIGGER picks_frozen_insert BEFORE INSERT ON picks
WHEN (SELECT revealed_at FROM rounds WHERE id = NEW.round_id) IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'the round is revealed: picks are final');
END;

CREATE TRIGGER picks_frozen_update BEFORE UPDATE ON picks
WHEN (SELECT revealed_at FROM rounds WHERE id = OLD.round_id) IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'the round is revealed: picks are final');
END;

CREATE TRIGGER picks_frozen_delete BEFORE DELETE ON picks
WHEN (SELECT revealed_at FROM rounds WHERE id = OLD.round_id) IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'the round is revealed: picks are final');
END;

-- The kinds of event are now checked in app/activity.py, so a new kind
-- doesn't mean rebuilding this table each time (0005 already had to once).
CREATE TABLE events_new (
    id          INTEGER PRIMARY KEY,
    at          INTEGER NOT NULL,
    visitor_id  TEXT,
    round_id    INTEGER REFERENCES rounds (id),
    kind        TEXT    NOT NULL,
    detail      TEXT    NOT NULL DEFAULT '{}'
);
INSERT INTO events_new (id, at, visitor_id, round_id, kind, detail)
    SELECT id, at, visitor_id, round_id, kind, detail FROM events;
DROP TABLE events;
ALTER TABLE events_new RENAME TO events;
CREATE INDEX events_by_time ON events (at);

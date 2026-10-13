-- The blind teammate study (ADR 0017). For each team that had a person in a
-- match, which bot filled that team's empty seats, the letter it was shown
-- under, and the seed the draw came from. One answer per visitor per match.

CREATE TABLE match_study (
    match_id  INTEGER NOT NULL REFERENCES matches (id),
    team      INTEGER NOT NULL CHECK (team IN (0, 1)),
    bot       TEXT    NOT NULL,  -- the bot type, e.g. "scripted" or "cur4"
    letter    TEXT    NOT NULL,  -- shown as "Bot A", "Bot B" during the match
    seed      INTEGER NOT NULL,  -- the draw's seed, so it can be checked
    PRIMARY KEY (match_id, team)
);

CREATE TABLE study_ratings (
    match_id    INTEGER NOT NULL REFERENCES matches (id),
    visitor_id  TEXT    NOT NULL,
    team        INTEGER NOT NULL CHECK (team IN (0, 1)),
    score       INTEGER CHECK (score BETWEEN 1 AND 5),  -- NULL: skipped
    at          INTEGER NOT NULL,
    PRIMARY KEY (match_id, visitor_id)
);

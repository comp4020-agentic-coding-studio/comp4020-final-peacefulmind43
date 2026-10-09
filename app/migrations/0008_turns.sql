-- Turns that wait for people, up to a deadline (ADR 0012). tick_hz no longer
-- describes how a match runs; it is 0 for turn-based matches from here on,
-- and the deadline is recorded instead.
ALTER TABLE matches ADD COLUMN turn_deadline REAL;

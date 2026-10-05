-- Judge a rule on its timing: what it adds over always holding 1x (ADR 0005).
--
-- Timing rules already in an open round carry no timing figures, and trials
-- never change, so they can't be given any. Such a round is closed here, kept
-- as it is, and the app opens a fresh one, as 0002 did. Nothing is deleted.

ALTER TABLE trials ADD COLUMN timing_sr REAL;
ALTER TABLE trials ADD COLUMN timing_skewness REAL;
ALTER TABLE trials ADD COLUMN timing_kurtosis REAL;
ALTER TABLE trials ADD COLUMN timing_beta REAL;

UPDATE rounds
SET closed_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE revealed_at IS NULL
  AND closed_at IS NULL
  AND EXISTS (
    SELECT 1 FROM trials
    WHERE trials.round_id = rounds.id AND trials.rule_type IN ('vol', 'trend')
  );

-- New timing rules must carry their timing figures.
CREATE TRIGGER trials_need_timing BEFORE INSERT ON trials
WHEN NEW.rule_type IN ('vol', 'trend')
  AND (NEW.timing_sr IS NULL OR NEW.timing_skewness IS NULL
       OR NEW.timing_kurtosis IS NULL OR NEW.timing_beta IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'a timing rule needs its timing figures');
END;

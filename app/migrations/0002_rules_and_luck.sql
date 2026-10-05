-- Rules beyond fixed leverage, trading costs, and the luck discount (ADR 0004).
--
-- Trials from version one used a different calculation (no trading costs) and
-- carry none of the figures the luck discount needs, so they can't be mixed
-- with new ones. Any open round that already has trials is closed here, kept
-- as it is, and the app opens a fresh round for the new rules. Nothing is
-- deleted: those trials stay in their own round.

ALTER TABLE rounds ADD COLUMN closed_at INTEGER;

UPDATE rounds
SET closed_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE revealed_at IS NULL
  AND EXISTS (SELECT 1 FROM trials WHERE trials.round_id = rounds.id);

ALTER TABLE trials ADD COLUMN rule_type TEXT CHECK (rule_type IN ('fixed', 'vol', 'trend'));
ALTER TABLE trials ADD COLUMN rule_key TEXT;
ALTER TABLE trials ADD COLUMN rule_params TEXT;
ALTER TABLE trials ADD COLUMN sr_monthly REAL;
ALTER TABLE trials ADD COLUMN skewness REAL;
ALTER TABLE trials ADD COLUMN kurtosis REAL;
ALTER TABLE trials ADD COLUMN n_months INTEGER;

-- New trials must carry everything the discount needs. (Old rows can't be
-- updated to add it: trials never change.)
CREATE TRIGGER trials_need_rule BEFORE INSERT ON trials
WHEN NEW.rule_key IS NULL OR NEW.rule_type IS NULL OR NEW.sr_monthly IS NULL
  OR NEW.skewness IS NULL OR NEW.kurtosis IS NULL OR NEW.n_months IS NULL
BEGIN
    SELECT RAISE(ABORT, 'a trial needs its rule and its discount figures');
END;

CREATE INDEX trials_by_round_rule ON trials (round_id, rule_key);

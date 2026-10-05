import { expect, it } from "vitest";
import { currentRound, getTrial, months, roundTrials, runTrial } from "./helpers";
import { deflatedSharpe, luckBar, moments, normCdf, normInv, timingSeries, wealth } from "./model";

// ADR 0005 (superseding the discount in 0004): a timing rule is judged on
// what it adds over always holding 1x, with the deflated Sharpe ratio (Bailey
// and López de Prado, 2014) over the distinct timing rules in the round.

it("reproduces the paper's worked example", () => {
  // 100 trials, annualised Sharpe variance 0.5, best annualised Sharpe 2.5,
  // 1250 daily observations, skewness -3, kurtosis 10: DSR ≈ 0.9004, with an
  // expected maximum (daily) Sharpe ratio of about 0.1132.
  const days = 250;
  const srZero = luckBar(100, 0.5 / days);
  expect(srZero).toBeCloseTo(0.1132, 4);
  expect(deflatedSharpe(2.5 / Math.sqrt(days), srZero, 1250, -3, 10)).toBeCloseTo(0.9004, 3);
});

it("has a normal distribution that round-trips", () => {
  for (const p of [0.001, 0.01, 0.3, 0.5, 0.9, 0.99, 0.999]) {
    expect(normCdf(normInv(p))).toBeCloseTo(p, 6);
  }
});

it("removes holding from the timing series", () => {
  // a rule that is exactly 2x the baseline plus a constant has no timing
  // left but the constant
  const b = [1, -2, 3, 0.5, -1];
  const x = b.map((v) => 2 * v + 0.1);
  for (const v of timingSeries(x, b)) expect(v).toBeCloseTo(0.1, 12);
});

it("publishes a luck bar and a chance-the-timing-helps that match an independent calculation", async () => {
  // a spread of distinct rules, by one visitor so all results are visible
  let cookie: string | undefined;
  for (const rule of [
    { type: "fixed", leverage: 1 },
    { type: "vol", leverage: 2, target: 10, lookback: 12 },
    { type: "trend", leverage: 1, months: 6 },
    { type: "vol", leverage: 1, target: 25, lookback: 6 },
    { type: "trend", leverage: 1, months: 6 }, // a repeat: kept, but not a new rule
  ] as const) {
    ({ cookie } = await runTrial(rule, cookie));
  }

  const round = await currentRound();
  const { trials, unlocked } = await roundTrials(cookie);
  expect(unlocked).toBe(true);

  // monthly excess returns: the baseline from the model, each trial from its
  // own published curve
  const all = months();
  const rf = new Map(all.map((m) => [m.month, m.rf]));
  const excessOf = (curve: { month: string; value: number }[]) =>
    curve.map((p, i) => (p.value / (i === 0 ? 1 : curve[i - 1].value) - 1) * 100 - rf.get(p.month)!);
  const base = excessOf(wealth({ type: "fixed", leverage: 1 }, all, round.in_sample_start, round.in_sample_end));

  const keys = new Set<string>();
  const timing = new Map<string, ReturnType<typeof moments> & { t: number }>();
  for (const trial of trials) {
    keys.add(trial.rule.key);
    if (trial.rule.type === "fixed") continue;
    const full = await getTrial(trial.id, cookie!);
    const series = timingSeries(excessOf(full.curve), base);
    timing.set(full.rule.key, { ...moments(series), t: series.length });
  }

  expect(round.distinct_rules).toBe(keys.size);
  expect(round.timing_rules).toBe(timing.size);
  expect(round.trial_count).toBeGreaterThan(keys.size); // the repeat counted as a trial, not a rule

  const n = timing.size;
  const srs = [...timing.values()].map((r) => r.sr);
  const mean = srs.reduce((a, b) => a + b, 0) / n;
  const variance = srs.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1);
  const srZero = luckBar(n, variance);
  expect(round.luck_bar).toBeCloseTo(srZero * Math.sqrt(12), 4);

  for (const trial of trials) {
    if (trial.rule.type === "fixed") {
      expect(trial.confidence, "fixed leverage has no timing to judge").toBeNull();
      continue;
    }
    const r = timing.get(trial.rule.key)!;
    expect(trial.confidence, trial.rule.key).toBeCloseTo(deflatedSharpe(r.sr, srZero, r.t, r.skew, r.kurtosis), 4);
  }
});

import { expect, it } from "vitest";
import { currentRound, getTrial, months, roundTrials, runTrial } from "./helpers";
import { deflatedSharpe, luckBar, moments, normCdf, normInv } from "./model";

// ADR 0004: each result is judged with the deflated Sharpe ratio (Bailey and
// López de Prado, 2014) over the distinct rules tested in the round.

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

it("publishes a luck bar and a chance-it-beats-luck that match an independent calculation", async () => {
  // a spread of distinct rules, by one visitor so all results are visible
  let cookie: string | undefined;
  for (const rule of [
    { type: "fixed", leverage: 1 },
    { type: "vol", leverage: 2, target: 10, lookback: 12 },
    { type: "trend", leverage: 1, months: 6 },
    { type: "fixed", leverage: 1 }, // a repeat: kept, but not a new rule
  ] as const) {
    ({ cookie } = await runTrial(rule, cookie));
  }

  const round = await currentRound();
  const { trials, unlocked } = await roundTrials(cookie);
  expect(unlocked).toBe(true);

  // monthly excess returns, recomputed from each trial's published curve
  const rf = new Map(months().map((m) => [m.month, m.rf]));
  const byRule = new Map<string, ReturnType<typeof moments> & { t: number }>();
  for (const trial of trials) {
    const full = await getTrial(trial.id, cookie!);
    const excess = full.curve.map((p, i) => (p.value / (i === 0 ? 1 : full.curve[i - 1].value) - 1) * 100 - rf.get(p.month)!);
    byRule.set(full.rule.key, { ...moments(excess), t: excess.length });
  }

  const n = byRule.size;
  expect(round.distinct_rules).toBe(n);
  expect(round.trial_count).toBeGreaterThan(n); // the repeat counted as a trial, not a rule

  const srs = [...byRule.values()].map((r) => r.sr);
  const mean = srs.reduce((a, b) => a + b, 0) / n;
  const variance = srs.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1);
  const srZero = luckBar(n, variance);
  expect(round.luck_bar).toBeCloseTo(srZero * Math.sqrt(12), 4);

  for (const trial of trials) {
    const r = byRule.get(trial.rule.key)!;
    expect(trial.confidence, trial.rule.key).toBeCloseTo(deflatedSharpe(r.sr, srZero, r.t, r.skew, r.kurtosis), 4);
  }
});

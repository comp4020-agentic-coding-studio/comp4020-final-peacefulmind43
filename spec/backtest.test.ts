import { expect, it } from "vitest";
import { currentRound, getTrial, months, runTrial } from "./helpers";
import { type Rule, wealth } from "./model";

// CLAUDE.md: statistics need a check against a known value. These recompute a
// trial from data/momentum.csv with spec/model.ts, which follows ADR 0004
// independently of the app, and compare.

const rules: Rule[] = [
  { type: "fixed", leverage: 1 },
  { type: "fixed", leverage: 2 },
  { type: "vol", leverage: 2, target: 15, lookback: 6 },
  { type: "vol", leverage: 3, target: 25, lookback: 12 },
  { type: "trend", leverage: 1.5, months: 10 },
];

for (const rule of rules) {
  it(`matches an independent backtest: ${JSON.stringify(rule)}`, async () => {
    const round = await currentRound();
    const expected = wealth(rule, months(), round.in_sample_start, round.in_sample_end);
    const { id, cookie } = await runTrial(rule);
    const trial = await getTrial(id, cookie);

    expect(trial.curve.map((p) => p.month)).toEqual(expected.map((p) => p.month));
    trial.curve.forEach((p, i) => {
      expect(p.value / expected[i].value, `value at ${p.month}`).toBeCloseTo(1, 9);
    });

    const years = expected.length / 12;
    expect(trial.stats.cagr).toBeCloseTo(expected.at(-1)!.value ** (1 / years) - 1, 9);

    let peak = 1; // the starting money is the first peak
    let worst = 0;
    for (const { value } of expected) {
      peak = Math.max(peak, value);
      worst = Math.min(worst, value / peak - 1);
    }
    expect(trial.stats.max_drawdown).toBeCloseTo(worst, 9);
  });
}

it("computes the Sharpe ratio from monthly excess returns", async () => {
  const round = await currentRound();
  const rule: Rule = { type: "fixed", leverage: 1 };
  const all = months();
  const values = wealth(rule, all, round.in_sample_start, round.in_sample_end);
  const rf = new Map(all.map((m) => [m.month, m.rf]));
  const excess = values.map((p, i) => (p.value / (i === 0 ? 1 : values[i - 1].value) - 1) * 100 - rf.get(p.month)!);
  const mean = excess.reduce((a, b) => a + b, 0) / excess.length;
  const sd = Math.sqrt(excess.reduce((a, b) => a + (b - mean) ** 2, 0) / (excess.length - 1));
  const { id, cookie } = await runTrial(rule);
  expect((await getTrial(id, cookie)).stats.sharpe).toBeCloseTo((mean / sd) * Math.sqrt(12), 9);
});

// Hand-checkable cases for the model itself, so the reference is pinned too.
it("charges costs the way ADR 0004 says", () => {
  const flat = [
    { month: "2000-01", momentum: 10, market: 0, rf: 0 },
    { month: "2000-02", momentum: -10, market: 0, rf: 0 },
  ];
  // 1x: +10% less 1%/12 holding less 0.1% first purchase, then -10% less 1%/12
  const h = 1 / 12;
  const oneX = (1 + (10 - h - 0.1) / 100) * (1 + (-10 - h) / 100);
  expect(wealth({ type: "fixed", leverage: 1 }, flat, "2000-01", "2000-02").at(-1)!.value).toBeCloseTo(oneX, 12);
  // 2x: 2x the move, 1.5%/12 spread on the borrowed half, 2x holding, 0.2% purchase
  const twoX = (1 + (20 - 1.5 / 12 - 2 * h - 0.2) / 100) * (1 + (-20 - 1.5 / 12 - 2 * h) / 100);
  expect(wealth({ type: "fixed", leverage: 2 }, flat, "2000-01", "2000-02").at(-1)!.value).toBeCloseTo(twoX, 12);
});

it("holds cash under the trend filter when the market is below its average", () => {
  // The market falls every month. With one month of history the level equals
  // its own average, so the rule stays in for month 2; by the end of month 2
  // the level is below its 2-month average, so month 3 is in cash.
  const falling = ["01", "02", "03", "04"].map((mm) => ({ month: `2000-${mm}`, momentum: 5, market: -5, rf: 0.3 }));
  const out = wealth({ type: "trend", leverage: 1, months: 2 }, falling, "2000-01", "2000-04");
  expect(out[1].value / out[0].value).toBeCloseTo(1 + (5 - 1 / 12) / 100, 12);
  // month 3: sell everything (0.1% of the amount moved), earn the T-bill rate
  expect(out[2].value / out[1].value).toBeCloseTo(1 + (0.3 - 0.1) / 100, 12);
  expect(out[3].value / out[2].value).toBeCloseTo(1 + 0.3 / 100, 12);
});

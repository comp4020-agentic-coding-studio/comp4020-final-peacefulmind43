import { expect, it } from "vitest";
import { currentRound, getTrial, months, runTrial } from "./helpers";

// CLAUDE.md: statistics need a check against a known value. These recompute a
// trial from data/momentum.csv, independently of the app, and compare.
//
// The rule being tested: hold `leverage` times your money in the momentum
// portfolio, rebalanced monthly. Above 1x, the borrowed part costs the T-bill
// rate plus 1.5% a year (doc/adr/0002).

const SPREAD_PER_MONTH = 1.5 / 12;

async function inSample() {
  const round = await currentRound();
  return months().filter((m) => m.month >= round.in_sample_start && m.month <= round.in_sample_end);
}

function wealth(leverage: number, rows: ReturnType<typeof months>): number[] {
  let value = 1;
  return rows.map((m) => {
    const borrowCost = (leverage - 1) * (m.rf + SPREAD_PER_MONTH);
    value *= 1 + (leverage * m.momentum - borrowCost) / 100;
    value = Math.max(value, 0); // wiped out stays wiped out
    return value;
  });
}

for (const leverage of [1, 2]) {
  it(`matches an independent backtest at ${leverage}x`, async () => {
    const rows = await inSample();
    const expected = wealth(leverage, rows);
    const trial = await getTrial((await runTrial(String(leverage))).id);

    expect(trial.curve).toHaveLength(rows.length);
    expect(trial.curve.at(-1)!.value / expected.at(-1)!).toBeCloseTo(1, 6);

    const years = rows.length / 12;
    expect(trial.stats.cagr).toBeCloseTo(expected.at(-1)! ** (1 / years) - 1, 6);

    let peak = 1; // the starting money is the first peak
    let worst = 0;
    for (const v of expected) {
      peak = Math.max(peak, v);
      worst = Math.min(worst, v / peak - 1);
    }
    expect(trial.stats.max_drawdown).toBeCloseTo(worst, 6);
  });
}

it("computes the Sharpe ratio from monthly excess returns", async () => {
  const rows = await inSample();
  const values = wealth(1, rows);
  const excess = values.map((v, i) => (v / (i === 0 ? 1 : values[i - 1]) - 1) * 100 - rows[i].rf);
  const mean = excess.reduce((a, b) => a + b, 0) / excess.length;
  const sd = Math.sqrt(excess.reduce((a, b) => a + (b - mean) ** 2, 0) / (excess.length - 1));
  const trial = await getTrial((await runTrial("1")).id);
  expect(trial.stats.sharpe).toBeCloseTo((mean / sd) * Math.sqrt(12), 6);
});

// A hand-checkable case: two months of +10% then -10% at 1x is 0.99 of the
// starting money, whatever the data. Guarded by the formula above; kept here
// so the arithmetic of `wealth` itself is pinned.
it("compounds the way the formula says", () => {
  const rows = [
    { month: "2000-01", momentum: 10, market: 0, rf: 0 },
    { month: "2000-02", momentum: -10, market: 0, rf: 0 },
  ];
  expect(wealth(1, rows).at(-1)).toBeCloseTo(0.99, 12);
  // at 2x with free borrowing: 1.2 * 0.8
  expect(wealth(2, rows.map((r) => ({ ...r, rf: -SPREAD_PER_MONTH }))).at(-1)).toBeCloseTo(0.96, 12);
});

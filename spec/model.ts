// An independent implementation of the rules, costs and luck discount in
// doc/adr/0004, written from the record rather than from the app's code. The
// spec compares the app's published numbers against these.

import type { Month } from "./helpers";

export const BORROW_SPREAD = 1.5; // % a year over the T-bill (ADR 0002)
export const HOLDING_COST = 1.0; // % a year on the amount held
export const SWITCHING_COST = 0.1; // % of the amount moved

export type Rule =
  | { type: "fixed"; leverage: number }
  | { type: "vol"; leverage: number; target: number; lookback: number }
  | { type: "trend"; leverage: number; months: number };

function sampleSd(xs: number[]): number {
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (xs.length - 1));
}

// How much of your money the rule holds in month `t` of `all`, deciding with
// data up to month t-1 only.
export function weight(rule: Rule, all: Month[], t: number): number {
  if (rule.type === "fixed" || t === 0) return rule.leverage;
  if (rule.type === "vol") {
    const past = all.slice(Math.max(0, t - rule.lookback), t).map((m) => m.momentum);
    if (past.length < 2) return rule.leverage;
    const annualVol = (sampleSd(past) * Math.sqrt(12)) / 100;
    return Math.min(rule.leverage, rule.target / 100 / annualVol);
  }
  // trend: market index level at the end of each month, from the data start
  let level = 1;
  const levels = all.slice(0, t).map((m) => (level *= 1 + m.market / 100));
  const recent = levels.slice(-rule.months);
  const average = recent.reduce((a, b) => a + b, 0) / recent.length;
  return levels.at(-1)! >= average ? rule.leverage : 0;
}

// Value of 1 unit of starting money at the end of each month in [start, end].
export function wealth(rule: Rule, all: Month[], start: string, end: string): { month: string; value: number }[] {
  let value = 1;
  let held = 0;
  const out: { month: string; value: number }[] = [];
  all.forEach((m, t) => {
    if (m.month < start || m.month > end) return;
    const w = weight(rule, all, t);
    const monthly =
      w * m.momentum +
      (1 - w) * m.rf -
      Math.max(w - 1, 0) * (BORROW_SPREAD / 12) -
      w * (HOLDING_COST / 12) -
      SWITCHING_COST * Math.abs(w - held);
    held = w;
    value = Math.max(value * (1 + monthly / 100), 0);
    out.push({ month: m.month, value });
  });
  return out;
}

// --- the deflated Sharpe ratio (Bailey and López de Prado, 2014) -------------

// erf by Abramowitz and Stegun 7.1.26 is too coarse here; this is the
// complementary error function from Numerical Recipes (erfcc), |error| < 1.2e-7.
function erfc(x: number): number {
  const z = Math.abs(x);
  const t = 1 / (1 + 0.5 * z);
  const r =
    t *
    Math.exp(
      -z * z -
        1.26551223 +
        t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))),
    );
  return x >= 0 ? r : 2 - r;
}

export const normCdf = (x: number): number => 0.5 * erfc(-x / Math.SQRT2);

// Acklam's inverse normal CDF, relative error < 1.2e-9.
export function normInv(p: number): number {
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.38357751867269e2, -3.066479806614716e1, 2.506628277459239];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  const lo = 0.02425;
  if (p < lo) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p > 1 - lo) return -normInv(1 - p);
  const q = p - 0.5;
  const r = q * q;
  return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

const EULER_GAMMA = 0.5772156649015329;

// The Sharpe ratio expected from the best of n rules with no skill, given the
// variance of their Sharpe ratios.
export function luckBar(n: number, variance: number): number {
  return Math.sqrt(variance) * ((1 - EULER_GAMMA) * normInv(1 - 1 / n) + EULER_GAMMA * normInv(1 - 1 / (n * Math.E)));
}

export function deflatedSharpe(sr: number, srZero: number, t: number, skew: number, kurtosis: number): number {
  return normCdf(((sr - srZero) * Math.sqrt(t - 1)) / Math.sqrt(1 - skew * sr + ((kurtosis - 1) / 4) * sr * sr));
}

// Per-period Sharpe ratio (sample sd), skewness and kurtosis (not excess) of a
// series of excess returns.
export function moments(xs: number[]): { sr: number; skew: number; kurtosis: number } {
  const n = xs.length;
  const mean = xs.reduce((a, b) => a + b, 0) / n;
  const m = (k: number) => xs.reduce((a, b) => a + (b - mean) ** k, 0) / n;
  return { sr: mean / sampleSd(xs), skew: m(3) / m(2) ** 1.5, kurtosis: m(4) / m(2) ** 2 };
}

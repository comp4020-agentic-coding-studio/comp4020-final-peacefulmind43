import { expect, it } from "vitest";
import { currentRound, getTrial, runTrial, url } from "./helpers";

// README: a stranger can run a trial and find it still there when they come
// back. (Who else sees it, and when, is ADR 0003: see visibility.test.ts.)

it("keeps a visitor's trial for them when they come back", async () => {
  const { id, cookie, res } = await runTrial("1.5");
  expect(res.status).toBe(303);
  expect(id).toBeGreaterThan(0);
  expect(cookie, "the first trial should give the visitor a cookie").toMatch(/=/);

  const back = await fetch(url("/"), { headers: { cookie } });
  expect(await back.text()).toContain(`data-trial-id="${id}"`);

  const trial = await getTrial(id, cookie);
  expect(trial.leverage).toBe(1.5);
  expect(trial.rule.type).toBe("fixed");
});

it("tells visitors apart", async () => {
  const a = await runTrial("1");
  const b = await runTrial("1");
  const again = await runTrial("1", a.cookie);
  const ta = await getTrial(a.id, a.cookie);
  const tb = await getTrial(b.id, b.cookie);
  const tagain = await getTrial(again.id, a.cookie);
  expect(ta.visitor).not.toBe(tb.visitor);
  expect(tagain.visitor).toBe(ta.visitor);
});

it("counts every trial in the round", async () => {
  const before = (await currentRound()).trial_count;
  await runTrial("2");
  expect((await currentRound()).trial_count).toBe(before + 1);
});

it("accepts each rule on the menu", async () => {
  for (const rule of [
    { type: "vol", leverage: 2, target: 15, lookback: 6 },
    { type: "trend", leverage: 1.5, months: 10 },
  ] as const) {
    const { id, cookie, res } = await runTrial(rule);
    expect(res.status, JSON.stringify(rule)).toBe(303);
    expect((await getTrial(id, cookie)).rule).toMatchObject(rule);
  }
});

it("refuses a rule outside the menu, and doesn't count it", async () => {
  const before = (await currentRound()).trial_count;
  const bad = [
    "10",
    "-1",
    "abc",
    "",
    { type: "vol", leverage: 2, target: 33, lookback: 6 },
    { type: "vol", leverage: 2, target: 15, lookback: 7 },
    { type: "trend", leverage: 2, months: 3 },
    { type: "short", leverage: 2 },
  ] as const;
  for (const rule of bad) {
    const { res } = await runTrial(rule as never);
    expect(res.status, JSON.stringify(rule)).toBeGreaterThanOrEqual(400);
    expect(res.status).toBeLessThan(500);
  }
  expect((await currentRound()).trial_count).toBe(before);
});

// CLAUDE.md: never hide, edit or delete a trial.
it("never deletes or edits a trial", async () => {
  const { id, cookie } = await runTrial("1.25");
  for (const method of ["DELETE", "PUT", "PATCH"]) {
    const res = await fetch(url(`/api/trials/${id}`), { method, headers: { cookie } });
    expect(res.ok, `${method} /api/trials/${id}`).toBe(false);
  }
  expect((await getTrial(id, cookie)).leverage).toBe(1.25);
});

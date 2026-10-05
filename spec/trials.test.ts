import { expect, it } from "vitest";
import { currentRound, getTrial, runTrial, url } from "./helpers";

// README: a stranger can run a trial and find it still there when they come
// back, and everyone else in the room sees it too.

it("keeps a visitor's trial, for them and for everyone else", async () => {
  const { id, cookie, res } = await runTrial("1.5");
  expect(res.status).toBe(303);
  expect(id).toBeGreaterThan(0);
  expect(cookie, "the first trial should give the visitor a cookie").toMatch(/=/);

  const back = await fetch(url("/"), { headers: { cookie } });
  expect(await back.text()).toContain(`data-trial-id="${id}"`);

  const stranger = await fetch(url("/"));
  expect(await stranger.text()).toContain(`data-trial-id="${id}"`);

  const trial = await getTrial(id);
  expect(trial.leverage).toBe(1.5);
});

it("tells visitors apart", async () => {
  const a = await runTrial("1");
  const b = await runTrial("1");
  const again = await runTrial("1", a.cookie);
  const [ta, tb, tagain] = await Promise.all([a.id, b.id, again.id].map(getTrial));
  expect(ta.visitor).not.toBe(tb.visitor);
  expect(tagain.visitor).toBe(ta.visitor);
});

it("counts every trial in the round", async () => {
  const before = (await currentRound()).trial_count;
  await runTrial("2");
  expect((await currentRound()).trial_count).toBe(before + 1);
});

it("refuses a leverage outside the menu, and doesn't count it", async () => {
  const before = (await currentRound()).trial_count;
  for (const bad of ["10", "-1", "abc", ""]) {
    const { res } = await runTrial(bad);
    expect(res.status, `leverage ${JSON.stringify(bad)}`).toBeGreaterThanOrEqual(400);
    expect(res.status).toBeLessThan(500);
  }
  expect((await currentRound()).trial_count).toBe(before);
});

// CLAUDE.md: never hide, edit or delete a trial.
it("never deletes or edits a trial", async () => {
  const { id } = await runTrial("1.25");
  for (const method of ["DELETE", "PUT", "PATCH"]) {
    const res = await fetch(url(`/api/trials/${id}`), { method });
    expect(res.ok, `${method} /api/trials/${id}`).toBe(false);
  }
  expect((await getTrial(id)).leverage).toBe(1.25);
});

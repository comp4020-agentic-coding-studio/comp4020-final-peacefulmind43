import { expect, it } from "vitest";
import { collectEvents, currentRound, months, readLog, runTrial, url } from "./helpers";
import { type Rule, wealth } from "./model";

// ADR 0007: rounds reveal on a published schedule. The spec can't wait a week,
// so it uses the operator key, which CI sets to a throwaway value. Without the
// key these checks can't run, and say so rather than passing quietly.

const key = process.env.REVEAL_KEY;
const reveal = (k?: string) =>
  fetch(url("/api/rounds/current/reveal"), { method: "POST", headers: k ? { "x-reveal-key": k } : {} });

it("publishes when the open round will be revealed", async () => {
  const round = (await currentRound()) as Awaited<ReturnType<typeof currentRound>> & { reveal_at: number; reveal_text: string };
  expect(round.reveal_at).toBeGreaterThan(Date.now() / 1000);
  expect(round.reveal_text).toMatch(/Wednesday/);
  const page = await (await fetch(url("/"))).text();
  expect(page).toContain(round.reveal_text);
});

it.runIf(key)("refuses an early reveal without the operator key", async () => {
  expect((await reveal()).status).toBe(403);
  expect((await reveal("wrong")).status).toBe(403);
});

it.runIf(key)("reveals a round: live to open pages, in public, and against an independent model", async () => {
  const rules: Rule[] = [
    { type: "fixed", leverage: 1 },
    { type: "vol", leverage: 2, target: 15, lookback: 12 },
    { type: "trend", leverage: 1, months: 10 },
  ];
  let cookie: string | undefined;
  for (const rule of rules) ({ cookie } = await runTrial(rule, cookie));
  const before = await currentRound();

  let response: Response | undefined;
  let sentAt = 0;
  const events = await collectEvents(
    cookie,
    5000,
    async () => {
      sentAt = Date.now();
      response = await reveal(key);
    },
    (evs) => evs.some((e) => e.event === "reveal"),
  );
  expect(response?.status).toBe(200);
  const live = events.find((e) => e.event === "reveal");
  expect(live, "no reveal event reached the open page").toBeDefined();
  expect(live!.at - sentAt).toBeLessThan(1000);
  expect(live!.data.revealed_round_id).toBe(before.id);

  // a fresh round is open, and still locked
  const after = await currentRound();
  expect(after.id).not.toBe(before.id);
  expect(after.revealed).toBe(false);
  expect(live!.data.round.id).toBe(after.id);

  // the revealed round is public: no cookie needed
  const res = await fetch(url(`/api/rounds/${before.id}`));
  expect(res.status).toBe(200);
  const revealed = await res.json();
  expect(revealed.revealed).toBe(true);
  expect(revealed.hold_out_start).toBe("2016-01");

  const all = months();
  const end = all.at(-1)!.month;
  expect(revealed.hold_out_end).toBe(end);
  for (const rule of rules) {
    const found = revealed.rules.find((r: any) => r.rule.type === rule.type && r.rule.leverage === rule.leverage &&
      (r.rule.target ?? null) === ((rule as any).target ?? null) && (r.rule.months ?? null) === ((rule as any).months ?? null));
    expect(found, JSON.stringify(rule)).toBeDefined();
    const locked = wealth(rule, all, "2016-01", end);
    const years = locked.length / 12;
    expect(found.hold_out.cagr).toBeCloseTo(locked.at(-1)!.value ** (1 / years) - 1, 9);
    if (rule.type === "fixed") expect(found.hold_out.timing_added).toBeNull();
    else expect(typeof found.hold_out.timing_added).toBe("number");
  }

  const page = await (await fetch(url(`/rounds/${before.id}`))).text();
  for (const r of revealed.rules) expect(page).toContain(r.rule.label);

  // an early reveal is never silent
  const { events: log } = await readLog();
  expect(log.some((e) => e.event === "reveal" && e.detail?.early === true && e.detail?.round_id === before.id)).toBe(true);
});

it.skipIf(key)("skips the reveal checks: REVEAL_KEY isn't set for this run", () => {
  console.warn("REVEAL_KEY isn't set: the reveal checks did not run");
});

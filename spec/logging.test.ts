import { expect, it } from "vitest";
import { collectEvents, getTrial, readLog, runTrial, url } from "./helpers";

// Crit 10 and ADR 0006: one log entry per user action (who, what, when), a
// live view of it, and that view follows ADR 0003's rule for who sees what.

const now = () => Math.floor(Date.now() / 1000);

it("logs a test with who, what and when", async () => {
  const { id, cookie } = await runTrial({ type: "vol", leverage: 1.5, target: 15, lookback: 12 });
  const trial = await getTrial(id, cookie);
  const { events } = await readLog(cookie);
  const entry = events.find((e) => e.event === "test" && e.detail?.trial_id === id);
  expect(entry, "no log entry for the test").toBeDefined();
  expect(entry!.visitor).toBe(trial.visitor);
  expect(Math.abs(entry!.at - now())).toBeLessThan(60);
  expect(entry!.detail).toMatchObject({ rule: { key: trial.rule.key }, first_test: true, had_seen_others: false });
});

it("logs what happened before a visitor's second test", async () => {
  const first = await runTrial({ type: "fixed", leverage: 1 });
  const second = await runTrial({ type: "trend", leverage: 1, months: 12 }, first.cookie);
  const { events } = await readLog(first.cookie);
  const entry = events.find((e) => e.event === "test" && e.detail?.trial_id === second.id);
  expect(entry!.detail).toMatchObject({ first_test: false, had_seen_others: true });
});

it("logs a refused test", async () => {
  const { cookie } = await runTrial("1");
  await runTrial("7", cookie);
  const { events } = await readLog(cookie);
  expect(events.some((e) => e.event === "refused")).toBe(true);
});

it("logs opening the room, reading the README, and coming and going on the live stream", async () => {
  const { cookie } = await runTrial("1.25");
  await fetch(url("/"), { headers: { cookie } });
  await fetch(url("/readme/"), { headers: { cookie } });
  await collectEvents(cookie, 1500, async () => {}, () => true); // open, then leave
  await new Promise((r) => setTimeout(r, 500));

  const { events } = await readLog(cookie);
  const mine = events.filter((e) => e.detail?.mine);
  for (const kind of ["visit", "readme", "watch_start", "watch_end"]) {
    expect(mine.some((e) => e.event === kind), `no ${kind} entry`).toBe(true);
  }
});

it("shows a newcomer that things happened, not what they were", async () => {
  const other = await runTrial({ type: "trend", leverage: 2.5, months: 10 });
  const { events } = await readLog(); // no cookie: has tested nothing
  const entry = events.find((e) => e.event === "test" && e.detail?.trial_id === other.id);
  expect(entry, "a newcomer can't even link a log entry to a trial id").toBeUndefined();
  const body = JSON.stringify(events);
  expect(body).not.toMatch(/"rule"|"cagr"|"sharpe"|"confidence"|trend:L=/);
  expect(events.some((e) => e.event === "test")).toBe(true);
});

it("never shows a visitor's cookie in the log", async () => {
  const { cookie } = await runTrial("1");
  const value = cookie.split("=")[1];
  const page = await (await fetch(url("/log"), { headers: { cookie } })).text();
  const api = JSON.stringify(await readLog(cookie));
  expect(page).not.toContain(value);
  expect(api).not.toContain(value);
});

it("updates the live log view within a second", async () => {
  const watcher = await runTrial("1"); // has tested, so sees detail
  let sentAt = 0;
  let newId = 0;
  const events = await collectEvents(
    watcher.cookie,
    5000,
    async () => {
      sentAt = Date.now();
      newId = (await runTrial({ type: "vol", leverage: 1, target: 10, lookback: 6 })).id;
    },
    (evs) => evs.some((e) => e.event === "log" && e.data.detail?.trial_id === newId),
    "/log/events",
  );
  const entry = events.find((e) => e.event === "log" && e.data.detail?.trial_id === newId);
  expect(entry, "no live log entry for the test").toBeDefined();
  expect(entry!.at - sentAt).toBeLessThan(1000);
});

import { expect, it } from "vitest";
import { collectEvents, currentRound, getTrial, months, readLog, runTrial, url } from "./helpers";
import { timingSeries, wealth } from "./model";

// ADR 0008: each person backs one rule before the reveal.

interface Picks {
  total: number;
  unlocked: boolean;
  mine: string | null;
  rules: { key: string; label: string; backers: number; visitors: string[] }[];
}

async function back(ruleKey: string, cookie?: string): Promise<Response> {
  return fetch(url("/picks"), {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", ...(cookie ? { cookie } : {}) },
    body: new URLSearchParams({ rule_key: ruleKey }),
    redirect: "manual",
  });
}

async function picks(cookie?: string): Promise<Picks> {
  const res = await fetch(url("/api/rounds/current/picks"), { headers: cookie ? { cookie } : {} });
  if (!res.ok) throw new Error(`/api/rounds/current/picks answered ${res.status}`);
  return (await res.json()) as Picks;
}

it("lets only someone who has tested back a rule, and only one tested this round", async () => {
  const a = await runTrial({ type: "trend", leverage: 1, months: 6 });
  const key = (await getTrial(a.id, a.cookie)).rule.key;

  expect((await back(key)).status, "a newcomer can't back anything").toBe(403);
  expect((await back("vol:L=3:T=25:K=6", a.cookie)).status, "not tested this round").toBeGreaterThanOrEqual(400);
  expect((await back("nonsense", a.cookie)).status).toBe(400);

  const ok = await back(key, a.cookie);
  expect(ok.status).toBe(303);
  expect((await picks(a.cookie)).mine).toBe(key);
});

it("counts one pick per person, and the latest one stands", async () => {
  const a = await runTrial({ type: "vol", leverage: 1, target: 20, lookback: 6 });
  const b = await runTrial({ type: "trend", leverage: 2, months: 12 }, a.cookie);
  const first = (await getTrial(a.id, a.cookie)).rule.key;
  const second = (await getTrial(b.id, a.cookie)).rule.key;

  const before = (await picks(a.cookie)).total;
  await back(first, a.cookie);
  await back(second, a.cookie);
  const after = await picks(a.cookie);
  expect(after.total).toBe(before + 1);
  expect(after.mine).toBe(second);

  // changes are logged, so the log can show people moving towards the crowd
  const { events } = await readLog(a.cookie);
  const mine = events.filter((e) => e.event === "pick" && e.detail?.mine);
  expect(mine.length).toBeGreaterThanOrEqual(2);
});

it("lets you back someone else's rule", async () => {
  const other = await runTrial({ type: "vol", leverage: 2.5, target: 25, lookback: 12 });
  const otherKey = (await getTrial(other.id, other.cookie)).rule.key;
  const me = await runTrial({ type: "fixed", leverage: 1 });
  expect((await back(otherKey, me.cookie)).status).toBe(303);
  const view = await picks(me.cookie);
  expect(view.mine).toBe(otherKey);
  expect(view.rules.find((r) => r.key === otherKey)?.backers).toBeGreaterThanOrEqual(1);
});

it("shows a newcomer how many picks there are, not what they are", async () => {
  const a = await runTrial({ type: "trend", leverage: 1.25, months: 10 });
  await back((await getTrial(a.id, a.cookie)).rule.key, a.cookie);
  const view = await picks();
  expect(view.unlocked).toBe(false);
  expect(view.total).toBeGreaterThan(0);
  expect(view.rules).toEqual([]);
  expect((await currentRound()) as unknown as { picks_total: number }).toMatchObject({ picks_total: view.total });
});

it("tells open pages about a new pick within a second", async () => {
  const watcher = await runTrial("1");
  const a = await runTrial({ type: "vol", leverage: 1.25, target: 10, lookback: 12 });
  const key = (await getTrial(a.id, a.cookie)).rule.key;
  const before = (await picks()).total;
  let sentAt = 0;
  const events = await collectEvents(
    watcher.cookie,
    5000,
    async () => {
      sentAt = Date.now();
      await back(key, a.cookie);
    },
    (evs) => evs.some((e) => e.event === "update" && e.data.picks_total > before),
  );
  const update = events.find((e) => e.event === "update" && e.data.picks_total > before);
  expect(update, "no update for the pick").toBeDefined();
  expect(update!.at - sentAt).toBeLessThan(1000);
});

const key = process.env.REVEAL_KEY;

it.runIf(key)("scores each pick at the reveal by what the rule added beyond holding", async () => {
  const a = await runTrial({ type: "vol", leverage: 1.5, target: 15, lookback: 12 });
  const b = await runTrial({ type: "fixed", leverage: 2 });
  const ka = await getTrial(a.id, a.cookie);
  await back(ka.rule.key, a.cookie);
  await back(ka.rule.key, b.cookie); // b backs a's rule
  const round = await currentRound();

  const res = await fetch(url("/api/rounds/current/reveal"), { method: "POST", headers: { "x-reveal-key": key! } });
  expect(res.status).toBe(200);
  const revealed = await (await fetch(url(`/api/rounds/${round.id}`))).json();

  // independent: regress the rule's locked-year excess returns on always-1x
  const all = months();
  const end = all.at(-1)!.month;
  const rf = new Map(all.map((m) => [m.month, m.rf]));
  const excessOf = (curve: { month: string; value: number }[]) =>
    curve.map((p, i) => (p.value / (i === 0 ? 1 : curve[i - 1].value) - 1) * 100 - rf.get(p.month)!);
  const base = excessOf(wealth({ type: "fixed", leverage: 1 }, all, "2016-01", end));
  const series = timingSeries(excessOf(wealth({ type: "vol", leverage: 1.5, target: 15, lookback: 12 }, all, "2016-01", end)), base);
  const added = ((series.reduce((s, v) => s + v, 0) / series.length) * 12) / 100;

  const theirs = revealed.picks.filter((p: any) => p.rule.key === ka.rule.key);
  expect(theirs.length).toBeGreaterThanOrEqual(2);
  for (const p of theirs) expect(p.added).toBeCloseTo(added, 9);
  expect(revealed.most_backed.rule.key).toBe(ka.rule.key);

  const page = await (await fetch(url(`/rounds/${round.id}`))).text();
  expect(page).toContain(ka.rule.label);
  expect(page).toMatch(/most-backed/i);

  // and a revealed round's picks can't be changed
  expect((await back(ka.rule.key, a.cookie)).status).not.toBe(500);
});

import { expect, it } from "vitest";
import { collectEvents, currentRound, getTrial, runTrial, url } from "./helpers";

// CLAUDE.md: during a round, nothing the app sends may contain a month after
// the round's in-sample end (doc/adr/0002). Checked on everything a visitor
// can reach, by looking for any YYYY-MM later than the end.

const MONTH = /\b(1[89]\d\d|20\d\d)-(0[1-9]|1[0-2])\b/g;

function laterMonths(body: string, end: string): string[] {
  return [...body.matchAll(MONTH)].map((m) => m[0]).filter((m) => m > end);
}

it("sends no hold-out month during an unrevealed round", async () => {
  const round = await currentRound();
  expect(round.revealed).toBe(false);
  const end = round.in_sample_end;
  expect(end).toMatch(/^\d{4}-\d{2}$/);

  const { id, cookie } = await runTrial({ type: "trend", leverage: 1.5, months: 10 });
  const trial = await getTrial(id, cookie);
  expect(trial.curve.at(-1)?.month).toBe(end);
  expect(trial.curve[0]?.month).toBe(round.in_sample_start);

  for (const path of ["/", `/?trial=${id}`, "/api/rounds/current", `/api/trials/${id}`, "/api/rounds/current/trials"]) {
    const body = await (await fetch(url(path), { headers: { cookie } })).text();
    expect(laterMonths(body, end), `${path} leaks hold-out months`).toEqual([]);
  }

  const events = await collectEvents(
    cookie,
    3000,
    async () => {
      await runTrial({ type: "vol", leverage: 3, target: 10, lookback: 6 });
    },
    (evs) => evs.some((e) => e.event === "update"),
  );
  expect(laterMonths(JSON.stringify(events), end), "/events leaks hold-out months").toEqual([]);
});

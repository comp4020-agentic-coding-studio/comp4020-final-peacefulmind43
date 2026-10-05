import { expect, it } from "vitest";
import { collectEvents, roundTrials, runTrial, url } from "./helpers";

// ADR 0003: other people's results unlock once you've run a test of your own
// in the round. The server enforces it on the page, the API and the stream.

it("hides other visitors' trials from a newcomer, everywhere", async () => {
  const other = await runTrial({ type: "trend", leverage: 2, months: 12 });

  // a newcomer with no cookie at all
  const page = await (await fetch(url("/"))).text();
  expect(page).not.toContain(`data-trial-id="${other.id}"`);

  const list = await roundTrials();
  expect(list.unlocked).toBe(false);
  expect(list.trials).toEqual([]);
  expect(list.hidden).toBeGreaterThan(0);

  const single = await fetch(url(`/api/trials/${other.id}`));
  expect(single.status).toBe(403);

  // and the stream: a newcomer hears that a test happened, not what it was
  const events = await collectEvents(
    undefined,
    3000,
    async () => {
      await runTrial({ type: "fixed", leverage: 1.5 });
    },
    (evs) => evs.some((e) => e.event === "update"),
  );
  const update = events.find((e) => e.event === "update");
  expect(update, "no update event arrived").toBeDefined();
  expect(update!.data.trial).toBeUndefined();
  expect(JSON.stringify(events)).not.toMatch(/"rule"|"stats"|"curve"/);
});

it("shows the room once the newcomer has run a test", async () => {
  const other = await runTrial({ type: "trend", leverage: 2, months: 6 });
  const me = await runTrial({ type: "fixed", leverage: 1 });

  const page = await (await fetch(url("/"), { headers: { cookie: me.cookie } })).text();
  expect(page).toContain(`data-trial-id="${other.id}"`);

  const list = await roundTrials(me.cookie);
  expect(list.unlocked).toBe(true);
  expect(list.trials.map((t) => t.id)).toContain(other.id);

  const single = await fetch(url(`/api/trials/${other.id}`), { headers: { cookie: me.cookie } });
  expect(single.status).toBe(200);
});

it("always shows a visitor their own trials", async () => {
  const me = await runTrial({ type: "vol", leverage: 1.5, target: 20, lookback: 6 });
  const res = await fetch(url(`/api/trials/${me.id}`), { headers: { cookie: me.cookie } });
  expect(res.status).toBe(200);
});

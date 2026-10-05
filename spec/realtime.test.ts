import { expect, it } from "vitest";
import { collectEvents, currentRound, runTrial } from "./helpers";

// The brief: a change one person makes appears in every other open session
// within about a second, with no reload. Here the "session" is the event
// stream every open page listens to.

it("tells every open page about a new test within a second", async () => {
  const watcher = await runTrial({ type: "fixed", leverage: 1 }); // unlocked, so it hears details
  const before = (await currentRound()).trial_count;
  let sentAt = 0;
  let newId = 0;

  const events = await collectEvents(
    watcher.cookie,
    5000,
    async () => {
      sentAt = Date.now();
      newId = (await runTrial({ type: "vol", leverage: 2, target: 20, lookback: 12 })).id;
    },
    (evs) => evs.some((e) => e.event === "update" && e.data.trial_count > before),
  );

  expect(events[0].event, "the stream should open with a snapshot").toBe("snapshot");
  expect(events[0].data.trial_count).toBe(before);

  const update = events.find((e) => e.event === "update" && e.data.trial_count > before);
  expect(update, "no update arrived within 5 seconds").toBeDefined();
  expect(update!.at - sentAt).toBeLessThan(1000);
  expect(update!.data.trial_count).toBe(before + 1);
  expect(update!.data.trial?.id).toBe(newId);
});

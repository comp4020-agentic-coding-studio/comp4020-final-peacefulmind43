import { readFileSync } from "node:fs";
import { afterEach, expect, it } from "vitest";
import { createArena, newVisitor, openStream, operatorKey, type Stream } from "./helpers";

// ADR 0023: in a match with a person, a team with no person is played by the
// balanced bot, so speed and strength don't decide the game for the bots.
// Teammates stay the deployed bot. The watch arena, with nobody in it, is
// unchanged. Every bot seat still shows its real name.

const bot = (file: string) => readFileSync(new URL(`../app/game/bots/${file}`, import.meta.url), "utf8").trim();
const balanced = bot("balanced.txt");
const deployed = bot("current.txt");

const open: Stream[] = [];
afterEach(() => {
  for (const s of open.splice(0)) s.close();
});

async function join(cookie: string, path: string) {
  const s = await openStream(cookie, path);
  open.push(s);
  return (await s.waitFor((e) => e.event === "snapshot", 3000)).data;
}

const botsOn = (seats: any[], team: string) => new Set(seats.filter((x) => x.team === team && x.kind === "bot").map((x) => x.bot));

it.runIf(operatorKey)("names the balanced bot on the other team when one person plays, and keeps the deployed bot beside them", async () => {
  expect(balanced).not.toBe(deployed);
  const { id } = await createArena({ team_size: 2, seed: 9301, max_ticks: 30, break_seconds: 30 });
  const snap = await join(await newVisitor(), `/arena/events?arena=${id}`);
  const mine = snap.seats[snap.you].team;
  const other = mine === "blue" ? "red" : "blue";
  expect(botsOn(snap.seats, other)).toEqual(new Set([balanced]));
  expect(botsOn(snap.seats, mine)).toEqual(new Set([deployed]));
});

it.runIf(operatorKey)("gives both teams the same bot when both teams have a person", async () => {
  const { id } = await createArena({ team_size: 2, seed: 9302, max_ticks: 30, break_seconds: 30 });
  await join(await newVisitor(), `/arena/events?arena=${id}`);
  const second = await newVisitor();
  const s = await openStream(second, `/arena/events?arena=${id}`);
  open.push(s);
  const snap = (await s.waitFor((e) => e.event === "snapshot", 3000)).data;
  expect(botsOn(snap.seats, "blue")).toEqual(new Set([deployed]));
  expect(botsOn(snap.seats, "red")).toEqual(new Set([deployed]));
});

it("keeps the deployed bot in the watch arena, where no person plays", async () => {
  const snap = await join(await newVisitor(), "/arena/events?arena=watch");
  expect(snap.seats.every((x: any) => x.kind === "bot")).toBe(true);
  expect(botsOn(snap.seats, "blue")).toEqual(new Set([bot("watch.txt")]));
  expect(snap.seats.some((x: any) => x.bot === balanced)).toBe(false);
});

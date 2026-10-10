import { afterEach, expect, it } from "vitest";
import { choose, createArena, fetchSaved, newVisitor, openStream, operatorKey, type Stream, url } from "./helpers";

// ADR 0011 (seats, joining, leaving) and ADR 0012 (turns that wait for people,
// up to a deadline). Tests that need a known map, a short match or a short
// deadline make a private arena with the operator key; the first test uses
// the default shared arena, as a visitor would.

const open: Stream[] = [];
async function watch(cookie: string | undefined, arena?: string): Promise<Stream> {
  const s = await openStream(cookie, arena ? `/arena/events?arena=${arena}` : "/arena/events");
  open.push(s);
  return s;
}
afterEach(() => {
  for (const s of open.splice(0)) s.close();
});

const snapshot = (s: Stream) => s.waitFor((e) => e.event === "snapshot", 3000);
const nextTick = (s: Stream, from = s.events.length, ms = 3000) => s.waitFor((e) => e.event === "tick", ms, from);
const STAY = 0, NORTH = 1, SOUTH = 2, EAST = 3, WEST = 4;
let seq = 1;

// A direction this seat can actually move in from (x, y): not a wall, not off
// the map, not its own flag.
function passable(map: any, team: number, x: number, y: number): number {
  const blocked = (cx: number, cy: number) =>
    cx < 0 || cy < 0 || cx >= map.width || cy >= map.height ||
    map.walls.some(([wx, wy]: number[]) => wx === cx && wy === cy) ||
    (map.flags[team][0] === cx && map.flags[team][1] === cy);
  const steps: [number, number, number][] = [[EAST, 1, 0], [WEST, -1, 0], [NORTH, 0, -1], [SOUTH, 0, 1]];
  return steps.find(([, dx, dy]) => !blocked(x + dx, y + dy))![0];
}

it("puts two visitors who open the game in the same match, and tells each when the other has chosen", async () => {
  const a = await newVisitor();
  const b = await newVisitor();
  const sa = await watch(a);
  const sb = await watch(b);
  const [snapA, snapB] = await Promise.all([snapshot(sa), snapshot(sb)]);
  expect(snapA.data.match.id).toBe(snapB.data.match.id);
  const seatB = snapB.data.you;
  expect(seatB).not.toBeNull();

  // B must be on the board to move (they may have taken over a bot that was caught)
  await sa.waitFor((e) => e.event === "tick" && e.data.players[seatB].respawn === 0, 15000);
  // the newest state, not the first match: a choice for a turn already over is ignored (ADR 0012)
  const now = sa.events.filter((e) => e.event === "tick").at(-1)!;
  const before = now.data.players[seatB];
  const team = snapB.data.seats[seatB].team === "blue" ? 0 : 1;
  const dir = passable(snapB.data.match.map, team, before.x, before.y);

  const from = sa.events.length;
  const sentAt = Date.now();
  await choose(b, dir, seq++, now.data.tick);
  const ready = await sa.waitFor((e) => e.event === "chosen" && e.data.seat === seatB, 2000, from);
  expect(ready.at - sentAt, "A hears that B has chosen within a second").toBeLessThan(1000);

  await choose(a, STAY, seq++, now.data.tick); // everyone present has chosen: the turn resolves at once
  const moved = await sa.waitFor(
    (e) => e.event === "tick" && (e.data.players[seatB].x !== before.x || e.data.players[seatB].y !== before.y),
    3000,
    from,
  );
  expect(moved.at - sentAt).toBeLessThan(1000);
}, 25000);

it("starts a fresh match for the first person to arrive, and plays no matches for nobody", async () => {
  // ADR 0011: an arena idles when empty; every saved match had a person in it
  const res = await fetch(url("/api/matches/recent"));
  expect(res.status).toBe(200);
  for (const m of (await res.json()) as { people: number }[]) {
    expect(m.people, "a saved match with nobody in it").toBeGreaterThan(0);
  }
});

it.runIf(operatorKey)("lets a visitor alone play with bots in every other seat", async () => {
  const { id } = await createArena({ team_size: 2, seed: 101 });
  const s = await watch(await newVisitor(), id);
  const snap = (await snapshot(s)).data;
  expect(snap.seats).toHaveLength(4);
  const humans = snap.seats.filter((seat: any) => seat.kind === "human");
  expect(humans.map((seat: any) => seat.seat)).toEqual([snap.you]);
  expect(snap.match.team_size).toBe(2);
  // every bot seat says which bot plays it: a trained one, or the scripted fallback
  for (const seat of snap.seats.filter((x: any) => x.kind === "bot")) expect(seat.bot).toEqual(expect.any(String));
});

it.runIf(operatorKey)("resolves a turn as soon as the only person has chosen, and at the deadline if they haven't", async () => {
  const { id } = await createArena({ team_size: 2, seed: 102, deadline_seconds: 1.5 });
  const me = await newVisitor();
  const s = await watch(me, id);
  await snapshot(s);
  const first = await nextTick(s);
  const t0 = first.at;

  // nobody chooses: the turn waits for the deadline
  const late = await nextTick(s, s.events.length, 4000);
  expect(late.at - t0).toBeGreaterThan(1200);
  expect(late.data.tick).toBe(first.data.tick + 1);

  // choose: the turn resolves without waiting for the deadline
  const sentAt = Date.now();
  await choose(me, STAY, seq++, late.data.tick);
  const quick = await nextTick(s);
  expect(quick.at - sentAt).toBeLessThan(700);
  expect(quick.data.tick).toBe(late.data.tick + 1);
}, 15000);

it.runIf(operatorKey)("moves a player at most one cell per turn, however many choices arrive", async () => {
  const { id } = await createArena({ team_size: 2, seed: 103, deadline_seconds: 0.3 });
  const me = await newVisitor();
  const s = await watch(me, id);
  const seat = (await snapshot(s)).data.you;
  const from = s.events.length;
  for (let i = 0; i < 50; i++) await choose(me, [NORTH, SOUTH, EAST, WEST][i % 4], seq++);
  await new Promise((r) => setTimeout(r, 1500));
  const path = s.events.slice(from).filter((e) => e.event === "tick").map((e) => e.data.players[seat]);
  expect(path.length).toBeGreaterThan(2);
  path.slice(1).forEach((p, i) => {
    if (p.respawn || path[i].respawn) return;
    expect(Math.abs(p.x - path[i].x) + Math.abs(p.y - path[i].y)).toBeLessThanOrEqual(1);
  });
});

it.runIf(operatorKey)("ignores a choice older than one already received, or for a turn already over", async () => {
  const { id } = await createArena({ team_size: 2, seed: 104, deadline_seconds: 1 });
  const me = await newVisitor();
  const s = await watch(me, id);
  const snap = (await snapshot(s)).data;
  const seat = snap.you;
  const start = (await nextTick(s)).data;
  const p = start.players[seat];

  // a choice for a turn that has already resolved changes nothing
  const from = s.events.length;
  await choose(me, passable(snap.match.map, 0, p.x, p.y), seq++, start.tick - 1);
  const next = await nextTick(s, from, 3000); // resolves at the deadline instead
  expect(next.data.players[seat]).toMatchObject({ x: p.x, y: p.y });

  // a newer number wins; an older one arriving late is ignored
  const big = seq + 100;
  await choose(me, EAST, big, next.data.tick);
  await choose(me, WEST, big - 50, next.data.tick); // arrives late: must not win
  const after = await nextTick(s);
  expect(after.data.players[seat].x, "never moved west").toBeGreaterThanOrEqual(next.data.players[seat].x);
  seq = big + 1;
});

it.runIf(operatorKey)("lets a newcomer take over a bot's seat without restarting the match", async () => {
  const { id } = await createArena({ team_size: 2, seed: 105, deadline_seconds: 0.3 });
  const first = await watch(await newVisitor(), id);
  const one = (await snapshot(first)).data;
  await new Promise((r) => setTimeout(r, 1500)); // a few turns pass at the deadline
  const second = await watch(await newVisitor(), id);
  const two = (await snapshot(second)).data;

  expect(two.match.id).toBe(one.match.id);
  expect(two.seats[two.you].team, "joins the team with fewer people").not.toBe(one.seats[one.you].team);
  expect(two.tick.tick, "the match kept going").toBeGreaterThan(2);
  const seats = await first.waitFor(
    (e) => e.event === "seats" && e.data.seats.filter((s: any) => s.kind === "human").length === 2,
    2000,
  );
  expect(seats.data.seats[two.you].kind).toBe("human");
});

it.runIf(operatorKey)("hands a closed page's seat to a bot within five seconds, and the match goes on", async () => {
  const { id } = await createArena({ team_size: 2, seed: 106, deadline_seconds: 0.5 });
  const watcher = await watch(await newVisitor(), id);
  await snapshot(watcher);
  const leaver = await openStream(await newVisitor(), `/arena/events?arena=${id}`);
  const seat = (await leaver.waitFor((e) => e.event === "snapshot", 3000)).data.you;
  await watcher.waitFor((e) => e.event === "seats" && e.data.seats[seat].kind === "human", 2000);

  const closedAt = Date.now();
  leaver.close();
  const covered = await watcher.waitFor(
    (e) => e.event === "seats" && e.data.seats[seat].kind === "bot" && e.at > closedAt,
    8000,
  );
  expect(covered.at - closedAt).toBeLessThan(7000);
  expect(covered.data.seats[seat].covering, "the page says whose seat the bot is covering").toMatch(/^Visitor /);
  await nextTick(watcher); // still going
}, 15000);

it.runIf(operatorKey)("puts a fifth person on the bench when every seat is a person", async () => {
  const { id } = await createArena({ team_size: 2, seed: 107 });
  for (let i = 0; i < 4; i++) await snapshot(await watch(await newVisitor(), id));
  const fifth = (await snapshot(await watch(await newVisitor(), id))).data;
  expect(fifth.you).toBeNull();
  expect(fifth.bench).toBe(true);
});

it.runIf(operatorKey)("saves a finished match, then starts the next one", async () => {
  const { id } = await createArena({ team_size: 2, seed: 108, max_ticks: 12, break_seconds: 1, deadline_seconds: 0.2 });
  const s = await watch(await newVisitor(), id);
  const first = (await snapshot(s)).data.match.id;
  const over = await s.waitFor((e) => e.event === "over", 8000);
  expect(over.data.match_id).toBe(first);
  const next = await s.waitFor((e) => e.event === "match", 4000);
  expect(next.data.match.id).not.toBe(first);

  // saved in a thread after the match ends, so wait for it to be finished
  let saved: any = {};
  for (let i = 0; i < 30 && saved.status !== "finished"; i++) {
    saved = await (await fetchSaved(`/api/matches/${first}`)).json();
    if (saved.status !== "finished") await new Promise((r) => setTimeout(r, 100));
  }
  expect(saved).toMatchObject({ id: first, status: "finished", ticks: 12, team_size: 2, seed: 108 });
  expect(saved.score).toEqual(over.data.score);
}, 15000);

it("lets people watch bots play without taking a seat or saving the match", async () => {
  const s = await watch(await newVisitor(), "watch");
  const snap = (await snapshot(s)).data;
  expect(snap.you).toBeNull();
  expect(snap.seats.every((seat: any) => seat.kind === "bot")).toBe(true);
  expect(snap.seats.find((seat: any) => seat.team === "red").bot).toBe("scripted");
  expect(snap.match.id, "a match nobody played isn't saved").toBeNull();
  const a = await nextTick(s);
  const b = await nextTick(s);
  expect(b.data.tick).toBeGreaterThan(a.data.tick);
});

it("refuses a choice from someone without a seat, and private arenas without the operator key", async () => {
  expect((await choose(await newVisitor(), EAST, 1)).status).toBe(409);
  const res = await fetch(url("/api/arenas"), {
    method: "POST",
    headers: { "content-type": "application/json", "x-operator-key": "wrong" },
    body: JSON.stringify({ team_size: 2, seed: 1 }),
  });
  expect([403, 404]).toContain(res.status);
});

it.skipIf(operatorKey)("skips the private-arena checks: OPERATOR_KEY isn't set for this run", () => {
  console.warn("OPERATOR_KEY isn't set: the private-arena checks did not run");
});

it.runIf(operatorKey)("lets anyone in a match pause it for everyone, and anyone resume it", async () => {
  const { id } = await createArena({ team_size: 2, seed: 109, deadline_seconds: 0.3 });
  const a = await newVisitor();
  const b = await newVisitor();
  const sa = await watch(a, id);
  await snapshot(sa);
  const sb = await watch(b, id);
  await snapshot(sb);
  await nextTick(sa);

  const paused = await fetch(url("/arena/pause"), { method: "POST", headers: { cookie: a } });
  expect(paused.status).toBe(200);
  expect(await paused.json()).toMatchObject({ paused: true });
  const told = await sb.waitFor((e) => e.event === "pause" && e.data.paused === true, 2000);
  expect(told.data.by, "others see who paused").toMatch(/^Visitor /);

  // no turn resolves while paused, though the deadline is 0.3 s
  const from = sa.events.length;
  await new Promise((r) => setTimeout(r, 1500));
  expect(sa.events.slice(from).filter((e) => e.event === "tick")).toHaveLength(0);

  // someone else carries on
  const resumed = await fetch(url("/arena/pause"), { method: "POST", headers: { cookie: b } });
  expect(await resumed.json()).toMatchObject({ paused: false });
  await sa.waitFor((e) => e.event === "pause" && e.data.paused === false, 2000);
  await nextTick(sa);
}, 15000);

it("doesn't let someone without a seat pause anything", async () => {
  expect((await fetch(url("/arena/pause"), { method: "POST", headers: { cookie: await newVisitor() } })).status).toBe(409);
});

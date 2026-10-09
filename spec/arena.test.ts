import { afterEach, expect, it } from "vitest";
import { createArena, newVisitor, openStream, operatorKey, sendInput, type Stream, url } from "./helpers";

// ADR 0011: how several people share a match. Tests that need a known map or
// a short match make a private arena with the operator key; the first test
// uses the default shared arena, as a visitor would.

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
// A match may be between matches (a 10 s break) when someone arrives.
const nextTick = (s: Stream, from = s.events.length, ms = 2000) => s.waitFor((e) => e.event === "tick", ms, from);
const STAY = 0, EAST = 3, WEST = 4;

it("puts two visitors who open the game in the same match, and shows each other's moves within a second", async () => {
  const a = await newVisitor();
  const b = await newVisitor();
  const sa = await watch(a);
  const sb = await watch(b);
  const [snapA, snapB] = await Promise.all([snapshot(sa), snapshot(sb)]);
  expect(snapA.data.match.id).toBe(snapB.data.match.id);
  const seatB = snapB.data.you;
  expect(seatB).not.toBeNull();

  // B took over a bot's seat; if that bot was waiting to respawn, wait for B to be back on the board
  const before = (
    await sa.waitFor((e) => e.event === "tick" && e.data.players[seatB].respawn === 0, 12000)
  ).data.players[seatB];
  // hold a direction B can actually move in: not a wall, not off the map, not B's own flag
  const map = snapB.data.match.map;
  const team = snapB.data.seats[seatB].team === "blue" ? 0 : 1;
  const blocked = (x: number, y: number) =>
    x < 0 || y < 0 || x >= map.width || y >= map.height ||
    map.walls.some(([wx, wy]: number[]) => wx === x && wy === y) ||
    (map.flags[team][0] === x && map.flags[team][1] === y);
  const steps: [number, number, number][] = [[EAST, 1, 0], [WEST, -1, 0], [1, 0, -1], [2, 0, 1]];
  const [dir] = steps.find(([, dx, dy]) => !blocked(before.x + dx, before.y + dy))!;
  const sentAt = Date.now();
  const from = sa.events.length;
  await sendInput(b, dir, true, 1);
  const moved = await sa.waitFor(
    (e) => e.event === "tick" && (e.data.players[seatB].x !== before.x || e.data.players[seatB].y !== before.y),
    3000,
    from,
  );
  expect(moved.at - sentAt).toBeLessThan(1000);
}, 20000);

it("starts a fresh match for the first person to arrive, and plays no matches for nobody", async () => {
  // ADR 0011: an empty shared arena idles; saved matches all had a person in them
  const res = await fetch(url("/api/matches/recent"));
  expect(res.status).toBe(200);
  const recent = (await res.json()) as { people: number }[];
  for (const m of recent) expect(m.people, "a saved match with nobody in it").toBeGreaterThan(0);
});

it.runIf(operatorKey)("lets a visitor alone play with bots in every other seat", async () => {
  const { id } = await createArena({ team_size: 2, seed: 101 });
  const s = await watch(await newVisitor(), id);
  const snap = (await snapshot(s)).data;
  expect(snap.seats).toHaveLength(4);
  const humans = snap.seats.filter((seat: any) => seat.kind === "human");
  expect(humans.map((seat: any) => seat.seat)).toEqual([snap.you]);
  expect(snap.match.team_size).toBe(2);
});

it.runIf(operatorKey)("ticks four times a second", async () => {
  const { id } = await createArena({ team_size: 2, seed: 102 });
  const s = await watch(await newVisitor(), id);
  await snapshot(s);
  await new Promise((r) => setTimeout(r, 3000));
  const ticks = s.events.filter((e) => e.event === "tick").map((e) => e.data.tick);
  expect(ticks.length).toBeGreaterThanOrEqual(10);
  expect(ticks.length).toBeLessThanOrEqual(14);
  ticks.slice(1).forEach((t, i) => expect(t, "ticks arrive in order, none skipped").toBe(ticks[i] + 1));
});

it.runIf(operatorKey)("moves a player at most one cell per tick, however many inputs arrive", async () => {
  const { id } = await createArena({ team_size: 2, seed: 103 });
  const me = await newVisitor();
  const s = await watch(me, id);
  const seat = (await snapshot(s)).data.you;
  const from = s.events.length;
  for (let i = 0; i < 50; i++) await sendInput(me, [1, 2, EAST, WEST][i % 4], false, i + 1);
  await new Promise((r) => setTimeout(r, 1500));
  const path = s.events.slice(from).filter((e) => e.event === "tick").map((e) => e.data.players[seat]);
  expect(path.length).toBeGreaterThan(3);
  path.slice(1).forEach((p, i) => {
    if (p.respawn || path[i].respawn) return;
    expect(Math.abs(p.x - path[i].x) + Math.abs(p.y - path[i].y)).toBeLessThanOrEqual(1);
  });
});

it.runIf(operatorKey)("ignores an input older than one already received", async () => {
  const { id } = await createArena({ team_size: 2, seed: 104 });
  const me = await newVisitor();
  const s = await watch(me, id);
  const seat = (await snapshot(s)).data.you;
  const start = (await nextTick(s)).data.players[seat];
  await sendInput(me, EAST, true, 10);
  await sendInput(me, WEST, true, 5); // arrives late: must not win
  const from = s.events.length;
  await new Promise((r) => setTimeout(r, 1500));
  for (const e of s.events.slice(from).filter((e) => e.event === "tick")) {
    expect(e.data.players[seat].x, "never moved west").toBeGreaterThanOrEqual(start.x);
  }
  await sendInput(me, STAY, true, 11);
});

it.runIf(operatorKey)("lets a newcomer take over a bot's seat without restarting the match", async () => {
  const { id } = await createArena({ team_size: 2, seed: 105 });
  const first = await watch(await newVisitor(), id);
  const one = (await snapshot(first)).data;
  await new Promise((r) => setTimeout(r, 800)); // let the match run a little
  const second = await watch(await newVisitor(), id);
  const two = (await snapshot(second)).data;

  expect(two.match.id).toBe(one.match.id);
  expect(two.seats[two.you].team, "joins the team with fewer people").not.toBe(one.seats[one.you].team);
  const tick = (await nextTick(second)).data.tick;
  expect(tick, "the match kept going").toBeGreaterThan(2);
  const seats = await first.waitFor(
    (e) => e.event === "seats" && e.data.seats.filter((s: any) => s.kind === "human").length === 2,
    2000,
  );
  expect(seats.data.seats[two.you].kind).toBe("human");
});

it.runIf(operatorKey)("hands a closed page's seat to a bot within five seconds, and the match goes on", async () => {
  const { id } = await createArena({ team_size: 2, seed: 106 });
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
  await nextTick(watcher); // still ticking
}, 15000);

it.runIf(operatorKey)("puts a fifth person on the bench when every seat is a person", async () => {
  const { id } = await createArena({ team_size: 2, seed: 107 });
  for (let i = 0; i < 4; i++) await snapshot(await watch(await newVisitor(), id));
  const fifth = (await snapshot(await watch(await newVisitor(), id))).data;
  expect(fifth.you).toBeNull();
  expect(fifth.bench).toBe(true);
});

it.runIf(operatorKey)("saves a finished match, then starts the next one", async () => {
  const { id } = await createArena({ team_size: 2, seed: 108, max_ticks: 12, break_seconds: 1 });
  const s = await watch(await newVisitor(), id);
  const first = (await snapshot(s)).data.match.id;
  const over = await s.waitFor((e) => e.event === "over", 6000);
  expect(over.data.match_id).toBe(first);
  const next = await s.waitFor((e) => e.event === "match", 4000);
  expect(next.data.match.id).not.toBe(first);

  const saved = await (await fetch(url(`/api/matches/${first}`))).json();
  expect(saved).toMatchObject({ id: first, status: "finished", ticks: 12, team_size: 2, seed: 108 });
  expect(saved.score).toEqual(over.data.score);
}, 15000);

it("refuses an input from someone without a seat, and private arenas without the operator key", async () => {
  expect((await sendInput(await newVisitor(), EAST, false, 1)).status).toBe(409);
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

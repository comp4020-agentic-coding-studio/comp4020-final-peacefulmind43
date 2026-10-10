import { afterEach, expect, it } from "vitest";
import { done, newGame, stateHash, step } from "./engine";
import { choose, createArena, fetchSaved, newVisitor, openStream, operatorKey, type Stream, url } from "./helpers";

// ADR 0014: every choice is logged, and every finished match can be replayed.
// The replay is checked by the independent TypeScript engine, not by the app.

const open: Stream[] = [];
afterEach(() => {
  for (const s of open.splice(0)) s.close();
});

async function playShortMatch() {
  const { id } = await createArena({ team_size: 2, seed: 4242, max_ticks: 30, break_seconds: 5, deadline_seconds: 0.2 });
  const me = await newVisitor();
  const s = await openStream(me, `/arena/events?arena=${id}`);
  open.push(s);
  const snap = (await s.waitFor((e) => e.event === "snapshot", 3000)).data;
  let seq = 1;
  // choose a few moves, so the replay holds a person's choices as well as bots'
  for (let i = 0; i < 6; i++) {
    const t = await s.waitFor((e) => e.event === "tick", 3000, s.events.length);
    await choose(me, [1, 2, 3, 4][i % 4], seq++, t.data.tick);
  }
  const over = await s.waitFor((e) => e.event === "over", 15000);
  return { matchId: snap.match.id as number, seat: snap.you as number, over };
}

it.runIf(operatorKey)("replays a finished match to the same score and state with the independent engine", async () => {
  const { matchId, over } = await playShortMatch();
  const res = await fetchSaved(`/api/matches/${matchId}/replay`);
  expect(res.status).toBe(200);
  const replay = await res.json();
  expect(replay).toMatchObject({ seed: 4242, team_size: 2, max_ticks: 30 });
  expect(replay.actions).toHaveLength(over.data.score[0] === 3 || over.data.score[1] === 3 ? replay.actions.length : 30);

  const s = newGame(replay.seed, replay.team_size);
  s.maxTicks = replay.max_ticks;
  for (const turn of replay.actions) step(s, turn);
  expect(done(s)).toBe(true);
  expect(s.score).toEqual(over.data.score);
  expect(stateHash(s)).toBe(replay.hash);
}, 30000);

it.runIf(operatorKey)("logs every choice with who, what and when", async () => {
  const before = Math.floor(Date.now() / 1000) - 1;
  const { matchId, seat } = await playShortMatch();
  await new Promise((r) => setTimeout(r, 3000)); // choices are written in batches
  const res = await fetch(url(`/api/matches/${matchId}/choices`));
  expect(res.status).toBe(200);
  const choices = (await res.json()) as { visitor: string; seat: number; turn: number; dir: number; at: number }[];
  const mine = choices.filter((c) => c.seat === seat);
  expect(mine.length).toBeGreaterThanOrEqual(6);
  for (const c of mine) {
    expect(c.visitor).toMatch(/^Visitor [0-9a-f]{6}$/);
    expect(c.at).toBeGreaterThanOrEqual(before);
    expect([0, 1, 2, 3, 4]).toContain(c.dir);
  }
  expect(JSON.stringify(choices), "never the cookie").not.toMatch(/visitor=/);
}, 30000);

it.runIf(operatorKey)("keeps a live match's choices to itself until the match is over", async () => {
  // ADR 0012: others learn that you have chosen, not what. The choices are
  // public only once the match has finished (ADR 0016).
  const { id } = await createArena({ team_size: 2, seed: 4243, deadline_seconds: 5 });
  const me = await newVisitor();
  const s = await openStream(me, `/arena/events?arena=${id}`);
  open.push(s);
  const matchId = (await s.waitFor((e) => e.event === "snapshot", 3000)).data.match.id;
  await choose(me, 3, 1);
  expect((await fetch(url(`/api/matches/${matchId}/choices`))).status).toBe(404);
});

it("refuses a replay of a match that doesn't exist", async () => {
  expect((await fetch(url("/api/matches/999999999/replay"))).status).toBe(404);
});

it.runIf(operatorKey)("shows, live, who is in each arena and how active they are", async () => {
  const { id } = await createArena({ team_size: 2, seed: 777, deadline_seconds: 0.5 });
  const me = await newVisitor();
  const s = await openStream(me, `/arena/events?arena=${id}`);
  open.push(s);
  const seat = (await s.waitFor((e) => e.event === "snapshot", 3000)).data.you;
  const t = await s.waitFor((e) => e.event === "tick", 3000);
  await choose(me, 3, 1, t.data.tick);
  const now = (await (await fetch(url("/api/now"))).json()) as any[];
  const arena = now.find((a) => a.arena === id);
  expect(arena, "the arena is in the live view").toBeDefined();
  expect(arena.seats[seat]).toMatchObject({ kind: "human", label: expect.stringMatching(/^Visitor /) });
  expect(arena.seats[seat].choices_last_minute).toBeGreaterThanOrEqual(1);
  expect(JSON.stringify(now)).not.toMatch(/visitor=/);
});

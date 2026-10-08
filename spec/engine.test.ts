import { expect, it } from "vitest";
import { type State, Rng, done, fingerprint, makeMap, newGame, stateHash, step } from "./engine";
import { url } from "./helpers";

// ADR 0010: the app's engine and spec/engine.ts, written separately from the
// same record, must agree on every map and every tick.

async function simulate(seed: number, teamSize: number, actions: number[][]) {
  const res = await fetch(url("/api/engine/simulate"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ seed, team_size: teamSize, actions }),
  });
  expect(res.status).toBe(200);
  return (await res.json()) as {
    map: { width: number; height: number; walls: [number, number][] };
    fingerprints: string[];
    events: [number, string, number][];
    hash: number;
  };
}

// A rough player so games include pickups, captures and tags, not just
// wandering: head for the enemy flag, then for home, with some noise.
function greedy(s: State, seat: number, rng: Rng): number {
  const p = s.players[seat];
  if (p.respawn || rng.next() < 0.25) return rng.below(5);
  const [tx, ty] = p.carrying ? s.map.flags[p.team] : s.map.flags[1 - p.team];
  const options: number[] = [];
  if (tx > p.x) options.push(3);
  if (tx < p.x) options.push(4);
  if (ty > p.y) options.push(2);
  if (ty < p.y) options.push(1);
  return options.length ? options[rng.below(options.length)] : 0;
}

function playLocally(seed: number, teamSize: number, policySeed: number) {
  const s = newGame(seed, teamSize);
  const rng = new Rng(policySeed);
  const actions: number[][] = [];
  const fingerprints: string[] = [];
  const events: [number, string, number][] = [];
  while (!done(s)) {
    const tick = s.players.map((_, i) => greedy(s, i, rng));
    actions.push(tick);
    for (const [name, seat] of step(s, tick)) events.push([s.tick, name, seat]);
    fingerprints.push(fingerprint(s));
  }
  return { actions, fingerprints, events, hash: stateHash(s) };
}

it("generates the same maps from the same seeds", async () => {
  for (const teamSize of [2, 3]) {
    for (const seed of [0, 1, 42, 123456, 4294967295]) {
      const mine = makeMap(seed, teamSize);
      const app = (await simulate(seed, teamSize, [])).map;
      expect([app.width, app.height]).toEqual([mine.width, mine.height]);
      const walls = [...mine.walls].map((k) => k.split(",").map(Number)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      expect(app.walls, `seed ${seed}, ${teamSize}v${teamSize}`).toEqual(walls);
    }
  }
});

it("plays every tick the same way as the independent engine", async () => {
  const seen = new Set<string>();
  for (const teamSize of [2, 3]) {
    for (const seed of [7, 99, 2026]) {
      const local = playLocally(seed, teamSize, seed + 1);
      const app = await simulate(seed, teamSize, local.actions);
      for (let t = 0; t < local.fingerprints.length; t++) {
        expect(app.fingerprints[t], `seed ${seed}, ${teamSize}v${teamSize}, tick ${t + 1}`).toBe(local.fingerprints[t]);
      }
      expect(app.events).toEqual(local.events);
      expect(app.hash).toBe(local.hash);
      for (const [, name] of local.events) seen.add(name);
    }
  }
  // the games exercised the rules that matter, not just walking
  for (const name of ["tag", "respawn", "pickup", "capture"]) expect(seen, `no ${name} in any game`).toContain(name);
});

it("refuses inputs it can't run", async () => {
  for (const body of [{}, { seed: 1, team_size: 4, actions: [] }, { seed: 1, team_size: 2, actions: [[0, 0, 0]] }]) {
    const res = await fetch(url("/api/engine/simulate"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    expect(res.status).toBe(400);
  }
});

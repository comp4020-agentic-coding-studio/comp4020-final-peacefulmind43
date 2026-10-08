// A second implementation of the rules in doc/adr/0010, written from the record
// in TypeScript, so the spec can check the app's Python engine tick by tick
// instead of trusting it to check itself.

export const SIZES: Record<number, [number, number]> = { 2: [16, 10], 3: [20, 12] };
export const WALL_FRACTION = 0.18;
export const RESPAWN_TICKS = 8;
export const MAX_TICKS = 720;
export const WIN_SCORE = 3;

const MOVES: [number, number][] = [
  [0, 0], // stay
  [0, -1], // north
  [0, 1], // south
  [1, 0], // east
  [-1, 0], // west
];
const BASE_OFFSETS: [number, number][] = [
  [0, -1], [0, 1], [1, 0], [1, -1], [1, 1], [-1, 0], [-1, -1], [-1, 1], [0, 0],
];

// mulberry32, matching app/game/engine.py's Rng bit for bit
export class Rng {
  private a: number;
  constructor(seed: number) {
    this.a = seed >>> 0;
  }
  next(): number {
    this.a = (this.a + 0x6d2b79f5) >>> 0;
    let t = this.a;
    t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
    t = (t ^ ((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  below(n: number): number {
    return Math.floor(this.next() * n);
  }
}

type Cell = [number, number];
const key = ([x, y]: Cell) => `${x},${y}`;

export interface GameMap {
  width: number;
  height: number;
  walls: Set<string>;
  flags: [Cell, Cell];
  bases: [Cell[], Cell[]];
}

const half = (m: GameMap, x: number) => (x < Math.floor(m.width / 2) ? 0 : 1);
const open = (m: GameMap, x: number, y: number) =>
  x >= 0 && x < m.width && y >= 0 && y < m.height && !m.walls.has(`${x},${y}`);

export function makeMap(seed: number, teamSize: number): GameMap {
  const [width, height] = SIZES[teamSize];
  const flags: [Cell, Cell] = [
    [1, Math.floor(height / 2)],
    [width - 2, Math.floor(height / 2)],
  ];
  const bases: [Cell[], Cell[]] = [
    BASE_OFFSETS.map(([dx, dy]) => [flags[0][0] + dx, flags[0][1] + dy] as Cell),
    BASE_OFFSETS.map(([dx, dy]) => [flags[1][0] - dx, flags[1][1] + dy] as Cell),
  ];
  const inBase = new Set(bases[0].map(key));
  const halfCells: Cell[] = [];
  for (let y = 0; y < height; y++) for (let x = 0; x < Math.floor(width / 2); x++) halfCells.push([x, y]);
  const candidates = halfCells.filter((c) => !inBase.has(key(c)));
  const nWalls = Math.round(WALL_FRACTION * halfCells.length);

  const rng = new Rng(seed);
  for (let attempt = 0; attempt < 100; attempt++) {
    const pool = candidates.slice();
    const chosen: Cell[] = [];
    for (let i = 0; i < nWalls; i++) {
      const j = i + rng.below(pool.length - i);
      [pool[i], pool[j]] = [pool[j], pool[i]];
      chosen.push(pool[i]);
    }
    const walls = new Set<string>();
    for (const [x, y] of chosen) {
      walls.add(`${x},${y}`);
      walls.add(`${width - 1 - x},${y}`);
    }
    const m: GameMap = { width, height, walls, flags, bases };
    if (connected(m)) return m;
  }
  return { width, height, walls: new Set(), flags, bases };
}

function connected(m: GameMap): boolean {
  const start = m.flags[0];
  const seen = new Set([key(start)]);
  const frontier: Cell[] = [start];
  while (frontier.length) {
    const [x, y] = frontier.pop()!;
    for (const [dx, dy] of [[0, -1], [0, 1], [1, 0], [-1, 0]]) {
      const nx = x + dx, ny = y + dy;
      if (!seen.has(`${nx},${ny}`) && open(m, nx, ny)) {
        seen.add(`${nx},${ny}`);
        frontier.push([nx, ny]);
      }
    }
  }
  return seen.size === m.width * m.height - m.walls.size;
}

export interface Player {
  team: number;
  x: number;
  y: number;
  respawn: number;
  carrying: boolean;
}

export interface State {
  map: GameMap;
  players: Player[];
  score: [number, number];
  carrier: [number | null, number | null];
  tick: number;
}

export const done = (s: State) => Math.max(...s.score) >= WIN_SCORE || s.tick >= MAX_TICKS;

export function newGame(seed: number, teamSize: number): State {
  const map = makeMap(seed, teamSize);
  const players: Player[] = [];
  for (let seat = 0; seat < 2 * teamSize; seat++) {
    const team = seat < teamSize ? 0 : 1;
    const [x, y] = map.bases[team][seat % teamSize];
    players.push({ team, x, y, respawn: 0, carrying: false });
  }
  return { map, players, score: [0, 0], carrier: [null, null], tick: 0 };
}

export function step(s: State, actions: number[]): [string, number][] {
  if (done(s)) return [];
  const m = s.map;
  const P = s.players;
  const events: [string, number][] = [];

  // 1. intended cells
  const target = new Map<number, Cell>();
  P.forEach((p, i) => {
    if (p.respawn !== 0) return;
    let a = actions[i] >= 0 && actions[i] <= 4 ? actions[i] : 0;
    if (p.carrying && s.tick % 3 === 2) a = 0;
    const [dx, dy] = MOVES[a];
    const nx = p.x + dx, ny = p.y + dy;
    target.set(i, open(m, nx, ny) ? [nx, ny] : [p.x, p.y]);
  });

  // 2. contact
  const tagged = new Set<number>();
  const active = [...target.keys()].sort((a, b) => a - b);
  for (let ai = 0; ai < active.length; ai++) {
    for (const j of active.slice(ai + 1)) {
      const i = active[ai];
      if (P[i].team === P[j].team) continue;
      const ti = target.get(i)!, tj = target.get(j)!;
      const same = ti[0] === tj[0] && ti[1] === tj[1];
      const swap = ti[0] === P[j].x && ti[1] === P[j].y && tj[0] === P[i].x && tj[1] === P[i].y;
      if (same || swap) {
        for (const k of [i, j]) if (half(m, target.get(k)![0]) !== P[k].team) tagged.add(k);
      }
    }
  }

  // 3. tagged leave the board
  for (const i of [...tagged].sort((a, b) => a - b)) {
    const p = P[i];
    if (p.carrying) {
      s.carrier[1 - p.team] = null;
      p.carrying = false;
    }
    p.x = -1;
    p.y = -1;
    p.respawn = RESPAWN_TICKS;
    events.push(["tag", i]);
  }

  // 4. everyone else moves
  for (const [i, [x, y]] of target) {
    if (!tagged.has(i)) {
      P[i].x = x;
      P[i].y = y;
    }
  }

  // respawns
  P.forEach((p, i) => {
    if (p.respawn && !tagged.has(i)) {
      p.respawn -= 1;
      if (p.respawn === 0) {
        const taken = new Set(P.filter((q) => q.respawn === 0 && q !== p).map((q) => `${q.x},${q.y}`));
        const free = m.bases[p.team].filter((c) => !taken.has(key(c)));
        if (free.length) {
          [p.x, p.y] = free[0];
          events.push(["respawn", i]);
        } else {
          p.respawn = 1;
        }
      }
    }
  });

  // 5. pickup
  for (const team of [0, 1]) {
    const enemy = 1 - team;
    if (s.carrier[enemy] !== null) continue;
    const [fx, fy] = m.flags[enemy];
    const onFlag = P.map((p, i) => [p, i] as const)
      .filter(([p]) => p.team === team && p.respawn === 0 && p.x === fx && p.y === fy)
      .map(([, i]) => i);
    if (onFlag.length) {
      const i = Math.min(...onFlag);
      P[i].carrying = true;
      s.carrier[enemy] = i;
      events.push(["pickup", i]);
    }
  }

  // 6. capture
  P.forEach((p, i) => {
    if (p.carrying && p.respawn === 0 && m.bases[p.team].some(([x, y]) => x === p.x && y === p.y)) {
      s.score[p.team] += 1;
      p.carrying = false;
      s.carrier[1 - p.team] = null;
      events.push(["capture", i]);
    }
  });

  s.tick += 1;
  return events;
}

export function fingerprint(s: State): string {
  let out = `${s.tick}|${s.score[0]},${s.score[1]}|`;
  for (const p of s.players) out += `${p.team},${p.x},${p.y},${p.respawn},${p.carrying ? 1 : 0};`;
  return out;
}

export function stateHash(s: State): number {
  let h = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(fingerprint(s))) h = Math.imul(h ^ byte, 0x01000193) >>> 0;
  return h;
}

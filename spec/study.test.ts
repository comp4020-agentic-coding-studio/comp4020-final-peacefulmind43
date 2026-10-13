import { afterEach, expect, it } from "vitest";
import { choose, createArena, newVisitor, openStream, operatorKey, type Stream, url } from "./helpers";

// ADR 0017: the blind teammate study. In a study match, the bot on a person's
// team is drawn at random and shown only as "Bot A" or "Bot B". After the
// match, each person who played beside it answers one question, once, and
// only then learns which bot it was.

const open: Stream[] = [];
afterEach(() => {
  for (const s of open.splice(0)) s.close();
});

async function studyArena(seed: number, extra: Record<string, unknown> = {}) {
  const res = await fetch(url("/api/arenas"), {
    method: "POST",
    headers: { "content-type": "application/json", "x-operator-key": operatorKey ?? "" },
    body: JSON.stringify({ team_size: 2, seed, max_ticks: 20, break_seconds: 30, deadline_seconds: 0.2, study: true, ...extra }),
  });
  expect(res.status).toBe(200);
  return (await res.json()).id as string;
}

async function join(cookie: string, id: string) {
  const s = await openStream(cookie, `/arena/events?arena=${id}`);
  open.push(s);
  return { s, snap: (await s.waitFor((e) => e.event === "snapshot", 3000)).data };
}

const rate = (id: number, cookie: string | undefined, body: unknown) =>
  fetch(url(`/api/matches/${id}/rating`), {
    method: "POST",
    headers: { "content-type": "application/json", ...(cookie ? { cookie } : {}) },
    body: JSON.stringify(body),
  });

// the finished match is saved in a thread: retry until the server knows you played
async function rateWhenSaved(id: number, cookie: string, body: unknown) {
  for (let i = 0; ; i++) {
    const res = await rate(id, cookie, body);
    if (res.status !== 403 || i > 30) return res;
    await new Promise((r) => setTimeout(r, 100));
  }
}

it.runIf(operatorKey)("shows your bot teammate only as Bot A or Bot B, never by its type, while the match runs", async () => {
  const id = await studyArena(9101);
  const { s, snap } = await join(await newVisitor(), id);
  const team = snap.seats[snap.you].team;
  const mates = snap.seats.filter((x: any) => x.team === team && x.kind === "bot");
  const others = snap.seats.filter((x: any) => x.team !== team);
  expect(mates.length).toBeGreaterThan(0);
  for (const m of mates) expect(m).toMatchObject({ blind: true, bot: expect.stringMatching(/^Bot [AB]$/) });
  // the team with no person in it still names its bot (CLAUDE.md: every bot seat shows a name)
  for (const o of others) expect(o).toMatchObject({ blind: false, bot: expect.any(String) });
  await new Promise((r) => setTimeout(r, 1000)); // a few turns, and any seat changes, pass
  for (const e of s.events.filter((x) => x.event === "seats" || x.event === "snapshot")) {
    for (const seat of e.data.seats.filter((x: any) => x.team === team && x.kind === "bot")) {
      expect(seat.bot, "the bot's type leaked during the match").toMatch(/^Bot [AB]$/);
    }
  }
  const live = (await (await fetch(url("/api/now"))).json()).find((a: any) => a.arena === id);
  for (const seat of live.seats.filter((x: any) => x.team === team && x.kind === "bot")) expect(seat.bot).toMatch(/^Bot [AB]$/);
});

it.runIf(operatorKey)("lets each person who played beside the bot rate it once, then says which bot it was", async () => {
  const id = await studyArena(9102);
  const me = await newVisitor();
  const { s, snap } = await join(me, id);
  const team = snap.seats[snap.you].team;
  const letter = snap.seats.find((x: any) => x.team === team && x.kind === "bot").bot.slice(-1);
  await choose(me, 0, 1);
  const over = (await s.waitFor((e) => e.event === "over", 15000)).data;
  expect(over.rate, "the page is told your team may rate").toContain(team);
  const matchId = snap.match.id;

  expect((await rateWhenSaved(matchId, me, { score: 6 })).status, "1 to 5 only").toBe(400);
  expect((await rate(matchId, me, { score: true })).status).toBe(400);
  expect((await rate(matchId, await newVisitor(), { score: 4 })).status, "someone who didn't play").toBe(403);
  expect((await rate(matchId, undefined, { score: 4 })).status, "no cookie").toBe(403);

  const before = (await (await fetch(url("/api/study"))).json()).bots as any[];
  const res = await rate(matchId, me, { score: 4 });
  expect(res.status).toBe(200);
  const answer = await res.json();
  expect(answer).toMatchObject({ score: 4, letter, bot: expect.stringMatching(/^(scripted|cur\d+)$/) });
  expect((await rate(matchId, me, { score: 2 })).status, "answering twice").toBe(409);
  expect((await rate(matchId, me, { score: null })).status, "skipping after answering").toBe(409);

  const after = (await (await fetch(url("/api/study"))).json()).bots as any[];
  const b = before.find((x) => x.bot === answer.bot);
  const a = after.find((x) => x.bot === answer.bot);
  expect(a.ratings).toBe(b.ratings + 1);
  expect(a.counts["4"]).toBe(b.counts["4"] + 1);
  expect(a.matches).toBeGreaterThan(b.matches - 1);
}, 30000);

it.runIf(operatorKey)("counts a skip as an answer, and never asks a team that had no bot teammate", async () => {
  const id = await studyArena(9103);
  const a = await newVisitor();
  const b = await newVisitor();
  const c = await newVisitor();
  const one = await join(a, id);
  const two = await join(b, id);
  const three = await join(c, id);
  // three people in 2v2: one team is all people, so it has no bot teammate to rate
  const seats = (await one.s.waitFor((e) => e.event === "seats" && e.data.seats.filter((x: any) => x.kind === "human").length === 3, 3000)).data.seats;
  const full = ["blue", "red"].find((t) => seats.filter((x: any) => x.team === t).every((x: any) => x.kind === "human"));
  const over = (await one.s.waitFor((e) => e.event === "over", 15000)).data;
  expect(over.rate).not.toContain(full);
  const matchId = one.snap.match.id;
  const people = [[a, one.snap], [b, two.snap], [c, three.snap]] as const;
  for (const [cookie, snap] of people) {
    const res = await rateWhenSaved(matchId, cookie, { score: null });
    if (snap.seats[snap.you].team === full) expect(res.status, "a team of people only had no bot to rate").toBe(403);
    else {
      expect(res.status).toBe(200);
      expect((await res.json()).score).toBeNull();
    }
  }
}, 30000);

it("refuses a rating for a match that doesn't exist, and a broken score", async () => {
  const cookie = await newVisitor();
  expect((await rate(999999999, cookie, { score: 3 })).status).toBe(403);
  expect((await rate(999999999, cookie, { score: "five" })).status).toBe(400);
});

it("publishes the study's results with n for each teammate bot, and labels only", async () => {
  const data = await (await fetch(url("/api/study"))).json();
  expect(data.bots.map((b: any) => b.bot)).toEqual(expect.arrayContaining(["scripted", "cur4"]));
  for (const b of data.bots) {
    expect(b).toMatchObject({ ratings: expect.any(Number), matches: expect.any(Number), captures: { people: expect.any(Number), bots: expect.any(Number) } });
  }
  const page = await fetch(url("/study"));
  expect(page.status).toBe(200);
  const html = await page.text();
  expect(html).toContain("Bot A");
  expect(html).toMatch(/n = \d+|\(\d/);
  expect(html).not.toMatch(/visitor=/);
});

it("tells people before they play that their bot teammate may be blinded", async () => {
  const html = await (await fetch(url("/"))).text();
  expect(html).toMatch(/Bot A.*Bot B/s);
  expect(html).toContain('href="/study"');
});

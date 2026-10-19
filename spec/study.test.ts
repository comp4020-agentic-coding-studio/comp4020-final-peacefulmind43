import { afterEach, expect, it } from "vitest";
import { choose, newVisitor, openStream, operatorKey, type Stream, url } from "./helpers";

// ADR 0017, changed by ADR 0019: in a study match, the bot on a person's team
// is drawn at random and recorded, so behaviour on teams with each bot can be
// compared. Nobody is blinded and nobody is asked to rate it: every bot seat
// shows its real name, and the rating endpoint is gone.

const open: Stream[] = [];
afterEach(() => {
  for (const s of open.splice(0)) s.close();
});

const realName = /^(scripted|[a-z]+\d+[a-z]*)$/; // "scripted" or an exported bot such as cur4, fcp1 or cur4snap

async function studyArena(seed: number) {
  const res = await fetch(url("/api/arenas"), {
    method: "POST",
    headers: { "content-type": "application/json", "x-operator-key": operatorKey ?? "" },
    body: JSON.stringify({ team_size: 2, seed, max_ticks: 20, break_seconds: 30, deadline_seconds: 0.2, study: true }),
  });
  expect(res.status).toBe(200);
  return (await res.json()).id as string;
}

async function join(cookie: string, id: string) {
  const s = await openStream(cookie, `/arena/events?arena=${id}`);
  open.push(s);
  return { s, snap: (await s.waitFor((e) => e.event === "snapshot", 3000)).data };
}

const study = async () => (await (await fetch(url("/api/study"))).json()) as { bots: any[]; people: any[] };

// the finished match is saved in a thread: wait until the server has it
async function myMatch(cookie: string, id: number, ms = 3000) {
  const deadline = Date.now() + ms;
  for (;;) {
    const data = await (await fetch(url("/api/me/matches"), { headers: { cookie } })).json();
    const m = data.matches.find((x: any) => x.id === id);
    if (m || Date.now() > deadline) return m;
    await new Promise((r) => setTimeout(r, 100));
  }
}

it.runIf(operatorKey)("names every bot seat by its real bot, teammates included, while the match runs", async () => {
  const id = await studyArena(9101);
  const { s, snap } = await join(await newVisitor(), id);
  const team = snap.seats[snap.you].team;
  const mates = snap.seats.filter((x: any) => x.team === team && x.kind === "bot");
  expect(mates.length).toBeGreaterThan(0);
  for (const seat of snap.seats.filter((x: any) => x.kind === "bot")) {
    expect(seat.bot, "a bot seat without its real name").toMatch(realName);
    expect(seat).not.toHaveProperty("blind");
  }
  await new Promise((r) => setTimeout(r, 1000)); // a few turns, and any seat changes, pass
  for (const e of s.events.filter((x) => x.event === "seats" || x.event === "snapshot")) {
    for (const seat of e.data.seats.filter((x: any) => x.kind === "bot")) expect(seat.bot).toMatch(realName);
  }
  const live = (await (await fetch(url("/api/now"))).json()).find((a: any) => a.arena === id);
  for (const seat of live.seats.filter((x: any) => x.kind === "bot")) expect(seat.bot).toMatch(realName);
});

it.runIf(operatorKey)("records which bot was drawn as your teammate, asks no question, and counts it on /study", async () => {
  const id = await studyArena(9102);
  const me = await newVisitor();
  const before = await study();
  const { s, snap } = await join(me, id);
  const team = snap.seats[snap.you].team;
  const bot = snap.seats.find((x: any) => x.team === team && x.kind === "bot").bot;
  await choose(me, 0, 1);
  const over = (await s.waitFor((e) => e.event === "over", 15000)).data;
  expect(over, "no rating question after the match").not.toHaveProperty("rate");

  const m = await myMatch(me, snap.match.id);
  expect(m.bot_teammate, "Your matches shows the bot you had, by name").toBe(bot);
  expect(m).not.toHaveProperty("rating");

  const after = await study();
  const b = before.bots.find((x) => x.bot === bot);
  const a = after.bots.find((x) => x.bot === bot);
  expect(a.matches, "the draw is recorded for the match (other tests may add more)").toBeGreaterThanOrEqual(b.matches + 1);
  expect(a).not.toHaveProperty("ratings");
  expect(after.people.find((p) => p.label === snap.label && p.bot === bot)).toMatchObject({
    matches: 1, own_captures: expect.any(Number), bot_captures: expect.any(Number),
  });

  const res = await fetch(url(`/api/matches/${snap.match.id}/rating`), {
    method: "POST", headers: { "content-type": "application/json", cookie: me }, body: JSON.stringify({ score: 4 }),
  });
  expect([404, 405], "the rating endpoint is gone").toContain(res.status);
}, 30000);

it("has no rating endpoint and no rating question on any page", async () => {
  const cookie = await newVisitor();
  const res = await fetch(url("/api/matches/1/rating"), {
    method: "POST", headers: { "content-type": "application/json", cookie }, body: JSON.stringify({ score: 3 }),
  });
  expect([404, 405]).toContain(res.status);
  for (const path of ["/", "/me", "/study"]) {
    const html = await (await fetch(url(path), { headers: { cookie } })).text();
    expect(html, `${path} asks a rating question`).not.toMatch(/Was your bot teammate helpful|Bot A|Bot B/);
  }
});

it("publishes behaviour for each teammate bot with n, and labels only", async () => {
  const data = await study();
  expect(data.bots.map((b: any) => b.bot)).toEqual(expect.arrayContaining(["scripted", "cur4", "fcp1"]));
  for (const b of data.bots) {
    expect(b).toMatchObject({ matches: expect.any(Number), people: expect.any(Number), captures: { people: expect.any(Number), bots: expect.any(Number) } });
  }
  for (const p of data.people) expect(p.label).toMatch(/^Visitor [0-9a-f]{6}$/);
  const page = await fetch(url("/study"));
  expect(page.status).toBe(200);
  const html = await page.text();
  expect(html).toContain("Matches");
  expect(html).not.toMatch(/visitor=/);
});

it("tells people before they play that their bot teammate is drawn at random, and links the results", async () => {
  const html = await (await fetch(url("/"))).text();
  expect(html).toMatch(/picked at random/);
  expect(html).toContain('href="/study"');
});

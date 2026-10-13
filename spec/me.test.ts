import { afterEach, expect, it } from "vitest";
import { choose, createArena, newVisitor, openStream, operatorKey, type Stream, url } from "./helpers";

// "Your matches": each visitor sees their own finished matches, kept on the
// server and found by their cookie, so coming back the next day shows what
// they played. Others' matches never show, and no cookie is ever sent out.

const open: Stream[] = [];
afterEach(() => {
  for (const s of open.splice(0)) s.close();
});

async function myMatches(cookie: string, ms = 3000) {
  // the finished match is saved in a thread: wait until it shows
  const deadline = Date.now() + ms;
  for (;;) {
    const data = await (await fetch(url("/api/me/matches"), { headers: { cookie } })).json();
    if (data.matches.length > 0 || Date.now() > deadline) return data;
    await new Promise((r) => setTimeout(r, 100));
  }
}

it.runIf(operatorKey)("lists your own finished matches with team, score, teammates and a replay link", async () => {
  const { id } = await createArena({ team_size: 2, seed: 9201, max_ticks: 15, break_seconds: 30, deadline_seconds: 0.2 });
  const a = await newVisitor();
  const b = await newVisitor();
  const sa = await openStream(a, `/arena/events?arena=${id}`);
  open.push(sa);
  const snapA = (await sa.waitFor((e) => e.event === "snapshot", 3000)).data;
  const sb = await openStream(b, `/arena/events?arena=${id}`);
  open.push(sb);
  const snapB = (await sb.waitFor((e) => e.event === "snapshot", 3000)).data;
  await choose(a, 0, 1);
  const over = (await sa.waitFor((e) => e.event === "over", 15000)).data;

  const mine = await myMatches(a);
  expect(mine.label).toBe(snapA.label);
  const m = mine.matches.find((x: any) => x.id === snapA.match.id);
  expect(m).toMatchObject({
    team: snapA.seats[snapA.you].team,
    score: over.score,
    replay: `/matches/${snapA.match.id}`,
    result: expect.stringMatching(/^(won|lost|drew)$/),
  });
  const together = snapA.seats[snapA.you].team === snapB.seats[snapB.you].team;
  expect(together ? m.teammates : m.opponents).toContain(snapB.label);

  const html = await (await fetch(url("/me"), { headers: { cookie: a } })).text();
  expect(html).toContain(`href="/matches/${snapA.match.id}"`);
  expect(html).toContain(snapA.label);
  for (const c of [a, b]) expect(html.includes(c.split("=")[1]), "a cookie on the page").toBe(false);
}, 30000);

it("shows a new visitor an empty history, not someone else's", async () => {
  const cookie = await newVisitor();
  const data = await (await fetch(url("/api/me/matches"), { headers: { cookie } })).json();
  expect(data.matches).toEqual([]);
  const res = await fetch(url("/me"), { headers: { cookie } });
  expect(res.status).toBe(200);
  expect(await res.text()).toContain("No finished matches yet");
  expect((await (await fetch(url("/api/me/matches"))).json()).matches, "no cookie, no history").toEqual([]);
});

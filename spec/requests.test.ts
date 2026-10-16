import { expect, it } from "vitest";
import { createArena, newVisitor, openStream, operatorKey, pause, url } from "./helpers";

// Week 10: every request gets a short id. The server logs one line per
// request with it, and tags every event logged during that request with it,
// so the narrator can tie a "pause" line to the request that caused it. The
// response carries the same id, so a person can quote it when something breaks.
const ID = /^[0-9a-f]{8}$/;

it("gives every response a short request id, a new one each time", async () => {
  const cookie = await newVisitor();
  const responses = [
    await fetch(url("/")),
    await fetch(url("/"), { headers: { cookie } }),
    await fetch(url("/api/log")),
    await fetch(url("/api/matches/999999")), // a 404 has one too
    await fetch(url("/arena/pause"), { method: "POST", headers: { cookie }, body: "not json" }), // and a 400
  ];
  const ids = responses.map((res) => res.headers.get("x-request-id"));
  for (const id of ids) expect(id).toMatch(ID);
  expect(new Set(ids).size, "two requests shared an id").toBe(ids.length);
  expect(responses[3].status).toBe(404);
  expect(responses[4].status).toBe(400);
});

it("gives the live event stream a request id too", async () => {
  const res = await fetch(url("/arena/events?arena=watch"), { headers: { cookie: await newVisitor() } });
  expect(res.headers.get("x-request-id")).toMatch(ID);
  await res.body?.cancel();
});

it.runIf(operatorKey)("tags an event logged during a request with that request's id", async () => {
  const { id } = await createArena({ team_size: 2, seed: 121, deadline_seconds: 0.5 });
  const cookie = await newVisitor();
  const s = await openStream(cookie, `/arena/events?arena=${id}`);
  try {
    await s.waitFor((e) => e.event === "snapshot", 3000);
    const res = await pause(cookie, true);
    expect(res.status).toBe(200);
    const request = res.headers.get("x-request-id");
    await new Promise((r) => setTimeout(r, 300)); // the log is written just after
    const log = (await (await fetch(url("/api/log"))).json()).events as any[];
    const line = log.find((e) => e.event === "pause" && e.detail.arena === id);
    expect(line?.detail.request, "the pause line names the request that paused").toBe(request);
  } finally {
    s.close();
  }
});

// Week 10: the visitor cookie is HttpOnly and SameSite=Lax always, and Secure
// when the page was served over https (Fly ends TLS and says so in
// x-forwarded-proto). Over plain http, as on a laptop, Secure would stop the
// browser sending it back, so it is left off there.
const attributes = (res: Response) =>
  (res.headers.get("set-cookie") ?? "").split(";").slice(1).map((a) => a.trim().toLowerCase());

it("sets the visitor cookie HttpOnly and SameSite=Lax, without Secure over plain http", async () => {
  const set = attributes(await fetch(url("/")));
  expect(set).toContain("httponly");
  expect(set).toContain("samesite=lax");
  expect(set, "a Secure cookie would never come back over http").not.toContain("secure");
});

it("adds Secure to the visitor cookie when the page was served over https", async () => {
  const set = attributes(await fetch(url("/"), { headers: { "x-forwarded-proto": "https" } }));
  expect(set).toContain("secure");
  expect(set).toContain("httponly");
  expect(set).toContain("samesite=lax");
});

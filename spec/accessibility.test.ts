import axe from "axe-core";
import { JSDOM } from "jsdom";
import { expect, it } from "vitest";
import { url } from "./helpers";

// README: a friend with no finance background can use the room, and the
// marker checks it with the keyboard. axe catches the mechanical part of that
// (labels, names, landmarks, heading order) on the HTML the server sends.
// Colour contrast needs a real layout engine, which jsdom doesn't have, so
// that rule is left to a person.

async function violations(path: string, cookie?: string) {
  const html = await (await fetch(url(path), { headers: cookie ? { cookie } : {} })).text();
  const dom = new JSDOM(html, { url: url(path).href, runScripts: "outside-only" });
  dom.window.eval(axe.source);
  const run = (dom.window as unknown as { axe: typeof axe }).axe.run(dom.window.document, {
    rules: { "color-contrast": { enabled: false } },
    resultTypes: ["violations"],
  });
  const results = await run;
  dom.window.close();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

it("has no serious accessibility problems on any page", async () => {
  for (const path of ["/", "/log", "/readme/"]) {
    expect(await violations(path), path).toEqual([]);
  }
});

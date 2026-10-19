import { JSDOM } from "jsdom";
import { expect, it } from "vitest";
import { url } from "./helpers";

// A marker arrives with only the URL and starts at /readme/. From there they
// must reach the game, learn the keys, and find their history; and the game
// must be playable with a keyboard or a tap.

const page = async (path: string) => new JSDOM(await (await fetch(url(path))).text()).window.document;

it("links every page to the game, your matches, the log and the README", async () => {
  for (const path of ["/", "/readme/", "/me", "/log", "/study"]) {
    const nav = (await page(path)).querySelector('nav[aria-label="Main"]');
    const hrefs = [...(nav?.querySelectorAll("a") ?? [])].map((a) => a.getAttribute("href"));
    expect(hrefs, path).toEqual(expect.arrayContaining(["/", "/me", "/log", "/readme/"]));
  }
});

it("tells a newcomer on /readme/ how to play and where their matches are", async () => {
  const doc = await page("/readme/");
  const body = doc.querySelector("main")!;
  const links = [...body.querySelectorAll("a")].map((a) => a.getAttribute("href") ?? "");
  expect(links.some((h) => /^https?:\/\/[^/]+\/?$/.test(h) || h === "/"), "a link to the game").toBe(true);
  expect(links.some((h) => h.endsWith("/me")), "a link to your matches").toBe(true);
  const text = body.textContent ?? "";
  expect(text).toMatch(/arrow keys/i);
  expect(text).toMatch(/second window/i);
});

it("makes every move on the pad a real button with a name, and the board reachable by Tab", async () => {
  const doc = await page("/");
  const pad = [...doc.querySelectorAll(".pad > *")];
  expect(pad).toHaveLength(5);
  for (const b of pad) {
    expect(b.tagName, "a pad control that isn't a button").toBe("BUTTON");
    expect(b.getAttribute("type")).toBe("button");
    expect(b.getAttribute("aria-label")).toMatch(/^(Move (up|down|left|right)|Stand still)$/);
  }
  const board = doc.querySelector('[data-field="board-focus"]')!;
  expect(board.getAttribute("tabindex")).toBe("0");
  expect(board.getAttribute("aria-label")).toMatch(/arrow keys/);
  expect(doc.querySelector('[data-field="pause"]')?.getAttribute("aria-keyshortcuts")).toBe("P");
  expect(doc.querySelector('a.skip[href="#board"]'), "a skip link to the board").not.toBeNull();
});

it("never makes a page wider than a phone: tables scroll inside a box a keyboard can reach", async () => {
  for (const path of ["/me", "/study"]) {
    for (const wrap of (await page(path)).querySelectorAll(".table-wrap")) {
      expect(wrap.getAttribute("tabindex"), path).toBe("0");
      expect(wrap.getAttribute("aria-label"), path).toBeTruthy();
    }
  }
});

it("sends every link on /readme/ somewhere that exists: repo files go to GitHub, site pages answer", async () => {
  const doc = await page("/readme/");
  for (const a of doc.querySelectorAll("main a")) {
    const href = a.getAttribute("href") ?? "";
    if (/^https?:/.test(href)) {
      expect(href.startsWith(url("/").origin + "/readme/") , `${href} points inside /readme/`).toBe(false);
      continue;
    }
    expect(href.startsWith("/"), `${href} is relative, so it breaks under /readme/`).toBe(true);
    expect((await fetch(url(href))).status, href).toBe(200);
  }
});

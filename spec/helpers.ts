import { readFileSync } from "node:fs";
import { inject } from "vitest";
import type { Rule } from "./model";

export const baseUrl = inject("baseUrl");
export const url = (path: string): URL => new URL(path, baseUrl);

export interface Round {
  id: number;
  in_sample_start: string;
  in_sample_end: string;
  trial_count: number;
  distinct_rules: number;
  timing_rules: number;
  luck_bar: number | null;
  revealed: boolean;
}

export interface Trial {
  id: number;
  round_id: number;
  visitor: string;
  rule: Rule & { key: string; label: string };
  leverage: number;
  stats: { cagr: number; volatility: number; sharpe: number; max_drawdown: number };
  confidence: number | null;
  curve: { month: string; value: number }[];
}

export async function currentRound(): Promise<Round> {
  const res = await fetch(url("/api/rounds/current"));
  if (!res.ok) throw new Error(`/api/rounds/current answered ${res.status}`);
  return (await res.json()) as Round;
}

// Form fields for a rule, as the page's form sends them. A bare string is a
// fixed-leverage rule (or a deliberately bad value).
function fields(rule: Rule | string): Record<string, string> {
  if (typeof rule === "string") return { rule: "fixed", leverage: rule };
  const { type, ...rest } = rule;
  return { rule: type, ...Object.fromEntries(Object.entries(rest).map(([k, v]) => [k, String(v)])) };
}

// Runs a trial the way the page's form does, as a fresh visitor unless a
// cookie is passed. Returns the new trial's id and the visitor cookie.
export async function runTrial(
  rule: Rule | string,
  cookie?: string,
): Promise<{ id: number; cookie: string; res: Response }> {
  const res = await fetch(url("/trials"), {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      ...(cookie ? { cookie } : {}),
    },
    body: new URLSearchParams(fields(rule)),
    redirect: "manual",
  });
  const location = res.headers.get("location") ?? "";
  const id = Number(new URL(location, baseUrl).searchParams.get("trial"));
  const setCookie = res.headers.get("set-cookie")?.split(";")[0];
  return { id, cookie: setCookie ?? cookie ?? "", res };
}

export async function getTrial(id: number, cookie: string): Promise<Trial> {
  const res = await fetch(url(`/api/trials/${id}`), { headers: { cookie } });
  if (!res.ok) throw new Error(`/api/trials/${id} answered ${res.status}`);
  return (await res.json()) as Trial;
}

export async function roundTrials(cookie?: string): Promise<{ unlocked: boolean; hidden: number; trials: Trial[] }> {
  const res = await fetch(url("/api/rounds/current/trials"), { headers: cookie ? { cookie } : {} });
  if (!res.ok) throw new Error(`/api/rounds/current/trials answered ${res.status}`);
  return (await res.json()) as { unlocked: boolean; hidden: number; trials: Trial[] };
}

// Opens the event stream and collects events until `stop` returns true or the
// time runs out. Returns the events seen, parsed from their JSON data.
export async function collectEvents(
  cookie: string | undefined,
  ms: number,
  onOpen: () => Promise<void>,
  stop: (events: { event: string; data: any }[]) => boolean,
): Promise<{ event: string; data: any; at: number }[]> {
  const controller = new AbortController();
  const res = await fetch(url("/events"), {
    headers: { accept: "text/event-stream", ...(cookie ? { cookie } : {}) },
    signal: controller.signal,
  });
  if (!res.ok || !res.body) throw new Error(`/events answered ${res.status}`);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  const events: { event: string; data: any; at: number }[] = [];
  let buffer = "";
  let opened = false;
  const deadline = Date.now() + ms;
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    while (Date.now() < deadline) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let cut: number;
      while ((cut = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const event = block.match(/^event: (.*)$/m)?.[1] ?? "message";
        const data = block.match(/^data: (.*)$/m)?.[1];
        if (data !== undefined) events.push({ event, data: JSON.parse(data), at: Date.now() });
      }
      if (!opened && events.length > 0) {
        opened = true; // the first event is the snapshot sent on connect
        await onOpen();
      }
      if (stop(events)) break;
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") throw err;
  } finally {
    clearTimeout(timer);
    controller.abort();
  }
  return events;
}

// data/momentum.csv, read independently of the app, for checking its numbers.
export interface Month {
  month: string;
  momentum: number;
  market: number;
  rf: number;
}

export function months(): Month[] {
  const [, ...rows] = readFileSync("data/momentum.csv", "utf8").trim().split("\n");
  return rows.map((row) => {
    const [month, momentum, market, rf] = row.split(",");
    return { month, momentum: Number(momentum), market: Number(market), rf: Number(rf) };
  });
}

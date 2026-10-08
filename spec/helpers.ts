import { inject } from "vitest";

export const baseUrl = inject("baseUrl");
export const url = (path: string): URL => new URL(path, baseUrl);

// Opens an event stream and collects events until `stop` returns true or the
// time runs out. `onOpen` runs once the first event (the snapshot) arrives.
export async function collectEvents(
  cookie: string | undefined,
  ms: number,
  onOpen: () => Promise<void>,
  stop: (events: { event: string; data: any }[]) => boolean,
  path = "/events",
): Promise<{ event: string; data: any; at: number }[]> {
  const controller = new AbortController();
  const res = await fetch(url(path), {
    headers: { accept: "text/event-stream", ...(cookie ? { cookie } : {}) },
    signal: controller.signal,
  });
  if (!res.ok || !res.body) throw new Error(`${path} answered ${res.status}`);
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
        opened = true;
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

// --- the arena ---------------------------------------------------------------

export const operatorKey = process.env.OPERATOR_KEY;

// A fresh visitor: the cookie the game page hands out on a first visit.
export async function newVisitor(): Promise<string> {
  const res = await fetch(url("/"));
  const cookie = res.headers.get("set-cookie")?.split(";")[0];
  if (!cookie) throw new Error("/ didn't set a visitor cookie");
  return cookie;
}

export async function createArena(options: { team_size: number; seed: number; max_ticks?: number; break_seconds?: number }) {
  const res = await fetch(url("/api/arenas"), {
    method: "POST",
    headers: { "content-type": "application/json", "x-operator-key": operatorKey ?? "" },
    body: JSON.stringify(options),
  });
  if (res.status !== 200) throw new Error(`/api/arenas answered ${res.status}`);
  return (await res.json()) as { id: string };
}

export async function sendInput(cookie: string, dir: number, held: boolean, seq: number): Promise<Response> {
  return fetch(url("/arena/input"), {
    method: "POST",
    headers: { "content-type": "application/json", cookie },
    body: JSON.stringify({ dir, held, seq }),
  });
}

export interface StreamEvent {
  event: string;
  data: any;
  at: number;
}

// A long-lived event stream the test can read from while doing other things.
export interface Stream {
  events: StreamEvent[];
  waitFor(match: (e: StreamEvent) => boolean, ms: number, from?: number): Promise<StreamEvent>;
  close(): void;
}

export async function openStream(cookie: string | undefined, path: string): Promise<Stream> {
  const controller = new AbortController();
  const res = await fetch(url(path), {
    headers: { accept: "text/event-stream", ...(cookie ? { cookie } : {}) },
    signal: controller.signal,
  });
  if (!res.ok || !res.body) throw new Error(`${path} answered ${res.status}`);
  const events: StreamEvent[] = [];
  const waiters = new Set<() => void>();
  (async () => {
    const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    try {
      for (;;) {
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
        for (const wake of [...waiters]) wake();
      }
    } catch {
      // aborted by close()
    }
  })();
  return {
    events,
    close: () => controller.abort(),
    waitFor(match, ms, from = 0) {
      return new Promise((resolve, reject) => {
        const check = () => {
          const found = events.slice(from).find(match);
          if (found) {
            waiters.delete(check);
            clearTimeout(timer);
            resolve(found);
          }
        };
        const timer = setTimeout(() => {
          waiters.delete(check);
          reject(new Error(`no matching event within ${ms} ms on ${path}`));
        }, ms);
        waiters.add(check);
        check();
      });
    },
  };
}

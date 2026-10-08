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

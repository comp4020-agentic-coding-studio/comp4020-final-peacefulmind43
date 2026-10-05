import { readFileSync } from "node:fs";
import { inject } from "vitest";

export const baseUrl = inject("baseUrl");
export const url = (path: string): URL => new URL(path, baseUrl);

export interface Round {
  id: number;
  in_sample_start: string;
  in_sample_end: string;
  trial_count: number;
  revealed: boolean;
}

export interface Trial {
  id: number;
  round_id: number;
  visitor: string;
  leverage: number;
  stats: { cagr: number; volatility: number; sharpe: number; max_drawdown: number };
  curve: { month: string; value: number }[];
}

export async function currentRound(): Promise<Round> {
  const res = await fetch(url("/api/rounds/current"));
  if (!res.ok) throw new Error(`/api/rounds/current answered ${res.status}`);
  return (await res.json()) as Round;
}

// Runs a trial the way the page's form does, as a fresh visitor unless a
// cookie is passed. Returns the new trial's id and the visitor cookie.
export async function runTrial(
  leverage: string,
  cookie?: string,
): Promise<{ id: number; cookie: string; res: Response }> {
  const res = await fetch(url("/trials"), {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      ...(cookie ? { cookie } : {}),
    },
    body: new URLSearchParams({ leverage }),
    redirect: "manual",
  });
  const location = res.headers.get("location") ?? "";
  const id = Number(new URL(location, baseUrl).searchParams.get("trial"));
  const setCookie = res.headers.get("set-cookie")?.split(";")[0];
  return { id, cookie: setCookie ?? cookie ?? "", res };
}

export async function getTrial(id: number): Promise<Trial> {
  const res = await fetch(url(`/api/trials/${id}`));
  if (!res.ok) throw new Error(`/api/trials/${id} answered ${res.status}`);
  return (await res.json()) as Trial;
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

# 0001. Python, FastAPI, SQLite on the volume, and server-sent events

Status: accepted (2026-10-06)

## Context

The app is a shared research room. A visitor picks a rule to lay over a
momentum portfolio (at first, just a leverage level), the server backtests it,
and the result joins every other result from the same round. Each trial anyone
runs makes everyone's results less trustworthy, so the trial count and the
results have to reach every open page within about a second.

Three answers shaped the stack:

- **A person** is an anonymous browser, told apart by a random id in a cookie.
  No names and no accounts.
- **What persists** is every trial, grouped into rounds. A round is archived and
  read-only once its hold-out period is revealed.
- **How a change travels** is one way: server to browser (a new trial, the
  count, a reveal). Visitors act through ordinary form posts.

The course fixes the rest: one `shared-cpu-1x` Fly machine with 256 MB of
memory, one volume at `/data`, HTTP on `0.0.0.0:$PORT`, and `/readme/` must
contain the README's headings in the HTML the server sends.

## Options

1. **Python + FastAPI + SQLite + SSE.** The backtests and statistics are
   numerical work, which Python does well, and it is the language I can read
   best. FastAPI is async, so holding SSE connections open is direct. SQLite is
   a file on the volume, so there is no database server to run.
2. **Django + Channels.** Mature, with migrations and an admin built in. But
   real-time needs Channels and an ASGI setup on top, which is a lot of moving
   parts for a few tables, and more memory on a 256 MB machine.
3. **Phoenix LiveView.** Real-time is built in, which is the strongest argument
   for it. But it is Elixir, which I cannot review well, and the statistics
   (deflated Sharpe ratios, drawdowns) are much less convenient there.
4. **Node + Express + WebSockets.** Widely used, and WebSockets are flexible.
   But the app never needs browser-to-server messages, and the numerical code
   would be weaker than in Python.

## Decision

Option 1:

- **FastAPI** served by uvicorn, one process. Pages are rendered on the server
  with Jinja templates, plus a little plain JavaScript. The README is rendered to
  HTML on the server, so `/readme/` works without any script.
- **SQLite at `/data/app.db`**, with numbered SQL migration files in
  `app/migrations/`. The app applies any missing ones when it starts, because the
  volume only exists on the running machine (Fly's `release_command` runs on a
  temporary machine without it).
- **Server-sent events** for real-time, broadcast inside the one process. There
  is only one machine, so no message queue is needed.
- **Plain Python for the arithmetic, no pandas**, to stay well inside 256 MB.
  The data is monthly and small; numpy can come in later if a statistic needs
  it.

## Consequences

- Only one process may write and broadcast. Running several workers would split
  the SSE subscribers and break real-time. That is fine on one small machine, and
  it is written into `CLAUDE.md` so a later change doesn't add workers.
- An open page keeps an SSE connection, which keeps the Fly machine awake while
  someone is watching. That is the right trade: the machine still stops when
  nobody is there.
- Hand-written SQL migrations mean no ORM to hide mistakes, but also nothing to
  generate them. Every schema change is a new numbered file, never an edit to an
  old one.
- If real-time later needs browser-to-server messages, SSE stops fitting, and a
  new record would replace this one.

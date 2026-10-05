# Harness

The app is a shared research room for overlay rules on a momentum portfolio.
`README.md` says what good means here. These rules come from it. When a rule and
a request conflict, stop and ask.

## Decisions

Decisions live in `doc/adr/`, one numbered file each. Read them before changing
the stack, storage, data, or data model. To change one, write a new record that
supersedes it. Never edit an accepted record.

## What the app must never do

- **Never send hold-out data before the reveal.** During a round, no page, API
  response, or SSE event may contain a month after the round's in-sample end.
  This includes charts, tables, error messages, and debug output.
- **Never hide, edit, or delete a trial.** Every trial counts against the whole
  room. A trial that disappears makes everyone's results look more trustworthy
  than they are. The database enforces this; don't work around it.
- **Never show other people's results to someone who hasn't tested this
  round** (ADR 0003). This applies to every surface, including ones added later:
  pages, the API, both event streams and the activity log. A new surface starts
  redacted and the spec checks it as a newcomer.
- **Never log or show a visitor's cookie.** Use the public label.
- **Never present a result as advice.** Results describe a historical momentum
  portfolio, not SPMO and not a recommendation. Say what was tested, not what
  to do.
- **Never let a failed backtest crash the page.** If a computation fails, show
  what failed and keep the room working.

## How the work must be done

- **Statistics need a check against a known value.** Any new metric (Sharpe,
  drawdown, deflated Sharpe, financing cost) gets a test with a hand-checkable
  case before it is shown to anyone.
- **A correct statistic can still answer the wrong question.** Before a new
  figure goes on the page, run it over a spread of real rules and look at the
  spread. If every rule gets the same answer (the first deflated Sharpe gave
  every rule 100%), the question is wrong, even if the formula is right. Say
  what question the figure answers in the ADR, in words a holder would ask.
- **Schema changes are new migration files** in `app/migrations/`, numbered in
  order. Never edit a migration that has been committed.
- **One process.** Real-time is broadcast inside one uvicorn process. Don't add
  workers or a second process; it would split the live updates.
- **Fit the machine.** 256 MB of memory. No pandas, no large in-memory caches.
- **Plain language on the page.** A first-time visitor with no finance
  background should understand what to do. Technical detail goes behind a
  "details" section, not in the main view.
- **English** for everything in the repo and on the site.

## Checks

`pnpm check` runs `spec/` against the running app (`APP_URL`, default
`http://localhost:8080`). Run it before every commit that changes behaviour.

**Never point `pnpm check` at the live app.** The spec runs trials, and trials
are permanent, so every run against `*.fly.dev` adds test trials to the real
room's count. Run it against a local app (`DATA_DIR=.data`) or let CI run it
against its throwaway `/data`. Check the live app by reading it, not by
writing to it.
When the agent gets something wrong twice, add a check or a rule here instead of
re-prompting.

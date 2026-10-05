# 0006. Log every action; show the log by the same rule as the room

Status: accepted (2026-10-06)

## Context

Crit 10 asks the app to write one structured log line for each thing a user
does (who, what, when) and to put a live view on it. The logs are also
evidence for or against the README: they show how people actually use the
room, against what good was said to look like. Two of the README's claims are
about behaviour, and logs are the only way to check them:

- that the first test is your own idea (ADR 0003 hides other people's results
  until you have tested), and
- that the luck bar changes how people search (do they keep tuning one rule,
  or stop?).

A live view raises the same question ADR 0003 answered for the room: a public
page that says "Visitor 3fa9c1 ran 2× with a trend filter, 24% a year" would
let anyone see results without testing first.

## Options

1. **Logs to stdout only.** `flyctl logs` tailed in a terminal satisfies the
   crit. But the logs vanish with the machine's log buffer, so there is nothing
   to look back at when writing the README, and only I can see them.
2. **A private stats page behind a secret.** Full detail for me, nothing for
   anyone else. But CI has no way to know the secret, so the page can't be
   checked, and the room loses something it could share.
3. **Every action to stdout in full, and to the database; a public live view
   that applies ADR 0003.** Visitors who haven't tested this round see that
   things happened ("ran a test", "opened the room"), not what the tests were.
   Visitors who have tested see the detail, as they already can in the table.

## Decision

Option 3.

- **One JSON line per action on stdout**, in full, for me and for the agent when
  the deployed app misbehaves: `event`, `visitor` (the public label, never the
  cookie), `at` (seconds since the epoch), and what the action was.
- **The same events in an `events` table** on the volume, so they survive a
  restart and can be read back for the README.
- **Actions logged**: opening the room (and whether it was locked for them),
  running a test (the rule, the results, whether it was their first in the
  round, whether they had already seen others' results, whether someone had
  already tried that rule), a refused test, opening and leaving the live
  stream (so the log knows who is in the room right now), and reading the
  README. Polling and the log view itself are not actions.
- **The live view at `/log`**, updated over its own event stream, shows who is
  in the room now, a few counts, and the recent actions, redacted per viewer
  by ADR 0003's rule.

## Consequences

- The log knows when each visitor first saw other people's results and what
  they tested next, which is exactly what ADR 0003's claim needs.
- Times are shown as "x seconds ago", never as calendar dates, so the log can't
  trip the hold-out check (ADR 0002).
- The cookie is never logged anywhere: it is the only thing that lets someone
  act as a visitor. The label is a one-way hash of it.
- The `events` table grows with use. At a room's scale (a few hundred actions
  an evening) that is nothing for SQLite; if it ever matters, old events can be
  summarised, because unlike trials they carry no promise to stay.
- Checked in `spec/`: each action produces a log entry with who, what and when;
  a newcomer's view of the log carries no rule or result; the log view updates
  live; no cookie value appears in it.

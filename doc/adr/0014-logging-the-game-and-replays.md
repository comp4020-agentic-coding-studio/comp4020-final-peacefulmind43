# 0014. Every choice logged, every match replayable

Status: accepted (2026-10-10). Carries ADR 0006's approach (one JSON line per
action on stdout, kept in the database, a live view) over to the game.

## Context

Crit 10 asks for one structured log line for each thing a user does (who,
what, when), a live view of it, and a demo narrated from the logs alone while
classmates play. For this game the actions that matter are the choices people
make each turn, arriving several times a second during a crit, plus joining,
leaving, takeovers, and what happened in a match.

Logs are also the evidence for the README. "Is the bot a good teammate?" can
only be answered from what people actually did with it, and the RL work needs
those games as data: a match that can be replayed exactly is a dataset; a
score is not.

## Options

1. **Log each choice into the existing `events` table.** One place for
   everything. But each insert there scans the last hour and pushes to every
   open log page, which at a crit's rate of choices would slow the server.
2. **Log choices to stdout only.** Cheap, and `fly logs` is a valid live view.
   But it vanishes with the log buffer, so nothing is left to analyse.
3. **Choices to stdout as they happen, batched into their own table, and a
   replay saved with each match.**

## Decision

Option 3.

- **Each choice** writes one JSON line to stdout when its request arrives:
  `event`, `visitor` (the public label, never the cookie), `at`, `arena`,
  `match`, `turn`, `seat`, `dir`. Never inside a turn.
- The same lines are **buffered and written in batches** to a `game_events`
  table every few seconds, in a thread.
- **Moments** (tags, pickups, captures, takeovers) go into the activity log too,
  so `/log` tells the story of a match: who joined, who scored, who left.
- **Each finished match saves a replay**: the seed, team size, rules version and
  every turn's actions for every seat. `GET /api/matches/<id>/replay` returns
  it. The spec replays it through the TypeScript engine and must reach the same
  score and state hash the server saved.
- Replays and choices are tied to the public label, not the cookie. The page
  says that moves are recorded. Raw exports stay out of the public repo.

## Consequences

- The crit 10 demo can be told from `fly logs` and `/log` without opening the
  game.
- Every match with a person in it becomes a test case for the engine and a
  sample for evaluating bots with people.
- A rules change makes old replays unplayable under the new rules; each replay
  records its rules version, and only current-version replays are checked.

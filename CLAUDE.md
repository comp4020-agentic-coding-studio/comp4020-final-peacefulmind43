# Harness

The app is a capture-the-flag game where people and bots share teams.
`README.md` says what good means here; these rules come from it. When a rule
and a request conflict, stop and ask.

## Decisions

Decisions live in `doc/adr/`, one numbered file each. Read them before changing
the rules, the stack, storage, the data model, or the bot. To change one, write
a new record that supersedes it; a record not yet merged may be amended, saying
so. The rules of the game are ADR 0010; any change to them bumps
`RULES_VERSION` in both engines.

## What the game must never do

- **Never let a bot see more than a person.** Bots choose from the game state
  as it was shown when the turn opened: never from people's choices, never
  from anything not on screen. A bot function takes the state and a seat,
  nothing else.
- **Never make a person lose for being slower than a program.** A turn waits
  for every person with the page open, up to the deadline (ADR 0012).
- **Never stop a game because someone left.** A closed page's seat is covered
  by a bot after the grace period; a match never waits on someone who can't
  choose.
- **Never play matches for nobody.** An arena with no one in it goes idle;
  every saved match had a person in it.
- **Never hide which bot is playing.** Every bot seat names its bot.
- **Never log or show a visitor's cookie.** Use the public label.
- **Never touch the database or the log inside a turn.** Write them after it,
  or in a thread.

## How the work must be done

- **Two engines, one set of rules.** `app/game/engine.py` and `spec/engine.ts`
  implement ADR 0010 separately. Change both, and the parity spec must pass.
- **Both teams are the same.** Anything that depends on a direction is
  mirrored for red: bot tie-breaks, guard cells, the observation, and the
  action the network chooses (`obs.to_engine`). The mirror tests in `tests/`
  must pass.
- **Try the design before trusting it.** Before a rule or balance change,
  play scripted bots against each other over many seeds and compare numbers;
  give each game its own randomness, or the games aren't separate samples.
- **Play it yourself.** Tests show the rules hold, not that the game is
  pleasant; a change to timing or input gets played by a person before it ships.
- **Look at what a trained bot does, not just its score.** Before changing a
  reward or a hyperparameter, watch the bot play and measure where it goes.
- **Profile before optimising.**
- **One observation builder.** Training and serving both use `app/game/obs.py`.
  A bot ships only with an export whose NumPy output matches PyTorch's.
- **Schema changes are new migration files** in `app/migrations/`, numbered in
  order. Never edit a migration that has been committed.
- **One process.** Live updates are broadcast inside one uvicorn process.
- **Fit the machine.** 256 MB of memory; no PyTorch on the server.
- **Write down each step that matters** in `doc/process-log.md`, and keep
  `PROCESS.md` current.
- **English** for everything in the repo and on the site.

## Checks

`pnpm check` runs `spec/` against a running app (`APP_URL`, default
`http://localhost:8080`; set `OPERATOR_KEY` to run the private-arena checks).
`python -m pytest tests` runs the engine, observation and bot tests. Run both
before every commit that changes behaviour.

**Never point `pnpm check` at the live app.** The spec plays matches and saves
them. Run it against a local app (`DATA_DIR=.data`) or let CI run it against its
throwaway `/data`. Check the live app by reading it, not by writing to it.

When the agent gets something wrong twice, add a check or a rule here instead
of re-prompting.

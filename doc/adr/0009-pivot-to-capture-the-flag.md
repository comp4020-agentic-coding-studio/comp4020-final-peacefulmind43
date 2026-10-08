# 0009. Change the project to a capture-the-flag game with bot teammates

Status: accepted (2026-10-08). Supersedes ADRs 0002, 0003, 0004, 0005, 0007 and
0008 (the Overlay Room's data, rules, discount, reveal and picks). ADR 0001's
stack stands, with the change in ADR 0011; ADR 0006's logging approach carries
over to the game in a later record.

## Context

Until crit 8 the project was the Overlay Room: friends testing rules on a
momentum portfolio, with every test counted against the room. At crit 8 it
felt static, and I agreed. Its core action, running a backtest, is something
one person does alone. Live counts, a luck bar and later picks (ADR 0008)
wrapped that solo action in shared numbers, but other people only changed what
was on your screen, never what you did next. The brief asks for an app that is
more interesting because other people are using it at the same time, and the
showcase is a room full of people at once.

I also want this project to show work in reinforcement learning for games,
which the Overlay Room couldn't.

## Options

1. **Keep the Overlay Room and polish it.** Safe, and most of it is built. It
   stays a solo tool with a social layer.
2. **Keep the room and make picking the centre (ADR 0008).** Better, but the
   interaction is still slow and indirect: you act once, and wait for a reveal.
3. **Change to a real-time game where people act on each other directly.** A
   team game makes other people the whole point: you block them, chase them,
   cover for them. Bots fill empty seats, so a game can always start, and
   training those bots is the reinforcement learning work.

## Decision

Option 3: a grid capture-the-flag game, two teams, humans and bots mixed
(ADR 0010 sets the rules). What makes it more than "a game with bots" is the
question the README argues: what makes a bot a good teammate for people, and
can that be measured with real players?

## Consequences

- The Overlay Room's code is removed from the current tree in one commit; its
  history, records and lessons stay in the repository. Its tables stay in the
  database untouched (its trials were promised never to be deleted).
- Most of what was learned carries over: the harness, test-first specs, an
  independent model for every number the app publishes, the redaction rule for
  new surfaces, and never running the spec against the live app.
- The work restarts six days before crit 9. Crit 9 is marked on applying its
  process lens (real-time, one decision about several people), not on how far
  the project is, which makes the change affordable now and not later.
- `main` holds the finished Overlay Room v2 as a working fallback until the game
  is ready to replace it.

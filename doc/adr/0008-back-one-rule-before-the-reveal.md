# 0008. Each person backs one rule before the reveal

Status: accepted (2026-10-07)

## Context

At crit 8 the room felt static. The core action, running a backtest, is
something one person does alone. The live count, the luck bar and the hidden
results (ADR 0003) wrap that solo action in shared numbers, but other people
only ever change what is on your screen, never what you decide. The brief asks
for an app that is more interesting because others are using it at the same
time, and the showcase is a room full of people at once.

The room also stops one step short of the question a holder actually faces.
Testing is cheap; holding a rule is a commitment made without knowing the
future. A room that only tests never asks anyone to commit.

## Options

1. **Keep the room as it is.** Least work. It stays a tool with a shared
   counter.
2. **Reactions on tests** ("I'd hold this" / "I wouldn't"). Social, and cheap
   to build, but costs nothing to give, so it says little and changes no one's
   mind.
3. **Each person backs one rule before the reveal.** From the rules the room has
   tested (anyone's, not only your own), you back the one you would actually
   hold. Everyone sees, live, how many people back each rule. At the reveal, the
   locked years show how each pick did.

## Decision

Option 3.

- **Who can back:** anyone who has run a test in the round (the same unlock as
  ADR 0003). One pick per person per round. You can change it until the reveal;
  only the pick standing at the reveal counts. Changing is allowed because
  nothing about the locked years is visible before the reveal, so a change can
  only respond to the room, which is the interaction this is for.
- **What can be backed:** only a rule someone has tested in this round.
- **Who sees what:** the number of picks is live for everyone. Which rules are
  backed, and by whom, is live for visitors who have tested, as with results.
- **How a pick is judged at the reveal:** by what the rule added per year in the
  locked years beyond holding the same amount of the portfolio (the regression
  of ADR 0005, applied to every rule, including fixed leverage, which adds only
  its costs). Growth alone would reward whoever borrowed most in a rising
  market, which is risk, not skill. The revealed round shows each person's
  pick, the room's most-backed rule, and how both did.
- Picks are logged, including changes, so the log shows whether people move
  towards the crowd.

## Consequences

- The room now has a reason to look at other people's rules: you may want to
  back one. Discussion moves from "what did you get" to "would you hold that".
- The reveal has stakes: every person's pick is scored in public.
- Fixed-leverage rules now show a (small, negative) "added beyond holding" in a
  revealed round, where ADR 0005 showed nothing. ADR 0005 still holds for the
  luck discount, which fixed rules stay out of.
- The events table's list of kinds is now checked in the app, not in a CHECK
  constraint, so a new kind of event doesn't need the table rebuilt again
  (migration 0005 already had to once).
- Checked in `spec/`: only visitors who have tested can back a rule, only a rule
  tested in the round, one pick each with the latest counting; the counts reach
  open pages live, redacted for newcomers; the revealed round scores each pick
  against an independent model.

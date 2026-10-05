# 0007. Rounds reveal on a published schedule

Status: accepted (2026-10-06)

## Context

The README promises that the years from 2016 stay locked "until the round is
revealed", but nothing ever revealed a round. The reveal is the payoff of the
whole room: a group searched 1927–2015 for rules that seemed to add something,
and the locked years show which of them still did in the years a SPMO holder
could actually have used them. Without it, the room only ever shows in-sample
results, which is the thing it warns about.

Someone has to decide when a round ends, and whoever decides can game it, for
example by revealing right after their own rule looks best.

## Options

1. **On a schedule published when the round opens.** Nobody controls the
   timing, and everyone knows the deadline. If nobody is online at the time,
   nobody watches it happen.
2. **When enough people in the room vote for it.** The most shared moment. But
   visitors are anonymous (ADR 0001), so one person with several browsers can
   push it through, and a vote invites timing games.
3. **When I decide.** Flexible, and good for a live demo. But the room then
   depends on one person, and the person running the room can game it as easily
   as anyone.

## Decision

Option 1.

- Each round's **reveal time is set when it opens**: the first Wednesday at
  11:00 Canberra time that is at least three days away. Wednesday 11:00 falls
  inside my crit session, so a pod can watch a reveal together. The page shows
  the time in words (never as a year-month, which ADR 0002's check forbids).
- At the reveal time the server reveals the round, opens the next one, and tells
  every open page over the event stream. A stopped Fly machine reveals on its
  next start; the results don't depend on when that is, because the data and
  the trials are fixed.
- **A revealed round is fully public**: every rule tried, its results on
  1927–2015 and on the locked years, and what its timing added there. ADR 0003's
  hiding only applies to an open round.
- **An operator key** (`REVEAL_KEY`, a secret, never in the repo) can reveal the
  open round early. It exists so the spec can test a reveal without waiting a
  week, and for an emergency. Every use is logged as a public event in the
  activity log, so an early reveal is never silent. Without the key set, the
  endpoint doesn't exist.

## Consequences

- The reveal can't be gamed by visitors, and an early reveal by me is visible.
- If the machine is asleep at 11:00, the reveal happens on the next request.
  That is fine for the results, but the "watch it together" moment needs someone
  to have the page open, which a crit session provides.
- Rounds are a week long by default. A round with no tests still reveals on
  time and simply shows nothing to compare.
- CI sets `REVEAL_KEY` to a throwaway value in the workflow so the spec can run
  a reveal; production sets its own as a Fly secret.
- Checked in `spec/`: a reveal opens a new round, the revealed round shows
  locked-year results while the new round still shows none, the reveal reaches
  open pages live, and an early reveal appears in the log.

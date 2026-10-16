# 0021. Playing alone keeps the 2-second deadline

Status: accepted (2026-10-16). Clarifies ADR 0012; it does not change it.

## Context

ADR 0012's options say that alone "you play at your own pace and can stop to
think". Its decision says something else: a turn resolves when every present
person has chosen, or 2 seconds after it opened. Alone, that still means 2
seconds, and the README's Limits says so. The game does this; only 0012's
wording is wrong.

WCAG 2.2.1 Timing Adjustable says a time limit should be one the user can turn
off, adjust or extend, unless it is essential to a real-time event
(https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html). The pause
button (ADR 0015) already lets anyone, alone or not, stop the clock for as long
as they like.

## Options

1. **No deadline when alone.** A turn waits for the only person. Matches 0012's
   wording, but solo play gets different rules, and a match against bots can
   wait forever on someone who left the page open.
2. **Keep the deadline when alone, with pause as the way to stop and think.**
   The same rules alone and together.
3. **A per-player setting** for the deadline (2 s, longer, or none). The most
   flexible, but it needs a setting, rules for when players disagree, and
   matches that are not comparable.

## Decision

Option 2, for now.

- The rules are the same alone and together, so a solo match plays like the
  matches the study compares.
- A match with only bots and one person never waits forever: if the person
  walks away, the deadline still moves it on until their seat is covered.
- Pause (ADR 0015) covers "stop and think": one press stops the clock with no
  time limit, and one press carries on.

## Consequences

- The deadline can't be made longer without pausing. A player who needs more
  than 2 seconds on every turn has to pause and resume each time.
- WCAG 2.2.1's real-time exception is weaker for solo play: with nobody else
  waiting, the 2 seconds is less clearly essential. Pause is what keeps this
  close to the rule (it lets the user turn the limit off).
- ADR 0012's decision stands as written; this record only corrects what its
  options text promised. The student may revisit this, most likely with
  option 3, if players find 2 seconds too short.

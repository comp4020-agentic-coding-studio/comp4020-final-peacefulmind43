# 0003. Run your own test before you see anyone else's results

Status: accepted (2026-10-06)

## Context

Crit 9 asks for one decision about how the app behaves with several people in
it, made using the README's definition of good. The README says the room exists
so that people can't fool themselves: the more rules a room tries, the more
likely one looks good by luck.

With real-time updates, every test anyone runs can reach every open page within
a second. The question is how much of it should. Suppose someone opens the room
and the first thing they see is "Visitor 3fa9c1: 2× leverage with a trend
filter, 24% a year". They are now likely to try something close to it, and then
something close to that. That is the search the room is meant to slow down,
done faster and by several people at once.

## Options

1. **Everything live, to everyone.** Every test's rule and results appear on
   every page as soon as it runs. The most open and the liveliest. But it
   invites everyone to chase the current best result, which speeds up exactly
   the overfitting the README warns about.
2. **Count and discount live; results once you've run your own test.** Everyone
   always sees, live, how many tests and how many different rules the room has
   tried, and how high a result now has to be before luck is a poor
   explanation. The rules and results of other people's tests unlock once you
   have run at least one test of your own in this round.
3. **Count and discount live; results only at the reveal.** Nobody sees anyone
   else's results until the round is revealed. The strongest protection against
   chasing, but the room becomes a row of people working alone with a shared
   counter, which is a weak reason to be in the same room.

## Decision

Option 2. The first test you run is your own idea, not a reaction to the
leaderboard. After that, the room is fully open: you can see what others tried
and argue about it, which is the reason to be in a room together.

- The **trial count, the number of distinct rules, and the "luck bar"** are sent
  live to every open page, whether or not that visitor has run a test.
- **Other people's trials** (their rules and results) are shown, and sent live,
  only to visitors who have at least one trial in the current round. Your own
  trials are always visible to you.
- The server enforces this, not the page. The HTML, the JSON API and the event
  stream all apply the same rule, so hiding it in the browser is not where the
  protection lives.

## Consequences

- A newcomer sees a busy room they can't look into yet. The page has to say
  plainly why, and what unlocks it, or the hiding feels like a bug.
- It only protects the first test. After that, chasing is possible again; the
  deflated Sharpe ratio (ADR 0004) is what keeps later tests honest.
- Someone can open a second browser to peek without testing. The visitor is
  anonymous (ADR 0001), so this can't be prevented, only made pointless: the
  peek still doesn't change how much luck the room's results are discounted for.
- Checked in `spec/`: a fresh visitor gets no other visitor's trial from the
  page, the API or the event stream, and gets them after running one test.

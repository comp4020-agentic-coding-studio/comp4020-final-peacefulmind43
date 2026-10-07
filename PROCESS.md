# Process overview

This is the week 10 version. I rewrite it at each crit, so it describes the
project as it is now. The decisions are in [`doc/adr/`](doc/adr/), and the
rules I hold the agent to are in [`CLAUDE.md`](CLAUDE.md).

## From the brief to the room

The brief asks what would make the app good, and lets that decide what it
does. I first looked at a question board for lectures and dropped it: a marker
tests with two browser windows, and its main feature only shows with many
people. Then I looked for something useful to me. I hold SPMO, a momentum
fund. I cannot change which stocks it buys, only how much I hold and when. So
the room tests rules on top of a momentum portfolio, and it is multi-user for a
real reason: every test anyone runs makes a lucky result more likely, so the
room counts all of them.

## How I work with the agent

The same loop runs through every feature, and the commits show it:

1. **Decide first, in a record.** For each choice that is expensive to reverse,
   the agent lays out the options and what each costs, I choose, and the choice
   becomes an ADR. For the stack I used the week 8 method: the agent asked me
   one question at a time (what is a person, what persists, how a change
   travels) before suggesting anything
   ([`678ad85`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/678ad85)).
2. **Write the spec before the code, and see it fail.** Each feature starts
   with checks in `spec/` that are red against the running app:
   [`2e2d332`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/2e2d332),
   [`70c2905`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/70c2905),
   [`cfae098`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/cfae098),
   [`347b8e8`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/347b8e8).
3. **Never let the app check its own numbers.** `spec/model.ts` is a separate
   implementation of the rules and costs, written from the ADR in TypeScript,
   while the app is Python. The spec compares every published figure with it,
   and pins the deflated Sharpe formula to the paper's own worked example
   (0.9004).
4. **When the agent gets something wrong, fix the harness, not just the code.**

## Corrections that went into the harness

**Test trials in the real room.** The course setup says to run `pnpm check`
against the live URL. I did, and it put 10 permanent test trials into round 1,
because my own rule says trials can never be deleted. I wiped the database once
before launch, and `CLAUDE.md` now says never to point the spec at the live
app
([`38a4f9f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/38a4f9f)).

**A correct statistic that answered the wrong question.** For crit 9 I added
the deflated Sharpe ratio as the room's luck discount (ADR 0004). Every check
passed, and every rule scored 100%. The formula was right; the question was
wrong. It tested whether a rule beats cash, and any momentum rule over 89 years
does. What a holder needs to know is whether a rule adds anything beyond
holding more or less of the portfolio. ADR 0005 replaces the discount: regress
each timing rule on "always 1×" and deflate what is left
([`a9a262c`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/a9a262c),
[`0f1d9e7`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/0f1d9e7)).
After that, one rule's score went from 70% with 7 rules tried to 25% with 66,
which is the effect the room exists to show. The lesson is now a rule: run a
new figure over a spread of real rules and look at the spread before showing it
([`c46d5b8`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/c46d5b8)).
Passing tests did not catch this. Looking at the numbers did.

**A new surface that could leak.** When I added the activity log, a public log
of "who tested what" would have shown results to people who hadn't tested yet.
It was designed redacted from the start, and `CLAUDE.md` now says the room's
hiding rule covers every surface, including future ones
([`d40ed4d`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/d40ed4d)).

## The crit 9 decision

Crit 9 asks for one decision about several people at once. Mine is ADR 0003:
everyone sees the test count and the luck bar live, but other people's results
unlock only after your own first test in a round. Showing everything live is
the obvious choice and the liveliest, but it invites everyone to chase the
current best result, which speeds up the overfitting the README warns about.
Hiding everything until the reveal protects more, but leaves a row of people
working alone. The server applies the rule on the page, the API and the event
stream, and the spec checks all three as a newcomer. The cost is that a
newcomer sees a busy room they can't look into yet, so the page says why.

Real-time uses server-sent events from one process
([`28a2534`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/28a2534)),
because every update goes from server to browser (ADR 0001).

## What crit 8 changed

At crit 8 the room felt static, and I agreed. Running a backtest is a thing
one person does alone; the live count and luck bar only changed numbers on
other people's screens, never what they decided. The obvious fix was a bigger
change of topic, which would have thrown away the work and the reason the room
is useful to me. Instead I changed the core action. ADR 0008 asks each person
to back one rule before the reveal, from any rule the room has tried, with the
counts live and every pick scored at the reveal by what its rule added beyond
holding
([`b17a418`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b17a418),
[`766358a`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/766358a)).
Now there is a reason to read other people's rules: you might back one. I
judged picks on what a rule adds, not on growth, because growth would reward
whoever borrowed most in a rising market.

## Built ahead, on purpose

Two things are in place before the crits that need them. The activity log
(crit 10) is live before crit 9, so my pod's session is recorded: the log notes
whether each test was a visitor's first and whether they could already see
others' results, which is what ADR 0003's claim needs. And rounds now reveal on
a published schedule (ADR 0007,
[`51b4643`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/51b4643)):
the first full round reveals at 11:00 on the day of crit 9, during the session,
so the pod sees the locked years open together.

## Checking it the way a marker will

I went through the marker's checks before shipping
([`15f0043`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/15f0043)).
Using only the keyboard found a real bug: changing a rule's dropdown left the
radio on "always", so the test ran a different rule from the one chosen.
Coming back the next day found a gap: nothing pointed to the last revealed
round. Both are fixed. An axe check now runs on every page in `spec/`; I first
confirmed that axe catches known faults in jsdom, so a pass means something.

## The stack, in short

Python and FastAPI because the work is statistics and Python is what I can
review; SQLite on the Fly volume with numbered migrations run at start-up,
because the volume only exists on the running machine; plain server-rendered
HTML so `/readme/` and the room work without scripts. The trade-offs are in
ADR 0001. Each migration that changed what a trial means closes the open round
instead of mixing old and new results, because trials can never be edited.

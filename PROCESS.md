# Process overview

This is the week 9 version. I will rewrite it at each crit, so it always
describes the project as it is now.

## From the brief to an idea

The brief says to decide what makes the app good, and let that decide what it
does. I first looked at a live question board for lectures, where an LLM merges
questions that mean the same thing. I dropped it for two reasons. A marker tests
with two browser windows side by side, and merging only shows its value with
many people and many questions. Also, more people make a question board more
useful, but not more interesting, and the brief asks for the second.

I then looked for something that was useful to me. I hold SPMO, a momentum
fund, and I care about two questions: how much leverage to use, and whether any
rule on top of the fund really helps. The key change in my thinking was this: I
cannot change which stocks SPMO buys, but I can change how much I hold and when.
So the room tests rules on top of a momentum portfolio. To make it multi-user
in a real way, the room counts every test anyone runs, because many tests make
any single good result less believable.

## Choosing the stack

I used the method from the week 8 lecture: the agent asked me one question at a
time before it suggested a stack. A person is an anonymous browser. Tests are
kept forever, grouped into rounds. Updates only go from server to browser. From
those answers, I chose Python with FastAPI, SQLite on the Fly volume, and
server-sent events for real-time. The options I ruled out (Django, Phoenix
LiveView, Node) and why are in
[`doc/adr/0001`](doc/adr/0001-python-fastapi-sqlite-sse.md). The data choice
(Kenneth French momentum portfolios instead of SPMO prices or stock-level data)
is in [`doc/adr/0002`](doc/adr/0002-momentum-data-and-hold-out.md). Both were
committed, with the first rules in `CLAUDE.md`, before any app code:
[`678ad85`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/678ad85).

## Tests before the app

I wrote the checks before the app existed
([`2e2d332`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/2e2d332)).
They come straight from the README: tests are kept and shared, a test can never
be deleted or changed, no response contains a locked month, and the backtest
matches a separate calculation from the data file. For the numbers, I did not
trust the app to check itself. The test file recomputes every result from
`data/momentum.csv` on its own, and pins the arithmetic with a hand-checked
case (+10% then -10% is 0.99). The first working room
([`f13ec06`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f13ec06))
made all 12 checks pass, locally and on the deployed app. I also restarted the
Fly machine to confirm the tests were still there afterwards.

The rule "a test can never be deleted" is not only in the app code. SQLite
triggers refuse any update or delete on the trials table, so the rule holds
whatever code is written later.

## A correction that went into the harness

The course's setup guide says to run `pnpm check` against the live URL. I did,
and it added 10 test trials to the real room. Because trials can never be
deleted, my own rule meant the room's first round was already polluted. I wiped
the database once, before launch, and added a rule to `CLAUDE.md`: never run the
spec against the live app
([`38a4f9f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/38a4f9f)).
I put this in the harness, not just in my memory, because the next agent session
would make the same mistake.

## What is next

For week 10: real-time updates over server-sent events, and the group discount
(deflated Sharpe ratio) based on the number of tests in a round. Trading costs
also need to be added before the results mean much.

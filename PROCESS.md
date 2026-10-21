# Process overview

How the project got from the brief to the game, and how I worked with the
agent. The full record is in the [process log](doc/process-log.md),
decisions are in [doc/adr/](doc/adr/), and the rules I hold the agent to are
in [CLAUDE.md](CLAUDE.md).

## Why the project changed

Until crit 8 this was the Overlay Room, for testing rules on a momentum
portfolio. At crit 8 it felt static, and I agreed. Others could
change numbers on my screen, never what I did next.

In [7dc8bb4](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4)
I switched to a team game where people and bots play together. The
question became what
makes a bot a good teammate for people.

## The stack, and its costs

Python and FastAPI, with SQLite on the Fly volume. The board goes out by
server-sent events and choices come in by POST, all in one uvicorn process
(ADRs 0001, 0011). The trained bot runs in NumPy because the machine has
256 MB and PyTorch doesn't fit
([ec7237e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)).

I chose Python because the server and RL training share one engine. One process keeps live updates
simple, as every page reads the same memory. It can never run on two
machines. For a few friends that is fine.

With SSE plus POST, each choice is one request and one log line, so request
ids and access rules were easy to add later. A WebSocket would be faster
but needs its own rules for who sent what. NumPy serving costs an export
step, and CLAUDE.md wants a test that NumPy matches PyTorch before a bot
ships.

## How I worked with the agent

The agent wrote most of the code. I decided and checked, and kept five
habits.

The first was a decision record before any change that is hard to undo. The
agent wrote the options and costs, I chose, and it became an ADR.
Writing the server made me reread ADR 0011, and I fixed two holes before
any code depended on them
([39c9047](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/39c9047)).
A merged record is never edited. A new one replaces it, as ADR 0021 did
for a wrong sentence in ADR 0012
([f550ebc](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f550ebc)).

Each new bot also got a bar in its ADR before training. fcp1
passed and was deployed in
[8b01211](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8b01211).
team1 was meant to help its partners score more, and its bar went in first
([574235e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/574235e)).
It failed. It became a much stronger lone wolf, winning 97% against the
scripted bot, but it was no better as a teammate and far too strong for
people. I agreed not to deploy it
([06d4919](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/06d4919)).
Without the bar, 97% would have been easy to call a success.

Training runs took about eight hours, so they ran on worktree branches.
They came back as the merges
[452628d](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/452628d)
and [e5c5ff1](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e5c5ff1),
and both had process-log conflicts. Long jobs went to subagents, and I
read their reports.

I also played it myself. The first real-time
version ran at four moves a second. Every check passed, but I could not
keep up, so since
[feb9602](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602)
a turn waits for everyone, up to 2 seconds. When I played again, one key
press walked two steps
([b0baeab](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab)).
I asked for a pause button, and
[09d04d2](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/09d04d2)
lets anyone pause with no time limit and press again to carry on. Pressing it
did nothing. The browser had kept an old script, and the spec
could not see that because it never runs the page. Since
[1f83298](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1f83298)
scripts load by a hash of their contents.

Last, corrections went into the harness. When something
went wrong, the fix was a rule in CLAUDE.md or a test in spec/ or tests/,
not a new prompt.
After the spec once wrote test data into
the live app, CLAUDE.md forbids it
([38a4f9f](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/38a4f9f)).
A flaky test was two bugs, one in the app (arenas played matches
for nobody) and one in the test
([312363f](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f)).

Red's view was flipped but its action was not, so half
of each training batch taught the opposite of the other half. A new mirror
test fails without the fix in
[034a144](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/034a144),
and since [1d51c17](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1d51c17)
CLAUDE.md says the action is mirrored too.

## Checking against the code, not my memory

Before writing down who may see and change what, I had the code audited. It found two holes, and each got a spec test that failed
before the fix. A reload could lose your seat to a newcomer, fixed in
[ba7700a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba7700a).
A live match's choices could also be read before the turn ended
([e573e75](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e573e75)).

The same check against the week 10 lecture found three gaps. Pause
was a toggle, so two people pressing it at once cancelled out
([c7a2a6b](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/c7a2a6b)).
No request had an id until
[1b822aa](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1b822aa),
and the cookie lacked a Secure flag until
[8044a2a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8044a2a).

The README admitted that a person rarely wins against two fcp1 bots, so
since [f1d9635](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f1d9635) a team with no person gets a weaker bot, chosen
by testing a stand-in program on 400 unseen maps per opponent. Driving the
app in Chrome with two profiles found six problems, such as keys that did
nothing until you clicked the board, fixed in [f78d2f0](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f78d2f0).

A browser pass checks that the page works, not that a newcomer
understands it. At crit 11 a classmate said the game was hard to follow.
The rules were one long paragraph above the board, mixed with timing,
pause and bots. Now the game page opens with four short rules: which token
is you, how to score, who catches whom, and first to 3. The rest comes
after them. On a phone the board moves to the top, so the rules move up
with it. A spec test checks that the rules are short and come before the
board.

For the RL work I measured first. A profile showed 92% of the time in
path searches. Caching them in
[ec7237e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)
made training 13 times faster. One bot never scored.
I watched it, and it never left home, so I added a curriculum
instead of a new reward
([4f32a7b](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/4f32a7b)).
The one-page summary is in [doc/rl/README.md](doc/rl/README.md).

## Dropping the ratings

I first built a blind study where people rated "Bot A" or "Bot B". I
removed it in
[9b2534e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/9b2534e)
because ratings from a few short, casual sessions would be too noisy to
use. Now every bot is named, and behaviour is the evidence. Siu et al.
(2021) found people can prefer one of two bots with the same score, and I
can't see that.

## My position on small-scale good

Robin Sloan's
["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/) and
Clay Shirky's
["Situated Software"](https://shirky.com/essays/situated-software/) say
software for a few people can leave out what strangers at scale need.
That is why the game has no accounts, chat or ranking.

Nelson Elhage's
["Situated Social Software"](https://buttondown.com/nelhage/archive/situated-social-software/)
argues that small groups mostly use general tools, and my own crit backs
him up. At crit 9 my pod did not open each other's sites, and since then
one classmate's comment is most of my feedback, so I have little human
data. So I don't claim smallness itself is
the value.

The game page is the home-cooked part. The RL work is not. What this game adds is the question of a fair
bot teammate, and so far I have half an answer. fcp1 holds up next to
weak partners, but it still plays alone.

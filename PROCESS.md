# Process overview

How I got from the brief to the game. The daily record is the
[process log](doc/process-log.md), decisions are in [doc/adr/](doc/adr/),
and my rules for the agent are in [CLAUDE.md](CLAUDE.md).

## Why the project changed

Until crit 8 this was the Overlay Room, a place to test rules on a momentum
portfolio. At crit 8 people said it felt static, and I had to agree. Other
people could change numbers on my screen, but nothing they did changed what I
did next.

So in
[7dc8bb4](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4)
I started again with a team game where people and bots play together. The
new question interested me more anyway: what makes a bot a good teammate?

## The stack, and what it costs

The server is Python and FastAPI, with SQLite on the Fly volume. The board
goes out by server-sent events and moves come in by POST, all in one uvicorn
process (ADRs 0001, 0011).

I picked Python so the server and RL training share one engine. One process keeps
live updates simple. The cost is
that it can never run on two machines. For a few friends, I can live with
that.

I chose SSE plus POST over a WebSocket. Each move is one request and one log
line, so adding request ids and access rules later was easy. A WebSocket
would be faster, but it needs its own rules for who sent what.

The trained bot runs in NumPy, not PyTorch, because the Fly machine has 256
MB and PyTorch does not fit
([ec7237e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)).
That costs an export step, so CLAUDE.md asks for a test that NumPy and
PyTorch agree before any bot ships.

## How I worked with the agent

The agent wrote most of the code. I decided and checked, with four habits.

Decide on paper first. Before any change that is hard to undo, the agent
wrote out the options and their costs, I picked one, and it became an ADR.
Writing the server made me reread ADR 0011, and I found two holes before
any code depended on them
([39c9047](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/39c9047)).
I never edit a merged ADR. A new one replaces it, as ADR 0021 did for a
wrong sentence in ADR 0012
([f550ebc](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f550ebc)).

Set the bar before training. Each new bot got a pass mark in its ADR
before it trained. fcp1 passed and went live in
[8b01211](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8b01211).
team1 was meant to help its partners score more, and I wrote that bar first
([574235e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/574235e)).
It failed: it won 97% against the scripted bot, but as a lone wolf, no
better as a teammate and far too strong for people. I did not deploy it
([06d4919](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/06d4919)).
Without the bar I think I would have called 97% a win.

Training took about eight hours a run, so it ran on worktree branches and
came back as merges
([452628d](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/452628d),
[e5c5ff1](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e5c5ff1)).

Play it myself. The first real-time version ran at four moves a second.
Every check passed, but I could not keep up with the bots. Since
[feb9602](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602)
a turn waits for everyone, up to 2 seconds. When I played again, one key
press walked two steps
([b0baeab](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab)).
Then I asked for a pause button
([09d04d2](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/09d04d2)),
and pressing it did nothing. The browser had kept an old script, and the spec
could not see that because it never runs the page. Since
[1f83298](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1f83298)
scripts load by a content hash. After that, a green test only told me about
the layer it tests.

Fix the harness, not the prompt. When the agent got something wrong, the
fix went into CLAUDE.md or a test, so it stayed fixed. After the
spec once wrote test data into the live app, CLAUDE.md forbids it
([38a4f9f](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/38a4f9f)).
A flaky test turned out to be two bugs, one in the app (arenas played matches
for nobody) and one in the test
([312363f](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f)).
The worst was in training: red's view was flipped but its action was not, so half of every batch taught the opposite of the other
half. A mirror test now fails without the fix
([034a144](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/034a144)),
and CLAUDE.md says the action is mirrored too
([1d51c17](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1d51c17)).

## Checking against the code, not my memory

Before I wrote down who may see and change what, I had the code audited
against each rule. It found two holes, and each got a test that failed
before the fix. A reload could give your seat to a newcomer
([ba7700a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba7700a)),
and a live match's moves could be read before the turn ended
([e573e75](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e573e75)).
A second pass against the week 10 lecture found three more. Pause was a
toggle, so two people pressing at once cancelled out
([c7a2a6b](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/c7a2a6b)).
Requests had no id
([1b822aa](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1b822aa)),
and the cookie was not Secure
([8044a2a](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8044a2a)).

My README admitted a person rarely beats two fcp1 bots. So since
[f1d9635](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f1d9635)
an all-bot team facing a person gets a weaker bot, chosen with a stand-in
player on 400 unseen maps. Chrome with two profiles found six more
problems, like arrow keys that needed a click first
([f78d2f0](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f78d2f0)).

None of this tells me whether a newcomer understands the game. At crit 11 a
classmate said it was hard to follow, and they were right. Since
[d0b86fc](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/d0b86fc)
the page opens with four short rules, also on a phone, and a test keeps them
short and above the board.

For RL I measured before guessing. Path searches took 92% of the
time, and caching them made training 13 times faster
([ec7237e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)).
One bot never scored. I watched it, saw it never left home, and added a
curriculum instead of a new reward
([4f32a7b](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/4f32a7b)).
The summary is in [doc/rl/README.md](doc/rl/README.md).

## Dropping the ratings

I first built a blind study where people rated "Bot A" or "Bot B". I removed
it in
[9b2534e](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/9b2534e),
because a few short, casual sessions would give ratings too noisy to use. Every
bot is named and judged by behaviour, though Siu et al. (2021) found people
can prefer one of two equally scored bots. I accept that gap.

## Where I stand

Robin Sloan's
["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/) and
Clay Shirky's
["Situated Software"](https://shirky.com/essays/situated-software/) convinced
me that software for a few people can skip what strangers at scale need.
That is why there are no accounts, chat or rankings. But Nelson Elhage's
["Situated Social Software"](https://buttondown.com/nelhage/archive/situated-social-software/)
says small groups mostly use general tools, and my crit backs him up: at crit
9 my pod did not open each other's sites. So I don't claim being small is
the value. The game page is the home-cooked part. What the project really
adds is the question of a fair bot teammate, and I have about half an
answer. fcp1 holds up next to weak partners, but it still plays alone.

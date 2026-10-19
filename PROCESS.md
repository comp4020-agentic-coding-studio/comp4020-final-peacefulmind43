# Process overview

How this project got from the brief to the game, and how I worked with the
agent. The full record is
[`doc/process-log.md`](doc/process-log.md). Decisions are in
[`doc/adr/`](doc/adr/), and the rules I hold the agent to are in
[`CLAUDE.md`](CLAUDE.md).

## Why the project changed

Until crit 8 this was the Overlay Room, a room for testing rules on a
momentum portfolio. At crit 8 it felt static, and I agreed. Other people only
changed numbers on my screen, never what I did next. So I changed to a team
game where people and bots play together
([`7dc8bb4`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4)).
I also wanted a game RL project to show for internships. The question became:
what makes a bot a good teammate for people?

## The stack, and its costs

Python and FastAPI, SQLite on the Fly volume, server-sent events for the board
and POST requests for choices, all in one uvicorn process (ADRs 0001,
0011). The trained bot runs in NumPy, because the machine has 256 MB and can't
hold PyTorch
([`ec7237e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)).

Python, because the server and RL training share one engine, and I review
it best. One process keeps live updates
simple: every page reads the same memory. The cost: it can never run on two
machines, which is fine for a few friends. SSE plus POST
means each choice is one request with one log line, which made
request ids and access rules easy to add later. A WebSocket would be
faster but needs its own rules for who sent what. NumPy serving costs
an export step and a test, required by `CLAUDE.md`, that NumPy matches
PyTorch before a bot ships.

## How I worked with the agent

The agent wrote most of the code. I decided, directed and checked, with five
habits.

**A decision record before a change.** For each hard-to-undo choice, the
agent wrote the options and costs, I chose, and it became an ADR. Writing
the server made me reread ADR 0011, and I fixed two holes before any
code depended on them
([`39c9047`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/39c9047)).
A merged record is never edited; a new one supersedes it, like ADR 0021 for a
wrong sentence in ADR 0012
([`f550ebc`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/f550ebc)).

**A bar written before training.** Each new bot's ADR sets its bar before
the run starts. fcp1 passed and is deployed
([`8b01211`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8b01211)).
team1 was meant to let its partners score more. Its bar was written first
([`574235e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/574235e)),
and it failed: it became a much stronger lone wolf, winning 97% against the
scripted bot. I agreed not to deploy it: it is far too
strong for people and no better as a teammate
([`06d4919`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/06d4919)).
Without the bar, 97% would have been easy to call a success.

**Subagents and worktrees for long work.** Training runs take about eight
hours, so they ran on branches in worktrees while `main` moved on, and
came back as merges
([`452628d`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/452628d),
[`e5c5ff1`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e5c5ff1)).
Long or parallel jobs, like checking my reading list's sources, went to
subagents, and I read their reports. The cost: both merges conflicted in the
process log.

**Playing it myself.** The first real-time version ran at four moves a
second. Every check passed, but I could not keep up with the bots. So turns
now wait for everyone, up to 2 seconds
([`feb9602`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602)).
Playing again, I found one key press walked two steps
([`b0baeab`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab)).
I asked for a pause button: anyone can pause, with no time limit, and press
again to carry on
([`09d04d2`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/09d04d2)).
Pressing it did nothing. The browser kept an old script, which the spec
could not see because it never runs the page. Scripts now load by a
hash of their contents
([`1f83298`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1f83298)).

**Corrections go into the harness.** When something went wrong, the fix was a
rule in `CLAUDE.md` or a test in `spec/` or `tests/`, not a new prompt. After
the spec once wrote test data into the live app, `CLAUDE.md` forbids it
([`38a4f9f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/38a4f9f)).
A flaky test was really two bugs, one in the app (arenas played matches for
nobody) and one in the test
([`312363f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f)).
Red's view was flipped but its action was not, so half of each training batch
taught the opposite of the other half. A new mirror test fails without the
fix, and `CLAUDE.md` now says the action is mirrored too
([`034a144`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/034a144),
[`1d51c17`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1d51c17)).
When CI's secret scan blocked a deploy over a pytest name, I checked the whole
history, then turned off only that detector
([`1f08f53`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1f08f53)).

## Checking against the code, not my memory

Before I wrote down who may see and change what, I had the code audited
against each rule. Two holes came out, each with a spec test that failed
before the fix: a reload could lose your seat to a newcomer
([`ba7700a`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba7700a)),
and a live match's choices could be read before the turn ended
([`e573e75`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e573e75)).
I did the same with the week 10 lecture and found three gaps. Pause was a
toggle, so two people pressing it at once cancelled out
([`c7a2a6b`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/c7a2a6b)).
No request had an id
([`1b822aa`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1b822aa)).
The cookie had no Secure flag
([`8044a2a`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8044a2a)).

The RL work followed the same idea: measure first. A profile showed 92% of
the time in path searches, and caching them made training 13 times faster
with the same results
([`ec7237e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e)).
When a bot never scored, I watched it: it never left home, so the fix
was a curriculum, not a new reward
([`4f32a7b`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/4f32a7b)).
The one-page summary is [`doc/rl/README.md`](doc/rl/README.md).

## Dropping the ratings

I first built a blind study where people rated "Bot A" or "Bot B", then
removed it
([`9b2534e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/9b2534e)).
Ratings from a few short, casual sessions would be too noisy to use.
Now every bot is named, and behaviour is the evidence. The cost: Siu et al.
(2021) found people can prefer one of two bots with the same score, and I
can't see that.

## My position on small-scale good

Robin Sloan's
["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/) and
Clay Shirky's
["Situated Software"](https://shirky.com/essays/situated-software/) say that
software for a few people can drop what strangers at scale need. That is why
there are no accounts, no chat and no ranking. But Nelson Elhage's
["Situated Social Software"](https://buttondown.com/nelhage/archive/situated-social-software/)
argues that small groups mostly use general tools. My own crit
supports him: at crit 9 my pod did not open each other's sites, so I have no
pod feedback and little human data. So I don't claim smallness itself is
the value. The game page is the
home-cooked part. The RL work is not; it is my research and portfolio piece.
What this game adds is the question of a fair bot teammate, and so far the
answer is only half there: fcp1 holds up beside weak partners, but it still
plays alone.

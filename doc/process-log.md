# Process log

A running record, newest last. Each entry says what happened, why, and where
the evidence is. `PROCESS.md` is rewritten from this log at each crit; this
file only grows.

Commit links point at
`https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/<hash>`.

## Before the change of topic (to crit 8)

The Overlay Room (a room for testing rules on a momentum portfolio) shipped for
crit 8 and grew through crit 9 work: ADRs 0001–0008, a test-first spec, and
three corrections that went into the harness (test trials in the live room, a
statistic that answered the wrong question, a new surface that could leak).
Those records stay in `doc/adr/` and the history.

## 2026-10-07: crit 8 says the room is static

At crit 8 the room felt static, and I agreed: its core action, running a
backtest, is something one person does alone. I first kept the topic and made
backing a rule the core (ADR 0008,
[`b17a418`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b17a418)),
but the interaction stayed slow and indirect.

## 2026-10-08: change to capture the flag

Decision: a real-time team game where people act on each other directly, with
bots filling empty seats; the question is what makes a bot a good teammate
(ADR 0009). I also wanted the project to show reinforcement learning for games.
Before anything else, `main` got the finished Overlay Room v2 as a working
fallback for crit 9.

- Chose the game from a long list by asking two things of each: is it more
  interesting with other people, and does it give an RL agent something real to
  learn? Grid capture the flag won over Bomberman-style for simpler rules, a
  clearer teamwork story and easier training.
- Rules decided one by one before code (ADR 0010):
  [`7dc8bb4`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4).
  Random mirror-symmetric maps from a seed, so a bot can't memorise one layout
  and can be tested on maps it never saw.
- The crit 9 decision (ADR 0011): someone arriving mid-match takes over a bot's
  seat at once, instead of watching until the next match:
  [`332105c`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/332105c).

## 2026-10-08: an engine that can't disagree with itself

- The engine is a pure function of state and actions, with a seeded generator I
  wrote myself (mulberry32) so another language can reproduce it, and a test
  for every rule:
  [`a455960`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/a455960).
- A second engine, written separately in TypeScript from the same ADR, checks
  the Python one tick by tick through an API. I broke the TypeScript one on
  purpose (respawn 8 → 9) to make sure the check fails, and it failed at tick 11
  naming the exact field:
  [`afa57ba`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/afa57ba).
- Removed the Overlay Room from the current tree in one commit:
  [`51b82a3`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/51b82a3).

## 2026-10-09: two holes in ADR 0011, found before building

Writing the server made me reread ADR 0011, and two parts were wrong:
[`39c9047`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/39c9047).

- "No input for 5 seconds means you left" is wrong: guarding means standing
  still, and a held key sends one request. Now a closed page is covered after
  5 s and an idle open page after 60 s.
- "Open a second arena when the seats are full" meant five or six people could
  never play one match. Now they wait on the bench and the next match grows to
  3v3.

## 2026-10-09: bots playing bots found broken rules

Before any training, I had the scripted bots play each other on many maps:
[`86d8836`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/86d8836).

1. 80 games out of 80 were 0–0. A defender standing on its own flag could
   never be beaten, because the attacker has to step on that cell, on the
   defenders' half. People would find this too, and an RL agent would learn
   nothing else. Rule change: a team's own flag cell is a wall to it.
2. Still 0–0: two mirror-image bots waited for each other at the middle line
   forever. Fix in the bots: one random move in ten, seeded by the match so it
   replays.
3. Blue then won far more often. I mirrored every direction-dependent choice in
   the bots and still saw it, so I checked the engine directly: a whole game
   flipped left-right with the teams swapped mirrors the original at every tick
   (60 games). The cause was my test: the bots' random moves were seeded the
   same in every game, so 80 games were not 80 samples. The mirror check is now
   a permanent test.
4. With defence working, carriers were almost always caught (0.57 captures a
   game, 72% draws). I made the carrier slowdown a parameter and compared four
   values over 120 games each; skipping 1 turn in 4 gave about 2 captures a
   game, 71% decided, even between teams. That is rules version 2.

## 2026-10-09: the arena, and what the spec caught

- The arena server, built to the spec written first:
  [`a5925cb`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/a5925cb)
  (spec, red) then
  [`8741762`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8741762)
  (green). Bots get only the game state, so they can't see people's inputs by
  construction.
- A check that every saved match had a person in it failed: a private arena
  kept starting matches after everyone left, and the shared arena would have
  saved bot-only matches all day. Arenas now wait for someone and go idle when
  a match ends with nobody there:
  [`312363f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f).
- A flaky test was two problems: bots playing in an empty arena (fixed above),
  and a test that pressed four directions at once so only the last counted,
  sometimes into a wall. The test now holds a direction it can actually move
  in.

## 2026-10-09: playing it myself changed the game

At four moves a second I couldn't keep up with the bots. The rules were fair;
the clock wasn't: a bot decides instantly and a person is always behind. That
breaks the README's promise of a fair teammate. ADR 0012 makes turns wait for
people, up to 2 seconds; alone, you play at your own pace. Matches cap at 500
turns (rules version 3) after comparing 300, 400, 500 and 720 in bot games:
[`feb9602`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602).

The spec found two bugs in the change: a person who had closed the page was
still waited for every turn, and an arena with nobody able to choose treated
"everyone has chosen" as true (an empty set) and raced through its match in
seconds.

Playing again found one more the spec couldn't: one key press walked two
steps. A solo turn resolves in 0.15 s, shorter than a normal key press, so the
page took the press for holding. A press now counts as holding only after
350 ms, like a keyboard's own repeat delay:
[`b0baeab`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab).
Tests show the system follows its rules; only playing it shows whether it is
pleasant to use.

## 2026-10-09: a countdown for every turn

While playing I asked for a visible countdown to the next move, to a tenth of a
second, with a bar. It counts from when the turn's board arrived in the
browser, not from the server's clock, so the two clocks never need to agree.
It is hidden from screen readers; the slower status line still speaks.

## 2026-10-09: designing the RL bot (ADR 0013)

Before any training code, three decisions, each with the alternatives written
down:

- **What the bot sees:** the whole map, padded to the largest size and flipped
  so every bot attacks to the right. A window around itself would fit any map
  but hide what teammates are doing, which is what teamwork is made of, and
  would see less than a person does.
- **What it's rewarded for:** +1/−1 to the whole team per capture, plus
  potential-based shaping towards the current objective that fades to nothing
  over the first half of training. Shaping of that form can't be farmed
  (walking there and back earns exactly zero), unlike rewards for events such
  as picking up the flag. Team rewards, because rewarding whoever scores
  teaches a bot to take the glory instead of helping.
- **How it trains:** PPO, one network shared by every seat, against the
  scripted bots until crit 9, evaluated on maps it never trained on.

The observation lives in one file used by both training and the server. Its
key test: in a game and its mirror image (flipped left to right, teams
swapped), each blue player sees exactly what the matching red player sees, at
every turn. That is what lets one network play both sides.

## 2026-10-09: the training pipeline, and two things it taught me

- **Profile before optimising.** The first environment ran 2,400 samples a
  second. A profile showed 92% of the time in shortest-path searches (the
  shaping potential and the scripted opponents), and most searches had the
  same map, team and target all match long. Caching them made it 13 times
  faster, and 120 scripted games gave exactly the same results as before, so
  behaviour didn't change. Then the network update on the CPU was the
  bottleneck; it runs on the M2's GPU now (5 times faster for a batch), while
  rollouts stay on the CPU where small batches are quicker.
- **NumPy agrees with PyTorch** to about 5e-10 on the policy logits, checked
  before any training, so the server will run the same bot that was trained.
- **The first runs learned to defend and never to score.** Entropy fell and
  losses dropped from 99% to 69%, but captures stayed at zero. The shaping
  potential was minus the distance to the current objective, which jumps when
  the objective changes: picking up the flag dropped it by about half the map,
  an immediate penalty for the one move the bot most needed to learn. Shaping
  of this form can't change the best policy in theory, but in practice a bot
  that almost never got home only ever saw the penalty. The potential is now
  minus the whole path still to walk before scoring, which doesn't change at
  all when the flag is picked up.

## 2026-10-10: the bot learned to never leave home

With the shaping fixed, a 4M-sample run still never scored. Before changing
anything I watched the exported bot play 40 games on unseen maps: its players
spent 100% of their turns on their own half and never came within 3 cells of
the enemy flag, while tagging 3.5 scripted attackers a game. It had found a
local optimum. Early on, every crossing of the middle line met a full scripted
defender, was caught and sent home, so it learned not to cross, and then never
explored far enough to find that a capture is worth +1. This was an
exploration problem, not a reward bug.

Fix: an adaptive curriculum. Opponents play their scripted move with
probability `level`, otherwise a random one; level starts at 0 (wandering
opponents that barely defend) and rises by 0.1 each time the bot wins 70% of
its last 100 games at that level, up to the full scripted bot. Self-play was
the alternative, but two learners can settle into both defending, and it gives
no fixed yardstick; it comes later, once the bot can attack.

Also found: the run took 96 minutes instead of about 15, because the cumulative
speed collapsed mid-run; the Mac had slowed or slept the background process.
Training now runs under `caffeinate -i`.

`rl/eval.py` measures a bot the way the server runs it (the exported NumPy
file) against the full scripted bot on maps it never trained on, alternating
sides and team sizes, with 95% Wilson intervals and a scripted-vs-scripted
baseline on the same maps.

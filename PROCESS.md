# Process overview

How this project went from the brief to the game, the harness and the way I
worked with the agent. This file is kept up to date as the project moves, and
always describes it as it is now. The full step-by-step record, with every
commit, is in [`doc/process-log.md`](doc/process-log.md); decisions are in
[`doc/adr/`](doc/adr/); the rules I hold the agent to are in
[`CLAUDE.md`](CLAUDE.md).

## From a static room to a team game

Until crit 8 this was the Overlay Room: friends testing rules on a momentum
stock portfolio, with every test counted against the room. At crit 8 it felt
static, and I agreed. Running a backtest is something one person does alone;
other people only changed numbers on your screen, never what you did next.
Making "back one rule" the core (ADR 0008) helped, but the interaction stayed
slow and indirect.

So I changed the topic (ADR 0009): a capture-the-flag game on a small grid,
where people act on each other directly and bots fill empty seats, so a game
can always start. The question the project argues is what makes a bot a good
teammate for people. I also wanted the project to show reinforcement learning
for games. I chose the game from a long list by asking two things of each: is
it more interesting with other people, and does it give an RL agent something
real to learn?

## How I work with the agent

The same loop runs through the project:

1. **Decide first, in a record.** For each choice that is expensive to reverse,
   the agent lays out options and costs, I choose, and it becomes an ADR. The
   rules were fixed one question at a time before any code (ADR 0010,
   [`7dc8bb4`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4)).
2. **Spec first, and see it fail.** The arena spec was red before the server
   existed
   ([`a5925cb`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/a5925cb),
   then
   [`8741762`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8741762)).
3. **The app never checks its own numbers.** A second engine, written
   separately in TypeScript from the same ADR, checks the Python engine tick by
   tick. I broke it on purpose once to make sure the check fails, and it named
   the exact field at tick 11
   ([`afa57ba`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/afa57ba)).
4. **Try it before trusting it**, with bots playing bots and with me playing.
5. **When something is wrong, fix the cause where it lives**: the rules, the
   record, or the harness, not just the symptom.

## What testing the design found

**Bots playing bots found broken rules** before any training
([`86d8836`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/86d8836)).
In 80 games out of 80 the score was 0–0: a defender standing on its own flag
could never be beaten, because the attacker had to step onto that cell, on the
defenders' half. People would find this too, and an RL agent would learn it
first and nothing else. A team's own flag cell is now a wall to it. With
defence working, carriers were almost always caught (0.57 captures a game), so
I made the carrier slowdown a parameter and compared four values over 120
games each; one skipped turn in four gave about two captures a game and
balanced teams.

**One balance result was the test's fault, not the game's.** Blue seemed to win
far more often. Before changing anything I checked the engine directly: a whole
game mirrored left to right, with the teams swapped, matched the original at
every tick. The real cause was that my bots' random moves were seeded the same
in every game, so 80 games were not 80 samples. The mirror check is now a
permanent test.

**Rereading my own record found two holes** before I built on it
([`39c9047`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/39c9047)):
"no input for 5 seconds means you left" would hand a guarding player's seat to
a bot, and a full arena opening a second one meant six friends could never play
together.

**Playing it myself changed the game** (ADR 0012,
[`feb9602`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602)).
At four moves a second I couldn't keep up with the bots. The rules were fair;
the clock wasn't, since a bot decides instantly. That broke the promise of a
fair teammate, so turns now wait for every person present, up to 2 seconds.
Alone, you play at your own pace. Playing again found a bug no test could: one
key press walked two steps, because a solo turn resolves faster than a normal
key press
([`b0baeab`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab)).

**The spec caught real bugs too**: arenas playing matches for nobody
([`312363f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f)),
and, after the turn change, an arena with nobody able to choose treating
"everyone has chosen" as true and racing through its match in seconds.

## Training the bot

The RL bot (ADR 0013) sees the whole map from its own side, is rewarded as a
team, and gets potential-based shaping that can't be farmed and fades out. It
trains with PPO against the scripted bots. Three things taught me the most
([`ec7237e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e),
[`4f32a7b`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/4f32a7b),
[`034a144`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/034a144)):

- **Profile before optimising.** 92% of the environment's time was
  shortest-path searches with the same targets all match; caching them made it
  13 times faster with identical bot results.
- **Watch the bot, not just the score.** An early bot never scored. Playing it
  showed its players spent 100% of their turns at home: every early crossing
  met a full defender, so it learned not to cross. An adaptive curriculum now
  starts opponents wandering and strengthens them as the bot wins.
- **A flipped view needs a flipped action.** Red sees the map mirrored, but its
  chosen move was applied unmirrored, so half of every batch taught the
  opposite of the other half. The mirror test had only checked what each side
  sees; a new one checks what the same choice means for each. I also designed
  one diagnostic badly (still opponents turned out to wall in their own flag)
  and said so in the log rather than trusting it.

## The stack, and why

Python and FastAPI, because the game and the RL work share one engine and
Python is what I can review; SQLite on the Fly volume, with numbered
migrations run at start-up; server-sent events for state and plain POST
requests for choices (ADR 0011, 0012). The server decides everything, and bots
choose from the board everyone was shown, so they can't see people's choices
by construction. The trade-offs are in ADRs 0001, 0011 and 0012.

## What comes next

Finishing training, evaluating on unseen maps over several seeds, deploying the
bot beside the scripted ones, and measuring whether people find it a better
teammate.

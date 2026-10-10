# Process overview

How this project went from the brief to the game, the harness and the way I
worked with the agent. This file always describes the project as it is now.
The full step-by-step record, with every commit, is in
[`doc/process-log.md`](doc/process-log.md); decisions are in
[`doc/adr/`](doc/adr/); the rules I hold the agent to are in
[`CLAUDE.md`](CLAUDE.md).

## From a static room to a team game

Until crit 8 this was the Overlay Room: friends testing rules on a momentum
stock portfolio. At crit 8 it felt static, and I agreed. Running a backtest is
something one person does alone; other people only changed numbers on your
screen, never what you did next.

So I changed the topic (ADR 0009): a capture-the-flag game on a small grid,
where people act on each other directly and bots fill empty seats, so a game
can always start. The question the project argues is what makes a bot a good
teammate for people. I chose the game by asking two things of each idea: is it
more interesting with other people, and does it give an RL agent something
real to learn?

## How I work with the agent

1. **Decide first, in a record.** For each choice that is expensive to reverse,
   the agent lays out options and costs, I choose, and it becomes an ADR. The
   rules were fixed one question at a time before any code (ADR 0010,
   [`7dc8bb4`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/7dc8bb4)).
2. **Spec first, and see it fail.** The arena spec was red before the server
   existed ([`a5925cb`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/a5925cb), then [`8741762`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/8741762)).
3. **The app never checks its own numbers.** A second engine, written
   separately in TypeScript, checks the Python engine tick by tick. I broke it
   on purpose once, and the check named the exact field at tick 11
   ([`afa57ba`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/afa57ba)).
4. **Try it before trusting it**, with bots playing bots and with me playing.
5. **When something is wrong, fix the cause where it lives**: the rules, the
   record, or the harness, not just the symptom.

## What testing the design found

**Bots playing bots found broken rules** before any training ([`86d8836`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/86d8836)).
In 80 games out of 80 the score was 0–0: a defender standing on its own flag
could never be beaten. A team's own flag cell is now a wall to it. Then
carriers were almost always caught, so I compared four carrier slowdowns over
120 games each and kept the one that gave about two captures a game.

**One balance result was the test's fault.** Blue seemed to win far more
often. A whole game mirrored left to right matched the original at every tick;
the real cause was that my bots' random moves were seeded the same in every
game. The mirror check is now a permanent test.

**Playing it myself changed the game** (ADR 0012, [`feb9602`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/feb9602)). At four
moves a second I couldn't keep up with the bots, which decide instantly. That
broke the promise of a fair teammate, so turns now wait for every person
present, up to 2 seconds. Playing again found a bug no test could: one key
press walked two steps ([`b0baeab`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/b0baeab)).

**The spec caught real bugs too**, such as arenas playing matches for nobody
([`312363f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/312363f)).

## Training the bot

The RL bot (ADR 0013) sees the whole map from its own side, is rewarded as a
team, and trains with PPO against the scripted bots. Three lessons
([`ec7237e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ec7237e), [`4f32a7b`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/4f32a7b), [`034a144`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/034a144)):

- **Profile before optimising.** 92% of the environment's time was repeated shortest-path
  searches; caching them made it 13 times faster with identical results.
- **Watch the bot, not just the score.** An early bot never scored. Watching
  it showed it never left home, because every early crossing met a full
  defender. An adaptive curriculum now starts opponents wandering and makes
  them stronger as the bot wins.
- **A flipped view needs a flipped action.** Red sees the map mirrored, but its
  move was applied unmirrored, so half of every batch taught the opposite of
  the other half. A new test checks what the same choice means for each side.

## Many people, one match: who may change what

Several people act on one match at once, so the server decides who may do what
(ADR 0016). People are an anonymous cookie with a public label ("Visitor
ab12cd"): no sign-up, but a new browser is a new person. The server finds your
seat from your cookie, so a request can't move anyone else's player. Each rule
has a spec check, and auditing the code against them found two holes: a
reload in a full match could lose you your seat to a newcomer
([`ba7700a`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba7700a)), and a live match's choices could be read before the turn
resolved ([`e573e75`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e573e75)). A pause button anyone seated can press (ADR 0015,
[`09d04d2`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/09d04d2)) came from asking what a group of friends needs while playing.

## Logs a narrator can read

Every action is one JSON line on stdout with who, which arena, match and seat,
and a plain sentence; the activity log and every finished match's replay are
kept in the database (ADR 0014). Reading the real lines for the crit 10 demo
showed bots named as "a new visitor" and no line for closing the page, so I
fixed them ([`378b5a1`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/378b5a1)), and the page now tells each person their label
([`e45222e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e45222e)). [`doc/reading-the-logs.md`](doc/reading-the-logs.md) says how
to read them. One bug no spec could see: the pause button did nothing because
the browser kept an old script. Scripts now load by a hash of their contents
([`1f83298`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1f83298)).

## The stack, and why

Python and FastAPI, because the game and the RL work share one engine and
Python is what I can review; SQLite on the Fly volume, with numbered
migrations; server-sent events for state and plain POST requests for choices
(ADRs 0001, 0011, 0012). The server decides everything, and bots choose from
the board everyone was shown, so they can't see people's choices.

## What comes next

The bot now fills every empty seat: on 400 unseen maps it beats the scripted
bot 48% of the time and loses 6% ([`65adbcc`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/65adbcc)). Beating a program is not
being a good teammate for people, so the next step is measuring that with real
players, starting at the crit, from the logs and replays above.

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

## 2026-10-10: a flipped view needs a flipped action

The curriculum run was learning too slowly: after 2M samples, against
opponents that only wandered, it won 3% of games. Watching a checkpoint showed
a faint preference for moving east (24% against 14% west) and otherwise near
random play. The cause was mine: the observation flips red's view so every bot
attacks to the right, but the network's action was applied to the board
unflipped. For red, "towards the enemy" moved it home. Half of every batch
taught the opposite of the other half.

The observation's mirror test had passed, because it only checked what the two
sides see, not what the same output means for each. `to_engine` in
`app/game/obs.py` now turns red's actions back, used by training and the
server alike, and a new test plays a game and its mirror with any policy of the
view and checks they stay mirrored. Removing the fix makes that test fail. I
stopped the run, since it was learning a contradiction, and restarted it.

## 2026-10-10: the README argues for the game

Rewrote README.md for capture the flag (597 words). Its "good" is about the
people at the table: a game can always start; bots are fair (same board, same
rules, never seeing choices); bots win by choosing, not by speed (the
turn-based change); a bot is a teammate, not the star (team reward); and every
bot seat says which bot it is. Each claim is either checked by a named test or
left to people to judge, and the sources are the human-AI teamwork work the
design leans on: Jaderberg et al. 2019, Carroll et al. 2019, Strouse et al.
2021, and Ng et al. 1999 for the shaping.

## 2026-10-10: a diagnostic that was wrong, and what it showed

The run with the action fix learned to attack (45% of its moves towards the
enemy, reaching the flag in almost every game) but not to bring the flag home:
holding it, it still moved towards the enemy more than towards home, and was
caught on every carry. Mid-run it also slid back towards random play.

To tell a pipeline bug from a hard problem, I trained against opponents that
never move, expecting an easy win. It scored nothing in 1M samples, which by my
own test meant a bug. But the main run was starting to win at the same time,
so I checked the diagnostic instead: opponents spawn on three sides of their
flag, so standing still they wall it in, and the shaping (shortest paths that
ignore players) kept pointing through them. Still opponents were a fortress,
harder than moving ones. The diagnostic was wrong, not the pipeline, and I
removed it rather than leave a misleading option in the trainer.

## 2026-10-10: the first bot that learned, and what it can't do yet

With the action fix and the curriculum, the 10M-sample run learned to attack
and bring the flag home: against wandering opponents it went from 3% wins to
70%, the curriculum stepped up twice (to level 0.2), and it kept its play after
the shaping faded to zero, so the attack wasn't propped up by shaping.

Evaluated the way the server would run it, on 400 unseen maps against the
full scripted bot, it lost every game 0–3 (scripted against itself on the same
maps: 29% / 43% / 28%, so the test is fair). It never defends, because its
opponents so far almost never attacked, and its attack can't get past a
defender that chases. It learned exactly the level it trained at. Training
continues from these weights at level 0.2 (30M samples, no shaping). A bot
that only charges would be the opposite of the teammate the README promises,
so it isn't deployed until it plays close to the scripted bot.

## 2026-10-10: a place to watch the trained bot

Since the trained bot isn't good enough to be anyone's teammate yet, people
can watch it instead: `/?watch` opens a bots-only arena where blue is the
trained bot on show and red the scripted bot. Nobody sits, it only runs while
someone is watching, and its matches aren't saved, so the promise that every
saved match had a person in it still holds. Each team can now have its own
bot, and the bot on show (`watch.txt`) is separate from the one that fills
people's seats (`current.txt`, none yet), so a bot can be shown honestly
before it is trusted with a seat.

## 2026-10-10: every choice logged, every match replayable (ADR 0014)

Each choice is one JSON line on stdout as its request arrives (who by public
label, what, when, which match and turn) and is written to its own table in
batches from a thread, never inside a turn. Tags, pickups and captures join
the activity log, so `/log` tells a match's story. Each finished match saves a
replay: seed, team size, rules version and every turn's actions. The spec
replays a match through the independent TypeScript engine and gets the
server's score and state hash.

The spec also showed a race I had built in on purpose: matches are saved in a
thread so a slow disk never delays a turn, so a replay fetched the instant a
match ends may not exist yet. The tests now wait for it rather than the server
saving synchronously; an older test had the same race and had only been lucky.

## 2026-10-10: judging a plateau too early

The continuation run sat at level 0.2 for 4M samples, winning 60–62% against a
70% threshold, so I stopped it to lower the threshold. The level-up event
arrived seconds later: it had just reached 70%. I had called a plateau too
soon. Checkpoints every 25 updates meant almost nothing was lost, and the
run continues from there at level 0.3.

The threshold change still stands on its own reasoning: at 62% wins the bot
was losing only 9% of games; the rest were draws, and draws are common in
this game (scripted against itself draws 43%). A 70% win bar treats a
defended draw as failure. It is 60% from here on.

## 2026-10-10: a live view for a demo told from the logs

Crit 10's demo is narrated from the logs alone while classmates play. `/log`
now opens with "Right now": every arena's score and turn, and for each seat who
is in it (public label, or which bot), how many choices that person made in the
last minute, and their pickups, captures and times caught this match. It reads
the server's memory, not the database, and refreshes every two seconds. A
person who stops choosing shows up at once, which is what a takeover story
needs.

## 2026-10-10: the first merge was stopped by CI, correctly

Merging to `main` ran the full checks in the real Docker image for the first
time. The spec and the engine tests passed; the secret scan failed, reporting a
"verified" Lob API key at `tests/test_engine.py` line 115, which is the name of
a pytest function. Nothing was deployed, which is the point of the gate.

Before changing anything, I ran TruffleHog locally over the whole history: it
found nothing at all, verified or not. The local binary was 3.99.2; CI pins
3.96.0, whose Lob pattern matched the function name (verification calls Lob's
API, so it can also succeed by accident). The repo has never used Lob. The fix
excludes that one detector in this repo, with the reason in the workflow;
every other detector still runs. The course page says to fix a step that
misfires on a site with nothing wrong in it, and this was the narrowest fix.

## 2026-10-10: the bot passes the scripted bot

The continuation run climbed the curriculum from level 0.3 to 1.0 (the full
scripted bot) in about 12M samples, stepping up whenever it won 60% of 100
games. Checkpoints evaluated on unseen maps against the full scripted bot
showed it learn defence as the opponents got stronger:

| when | win | draw | loss | captures for / against |
|---|---|---|---|---|
| first learning run (level 0.2) | 0% | 0% | 100% | 0.01 / 3.00 |
| at level 0.6 (200 games) | 2.5% | 12% | 85.5% | 0.23 / 2.02 |
| at level 0.8 (200 games) | 28.5% | 18% | 53.5% | 1.02 / 1.45 |
| reaching level 1.0 (400 games) | 40.0% [35.3, 44.9] | 25% | 35% | 1.18 / 0.77 |
| scripted against itself (400 games) | 29% | 43% | 28% | 0.69 / 0.68 |

At level 1.0 it wins more than it loses against the scripted bot, and its
whole 95% interval for wins sits above the scripted bot's own 29%. Its attack
passed the scripted bot's first (at level 0.8 it already scored more); its
defence caught up last. Training continues against the full scripted bot.

## 2026-10-10: cur4 fills the seats

The 30M-sample continuation finished against the full scripted bot. On 400
unseen maps against the full scripted bot: 48.2% wins [43.4, 53.1], 45.8%
draws, 6.0% losses, 1.44 captures for and 0.10 against (scripted against
itself on the same maps: 29.2% / 43.0% / 27.8%, 0.69 / 0.68). It barely lets
the scripted bot score, and scores twice as often.

I chose to have it fill every empty seat. Beating the scripted bot is not the
same as being a good teammate for people (Carroll et al. 2019 found agents
trained only with programs can be poor human partners), and the README says
so in its limits; the crit sessions are the first test with people. It is
also the bot on show at `/?watch`. cur2 is removed from the server; its
numbers stay in this log.

## 2026-10-10: a pause button

Asked for while playing. With several people in a match a pause stops
everyone, so who may pause, and for how long, is a design choice (ADR 0015).
I chose: anyone with a seat can pause, with no time limit, and anyone with a
seat can resume. The game is for a few friends who can sort it out between
themselves, and a time limit would cut off the interruptions a pause is for.
While paused no turn resolves and no seat is handed to a bot; resuming
restarts everyone's idle clock. Pauses are logged. Two new spec checks: a
pause stops turns and others see who paused, then someone else resumes; a
visitor without a seat can't pause.

## 2026-10-10: the pause button did nothing

Playing it, the button did nothing: the browser had kept the old game.js,
which had no handler for it. The spec could not see this, because it talks
to the server directly. Scripts and styles are now loaded by a hash of their
contents, so a new page always gets new code, after a deploy too. From here
all work happens on main: crit tags freeze each crit's state, so a separate
branch adds nothing.

## 2026-10-10: who may change what, and logs for a narrator

Crit 10 asks that the server check what each person may see and change, and
that the decision is written down. Before writing it, I audited the checks in
the code instead of trusting what I remembered. Most held: the server finds
your seat from your cookie, a request can't name a seat, only seated people
can pause, private arenas need the operator key, and no cookie is shown or
logged. The audit found two real holes, each fixed with a spec check that
failed first:

- **A reload could lose your seat.** A newcomer could take the seat of
  someone whose page had just closed, so in a full match a reload put you on
  the bench. ADR 0011 promises your seat back. Now a newcomer can take a gone
  person's seat only after a bot covers it
  ([`ba7700a`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba7700a)).
- **Live choices were public.** Choices are saved every two seconds, and the
  choices endpoint answered for live matches, so someone could read what
  another person chose before the turn resolved. It now answers only once the
  match is over ([`e573e75`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e573e75)).

New spec checks cover the rest: a request naming someone else's seat still
only chooses for your own; people on the bench, watchers and people with no
cookie can't move or pause; the cookie is in no page, stream or log view; your
seat comes back after a bot covers it; everyone sees the same board
([`1b8f4dd`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1b8f4dd), [`01781c1`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/01781c1)). ADR 0016 writes the
decision down: an anonymous cookie with a public label, and for each action
who may do it, where the server checks it, and which check holds it
([`2267667`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/2267667)).

The demo is narrated from the logs while classmates play, so I read the real
lines from two Chrome profiles on a local server. Bots were logged as "A new
visitor", lines had no match or seat, and closing the page was never logged.
Each line now says who, which arena, match and seat, and ends with a plain
sentence, the one `/log` shows ([`378b5a1`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/378b5a1)). The page now
tells each person their label, so they can find themselves in the log
([`e45222e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e45222e)). `doc/reading-the-logs.md` explains each line, a
narration script, and how the same logs debug the live app
([`5fb852f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/5fb852f)).

## 2026-10-11: broken bodies, pausing from a closed page, a shorter README

Three small fixes, each with a spec check that failed first:

- **A broken body gave a 500.** A POST whose body was not JSON, or was JSON
  but not an object, crashed the handler. Now one helper reads every POST body
  and answers 400 with a short message ([`e2eeba2`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/e2eeba2)).
- **A closed page could still pause.** After you close the page, your seat is
  kept for you through the grace period, and the server still let a direct
  request from you pause or resume. But you can't see the match, so now it
  answers 409, the same as having no seat. ADR 0016 is amended to say so, and
  ADR 0015's "anyone with a seat" is narrowed ([`952ed6f`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/952ed6f)).
- **The README was 604 words**, over the 600 limit. Tighter wording brings it
  to 593, with no claim, heading, source or limit dropped
  ([`32a72c9`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/32a72c9)).

## 2026-10-13: a blind study of which bot is the better teammate

The README says a bot can be a good teammate for people, but the only
evidence was bots against bots: cur4 beats the scripted bot. That shows the
bot plays well, not that people are glad to have it on their team. So people
now rate it, without knowing which bot it is (ADR 0017). In the shared arena,
each match draws a bot for each team from a list (scripted and cur4 for now;
a new bot is added by name). Your bot teammate shows as "Bot A" or "Bot B",
with a letter drawn each match, so a letter tells you nothing. When the match
ends you answer "Was your bot teammate helpful?" 1 to 5, or skip, and then
see which bot it was. The server takes one answer per person per match, only
from someone who sat on that team. Opponent bots are still named, and bots
still choose only from the board shown when the turn opened: the study
changes which bot plays, never what it sees. The CLAUDE.md rule "never hide
which bot is playing" now says this, and the game page and the README's
limits tell people before they play.

Ratings alone can't tell a helpful bot from one that scores everything
itself, so the study also counts, for each team, captures by people and by
bots. `/study` shows both, with n. It shows a mean and a 95% interval only
from 10 ratings up, and says the interval is too narrow, since one person
can rate many matches
([`80d7c5a`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/80d7c5a)).

## 2026-10-13: your matches, and replays you can watch

A marker comes back the next day to see that the app kept what they did.
Before, nothing on screen showed it. `/me` now lists your own finished
matches, found by your cookie on the server: when, your team, the score, who
played with you (labels only), your bot teammate and your rating, with a
late answer if you missed the question
([`423238e`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/423238e)). Each links to `/matches/{id}`, which plays the
match back with back, play, next, a slider and three speeds, by keyboard too.
The board drawing moved into `board.js`, so the game and the replay draw the
same way. The server rebuilds each turn from the saved moves, and the spec
checks every frame against the TypeScript engine, down to the saved final
score ([`ba75d0b`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/ba75d0b)).

## 2026-10-13: two browsers, a phone and a slow link

I drove two Chrome profiles at the marking viewports, 1920×1080 and 390×844,
one of them on a slow-3G link (400 ms latency, about 400 kbit/s). The slow
page took about 6 seconds to load, then played: its moves landed, turns
waited for it, and both people got the question after the match and saw
the bot revealed. Two real problems, both on the phone:

- **The move pad was off the screen.** It started at 935 px on an 844 px
  screen, under the introduction, so you had to scroll down to play. On
  narrow screens the game now comes right after the heading, and the pad
  ends at 720 px.
- **Your matches scrolled sideways**, 408 px in 390. On narrow screens each
  match is now a labelled card.

([`1068ce1`](https://github.com/comp4020-agentic-coding-studio/comp4020-final-peacefulmind43/commit/1068ce1)). The accessibility check now covers `/study`,
`/me` and a replay page. The layout checks themselves need a real browser,
which the spec doesn't run, so they stay a manual step for now.

## 2026-10-13: no ratings, only behaviour

I decided to remove the rating question. At crits, my classmates mostly play
a match or two quickly and without care, so their ratings would be noise. I
also thought about letting only me rate, blinded, but that needs a sign-in
page, a signed cookie and rules for shared teams, all for one rater who knows
the project. It is not worth it. So now nobody is blinded and nobody is asked:
every bot seat shows its real name again. The random choice of the teammate
bot (scripted or cur4) stays and is saved for every match, so the behaviour
of everyone who plays is the evidence. `/study` now shows, for each bot, the
captures by people and by bots on its teams, and for each person, their own
captures and their bot teammate's, with n on the page (ADR 0019).

## 2026-10-13: training the bot with many partners (ADR 0018)

cur4 learned with copies of itself on its team. People are not copies of
cur4. So I wrote ADR 0018: FCP-lite, after Strouse et al. 2021. The bot plays
one or two seats, and a partner from a pool plays the rest of its team. The
pool has old runs at different stages (cur1 early and weak, cur2, a mid-run
cur4, cur4 itself, phi2 which only defends), the scripted bot, the scripted
bot with more noise, and a random walker. Before choosing the pool, I played
each old bot against the scripted bot on 40 unseen maps and looked at where
it went, so I know what kind of partner each one is.

A new evaluation, `rl/eval.py --teammate`, puts the bot in one seat beside
partners that are not in the pool (scripted with 30% noise, cur3, lr1e3)
against the full scripted team, and puts cur4 in the same seat with the same
partners and maps. It counts captures by the bot and by its partners, so I
can see if the bot does everything itself.

This check already showed a problem with cur4 before any new training: beside
the scripted bot with 30% noise it lost 52% of 200 games, and beside cur3 it
lost 79%. Against the scripted bot, with cur4 on every seat, it loses 6%.

**Profile first.** The first version ran each partner network one seat at a
time. A profile of the environment showed the partners' forward passes were
the largest cost, so now each network makes one batched pass per turn for all
the games it plays in. The environment alone runs about 6,000 samples a
second; full training about 2,950 (cur4's runs: about 4,000).

**Smoke test** (1M samples, 6 minutes, from cur4). It learns: in training,
losses fell from 23% to 16% of games. On 200 unseen maps, beside held-out
partners, against the full scripted team, compared with cur4 in the same
seat:

| partner (held out) | bot | win | draw | loss |
|---|---|---|---|---|
| scripted, 30% noise | smoke | 24.5% | 41.5% | 34.0% [27.8, 40.8] |
| | cur4 | 24.0% | 24.0% | 52.0% [45.1, 58.8] |
| cur3 | smoke | 8.5% | 39.0% | 52.5% [45.6, 59.3] |
| | cur4 | 5.0% | 16.0% | 79.0% [72.8, 84.1] |
| lr1e3 | smoke | 43.5% | 32.5% | 24.0% [18.6, 30.4] |
| | cur4 | 43.0% | 28.0% | 29.0% [23.2, 35.6] |

Against the full scripted bot on all seats it still wins 47.0% and loses
7.0% (200 games), close to cur4. The gain is mostly fewer losses, not more
wins: the smoke bot spends less time on the enemy half (8% of turns, cur4
11%) and lets in fewer captures. This is one short run, so it is a sign, not
a result. The mirror tests still pass (28 passed).

**The real run** is `fcp1`: 88M samples from cur4, seed 7, about 8.3 hours,
with a checkpoint kept every 250 updates. `rl/after_fcp.sh fcp1` waits for it,
checks the export against PyTorch, and runs both evaluations on 400 unseen
maps next to cur4. Nothing is deployed from this; that is a separate choice,
and the people in the blind study (ADR 0017) are the real test.

## 2026-10-14: fcp1 passes its bar, and what it really learned

The fcp1 run finished. `rl/after_fcp.sh` checked the export (NumPy and
PyTorch differ by at most 1e-6) and played fcp1 and cur4 in the same seat,
with the same partners and maps, on 400 unseen maps against the full scripted
team. Win, draw and loss, with 95% intervals:

| partner | bot | win | draw | loss |
|---|---|---|---|---|
| scripted, 30% noise (held out) | fcp1 | 43.5% [38.7, 48.4] | 34.2% [29.8, 39.0] | 22.2% [18.4, 26.6] |
| | cur4 | 22.8% [18.9, 27.1] | 24.2% [20.3, 28.7] | 53.0% [48.1, 57.8] |
| cur3 (held out) | fcp1 | 36.5% [31.9, 41.3] | 31.2% [26.9, 36.0] | 32.2% [27.9, 37.0] |
| | cur4 | 4.8% [3.1, 7.3] | 17.5% [14.1, 21.5] | 77.8% [73.4, 81.6] |
| lr1e3 (held out) | fcp1 | 48.2% [43.4, 53.1] | 37.8% [33.1, 42.6] | 14.0% [10.9, 17.7] |
| | cur4 | 44.5% [39.7, 49.4] | 27.0% [22.9, 31.6] | 28.5% [24.3, 33.1] |
| scripted (in the pool) | fcp1 | 55.8% [50.9, 60.5] | 33.5% [29.1, 38.3] | 10.8% [8.1, 14.2] |
| | cur4 | 36.2% [31.7, 41.1] | 34.5% [30.0, 39.3] | 29.2% [25.0, 33.9] |

With fcp1 on every seat against the full scripted bot, it wins 48.5%
[43.6, 53.4], draws 49.2% and loses 2.2%. cur4 there wins 48.2% [43.4, 53.1],
draws 45.8% and loses 6.0%.

**The bar in ADR 0018 is met.** fcp1 loses less than cur4 beside every
held-out partner, and the loss intervals don't overlap for any of the three
(the ADR asked for one). Against the full scripted bot it did not get worse:
its win rate is inside cur4's interval, and it loses fewer games.

**But it is not a team player.** The partners still score almost nothing:
beside the held-out partners, captures by partners are 0.00 to 0.05 a game,
and the bot makes nearly all of them (1.20 to 1.45). Beside the scripted bot,
partners score 0.25 with fcp1 and 0.27 with cur4, so no change. What changed
is where the bot goes: it spends 14 to 21% of turns on the enemy half (18 to
19% beside two of the held-out partners), against 9 to 13% for cur4, and it
is caught more often (1.1 to 2.4 times a game, cur4 about 1.0). So FCP made
the bot robust to how good its partner is: it no longer falls apart beside a
weak one. It did not teach it to help the partner score. The next idea would
be a reward for cooperation, or giving the bot its partners' intent (for
example, where each partner is heading) in the observation.

**I decided to deploy fcp1 and add it to the study.** fcp1 now fills every
empty seat, plays the opponents and is the bot at `/?watch`. The teammate draw
in the shared arena is now scripted, cur4 or fcp1, so `/study` compares all
three with real people. cur4 stays on the server for that. ADR 0018 is now
accepted (2026-10-14). It was merged as proposed, and a proposed record may
be finalised, so only its status line changed.

## 2026-10-16: teaching fcp1 to let its partners score (ADR 0020)

fcp1 is strong beside any partner, but it does everything itself: beside the
held-out partners, they score 0.00 to 0.05 captures a game. So I wrote ADR
0020. The bot keeps the team reward and FCP-lite, and gets two new terms:

- a potential-based reward for its partners' progress: when a partner gets
  closer to scoring, the bot gets a small reward; when a partner is caught,
  it loses it. This form can't be farmed and does not change the best
  policy (Ng et al. 1999);
- a small bonus (0.3) when a partner captures. This one is not
  potential-based, so it falls to 0 at 75% of training.

fcp1 joins the training pool (cur4 was already in it). The held-out partners
stay the same. Before training, the ADR writes down the bar: the partners'
share of captures must be higher than with fcp1 beside at least two of the
three held-out partners, with 95% bootstrap intervals that don't overlap;
losses not clearly higher; and no drop against the full scripted bot. A test
plays each game and its mirror and checks blue and red get the same reward.

**The slow update was not the new code.** An earlier try saw some updates
take 89 s or 155 s instead of 7 s. I profiled before changing anything. The
environment alone with the new terms runs 5,900 samples a second, against
6,200 without them; the shortest-path searches stay cached (98% hits). Most
smoke updates took 7 s, the same as fcp1, and the slow ones were single
spikes, so the cause was outside the code (the Mac was busy or idle-sleeping
then). I can't prove which. To see it next time, `metrics.csv` now logs the
rollout time and the update time of every update. In a new 2M-sample smoke
run they were steady: about 5 s for the rollout and 2 s for the update,
2,850 samples a second overall (fcp1: 2,845).

**Smoke test** (2M samples from fcp1, 100 unseen maps, same seat as fcp1).
NumPy and PyTorch agree (1.9e-6). Against the full scripted bot it wins
49.0% and loses 2.0%. Beside the held-out partners, it plays like fcp1:
the partners' share of captures is 0.0% (fcp1 0.8%) with scripted30, 4.2%
(fcp1 5.6%) with cur3, and 0% for both with lr1e3. That is expected after
2M samples; it shows the pipeline and the new measures work, not a result.
The tests pass (37 passed, with the new team-play tests).

**The real run** is `team1`: 82M samples from fcp1, seed 13, about 8 hours.
`rl/after_team.sh team1` waits for it, checks the export, and writes
`rl/runs/team1/eval.txt` with team1 and fcp1 side by side on 400 unseen maps.

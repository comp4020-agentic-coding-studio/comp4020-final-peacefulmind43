# The RL bot, on one page

Every number here comes from an evaluation file or the process log, linked
next to it.

## The problem

The app is a small capture-the-flag game where people and bots share teams
(2v2 or 3v3, on random symmetric maps). Bots fill every empty seat. The
question is what makes a bot a **good teammate for people** ([ADR 0013](../adr/0013-rl-bot-design.md),
[ADR 0018](../adr/0018-fcp-lite-partner-pool.md)).

## Environment and engine

The rules are written down once ([ADR 0010](../adr/0010-capture-the-flag-rules.md))
and implemented twice, separately: in Python (`app/game/engine.py`, used by
the server and by training) and in TypeScript (`spec/engine.ts`). A parity
test plays both on many maps and checks they agree on every tick. The game is
deterministic: the same seed gives the same map and, with the same choices,
the same game, so every match can be replayed
([ADR 0014](../adr/0014-logging-the-game-and-replays.md)).

## Observation and mirroring

The bot sees the whole map as image planes (walls, bases, players, flags),
padded to 20×12, plus six numbers. It sees exactly what a person sees on
screen, no more. Red's view is flipped left to right, so one network plays
both teams, always attacking to the right
([ADR 0013](../adr/0013-rl-bot-design.md)).

A mirror test caught a real bug. The view was flipped for red, but the
network's action was applied to the board unflipped, so for red "towards the
enemy" moved it home. Half of every batch taught the opposite of the other
half. The old test only checked what the two sides *see*. A new test plays a
game and its mirror with the same policy and checks they stay mirrored;
removing the fix makes it fail ([process log, 2026-10-10](../process-log.md)).

## Training

- **PPO with shared parameters.** Every learning seat is played by the same
  small convolutional network (about 250 thousand parameters) from its own view.
- **Potential-based shaping.** Each player gets `γ·Φ(after) − Φ(before)`, where
  Φ is minus the path still to walk before scoring. This form cannot be farmed
  and does not change the best policy (Ng, Harada and Russell 1999). Its weight
  falls to 0, so the bot ends up optimising the score alone.
- **Curriculum.** The first bot never left home: every crossing met a full
  defender. Opponents now start wandering and get stronger each time the bot
  wins 60% of 100 games.
- **Profiling first.** A profile showed 92% of the time in shortest-path
  searches. Caching them made the environment **13 times faster**, with exactly
  the same results on 120 scripted games ([process log, 2026-10-09](../process-log.md)).

## Results

Each bot was evaluated on 400 maps it never trained on, against the full
scripted team, with Wilson 95% intervals
([fcp1-eval.txt](fcp1-eval.txt), [team1-eval.txt](team1-eval.txt)).

**On every seat, against the scripted bot** (win / draw / loss):

| bot | win | draw | loss |
|---|---|---|---|
| scripted (itself) | 29.2% [25.0, 33.9] | 43.0% | 27.8% |
| cur4 (self-play) | 48.2% [43.4, 53.1] | 45.8% | 6.0% |
| fcp1 (partner pool) | 48.5% [43.6, 53.4] | 49.2% | 2.2% |
| team1 (team-play reward) | 97.2% [95.1, 98.5] | 2.0% | 0.8% |

**One seat, beside a held-out partner** (loss rate; partners never seen in training):

| partner | cur4 | fcp1 | team1 |
|---|---|---|---|
| scripted, 30% noise | 53.0% [48.1, 57.8] | 22.2% [18.4, 26.6] | 20.2% [16.6, 24.5] |
| cur3 (older bot) | 77.8% [73.4, 81.6] | 32.2% [27.9, 37.0] | 40.2% [35.6, 45.1] |
| lr1e3 (only defends) | 28.5% [24.3, 33.1] | 14.0% [10.9, 17.7] | 5.5% [3.7, 8.2] |

## FCP-lite: robust, but not a team player

cur4 was trained only with copies of itself and fell apart beside weaker
partners. fcp1 was trained beside a pool of eight fixed partners of mixed
skill. It met its
bar: fewer losses than cur4 beside every held-out partner, with intervals
that don't overlap. But its partners still scored almost nothing (0.00 to
0.05 captures a game, the bot 1.20 to 1.45). FCP made the bot **robust to its
partner's quality**; it did not teach it to **help its partner score**
([ADR 0018](../adr/0018-fcp-lite-partner-pool.md), [process log, 2026-10-14](../process-log.md)).

## The team-play reward: a negative result

team1 added a potential-based reward for partners' progress and a bonus for
partner captures that fell to 0 at 75% of training
([ADR 0020](../adr/0020-team-play-reward.md)). It **failed**: the partners'
share of captures went down, not up (beside scripted30 0.4% [0.1, 1.0]
against fcp1's 1.5% [0.6, 2.7]; beside cur3 2.3% against 4.2%). It became a
much stronger lone wolf, on the enemy half 32 to 51% of turns against 14 to
21%. The reason: the partner term is potential-based, so by design it cannot
change the best policy, and the bonus was gone by the end. If playing alone
is best for the team reward, neither term can teach a split of the work. An
objective that values partners' scoring itself, partner intent in the
observation, or human-like partners could. team1 was **not deployed**: it
would be far too strong for people, and it is no better as a teammate.

## Bars written before training

Each run's deployment bar was written in its ADR **before** training, so a
result could not be explained away afterwards. fcp1 passed and is deployed; team1 failed and is recorded
as it is.

## Serving

The server has 256 MB of memory and no PyTorch. The weights are exported to
a NumPy file and run with NumPy. A bot ships only if NumPy's output matches
PyTorch's: the largest difference was 9.5e-7 for fcp1 and 1.9e-6 for team1.
Training and serving use the same observation builder, `app/game/obs.py`.

## Limits

- **No human evaluation data yet.** Every partner above is a program. For each
  match with people, the live site records which bot was their teammate and
  compares behaviour on `/study`
  ([ADR 0017](../adr/0017-blind-teammate-study.md), with ratings and blinding
  removed by [ADR 0019](../adr/0019-no-ratings-behaviour-only.md)). But there is
  little such data yet, so these results show a better partner for bots, not
  for people.
- Each bot is one training run; checkpoints are local and not in git.

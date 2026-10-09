# 0013. The RL bot: what it sees, what it is rewarded for, how it trains

Status: accepted (2026-10-09)

## Context

Scripted bots fill every empty seat today (ADR 0011). The project's question is
what makes a bot a good teammate for people, and the first step is a bot that
learns to play at all, on the same engine and rules as everyone else, and then
beats the scripted bots on maps it has never seen. It has to run on the server
(256 MB, no GPU) and choose a move well inside a turn.

## Decisions

**Observation: the whole map, padded to the largest size, seen from your own
side.** The network needs a fixed-size input, but 2v2 maps are 16×10 and 3v3
maps 20×12. Every map is drawn into 20×12 planes, with a plane marking cells
outside the real map. Red's view is flipped left to right, so every bot sees
itself attacking to the right, and one network plays both teams. The planes:
walls, outside the map, own half, own base, enemy base, self, teammates on the
board, enemies on the board, own flag, enemy flag, carriers. Plus six numbers:
turns left, score difference, whether you carry the flag, your respawn timer,
whether it is 3v3, and whether your flag has been taken. A bot sees exactly what
a person sees on screen, no more.

*Rejected:* a window centred on yourself. It fits any map size and generalises
by position, but it hides the rest of the map: what your teammates are doing,
which is what teamwork is made of, and more than a person sees is not the
problem; less than a person sees would be unfair the other way.

**Reward: team reward, plus potential-based shaping that fades out.** A
capture gives +1 to every player on the scoring team and −1 to every player on
the other. That alone is too sparse for a bot that starts by wandering: it
would almost never score, and learn nothing. So each player also gets
`γ·Φ(after) − Φ(before)`, where Φ is minus their distance (by shortest path,
scaled) to what they should go for: the enemy flag, or home if they carry it.
Shaping of this form provably doesn't change which policy is best (Ng, Harada
and Russell, 1999): walking towards the flag and back again earns exactly
nothing, so it can't be farmed. Its weight falls from 1 to 0 over the first
half of training, so the bot ends up optimising the score alone.

*Rejected:* only the sparse reward (likely never learns before crit 9);
rewards for events such as picking up the flag (easy to farm: pick up, get
caught, pick up again); individual rewards for scoring (teaches a bot to take
the glory instead of helping, the opposite of a good teammate).

**Training: PPO with one shared network.** Every seat on the learning team is
played by the same network from its own view (independent PPO with shared
parameters). Until crit 9 the opponents are the scripted bots, so "better than
scripted" is a clear, measurable target. Team sizes 2v2 and 3v3 are mixed.
Training maps come from one range of seeds; evaluation uses seeds the bot never
trained on. Self-play and a pool of past versions come after crit 9.

**Network:** a small convolutional net (two layers, then one hidden layer of
128) with a policy head (5 actions) and a value head, about 250 thousand
parameters, under 1 MB.

**Serving:** the weights are exported to a NumPy file and run with NumPy on the
server, which can't hold PyTorch. A test checks that NumPy gives the same
outputs as PyTorch on saved inputs. The bot samples its move from the policy,
seeded by the match, turn and seat, so matches still replay exactly and the bot
is harder to read than one that always takes its top choice.

**The bot sees only the board** everyone was shown when the turn opened, as the
scripted bots do (ADR 0011, 0012). The observation is built in one place,
`app/game/obs.py`, used by both training and the server, so the two can't
drift apart.

## Consequences

- Results are reported as win rates against the scripted bots on unseen maps,
  over several training seeds, with confidence intervals, not single runs.
- The scripted bots stay as the fallback: if a trained bot is missing or worse,
  seats still fill.
- Training code and its PyTorch dependency live in `rl/`, outside the server
  image; checkpoints stay local, and only an exported bot that passed
  evaluation is committed.

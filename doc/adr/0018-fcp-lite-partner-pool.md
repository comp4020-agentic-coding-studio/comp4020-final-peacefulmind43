# 0018. FCP-lite: training the bot with a pool of partners, not copies of itself

Status: accepted (2026-10-14; proposed 2026-10-13). Extends ADR 0013
(training); the observation, reward, network and serving there are unchanged.
Accepted after fcp1 met the bar below; this status line is the only change
made at acceptance.

## Context

cur4 (ADR 0013) was trained with every seat of its team played by itself. On
400 unseen maps against the full scripted bot it wins 48.2%, draws 45.8% and
loses 6.0%. But a seat beside a person is not a seat beside cur4. Carroll et
al. (2019) found that agents trained only with copies of themselves or with
one fixed program can be poor partners for people, because they learn
conventions that only their training partner follows. Strouse et al. (2021,
Fictitious Co-Play) trained an agent as the best response to a pool of
partners of different skill, including early, weak checkpoints, and it was a
better partner for people it never met.

A quick check before any training shows the gap. With cur4 in one seat and a
partner it never trained with against the full scripted team (200 unseen
maps), cur4 loses 52% of games beside the scripted bot at 30% noise, and 79%
beside cur3, an earlier version of itself. People are more varied than either.

## Options

1. **Keep self-play with shared parameters (cur4's training).** No cost, but
   it optimises for the one partner that will never sit beside a person.
2. **Train beside the scripted bot only.** One fixed partner: the bot learns
   the scripted bot's habits (its roles depend on its seat) and can lean on
   them. Cheap, but it is the same overfitting with a different partner.
3. **FCP-lite: a pool of fixed partners of mixed skill and style.** Each game
   draws one partner; the learner plays one or two seats and the partner the
   rest. Costs a pool to build and slower training (partners need their own
   forward passes), and the learner still never meets a person.
4. **Full FCP: train many self-play agents from scratch with different seeds,
   keep checkpoints at several stages, then train the final agent.** The
   paper's version, with a more diverse pool. Each cur run took 1 to 2 hours
   on this Mac, so a pool of several seeds is days of compute before the real
   run starts.
5. **Model the partner online (infer its type from its moves).** Needs memory
   in the network or a history in the observation; a bigger change to ADR 0013
   and to the server, for a bot that is not yet shown to need it.

## Decision

Option 3, using checkpoints that already exist instead of training new ones.

**The training pool** (`rl/partners.py`, `TRAIN_POOL`), chosen after playing
each candidate against the full scripted bot on 40 unseen maps and watching
where it goes:

| partner | what it does |
|---|---|
| cur1 (early, 2M samples) | never scores; almost never crosses the middle |
| cur2 | the first run that attacked; never gets home past a defender |
| cur4 snapshot (mid-run) | about even with the scripted bot |
| cur4 (final) | the bot itself, so self-play is one case among eight |
| phi2 | a failed run: never leaves its own half, a pure defender |
| scripted | the full scripted bot (10% random moves) |
| scripted, 50% more noise | a weaker, erratic version of it |
| random walker | repeats its last move half the time, else a new one |

**Each training game.** Slots cycle through 2v2 with the learner in 1 seat,
3v3 with 1 seat, and 3v3 with 2 seats (the 2 seats share one network, the only
parameter sharing left). Which seats are the learner's is drawn each game, so
the scripted partner's role (it attacks or defends by seat) varies. One pool
member plays all the partner seats. The other team is the full scripted bot
with probability 0.6, otherwise one pool member, so the learner also meets
weak and strange opponents.

**Starting point and length.** Initialised from cur4's checkpoint, so it
starts able to play. No curriculum and no shaping (cur4 already scores); the
reward is the team reward of ADR 0013, so a capture by the partner is worth
exactly as much as one by the bot. 88M learner samples, 120 games at a time,
about 8.3 hours on the M2 (measured in the smoke test).

**Held out, never a partner or opponent in training** (`HELD_OUT`): the
scripted bot with 30% noise (a level between the two in the pool), cur3 (the
run between cur2 and cur4), and lr1e3 (a failed run that only defends). cur3
is an ancestor of cur4, so it is held out from the pool but not unrelated to
it; the scripted noise level is the cleaner test.

**The teammate evaluation** (`rl/eval.py --teammate`). The bot plays one seat
(which seat rotates), a held-out partner the rest, against the full scripted
team, on the unseen maps (seeds from 1,000,000) that ADR 0013 uses. cur4 plays
the same seat with the same partners, maps and randomness. It reports wins,
draws and losses with Wilson 95% intervals, captures for and against, captures
by the bot against by its partners, how much of its time the bot spends on the
enemy half and how often it is caught. The existing evaluation against the
full scripted bot stays, to check the bot did not get worse at playing.

**What would make it worth deploying:** fewer losses than cur4 beside every
held-out partner, with intervals that don't overlap for at least one of them,
and no drop against the full scripted bot outside cur4's interval. Then it can
be added to the blind study (ADR 0017) as a second trained bot; the people
there are the real test. Deployment stays a separate decision.

## Consequences

- Training is slower per sample (about 2,900 a second against cur4's 4,000):
  profiling showed partners' forward passes were most of the extra time, so
  they are batched, one pass per network per turn across all games.
- The pool is built from local checkpoints that are not committed;
  `rl/make_pool.sh` copies them into `rl/runs/pool/`. A result from this run
  is reproducible only on a machine with those runs.
- The learner sees fewer of its own samples per game (1 or 2 seats, not all),
  so each sample is about a partner that behaves differently, which is the
  point, but the value estimates are noisier.
- A bot that wins more beside weak partners may do it by doing everything
  itself: the captures-by-bot count is there to see that. Team reward does not
  stop it; that may be the right behaviour beside a weak partner, and the
  ratings in ADR 0017 say whether people like it.
- Still not people. The pool has no person in it, and nothing here shows the
  bot is a better partner for people; it shows it is a better partner for
  programs it did not train with.

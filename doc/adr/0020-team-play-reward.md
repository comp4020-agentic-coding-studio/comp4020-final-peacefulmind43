# 0020. Team play: reward the bot for its partners' progress

Status: proposed (2026-10-16). Extends ADR 0018 (FCP-lite training) and the
reward of ADR 0013; the observation, network and serving are unchanged.

## Context

fcp1 (ADR 0018) is robust to how good its partner is: beside held-out
partners it loses 14 to 32% of games against the full scripted team, where
cur4 lost 28 to 78%. But it is a lone wolf. On 400 unseen maps, beside the
three held-out partners, the partners score 0.00 to 0.05 captures a game and
fcp1 scores 1.20 to 1.45. Beside the scripted bot (in the pool) partners score
0.25 with fcp1 and 0.27 with cur4: no change. The team reward of ADR 0013
pays the same for a capture by anyone, so it gives no reason to help a
partner score when the bot can score itself. Beside a person that is a poor
teammate: the person has nothing to do but watch.

The goal is a bot that helps its partners score, measured by what happens in
games (ADR 0019: behaviour, not ratings), without losing much strength.

## Options

1. **Potential-based shaping on the partners' progress.** Each learner seat
   also gets `w · mean over its teammates of (γ·Φ_mate(after) − Φ_mate(before))`,
   where Φ_mate is ADR 0013's potential for that teammate: minus the path it
   still has to walk to score (to the enemy flag and home, or home if it
   carries the flag). The bot is paid when a partner gets closer to scoring,
   for example because the bot drew a defender away or cleared the way, and
   charged when a partner is caught. It is a function of the state, so it
   telescopes: it can't be farmed and does not change which policy is best
   for the team reward (Ng, Harada and Russell 1999; for several agents,
   Devlin and Kudenko 2011). It guides learning; it does not change the goal.
   Cost: one more shortest-path lookup per teammate per turn, cached.
2. **A bonus when a partner captures.** `b` per capture by a teammate (not by
   the seat itself). Direct, but not potential-based: kept forever, it would
   pay the bot to let a partner score instead of scoring itself, even when
   that loses games. So it must fade to 0 before training ends.
3. **Reward for tagging the enemy carrier** (or a potential on the enemy
   carrier's remaining path). A defensive help. fcp1 already defends well
   (its losses are low); the gap is that partners never score, so this does
   not aim at the problem. Left for later.
4. **Role diversity** (for example a "support" role drawn per game, or an
   entropy bonus over where seats go). Needs a role signal in the observation
   or a population of learners; a bigger change for an unclear gain.
5. **Partner intent in the observation** (where each teammate is heading).
   Probably the strongest long-term fix, but it changes `app/game/obs.py`,
   the network input, the export and the server, and every old bot in the
   pool would need the old observation. Too big for this step.

## Decision

Options 1 and 2 together, on top of ADR 0018's FCP-lite.

- **Shaping on the partners' progress**, weight `w = 0.5`, kept constant for
  the whole run (it is potential-based, so it does not need to fade). The
  bot's own shaping stays off, as in fcp1.
- **A bonus for each partner capture**, `b = 0.3` at the start, falling
  linearly to 0 at 75% of training, so the last quarter trains on the team
  reward and the potential term only. 0.3 is less than the +1 of a capture,
  so scoring itself is still worth more than waiting for a partner.
- **Mirrored for red.** Both terms are defined on seats and path lengths, not
  directions; a test plays each game and its mirror image and checks every
  blue seat gets exactly the reward of the matching red seat
  (`rl/test_team_play.py`). Another test checks the shaping telescopes.
- **The pool** (`rl/partners.py`, `TEAM_POOL`): ADR 0018's pool, which
  already has cur4, plus fcp1. fcp1 is the strongest partner and the most
  selfish one, so the bot must also learn to play beside a copy of itself
  that takes the flag. Held out, as before, never a partner or an opponent:
  scripted at 30% noise, cur3 and lr1e3.
- **Start and length.** From fcp1's checkpoint, seed 13, 82M learner
  samples (about 8 hours at fcp1's 2,850 samples a second), a checkpoint kept
  every 250 updates. Run name `team1`.

**New measures** in `rl/eval.py --teammate`, so the result can be seen, not
only scored:

- **partners' share of captures**: all partner captures over all team
  captures, pooled over the 400 games, with a 95% **percentile bootstrap**
  interval (2,000 resamples of whole games, fixed seed);
- **escort**: of the turns a partner carries the enemy flag, the share the
  bot is within 2 steps of it;
- **home while a partner attacks**: of the turns a partner is on the enemy
  half, the share the bot is on its own half;
- **enemy carriers tagged** by the bot per game.

**The bar, written before training.** `rl/after_team.sh team1` plays team1
and fcp1 in the same seat with the same partners, maps and randomness (400
unseen maps, seeds from 1,000,000, against the full scripted team). team1 is
a better team player if all three hold:

1. Beside **at least two of the three** held-out partners, the partners'
   share of captures is higher with team1 than with fcp1, and the two 95%
   bootstrap intervals do not overlap.
2. Beside **each** held-out partner, team1's loss rate is not significantly
   higher than fcp1's: team1's Wilson 95% interval for losses must not lie
   wholly above fcp1's.
3. With team1 on every seat against the full scripted bot (400 unseen maps),
   its win rate is not below fcp1's Wilson 95% interval, [43.6%, 53.4%].

If it passes, it can be added to the study as another named bot (ADR 0019);
deploying it in fcp1's place is a separate decision. If it fails, the
numbers go in the process log as they are.

## Consequences

- One of the three held-out partners, lr1e3, never leaves its own half and
  has scored 0.00 a game beside every bot so far. Its share can only rise if
  the bot makes room for a pure defender to attack, which may not be
  possible. That is why the bar asks for two of three.
- A bot paid for partner progress may hang back and score less itself.
  Bar 2 and 3 are there to catch that; the captures by the bot are reported.
- The bonus (option 2) is not policy-invariant while it is on. It fades to 0
  at 75%, so the last quarter of training removes any habit that only pays
  because of it, but the run is too short to be sure of that.
- Throughput: the new terms cost little. The smoke test ran at about 2,900
  samples a second, the same as fcp1 (2,845); a rollout of 128 turns takes
  about 5 s and an update about 2 s, now logged per update in `metrics.csv`.
- The pool still has no person in it. This shows a better partner for
  programs the bot never trained with, by behaviour; people are the real test.

# 0023. Weaker opponent bots when a person plays

Status: accepted (2026-10-19). Changes which bot fills a seat (ADR 0011,
0013). The draw of the teammate bot (ADR 0017, 0019) stays. The watch arena
and the bot-against-bot evaluations do not change.

## Context

The README says speed does not decide, and that a game is fair. But every
empty seat was played by fcp1, on both teams. A person with fcp1 beside them
played against two copies of fcp1. The README admitted that such a person
rarely wins.

I have no data from people to measure this. So I measured it with a stand-in.
The stand-in is the scripted bot with 50% extra random moves. It is not a
person. It sees the whole board at once and never hesitates, but it often
walks the wrong way. It sat in one seat of a team, and fcp1 played the rest of
that team, as it does beside a person. Against two fcp1 bots, on 400 maps no
bot trained or was tested on (seeds from 3,000,000), the stand-in's team won
2.8% [1.5, 4.9] of games and lost 31.8% [27.4, 36.5]. The rest were draws.

## Options

1. Keep fcp1 everywhere. Nothing to build. The bots on the other team stay
   much stronger than the team with a person on it, and the README's claim of
   a fair game stays untrue for anyone who plays alone.
2. Weaker opponent bots when people play. A team with no person on it gets a
   weaker bot, chosen once by measurement. It is simple, and every seat still
   shows the real name of its bot. The cost is that it is tuned to a stand-in,
   not to people, and one level can't suit both a beginner and a strong player.
3. Adaptive difficulty from the score. The opponent gets weaker when the
   person's team falls behind and stronger when it leads. It could fit each
   person. But a match is short (3 captures or 500 turns), so there is little
   score to adapt to. A bot that changes level in the middle of a match is
   also hard to name honestly, and a player who notices it can lose on purpose
   to get an easy bot. It needs its own tuning, again without people.

## Decision

Option 2.

In a match with at least one person, a team with no person is played by the
balanced bot, named in `app/game/bots/balanced.txt`. A team with a person
keeps its teammate bot as before: the bot drawn for it in the shared arena,
or else the deployed bot. If both teams have a person, both teams get the
same bot as teammates, so the match stays even. In the shared arena the
second team then gets the first team's drawn bot, and that is the bot
recorded for it. When a person joins a team that had none, that team's bots
become teammates from then on. The watch arena, where no person plays, is
unchanged: fcp1 against the scripted bot.

The balanced bot is cur4snap, a snapshot taken partway through training
cur4. It was a training partner in ADR 0018, and its export matches PyTorch
like every bot the server runs. Bots still choose only from the board as it
was shown. Nothing about a person's choices reaches them.

I chose it by measurement, with `rl/balance.py`. The stand-in and fcp1 played
each candidate opponent, 400 games each, alternating blue and red and 2v2 and
3v3. I wanted the candidate whose match is closest to even, so I compared the
points share, where a win is 1 and a draw is a half. I did not compare the
win rate alone, because most of these games are draws. A 50% win rate here
means the person's team almost never loses, so it is not an even match.

| opponent | win | draw | loss | points |
|---|---|---|---|---|
| fcp1 (before) | 2.8% [1.5, 4.9] | 65.5% | 31.8% [27.4, 36.5] | 35.5% |
| cur4 | 8.2% [5.9, 11.4] | 73.5% | 18.2% [14.8, 22.3] | 45.0% |
| cur4snap | 23.5% [19.6, 27.9] | 62.5% | 14.0% [10.9, 17.7] | 54.8% |
| scripted | 38.0% [33.4, 42.8] | 50.0% | 12.0% [9.2, 15.6] | 63.0% |
| scripted, 10% more noise | 45.5% [40.7, 50.4] | 46.2% | 8.2% [5.9, 11.4] | 68.6% |
| scripted, 20% more noise | 54.5% [49.6, 59.3] | 41.5% | 4.0% [2.5, 6.4] | 75.2% |
| scripted, 30% more noise | 61.3% [56.4, 65.9] | 37.0% | 1.8% [0.9, 3.6] | 79.8% |
| scripted, 50% more noise | 76.0% [71.6, 79.9] | 23.0% | 1.0% [0.4, 2.5] | 87.5% |

Win and loss are for the stand-in's team, with 95% Wilson intervals.
cur4snap and cur4 are both close to even, from opposite sides. I checked
whether the choice depends on the stand-in. With 30% or 70% extra noise in
the stand-in, cur4snap gave 56.8% and 52.1%, and cur4 gave 42.4% and 44.8%.
On 400 other maps (seeds from 3,100,000) cur4snap gave 55.1% and cur4 42.9%.
cur4snap was the closer one every time, so I chose it. It leans slightly
towards the person's team, which is the side I prefer to err on. The full
output is in `doc/rl/balance-eval.txt`.

## Consequences

- A person who plays alone now meets opponents near their stand-in's level,
  not two strong bots. Whether that suits real people is judged, not
  measured. The stand-in is a program, and real people may be much weaker or
  stronger than it.
- Two thirds of these games are draws, often 0 to 0. Balancing makes the
  result less one-sided. It does not make scoring more common.
- The opponent and the teammate can now be different bots, so a person sees
  two names on the board. Both are always shown (CLAUDE.md).
- The server holds one more export, about 1 MB. With the app running, a
  match on and a person playing, it used about 83 MB of memory locally,
  well under 256 MB.
- If balanced.txt is removed, every seat gets the deployed bot, as before.
- Checked in `tests/test_balance.py` (which bot plays which seat, the same
  bot on both sides when both have people, the watch arena, and that the
  balanced bot moves the same whatever a person chose) and in
  `spec/balance.test.ts` (the balanced bot is named on the other team in a
  private arena with a person, and the watch arena has none of it).

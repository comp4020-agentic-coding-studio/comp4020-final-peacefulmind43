# 0012. Turns that wait for people, up to a deadline

Status: accepted (2026-10-09). Supersedes ADR 0011's fixed 4 Hz tick and its
held/tapped inputs; the rest of 0011 (seats, joining, leaving, the bench,
bots acting on the state everyone saw) stands.

## Context

Playing the game for the first time, at four moves a second, I couldn't keep
up with the bots. A bot chooses every move instantly from the whole board; a
person has to see, decide and press, a fraction of a second behind. The rules
were fair (ADR 0010) but the clock wasn't: the game rewarded reaction time,
which no person has against a program. The README promises a bot that is a
fair teammate and opponent, so this has to change, not just get "easier".

The RL side doesn't care: the environment already advances one step at a time,
and training never sees a clock. Only how the server advances a match changes.

## Options

1. **Slow the clock to one move a second.** Least work, but people still race
   a program that never needs the second, and a 720-move match takes 12
   minutes.
2. **Pure turns: wait until every person has chosen.** Removes the race
   entirely. But one person who wanders off stops everyone.
3. **Turns with a deadline.** A turn resolves as soon as every person in the
   match has chosen, or after 2 seconds, whichever comes first; anyone who
   hasn't chosen stands still. Alone, your choice resolves the turn at once, so
   you play at your own pace and can stop to think. Together, the game moves as
   fast as the slowest ready person, and a distracted one costs at most 2
   seconds a turn.

## Decision

Option 3.

- **A turn resolves** when every seat held by a present person (a page open,
  not covered by a bot) has a choice, or 2 seconds after the turn opened.
  Turns are at least 0.15 seconds apart, so moves stay readable on screen.
- **A choice** is one of the five actions for the current turn. It can be
  changed until the turn resolves; the newest (highest sequence number) wins,
  and a choice sent for a turn that has already resolved is ignored.
- **Everyone sees who is ready**, live: when a person chooses, the others are
  told within a second that they have chosen (not what). The new board goes to
  everyone as soon as the turn resolves. This is how the real-time requirement
  is met in a turn-based game.
- **Bots** choose when the turn resolves, from the board as it stood when the
  turn opened, the board everyone was shown. They never see people's choices.
- **Matches** are capped at 500 turns instead of 720 (rules version 3, ADR
  0010): with people taking time to think, 720 turns ran six to eight minutes.
  Over 120 scripted-bot games, 500 turns still decides 64% of matches.
- The rest of ADR 0011 stands: closed pages are covered after 5 seconds, idle
  ones after 60 (a person who never chooses also costs everyone 2 seconds a
  turn until then), newcomers take a bot's seat, the bench holds up to six.

## Consequences

- People and bots now differ only in how well they choose, not how fast. That
  is the comparison the README's "good teammate" argument needs.
- Holding a key no longer means "keep walking" by itself: the page re-sends the
  held direction once per turn, so a held key still walks, one step a turn.
- A solo game can run as fast as the player presses, so the server checks
  readiness 20 times a second instead of ticking 4 times.
- Matches last a different number of seconds for different groups; the record
  keeps turns, not seconds.
- Checked in `spec/`: a turn resolves as soon as everyone present has chosen;
  it resolves at the deadline when someone hasn't; seats played by bots never
  hold a turn; others are told within a second that someone has chosen; a
  choice for a past turn is ignored.

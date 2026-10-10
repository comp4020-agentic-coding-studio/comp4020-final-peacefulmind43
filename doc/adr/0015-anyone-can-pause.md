# 0015. Anyone in a match can pause it, and anyone can carry on

Status: accepted (2026-10-10), amended 2026-10-11 (pausing needs the page open, ADR 0016)

## Context

People asked for a pause button. Alone, pausing is simple: the game waits for
you. With several people in a match, a pause stops everyone, so someone has to
be allowed to do it, and someone has to be allowed to undo it.

## Options

1. **Anyone can pause, for at most a minute.** Nobody can hold a match hostage,
   but a real interruption (a phone call, a question in a crit) may need longer.
2. **Only when you're the only person in the match.** Never affects anyone
   else, but people playing together can't pause at all, which is when it's
   most needed.
3. **Pause by vote.** Fair, but slow and fiddly for a few friends.
4. **Anyone can pause, with no time limit, and anyone can carry on.** One press
   pauses; one press by anyone in the match resumes.

## Decision

Option 4. The game is for a few friends, who can sort out a pause between
themselves; a time limit would cut off exactly the interruptions a pause is
for, and anyone who disagrees can resume with one press.

- Only people with a seat and the page open can pause or resume; people
  watching can't, and nor can someone whose page is closed, even while their
  seat is kept for them (amended 2026-10-11, ADR 0016).
- Everyone in the match sees, live, who paused and who resumed.
- While paused, no turn resolves and nobody's seat is handed to a bot, however
  long the pause lasts. On resuming, everyone's idle clock starts again, so a
  long pause doesn't make anyone look idle.
- The watch arena (bots only) has no pause.

## Consequences

- One person can stop a match until someone else resumes it. With friends
  that is fine; it would not be with strangers, and a time limit or vote would
  be the change if that ever mattered.
- Pauses and resumes are logged, so the activity log can tell a match's story
  including its interruptions.
- Checked in `spec/`: a pause stops turns for everyone and others see who
  paused; anyone with a seat can resume and turns carry on; watchers can't pause,
  and nor can someone whose page is closed.

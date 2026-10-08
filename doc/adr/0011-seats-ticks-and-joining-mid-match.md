# 0011. Seats, ticks, and joining a match already under way

Status: accepted (2026-10-08); amended 2026-10-09, before it was merged, in
the two places marked "Amended". The crit 9 decision. Supersedes ADR 0001's
"updates only go from server to browser"; the rest of 0001 stands.

## Context

Crit 9 asks for one decision about how the app behaves with several people in
it at once, made from the README's definition of good. The README's good is a
game a few friends can play at any time, where a bot is a good teammate and
never an unfair one. Several things follow from "several people at once": how
moves travel, what a slow connection sees, what happens when someone leaves,
and, the decision this record is mainly about, what happens when someone
arrives while a match is being played.

## Options for someone arriving mid-match

1. **Take over a bot's seat straight away.** You play within a second, from
   wherever that bot was, carrying its flag if it had one. Two people opening the
   page land in the same match at once. The cost: you inherit a score and a
   position you didn't earn, and the team size can't change until the next match.
2. **Watch until the next match starts.** Every match is played start to finish
   by the same people, so it is complete and fair, and the team size can be set
   for who is there. The cost: up to three minutes of waiting, which reads as
   "broken" to a first-time visitor and to a marker opening two windows.
3. **Join at once in an extra seat.** No bot is displaced, but teams become
   uneven, and the map can't grow mid-match.

## Decision

Option 1. A game for friends at any time means no waiting; and the bot you
replace was a stand-in for a person in the first place.

How the rest works:

- **The server decides everything.** The game state lives only on the server.
  The browser sends inputs and draws what it is sent.
- **Ticks.** One loop runs every arena at 4 ticks a second on a fixed clock
  (tick n is due at start + n × 0.25 s, so it never drifts). No database writes
  or logging happen inside a tick.
- **Inputs travel by POST, state by server-sent events.** Each seat keeps the
  direction being *held* and a one-shot *tapped* direction; a tick uses the tap
  if there is one, else the held direction, then clears the tap, so a quick tap
  between two ticks still moves you. Each input carries a sequence number, and
  the server ignores older ones, because two requests can arrive out of order.
  ADR 0001 said server-sent events stop fitting if the browser needs to send
  messages; for a few inputs a second, plain requests are enough, and keep one
  log line per action. If key-to-screen delay passes about 400 ms on a slow
  connection, this gets revisited.
- **A slow connection sees the newest state, never a backlog.** Each open page
  holds at most one waiting update; a newer one replaces it.
- **Bots don't peek.** A bot chooses its move from the state broadcast at the
  previous tick, never from the inputs people have just sent.
- **Seats belong to a visitor** (the cookie). Two tabs with one cookie control
  one seat.
- **Leaving.** If your page closes, a bot covers your seat after 5 seconds
  (long enough to survive a dropped connection), and everyone sees "bot
  covering for Visitor ab12". If the page stays open but you do nothing for 60
  seconds, the same happens; your next input takes the seat back. Coming back
  during the match always gives you your seat back.
  *Amended:* the first version said 5 seconds without input. Standing still is
  a real tactic (guarding the flag), and a held key sends one request, so
  silence doesn't mean someone has gone.
- **Team size** is set when a match starts: 2v2 for up to four people, 3v3 for
  five or six. A newcomer takes a bot's seat on the team with fewer people.
  If every seat is already a person and there are six people or fewer, the
  newcomer waits on the bench and plays from the next match, which grows to
  3v3. Only a seventh person opens a second shared arena.
  *Amended:* the first version opened a second arena as soon as the seats were
  full, which meant a group of five or six could never play one match together.
- **Restarts.** A redeploy or a stopped machine ends live matches; on start-up
  they are marked interrupted, not lost.

## Consequences

- A marker's two windows are in the same match within a second, and someone
  alone plays at once with a bot teammate.
- A newcomer may join a match that is already 0–2. The page says so ("you took
  over from a bot"), and match records note who played which ticks, so nobody's
  record counts ticks they didn't play.
- Checked in `spec/`: two visitors land in the same match; a newcomer replaces a
  bot within a second; a closed page hands its seat to a bot within 5 seconds
  while the match keeps going; many inputs in one tick still move a player at
  most one cell; in a seeded private arena, bot moves depend only on the
  previous tick's state.

# 0022. Two people acting on the same thing at once

Status: accepted (2026-10-16). Supersedes only the "one press by anyone
resumes" mechanics of ADR 0015 (a press toggled the pause). Who may pause
(ADR 0015, 0016) is unchanged.

## Context

Several people play one match, so two requests can arrive at the same moment
about the same thing. The week 10 lecture calls the bad case a lost update:
both read the old state, both write, and one write undoes the other.

There are two shared things a person can change here.

- **Moves.** Every seat chooses each turn, and everyone moves at the same time
  (ADR 0010). The server keeps one choice per seat and the engine resolves all
  of them together when the turn closes (ADR 0012). A person can only choose
  for their own seat (ADR 0016), so two people never write the same choice.
  Two choices at once both count: that is the game.
- **Pause.** One flag for the whole match. The button sent "toggle", so if two
  people pressed Pause at the same moment, the first request paused the match
  and the second resumed it. Both meant "pause", and the match ran on.

## Options

1. **Toggle (as before).** Simple, but the result depends on what the server
   saw last, not on what people asked for. Two Pause presses cancel out.
2. **Set to a state.** The request says what the person wants:
   `{"paused": true}` or `{"paused": false}`, from what their button shows. The
   server sets that state. Asking for the state the match is already in
   changes nothing.
3. **A version check.** The request carries the version of the state the
   person saw; the server refuses (409) if it changed since. Nothing is lost
   silently, but the person who loses the race gets an error for something
   that already happened the way they wanted, and must try again.

## Decision

Option 2.

- `POST /arena/pause` needs `paused` (true or false); without it the server
  answers 400. There is no old client to keep working: the page's script loads
  by a hash of its contents, so a deploy brings the new one.
- Two requests that agree agree: the match is paused once, everyone is told
  once, and the log has one pause line. The repeat answers 200 with the
  current state (who paused it).
- Two requests that disagree (one Pause, one Resume at the same moment): the
  last one the server handles wins. Both people see the result live, and
  either can press again.
- The page sends what its button shows: Pause asks for paused, Resume asks for
  running. The P key does the same.

## Consequences

- A pause can no longer be lost to someone else's press of the same button.
- Opposite presses at the same moment still race, and the result is whichever
  came last. A version check (option 3) would catch that, at the cost of an
  error for one person; for a few friends, seeing the result and pressing
  again is cheaper.
- `Hall.toggle_pause`, named in ADR 0016's table, is now `Hall.set_pause`.
- Checked in `spec/arena.test.ts`: "keeps a match paused when two people press
  Pause at the same moment..." and "counts both choices when two people choose
  in the same turn...".

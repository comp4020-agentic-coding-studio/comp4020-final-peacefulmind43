# Reading the logs

The server writes one JSON line to stdout for each thing a person does
(ADR 0006, 0014). The same lines, except moves, also go into the database and
appear on `/log`. This page says how to read them.

## Tail the logs on Fly

```sh
mise exec -- flyctl logs -a comp4020-final-peacefulmind43
```

Fly puts a time and the machine in front of each line. Moves arrive several
times a second, and there is also one line for each request (see "Request
lines" below). For a story, hide both and keep only the sentence:

```sh
mise exec -- flyctl logs -a comp4020-final-peacefulmind43 \
  | grep --line-buffered -o '{"event".*}' \
  | grep --line-buffered -v -E '"event": "(choice|request|stream_open|stream_close)"' \
  | jq -r --unbuffered .text
```

## What a line says

Every line has `event` (what happened), `visitor` (who: a public label like
`Visitor b17e82`, or a bot), `at` (Unix time), and `text`, a plain sentence.
Lines about a match also have `arena`, `match`, `seat` and `team`. `seat`
counts from 0, so seat 0 is "player 1" on the page. The cookie is never in a
line.

| event | example `text` |
|---|---|
| visit | `Visitor b17e82 opened the game` |
| join | `Visitor be016f joined red as player 3 in match 1` |
| choice | `Visitor b17e82 chose right for player 1, turn 2` |
| pause | `Visitor be016f paused match 1 (player 3, red)` |
| resume | `Visitor b17e82 resumed match 1 (player 1, blue)` |
| tag | `A bot (fcp1) got caught (player 2, blue)` |
| pickup | `Visitor b17e82 picked up the flag (player 1, blue)` |
| capture | `Visitor b17e82 scored! (player 1, blue)` |
| leave | `Visitor be016f closed the game page (player 3, red)` |
| takeover | `Visitor be016f has gone; a bot now plays player 3 for them` |
| reclaim | `Visitor be016f came back to player 3` |
| match_end | `Arena main finished match 1, blue 2, red 1` |

A full line looks like this:

```json
{"event": "pause", "visitor": "Visitor be016f", "at": 1791637013, "arena": "main", "match": 1, "seat": 2, "team": "red", "text": "Visitor be016f paused match 1 (player 3, red)"}
```

If a person caused the line (a page they opened, a button they pressed), it
also has `request`: the id of that request (see below). Lines from the game
clock (tag, pickup, capture, takeover, match_end) have no `request`, because
no request caused them.

A takeover comes 5 seconds after a leave, unless the person comes back first
(then you see a reclaim). After 60 seconds with no move, a takeover says "went
quiet" instead.

## Request lines and request ids

The server also writes one line for each request it answers. Each request
gets a short id of 8 letters and digits, like `c0cdafcb`. The same id is in
the response header `x-request-id`, in the request line, and in every event
line that the request caused. So you can tie them together: find the `pause`
line, take its `request`, and search for it.

```json
{"event": "request", "request": "c0cdafcb", "method": "POST", "path": "/arena/pause", "visitor": "Visitor deb6ae", "status": 200, "ms": 0, "at": 1792122612, "text": "POST /arena/pause 200 in 0 ms"}
{"event": "pause", "visitor": "Visitor deb6ae", "at": 1792122612, "arena": "p-OPw04yF9", "match": 1, "seat": 0, "team": "blue", "request": "c0cdafcb", "text": "Visitor deb6ae paused match 1 (player 1, blue)"}
```

| event | what it means |
|---|---|
| request | one request answered: `method`, `path`, `status`, `ms` (how long it took) and `visitor` (the public label, or `null` with no cookie) |
| stream_open | a page opened a live stream (`/arena/events` or `/log/events`) |
| stream_close | that stream closed; `ms` says how long it was open |
| request_error | the server failed on a request it did not expect to fail; it answered 500 |

To find every line about one request:

```sh
mise exec -- flyctl logs -a comp4020-final-peacefulmind43 | grep c0cdafcb
```

A live stream stays open for minutes, so it gets a line when it opens and a
line when it closes, not one for each keep-alive. Files under `/static` get no
line. The line never has the cookie, the request body or the query string.

## Telling two people apart

Each Chrome profile has its own cookie, so it is its own person. Two tabs in
one profile are one person. The game page tells each person their label:
"You are Visitor b17e82, player 1 on blue." Ask each player to read theirs out
at the start, and match it to the `join` lines.

## A narration script for the crit

1. "Visitor b17e82 opened the game and joined blue as player 1. Visitor be016f
   joined red as player 3. The other seats are bots, each shown by its name
   (fcp1, cur4 or scripted)."
2. "Both are choosing now: each choice line has their label and their seat,
   so one person can never move the other's player."
3. "Visitor be016f paused match 1. Visitor b17e82 resumed it: anyone with a
   seat and the page open can do that, and people watching can't. If both
   press Pause at the same moment, the match is paused once, with one pause
   line (ADR 0022)."
4. "Visitor be016f closed the page. Five seconds later a bot took over player
   3 for them, and the match went on."
5. "Visitor be016f came back to player 3. The match ended blue 2, red 1, and
   its replay is saved."

## After the crit: debugging the deployed app

The same logs are how the live app is debugged. A few lines are not about
people:

- `request_error`: a request failed in a way the code did not expect. It has
  the request id, the path, the error type and message, and the last three
  places in the code (`trace`). The person saw "Something went wrong" with
  the same id, so if they tell you the id, you can find the line.
- `tick_error`: one arena failed a turn (the others keep running). It has the
  arena and the error.
- `slow_tick`: a check of the arenas took too long, with how many ms.
- `log_error`: a batch of moves could not be saved.
- `matches_interrupted`: on start-up, how many live matches a restart cut off.

Fly keeps stdout for a short time only. What lasts is in SQLite on the Fly
volume: the activity log (`/log`, `/api/log`), every finished match
(`/api/matches/recent`), its moves (`/api/matches/<id>/choices`) and its replay
(`/api/matches/<id>/replay`). To find what someone did later, start from their
label.

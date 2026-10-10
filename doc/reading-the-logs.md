# Reading the logs

The server writes one JSON line to stdout for each thing a person does
(ADR 0006, 0014). The same lines, except moves, also go into the database and
appear on `/log`. This page says how to read them.

## Tail the logs on Fly

```sh
mise exec -- flyctl logs -a comp4020-final-peacefulmind43
```

Fly puts a time and the machine in front of each line. Moves arrive several
times a second, so for a story, hide them and keep only the sentence:

```sh
mise exec -- flyctl logs -a comp4020-final-peacefulmind43 \
  | grep --line-buffered -o '{"event".*}' | grep --line-buffered -v '"choice"' \
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
| tag | `A bot (cur4) got caught (player 2, blue)` |
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

A takeover comes 5 seconds after a leave, unless the person comes back first
(then you see a reclaim). After 60 seconds with no move, a takeover says "went
quiet" instead.

## Telling two people apart

Each Chrome profile has its own cookie, so it is its own person. Two tabs in
one profile are one person. The game page tells each person their label:
"You are Visitor b17e82, player 1 on blue." Ask each player to read theirs out
at the start, and match it to the `join` lines.

## A narration script for the crit

1. "Visitor b17e82 opened the game and joined blue as player 1. Visitor be016f
   joined red as player 3. The other seats are bots, named as cur4."
2. "Both are choosing now: each choice line has their label and their seat,
   so one person can never move the other's player."
3. "Visitor be016f paused match 1. Visitor b17e82 resumed it: anyone with a
   seat and the page open can do that, and people watching can't."
4. "Visitor be016f closed the page. Five seconds later a bot took over player
   3 for them, and the match went on."
5. "Visitor be016f came back to player 3. The match ended blue 2, red 1, and
   its replay is saved."

## After the crit: debugging the deployed app

The same logs are how the live app is debugged. A few lines are not about
people:

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

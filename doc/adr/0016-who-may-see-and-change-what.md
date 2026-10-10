# 0016. Who may see and change what

Status: accepted (2026-10-10), amended 2026-10-11 (pausing needs the page open).
Narrows one sentence of ADR 0011 and one of ADR 0015 (marked below).

## Context

Crit 10 asks that the app tell people apart, and that the server checks what
each person may see and change. Here several people act on one match at once:
who may move which player, who may pause, and what can anyone read about others?

## Options for telling people apart

1. **Accounts with a login.** Strong identity, but friends must sign up before
   the first move, and the game must keep passwords or trust another service.
2. **A name you choose.** Friendly, but anyone can type someone else's name.
3. **An anonymous cookie with a public label.** The first visit sets a random
   cookie; others only ever see a short label made from it ("Visitor ab12cd").

## Decision

Option 3. You play the moment the page opens, and nobody can act under your
label, because it comes from a secret only your browser holds. The cost:
clearing cookies, another browser or another device makes you a new person, and
nothing proves who is behind a label. Anyone holding a cookie could act as that
visitor, so the cookie is never shown or logged.

**Changing.** The server finds your seat from your cookie. A request never
names a seat; a seat field in it is ignored. Spec checks are in
`spec/arena.test.ts` unless marked.

| Action | Who may | Checked in | Spec check |
|---|---|---|---|
| Move a player | that seat's person only | `main.py` `arena_input`, `arena.py` `Hall.choose` | "only ever acts for your own seat..."; "refuses moves and pauses from people on the bench, people watching..." |
| Pause, resume | anyone seated in the match, with the page open | `main.py` `arena_pause`, `Hall.toggle_pause` | "lets anyone in a match pause it..."; "doesn't let someone without a seat pause..."; "doesn't let someone whose page is closed pause..." |
| Get your seat back | you | `Hall.arrive`, `Hall.seat_person`, `Hall.choose` | "keeps a seat for someone who reloads..."; "gives your seat back when you come back..." |
| Create a private arena | the operator key only | `main.py` `operator` | "refuses a choice from someone without a seat, and private arenas..." |
| Watch | anyone, with no seat | `Hall.arrive` | "lets people watch bots play..." |
| Read `/log`, live view, replays | anyone; labels only | `activity.py` `view`, `visitor_label` | "never sends a visitor's cookie..."; "tells each visitor their own public label..." |
| Read a match's choices | anyone, once it is over | `main.py` `api_choices` | "keeps a live match's choices to itself..." (`spec/replay.test.ts`) |

*Amended from ADR 0011*, which said coming back "always" gives your seat back.
During the 5-second grace period nobody can take it. Once a bot covers it, a
newcomer may, since a covered seat is not a person playing.

*Amended 2026-10-11, and narrows ADR 0015*, which said anyone with a seat can
pause. Now you also need the page open. Someone who closed the page still owns
their seat through the grace period, so they can come back to it, but they
can't see the match, so a request from them to pause or resume gets 409, the
same as having no seat.

**Seeing.** Everyone sees the whole board, the same board the bots see (README,
"Bots are fair"; "shows everyone in a match the same board"). During a turn,
others learn that you have chosen, never what (ADR 0012). The page tells you
your own label, so you can find yourself in the log.

## Consequences

- Two browsers are two players at once, with no sign-up. One person on two
  devices is two people, and the game can't join them.
- Private arenas are for the spec and demos. Their ids show in `/log`, so
  anyone can join one; nothing private is played there.
- Every choice is in the stdout log on Fly, which only the owner can read.

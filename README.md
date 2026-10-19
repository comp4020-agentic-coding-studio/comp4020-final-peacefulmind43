# Capture the flag

A capture-the-flag game where people and bots play on the same teams.
Open [the game](https://comp4020-final-peacefulmind43.fly.dev/) and you
join whoever else has it open. Move with the arrow keys or W A S D, or tap
the pad on a phone. To play together, open a second window. Your past
matches and replays are at [/me](https://comp4020-final-peacefulmind43.fly.dev/me).

## Who it is for

A few friends, often in one room. Robin Sloan calls an app for a few
people a ["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/).
It can be narrow and skip logins. Playing with someone in the same room
is more fun than with someone you can't see
([Gajadhar et al. 2008](https://doi.org/10.1007/978-3-540-88322-7_11),
abstract only). The bots let a game start when friends are missing.

## What good means here

A game can work and still be unfair. Good means five things.

1. A game can always start. You can play alone with bots. A newcomer takes
   a bot's seat at once. If you leave, a bot covers you within five seconds.
2. Bots see the board people see, but never what people just pressed.
3. Speed does not decide. At four moves a second I could not keep up with
   the bots, so a turn waits for everyone, up to 2 seconds. WCAG 2.2.1
   ([Timing Adjustable](https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html))
   asks that a user can turn a time limit off. So anyone can pause, with
   no time limit. The catch
   ([ADR 0021](doc/adr/0021-playing-alone-keeps-the-deadline.md)) is that
   someone who needs more than 2 seconds every turn must pause every turn.
   Nor should strength. When a person plays, a team with no person gets a
   weaker bot, cur4snap, so the match is close to even
   ([ADR 0023](doc/adr/0023-balanced-opponents.md)).
4. A bot plays for its team. It is rewarded when its team scores, and
   /study counts who scored, next to a larger test of bots beside bots.
5. Every bot is named, though it costs something. A bot made people cooperate
   more only while they did not know it was a bot
   ([Ishowo-Oloko et al. 2019](https://doi.org/10.1038/s42256-019-0113-5),
   abstract only). Hiding it from friends is worse.

I compare bots by behaviour, because a few short, casual sessions would
give ratings too noisy to use.
[Siu et al. 2021](https://arxiv.org/abs/2107.07630) found two bots with
similar scores where people clearly liked one more, and behaviour can
miss that. I accept the gap.

## Checked and judged

Checks in spec/ and tests/ run on every change. Point 1 uses
"lets a visitor alone play with bots", "lets a newcomer take over a bot's
seat" and "hands a closed page's seat to a bot within five seconds".
Point 2 has "shows everyone in a match the same board" and
tests/test_fairness.py.

Point 3 has "resolves a turn as soon as the only person has chosen, and at
the deadline", "lets anyone in a match pause it" and "keeps a match paused
when two people press Pause". The weaker bot has "names the balanced bot
on the other team when one person plays". Point 5 has "names every bot
seat by its real bot" and "has no rating endpoint".

Point 4 is judged from /study and the [RL evaluation](doc/rl/README.md),
and a test keeps their numbers the same. Whether a match is even for
people, and fun, is judged by playing.

## What I chose not to build

There are no accounts, since the game only needs to tell people apart.
There is no chat, because friends talk in the room. There are no ratings
of bots or people.

## Limits

I have very little human data. Every partner in the RL evaluation is a bot.

The teammate bot, fcp1, holds up next to weak partners but scores almost
everything itself, so point 4 is not met.

I chose the weaker bot by testing it with a stand-in program, not people.
Real people may be much weaker or stronger, and most such games still end
in a draw.

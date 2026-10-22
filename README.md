# Capture the flag

A capture-the-flag game where people and bots share teams.
Open [the game](https://comp4020-final-peacefulmind43.fly.dev/) to
join anyone there. Move with the arrow keys or W A S D, or tap
the pad on a phone. To play together, open a second window. Your
matches and replays are at [/me](https://comp4020-final-peacefulmind43.fly.dev/me).

## Who it is for

It is for a few friends, often in one room. Robin Sloan calls an app
for a few people a ["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/).
It can be narrow and skip logins. Playing next to someone is more fun
than with someone you can't see
([Gajadhar et al. 2008](https://doi.org/10.1007/978-3-540-88322-7_11),
abstract only). Bots fill in for missing friends.

## What good means here

A game can work and still feel unfair. Good means five things to me.

1. A game can always start. You can play alone with bots. A newcomer takes
   a bot's seat at once. If you leave, a bot covers you within five seconds.
2. Bots see the board people see, but never what people just pressed.
3. Speed does not decide. At four moves a second I could not keep up with
   bots, so a turn waits for everyone, up to 2 seconds. WCAG 2.2.1
   ([Timing Adjustable](https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html))
   asks that users can turn time limits off. So anyone can pause with
   no limit. The catch
   ([ADR 0021](doc/adr/0021-playing-alone-keeps-the-deadline.md)) is that
   someone needing over 2 seconds a turn must pause every turn.
   Strength should not decide either. When a person plays, an all-bot team gets a
   weaker bot, cur4snap, so the match is close
   ([ADR 0023](doc/adr/0023-balanced-opponents.md)).
4. A bot plays for its team. It is rewarded when its team scores, and
   /study counts who scored, next to a larger bot-only test.
5. Every bot is named, at a cost. A bot made people cooperate more only
   while they didn't know it was a bot
   ([Ishowo-Oloko et al. 2019](https://doi.org/10.1038/s42256-019-0113-5),
   abstract only). Hiding it from friends is worse.

I compare bots by what they do, because a few casual sessions give
noisy ratings. [Siu et al. 2021](https://arxiv.org/abs/2107.07630) found people
clearly liked one of two similarly scored bots. My numbers miss that,
and I accept it.

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

Point 4 is judged, from /study and the [RL evaluation](doc/rl/README.md),
and a test keeps their numbers the same. Whether a match is fun I judge by
playing.

## What I chose not to build

No accounts, since a cookie is enough to tell people apart. Friends
talk in the room, so there is no chat. Nothing is rated.

## Limits

I have little human data. Every RL evaluation partner is a bot.

The teammate bot, fcp1, holds up next to weak partners but scores almost
everything itself, so point 4 is not met yet.

I tested the weaker bot with a stand-in program, not people. Real people
may be weaker or stronger, and most such games still end in a draw.

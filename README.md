# Capture the flag

A capture-the-flag game where people and bots play on the same teams.
Open the page and you join a match with whoever else has it open.

## Who it is for

A few friends, often in one room. Two may be free, or six.
Robin Sloan calls an app for a few people a
["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/).
It can be narrow and skip logins, so I built no accounts. Playing with
someone in the same room is more fun than with someone you can't see
([Gajadhar et al. 2008](https://doi.org/10.1007/978-3-540-88322-7_11),
abstract only). The bots let a game start. They don't replace friends.

## What good means here

A game can work and look nice and still be unfair. Good means:

1. **A game can always start.** You can play alone with bots. A newcomer
   takes a bot's seat at once. If you leave, a bot covers you within five
   seconds.
2. **Bots are fair.** They see the board people see, never what
   people just pressed.
3. **Speed does not decide.** At four moves a second I could hardly keep up
   with the bots, so a turn now waits for everyone, up to 2 seconds. WCAG 2.2.1
   ([Timing Adjustable](https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html))
   asks that a user can turn a time limit off. So anyone can pause,
   with no time limit, and press again to carry on. The catch
   ([ADR 0021](doc/adr/0021-playing-alone-keeps-the-deadline.md)) is that
   someone who needs more than 2 seconds every turn must pause every turn.
4. **A bot is a teammate, not the star.** It is rewarded when its team scores,
   and I count who scored, the person or the bot.
5. **Every bot is named.** It costs something. A bot made people cooperate more
   only while they did not know it was a bot
   ([Ishowo-Oloko et al. 2019](https://doi.org/10.1038/s42256-019-0113-5),
   abstract only). Hiding it from friends is worse.

I compare bots by behaviour, not ratings. A few short, casual
sessions would give ratings that are too noisy.
[Siu et al. 2021](https://arxiv.org/abs/2107.07630) found two bots with
similar scores where people clearly liked one more. Behaviour can miss that. I accept
the gap.

## Checked and judged

`spec/` and `tests/` check these on every change.

- 1: "lets a visitor alone play with bots", "lets a newcomer take over a
  bot's seat", "hands a closed page's seat to a bot within five seconds".
- 2: "shows everyone in a match the same board", and
  `tests/test_fairness.py`. A second engine must agree every turn.
- 3: "resolves a turn as soon as the only person has chosen, and at the
  deadline", "lets anyone in a match pause it", "keeps a match paused when
  two people press Pause".
- 5: "names every bot seat by its real bot", "has no rating endpoint".

Point 4 is judged from `/study` and the [RL evaluation](doc/rl/README.md).
Fun is judged by playing.

## What I chose not to build

- **No accounts.** The game only tells people apart.
- **No chat.** Friends talk in the room, and chat favours fast typers.
- **No ranking of people** or **ratings of bots.**

## Limits

- No human ratings, and very little human data.
- Every partner in the RL evaluation is a bot.
- The deployed bot, fcp1, holds up next to weak partners, but it is not a
  team player. It scores almost everything itself and does not adapt to you,
  so point 4 is not met. A person with a bot teammate rarely wins. The
  other team is two strong bots, and a person is weaker than a bot. For now I
  chose not to add difficulty settings or more training.

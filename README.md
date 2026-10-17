# Capture the flag

A small capture-the-flag game where people and bots play on the same teams.
Open the page and you are in a match with whoever else opened it.

## Who it is for

A few friends, often in one room, whether two are free or six. Robin Sloan
says an app for a few people can be a
["home-cooked meal"](https://www.robinsloan.com/notes/home-cooked-app/):
narrow, with no logins, so I built no accounts. Playing with someone in the
same room is more fun than with an unseen player
([Gajadhar et al. 2008](https://doi.org/10.1007/978-3-540-88322-7_11),
abstract only), so bots are there to let a game start, not to replace
friends.

## What good means here

A game can work and look nice and still be unfair. Here, good means:

1. **A game can always start.** You play alone with bots; others take a bot's
   seat at once; if you leave, a bot covers you within five seconds.
2. **Bots are fair.** They see the board people see, and never what people
   just pressed.
3. **Speed does not decide.** At four moves a second I found it really hard
   to keep up with the bots, so a turn now waits for everyone, up to 2
   seconds. WCAG 2.2.1
   ([Timing Adjustable](https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html))
   asks that a user can turn a limit off. My answer is pause: anyone can
   pause, with no time limit, and press again to carry on. The limit
   ([ADR 0021](doc/adr/0021-playing-alone-keeps-the-deadline.md)): someone who
   needs more than 2 seconds every turn must pause every turn.
4. **A bot is a teammate, not the star.** It is rewarded when its team
   scores, and I count who scores: the person or the bot.
5. **Every bot is named.** This costs something: a bot made people cooperate
   more only while they did not know it was a bot
   ([Ishowo-Oloko et al. 2019](https://doi.org/10.1038/s42256-019-0113-5),
   abstract only). Hiding it from friends is worse.

I compare bots by behaviour, not ratings. Classmates at crits mostly play
carelessly, so ratings would be noise. But
[Siu et al. 2021](https://arxiv.org/abs/2107.07630) found two bots with
similar scores where people clearly preferred one. Behaviour can miss that,
and I accept the gap.

## Checked and judged

Checked on every change by `spec/` and `tests/`:

- 1: "lets a visitor alone play with bots", "lets a newcomer take over a
  bot's seat", "hands a closed page's seat to a bot within five seconds".
- 2: "shows everyone in a match the same board"; `tests/test_fairness.py`;
  a second engine must agree every turn.
- 3: "resolves a turn as soon as the only person has chosen, and at the
  deadline"; "lets anyone in a match pause it"; "keeps a match paused when
  two people press Pause".
- 5: "names every bot seat by its real bot"; "has no rating endpoint".

Judged: point 4, from `/study` and the [RL evaluation](doc/rl/README.md);
and whether it is fun, by playing.

## What I chose not to build

- **No accounts.** The game only tells people apart.
- **No chat.** Friends talk in the room; chat favours fast typers.
- **No ranking of people** or **ratings of bots.**

## Limits

- No human ratings, and very little human data.
- Every partner in the RL evaluation is a bot.
- The deployed bot, fcp1, holds up beside weak partners but is not a team
  player: it scores almost everything itself and does not adapt to you, so
  point 4 is not met. A person with a bot teammate rarely wins: the
  opponents are two strong bots, and a person is weaker than a bot. I
  chose not to add difficulty settings or more training for now.

# 0017. A blind study of which bot is the better teammate

Status: accepted (2026-10-13). Supersedes, for teammates only, the CLAUDE.md
rule "Never hide which bot is playing" and the README's "every bot seat says
whether a scripted or a trained bot is playing". Opponent bots are still named.

## Context

The README's core claim is that a bot can be a good teammate for people. The
only evidence so far is that the trained bot (cur4) beats the scripted bot,
bots against bots. That says the bot plays well, not that people are glad to
have it on their team. The way to find out is to ask the people who played
with it. But if the page says "trained bot", people may rate what they expect
of a trained bot, not what it did.

## Options

1. **Keep naming every bot, and ask people to rate it.** Simple and fully
   open, but the name can change the answer.
2. **Blind the teammate, ask, then reveal.** The bot on your team is drawn at
   random each match and shown as "Bot A" or "Bot B". After the match you
   rate it, or skip, and only then see which bot it was.
3. **No ratings, only behaviour.** Count who scores on each team. Free of
   bias from names, but a bot that scores everything itself may not be a good
   teammate, so behaviour alone can't answer the question.

## Decision

Option 2, together with the behaviour of option 3.

- **The draw.** In the shared arena, each match draws, for each team, one bot
  from `TEAMMATE_BOTS` in `app/game/study.py` (now "scripted" and "cur4"; a
  new bot is added by name). The letter for each bot is also drawn, so "Bot
  A" does not always mean the same bot. A team gets its drawn bot from the
  moment a person sits on it; a team with no person keeps the deployed bot,
  named as before. The seed, the bot and the letter are saved per team in
  `match_study` (migration 0010), only for teams where the drawn bot played
  beside a person.
- **What changes for the bot: only which bot plays.** Every bot still chooses
  from the board as it was shown when the turn opened (CLAUDE.md).
- **The question.** When the match ends, each person on such a team is asked
  "Was your bot teammate helpful?", 1 to 5, or Skip, with the keyboard or a
  tap. The server accepts an answer only from someone who held a seat on that
  team in that match, and only once (a skip counts as the answer). The answer
  returns which bot it was, and the page shows it.
- **Behaviour.** For each team in the study, the captures made by people and
  by bots, from the activity log, so the results can talk about roles, not
  only ratings.
- **Results are public** at `/study`: for each bot, matches, ratings, skips,
  counts per score, and captures by people and by bots. The mean and a 95%
  interval appear only from 10 ratings up; below that, only counts.
- **People are told before they play**, on the game page, that their bot
  teammate may be blinded and why, with a link to `/study`.

## Consequences

- The README can argue from what people said and did, with n stated, instead
  of only from bots against bots.
- For one match, a person does not know which bot is on their team. This is
  the cost; the reveal right after the match, and the note before it, are
  how the game stays honest.
- People may get the weaker bot as a teammate half the time. With "scripted"
  and "cur4" both able to play, that is acceptable for a short game.
- One person can rate many matches, so ratings are not independent, and the
  interval is too narrow. The page says so.
- The log line for an answer says that someone answered, not what, so a
  teammate still rating can't be swayed.
- Checked in `spec/study.test.ts`: the teammate shows only as Bot A or Bot B
  during the match, in the stream and the live view; only people who played
  beside it may rate, once; a skip counts; a team of only people is not asked;
  the results page states n and shows no cookies. `tests/test_study.py` checks
  the draw (seeded, both letters for both bots) and the interval.

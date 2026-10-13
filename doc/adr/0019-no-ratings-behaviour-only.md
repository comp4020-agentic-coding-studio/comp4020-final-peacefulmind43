# 0019. No ratings: compare bot teammates by behaviour only

Status: accepted (2026-10-13). Supersedes the parts of ADR 0017 about
blinding and ratings, including its rule on who may rate (people who held a
seat on that team, once), which ADR 0016's who-may-do-what table never
listed. ADR 0017's random draw of the teammate bot stays.

## Context

ADR 0017 hid the teammate bot as "Bot A" or "Bot B", asked "Was your bot
teammate helpful?" after each match, and only then said which bot it was.
Before the first crit with it, I looked again at who would answer. At crits,
classmates mostly play a match or two quickly and carelessly, to see the
game. Their answers would be noise, and the blinding costs every one of them
a match where they don't know which bot they have.

## Options

1. **Everyone rates, blinded (ADR 0017).** The most answers, but mostly from
   careless play, so the numbers would mean little; and everybody is blinded.
2. **Only the owner rates, blinded.** A one-rater blind pilot: careful
   answers, and only the owner's team is blinded. It needs an owner sign-in
   page, a cookie signed with a key, and rules for a team where the owner
   plays beside a classmate. All that for n = 1 rater, who knows the project
   and may guess the bot from how it plays.
3. **No ratings, behaviour only.** Keep the random draw of the teammate bot
   and compare what happened on teams with each bot: who scored, the people
   or the bot.

## Decision

Option 3. Classmates' ratings would be noise, and owner-only ratings add a
sign-in, a key-signed cookie and blinding rules for a one-rater pilot that is
not worth the complexity.

- **The draw stays.** In the shared arena, each match draws one bot per team
  from `TEAMMATE_BOTS` in `app/game/study.py` and records it in
  `match_study`, as ADR 0017 said. The draw no longer has letters.
- **Every bot is named, always.** Teammates too, during and after the match
  (CLAUDE.md, "Never hide which bot is playing").
- **No question, no endpoint.** `POST /api/matches/{id}/rating` is removed;
  the game page and `/me` ask nothing. `/me` shows which bot you had.
- **`/study` shows behaviour only:** for each teammate bot, matches, people,
  and captures by people and by bots on those teams; and for each person
  (label only), matches with each bot, their own captures, and their bot
  teammate's captures. It states n and says matches are not independent.
- **No new migration.** The `study_ratings` table (migration 0010) stays,
  unused, since a committed migration is never edited. Its rows from before
  this change are not shown. The `letter` column of `match_study` is now
  written empty.

## Consequences

- There is no subjective measure of "helpful". The evidence is behaviour
  only, and a bot that scores everything itself may still be a poor
  teammate; the per-person captures are there to show that case.
- Nobody plays a match without knowing which bot is on their team.
- Less code: no sign-in, no blinding rules, no question to get right on a
  phone.
- Checked in `spec/study.test.ts`: every bot seat shows its real name in the
  stream and the live view; the draw is recorded and counted on `/study` and
  `/me`; the rating endpoint answers 404 or 405 and no page asks the
  question. `tests/test_study.py` checks the draw and that a study match
  names its bots and records the drawn one.

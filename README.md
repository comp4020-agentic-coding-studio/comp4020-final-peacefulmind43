# Capture the flag

A small capture-the-flag game where people and bots play on the same teams.
Open the page and you are in a game: alone, with a bot as your teammate, or
with anyone who opens it at the same time.

## Who it is for

A few friends who want a short game together, whether two of them are free or
six. Empty seats are filled by bots, so a game can always start, and the bots
have to be teammates worth having. To try it with someone, open the page in
two browsers: you land in the same match.

## What good means here

A bot is good when the people in its game are glad it is there. That
means:

1. **A game can always start.** One person plays at once; others join the same
   match by taking over a bot's seat, and a seat someone leaves is covered by a
   bot within five seconds.
2. **Bots are fair.** They see exactly the board a person sees, play by the
   same rules, and choose from the board everyone was shown, never from what
   people have just pressed.
3. **Bots win by choosing well, not by being fast.** A turn waits until every
   person has chosen, for up to two seconds, so nobody loses for being slower
   than a program. I changed the game to this after losing at four moves a
   second.
4. **A bot is a teammate, not the star.** The trained bot is rewarded for its
   team scoring, not for scoring itself.
5. **It is honest about which bot is which.** Every bot seat says whether a
   scripted or a trained bot is playing.

## Checked and judged

Tests in `spec/` and `tests/` check, on every change: every rule, against a
second engine in TypeScript that must agree every turn; that the game is the
same for both teams; that two people share a match and see each other's choices
within a second; that turns wait for people up to the deadline; that bots can't
see choices; and that the server runs the evaluated bot.

People judge the rest: whether the bot feels like a good teammate, and whether
the game is fun. My crit group plays it, and the activity log records what
happens.

## What I read

- Max Jaderberg and others, "Human-level performance in 3D multiplayer games
  with population-based reinforcement learning" (Science, 2019): agents
  trained to play capture the flag with and against people.
- Micah Carroll and others, "On the Utility of Learning about Humans for
  Human-AI Coordination" (NeurIPS, 2019): agents trained only with copies of
  themselves are poor partners for people.
- DJ Strouse and others, "Collaborating with Humans without Human Data"
  (NeurIPS, 2021): training with a variety of past partners makes better
  teammates for people.
- Andrew Ng, Daishi Harada and Stuart Russell, "Policy invariance under reward
  transformations" (ICML, 1999): the kind of reward shaping I use can't change
  which strategy is best.

## What I chose not to build

- **No accounts.** The game only needs to tell people apart.
- **No chat.** The game is played in moves, and a chat would favour fast typers.
- **No ranking of people.** With a few friends, it would only show who played most.

## Limits

- The trained bot so far learns against scripted bots, not people, so
  it may play differently with people than it does in tests.
- Waiting for people helps, but a choice is still needed within two seconds,
  which some players will find too short.

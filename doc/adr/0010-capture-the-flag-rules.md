# 0010. The rules of the game

Status: accepted (2026-10-08). Rules version 2 since 2026-10-09 (see the end).

## Context

The server, the TypeScript reference engine in `spec/`, and the RL training code
all run these rules, so they have to be exact enough to implement three times
and get the same answer. They also have to be quick to learn for a first-time
visitor, fair between teams, and make teamwork worth learning for a bot.

## Decision

**Teams and map.** Blue and red, 2v2 or 3v3. The grid is 16×10 for 2v2 and
20×12 for 3v3; columns `x` count from the left, rows `y` from the top. Blue owns
the left half (`x < W/2`), red the right half. Each team's flag sits at
`(1, H/2)` for blue and `(W−2, H/2)` for red; a team's **base** is the 3×3 block
around its flag. Moving off the grid or into a wall means staying put.

**Maps are random and symmetric.** Each match has a seed. Walls are placed at
random on the blue half (about 18% of cells, never in a base) and mirrored onto
the red half (`x → W−1−x`), so both teams always face the same map. A map is
kept only if every open cell can be reached from every other; otherwise the
generator tries the next attempt from the same seed. The same seed always gives
the same map.

**A tick.** Four ticks a second. Every player picks one of five actions (stay,
north, south, east, west) and everyone moves **at the same time**:

1. Work out where each player is trying to go.
2. **Contact**: two enemies make contact if they are trying to go to the same
   cell, or to swap cells. A player in contact whose destination is in the
   enemy half is **tagged**. (In a swap across the middle line, both are.)
   A player only needs one such contact to be tagged.
3. Tagged players leave the board for 8 ticks (2 seconds), then return on the
   first free cell of their base in a fixed order. A tagged carrier's flag goes
   straight home.
4. Everyone else moves. Teammates may share a cell.
5. **Pickup**: a player standing on the enemy flag while it is home picks it up.
   If several teammates stand there, the lowest seat number takes it.
6. **Capture**: a carrier standing in their own base scores 1 for their team,
   and the flag goes home.

**Carriers are slower**: a carrier doesn't move on every fourth tick
(`tick mod 4 = 3`; every third in version 1). Otherwise a carrier could never
be caught from behind, and defending would be pointless.

**A team can't enter its own flag's cell** (version 2). It is a wall to that
team, and spawning and respawning skip it.

**Scoring doesn't need your own flag at home.** Simpler to learn, and games
don't stall.

**A match ends** when a team reaches 3, or after 720 ticks (3 minutes).

**Fairness.** No fog of war: the whole map is on screen, so a bot sees exactly
what a person sees. Bots choose their action from the state broadcast at the
previous tick, never from the inputs people have just sent (ADR 0011).

## Consequences

- Seat number matters only for who picks up a flag when two teammates arrive at
  once, which never changes the score. Swapping seats otherwise gives the same
  game, and the spec checks it.
- Random maps stop a bot memorising one layout. It has to learn general skills
  (shortest paths, guarding a gap), and it can be tested on map seeds it never
  trained on.
- Any change to these rules gets a new rules version; replays record the
  version they were played under.

## Rules version 2 (2026-10-09)

Before training anything on these rules, I played the scripted bots against
each other on many random maps. That found two problems with version 1.

1. **Standing on your own flag made it untakeable.** To pick up a flag you
   have to step onto its cell, which is on the defenders' half, so contact
   there always tags the attacker. A defender parked on the flag could never be
   beaten: 80 bot games out of 80 were 0–0 draws. People would find this too,
   and an RL agent would learn it first and learn nothing else. Version 2 makes
   a team's own flag cell a wall to that team.
2. **Carriers were too slow.** With competent defenders, carriers were caught
   on the way home almost every time: about 26 pickups but 0.6 captures a game,
   and 72% draws. Comparing skip rates over 120 bot games each:

   | carrier skips | captures a game | matches decided | mean length |
   |---|---|---|---|
   | 1 tick in 3 | 0.57 | 28% | 719 ticks |
   | 1 tick in 4 | 1.98 | 71% | 672 ticks |
   | 1 tick in 6 | 3.08 | 82% | 589 ticks |
   | never | 4.43 | 98% | 268 ticks |

   One in four keeps defending worthwhile while most matches get decided, and
   blue and red won about equally (45–40). For RL it also keeps scoring
   neither so rare that the reward is almost always zero, nor so easy that one
   rushing move is all there is to learn.

Along the way, a balance check that looked unfair turned out to be the test's
fault: the bots' random moves were seeded the same in every game, so 80 games
were not 80 independent samples. A direct check showed the engine itself is
exactly mirror-symmetric between the teams (60 games of random moves, every
tick mirrored).

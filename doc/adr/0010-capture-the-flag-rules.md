# 0010. The rules of the game

Status: accepted (2026-10-08). Rules version 1.

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

**Carriers are slower**: a carrier doesn't move on every third tick
(`tick mod 3 = 2`). Otherwise a carrier could never be caught from behind, and
defending would be pointless.

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

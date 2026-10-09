"""Evaluate a bot against the full scripted bots on maps it never trained on
(ADR 0013).

    python rl/eval.py rl/runs/cur1/cur1.npz --games 400

Runs the exported NumPy bot, the same code the server runs. Games alternate
blue and red and 2v2 and 3v3, on seeds from 1,000,000 up (training uses seeds
below that). Reports wins, draws and losses with 95% Wilson intervals, next to
a baseline of the scripted bot playing itself on the same maps, which should be
close to even.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.game.bots import scripted_action  # noqa: E402
from app.game.engine import new_game, step  # noqa: E402
from app.game.policy import Policy  # noqa: E402

EVAL_SEED = 1_000_000


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a proportion k/n, sound even near 0 or 1."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def play(choose, games: int) -> dict:
    """`choose(state, seat)` plays one team; scripted bots play the other."""
    w = d = l = 0
    scored = conceded = 0
    for g in range(games):
        k = 2 if g % 2 == 0 else 3
        team = (g // 2) % 2
        s = new_game(EVAL_SEED + g, k)
        while not s.done:
            step(s, [choose(s, i) if p.team == team else scripted_action(s, i) for i, p in enumerate(s.players)])
        mine, theirs = s.score[team], s.score[1 - team]
        scored += mine
        conceded += theirs
        w += mine > theirs
        d += mine == theirs
        l += mine < theirs
    return {"games": games, "win": w, "draw": d, "loss": l, "scored": scored / games, "conceded": conceded / games}


def report(label: str, r: dict) -> None:
    n = r["games"]
    lo, hi = wilson(r["win"], n)
    print(f"{label:24s} win {r['win'] / n:5.1%} [{lo:.1%}, {hi:.1%}]  draw {r['draw'] / n:5.1%}  "
          f"loss {r['loss'] / n:5.1%}  captures {r['scored']:.2f} for, {r['conceded']:.2f} against  ({n} games)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bot", help="an exported .npz")
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--no-baseline", action="store_true")
    args = ap.parse_args()
    policy = Policy(Path(args.bot))
    report(f"{policy.name} vs scripted", play(policy.action, args.games))
    if not args.no_baseline:
        report("scripted vs scripted", play(scripted_action, args.games))


if __name__ == "__main__":
    main()

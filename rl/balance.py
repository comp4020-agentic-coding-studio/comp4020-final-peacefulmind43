"""Pick the opponent bot for a match with people in it (ADR 0023).

    python rl/balance.py --games 400

No person plays here. A stand-in for a person (the scripted bot with extra
random moves, `--stand-in`) sits in one seat of a team, and the deployed bot
(fcp1) plays the rest of that team, as it would beside a person. Each
candidate opponent plays every seat of the other team. Games alternate blue
and red and 2v2 and 3v3, on seeds from 3,000,000 up, which no bot trained or
was evaluated on. The stand-in's seat rotates.

For each candidate it prints wins, draws and losses for the stand-in's team
with 95% Wilson intervals, and the points share (a win is 1, a draw 1/2). The
candidate whose points share is closest to 50% is the even match.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.game import policy  # noqa: E402
from app.game.engine import new_game, step  # noqa: E402
from eval import wilson  # noqa: E402
from partners import Partner  # noqa: E402

BALANCE_SEED = 3_000_000


def candidate(name: str) -> Partner:
    """A candidate opponent: "scripted", "noisyNN" (the scripted bot with NN%
    extra random moves, mirrored for red by partners.Partner), or a trained
    bot from app/game/bots/ or rl/runs/pool/."""
    if name == "scripted":
        return Partner(name, "scripted")
    if name.startswith("noisy"):
        return Partner(name, f"scripted:{int(name[5:]) / 100}")
    path = policy.BOT_DIR / f"{name}.npz"
    if not path.exists():
        path = Path(__file__).resolve().parent / "runs" / "pool" / f"{name}.npz"
    return Partner(name, f"net:{path}")


def play(args: tuple[str, str, str, int, int, int]) -> dict:
    opp_name, stand_in, mate_name, start, games, base = args
    opp = candidate(opp_name)
    person = Partner("stand-in", stand_in)
    mate = policy.load(mate_name)
    out = {"win": 0, "draw": 0, "loss": 0, "for": 0, "against": 0, "by_person": 0}
    for g in range(start, start + games):
        k = 2 if g % 2 == 0 else 3
        team = (g // 2) % 2
        s = new_game(base + g, k)
        seat = team * k + (g // 4) % k
        while not s.done:
            acts = []
            for i, p in enumerate(s.players):
                if p.team != team:
                    acts.append(opp.act(s, i))
                elif i == seat:
                    acts.append(person.act(s, i))
                else:
                    acts.append(mate.action(s, i))
            for ev, who in step(s, acts):
                if ev == "capture" and who == seat:
                    out["by_person"] += 1
        mine, theirs = s.score[team], s.score[1 - team]
        out["for"] += mine
        out["against"] += theirs
        out["win" if mine > theirs else "draw" if mine == theirs else "loss"] += 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--stand-in", default="scripted:0.5", help="the partner spec that stands in for a person")
    ap.add_argument("--mate", default="fcp1", help="the bot beside the stand-in")
    ap.add_argument("--candidates", default="fcp1,scripted,noisy25,noisy50,noisy75")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=BALANCE_SEED, help="the first map seed")
    args = ap.parse_args()
    names = args.candidates.split(",")
    chunks = 8
    per = args.games // chunks
    jobs = [(n, args.stand_in, args.mate, c * per, per, args.seed) for n in names for c in range(chunks)]
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(play, jobs))
    print(f"stand-in for a person: {args.stand_in}; beside it: {args.mate}; seeds from {args.seed:,}; {per * chunks} games each")
    best = None
    for idx, name in enumerate(names):
        r = {k: sum(x[k] for x in results[idx * chunks:(idx + 1) * chunks]) for k in results[0]}
        n = r["win"] + r["draw"] + r["loss"]
        points = (r["win"] + r["draw"] / 2) / n
        line = f"vs {name:10s}"
        for key in ("win", "draw", "loss"):
            lo, hi = wilson(r[key], n)
            line += f" {key} {r[key] / n:5.1%} [{lo:.1%}, {hi:.1%}]"
        line += (f"  points {points:5.1%}  captures {r['for'] / n:.2f} for, {r['against'] / n:.2f} against;"
                 f" by the stand-in {r['by_person'] / n:.2f}")
        print(line, flush=True)
        if best is None or abs(points - 0.5) < best[1]:
            best = (name, abs(points - 0.5))
    print(f"closest to an even match: {best[0]}")


if __name__ == "__main__":
    main()

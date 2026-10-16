"""Evaluate a bot against the full scripted bots on maps it never trained on
(ADR 0013).

    python rl/eval.py rl/runs/cur1/cur1.npz --games 400

Runs the exported NumPy bot, the same code the server runs. Games alternate
blue and red and 2v2 and 3v3, on seeds from 1,000,000 up (training uses seeds
below that). Reports wins, draws and losses with 95% Wilson intervals, next to
a baseline of the scripted bot playing itself on the same maps, which should be
close to even.

The teammate evaluation (ADR 0018) pairs the bot with partners it never
trained with, against the full scripted team, and puts a second bot (cur4) in
the same seat with the same partners, maps and randomness:

    python rl/eval.py rl/runs/fcp1/fcp1.npz --teammate --compare app/game/bots/cur4.npz

The bot plays one seat of its team (which one rotates); the partner plays the
rest. It reports results, captures, and how many of the team's captures the
bot made against its partners, plus where the bot spends its turns.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from app.game.bots import scripted_action  # noqa: E402
from app.game.engine import CARRIER_SKIP, MOVES, STAY, new_game, step  # noqa: E402
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


def _target(s, i: int, action: int):
    """Where seat i tries to go this tick (step 1 of engine.step), so a tag
    can be credited to the player who made the contact."""
    p = s.players[i]
    if not p.active:
        return None
    if p.carrying and s.tick % CARRIER_SKIP == CARRIER_SKIP - 1:
        action = STAY
    dx, dy = MOVES[action if 0 <= action <= 4 else STAY]
    nx, ny = p.x + dx, p.y + dy
    return (nx, ny) if s.map.open_for(p.team, nx, ny) else (p.x, p.y)


def play_team(bot, partner, games: int) -> dict:
    """`bot.action` plays one seat of a team, `partner.act` the rest; the full
    scripted bot plays the other team.

    Team-play measures (ADR 0020), over the bot's turns on the board:
    - escort: of the turns a partner carries the enemy flag, the share the bot
      is within 2 steps (Manhattan) of that partner;
    - home while a partner attacks: of the turns a partner is on the enemy
      half, the share the bot is on its own half;
    - carrier tags: enemy carriers of our flag tagged by the bot (its move
      made the contact).
    Captures are kept per game, so the partners' share of the team's captures
    gets a bootstrap interval over games (`share_interval`)."""
    w = d = l = 0
    scored = conceded = 0
    bot_turns = enemy_half = tagged = 0
    escort_turns = escort_near = attack_turns = attack_home = carrier_tags = 0
    caps_bot, caps_partner = [], []
    for g in range(games):
        k = 2 if g % 2 == 0 else 3
        team = (g // 2) % 2
        s = new_game(EVAL_SEED + g, k)
        seat = team * k + (g // 4) % k  # rotate which seat of the team the bot plays
        mates = [i for i, p in enumerate(s.players) if p.team == team and i != seat]
        gb = gp = 0
        while not s.done:
            acts = []
            for i, p in enumerate(s.players):
                if p.team != team:
                    acts.append(scripted_action(s, i))
                elif i == seat:
                    acts.append(bot.action(s, i))
                else:
                    acts.append(partner.act(s, i))
            me = s.players[seat]
            if me.active:
                bot_turns += 1
                enemy_half += s.map.half(me.x) != team
                c = s.carrier[1 - team]  # who on this team holds the enemy flag
                if c is not None and c != seat and s.players[c].active:
                    escort_turns += 1
                    escort_near += abs(s.players[c].x - me.x) + abs(s.players[c].y - me.y) <= 2
                if any(s.players[i].active and s.map.half(s.players[i].x) != team for i in mates):
                    attack_turns += 1
                    attack_home += s.map.half(me.x) == team
            enemy_carrier = s.carrier[team]  # the enemy holding our flag
            if enemy_carrier is not None:
                t_me, t_c = _target(s, seat, acts[seat]), _target(s, enemy_carrier, acts[enemy_carrier])
                p_me, p_c = (me.x, me.y), (s.players[enemy_carrier].x, s.players[enemy_carrier].y)
                contact = t_me is not None and t_c is not None and (t_me == t_c or (t_me == p_c and t_c == p_me))
            for ev, who in step(s, acts):
                if ev == "capture" and s.players[who].team == team:
                    gb += who == seat
                    gp += who != seat
                if ev == "tag" and who == seat:
                    tagged += 1
                if ev == "tag" and enemy_carrier is not None and who == enemy_carrier and contact:
                    carrier_tags += 1
        caps_bot.append(gb)
        caps_partner.append(gp)
        mine, theirs = s.score[team], s.score[1 - team]
        scored += mine
        conceded += theirs
        w += mine > theirs
        d += mine == theirs
        l += mine < theirs
    return {"games": games, "win": w, "draw": d, "loss": l, "scored": scored / games, "conceded": conceded / games,
            "by_bot": sum(caps_bot) / games, "by_partner": sum(caps_partner) / games,
            "caps_bot": caps_bot, "caps_partner": caps_partner,
            "enemy_half": enemy_half / max(bot_turns, 1), "tagged": tagged / games,
            "escort": escort_near / max(escort_turns, 1), "escort_turns": escort_turns / games,
            "home_while_attack": attack_home / max(attack_turns, 1), "carrier_tags": carrier_tags / games}


def share_interval(caps_bot: list[int], caps_partner: list[int], boots: int = 2000, seed: int = 20261014) -> tuple[float, float, float]:
    """The partners' share of the team's captures (all partner captures over
    all team captures, pooled over games), with a 95% percentile bootstrap
    interval that resamples whole games. Pre-registered in ADR 0020."""
    b, p = np.array(caps_bot, dtype=float), np.array(caps_partner, dtype=float)
    share = p.sum() / max(b.sum() + p.sum(), 1.0)
    idx = np.random.default_rng(seed).integers(0, len(b), size=(boots, len(b)))
    pb, pp = b[idx].sum(1), p[idx].sum(1)
    lo, hi = np.percentile(pp / np.maximum(pb + pp, 1.0), [2.5, 97.5])
    return float(share), float(lo), float(hi)


def report_team(label: str, r: dict) -> None:
    n = r["games"]
    print(f"  {label:10s}", end="")
    for key in ("win", "draw", "loss"):
        lo, hi = wilson(r[key], n)
        print(f" {key} {r[key] / n:5.1%} [{lo:.1%}, {hi:.1%}]", end="")
    print(f"  captures {r['scored']:.2f} for, {r['conceded']:.2f} against;"
          f" by bot {r['by_bot']:.2f}, by partners {r['by_partner']:.2f};"
          f" bot on their half {r['enemy_half']:.0%} of turns, caught {r['tagged']:.2f}/game", flush=True)
    share, lo, hi = share_interval(r["caps_bot"], r["caps_partner"])
    print(f"  {'':10s} partners' share of captures {share:.1%} [{lo:.1%}, {hi:.1%}];"
          f" escort {r['escort']:.0%} of {r['escort_turns']:.1f} partner-carrier turns/game;"
          f" home while a partner attacks {r['home_while_attack']:.0%};"
          f" enemy carriers tagged {r['carrier_tags']:.2f}/game", flush=True)


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
    ap.add_argument("--teammate", action="store_true", help="the teammate evaluation with held-out partners (ADR 0018)")
    ap.add_argument("--compare", help="a second .npz to put in the same seat (teammate evaluation)")
    ap.add_argument("--partners", help="comma-separated partner names from rl/partners.py (default: the held-out ones)")
    args = ap.parse_args()
    policy = Policy(Path(args.bot))
    if args.teammate:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import partners as pool

        known = {**pool.HELD_OUT, **pool.TEAM_POOL}
        names = args.partners.split(",") if args.partners else list(pool.HELD_OUT)
        players = [policy] + ([Policy(Path(args.compare))] if args.compare else [])
        for name in names:
            where = "held out" if name in pool.HELD_OUT else "in the training pool"
            print(f"partner {name} ({known[name]}, {where}), {args.games} games against the full scripted team:", flush=True)
            for b in players:
                report_team(b.name, play_team(b, pool.Partner(name, known[name]), args.games))
        return
    report(f"{policy.name} vs scripted", play(policy.action, args.games))
    if not args.no_baseline:
        report("scripted vs scripted", play(scripted_action, args.games))


if __name__ == "__main__":
    main()

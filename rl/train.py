"""PPO for the capture-the-flag bot (ADR 0013), in the style of CleanRL's single
file. One network plays every seat of the learning team; the scripted bots play
the other team. Shaping fades from 1 to 0 over the first half of training.

Opponents follow an adaptive curriculum: they start at level 0 (wandering) and
step up by 0.1 whenever the learner wins 70% of its last 100 games at the
current level, until they are the full scripted bot. Without it, the first
runs met full defenders from the start, were caught every time they crossed
the middle, and learned to stay on their own half: 100% of their turns.

    python rl/train.py --name first --steps 10000000

Writes rl/runs/<name>/: metrics.csv (one row per update), checkpoints, and
<name>.npz (the exported bot) at the end.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from collections import deque
from pathlib import Path

import numpy as np
import torch
from torch import nn

from env import Batch
from model import Net, export

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--steps", type=int, default=10_000_000, help="learner samples in total")
    ap.add_argument("--games", type=int, default=64)
    ap.add_argument("--rollout", type=int, default=128)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=4096)
    ap.add_argument("--lr", type=float, default=2.5e-4)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--vf", type=float, default=0.5)
    ap.add_argument("--shaping-frac", type=float, default=0.5, help="shaping reaches 0 at this fraction of training")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--level-step", type=float, default=0.1, help="curriculum step; 0 disables it")
    ap.add_argument("--level-win", type=float, default=0.7, help="win rate that raises the level")
    ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu",
                    help="where the update runs; rollouts always run on the CPU")
    args = ap.parse_args()

    out = HERE / "runs" / args.name
    out.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)

    batch = Batch(args.games, seed=args.seed)
    planes, scalars, owner = batch.observe()
    rows, T = len(owner), args.rollout
    # Two copies of one network: `learner` is trained on the GPU (5x faster on
    # an M2 than the CPU for a 2048 batch); `actor` plays the rollouts on the
    # CPU, where a batch of 80-160 rows is faster than moving it to the GPU.
    learner = Net().to(args.device)
    actor = Net()
    actor.load_state_dict(learner.state_dict())
    net = actor
    opt = torch.optim.Adam(learner.parameters(), lr=args.lr, eps=1e-5)

    # rollout storage; the planes are 0/1, so uint8 keeps memory a quarter of float32
    buf_planes = np.zeros((T, rows, *planes.shape[1:]), dtype=np.uint8)
    buf_scalars = np.zeros((T, rows, scalars.shape[1]), dtype=np.float32)
    buf_actions = np.zeros((T, rows), dtype=np.int64)
    buf_logp = np.zeros((T, rows), dtype=np.float32)
    buf_values = np.zeros((T, rows), dtype=np.float32)
    buf_rewards = np.zeros((T, rows), dtype=np.float32)
    buf_dones = np.zeros((T, rows), dtype=np.float32)

    level = 0.0 if args.level_step > 0 else 1.0
    at_level: deque = deque(maxlen=100)  # results since the level last changed
    results: deque = deque(maxlen=200)
    captures: deque = deque(maxlen=200)
    updates = args.steps // (T * rows)
    log = open(out / "metrics.csv", "w", newline="")
    writer = csv.writer(log)
    writer.writerow(["update", "samples", "seconds", "samples_per_s", "level", "shaping", "lr", "games", "win", "draw", "loss_rate",
                     "captures", "policy_loss", "value_loss", "entropy", "approx_kl", "clip_frac"])
    start = time.time()
    samples = 0
    done_prev = np.zeros(rows, dtype=np.float32)

    for update in range(1, updates + 1):
        frac = (update - 1) / updates
        shaping = max(0.0, 1.0 - frac / args.shaping_frac)
        lr = args.lr * (1.0 - frac)
        for g in opt.param_groups:
            g["lr"] = lr

        for t in range(T):
            buf_planes[t] = planes
            buf_scalars[t] = scalars
            buf_dones[t] = done_prev
            with torch.no_grad():
                logits, value = net(torch.from_numpy(planes), torch.from_numpy(scalars))
                dist = torch.distributions.Categorical(logits=logits)
                action = dist.sample()
            buf_actions[t] = action.numpy()
            buf_logp[t] = dist.log_prob(action).numpy()
            buf_values[t] = value.numpy()
            rewards, dones, finished = batch.step(action.numpy(), owner, args.gamma, shaping, level)
            buf_rewards[t] = rewards
            done_prev = dones
            for info in finished:
                results.append(info["result"])
                captures.append(info["captures"])
                at_level.append(info["result"])
            if level < 1.0 and len(at_level) == at_level.maxlen and sum(r == 1 for r in at_level) / len(at_level) >= args.level_win:
                level = min(1.0, round(level + args.level_step, 2))
                at_level.clear()
                print(f"  curriculum: opponents now at level {level:.1f}", flush=True)
            planes, scalars, owner = batch.observe()
            samples += rows

        # generalised advantage estimation, bootstrapped from the last state
        with torch.no_grad():
            _, last_value = net(torch.from_numpy(planes), torch.from_numpy(scalars))
        last_value = last_value.numpy()
        adv = np.zeros((T, rows), dtype=np.float32)
        gae = np.zeros(rows, dtype=np.float32)
        for t in reversed(range(T)):
            next_nonterminal = 1.0 - (done_prev if t == T - 1 else buf_dones[t + 1])
            next_value = last_value if t == T - 1 else buf_values[t + 1]
            delta = buf_rewards[t] + args.gamma * next_value * next_nonterminal - buf_values[t]
            gae = delta + args.gamma * args.lam * next_nonterminal * gae
            adv[t] = gae
        returns = adv + buf_values

        b_planes = buf_planes.reshape(T * rows, *planes.shape[1:])
        b_scalars = buf_scalars.reshape(T * rows, -1)
        dev = args.device
        b_actions = torch.from_numpy(buf_actions.reshape(-1)).to(dev)
        b_logp = torch.from_numpy(buf_logp.reshape(-1)).to(dev)
        b_adv = torch.from_numpy(adv.reshape(-1)).to(dev)
        b_returns = torch.from_numpy(returns.reshape(-1)).to(dev)
        n = T * rows
        stats = []
        for _ in range(args.epochs):
            order = np.random.permutation(n)
            for lo in range(0, n, args.minibatch):
                idx = order[lo : lo + args.minibatch]
                p = torch.from_numpy(b_planes[idx].astype(np.float32)).to(dev)
                s = torch.from_numpy(b_scalars[idx]).to(dev)
                logits, value = learner(p, s)
                dist = torch.distributions.Categorical(logits=logits)
                logp = dist.log_prob(b_actions[idx])
                ratio = (logp - b_logp[idx]).exp()
                a = b_adv[idx]
                a = (a - a.mean()) / (a.std() + 1e-8)
                pg = torch.max(-a * ratio, -a * ratio.clamp(1 - args.clip, 1 + args.clip)).mean()
                vl = 0.5 * ((value - b_returns[idx]) ** 2).mean()
                ent = dist.entropy().mean()
                loss = pg + args.vf * vl - args.ent * ent
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(learner.parameters(), 0.5)
                opt.step()
                with torch.no_grad():
                    kl = ((ratio - 1) - (logp - b_logp[idx])).mean().item()
                    clipped = ((ratio - 1).abs() > args.clip).float().mean().item()
                stats.append((pg.item(), vl.item(), ent.item(), kl, clipped))

        actor.load_state_dict({k: v.cpu() for k, v in learner.state_dict().items()})
        secs = time.time() - start
        pg_l, v_l, ent_v, kl_v, clip_v = np.mean(stats, axis=0)
        games = len(results)
        win = sum(r == 1 for r in results) / games if games else float("nan")
        draw = sum(r == 0 for r in results) / games if games else float("nan")
        lose = sum(r == -1 for r in results) / games if games else float("nan")
        caps = float(np.mean(captures)) if captures else float("nan")
        writer.writerow([update, samples, round(secs), round(samples / secs), level, round(shaping, 3), f"{lr:.2e}", games,
                         round(win, 3), round(draw, 3), round(lose, 3), round(caps, 2),
                         round(pg_l, 4), round(v_l, 4), round(ent_v, 3), round(kl_v, 4), round(clip_v, 3)])
        log.flush()
        if update % 5 == 0 or update == updates:
            print(f"update {update}/{updates}  samples {samples:,}  {samples / secs:,.0f}/s  level {level:.1f}  shaping {shaping:.2f}  "
                  f"last {games} games vs scripted: win {win:.2f} draw {draw:.2f} lose {lose:.2f}  captures {caps:.2f}  "
                  f"entropy {ent_v:.2f}", flush=True)
        if update % 25 == 0 or update == updates:
            torch.save(actor.state_dict(), out / "checkpoint.pt")

    probe = Batch(4, seed=12345).observe()
    export(net, str(out / f"{args.name}.npz"), (probe[0][:16], probe[1][:16]))
    print(f"exported {out / (args.name + '.npz')}", flush=True)


if __name__ == "__main__":
    main()

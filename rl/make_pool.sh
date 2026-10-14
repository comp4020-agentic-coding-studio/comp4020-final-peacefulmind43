#!/bin/sh
# Fill rl/runs/pool/ with the past bots that FCP-lite uses as partners
# (ADR 0018, rl/partners.py). Checkpoints are local, never committed, so this
# copies them from a checkout that has the old runs.
#
#     sh rl/make_pool.sh /path/to/checkout/with/rl/runs
set -eu
SRC="${1:?give the checkout whose rl/runs has cur1..cur4, phi2 and lr1e3}/rl/runs"
DST="$(cd "$(dirname "$0")" && pwd)/runs/pool"
mkdir -p "$DST"
cp "$SRC/cur1/checkpoint.pt" "$DST/cur1.pt"        # early: before it learned to attack
cp "$SRC/cur2/cur2.npz" "$DST/cur2.npz"            # attacks, never defends
cp "$SRC/cur3/checkpoint.pt" "$DST/cur3.pt"        # held out
cp "$SRC/cur4/snapshot.npz" "$DST/cur4snap.npz"    # mid-run cur4
cp "$SRC/cur4/checkpoint.pt" "$DST/cur4.pt"        # the deployed bot, and the starting point
cp "$SRC/phi2/phi2.npz" "$DST/phi2.npz"            # stays home
cp "$SRC/lr1e3/lr1e3.npz" "$DST/lr1e3.npz"         # held out
ls -l "$DST"

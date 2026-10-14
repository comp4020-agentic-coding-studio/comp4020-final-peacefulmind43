#!/bin/sh
# After an FCP-lite run (ADR 0018): wait for it to finish, check the export,
# and run both evaluations against cur4. Writes rl/runs/<name>/eval.txt.
# Deploys nothing: copying a bot into app/game/bots/ is a separate decision.
#
#     sh rl/after_fcp.sh fcp1            # waits for training to end first
set -eu
NAME="${1:?run name, e.g. fcp1}"
GAMES="${2:-400}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-$HERE/../.venv/bin/python}"
[ -x "$PY" ] || PY=/Users/zhangshuo/Desktop/comp4020/comp4020-final-peacefulmind43/.venv/bin/python
RUN="$HERE/runs/$NAME"
BOT="$RUN/$NAME.npz"
CUR4="$HERE/../app/game/bots/cur4.npz"

while pgrep -f "train.py --name $NAME " >/dev/null; do sleep 60; done
[ -f "$BOT" ] || { echo "no export at $BOT: did training finish? see $RUN/train.log"; exit 1; }

cd "$HERE"
{
  echo "== $NAME, evaluated $(date '+%Y-%m-%d %H:%M')"
  echo "-- NumPy export agrees with PyTorch"
  "$PY" -c "
import sys, numpy as np; from pathlib import Path
sys.path.insert(0, '..'); from app.game.policy import Policy
d = np.load('$BOT'); got = Policy(Path('$BOT')).logits(d['check_planes'], d['check_scalars'])
err = float(np.abs(got - d['check_logits']).max()); print('max abs difference', err); assert err < 1e-4"
  echo "-- against the full scripted bot, $GAMES unseen maps"
  "$PY" eval.py "$BOT" --games "$GAMES" --no-baseline
  "$PY" eval.py "$CUR4" --games "$GAMES"
  echo "-- teammate: one seat, held-out partners (and the scripted bot, in the pool), vs the full scripted team"
  "$PY" eval.py "$BOT" --teammate --compare "$CUR4" --games "$GAMES" --partners scripted30,cur3,lr1e3,scripted
} 2>&1 | tee "$RUN/eval.txt"

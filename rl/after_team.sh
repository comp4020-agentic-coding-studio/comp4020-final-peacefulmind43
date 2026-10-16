#!/bin/sh
# After a team-play run (ADR 0020): wait for it to finish, check the export,
# and run both evaluations against fcp1, the deployed bot. Writes
# rl/runs/<name>/eval.txt. The teammate lines include the partners' share of
# the team's captures with a 95% bootstrap interval over games, and the
# team-play measures (escort, home while a partner attacks, enemy carriers
# tagged). Deploys nothing.
#
#     sh rl/after_team.sh team1            # waits for training to end first
set -eu
NAME="${1:?run name, e.g. team1}"
GAMES="${2:-400}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-$HERE/../.venv/bin/python}"
[ -x "$PY" ] || PY=/Users/zhangshuo/Desktop/comp4020/comp4020-final-peacefulmind43/.venv/bin/python
RUN="$HERE/runs/$NAME"
BOT="$RUN/$NAME.npz"
FCP1="$HERE/../app/game/bots/fcp1.npz"

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
  "$PY" eval.py "$FCP1" --games "$GAMES"
  echo "-- teammate: one seat, held-out partners (and the scripted bot, in the pool), vs the full scripted team"
  "$PY" eval.py "$BOT" --teammate --compare "$FCP1" --games "$GAMES" --partners scripted30,cur3,lr1e3,scripted
} 2>&1 | tee "$RUN/eval.txt"

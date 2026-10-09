"""The trained RL bot on the server: the policy network in NumPy (ADR 0013).

The server can't hold PyTorch (256 MB), so the exported weights run here with
NumPy. tests/test_policy.py checks that this gives the same logits PyTorch gave
for the inputs saved in the export. The bot samples its move from the policy,
seeded by the match, turn and seat, so matches still replay exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .engine import Rng, State
from .obs import observe, to_engine

BOT_DIR = Path(__file__).resolve().parent / "bots"


def conv2d(x: np.ndarray, w: np.ndarray, b: np.ndarray, stride: int = 1, pad: int = 1) -> np.ndarray:
    """A 2D convolution like torch.nn.Conv2d, for a batch [N, C, H, W]."""
    n, c, h, wd = x.shape
    out_c, _, kh, kw = w.shape
    xp = np.pad(x, ((0, 0), (0, 0), (pad, pad), (pad, pad)))
    oh = (h + 2 * pad - kh) // stride + 1
    ow = (wd + 2 * pad - kw) // stride + 1
    cols = np.empty((n, c, kh, kw, oh, ow), dtype=x.dtype)
    for i in range(kh):
        for j in range(kw):
            cols[:, :, i, j] = xp[:, :, i : i + stride * oh : stride, j : j + stride * ow : stride]
    # im2col: every output position's input patch as one row, then one matmul
    flat = cols.transpose(0, 4, 5, 1, 2, 3).reshape(n * oh * ow, c * kh * kw)
    y = flat @ w.reshape(out_c, -1).T + b
    return y.reshape(n, oh, ow, out_c).transpose(0, 3, 1, 2)


class Policy:
    def __init__(self, path: Path):
        data = np.load(path)
        self.w = {k: data[k] for k in data.files if not k.startswith("check_")}
        self.name = path.stem

    def logits(self, planes: np.ndarray, scalars: np.ndarray) -> np.ndarray:
        w = self.w
        x = np.maximum(conv2d(planes, w["conv1.weight"], w["conv1.bias"], stride=1), 0)
        x = np.maximum(conv2d(x, w["conv2.weight"], w["conv2.bias"], stride=2), 0)
        x = np.concatenate([x.reshape(x.shape[0], -1), scalars], axis=1)
        x = np.maximum(x @ w["fc.weight"].T + w["fc.bias"], 0)
        return x @ w["pi.weight"].T + w["pi.bias"]

    def action(self, state: State, seat: int) -> int:
        planes, scalars = observe(state, seat)
        z = self.logits(planes[None], scalars[None])[0]
        p = np.exp(z - z.max())
        p /= p.sum()
        r = Rng((state.tick * 2654435761 + seat * 40503 + state.seed * 2246822519 + 777) & 0xFFFFFFFF).next()
        choice = int(min(np.searchsorted(np.cumsum(p), r, side="right"), len(p) - 1))
        return to_engine(state.players[seat].team, choice)  # chosen in its flipped view


def load(name: str) -> Policy | None:
    path = BOT_DIR / f"{name}.npz"
    return Policy(path) if path.exists() else None


def on_show() -> Policy | None:
    """The bot named in BOT_DIR/watch.txt, shown in the watch arena against the
    scripted bot, whether or not it is good enough to fill people's seats yet."""
    pointer = BOT_DIR / "watch.txt"
    return load(pointer.read_text().strip()) if pointer.exists() else None


def deployed() -> Policy | None:
    """The bot named in BOT_DIR/current.txt, if there is one. Without it, the
    scripted bots fill every seat (ADR 0013: they are the fallback)."""
    pointer = BOT_DIR / "current.txt"
    if not pointer.exists():
        return None
    return load(pointer.read_text().strip())

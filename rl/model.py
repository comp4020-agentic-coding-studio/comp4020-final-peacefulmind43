"""The policy network (ADR 0013), and its export to NumPy for the server."""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from env import N_SCALARS, OBS_SHAPE

N_ACTIONS = 5


class Net(nn.Module):
    """Two convolutions over the map planes, then one hidden layer with the
    scalars, then a policy head (5 moves) and a value head."""

    def __init__(self, hidden: int = 128):
        super().__init__()
        c, h, w = OBS_SHAPE
        self.conv1 = nn.Conv2d(c, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 32, 3, stride=2, padding=1)
        flat = 32 * ((h + 1) // 2) * ((w + 1) // 2)
        self.fc = nn.Linear(flat + N_SCALARS, hidden)
        self.pi = nn.Linear(hidden, N_ACTIONS)
        self.v = nn.Linear(hidden, 1)
        # small initial policy logits: start close to uniform
        nn.init.orthogonal_(self.pi.weight, 0.01)
        nn.init.zeros_(self.pi.bias)
        nn.init.orthogonal_(self.v.weight, 1.0)

    def forward(self, planes: torch.Tensor, scalars: torch.Tensor):
        x = torch.relu(self.conv1(planes))
        x = torch.relu(self.conv2(x))
        x = torch.cat([x.flatten(1), scalars], dim=1)
        x = torch.relu(self.fc(x))
        return self.pi(x), self.v(x).squeeze(-1)


def export(net: Net, path: str, samples: tuple[np.ndarray, np.ndarray]) -> None:
    """Save the weights for NumPy, with a few inputs and the policy logits
    PyTorch gives for them, so a test can check NumPy agrees."""
    planes, scalars = samples
    with torch.no_grad():
        logits, _ = net(torch.from_numpy(planes), torch.from_numpy(scalars))
    weights = {k: v.detach().cpu().numpy() for k, v in net.state_dict().items() if not k.startswith("v.")}
    np.savez_compressed(path, **weights, check_planes=planes, check_scalars=scalars, check_logits=logits.numpy())

"""Black-box MLP baseline skeleton."""

from __future__ import annotations

import torch
from torch import nn


class BlackBoxMLP(nn.Module):
    """Simple feed-forward baseline for future data-only comparisons."""

    def __init__(self, in_dim: int = 2, out_dim: int = 2, hidden_dim: int = 128, hidden_layers: int = 3) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        last_dim = in_dim
        for _ in range(hidden_layers):
            layers.append(nn.Linear(last_dim, hidden_dim))
            layers.append(nn.ReLU())
            last_dim = hidden_dim
        layers.append(nn.Linear(last_dim, out_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Evaluate the baseline network."""

        return self.net(x)

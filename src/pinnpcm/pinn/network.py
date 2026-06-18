"""Neural network definitions for the PINN skeleton."""

from __future__ import annotations

import torch
from torch import nn


class FourierFeatureMLP(nn.Module):
    """MLP with fixed random Fourier features for normalized (x, t) inputs."""

    def __init__(
        self,
        in_dim: int = 2,
        out_dim: int = 4,
        hidden_dim: int = 128,
        hidden_layers: int = 4,
        fourier_features: int = 32,
        fourier_scale: float = 4.0,
    ) -> None:
        super().__init__()
        if in_dim != 2:
            raise ValueError("FourierFeatureMLP expects normalized x and t inputs.")

        self.in_dim = in_dim
        self.out_dim = out_dim
        self.fourier_features = fourier_features

        if fourier_features > 0:
            basis = torch.randn(in_dim, fourier_features) * fourier_scale
            self.register_buffer("fourier_basis", basis)
            encoded_dim = 2 * fourier_features
        else:
            self.register_buffer("fourier_basis", torch.empty(in_dim, 0))
            encoded_dim = in_dim

        layers: list[nn.Module] = []
        last_dim = encoded_dim
        for _ in range(hidden_layers):
            layers.append(nn.Linear(last_dim, hidden_dim))
            layers.append(nn.SiLU())
            last_dim = hidden_dim
        layers.append(nn.Linear(last_dim, out_dim))
        self.net = nn.Sequential(*layers)

    def _encode(self, coords: torch.Tensor) -> torch.Tensor:
        """Encode normalized coordinates."""

        if self.fourier_features <= 0:
            return coords
        projection = 2.0 * torch.pi * coords @ self.fourier_basis
        return torch.cat([torch.sin(projection), torch.cos(projection)], dim=-1)

    def forward(
        self,
        x_norm: torch.Tensor,
        t_norm: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Return raw variables phi_raw, c_raw, T_raw, and m_raw."""

        if t_norm is None:
            coords = x_norm
        else:
            coords = torch.cat([x_norm, t_norm], dim=-1)
        if coords.shape[-1] != 2:
            raise ValueError("Input coordinates must have last dimension 2.")

        raw = self.net(self._encode(coords))
        return {
            "phi_raw": raw[..., 0:1],
            "c_raw": raw[..., 1:2],
            "T_raw": raw[..., 2:3],
            "m_raw": raw[..., 3:4],
        }

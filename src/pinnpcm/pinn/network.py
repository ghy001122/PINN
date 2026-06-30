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

class FourierPyramidEmbedding(nn.Module):
    """Deterministic multiscale Fourier embedding for normalized coordinates.

    The module is isolated and opt-in. It does not change `FourierFeatureMLP` or
    any existing inverse v0/v1/v1.1 model unless explicitly constructed.
    """

    def __init__(
        self,
        in_dim: int = 2,
        scales: tuple[float, ...] | list[float] = (1.0, 2.0, 4.0, 8.0),
        *,
        include_input: bool = True,
    ) -> None:
        super().__init__()
        if in_dim <= 0:
            raise ValueError("in_dim must be positive.")
        if not scales:
            raise ValueError("scales must contain at least one frequency scale.")
        scale_tensor = torch.as_tensor([float(scale) for scale in scales], dtype=torch.float32)
        if torch.any(scale_tensor <= 0):
            raise ValueError("All Fourier pyramid scales must be positive.")
        self.in_dim = int(in_dim)
        self.include_input = bool(include_input)
        self.register_buffer("scales", scale_tensor)

    @property
    def out_dim(self) -> int:
        base = self.in_dim if self.include_input else 0
        return base + 2 * self.in_dim * int(self.scales.numel())

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        """Encode coordinates with `[z, sin(2*pi*s*z), cos(...)]`."""

        if coords.shape[-1] != self.in_dim:
            raise ValueError(f"Expected last dimension {self.in_dim}, got {coords.shape[-1]}.")
        scales = self.scales.to(dtype=coords.dtype, device=coords.device)
        angles = 2.0 * torch.pi * coords.unsqueeze(-2) * scales.view(-1, 1)
        encoded = [torch.sin(angles).flatten(start_dim=-2), torch.cos(angles).flatten(start_dim=-2)]
        if self.include_input:
            encoded.insert(0, coords)
        return torch.cat(encoded, dim=-1)


class StiffAwareMLP(nn.Module):
    """Opt-in MLP using `FourierPyramidEmbedding` for stiffness-aware MVP tests."""

    def __init__(
        self,
        in_dim: int = 2,
        out_dim: int = 4,
        hidden_dim: int = 64,
        hidden_layers: int = 3,
        scales: tuple[float, ...] | list[float] = (1.0, 2.0, 4.0, 8.0),
        use_fourier: bool = True,
    ) -> None:
        super().__init__()
        self.use_fourier = bool(use_fourier)
        if self.use_fourier:
            self.embedding = FourierPyramidEmbedding(in_dim=in_dim, scales=scales, include_input=True)
            encoded_dim = self.embedding.out_dim
        else:
            self.embedding = nn.Identity()
            encoded_dim = int(in_dim)
        layers: list[nn.Module] = []
        last_dim = encoded_dim
        for _ in range(int(hidden_layers)):
            layers.append(nn.Linear(last_dim, int(hidden_dim)))
            layers.append(nn.SiLU())
            last_dim = int(hidden_dim)
        layers.append(nn.Linear(last_dim, int(out_dim)))
        self.net = nn.Sequential(*layers)

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        """Return raw network outputs from multiscale encoded coordinates."""

        return self.net(self.embedding(coords))

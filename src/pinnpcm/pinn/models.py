"""Neural field models for PINN inverse v0."""

from __future__ import annotations

import math

import torch
from torch import nn


def _logit(value: float) -> float:
    """Numerically stable scalar logit for initialization."""

    clipped = min(max(value, 1.0e-6), 1.0 - 1.0e-6)
    return math.log(clipped / (1.0 - clipped))


class InverseV0Net(nn.Module):
    """Small Fourier-feature MLP for inverse v0 hidden-field reconstruction.

    The model maps normalized coordinates `(x_norm, t_norm)` to constrained
    fields. `sigma` is a positive v0 surrogate closure rather than a strict
    differentiable reimplementation of the full Ground Truth conductivity law.
    """

    def __init__(
        self,
        *,
        hidden_dim: int = 64,
        num_layers: int = 3,
        fourier_features: int = 32,
        fourier_scale: float = 3.0,
        c_v_min: float = 0.0,
        c_v_max: float = 0.2,
        delta_T_max: float = 20.0,
        sigma_min: float = 1.0e-4,
        sigma_max: float = 1.0,
        initial_c_v: float = 0.08,
        initial_m: float = 0.07,
        initial_sigma: float = 4.0e-3,
    ) -> None:
        super().__init__()
        if c_v_max <= c_v_min:
            raise ValueError("c_v_max must be greater than c_v_min.")
        if delta_T_max <= 0.0:
            raise ValueError("delta_T_max must be positive.")
        if sigma_max <= sigma_min or sigma_min <= 0.0:
            raise ValueError("sigma bounds must be positive and ordered.")

        self.c_v_min = float(c_v_min)
        self.c_v_max = float(c_v_max)
        self.delta_T_max = float(delta_T_max)
        self.log_sigma_min = math.log(float(sigma_min))
        self.log_sigma_max = math.log(float(sigma_max))
        self.fourier_features = int(fourier_features)

        if self.fourier_features > 0:
            basis = torch.randn(2, self.fourier_features) * float(fourier_scale)
            self.register_buffer("fourier_basis", basis)
            in_features = 2 * self.fourier_features
        else:
            self.register_buffer("fourier_basis", torch.empty(2, 0))
            in_features = 2

        layers: list[nn.Module] = []
        last_dim = in_features
        for _ in range(int(num_layers)):
            layers.append(nn.Linear(last_dim, int(hidden_dim)))
            layers.append(nn.SiLU())
            last_dim = int(hidden_dim)
        output = nn.Linear(last_dim, 4)
        layers.append(output)
        self.net = nn.Sequential(*layers)
        self._initialize_output_bias(output, initial_c_v, initial_m, initial_sigma)

    def _initialize_output_bias(
        self,
        output: nn.Linear,
        initial_c_v: float,
        initial_m: float,
        initial_sigma: float,
    ) -> None:
        """Start near physically plausible frozen-GT initial values."""

        with torch.no_grad():
            c_ratio = (float(initial_c_v) - self.c_v_min) / (self.c_v_max - self.c_v_min)
            sigma_ratio = (math.log(float(initial_sigma)) - self.log_sigma_min) / (
                self.log_sigma_max - self.log_sigma_min
            )
            output.bias.copy_(
                torch.tensor(
                    [
                        _logit(c_ratio),
                        _logit(1.0e-2 / self.delta_T_max),
                        _logit(float(initial_m)),
                        _logit(sigma_ratio),
                    ],
                    dtype=output.bias.dtype,
                )
            )

    def _encode(self, coords: torch.Tensor) -> torch.Tensor:
        """Apply fixed Fourier features to normalized coordinates."""

        if coords.shape[-1] != 2:
            raise ValueError("InverseV0Net expects coordinates with last dimension 2.")
        if self.fourier_features <= 0:
            return coords
        projection = 2.0 * torch.pi * coords @ self.fourier_basis
        return torch.cat([torch.sin(projection), torch.cos(projection)], dim=-1)

    def forward(
        self,
        coords: torch.Tensor,
        t_norm: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Predict constrained hidden fields from normalized coordinates."""

        if t_norm is not None:
            coords = torch.cat([coords, t_norm], dim=-1)

        raw = self.net(self._encode(coords))
        c_v = self.c_v_min + (self.c_v_max - self.c_v_min) * torch.sigmoid(raw[..., 0:1])
        delta_T = self.delta_T_max * torch.sigmoid(raw[..., 1:2])
        m = torch.sigmoid(raw[..., 2:3])
        log_sigma = self.log_sigma_min + (self.log_sigma_max - self.log_sigma_min) * torch.sigmoid(raw[..., 3:4])
        sigma = torch.exp(log_sigma)

        return {
            "c_v": c_v,
            "delta_T": delta_T,
            "m": m,
            "log_sigma": log_sigma,
            "sigma": sigma,
        }


@torch.no_grad()
def predict_on_grid(
    model: nn.Module,
    x_norm: torch.Tensor,
    t_norm: torch.Tensor,
    *,
    chunk_size: int = 8192,
) -> dict[str, torch.Tensor]:
    """Evaluate a neural field on a tensor-product `(t, x)` grid."""

    mesh_t, mesh_x = torch.meshgrid(t_norm, x_norm, indexing="ij")
    coords = torch.stack([mesh_x.reshape(-1), mesh_t.reshape(-1)], dim=-1)
    pieces: dict[str, list[torch.Tensor]] = {}
    for start in range(0, coords.shape[0], chunk_size):
        pred = model(coords[start : start + chunk_size])
        for key, value in pred.items():
            pieces.setdefault(key, []).append(value.detach())
    return {
        key: torch.cat(values, dim=0).reshape(t_norm.numel(), x_norm.numel())
        for key, values in pieces.items()
    }

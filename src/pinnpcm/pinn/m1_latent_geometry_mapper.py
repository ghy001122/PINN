"""Five-input low-rank latent mapper for the M1 geometry-admission study."""

from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class M1LatentGeometryMapper(nn.Module):
    """Map normalized operating and contact-geometry inputs to POD coefficients."""

    input_dimension = 5
    hidden_width = 32

    def __init__(
        self,
        *,
        pod_mean_y: torch.Tensor,
        pod_basis: torch.Tensor,
        coefficient_center: torch.Tensor,
        coefficient_scale: torch.Tensor,
        ambient_temperature_K: float,
        smooth_nonnegative_beta_K: float,
    ) -> None:
        super().__init__()
        if pod_mean_y.ndim != 1 or pod_basis.ndim != 2:
            raise ValueError("POD mean and basis must be one- and two-dimensional")
        if pod_basis.shape[1] != pod_mean_y.numel():
            raise ValueError("POD basis and mean have incompatible field dimensions")
        rank = int(pod_basis.shape[0])
        if coefficient_center.shape != (rank,) or coefficient_scale.shape != (rank,):
            raise ValueError("coefficient normalization does not match POD rank")
        if torch.any(coefficient_scale <= 0):
            raise ValueError("coefficient scales must be strictly positive")
        if smooth_nonnegative_beta_K <= 0.0:
            raise ValueError("smooth nonnegative beta must be strictly positive")

        self.rank = rank
        self.ambient_temperature_K = float(ambient_temperature_K)
        self.smooth_nonnegative_beta_K = float(smooth_nonnegative_beta_K)
        self.register_buffer("pod_mean_y", pod_mean_y.detach().clone())
        self.register_buffer("pod_basis", pod_basis.detach().clone())
        self.register_buffer("coefficient_center", coefficient_center.detach().clone())
        self.register_buffer("coefficient_scale", coefficient_scale.detach().clone())
        self.network = nn.Sequential(
            nn.Linear(self.input_dimension, self.hidden_width),
            nn.SiLU(),
            nn.Linear(self.hidden_width, self.hidden_width),
            nn.SiLU(),
            nn.Linear(self.hidden_width, rank),
        )
        self.to(dtype=torch.float64)

    def normalized_coefficients(self, normalized_mu: torch.Tensor) -> torch.Tensor:
        """Return normalized POD coefficients for five normalized inputs."""

        if normalized_mu.ndim != 2 or normalized_mu.shape[1] != self.input_dimension:
            raise ValueError("geometry latent inputs must have shape [batch, 5]")
        return self.network(normalized_mu)

    def forward(self, normalized_mu: torch.Tensor) -> torch.Tensor:
        """Return POD coefficients in the training-field coefficient scale."""

        normalized = self.normalized_coefficients(normalized_mu)
        return self.coefficient_center + self.coefficient_scale * normalized

    def decode_temperature(self, coefficients: torch.Tensor) -> torch.Tensor:
        """Decode coefficients using the train-only POD and smooth rise protection."""

        if coefficients.ndim != 2 or coefficients.shape[1] != self.rank:
            raise ValueError("coefficients do not match the configured POD rank")
        y = self.pod_mean_y + coefficients @ self.pod_basis
        raw_rise_K = torch.expm1(y)
        beta = self.smooth_nonnegative_beta_K
        protected_rise_K = beta * F.softplus(raw_rise_K / beta)
        return self.ambient_temperature_K + protected_rise_K

    def initial_temperature(
        self, normalized_mu: torch.Tensor, ny: int, nx: int
    ) -> torch.Tensor:
        """Decode and reshape the latent prediction into a batch of thermal fields."""

        temperature = self.decode_temperature(self(normalized_mu))
        if temperature.shape[1] != ny * nx:
            raise ValueError("decoded POD field does not match the requested grid")
        return temperature.reshape(-1, ny, nx)

    @property
    def parameter_count(self) -> int:
        """Return the number of trainable mapper parameters."""

        return sum(parameter.numel() for parameter in self.parameters())

"""Dynamic residual balancing utilities for stiffness-aware PINN MVPs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import torch
from torch import nn


def _residual_list(residuals: Sequence[torch.Tensor] | Mapping[str, torch.Tensor]) -> list[torch.Tensor]:
    values = list(residuals.values()) if isinstance(residuals, Mapping) else list(residuals)
    if not values:
        raise ValueError("At least one residual tensor is required.")
    return values


class DynamicResidualGate(nn.Module):
    """Softmax residual gate with anti-collapse safeguards.

    Safeguards used by default:

    - temperature scaling with `tau > 1`;
    - detached EMA residual-scale normalization;
    - entropy regularization;
    - minimum weight floor.
    """

    def __init__(
        self,
        num_losses: int,
        *,
        tau: float = 2.0,
        min_weight: float = 0.03,
        entropy_weight: float = 1.0e-3,
        ema_decay: float = 0.95,
        eps: float = 1.0e-12,
    ) -> None:
        super().__init__()
        if num_losses <= 0:
            raise ValueError("num_losses must be positive.")
        if tau <= 0.0:
            raise ValueError("tau must be positive.")
        if min_weight < 0.0 or min_weight >= 1.0:
            raise ValueError("min_weight must be in [0, 1).")
        if not 0.0 <= ema_decay < 1.0:
            raise ValueError("ema_decay must be in [0, 1).")
        self.num_losses = int(num_losses)
        self.tau = float(tau)
        self.min_weight = float(min_weight)
        self.entropy_weight = float(entropy_weight)
        self.ema_decay = float(ema_decay)
        self.eps = float(eps)
        self.logits = nn.Parameter(torch.zeros(self.num_losses))
        self.register_buffer("ema_scales", torch.ones(self.num_losses))
        self.register_buffer("ema_initialized", torch.tensor(False, dtype=torch.bool))

    def weights(self) -> torch.Tensor:
        """Return positive normalized weights with a minimum floor."""

        soft = torch.softmax(self.logits / self.tau, dim=0)
        if self.min_weight > 0.0:
            floor = self.min_weight / self.num_losses
            soft = (1.0 - self.min_weight) * soft + floor
        return soft / torch.sum(soft)

    def component_losses(self, residuals: Sequence[torch.Tensor] | Mapping[str, torch.Tensor]) -> torch.Tensor:
        """Return mean-square residual losses as a vector."""

        values = _residual_list(residuals)
        if len(values) != self.num_losses:
            raise ValueError(f"Expected {self.num_losses} residuals, got {len(values)}.")
        return torch.stack([torch.mean(value.square()) for value in values])

    def normalized_losses(self, losses: torch.Tensor) -> torch.Tensor:
        """Normalize residual scales with detached EMA safeguards."""

        safe_losses = torch.clamp(losses, min=self.eps)
        detached = safe_losses.detach()
        if self.training:
            with torch.no_grad():
                if not bool(self.ema_initialized.item()):
                    self.ema_scales.copy_(detached)
                    self.ema_initialized.fill_(True)
                else:
                    self.ema_scales.mul_(self.ema_decay).add_((1.0 - self.ema_decay) * detached)
        scales = torch.clamp(self.ema_scales.to(dtype=losses.dtype, device=losses.device), min=self.eps)
        return safe_losses / scales

    def forward(self, residuals: Sequence[torch.Tensor] | Mapping[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        """Return gated residual loss and diagnostics."""

        losses = self.component_losses(residuals)
        normalized = self.normalized_losses(losses)
        weights = self.weights().to(dtype=losses.dtype, device=losses.device)
        residual_loss = torch.sum(weights * normalized)
        entropy = -torch.sum(weights * torch.log(torch.clamp(weights, min=self.eps)))
        entropy_loss = -self.entropy_weight * entropy
        total = residual_loss + entropy_loss
        return {
            "total": total,
            "residual_loss": residual_loss,
            "entropy_loss": entropy_loss,
            "entropy": entropy,
            "weights": weights,
            "component_losses": losses,
            "normalized_losses": normalized,
        }


def gated_residual_loss(
    residuals: Sequence[torch.Tensor] | Mapping[str, torch.Tensor],
    gate: DynamicResidualGate | None = None,
    **gate_kwargs: Any,
) -> dict[str, torch.Tensor]:
    """Convenience wrapper for dynamic residual-gated loss."""

    values = _residual_list(residuals)
    module = gate or DynamicResidualGate(len(values), **gate_kwargs)
    return module(values)
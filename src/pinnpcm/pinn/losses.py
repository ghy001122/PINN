"""Loss aggregation for the PINN skeleton."""

from __future__ import annotations

import torch


def _mse(value: torch.Tensor) -> torch.Tensor:
    """Mean-square helper."""

    return torch.mean(value.square())


def total_loss(
    residuals: dict[str, torch.Tensor | dict[str, torch.Tensor]],
    data_terms: dict[str, torch.Tensor] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, torch.Tensor]:
    """Aggregate residual, boundary, initial, data, and regularization losses."""

    w = weights or {}
    device_tensor = next(value for value in residuals.values() if isinstance(value, torch.Tensor))
    zero = torch.zeros((), dtype=device_tensor.dtype, device=device_tensor.device)

    losses = {
        "L_phi": _mse(residuals["r_phi"]) if isinstance(residuals.get("r_phi"), torch.Tensor) else zero,
        "L_c": _mse(residuals["r_c"]) if isinstance(residuals.get("r_c"), torch.Tensor) else zero,
        "L_T": _mse(residuals["r_T"]) if isinstance(residuals.get("r_T"), torch.Tensor) else zero,
        "L_m": _mse(residuals["r_m"]) if isinstance(residuals.get("r_m"), torch.Tensor) else zero,
        "L_bc": zero,
        "L_ic": zero,
        "L_data": zero,
        "L_reg": zero,
    }

    if data_terms:
        data_loss = zero
        for residual in data_terms.values():
            data_loss = data_loss + _mse(residual)
        losses["L_data"] = data_loss

    total = zero
    for name, value in losses.items():
        total = total + float(w.get(name, 1.0)) * value
    losses["total"] = total
    return losses

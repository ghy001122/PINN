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


def _scalar_param(params: dict[str, float], key: str, like: torch.Tensor) -> torch.Tensor:
    """Return a scalar parameter tensor on the same device as a reference."""

    return torch.as_tensor(float(params[key]), dtype=like.dtype, device=like.device)


def reconstruct_port_from_sigma(
    sigma: torch.Tensor,
    voltage: torch.Tensor,
    dx: float,
    params: dict[str, float],
) -> dict[str, torch.Tensor]:
    """Reconstruct one-dimensional port `I(t)` and `G(t)` from `sigma(x,t)`.

    `sigma` must have shape `(nt, nx)` or `(batch, nx)`, matching the
    cell-centered series relation used by the frozen Ground Truth generator.
    """

    if sigma.ndim != 2:
        raise ValueError("sigma must have shape (nt, nx) or (batch, nx).")
    if voltage.ndim != 1 or voltage.shape[0] != sigma.shape[0]:
        raise ValueError("voltage must be one-dimensional and aligned with sigma.")

    eps_sigma = _scalar_param(params, "eps_sigma", sigma)
    eps_r = _scalar_param(params, "eps_R", sigma)
    eps_v = _scalar_param(params, "eps_V", sigma)
    active_area = _scalar_param(params, "eta_A", sigma) * _scalar_param(params, "A_contact", sigma)
    dx_tensor = torch.as_tensor(float(dx), dtype=sigma.dtype, device=sigma.device)

    sigma_safe = torch.clamp(sigma, min=eps_sigma)
    r_area = torch.sum(dx_tensor / sigma_safe, dim=-1) + eps_r
    current_density = voltage / r_area
    current = active_area * current_density
    conductance = current / (voltage + eps_v)

    return {
        "R_area": r_area,
        "J": current_density,
        "I": current,
        "G": conductance,
    }


def normalized_mse(
    pred: torch.Tensor,
    target: torch.Tensor,
    scale: float | torch.Tensor,
) -> torch.Tensor:
    """Mean-square error normalized by a positive scalar scale."""

    scale_tensor = torch.as_tensor(scale, dtype=pred.dtype, device=pred.device)
    scale_safe = torch.clamp(torch.abs(scale_tensor), min=torch.as_tensor(1.0e-30, dtype=pred.dtype, device=pred.device))
    return _mse((pred - target) / scale_safe)


def smoothness_loss(field: torch.Tensor) -> torch.Tensor:
    """First-difference smoothness penalty for a `(nt, nx)` field."""

    if field.ndim != 2:
        raise ValueError("smoothness_loss expects a two-dimensional field.")
    loss = torch.zeros((), dtype=field.dtype, device=field.device)
    if field.shape[0] > 1:
        loss = loss + _mse(field[1:, :] - field[:-1, :])
    if field.shape[1] > 1:
        loss = loss + _mse(field[:, 1:] - field[:, :-1])
    return loss


def physics_light_loss(fields: dict[str, torch.Tensor]) -> torch.Tensor:
    """Lightweight feasibility penalty for inverse v0 constrained outputs."""

    reference = next(iter(fields.values()))
    loss = torch.zeros((), dtype=reference.dtype, device=reference.device)
    if "delta_T" in fields:
        loss = loss + _mse(torch.relu(-fields["delta_T"]))
    if "m" in fields:
        loss = loss + _mse(torch.relu(-fields["m"])) + _mse(torch.relu(fields["m"] - 1.0))
    if "sigma" in fields:
        loss = loss + _mse(torch.relu(-fields["sigma"]))
    return loss

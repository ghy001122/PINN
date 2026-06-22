"""Physics-regularized residuals for PINN inverse v1.

The residuals in this module are intentionally lightweight approximations used
to regularize the inverse training pipeline. They are not a complete
PDE-constrained reproduction of the frozen Ground Truth solver.
"""

from __future__ import annotations

import torch

from pinnpcm.constants import K_B_EV_PER_K


def _param(params: dict[str, float], key: str, like: torch.Tensor, default: float | None = None) -> torch.Tensor:
    """Return a scalar parameter tensor matching a reference tensor."""

    if key in params:
        value = params[key]
    elif default is not None:
        value = default
    else:
        raise KeyError(key)
    return torch.as_tensor(float(value), dtype=like.dtype, device=like.device)


def _grad(y: torch.Tensor, coords: torch.Tensor) -> torch.Tensor:
    """Differentiate a field with respect to normalized coordinates."""

    grad = torch.autograd.grad(
        y,
        coords,
        grad_outputs=torch.ones_like(y),
        create_graph=True,
        retain_graph=True,
        allow_unused=True,
    )[0]
    if grad is None:
        return torch.zeros_like(coords)
    return grad


def triangle_voltage_torch(t_norm: torch.Tensor, params: dict[str, float]) -> torch.Tensor:
    """Differentiable triangular voltage protocol on normalized time."""

    v_peak = _param(params, "triangle_v_peak", t_norm, default=0.20)
    phase = torch.clamp(t_norm, 0.0, 1.0)
    return torch.where(phase <= 0.5, -v_peak + 4.0 * v_peak * phase, 3.0 * v_peak - 4.0 * v_peak * phase)


def _layer_param(
    params: dict[str, float],
    key: str,
    x_norm: torch.Tensor,
    default: float,
) -> torch.Tensor:
    """Return a possibly bilayer parameter profile."""

    profile = str(params.get("layer_profile", "uniform"))
    base = _param(params, key, x_norm, default=default)
    if profile != "bilayer":
        return torch.ones_like(x_norm) * base

    l_eff = _param(params, "L_eff", x_norm)
    l_int = _param(params, "L_int", x_norm, default=0.0)
    in_interface = x_norm * l_eff <= l_int
    nb_key = f"nb_oxide_{key}"
    v2_key = f"v2o5_{key}"
    nb_value = _param(params, nb_key, x_norm, default=float(base))
    v2_value = _param(params, v2_key, x_norm, default=float(base))
    return torch.where(in_interface, nb_value, v2_value)


def _arrhenius_torch(
    p0: torch.Tensor,
    activation_e_ev: torch.Tensor,
    temperature: torch.Tensor,
    reference_temperature: torch.Tensor,
) -> torch.Tensor:
    """Torch Arrhenius relation around a reference temperature."""

    safe_t = torch.clamp(temperature, min=1.0, max=5000.0)
    exponent = -activation_e_ev / K_B_EV_PER_K * (1.0 / safe_t - 1.0 / reference_temperature)
    return p0 * torch.exp(torch.clamp(exponent, min=-80.0, max=80.0))


def sigma_physics_torch(
    c_v: torch.Tensor,
    temperature: torch.Tensor,
    m: torch.Tensor,
    x_norm: torch.Tensor,
    params: dict[str, float],
) -> torch.Tensor:
    """Approximate differentiable conductivity closure for inverse v1."""

    c0 = _param(params, "c_v0", c_v)
    sigma_off0 = _layer_param(params, "sigma_off0", x_norm, default=float(params.get("sigma_off0", 3.0e-3)))
    sigma_on0 = _layer_param(params, "sigma_on0", x_norm, default=float(params.get("sigma_on0", 1.0)))
    thermal_factor = _arrhenius_torch(
        torch.ones_like(c_v),
        _param(params, "E_off_eV", c_v, default=0.12),
        temperature,
        _param(params, "T0", c_v),
    )
    sigma_off = sigma_off0 * thermal_factor * torch.exp(
        torch.clamp(_param(params, "beta_off", c_v, default=3.0) * (c_v - c0), min=-80.0, max=80.0)
    )
    sigma_on = sigma_on0 * torch.exp(
        torch.clamp(_param(params, "beta_on", c_v, default=7.0) * (c_v - c0), min=-80.0, max=80.0)
    )
    eps = _param(params, "eps_sigma", c_v, default=1.0e-30)
    m_safe = torch.clamp(m, 0.0, 1.0)
    log_sigma = (1.0 - m_safe) * torch.log(torch.clamp(sigma_off, min=eps)) + m_safe * torch.log(
        torch.clamp(sigma_on, min=eps)
    )
    return torch.exp(torch.clamp(log_sigma, min=-80.0, max=80.0))


def compute_field_derivatives(
    fields: dict[str, torch.Tensor],
    coords: torch.Tensor,
    *,
    x_scale: float,
    t_scale: float,
) -> dict[str, torch.Tensor]:
    """Compute first and second derivatives through torch autograd."""

    derivatives: dict[str, torch.Tensor] = {}
    x_scale_t = torch.as_tensor(float(x_scale), dtype=coords.dtype, device=coords.device)
    t_scale_t = torch.as_tensor(float(t_scale), dtype=coords.dtype, device=coords.device)

    for name in ("c_v", "delta_T", "m", "log_sigma", "sigma"):
        if name not in fields:
            continue
        grad = _grad(fields[name], coords)
        dx_norm = grad[..., 0:1]
        dt_norm = grad[..., 1:2]
        d2x_norm = _grad(dx_norm, coords)[..., 0:1]
        derivatives[f"{name}_x_norm"] = dx_norm
        derivatives[f"{name}_t_norm"] = dt_norm
        derivatives[f"{name}_xx_norm"] = d2x_norm
        derivatives[f"{name}_x"] = dx_norm / x_scale_t
        derivatives[f"{name}_t"] = dt_norm / t_scale_t
        derivatives[f"{name}_xx"] = d2x_norm / x_scale_t.square()
    return derivatives


def compute_physics_residuals(
    model: torch.nn.Module,
    coords: torch.Tensor,
    params: dict[str, float],
    *,
    x_scale: float,
    t_scale: float,
    physics_scales: dict[str, float] | None = None,
) -> dict[str, torch.Tensor | dict[str, torch.Tensor]]:
    """Compute inverse v1 approximate physics residuals on collocation points."""

    scales = physics_scales or {}
    coords_req = coords.detach().clone().requires_grad_(True)
    fields = model(coords_req)
    x_norm = coords_req[..., 0:1]
    t_norm = coords_req[..., 1:2]
    temperature = _param(params, "T0", x_norm) + fields["delta_T"]
    derivatives = compute_field_derivatives(fields, coords_req, x_scale=x_scale, t_scale=t_scale)

    v_app = triangle_voltage_torch(t_norm, params)
    v_peak = torch.clamp(torch.abs(_param(params, "triangle_v_peak", x_norm, default=0.20)), min=1.0e-12)
    v_norm = v_app / v_peak
    temp_scale = torch.as_tensor(10.0, dtype=coords_req.dtype, device=coords_req.device)
    sigma_ref = torch.clamp(_param(params, "sigma_on0", x_norm, default=1.0), min=1.0e-12)

    theta = fields["delta_T"] / temp_scale
    heat_residual = (
        derivatives["delta_T_t_norm"] / temp_scale
        - float(scales.get("heat_diffusion", 2.0e-2)) * derivatives["delta_T_xx_norm"] / temp_scale
        - float(scales.get("heat_source", 5.0e-2)) * v_norm.square() * fields["sigma"] / sigma_ref
        + float(scales.get("heat_cooling", 1.0e-1)) * theta
    )

    m_eq = torch.sigmoid(
        (
            temperature
            - _param(params, "T_sw", x_norm)
            + _param(params, "alpha_c", x_norm) * (fields["c_v"] - _param(params, "c_v0", x_norm))
        )
        / _param(params, "dT_sw", x_norm)
    )
    state_residual = _param(params, "tau_m", x_norm) * derivatives["m_t"] - (m_eq - fields["m"])

    defect_residual = (
        derivatives["c_v_t_norm"]
        - float(scales.get("defect_diffusion", 2.0e-3)) * derivatives["c_v_xx_norm"]
        + float(scales.get("defect_drift", 1.0e-3)) * v_norm * derivatives["c_v_x_norm"]
        + float(scales.get("defect_relaxation", 5.0e-2)) * (fields["c_v"] - _param(params, "c_v0", x_norm))
    )

    sigma_physics = sigma_physics_torch(fields["c_v"], temperature, fields["m"], x_norm, params)
    eps_sigma = _param(params, "eps_sigma", x_norm, default=1.0e-30)
    sigma_consistency = torch.log(torch.clamp(fields["sigma"], min=eps_sigma)) - torch.log(
        torch.clamp(sigma_physics, min=eps_sigma)
    )

    return {
        "heat_residual": heat_residual,
        "state_residual": state_residual,
        "defect_residual": defect_residual,
        "sigma_consistency": sigma_consistency,
        "fields": fields,
        "derivatives": derivatives,
        "sigma_physics": sigma_physics,
    }


def compute_boundary_residuals(
    model: torch.nn.Module,
    t_norm: torch.Tensor,
    params: dict[str, float],
    *,
    x_scale: float,
    t_scale: float,
) -> dict[str, torch.Tensor]:
    """Compute no-flux style boundary residuals for `delta_T` and `c_v`."""

    zeros = torch.zeros_like(t_norm)
    ones = torch.ones_like(t_norm)
    coords = torch.cat(
        [
            torch.stack([zeros, t_norm], dim=-1).reshape(-1, 2),
            torch.stack([ones, t_norm], dim=-1).reshape(-1, 2),
        ],
        dim=0,
    )
    residuals = compute_physics_residuals(
        model,
        coords,
        params,
        x_scale=x_scale,
        t_scale=t_scale,
        physics_scales={},
    )
    derivatives = residuals["derivatives"]
    if not isinstance(derivatives, dict):
        raise TypeError("derivatives must be a dictionary")
    return {
        "temperature_boundary": derivatives["delta_T_x_norm"],
        "defect_boundary": derivatives["c_v_x_norm"],
    }

"""Autograd residual interfaces for the PINN skeleton."""

from __future__ import annotations

from collections.abc import Callable

import torch

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.pinn.transforms import apply_physical_transforms


def _param(params: dict[str, float], key: str, like: torch.Tensor) -> torch.Tensor:
    """Return a scalar parameter tensor matching a reference tensor."""

    return torch.as_tensor(params[key], dtype=like.dtype, device=like.device)


def _grad(y: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
    """Compute dy/dx with autograd, returning zeros when unused."""

    grad = torch.autograd.grad(
        y,
        x,
        grad_outputs=torch.ones_like(y),
        create_graph=True,
        retain_graph=True,
        allow_unused=True,
    )[0]
    if grad is None:
        return torch.zeros_like(x)
    return grad


def _arrhenius_torch(
    p0: torch.Tensor,
    activation_e_ev: torch.Tensor,
    temperature: torch.Tensor,
    reference_temperature: torch.Tensor,
) -> torch.Tensor:
    """Torch version of the reference-temperature Arrhenius relation."""

    safe_t = torch.clamp(temperature, min=1.0, max=5000.0)
    exponent = -activation_e_ev / K_B_EV_PER_K * (1.0 / safe_t - 1.0 / reference_temperature)
    return p0 * torch.exp(torch.clamp(exponent, min=-80.0, max=80.0))


def _sigma_torch(c_v: torch.Tensor, temperature: torch.Tensor, m: torch.Tensor, params: dict[str, float]) -> torch.Tensor:
    """Torch conductivity model consistent with the NumPy Ground Truth code."""

    c0 = _param(params, "c_v0", c_v)
    sigma_off0 = _param(params, "sigma_off0", c_v)
    sigma_on0 = _param(params, "sigma_on0", c_v)
    sigma_off = sigma_off0 * _arrhenius_torch(
        torch.ones_like(sigma_off0),
        _param(params, "E_off_eV", c_v),
        temperature,
        _param(params, "T0", c_v),
    ) * torch.exp(torch.clamp(_param(params, "beta_off", c_v) * (c_v - c0), min=-80.0, max=80.0))
    sigma_on = sigma_on0 * torch.exp(torch.clamp(_param(params, "beta_on", c_v) * (c_v - c0), min=-80.0, max=80.0))
    log_sigma = (1.0 - m) * torch.log(torch.clamp(sigma_off, min=_param(params, "eps_sigma", c_v))) + m * torch.log(
        torch.clamp(sigma_on, min=_param(params, "eps_sigma", c_v))
    )
    return torch.exp(torch.clamp(log_sigma, min=-80.0, max=80.0))


def _voltage_tensor(voltage_fn: Callable[[torch.Tensor], torch.Tensor], t_norm: torch.Tensor) -> torch.Tensor:
    """Evaluate a voltage function and return a tensor on the current device."""

    try:
        voltage = voltage_fn(t_norm)
        if isinstance(voltage, torch.Tensor):
            return voltage.to(dtype=t_norm.dtype, device=t_norm.device)
    except Exception:
        pass

    with torch.no_grad():
        voltage_np = voltage_fn(t_norm.detach().cpu().numpy())
    return torch.as_tensor(voltage_np, dtype=t_norm.dtype, device=t_norm.device)


def compute_residuals(
    model: torch.nn.Module,
    coords: torch.Tensor,
    params: dict[str, float],
    voltage_fn: Callable[[torch.Tensor], torch.Tensor],
) -> dict[str, torch.Tensor]:
    """Compute first-version PINN residuals from normalized coordinates.

    This skeleton keeps the public interface stable while the inverse-training
    workflow is developed. The terms are dimensionally scaled by `L_eff` and
    an optional `t_scale` parameter when provided.
    """

    coords_req = coords.detach().clone().requires_grad_(True)
    raw = model(coords_req)
    fields = apply_physical_transforms(raw, params)

    x_norm = coords_req[..., 0:1]
    t_norm = coords_req[..., 1:2]
    _ = x_norm
    voltage = _voltage_tensor(voltage_fn, t_norm)

    phi = fields["phi"]
    c_v = fields["c_v"]
    temperature = fields["T"]
    m = fields["m"]
    sigma = _sigma_torch(c_v, temperature, m, params)

    grad_phi = _grad(phi, coords_req)
    grad_c = _grad(c_v, coords_req)
    grad_t = _grad(temperature, coords_req)
    grad_m = _grad(m, coords_req)

    phi_x = grad_phi[..., 0:1] / _param(params, "L_eff", phi)
    c_x = grad_c[..., 0:1] / _param(params, "L_eff", c_v)
    c_t = grad_c[..., 1:2] / torch.as_tensor(params.get("t_scale", 1.0), dtype=c_v.dtype, device=c_v.device)
    temp_x = grad_t[..., 0:1] / _param(params, "L_eff", temperature)
    temp_t = grad_t[..., 1:2] / torch.as_tensor(params.get("t_scale", 1.0), dtype=temperature.dtype, device=temperature.device)
    m_t = grad_m[..., 1:2] / torch.as_tensor(params.get("t_scale", 1.0), dtype=m.dtype, device=m.device)

    sigma_phi_x = sigma * phi_x
    r_phi = _grad(sigma_phi_x, coords_req)[..., 0:1] / _param(params, "L_eff", phi)

    electric_field = -phi_x
    d_v = _arrhenius_torch(_param(params, "D_v0", c_v), _param(params, "E_D_eV", c_v), temperature, _param(params, "T0", c_v))
    mu_v = _arrhenius_torch(_param(params, "mu_v0", c_v), _param(params, "E_mu_eV", c_v), temperature, _param(params, "T0", c_v))
    k_r = _arrhenius_torch(_param(params, "k_r0", c_v), _param(params, "E_r_eV", c_v), temperature, _param(params, "T0", c_v))
    flux_v = -d_v * c_x + mu_v * c_v * (1.0 - c_v) * electric_field
    r_c = c_t + _grad(flux_v, coords_req)[..., 0:1] / _param(params, "L_eff", c_v) + k_r * (c_v - _param(params, "c_v0", c_v))

    heat_flux = -_param(params, "k_th", temperature) * temp_x
    joule_heat = sigma * electric_field.square()
    r_T = (
        _param(params, "rho", temperature) * _param(params, "Cp", temperature) * temp_t
        + _grad(heat_flux, coords_req)[..., 0:1] / _param(params, "L_eff", temperature)
        - joule_heat
        + _param(params, "gamma_sub", temperature) * (temperature - _param(params, "T0", temperature))
    )

    m_eq = torch.sigmoid(
        (
            temperature
            - _param(params, "T_sw", temperature)
            + _param(params, "alpha_c", temperature) * (c_v - _param(params, "c_v0", temperature))
        )
        / _param(params, "dT_sw", temperature)
    )
    r_m = m_t - (m_eq - m) / _param(params, "tau_m", m)

    active_area = _param(params, "eta_A", sigma) * _param(params, "A_contact", sigma)
    current_density = sigma * electric_field
    i_pred = active_area * current_density
    g_pred = i_pred / (voltage + _param(params, "eps_V", voltage))

    return {
        "r_phi": r_phi,
        "r_c": r_c,
        "r_T": r_T,
        "r_m": r_m,
        "I_pred": i_pred,
        "G_pred": g_pred,
        "fields": fields,
    }

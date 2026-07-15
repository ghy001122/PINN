"""Dimensionless residual and boundary operators for ``FullPINN1D``."""

from __future__ import annotations

from typing import Any

import torch

from pinnpcm.constants import K_B_EV_PER_K


def _scalar(value: float, like: torch.Tensor) -> torch.Tensor:
    return torch.as_tensor(value, dtype=like.dtype, device=like.device)


def _grad(y: torch.Tensor, coords: torch.Tensor) -> torch.Tensor:
    result = torch.autograd.grad(
        y,
        coords,
        grad_outputs=torch.ones_like(y),
        create_graph=True,
        retain_graph=True,
        allow_unused=True,
    )[0]
    return torch.zeros_like(coords) if result is None else result


def _arrhenius(prefactor: torch.Tensor, energy_ev: float, temperature: torch.Tensor, t0: float) -> torch.Tensor:
    safe_t = torch.clamp(temperature, 1.0, 5000.0)
    exponent = -energy_ev / K_B_EV_PER_K * (1.0 / safe_t - 1.0 / t0)
    return prefactor * torch.exp(torch.clamp(exponent, -80.0, 80.0))


def compute_full_residuals(model: torch.nn.Module, coords: torch.Tensor) -> dict[str, torch.Tensor]:
    """Evaluate all four physical residuals with explicit SI derivatives."""

    z = coords.detach().clone().requires_grad_(True)
    fields = model(z)
    params: dict[str, Any] = model.params
    length = float(params["L_eff"])
    duration = float(model.t_max_s)

    phi = fields["phi"]
    c_v = fields["c_v"]
    temperature = fields["T"]
    m = fields["m"]
    sigma = fields["sigma"]
    profiles = fields["profiles"]

    grad_phi = _grad(phi, z)
    grad_c = _grad(c_v, z)
    grad_temperature = _grad(temperature, z)
    grad_m = _grad(m, z)
    phi_x = grad_phi[..., 0:1] / length
    c_x = grad_c[..., 0:1] / length
    c_t = grad_c[..., 1:2] / duration
    temperature_x = grad_temperature[..., 0:1] / length
    temperature_t = grad_temperature[..., 1:2] / duration
    m_t = grad_m[..., 1:2] / duration

    electric_field = -phi_x
    current_density = sigma * electric_field
    r_phi_si = _grad(sigma * phi_x, z)[..., 0:1] / length

    d_v = _arrhenius(profiles["D_v0"], float(params["E_D_eV"]), temperature, float(params["T0"]))
    mu_v = _arrhenius(profiles["mu_v0"], float(params["E_mu_eV"]), temperature, float(params["T0"]))
    k_r = _arrhenius(
        torch.ones_like(c_v) * _scalar(float(params["k_r0"]), c_v),
        float(params["E_r_eV"]),
        temperature,
        float(params["T0"]),
    )
    defect_flux = -d_v * c_x + mu_v * c_v * (1.0 - c_v) * electric_field
    r_c_si = c_t + _grad(defect_flux, z)[..., 0:1] / length + k_r * (
        c_v - _scalar(float(params["c_v0"]), c_v)
    )

    heat_flux = -profiles["k_th"] * temperature_x
    joule_heat = sigma * electric_field.square()
    r_t_si = (
        float(params["rho"]) * float(params["Cp"]) * temperature_t
        + _grad(heat_flux, z)[..., 0:1] / length
        - joule_heat
        + float(params["gamma_sub"]) * (temperature - float(params["T0"]))
    )
    m_eq = model.equilibrium_phase(c_v, temperature)
    r_m_si = m_t - (m_eq - m) / float(params["tau_m"])

    sigma_reference = max(
        float(params["nb_oxide_sigma_on0"]),
        float(params["v2o5_sigma_on0"]),
        float(params["sigma_on0"]),
    )
    phi_scale = max(float(model.voltage_scale_v), 1.0e-12)
    temperature_scale = max(float(model.temperature_scale_k), 1.0)
    r_phi_scale = sigma_reference * phi_scale / length**2
    r_c_scale = 1.0 / duration + max(float(params["D_v0"]), 1.0e-30) / length**2 + float(params["k_r0"])
    r_t_scale = (
        float(params["rho"]) * float(params["Cp"]) * temperature_scale / duration
        + max(float(params["k_th"]), float(params.get("v2o5_k_th", params["k_th"]))) * temperature_scale / length**2
        + float(params["gamma_sub"]) * temperature_scale
        + sigma_reference * (phi_scale / length) ** 2
    )
    r_m_scale = 1.0 / duration + 1.0 / float(params["tau_m"])

    return {
        "r_phi": r_phi_si / r_phi_scale,
        "r_c": r_c_si / r_c_scale,
        "r_T": r_t_si / r_t_scale,
        "r_m": r_m_si / r_m_scale,
        "r_phi_si": r_phi_si,
        "r_c_si": r_c_si,
        "r_T_si": r_t_si,
        "r_m_si": r_m_si,
        "electric_field": electric_field,
        "current_density": current_density,
        "defect_flux": defect_flux,
        "heat_flux": heat_flux,
        "fields": fields,
        "coords": z,
    }


def compute_boundary_terms(model: torch.nn.Module, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
    """Evaluate hard Dirichlet and physical no-flux endpoint conditions."""

    t = t_norm.reshape(-1, 1)
    zeros = torch.zeros_like(t)
    ones = torch.ones_like(t)
    left = compute_full_residuals(model, torch.cat([zeros, t], dim=-1))
    right = compute_full_residuals(model, torch.cat([ones, t], dim=-1))
    voltage = model.voltage(t)
    params = model.params
    defect_scale = max(float(params["D_v0"]) / float(params["L_eff"]), 1.0e-30)
    heat_scale = max(float(params["k_th"]) * float(model.temperature_scale_k) / float(params["L_eff"]), 1.0e-30)
    return {
        "phi_left": left["fields"]["phi"] / max(float(model.voltage_scale_v), 1.0e-12),
        "phi_right": (right["fields"]["phi"] - voltage) / max(float(model.voltage_scale_v), 1.0e-12),
        "defect_left": left["defect_flux"] / defect_scale,
        "defect_right": right["defect_flux"] / defect_scale,
        "heat_left": left["heat_flux"] / heat_scale,
        "heat_right": right["heat_flux"] / heat_scale,
    }


def compute_interface_terms(
    model: torch.nn.Module,
    t_norm: torch.Tensor,
    probe_fraction: float,
) -> dict[str, torch.Tensor]:
    """Evaluate a bounded one-sided interface diagnostic/loss.

    Passing this diagnostic is not used to resurrect the historical P1 claim.
    """

    interface = float(model.params["L_int"]) / float(model.params["L_eff"])
    eps = float(probe_fraction)
    t = t_norm.reshape(-1, 1)
    left_coords = torch.cat([torch.full_like(t, interface - eps), t], dim=-1)
    right_coords = torch.cat([torch.full_like(t, interface + eps), t], dim=-1)
    left = compute_full_residuals(model, left_coords)
    right = compute_full_residuals(model, right_coords)
    voltage_scale = max(float(model.voltage_scale_v), 1.0e-12)
    temperature_scale = max(float(model.temperature_scale_k), 1.0)
    current_scale = max(
        float(model.params["sigma_on0"]) * voltage_scale / float(model.params["L_eff"]), 1.0e-30
    )
    defect_scale = max(float(model.params["D_v0"]) / float(model.params["L_eff"]), 1.0e-30)
    heat_scale = max(float(model.params["k_th"]) * temperature_scale / float(model.params["L_eff"]), 1.0e-30)
    return {
        "phi_jump": (right["fields"]["phi"] - left["fields"]["phi"]) / voltage_scale,
        "c_jump": right["fields"]["c_v"] - left["fields"]["c_v"],
        "temperature_jump": (right["fields"]["T"] - left["fields"]["T"]) / temperature_scale,
        "m_jump": right["fields"]["m"] - left["fields"]["m"],
        "current_flux_jump": (right["current_density"] - left["current_density"]) / current_scale,
        "defect_flux_jump": (right["defect_flux"] - left["defect_flux"]) / defect_scale,
        "heat_flux_jump": (right["heat_flux"] - left["heat_flux"]) / heat_scale,
    }


def squared_mean(terms: dict[str, torch.Tensor]) -> torch.Tensor:
    values = [torch.mean(value.square()) for value in terms.values()]
    return torch.stack(values).mean()


def residual_rms(residuals: dict[str, torch.Tensor]) -> dict[str, float]:
    return {
        key: float(torch.sqrt(torch.mean(residuals[key].detach().square())).cpu())
        for key in ("r_phi", "r_c", "r_T", "r_m")
    }

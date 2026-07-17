"""SI strong-form and exact-trace operators for the N0-R split PINN."""

from __future__ import annotations

from typing import Any

import torch

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.pinn.full_pinn_1d_split import DomainName, DualDomainFullPINN1D


def _float(value: Any) -> float:
    return float(value)


def _scalar(value: float, like: torch.Tensor) -> torch.Tensor:
    return torch.as_tensor(value, dtype=like.dtype, device=like.device)


def _grad(value: torch.Tensor, coordinates: torch.Tensor) -> torch.Tensor:
    result = torch.autograd.grad(
        value,
        coordinates,
        grad_outputs=torch.ones_like(value),
        create_graph=True,
        retain_graph=True,
        allow_unused=True,
    )[0]
    return torch.zeros_like(coordinates) if result is None else result


def _arrhenius(prefactor: torch.Tensor, energy_eV: float, temperature: torch.Tensor, reference_K: float) -> torch.Tensor:
    safe_temperature = torch.clamp(temperature, 1.0, 5000.0)
    exponent = -float(energy_eV) / K_B_EV_PER_K * (1.0 / safe_temperature - 1.0 / float(reference_K))
    return prefactor * torch.exp(torch.clamp(exponent, -80.0, 80.0))


def layer_residual_scales(model: DualDomainFullPINN1D, domain: DomainName) -> dict[str, Any]:
    """Preregistered dimensional term-sum scales for one material layer."""

    params = model.params
    length_domain = model.domain_length_m(domain)
    length_global = _float(params["L_eff"])
    duration = float(model.t_max_s)
    if domain == "left":
        sigma_off = _float(params["nb_oxide_sigma_off0"])
        sigma_on = _float(params["nb_oxide_sigma_on0"])
        diffusion = _float(params["nb_oxide_D_v0"])
        mobility = _float(params["nb_oxide_mu_v0"])
        conductivity_thermal = _float(params["nb_oxide_k_th"])
    else:
        sigma_off = _float(params["v2o5_sigma_off0"])
        sigma_on = _float(params["v2o5_sigma_on0"])
        diffusion = _float(params["v2o5_D_v0"])
        mobility = _float(params["v2o5_mu_v0"])
        conductivity_thermal = _float(params["v2o5_k_th"])
    sigma_reference = max(sigma_off, sigma_on)
    voltage = max(float(model.voltage_scale_v), 1.0e-12)
    temperature = max(float(model.temperature_scale_k), 1.0)
    defect_terms = {
        "storage": 1.0 / duration,
        "diffusion": diffusion / length_domain**2,
        "drift": 0.25 * mobility * voltage / (length_global * length_domain),
        "reaction": _float(params["k_r0"]),
    }
    thermal_terms = {
        "storage": _float(params["rho"]) * _float(params["Cp"]) * temperature / duration,
        "conduction": conductivity_thermal * temperature / length_domain**2,
        "joule": sigma_reference * (voltage / length_global) ** 2,
        "sink": _float(params["gamma_sub"]) * temperature,
    }
    phase_terms = {"storage": 1.0 / duration, "relaxation": 1.0 / _float(params["tau_m"])}
    electrical_terms = {
        "conductivity_voltage_curvature": sigma_reference * voltage / length_domain**2,
    }
    return {
        "domain": domain,
        "length_m": length_domain,
        "electrical_terms": electrical_terms,
        "defect_terms": defect_terms,
        "thermal_terms": thermal_terms,
        "phase_terms": phase_terms,
        "r_phi": sum(electrical_terms.values()),
        "r_c": sum(defect_terms.values()),
        "r_T": sum(thermal_terms.values()),
        "r_m": sum(phase_terms.values()),
    }


def compute_domain_quantities(
    model: DualDomainFullPINN1D, local_coords: torch.Tensor, domain: DomainName
) -> dict[str, Any]:
    """Evaluate states, SI first derivatives, and physical fluxes."""

    coordinates = local_coords.detach().clone().requires_grad_(True)
    fields = model.forward_domain(coordinates, domain)
    params = model.params
    length = model.domain_length_m(domain)
    duration = float(model.t_max_s)
    phi_gradient = _grad(fields["phi"], coordinates)
    concentration_gradient = _grad(fields["c_v"], coordinates)
    temperature_gradient = _grad(fields["T"], coordinates)
    phase_gradient = _grad(fields["m"], coordinates)
    phi_x = phi_gradient[..., :1] / length
    concentration_x = concentration_gradient[..., :1] / length
    concentration_t = concentration_gradient[..., 1:] / duration
    temperature_x = temperature_gradient[..., :1] / length
    temperature_t = temperature_gradient[..., 1:] / duration
    phase_t = phase_gradient[..., 1:] / duration
    electric_field = -phi_x
    current_density = fields["sigma"] * electric_field
    diffusion = _arrhenius(
        fields["profiles"]["D_v0"], _float(params["E_D_eV"]), fields["T"], _float(params["T0"])
    )
    mobility = _arrhenius(
        fields["profiles"]["mu_v0"], _float(params["E_mu_eV"]), fields["T"], _float(params["T0"])
    )
    reaction_rate = _arrhenius(
        torch.ones_like(fields["c_v"]) * _scalar(_float(params["k_r0"]), fields["c_v"]),
        _float(params["E_r_eV"]),
        fields["T"],
        _float(params["T0"]),
    )
    defect_flux = (
        -diffusion * concentration_x
        + mobility * fields["c_v"] * (1.0 - fields["c_v"]) * electric_field
    )
    heat_flux = -fields["profiles"]["k_th"] * temperature_x
    return {
        "coords": coordinates,
        "fields": fields,
        "phi_x": phi_x,
        "c_x": concentration_x,
        "c_t": concentration_t,
        "T_x": temperature_x,
        "T_t": temperature_t,
        "m_t": phase_t,
        "electric_field": electric_field,
        "current_density": current_density,
        "diffusion": diffusion,
        "mobility": mobility,
        "reaction_rate": reaction_rate,
        "defect_flux": defect_flux,
        "heat_flux": heat_flux,
    }


def compute_domain_residuals(
    model: DualDomainFullPINN1D, local_coords: torch.Tensor, domain: DomainName
) -> dict[str, Any]:
    """Evaluate all four normalized residuals in one smooth material domain."""

    quantities = compute_domain_quantities(model, local_coords, domain)
    coordinates = quantities["coords"]
    fields = quantities["fields"]
    params = model.params
    length = model.domain_length_m(domain)
    r_phi_si = _grad(fields["sigma"] * quantities["phi_x"], coordinates)[..., :1] / length
    defect_divergence = _grad(quantities["defect_flux"], coordinates)[..., :1] / length
    reaction = quantities["reaction_rate"] * (
        fields["c_v"] - _scalar(_float(params["c_v0"]), fields["c_v"])
    )
    r_c_si = quantities["c_t"] + defect_divergence + reaction
    heat_flux_divergence = _grad(quantities["heat_flux"], coordinates)[..., :1] / length
    heat_storage = _float(params["rho"]) * _float(params["Cp"]) * quantities["T_t"]
    joule = fields["sigma"] * quantities["electric_field"].square()
    sink = _float(params["gamma_sub"]) * (fields["T"] - _float(params["T0"]))
    r_T_si = heat_storage + heat_flux_divergence - joule + sink
    equilibrium = model.equilibrium_phase(fields["c_v"], fields["T"])
    relaxation = (equilibrium - fields["m"]) / _float(params["tau_m"])
    r_m_si = quantities["m_t"] - relaxation
    scales = layer_residual_scales(model, domain)
    return {
        **quantities,
        "r_phi": r_phi_si / scales["r_phi"],
        "r_c": r_c_si / scales["r_c"],
        "r_T": r_T_si / scales["r_T"],
        "r_m": r_m_si / scales["r_m"],
        "r_phi_si": r_phi_si,
        "r_c_si": r_c_si,
        "r_T_si": r_T_si,
        "r_m_si": r_m_si,
        "defect_divergence": defect_divergence,
        "reaction": reaction,
        "heat_storage": heat_storage,
        "heat_flux_divergence": heat_flux_divergence,
        "joule": joule,
        "sink": sink,
        "phase_relaxation": relaxation,
        "scales": scales,
    }


def flux_scales(model: DualDomainFullPINN1D) -> dict[str, float]:
    params = model.params
    voltage = max(float(model.voltage_scale_v), 1.0e-12)
    left_length = model.domain_length_m("left")
    right_length = model.domain_length_m("right")
    sigma_left = _float(params["nb_oxide_sigma_off0"])
    sigma_right = _float(params["v2o5_sigma_off0"])
    current = voltage / (left_length / sigma_left + right_length / sigma_right)
    defect = max(
        _float(params["nb_oxide_D_v0"]) / left_length
        + 0.25 * _float(params["nb_oxide_mu_v0"]) * voltage / _float(params["L_eff"]),
        _float(params["v2o5_D_v0"]) / right_length
        + 0.25 * _float(params["v2o5_mu_v0"]) * voltage / _float(params["L_eff"]),
    )
    heat = max(
        _float(params["nb_oxide_k_th"]) * float(model.temperature_scale_k) / left_length,
        _float(params["v2o5_k_th"]) * float(model.temperature_scale_k) / right_length,
    )
    return {"current": max(current, 1.0e-30), "defect": max(defect, 1.0e-30), "heat": max(heat, 1.0e-30)}


def compute_boundary_terms(model: DualDomainFullPINN1D, t_norm: torch.Tensor) -> dict[str, torch.Tensor]:
    t = t_norm.reshape(-1, 1)
    left = compute_domain_quantities(model, torch.cat([torch.zeros_like(t), t], dim=-1), "left")
    right = compute_domain_quantities(model, torch.cat([torch.ones_like(t), t], dim=-1), "right")
    scales = flux_scales(model)
    return {
        "phi_left": (left["fields"]["phi"] - model.voltage(t)) / max(model.voltage_scale_v, 1.0e-12),
        "phi_right": right["fields"]["phi"] / max(model.voltage_scale_v, 1.0e-12),
        "defect_left": left["defect_flux"] / scales["defect"],
        "defect_right": right["defect_flux"] / scales["defect"],
        "heat_left": left["heat_flux"] / scales["heat"],
        "heat_right": right["heat_flux"] / scales["heat"],
    }


def compute_exact_interface_terms(
    model: DualDomainFullPINN1D, t_norm: torch.Tensor
) -> dict[str, dict[str, torch.Tensor]]:
    t = t_norm.reshape(-1, 1)
    left = compute_domain_quantities(model, torch.cat([torch.ones_like(t), t], dim=-1), "left")
    right = compute_domain_quantities(model, torch.cat([torch.zeros_like(t), t], dim=-1), "right")
    scales = flux_scales(model)
    state = {
        "phi": (right["fields"]["phi"] - left["fields"]["phi"]) / max(model.voltage_scale_v, 1.0e-12),
        "c_v": right["fields"]["c_v"] - left["fields"]["c_v"],
        "T": (right["fields"]["T"] - left["fields"]["T"]) / max(model.temperature_scale_k, 1.0),
        "m": right["fields"]["m"] - left["fields"]["m"],
    }
    flux = {
        "current": (right["current_density"] - left["current_density"]) / scales["current"],
        "heat": (right["heat_flux"] - left["heat_flux"]) / scales["heat"],
        "defect": (right["defect_flux"] - left["defect_flux"]) / scales["defect"],
    }
    return {"state": state, "flux": flux, "left": left, "right": right}


def squared_mean(terms: dict[str, torch.Tensor]) -> torch.Tensor:
    return torch.stack([torch.mean(value.square()) for value in terms.values()]).mean()


def residual_rms(residuals: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(torch.sqrt(torch.mean(residuals[key].detach().square())).cpu())
        for key in ("r_phi", "r_c", "r_T", "r_m")
    }


def term_rms(terms: dict[str, torch.Tensor]) -> dict[str, float]:
    return {
        key: float(torch.sqrt(torch.mean(value.detach().square())).cpu())
        for key, value in terms.items()
    }

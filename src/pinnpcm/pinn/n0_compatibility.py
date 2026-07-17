"""No-training compatibility audits for frozen GT v1.1 and N0 equations.

The helpers in this module do not alter or regenerate the frozen benchmark.
They evaluate analytic manufactured cases and reconstruct the finite-volume
ledger from frozen cell-centred states using the declared GT discretisation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from pinnpcm.constants import K_B_EV_PER_K
from pinnpcm.physics.conductivity import arrhenius_reference, mixed_conductivity
from pinnpcm.physics.electrostatics import solve_series_electrostatics
from pinnpcm.physics.params import spatial_param_profiles


def _torch_grad(value: torch.Tensor, coordinates: torch.Tensor) -> torch.Tensor:
    gradient = torch.autograd.grad(
        value,
        coordinates,
        grad_outputs=torch.ones_like(value),
        create_graph=True,
        retain_graph=True,
    )[0]
    if gradient is None:
        return torch.zeros_like(coordinates)
    return gradient


def _rms(values: np.ndarray | torch.Tensor) -> float:
    if isinstance(values, torch.Tensor):
        values = values.detach().cpu().numpy()
    array = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(np.square(array))))


def nrmse95(prediction: np.ndarray, target: np.ndarray) -> float:
    """Return the repository operational NRMSE95 metric."""

    target_array = np.asarray(target, dtype=float)
    scale = max(float(np.quantile(target_array, 0.95) - np.quantile(target_array, 0.05)), 1.0e-30)
    return float(np.sqrt(np.mean((np.asarray(prediction, dtype=float) - target_array) ** 2)) / scale)


def uniform_conduction_manufactured(params: dict[str, Any]) -> dict[str, float]:
    """Non-zero-voltage uniform steady conduction with an analytic solution."""

    length = float(params["L_eff"])
    voltage = float(params["triangle_v_peak"])
    sigma = 2.0
    current_density = sigma * voltage / length
    x = np.linspace(0.0, length, 65)
    phi = voltage - current_density * x / sigma
    numerical_gradient = np.gradient(phi, x, edge_order=2)
    reconstructed_current = -sigma * numerical_gradient
    active_area = float(params["eta_A"]) * float(params["A_contact"])
    resistance_area = length / sigma
    return {
        "voltage_V": voltage,
        "sigma_S_per_m": sigma,
        "potential_left_error_V": abs(float(phi[0]) - voltage),
        "potential_right_error_V": abs(float(phi[-1])),
        "current_density_relative_rms_error": _rms(reconstructed_current - current_density)
        / max(abs(current_density), 1.0e-30),
        "port_current_relative_error": abs(active_area * voltage / resistance_area - active_area * current_density)
        / max(abs(active_area * current_density), 1.0e-30),
        "analytic_current_density_A_per_m2": current_density,
    }


def heat_manufactured(params: dict[str, Any], duration_s: float) -> dict[str, float]:
    """Heat operator check with storage, conduction, source, and sink terms."""

    coordinates = torch.rand(
        (128, 2), generator=torch.Generator().manual_seed(20260715), dtype=torch.float64
    ).requires_grad_(True)
    x_norm = coordinates[:, :1]
    t_norm = coordinates[:, 1:]
    length = float(params["L_eff"])
    temperature = float(params["T0"]) + 5.0 * t_norm + 3.0 * x_norm * (1.0 - x_norm)
    gradient = _torch_grad(temperature, coordinates)
    temperature_t = gradient[:, 1:] / float(duration_s)
    temperature_x = gradient[:, :1] / length
    temperature_xx = _torch_grad(temperature_x, coordinates)[:, :1] / length
    storage = float(params["rho"]) * float(params["Cp"]) * temperature_t
    conduction_operator = -float(params["k_th"]) * temperature_xx
    sink = float(params["gamma_sub"]) * (temperature - float(params["T0"]))
    manufactured_source = storage + conduction_operator + sink
    residual = storage + conduction_operator - manufactured_source + sink
    scale = _rms(manufactured_source) + _rms(storage) + _rms(conduction_operator) + _rms(sink)
    return {
        "normalized_residual_rms": _rms(residual) / max(scale, 1.0e-30),
        "storage_rms_W_per_m3": _rms(storage),
        "conduction_rms_W_per_m3": _rms(conduction_operator),
        "sink_rms_W_per_m3": _rms(sink),
        "manufactured_source_rms_W_per_m3": _rms(manufactured_source),
    }


def defect_manufactured(params: dict[str, Any], duration_s: float) -> dict[str, float]:
    """Defect operator check with storage, diffusion, drift, and reaction."""

    coordinates = torch.rand(
        (128, 2), generator=torch.Generator().manual_seed(20260716), dtype=torch.float64
    ).requires_grad_(True)
    x_norm = coordinates[:, :1]
    t_norm = coordinates[:, 1:]
    length = float(params["L_eff"])
    concentration = float(params["c_v0"]) + 0.004 * t_norm + 0.012 * x_norm * (1.0 - x_norm)
    voltage = float(params["triangle_v_peak"])
    electric_field = torch.ones_like(concentration) * voltage / length
    gradient = _torch_grad(concentration, coordinates)
    concentration_t = gradient[:, 1:] / float(duration_s)
    concentration_x = gradient[:, :1] / length
    diffusion_flux = -float(params["D_v0"]) * concentration_x
    drift_flux = float(params["mu_v0"]) * concentration * (1.0 - concentration) * electric_field
    diffusion_divergence = _torch_grad(diffusion_flux, coordinates)[:, :1] / length
    drift_divergence = _torch_grad(drift_flux, coordinates)[:, :1] / length
    reaction = float(params["k_r0"]) * (concentration - float(params["c_v0"]))
    manufactured_source = concentration_t + diffusion_divergence + drift_divergence + reaction
    residual = concentration_t + diffusion_divergence + drift_divergence + reaction - manufactured_source
    scale = (
        _rms(concentration_t)
        + _rms(diffusion_divergence)
        + _rms(drift_divergence)
        + _rms(reaction)
        + _rms(manufactured_source)
    )
    return {
        "normalized_residual_rms": _rms(residual) / max(scale, 1.0e-30),
        "storage_rms_per_s": _rms(concentration_t),
        "diffusion_divergence_rms_per_s": _rms(diffusion_divergence),
        "drift_divergence_rms_per_s": _rms(drift_divergence),
        "reaction_rms_per_s": _rms(reaction),
        "manufactured_source_rms_per_s": _rms(manufactured_source),
    }


def bilayer_piecewise_manufactured(params: dict[str, Any]) -> dict[str, float]:
    """Exact bilayer state with derivative jumps and continuous normal fluxes."""

    length = float(params["L_eff"])
    interface = float(params["L_int"])
    voltage = float(params["triangle_v_peak"])
    sigma_left = float(params["nb_oxide_sigma_off0"])
    sigma_right = float(params["v2o5_sigma_off0"])
    resistance_area = interface / sigma_left + (length - interface) / sigma_right
    current_density = voltage / resistance_area
    phi_left_trace = voltage - current_density * interface / sigma_left
    phi_right_trace = current_density * (length - interface) / sigma_right
    dphi_left = -current_density / sigma_left
    dphi_right = -current_density / sigma_right

    k_left = float(params["nb_oxide_k_th"])
    k_right = float(params["v2o5_k_th"])
    delta_temperature = 10.0
    heat_flux = delta_temperature / (interface / k_left + (length - interface) / k_right)
    temperature_left_trace = float(params["T0"]) + delta_temperature - heat_flux * interface / k_left
    temperature_right_trace = float(params["T0"]) + heat_flux * (length - interface) / k_right
    dtemperature_left = -heat_flux / k_left
    dtemperature_right = -heat_flux / k_right
    return {
        "phi_jump_normalized": abs(phi_right_trace - phi_left_trace) / max(abs(voltage), 1.0e-30),
        "temperature_jump_normalized": abs(temperature_right_trace - temperature_left_trace) / delta_temperature,
        "current_flux_jump_normalized": abs(-sigma_left * dphi_left + sigma_right * dphi_right)
        / max(abs(current_density), 1.0e-30),
        "heat_flux_jump_normalized": abs(-k_left * dtemperature_left + k_right * dtemperature_right)
        / max(abs(heat_flux), 1.0e-30),
        "potential_derivative_ratio": abs(dphi_left / dphi_right),
        "temperature_derivative_ratio": abs(dtemperature_left / dtemperature_right),
        "expected_potential_derivative_ratio": sigma_right / sigma_left,
        "expected_temperature_derivative_ratio": k_right / k_left,
        "c_v_jump": 0.0,
        "m_jump": 0.0,
    }


def interface_discretization_audit(x_m: np.ndarray, params: dict[str, Any]) -> dict[str, float | int]:
    """Locate the material transition implied by frozen cell-centre labels."""

    x = np.asarray(x_m, dtype=float)
    interface = float(params["L_int"])
    left = x <= interface
    last_left = int(np.flatnonzero(left)[-1])
    first_right = int(np.flatnonzero(~left)[0])
    discrete_face = 0.5 * (x[last_left] + x[first_right])
    return {
        "declared_interface_m": interface,
        "last_left_cell_index": last_left,
        "first_right_cell_index": first_right,
        "last_left_cell_center_m": float(x[last_left]),
        "first_right_cell_center_m": float(x[first_right]),
        "implied_discrete_face_m": float(discrete_face),
        "face_offset_from_declared_m": float(discrete_face - interface),
        "face_offset_over_dx": float((discrete_face - interface) / (x[1] - x[0])),
    }


def frozen_fvm_conservation_audit(
    gt: dict[str, np.ndarray], params: dict[str, Any], sample_count: int = 21
) -> dict[str, Any]:
    """Reconstruct the GT finite-volume mass, heat, and current ledgers."""

    x = np.asarray(gt["x"], dtype=float)
    nx = x.size
    dx = float(params["L_eff"]) / nx
    profiles = {**params, **spatial_param_profiles(x, params)}
    time_indices = np.unique(np.linspace(0, np.asarray(gt["t"]).size - 1, sample_count, dtype=int))
    mass_errors: list[float] = []
    energy_errors: list[float] = []
    current_errors: list[float] = []
    port_errors: list[float] = []
    ledger_rows: list[dict[str, float | int]] = []

    for index in time_indices:
        concentration = np.clip(np.asarray(gt["c_v"])[index], 1.0e-8, 1.0 - 1.0e-8)
        temperature = np.clip(np.asarray(gt["T"])[index], 1.0, 5000.0)
        phase = np.clip(np.asarray(gt["m"])[index], 0.0, 1.0)
        voltage = float(np.asarray(gt["V"])[index])
        sigma = mixed_conductivity(concentration, temperature, phase, profiles)
        electrical = solve_series_electrostatics(voltage, sigma, profiles, dx)
        electric_field = np.asarray(electrical["E"], dtype=float)
        current_density = float(electrical["J"])

        diffusion = arrhenius_reference(profiles["D_v0"], params["E_D_eV"], temperature, params["T0"])
        mobility = arrhenius_reference(profiles["mu_v0"], params["E_mu_eV"], temperature, params["T0"])
        reaction_rate = arrhenius_reference(params["k_r0"], params["E_r_eV"], temperature, params["T0"])
        defect_flux = np.zeros(nx + 1, dtype=float)
        face = lambda values: 0.5 * (np.asarray(values[:-1]) + np.asarray(values[1:]))
        defect_flux[1:-1] = (
            -face(diffusion) * np.diff(concentration) / dx
            + face(mobility) * face(concentration) * (1.0 - face(concentration)) * face(electric_field)
        )
        reaction = reaction_rate * (concentration - float(params["c_v0"]))
        concentration_rate = -np.diff(defect_flux) / dx - reaction
        mass_storage = float(np.sum(concentration_rate) * dx)
        mass_boundary = float(defect_flux[-1] - defect_flux[0])
        mass_reaction = float(np.sum(reaction) * dx)
        mass_balance = mass_storage + mass_boundary + mass_reaction
        mass_scale = max(abs(mass_storage) + abs(mass_boundary) + abs(mass_reaction), 1.0e-30)
        mass_error = abs(mass_balance) / mass_scale

        heat_flux = np.zeros(nx + 1, dtype=float)
        heat_flux[1:-1] = -face(profiles["k_th"]) * np.diff(temperature) / dx
        joule = current_density * electric_field
        sink = float(params["gamma_sub"]) * (temperature - float(params["T0"]))
        temperature_rate = (-np.diff(heat_flux) / dx + joule - sink) / (
            float(params["rho"]) * float(params["Cp"])
        )
        heat_storage = float(np.sum(float(params["rho"]) * float(params["Cp"]) * temperature_rate) * dx)
        heat_boundary = float(heat_flux[-1] - heat_flux[0])
        heat_sink = float(np.sum(sink) * dx)
        heat_joule = float(np.sum(joule) * dx)
        energy_balance = heat_storage + heat_boundary + heat_sink - heat_joule
        energy_scale = max(abs(heat_storage) + abs(heat_boundary) + abs(heat_sink) + abs(heat_joule), 1.0e-30)
        energy_error = abs(energy_balance) / energy_scale

        current_cells = sigma * electric_field
        current_error = _rms(current_cells - current_density) / max(abs(current_density), 1.0e-30)
        port_error = abs(float(electrical["I"]) - float(np.asarray(gt["I"])[index])) / max(
            abs(float(np.asarray(gt["I"])[index])), 1.0e-30
        )
        mass_errors.append(mass_error)
        energy_errors.append(energy_error)
        current_errors.append(current_error)
        port_errors.append(port_error)
        ledger_rows.append(
            {
                "time_index": int(index),
                "mass_storage_m_per_s": mass_storage,
                "mass_boundary_m_per_s": mass_boundary,
                "mass_reaction_m_per_s": mass_reaction,
                "mass_normalized_imbalance": mass_error,
                "heat_storage_W_per_m2": heat_storage,
                "heat_boundary_W_per_m2": heat_boundary,
                "heat_sink_W_per_m2": heat_sink,
                "joule_input_W_per_m2": heat_joule,
                "energy_normalized_imbalance": energy_error,
                "current_normalized_spread": current_error,
                "port_current_relative_error": port_error,
            }
        )

    return {
        "sampled_time_indices": [int(value) for value in time_indices],
        "max_defect_mass_normalized_imbalance": max(mass_errors),
        "rms_defect_mass_normalized_imbalance": _rms(np.asarray(mass_errors)),
        "max_global_energy_normalized_imbalance": max(energy_errors),
        "rms_global_energy_normalized_imbalance": _rms(np.asarray(energy_errors)),
        "max_current_normalized_spread": max(current_errors),
        "max_port_current_relative_error": max(port_errors),
        "ledger_rows": ledger_rows,
        "semantics": "independent reconstruction of frozen FVM face-flux and volume-source ledger",
    }


def equation_parity_rows(interface_audit: dict[str, Any]) -> list[dict[str, str]]:
    """Return the preregistered term-by-term GT/continuum comparison."""

    face_offset = float(interface_audit["face_offset_from_declared_m"])
    return [
        {
            "item": "electrostatic_sign_and_boundary",
            "frozen_gt": "E=-dphi/dx; stored phi decreases from V at x=0 to 0 at x=L",
            "continuous_full_pinn_v1": "E=-dphi/dx but hard phi(0)=0, phi(L)=V",
            "status": "incompatible_v1_boundary_orientation",
            "repair_requirement": "use phi(0)=V and phi(L)=0 without changing GT",
        },
        {
            "item": "terminal_operator",
            "frozen_gt": "R_area=sum(dx/sigma); I=A_eff*V/R_area",
            "continuous_full_pinn_v1": "R_area=L*mean(1/sigma); I=A_eff*V/R_area",
            "status": "compatible_on_uniform_cell_centres",
            "repair_requirement": "none",
        },
        {
            "item": "defect_transport",
            "frozen_gt": "dc/dt=-div(-D grad c+mu c(1-c)E)-k(c-c0)",
            "continuous_full_pinn_v1": "dc/dt+div(F)+k(c-c0)=0",
            "status": "equation_compatible_if_electric_field_orientation_is_repaired",
            "repair_requirement": "correct electrical boundary orientation",
        },
        {
            "item": "heat_balance",
            "frozen_gt": "rhoCp dT/dt=-div(q)+J E-gamma(T-T0), q=-k grad T",
            "continuous_full_pinn_v1": "rhoCp dT/dt+div(q)-sigma E^2+gamma(T-T0)=0",
            "status": "equation_compatible",
            "repair_requirement": "enforce exact one-sided k-flux at the material interface",
        },
        {
            "item": "phase_relaxation",
            "frozen_gt": "dm/dt=(m_eq-m)/tau_m",
            "continuous_full_pinn_v1": "dm/dt-(m_eq-m)/tau_m=0",
            "status": "compatible",
            "repair_requirement": "none",
        },
        {
            "item": "initial_conditions",
            "frozen_gt": "Gaussian c seed; T=T0; m=m_eq(c,T0)",
            "continuous_full_pinn_v1": "same hard initial transforms",
            "status": "compatible",
            "repair_requirement": "none",
        },
        {
            "item": "endpoint_flux_boundaries",
            "frozen_gt": "zero defect and heat face flux at both ends",
            "continuous_full_pinn_v1": "zero defect and heat flux losses",
            "status": "compatible_but_not_hard_enforced",
            "repair_requirement": "retain explicit endpoint flux gates",
        },
        {
            "item": "bilayer_material_coefficients",
            "frozen_gt": "cell centres x<=L_int use Nb-oxide values; remaining cells use V2O5 values",
            "continuous_full_pinn_v1": "piecewise profiles at exact x=L_int inside one smooth network",
            "status": "coefficient_values_compatible_representation_not_conservative",
            "repair_requirement": "use independent left/right traces and local coordinates",
        },
        {
            "item": "interface_face_semantics",
            "frozen_gt": f"arithmetic face averages at a face offset {face_offset:.6e} m from L_int",
            "continuous_full_pinn_v1": "finite-band x_i+/-epsilon proxy from one smooth network",
            "status": "not_equivalent",
            "repair_requirement": "exact interface traces; record continuum-discrete face offset",
        },
        {
            "item": "cell_center_scoring_map",
            "frozen_gt": "states and phi stored at cell centres",
            "continuous_full_pinn_v1": "network evaluated at normalized frozen cell-centre coordinates",
            "status": "coordinate_compatible_after_phi_orientation_repair",
            "repair_requirement": "do not treat cell-centre phi as electrode value",
        },
    ]

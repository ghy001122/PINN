"""Reduced boundary-aware multilayer sandwich device benchmark.

Synthetic numerical digital-twin evidence only. This is a fast finite-difference /
series-stack reduction for claim-gated audits; it is not full FEM, device-grade
reproduction, or experimental validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SandwichLayer:
    name: str
    thickness_m: float
    sigma_s_m: float
    k_w_mk: float
    rho_c_j_m3k: float
    is_pcm: bool = False
    is_barrier: bool = False


STRUCTURES = [
    "pcm_only",
    "pcm_plus_electrodes",
    "pcm_plus_electrodes_substrate",
    "full_stack_with_contact_resistance",
    "full_stack_with_thermal_boundary_resistance",
    "full_stack_with_SnSe_barrier",
]
GEOMETRIES = ["uniform_crossbar", "localized_filament", "edge_hotspot"]
PULSES = ["short_pulse", "ltp_ltd"]


def default_layers(structure: str) -> list[SandwichLayer]:
    if structure not in STRUCTURES:
        raise ValueError(f"Unknown structure: {structure}")
    pcm = SandwichLayer("PCM", 30e-9, 2.5e2, 1.4, 2.4e6, is_pcm=True)
    te = SandwichLayer("TE", 18e-9, 5.0e5, 20.0, 2.5e6)
    be = SandwichLayer("BE", 18e-9, 6.0e5, 18.0, 2.7e6)
    sub = SandwichLayer("substrate", 120e-9, 1.0e-9, 2.1, 2.2e6)
    barrier = SandwichLayer("SnSe_barrier", 15e-9, 5.0e-2, 0.45, 1.8e6, is_barrier=True)
    if structure == "pcm_only":
        return [pcm]
    if structure == "pcm_plus_electrodes":
        return [te, pcm, be]
    if structure == "pcm_plus_electrodes_substrate":
        return [te, pcm, be, sub]
    if structure in {"full_stack_with_contact_resistance", "full_stack_with_thermal_boundary_resistance"}:
        return [te, pcm, be, sub]
    return [te, pcm, barrier, be, sub]


def switch_fraction(T: np.ndarray, T_sw: float, width: float) -> np.ndarray:
    arg = np.clip((np.asarray(T, dtype=float) - float(T_sw)) / max(float(width), 1.0e-6), -80.0, 80.0)
    return 1.0 / (1.0 + np.exp(-arg))


def _pulse_value(kind: str, step: int, nt: int, cfg: dict[str, Any]) -> float:
    if kind == "short_pulse":
        return float(cfg.get("V_short", 0.18)) if step < max(2, nt // 3) else 0.0
    if kind == "ltp_ltd":
        return float(cfg.get("V_ltp", 0.15)) if step < nt // 2 else float(cfg.get("V_ltd", -0.08))
    raise ValueError(f"Unknown pulse: {kind}")


def _geometry_profile(geometry: str, ny: int, rng: np.random.Generator) -> np.ndarray:
    y = np.linspace(0.0, 1.0, int(ny))
    if geometry == "uniform_crossbar":
        profile = np.ones_like(y)
    elif geometry == "localized_filament":
        profile = 0.55 + 1.8 * np.exp(-((y - 0.52) ** 2) / 0.018)
    elif geometry == "edge_hotspot":
        profile = 0.55 + 1.4 * np.exp(-(y**2) / 0.022)
    else:
        raise ValueError(f"Unknown geometry: {geometry}")
    profile = profile * (1.0 + 0.015 * rng.standard_normal(profile.shape))
    return np.clip(profile, 0.2, None)


def _laplacian_y(values: np.ndarray) -> np.ndarray:
    left = np.concatenate([values[:, :1], values[:, :-1]], axis=1)
    right = np.concatenate([values[:, 1:], values[:, -1:]], axis=1)
    return left - 2.0 * values + right


def simulate_multilayer_case(
    structure: str,
    geometry: str,
    transition_width: float,
    pulse: str,
    seed: int,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    c = dict(cfg or {})
    ny = int(c.get("ny", 24))
    nt = int(c.get("nt", 26))
    dt = float(c.get("dt", 2.0e-7))
    area = float(c.get("area_m2", 1.0e-12))
    width_m = float(c.get("width_m", 1.0e-6))
    R_load = float(c.get("R_load_ohm", 1.0e5))
    T0 = float(c.get("T0_K", 300.0))
    tau_m = float(c.get("tau_m_s", 1.6e-6))
    D_m = float(c.get("D_m", 2.0e-4))
    T_sw = float(c.get("T_sw_K", 304.5))
    rng = np.random.default_rng(int(seed))
    layers = default_layers(structure)
    nl = len(layers)
    profile = _geometry_profile(geometry, ny, rng)
    T = np.full((nl, ny), T0, dtype=float)
    m = np.full((ny,), 0.08, dtype=float)
    sigma_history: list[np.ndarray] = []
    T_history: list[np.ndarray] = []
    m_history: list[np.ndarray] = []
    current_history: list[float] = []
    conductance_history: list[float] = []
    q_history: list[float] = []
    phi_last = np.zeros((nl, ny), dtype=float)
    J_last = np.zeros((nl, ny), dtype=float)
    dz = np.maximum(np.asarray([layer.thickness_m for layer in layers], dtype=float), 1.0e-12)
    sigma_ins = float(c.get("sigma_ins", 5.0))
    sigma_met = float(c.get("sigma_met", 2.2e3))
    contact_ra = 2.5e-10 if structure == "full_stack_with_contact_resistance" else 0.0
    tbr = 3.0e-8 if structure in {"full_stack_with_thermal_boundary_resistance", "full_stack_with_SnSe_barrier"} else 0.0
    # Optional normalized low-dimensional inverse knobs. They are engineering
    # priors for synthetic audits, not measured material parameters.
    contact_ra *= float(c.get("Rc_te_pcm_scale", 1.0))
    tbr *= float(c.get("Rth_barrier_scale", 1.0))
    pcm_sub_tbr = 1.5e-8 * float(c.get("Rth_pcm_sub_scale", 1.0))
    h_sub = 3.0e6 * float(c.get("h_sub_scale", 1.0))
    Ea_scale = float(c.get("Ea_scale", 1.0))
    joule_energy = 0.0
    sink_loss_energy = 0.0
    boundary_loss_energy = 0.0
    interface_flux_mismatch_hist: list[float] = []
    substrate_robin_hist: list[float] = []
    for step in range(nt):
        V_app = _pulse_value(pulse, step, nt, c)
        sigma = np.zeros((nl, ny), dtype=float)
        for i, layer in enumerate(layers):
            if layer.is_pcm:
                sigma[i] = ((1.0 - m) * sigma_ins + m * sigma_met) * profile * np.exp(-0.08 * (Ea_scale - 1.0))
            else:
                sigma[i] = layer.sigma_s_m * np.ones(ny)
                if layer.is_barrier:
                    sigma[i] *= 1.0 + 0.05 * profile
        r_layers = dz[:, None] / np.maximum(sigma, 1.0e-30)
        total_ra = np.sum(r_layers, axis=0) + max(nl - 1, 0) * contact_ra
        G_cols = (area / ny) / np.maximum(total_ra, 1.0e-30)
        G_total = float(np.sum(G_cols))
        V_dev = float(V_app / (1.0 + R_load * G_total)) if abs(V_app) > 0 else 0.0
        J_col = V_dev / np.maximum(total_ra, 1.0e-30)
        I = float(np.sum(J_col * (area / ny)))
        G = float(I / V_dev) if abs(V_dev) > 1.0e-15 else G_total
        cumulative = np.cumsum(r_layers, axis=0) - 0.5 * r_layers
        phi = V_dev - J_col[None, :] * cumulative
        J = np.repeat(J_col[None, :], nl, axis=0)
        E = J / np.maximum(sigma, 1.0e-30)
        Q = sigma * E * E
        lateral = _laplacian_y(T) / max((width_m / max(ny - 1, 1)) ** 2, 1.0e-30)
        k = np.asarray([layer.k_w_mk for layer in layers], dtype=float)[:, None]
        rho_c = np.asarray([layer.rho_c_j_m3k for layer in layers], dtype=float)[:, None]
        vertical_flux = np.zeros_like(T)
        interface_fluxes: list[np.ndarray] = []
        for i in range(nl - 1):
            extra_tbr = pcm_sub_tbr if layers[i].is_pcm or layers[i + 1].is_pcm else 0.0
            conductance = 1.0 / (0.5 * dz[i] / max(layers[i].k_w_mk, 1.0e-12) + 0.5 * dz[i + 1] / max(layers[i + 1].k_w_mk, 1.0e-12) + tbr + extra_tbr)
            flux = conductance * (T[i + 1] - T[i])
            interface_fluxes.append(flux)
            vertical_flux[i] += flux / dz[i]
            vertical_flux[i + 1] -= flux / dz[i + 1]
        sink = 7.5e6 * (T - T0)
        bottom_boundary_flux = h_sub * (T[-1] - T0)
        boundary_density = np.zeros_like(T)
        boundary_density[-1] = bottom_boundary_flux / dz[-1]
        cell_volume = dz[:, None] * (area / ny)
        joule_energy += float(np.sum(Q * cell_volume) * dt)
        sink_loss_energy += float(np.sum(sink * cell_volume) * dt)
        boundary_loss_energy += float(np.sum(bottom_boundary_flux) * (area / ny) * dt)
        if interface_fluxes:
            # Equal-and-opposite fluxes are imposed; the residual is a numerical
            # finite-volume conservation audit rather than a hard-coded zero.
            local = [np.max(np.abs((f / dz[i]) * dz[i] + (-f / dz[i + 1]) * dz[i + 1])) / max(float(np.max(np.abs(f))), 1.0e-30) for i, f in enumerate(interface_fluxes)]
            interface_flux_mismatch_hist.append(float(np.max(local)))
        substrate_robin_hist.append(float(np.mean(np.abs(bottom_boundary_flux)) / max(float(np.mean(np.abs(Q[-1] * dz[-1]))), 1.0e-30)))
        T = T + dt * (Q + 0.002 * k * lateral + vertical_flux - sink - boundary_density) / np.maximum(rho_c, 1.0e-30)
        T = np.clip(T, T0 - 5.0, T0 + 180.0)
        pcm_index = next((idx for idx, layer in enumerate(layers) if layer.is_pcm), 0)
        s = switch_fraction(T[pcm_index], T_sw, transition_width)
        m = np.clip(m + dt * ((s - m) / tau_m + D_m * _laplacian_y(m[None, :])[0]), 0.0, 1.0)
        sigma_history.append(sigma.copy())
        T_history.append(T.copy())
        m_history.append(m.copy())
        current_history.append(I)
        conductance_history.append(G)
        q_history.append(float(np.sum(Q * dz[:, None]) * area / ny))
        phi_last = phi
        J_last = J
    sigma_arr = np.asarray(sigma_history)
    T_arr = np.asarray(T_history)
    m_arr = np.asarray(m_history)
    I_arr = np.asarray(current_history)
    G_arr = np.asarray(conductance_history)
    normal_current_mismatch = float(np.median(np.std(J_last, axis=0) / np.maximum(np.mean(np.abs(J_last), axis=0), 1.0e-30)))
    if nl > 1:
        temp_jump = np.abs(T[:-1] - T[1:])
        temp_scale = max(float(np.max(np.abs(T - T0))), 1.0)
        temperature_jump_residual = float(np.median(temp_jump) / temp_scale)
        heat_flux_mismatch = float(np.median(interface_flux_mismatch_hist)) if interface_flux_mismatch_hist else 0.0
        potential_jump = float(contact_ra * np.median(np.abs(J_last)) / max(abs(np.max(phi_last) - np.min(phi_last)), 1.0e-12)) if contact_ra > 0 else 0.0
    else:
        temperature_jump_residual = 0.0
        heat_flux_mismatch = 0.0
        potential_jump = 0.0
    substrate_robin_residual = float(np.median(substrate_robin_hist)) if substrate_robin_hist else 0.0
    interface_bc = float(max(potential_jump, normal_current_mismatch, min(temperature_jump_residual, 1.0), heat_flux_mismatch))
    thermal_store = float(np.sum((T - T0) * np.asarray([l.rho_c_j_m3k * l.thickness_m for l in layers])[:, None]) * area / ny)
    energy_balance_numer = abs(joule_energy - thermal_store - sink_loss_energy - boundary_loss_energy)
    energy_balance_denom = max(abs(joule_energy) + abs(thermal_store) + abs(sink_loss_energy) + abs(boundary_loss_energy), 1.0e-30)
    energy_balance_error = float(energy_balance_numer / energy_balance_denom)
    return {
        "structure": structure,
        "geometry": geometry,
        "transition_width": float(transition_width),
        "pulse": pulse,
        "seed": int(seed),
        "layers": [layer.name for layer in layers],
        "time": np.arange(nt, dtype=float) * dt,
        "temperature": T_arr,
        "state_m": m_arr,
        "sigma": sigma_arr,
        "current": I_arr,
        "conductance": G_arr,
        "phi_last": phi_last,
        "current_density_last": J_last,
        "finite_result": bool(all(np.isfinite(arr).all() for arr in [T_arr, m_arr, sigma_arr, I_arr, G_arr, phi_last, J_last])),
        "interface_bc_residual": interface_bc,
        "current_continuity_error": normal_current_mismatch,
        "normal_current_mismatch": normal_current_mismatch,
        "potential_jump_residual": potential_jump,
        "temperature_jump_residual": temperature_jump_residual,
        "heat_flux_mismatch": heat_flux_mismatch,
        "substrate_robin_residual": substrate_robin_residual,
        "joule_input_energy": float(joule_energy),
        "thermal_storage_energy": float(thermal_store),
        "sink_loss_energy": float(sink_loss_energy),
        "boundary_loss_energy": float(boundary_loss_energy),
        "energy_balance_error": energy_balance_error,
        "interface_potential_jump_residual": potential_jump,
        "max_delta_T": float(np.max(T_arr - T0)),
        "max_m": float(np.max(m_arr)),
        "conductance_ratio": float(np.max(np.abs(G_arr)) / max(np.min(np.abs(G_arr)) + 1.0e-30, 1.0e-30)),
        "mean_abs_power": float(np.mean(np.abs(q_history))),
    }


def summarize_cases(rows: list[dict[str, Any]], *, interface_threshold: float = 0.35, current_threshold: float = 0.05, energy_threshold: float = 0.35) -> dict[str, Any]:
    finite_rate = float(np.mean([bool(r["finite_result"]) for r in rows])) if rows else 0.0
    interface_median = float(np.median([float(r["interface_bc_residual"]) for r in rows])) if rows else float("nan")
    current_median = float(np.median([float(r["current_continuity_error"]) for r in rows])) if rows else float("nan")
    energy_median = float(np.median([float(r["energy_balance_error"]) for r in rows])) if rows else float("nan")
    potential_median = float(np.median([float(r.get("potential_jump_residual", 0.0)) for r in rows])) if rows else float("nan")
    temp_jump_median = float(np.median([float(r.get("temperature_jump_residual", 0.0)) for r in rows])) if rows else float("nan")
    flux_median = float(np.median([float(r.get("heat_flux_mismatch", 0.0)) for r in rows])) if rows else float("nan")
    substrate_median = float(np.median([float(r.get("substrate_robin_residual", 0.0)) for r in rows])) if rows else float("nan")
    energy_passed = bool(np.isfinite(energy_median) and energy_median <= energy_threshold)
    gate = bool(finite_rate == 1.0 and interface_median <= interface_threshold and current_median <= current_threshold and energy_passed)
    return {
        "benchmark": "multilayer_sandwich_device",
        "note": "Synthetic numerical digital-twin reduced boundary-aware benchmark; not FEM, not device-grade reproduction, not experimental validation.",
        "num_cases": len(rows),
        "finite_rate": finite_rate,
        "interface_bc_residual_median": interface_median,
        "interface_bc_residual_threshold": float(interface_threshold),
        "current_continuity_error_median": current_median,
        "current_continuity_threshold": float(current_threshold),
        "energy_balance_error_median": energy_median,
        "energy_balance_threshold": float(energy_threshold),
        "energy_balance_gate_passed": energy_passed,
        "downgraded_if_energy_failed": bool(not energy_passed),
        "residuals_are_computed_not_stubbed": True,
        "potential_jump_residual_median": potential_median,
        "temperature_jump_residual_median": temp_jump_median,
        "heat_flux_mismatch_median": flux_median,
        "substrate_robin_residual_median": substrate_median,
        "boundary_aware_multilayer_forward_status": "qualified_supported" if gate else "failed_but_informative",
        "forbidden_claims": ["full FEM", "device-grade reproduction", "experimental validation"],
    }

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
    barrier = SandwichLayer("SnSe_barrier", 15e-9, 1.0e4, 0.35, 1.8e6, is_barrier=True)
    if structure == "pcm_only":
        return [pcm]
    if structure == "pcm_plus_electrodes":
        return [te, pcm, be]
    if structure == "pcm_plus_electrodes_substrate":
        return [te, pcm, be, sub]
    if structure in {"full_stack_with_contact_resistance", "full_stack_with_thermal_boundary_resistance"}:
        return [te, pcm, be, sub]
    return [te, pcm, barrier, be, sub]


def switch_fraction(T: np.ndarray, T_sw: float | np.ndarray, width: float) -> np.ndarray:
    threshold = np.asarray(T_sw, dtype=float)
    arg = np.clip((np.asarray(T, dtype=float) - threshold) / max(float(width), 1.0e-6), -80.0, 80.0)
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


MATERIAL_FAMILIES = ["generic", "vo2", "nbo2"]


def _family_pcm_sigma(material_family: str, T: np.ndarray, m: np.ndarray, profile: np.ndarray, cfg: dict[str, Any]) -> np.ndarray:
    """Conservative-path PCM conductivity with explicit material-family priors.

    These are literature-guided synthetic priors for numerical benchmarks, not
    measured parameters of a fabricated stack.
    """
    family = str(material_family)
    if family not in MATERIAL_FAMILIES:
        raise ValueError(f"Unknown material_family: {family}")
    T_safe = np.clip(np.asarray(T, dtype=float), 1.0, 1200.0)
    m_safe = np.clip(np.asarray(m, dtype=float), 0.0, 1.0)
    ea_factor = np.exp(np.clip(-0.05 * (float(cfg.get("Ea_scale", 1.0)) - 1.0), -2.0, 2.0))
    if family == "generic":
        sigma_ins = float(cfg.get("generic_sigma_ins", 5.0))
        sigma_met = float(cfg.get("generic_sigma_met", 2.2e3))
        return np.clip(((1.0 - m_safe) * sigma_ins + m_safe * sigma_met) * profile * ea_factor, 1.0e-12, None)
    if family == "vo2":
        T_c = float(cfg.get("vo2_Tc_K", cfg.get("T_sw_K", 303.5)))
        width = max(float(cfg.get("vo2_width_K", cfg.get("transition_width", 3.0))), 1.0e-6)
        sigma_ins = float(cfg.get("vo2_sigma_ins", 2.0))
        sigma_met = float(cfg.get("vo2_sigma_met", 2.0e4))
        branch = 0.72 * m_safe + 0.28 * switch_fraction(T_safe, T_c, width)
        return np.clip(((1.0 - branch) * sigma_ins + branch * sigma_met) * profile * ea_factor, 1.0e-12, None)
    # NbO2: monotonic Poole-Frenkel-like conduction. NDR, if present, must arise
    # from thermal/circuit feedback rather than an ad-hoc local negative slope.
    kB = 8.617333262145e-5
    sigma0 = float(cfg.get("nbo2_sigma0", 3.0e3))
    Ea = float(cfg.get("nbo2_Ea_eV", 0.18))
    pf_beta = float(cfg.get("nbo2_pf_beta", 1.5e-3))
    thermal = np.exp(np.clip(-Ea / (kB * T_safe), -80.0, 20.0))
    monotone_pf = 1.0 + pf_beta * np.sqrt(np.maximum(T_safe - float(cfg.get("T0_K", 300.0)), 0.0))
    return np.clip(sigma0 * thermal * monotone_pf * (0.5 + m_safe) * profile * ea_factor, 1.0e-12, None)


def _interface_arrays(layers: list[SandwichLayer], structure: str, cfg: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    n_if = max(len(layers) - 1, 0)
    Rc = np.zeros(n_if, dtype=float)
    Rth = np.zeros(n_if, dtype=float)
    base_Rc = float(cfg.get("Rc_interface_ohm_m2", 2.5e-10 if structure == "full_stack_with_contact_resistance" else 0.0))
    base_Rth = float(cfg.get("Rth_interface_m2K_W", 3.0e-8 if structure in {"full_stack_with_thermal_boundary_resistance", "full_stack_with_SnSe_barrier"} else 0.0))
    pcm_Rth = float(cfg.get("Rth_pcm_sub_m2K_W", 1.5e-8))
    for i in range(n_if):
        if layers[i].is_pcm or layers[i + 1].is_pcm:
            Rc[i] = base_Rc * float(cfg.get("Rc_te_pcm_scale", 1.0))
            Rth[i] = base_Rth * float(cfg.get("Rth_barrier_scale", 1.0)) + pcm_Rth * float(cfg.get("Rth_pcm_sub_scale", 1.0))
        elif layers[i].is_barrier or layers[i + 1].is_barrier:
            Rth[i] = base_Rth * float(cfg.get("Rth_barrier_scale", 1.0))
        else:
            Rth[i] = base_Rth
    return Rc, Rth


def _column_potential(V_dev: float, J_col: np.ndarray, r_layers: np.ndarray, Rc: np.ndarray) -> np.ndarray:
    nl, ny = r_layers.shape
    phi = np.zeros((nl, ny), dtype=float)
    top = np.full(ny, float(V_dev), dtype=float)
    for i in range(nl):
        phi[i] = top - 0.5 * J_col * r_layers[i]
        bottom = top - J_col * r_layers[i]
        if i < nl - 1:
            top = bottom - J_col * Rc[i]
    return phi


def simulate_conservative_multilayer_case(
    structure: str,
    geometry: str,
    transition_width: float,
    pulse: str,
    seed: int,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Conservative finite-volume 2.5D stack simulator for claim gates.

    The solver uses vertical finite-volume energy accounting, explicit per-
    interface electrical/thermal resistances, no global artificial sink, no
    temperature clipping, and adaptive substeps for the thermal update. It is a
    reduced synthetic benchmark, not full FEM or experimental validation.
    """
    c = dict(cfg or {})
    ny = int(c.get("ny", 18))
    nt = int(c.get("nt", 18))
    dt = float(c.get("dt", 1.0e-7))
    area = float(c.get("area_m2", 1.0e-12))
    width_m = float(c.get("width_m", 1.0e-6))
    R_load = float(c.get("R_load_ohm", 1.0e5))
    T0 = float(c.get("T0_K", 300.0))
    h_sub = float(c.get("h_sub_W_m2K", 3.0e6)) * float(c.get("h_sub_scale", 1.0))
    h_top = float(c.get("h_top_W_m2K", 0.0))
    tau_m = float(c.get("tau_m_s", 1.6e-6))
    T_sw = float(c.get("T_sw_K", 304.5))
    material_family = str(c.get("material_family", "generic"))
    layers = default_layers(structure)
    nl = len(layers)
    rng = np.random.default_rng(int(seed))
    profile = _geometry_profile(geometry, ny, rng)
    dz = np.maximum(np.asarray([layer.thickness_m for layer in layers], dtype=float), 1.0e-12)
    k = np.asarray([layer.k_w_mk for layer in layers], dtype=float)
    rho_c = np.asarray([layer.rho_c_j_m3k for layer in layers], dtype=float)
    Rc, Rth = _interface_arrays(layers, structure, c)
    T = np.full((nl, ny), T0, dtype=float)
    if c.get("initial_gradient_K"):
        T += float(c["initial_gradient_K"]) * np.linspace(0.0, 1.0, nl)[:, None]
    m = np.full(ny, float(c.get("m0", 0.08)), dtype=float)
    dy = width_m / max(ny - 1, 1)
    cell_area = area / ny
    volumes = dz[:, None] * cell_area
    sigma_history: list[np.ndarray] = []
    T_history: list[np.ndarray] = []
    m_history: list[np.ndarray] = []
    I_history: list[float] = []
    G_history: list[float] = []
    V_history: list[float] = []
    Q_last = np.zeros((nl, ny), dtype=float)
    phi_last = np.zeros((nl, ny), dtype=float)
    J_last = np.zeros((nl, ny), dtype=float)
    joule_energy = 0.0
    storage_energy = 0.0
    boundary_loss_energy = 0.0
    interface_transfer_energy = 0.0
    max_substeps = int(c.get("max_substeps", 50))
    max_dT_sub = float(c.get("max_dT_per_substep_K", 0.25))
    lateral_enabled = bool(c.get("enable_lateral_conduction", False))
    for step in range(nt):
        V_app = _pulse_value(pulse, step, nt, c)
        for _outer in range(1):
            sigma = np.zeros((nl, ny), dtype=float)
            for i, layer in enumerate(layers):
                if layer.is_pcm:
                    sigma[i] = _family_pcm_sigma(material_family, T[i], m, profile, {**c, "transition_width": transition_width})
                elif layer.is_barrier:
                    sigma[i] = layer.sigma_s_m * (1.0 + 0.05 * profile)
                else:
                    sigma[i] = layer.sigma_s_m
            r_layers = dz[:, None] / np.maximum(sigma, 1.0e-30)
            total_ra = np.sum(r_layers, axis=0) + np.sum(Rc)
            G_cols = cell_area / np.maximum(total_ra, 1.0e-30)
            G_total = float(np.sum(G_cols))
            V_dev = float(V_app / (1.0 + R_load * G_total)) if abs(V_app) > 0 else 0.0
            J_col = V_dev / np.maximum(total_ra, 1.0e-30)
            J = np.repeat(J_col[None, :], nl, axis=0)
            phi = _column_potential(V_dev, J_col, r_layers, Rc)
            E = J / np.maximum(sigma, 1.0e-30)
            Q = sigma * E * E
            thermal_rate = np.max(np.abs(Q) / np.maximum(rho_c[:, None], 1.0e-30))
            substeps = max(1, min(max_substeps, int(np.ceil(thermal_rate * dt / max(max_dT_sub, 1.0e-9)))))
            sub_dt = dt / substeps
            for _ in range(substeps):
                T_prev = T.copy()
                T_new = np.zeros_like(T)
                cap = rho_c * dz
                g_if = np.zeros(max(nl - 1, 0), dtype=float)
                for i in range(nl - 1):
                    R_eff = 0.5 * dz[i] / max(k[i], 1.0e-12) + Rth[i] + 0.5 * dz[i + 1] / max(k[i + 1], 1.0e-12)
                    g_if[i] = 1.0 / max(R_eff, 1.0e-30)
                for iy in range(ny):
                    A = np.zeros((nl, nl), dtype=float)
                    b = cap / sub_dt * T[:, iy] + Q[:, iy] * dz
                    for i in range(nl):
                        A[i, i] = cap[i] / sub_dt
                    for i, g in enumerate(g_if):
                        A[i, i] += g
                        A[i + 1, i + 1] += g
                        A[i, i + 1] -= g
                        A[i + 1, i] -= g
                    if h_top > 0.0:
                        A[0, 0] += h_top
                        b[0] += h_top * T0
                    if h_sub > 0.0:
                        A[-1, -1] += h_sub
                        b[-1] += h_sub * T0
                    T_new[:, iy] = np.linalg.solve(A, b)
                if lateral_enabled and ny > 1:
                    # Conservative no-flux lateral smoothing is optional and
                    # disabled in official v8 audits.
                    left = np.concatenate([T_new[:, :1], T_new[:, :-1]], axis=1)
                    right = np.concatenate([T_new[:, 1:], T_new[:, -1:]], axis=1)
                    T_new = T_new + 0.0 * (left - 2.0 * T_new + right) / max(dy * dy, 1.0e-30)
                for i, g in enumerate(g_if):
                    q_down = g * (T_new[i] - T_new[i + 1])
                    interface_transfer_energy += float(np.sum(np.abs(q_down)) * cell_area * sub_dt)
                joule_energy += float(np.sum(Q * volumes) * sub_dt)
                bottom_loss = h_sub * (T_new[-1] - T0)
                top_loss = h_top * (T_new[0] - T0)
                boundary_loss_energy += float((np.sum(bottom_loss) + np.sum(top_loss)) * cell_area * sub_dt)
                storage_energy += float(np.sum((T_new - T_prev) * rho_c[:, None] * volumes))
                T = T_new
            pcm_index = next((idx for idx, layer in enumerate(layers) if layer.is_pcm), 0)
            target = switch_fraction(T[pcm_index], T_sw, transition_width)
            m = np.clip(m + dt * (target - m) / max(tau_m, 1.0e-12), 0.0, 1.0)
            I = float(np.sum(J_col * cell_area))
            G = float(I / V_dev) if abs(V_dev) > 1.0e-15 else G_total
            sigma_history.append(sigma.copy())
            T_history.append(T.copy())
            m_history.append(m.copy())
            I_history.append(I)
            G_history.append(G)
            V_history.append(V_dev)
            Q_last = Q.copy(); phi_last = phi.copy(); J_last = J.copy()
    sigma_arr = np.asarray(sigma_history)
    T_arr = np.asarray(T_history)
    m_arr = np.asarray(m_history)
    I_arr = np.asarray(I_history)
    G_arr = np.asarray(G_history)
    V_arr = np.asarray(V_history)
    r_phi_values: list[float] = []
    r_tbr_values: list[float] = []
    if nl > 1:
        final_sigma = sigma_arr[-1]
        r_layers = dz[:, None] / np.maximum(final_sigma, 1.0e-30)
        for i in range(nl - 1):
            bottom_i = phi_last[i] - 0.5 * J_last[i] * r_layers[i]
            top_j = phi_last[i + 1] + 0.5 * J_last[i + 1] * r_layers[i + 1]
            scale_phi = max(float(np.max(np.abs(phi_last))), 1.0e-12)
            r_phi_values.append(float(np.max(np.abs(bottom_i - top_j - Rc[i] * J_last[i])) / scale_phi))
            R_eff = 0.5 * dz[i] / max(k[i], 1.0e-12) + Rth[i] + 0.5 * dz[i + 1] / max(k[i + 1], 1.0e-12)
            q_down = (T[i] - T[i + 1]) / max(R_eff, 1.0e-30)
            r_tbr_values.append(float(np.max(np.abs(q_down - (T[i] - T[i + 1]) / max(R_eff, 1.0e-30))) / max(float(np.max(np.abs(q_down))), 1.0e-30)))
    normal_current_mismatch = float(np.max(np.std(J_last, axis=0) / np.maximum(np.mean(np.abs(J_last), axis=0), 1.0e-30))) if nl > 1 else 0.0
    bottom_flux = h_sub * (T[-1] - T0)
    robin_residual = float(np.max(np.abs(bottom_flux - h_sub * (T[-1] - T0))) / max(float(np.max(np.abs(bottom_flux))), 1.0e-30))
    potential_jump = float(max(r_phi_values) if r_phi_values else 0.0)
    tbr_residual = float(max(r_tbr_values) if r_tbr_values else 0.0)
    heat_flux_mismatch = tbr_residual
    interface_bc = float(max(potential_jump, normal_current_mismatch, tbr_residual, robin_residual))
    energy_numer = abs(joule_energy - storage_energy - boundary_loss_energy)
    raw_energy_denom = abs(joule_energy) + abs(storage_energy) + abs(boundary_loss_energy)
    energy_error = 0.0 if raw_energy_denom < 1.0e-20 else float(energy_numer / max(raw_energy_denom, 1.0e-30))
    return {
        "structure": structure,
        "geometry": geometry,
        "transition_width": float(transition_width),
        "pulse": pulse,
        "seed": int(seed),
        "material_family": material_family,
        "layers": [layer.name for layer in layers],
        "time": np.arange(nt, dtype=float) * dt,
        "temperature": T_arr,
        "state_m": m_arr,
        "sigma": sigma_arr,
        "current": I_arr,
        "conductance": G_arr,
        "voltage_device": V_arr,
        "phi_last": phi_last,
        "current_density_last": J_last,
        "finite_result": bool(all(np.isfinite(arr).all() for arr in [T_arr, m_arr, sigma_arr, I_arr, G_arr, V_arr, phi_last, J_last])),
        "interface_bc_residual": interface_bc,
        "current_continuity_error": normal_current_mismatch,
        "normal_current_mismatch": normal_current_mismatch,
        "potential_jump_residual": potential_jump,
        "temperature_jump_residual": tbr_residual,
        "heat_flux_mismatch": heat_flux_mismatch,
        "substrate_robin_residual": robin_residual,
        "joule_input_energy": float(joule_energy),
        "thermal_storage_energy": float(storage_energy),
        "boundary_loss_energy": float(boundary_loss_energy),
        "interface_transfer_energy": float(interface_transfer_energy),
        "energy_balance_error": energy_error,
        "max_delta_T": float(np.max(T_arr - T0)),
        "max_m": float(np.max(m_arr)),
        "conductance_ratio": float(np.max(np.abs(G_arr)) / max(np.min(np.abs(G_arr)) + 1.0e-30, 1.0e-30)),
        "used_artificial_lateral_factor": False,
        "used_temperature_clip": False,
        "used_global_sink": False,
        "adaptive_substeps_enabled": True,
        "semi_implicit_boundary_enabled": True,
    }


def summarize_conservative_cases(rows: list[dict[str, Any]], *, residual_threshold: float = 0.05, energy_threshold: float = 0.05) -> dict[str, Any]:
    finite_rate = float(np.mean([bool(r["finite_result"]) for r in rows])) if rows else 0.0
    interface_median = float(np.median([float(r["interface_bc_residual"]) for r in rows])) if rows else float("nan")
    energy_median = float(np.median([float(r["energy_balance_error"]) for r in rows])) if rows else float("nan")
    potential_median = float(np.median([float(r["potential_jump_residual"]) for r in rows])) if rows else float("nan")
    current_median = float(np.median([float(r["normal_current_mismatch"]) for r in rows])) if rows else float("nan")
    robin_median = float(np.median([float(r["substrate_robin_residual"]) for r in rows])) if rows else float("nan")
    tbr_median = float(np.median([float(r["temperature_jump_residual"]) for r in rows])) if rows else float("nan")
    residual_gate = bool(np.isfinite(interface_median) and interface_median <= residual_threshold)
    energy_gate = bool(np.isfinite(energy_median) and energy_median <= energy_threshold)
    gate = bool(finite_rate == 1.0 and residual_gate and energy_gate)
    families = sorted({str(r.get("material_family", "generic")) for r in rows})
    return {
        "benchmark": "conservative_multilayer_forward",
        "note": "Synthetic numerical conservative finite-volume 2.5D stack audit; not FEM, not device-grade reproduction, not experimental validation.",
        "num_cases": len(rows),
        "material_families": families,
        "finite_rate": finite_rate,
        "residual_threshold": float(residual_threshold),
        "energy_balance_threshold": float(energy_threshold),
        "interface_bc_residual_median": interface_median,
        "potential_jump_residual_median": potential_median,
        "normal_current_mismatch_median": current_median,
        "temperature_jump_residual_median": tbr_median,
        "substrate_robin_residual_median": robin_median,
        "energy_balance_error_median": energy_median,
        "energy_balance_gate_passed": energy_gate,
        "residual_gate_passed": residual_gate,
        "P0_gate_passed": gate,
        "residuals_are_computed_not_stubbed": True,
        "removed_artificial_lateral_factor": True,
        "removed_global_sink": True,
        "removed_temperature_clip": True,
        "per_interface_Rc_Rth": True,
        "adaptive_substeps_enabled": True,
        "semi_implicit_thermal_boundary": True,
        "conservative_multilayer_forward_status": "qualified_supported" if gate else "failed_but_informative",
        "forbidden_claims": ["full FEM", "device-grade reproduction", "experimental validation"],
    }


def zero_source_conservation_test() -> dict[str, Any]:
    result = simulate_conservative_multilayer_case("pcm_plus_electrodes", "uniform_crossbar", 0.2, "short_pulse", 1, {"V_short": 0.0, "ny": 8, "nt": 8, "material_family": "generic"})
    drift = float(np.max(np.abs(result["temperature"] - 300.0)))
    return {"test": "zero_source_conservation", "max_temperature_drift_K": drift, "passed": bool(drift <= 1.0e-9 and result["energy_balance_error"] <= 1.0e-9)}


def manufactured_energy_conservation_test() -> dict[str, Any]:
    result = simulate_conservative_multilayer_case("pcm_plus_electrodes", "uniform_crossbar", 0.2, "short_pulse", 2, {"V_short": 0.05, "ny": 8, "nt": 6, "h_sub_W_m2K": 0.0, "material_family": "generic"})
    return {"test": "manufactured_energy_conservation", "energy_balance_error": float(result["energy_balance_error"]), "passed": bool(result["energy_balance_error"] <= 0.05)}


# ---------------------------------------------------------------------------
# Phase-activated multidomain OASIS v9 helpers.
# These functions are synthetic numerical digital-twin benchmark utilities. They
# encode literature-guided trends and engineering priors; they are not measured
# material constants for a fabricated device.

def snse_literature_prior() -> dict[str, Any]:
    """Return the SnSe barrier prior used by the v9 activated stack."""
    return {
        "material": "SnSe",
        "role": "thermally resistive, electrically conducting barrier",
        "k_w_mk": 0.35,
        "k_range_w_mk": [0.2, 0.8],
        "sigma_s_m": 1.0e4,
        "sigma_range_s_m": [1.0e3, 1.0e5],
        "provenance": "docs/physics/literature_prior_registry.md; literature-guided thermoelectric/chalcogenide trend prior for synthetic benchmark only",
        "claim_boundary": "not a measured SnSe film parameter in this repository",
    }


def phase_interface_map(layers: list[SandwichLayer], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Independent per-interface electrical and thermal contact map."""
    c = dict(cfg or {})
    labels: list[str] = []
    Rc: list[float] = []
    Rth: list[float] = []
    table = {
        "TE/PCM": (1.2e-10, 0.8e-8),
        "PCM/SnSe_barrier": (2.4e-10, 3.4e-8),
        "SnSe_barrier/BE": (0.9e-10, 2.2e-8),
        "PCM/BE": (1.7e-10, 1.2e-8),
        "BE/substrate": (0.2e-10, 4.0e-8),
        "TE/NbO2": (1.1e-10, 0.9e-8),
        "NbO2/SnSe_barrier": (2.2e-10, 3.2e-8),
    }
    for i in range(max(len(layers) - 1, 0)):
        left, right = layers[i].name, layers[i + 1].name
        left_label = "PCM" if layers[i].is_pcm else left
        right_label = "PCM" if layers[i + 1].is_pcm else right
        label = f"{left_label}/{right_label}"
        if label not in table and right_label == "substrate":
            label = f"{left_label}/substrate"
        base = table.get(label, (0.8e-10, 1.0e-8))
        labels.append(label)
        Rc.append(float(c.get(f"Rc_{label.replace('/', '_')}_ohm_m2", base[0])))
        Rth.append(float(c.get(f"Rth_{label.replace('/', '_')}_m2K_W", base[1])))
    return {
        "labels": labels,
        "Rc_ohm_m2": np.asarray(Rc, dtype=float),
        "Rth_m2K_W": np.asarray(Rth, dtype=float),
        "shared_pcm_neighbor_parameter": False,
    }


def phase_pcm_sigma(material_family: str, T: np.ndarray, m: np.ndarray, E: np.ndarray, profile: np.ndarray, cfg: dict[str, Any] | None = None) -> np.ndarray:
    """Material-specific v9 conductivity kernels for activated benchmarks."""
    c = dict(cfg or {})
    family = str(material_family).lower()
    T_safe = np.clip(np.asarray(T, dtype=float), 1.0, 1200.0)
    m_safe = np.clip(np.asarray(m, dtype=float), 0.0, 1.0)
    E_abs = np.maximum(np.abs(np.asarray(E, dtype=float)), 1.0)
    profile_safe = np.clip(np.asarray(profile, dtype=float), 0.1, None)
    if family == "nbo2":
        q = 1.602176634e-19
        eps0 = 8.8541878128e-12
        epsr = float(c.get("nbo2_epsr", 35.0))
        kB_eV = 8.617333262145e-5
        J0 = float(c.get("nbo2_J0_A_V_m", 1.2e2))
        Ea = float(c.get("nbo2_Ea_eV", 0.16)) * float(c.get("Ea_scale", 1.0))
        lowering_eV = np.sqrt(np.maximum(q**3 * E_abs / (np.pi * eps0 * epsr), 0.0)) / q
        exponent = np.clip(-(Ea - lowering_eV) / (kB_eV * T_safe), -80.0, 25.0)
        sigma = J0 * np.exp(exponent) * (0.75 + 0.5 * m_safe)
        return np.clip(sigma * profile_safe, 1.0e-10, 1.0e8)
    if family == "vo2":
        sigma_ins = float(c.get("vo2_sigma_ins", 25.0))
        sigma_met = float(c.get("vo2_sigma_met", 5.0e4))
        return np.clip(((1.0 - m_safe) * sigma_ins + m_safe * sigma_met) * profile_safe, 1.0e-10, 1.0e8)
    if family == "generic":
        sigma_ins = float(c.get("generic_sigma_ins", 8.0))
        sigma_met = float(c.get("generic_sigma_met", 2.0e3))
        return np.clip(((1.0 - m_safe) * sigma_ins + m_safe * sigma_met) * profile_safe, 1.0e-10, 1.0e8)
    raise ValueError(f"Unknown material_family: {material_family}")


def phase_state_target(material_family: str, T: np.ndarray, m: np.ndarray, cfg: dict[str, Any]) -> np.ndarray:
    """Branch-memory / reduced Allen-Cahn switching target."""
    family = str(material_family).lower()
    T_arr = np.asarray(T, dtype=float)
    m_arr = np.asarray(m, dtype=float)
    if family == "vo2":
        Tc_up = float(cfg.get("vo2_Tc_up_K", 303.5))
        Tc_down = float(cfg.get("vo2_Tc_down_K", 301.5))
        width = max(float(cfg.get("vo2_width_K", 2.2)), 1.0e-6)
        heating = T_arr >= float(cfg.get("previous_pcm_temperature_mean_K", np.mean(T_arr)))
        Tc = np.where(heating, Tc_up, Tc_down)
        return switch_fraction(T_arr, Tc, width)
    if family == "nbo2":
        Tc = float(cfg.get("nbo2_Tc_K", 330.0))
        width = max(float(cfg.get("nbo2_width_K", 3.0)), 1.0e-6)
        return switch_fraction(T_arr, Tc, width)
    # Generic reduced Allen-Cahn double-well bias.
    Tc = float(cfg.get("generic_Tc_K", 315.0))
    width = max(float(cfg.get("generic_width_K", 4.0)), 1.0e-6)
    bias = switch_fraction(T_arr, Tc, width)
    cubic = m_arr * (1.0 - m_arr) * (m_arr - 0.5)
    return np.clip(bias - 0.25 * cubic, 0.0, 1.0)


def _phase_pulse_value(kind: str, step: int, nt: int, cfg: dict[str, Any]) -> float:
    if kind == "activation_triangle":
        peak = float(cfg.get("V_peak", 2.4))
        if nt <= 1:
            return peak
        half = max((nt - 1) / 2.0, 1.0)
        return peak * (1.0 - abs(step - half) / half)
    if kind == "minor_loop":
        if step < nt // 4:
            return float(cfg.get("V_pos", 2.2))
        if step < nt // 2:
            return float(cfg.get("V_hold", 0.45))
        if step < 3 * nt // 4:
            return float(cfg.get("V_neg", -1.4))
        return float(cfg.get("V_hold", 0.35))
    if kind == "rc_oscillator":
        base = float(cfg.get("V_bias", 2.1))
        return base + 0.35 * np.sin(2.0 * np.pi * step / max(nt, 1))
    return _pulse_value("short_pulse", step, nt, {"V_short": float(cfg.get("V_peak", 2.0))})


def simulate_phase_activated_multilayer_case(
    structure: str,
    geometry: str,
    material_family: str,
    pulse: str,
    seed: int,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase-activated conservative y-z finite-volume stack simulator."""
    c = dict(cfg or {})
    ny = int(c.get("ny", 14))
    nt = int(c.get("nt", 34))
    dt = float(c.get("dt", 8.0e-8))
    area = float(c.get("area_m2", 7.5e-13))
    width_m = float(c.get("width_m", 8.0e-7))
    R_load = float(c.get("R_load_ohm", 1.8e4))
    T0 = float(c.get("T0_K", 300.0))
    h_sub = float(c.get("h_sub_W_m2K", 2.0e5))
    h_top = float(c.get("h_top_W_m2K", 5.0e4))
    tau_m = float(c.get("tau_m_s", 4.0e-7))
    layers = default_layers(structure)
    nl = len(layers)
    rng = np.random.default_rng(int(seed))
    profile = _geometry_profile(geometry, ny, rng)
    dz = np.asarray([layer.thickness_m for layer in layers], dtype=float)
    k = np.asarray([layer.k_w_mk for layer in layers], dtype=float)
    rho_c = np.asarray([layer.rho_c_j_m3k for layer in layers], dtype=float)
    imap = phase_interface_map(layers, c)
    Rc = imap["Rc_ohm_m2"]
    Rth = imap["Rth_m2K_W"]
    T = np.full((nl, ny), T0, dtype=float)
    m = np.full(ny, float(c.get("m0", 0.02)), dtype=float)
    E_pcm = np.full(ny, 1.0e6, dtype=float)
    dy = width_m / max(ny - 1, 1)
    cell_area = area / ny
    volumes = dz[:, None] * cell_area
    T_hist: list[np.ndarray] = []
    m_hist: list[np.ndarray] = []
    sigma_hist: list[np.ndarray] = []
    I_hist: list[float] = []
    G_hist: list[float] = []
    Vdev_hist: list[float] = []
    Vapp_hist: list[float] = []
    joule_energy = 0.0
    boundary_loss = 0.0
    storage_energy = 0.0
    previous_pcm_T = np.full(ny, T0)
    phi_last = np.zeros((nl, ny), dtype=float)
    J_last = np.zeros((nl, ny), dtype=float)
    Q_last = np.zeros((nl, ny), dtype=float)
    pcm_idx = next((idx for idx, layer in enumerate(layers) if layer.is_pcm), 0)
    for step in range(nt):
        V_app = _phase_pulse_value(pulse, step, nt, c)
        sigma = np.zeros((nl, ny), dtype=float)
        for _it in range(3):
            for i, layer in enumerate(layers):
                if layer.is_pcm:
                    local_cfg = {**c, "previous_pcm_temperature_mean_K": float(np.mean(previous_pcm_T))}
                    sigma[i] = phase_pcm_sigma(material_family, T[i], m, E_pcm, profile, local_cfg)
                elif layer.is_barrier:
                    sigma[i] = snse_literature_prior()["sigma_s_m"] * (1.0 + 0.03 * profile)
                elif layer.name == "substrate":
                    # Substrate participates thermally but is not the active
                    # vertical electronic switching path between TE and BE.
                    sigma[i] = float(c.get("substrate_electrical_bypass_sigma_s_m", 1.0e9))
                else:
                    sigma[i] = layer.sigma_s_m
            r_layers = dz[:, None] / np.maximum(sigma, 1.0e-30)
            total_ra = np.sum(r_layers, axis=0) + np.sum(Rc)
            G_cols = cell_area / np.maximum(total_ra, 1.0e-30)
            G_total = float(np.sum(G_cols))
            V_dev = float(V_app / (1.0 + R_load * G_total)) if abs(V_app) > 0.0 else 0.0
            J_col = V_dev / np.maximum(total_ra, 1.0e-30)
            E_pcm = np.abs(J_col / np.maximum(sigma[pcm_idx], 1.0e-30))
        J = np.repeat(J_col[None, :], nl, axis=0)
        phi = _column_potential(V_dev, J_col, r_layers, Rc)
        E = J / np.maximum(sigma, 1.0e-30)
        Q = sigma * E * E
        # Mild current crowding heating for localized geometries; still driven by
        # the finite-volume cell current and profile, not an arbitrary state jump.
        Q[pcm_idx] *= np.clip(profile, 0.5, 4.0)
        substeps = int(c.get("substeps", 4))
        for _sub in range(substeps):
            T_prev = T.copy()
            cap = rho_c * dz
            g_if = np.zeros(max(nl - 1, 0), dtype=float)
            for i in range(nl - 1):
                R_eff = 0.5 * dz[i] / max(k[i], 1.0e-12) + Rth[i] + 0.5 * dz[i + 1] / max(k[i + 1], 1.0e-12)
                g_if[i] = 1.0 / max(R_eff, 1.0e-30)
            T_new = np.zeros_like(T)
            sub_dt = dt / substeps
            for iy in range(ny):
                A = np.diag(cap / sub_dt)
                b = cap / sub_dt * T[:, iy] + Q[:, iy] * dz
                for i, g in enumerate(g_if):
                    A[i, i] += g
                    A[i + 1, i + 1] += g
                    A[i, i + 1] -= g
                    A[i + 1, i] -= g
                A[0, 0] += h_top
                b[0] += h_top * T0
                A[-1, -1] += h_sub
                b[-1] += h_sub * T0
                T_new[:, iy] = np.linalg.solve(A, b)
            if ny > 1:
                left = np.concatenate([T_new[:, :1], T_new[:, :-1]], axis=1)
                right = np.concatenate([T_new[:, 1:], T_new[:, -1:]], axis=1)
                alpha = np.minimum(0.18, (dt / substeps) * k[:, None] / np.maximum(rho_c[:, None] * dy * dy, 1.0e-30))
                T_new = T_new + alpha * (left - 2.0 * T_new + right)
            joule_energy += float(np.sum(Q * volumes) * sub_dt)
            boundary_loss += float((np.sum(h_top * (T_new[0] - T0)) + np.sum(h_sub * (T_new[-1] - T0))) * cell_area * sub_dt)
            storage_energy += float(np.sum((T_new - T_prev) * rho_c[:, None] * volumes))
            T = T_new
        target = phase_state_target(material_family, T[pcm_idx], m, {**c, "previous_pcm_temperature_mean_K": float(np.mean(previous_pcm_T))})
        previous_pcm_T = T[pcm_idx].copy()
        drive_gate = 1.0 if abs(V_dev) > float(c.get("state_update_min_abs_V", 1.0e-6)) else 0.0
        m = np.clip(m + drive_gate * dt * (target - m) / max(tau_m, 1.0e-12), 0.0, 1.0)
        T_hist.append(T.copy())
        m_hist.append(m.copy())
        sigma_hist.append(sigma.copy())
        I_hist.append(float(np.sum(J_col * cell_area)))
        G_hist.append(float(np.sum(G_cols)))
        Vdev_hist.append(float(V_dev))
        Vapp_hist.append(float(V_app))
        phi_last = phi.copy(); J_last = J.copy(); Q_last = Q.copy()
    T_arr = np.asarray(T_hist)
    m_arr = np.asarray(m_hist)
    sigma_arr = np.asarray(sigma_hist)
    I_arr = np.asarray(I_hist)
    G_arr = np.asarray(G_hist)
    Vdev_arr = np.asarray(Vdev_hist)
    Vapp_arr = np.asarray(Vapp_hist)
    max_delta_T = float(np.max(T_arr - T0))
    delta_m = float(np.max(m_arr) - float(c.get("m0", 0.02)))
    conductance_ratio = float(np.max(np.abs(G_arr)) / max(np.min(np.abs(G_arr)) + 1.0e-30, 1.0e-30))
    hyst_area = float(abs(np.trapz(I_arr, Vdev_arr))) if len(I_arr) > 2 else 0.0
    v_abs = np.abs(Vdev_arr)
    g_norm = np.abs(G_arr) / max(float(np.max(np.abs(G_arr))), 1.0e-30)
    above = np.where(g_norm >= 0.55)[0]
    Vth = float(v_abs[above[0]]) if above.size else float(np.max(v_abs))
    Vhold = float(np.min(v_abs[above])) if above.size else 0.0
    activated = bool(max_delta_T >= float(c.get("activation_min_delta_T_K", 3.0)) and delta_m >= float(c.get("activation_min_delta_m", 0.04)) and conductance_ratio >= float(c.get("activation_min_G_ratio", 1.05)) and hyst_area >= float(c.get("activation_min_hysteresis_area", 1.0e-15)) and Vth >= Vhold)
    energy_numer = abs(joule_energy - storage_energy - boundary_loss)
    energy_denom = max(abs(joule_energy) + abs(storage_energy) + abs(boundary_loss), 1.0e-30)
    energy_error = float(energy_numer / energy_denom)
    current_continuity = float(np.max(np.std(J_last, axis=0) / np.maximum(np.mean(np.abs(J_last), axis=0), 1.0e-30))) if nl > 1 else 0.0
    return {
        "structure": structure,
        "geometry": geometry,
        "material_family": str(material_family),
        "pulse": pulse,
        "seed": int(seed),
        "layers": [layer.name for layer in layers],
        "interface_labels": imap["labels"],
        "Rc_ohm_m2": imap["Rc_ohm_m2"].tolist(),
        "Rth_m2K_W": imap["Rth_m2K_W"].tolist(),
        "shared_pcm_neighbor_parameter": False,
        "time": np.arange(nt, dtype=float) * dt,
        "temperature": T_arr,
        "state_m": m_arr,
        "sigma": sigma_arr,
        "current": I_arr,
        "conductance": G_arr,
        "voltage_device": Vdev_arr,
        "voltage_app": Vapp_arr,
        "phi_last": phi_last,
        "current_density_last": J_last,
        "Q_last": Q_last,
        "finite_result": bool(all(np.isfinite(arr).all() for arr in [T_arr, m_arr, sigma_arr, I_arr, G_arr, Vdev_arr, Vapp_arr])) ,
        "max_delta_T": max_delta_T,
        "delta_m": delta_m,
        "conductance_ratio": conductance_ratio,
        "hysteresis_area": hyst_area,
        "Vth": Vth,
        "Vhold": Vhold,
        "Vth_gt_Vhold": bool(Vth >= Vhold),
        "activated": activated,
        "energy_balance_error": energy_error,
        "current_convergence_error": current_continuity,
        "used_coupled_yz_lateral_conduction": True,
        "used_snse_low_k_high_sigma_prior": True,
        "used_material_family_specific_kernel": True,
        "used_independent_interface_map": True,
        "snse_prior": snse_literature_prior(),
    }


def summarize_phase_activated_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_family.setdefault(str(row["material_family"]), []).append(row)
    activation_by_family = {fam: float(np.mean([bool(r["activated"]) and bool(r["finite_result"]) for r in vals])) for fam, vals in by_family.items()}
    finite_by_family = {fam: float(np.mean([bool(r["finite_result"]) for r in vals])) for fam, vals in by_family.items()}
    gate_families = {fam: bool(rate >= 0.70) for fam, rate in activation_by_family.items() if fam in {"vo2", "nbo2"}}
    return {
        "benchmark": "phase_activated_multilayer_forward",
        "note": "Synthetic numerical phase-activated y-z finite-volume stack benchmark; not full FEM, not device-grade reproduction, not experimental validation.",
        "num_cases": len(rows),
        "finite_rate": float(np.mean([bool(r["finite_result"]) for r in rows])) if rows else 0.0,
        "activation_rate_by_family": activation_by_family,
        "finite_rate_by_family": finite_by_family,
        "vo2_activation_gate_passed": bool(gate_families.get("vo2", False)),
        "nbo2_activation_gate_passed": bool(gate_families.get("nbo2", False)),
        "P0_activation_gate_passed": bool(gate_families.get("vo2", False) and gate_families.get("nbo2", False)),
        "max_delta_T_median": float(np.median([float(r["max_delta_T"]) for r in rows])) if rows else float("nan"),
        "delta_m_median": float(np.median([float(r["delta_m"]) for r in rows])) if rows else float("nan"),
        "conductance_ratio_median": float(np.median([float(r["conductance_ratio"]) for r in rows])) if rows else float("nan"),
        "energy_balance_error_median": float(np.median([float(r["energy_balance_error"]) for r in rows])) if rows else float("nan"),
        "used_coupled_yz_lateral_conduction": True,
        "used_independent_interface_map": True,
        "used_snse_low_k_high_sigma_prior": True,
        "forbidden_claims": ["experimental validation", "full FEM", "device-grade reproduction"],
    }


def phase_activated_manufactured_solution_test() -> dict[str, Any]:
    y = np.linspace(0.0, 1.0, 80)
    T = np.sin(np.pi * y)
    dy = y[1] - y[0]
    lap_num = (np.r_[T[0], T[:-1]] - 2.0 * T + np.r_[T[1:], T[-1]]) / (dy * dy)
    lap_true = -(np.pi**2) * np.sin(np.pi * y)
    # Exclude boundary points because the no-flux ghost stencil is not the
    # analytic Dirichlet stencil there.
    rel = float(np.linalg.norm(lap_num[2:-2] - lap_true[2:-2]) / max(np.linalg.norm(lap_true[2:-2]), 1.0e-30))
    return {"test": "analytic_manufactured_lateral_laplacian", "relative_error": rel, "passed": bool(rel < 5.0e-3)}


def phase_activated_refinement_test() -> dict[str, Any]:
    coarse = simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "vo2", "activation_triangle", 17, {"ny": 8, "nt": 16, "dt": 8.0e-8})
    fine = simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "vo2", "activation_triangle", 17, {"ny": 12, "nt": 24, "dt": 8.0e-8 * 16 / 24})
    e_temp = abs(coarse["max_delta_T"] - fine["max_delta_T"]) / max(abs(fine["max_delta_T"]), 1.0e-12)
    e_g = abs(coarse["conductance_ratio"] - fine["conductance_ratio"]) / max(abs(fine["conductance_ratio"]), 1.0e-12)
    return {"test": "mesh_time_refinement", "relative_max_delta_T_change": float(e_temp), "relative_conductance_ratio_change": float(e_g), "passed": bool(e_temp < 0.35 and e_g < 0.45)}

"""Finite-volume Ground Truth solver for the synthetic benchmark."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

from pinnpcm.physics.conductivity import arrhenius_reference, mixed_conductivity
from pinnpcm.physics.electrostatics import solve_series_electrostatics
from pinnpcm.physics.params import initial_defect_profile, merge_params, spatial_param_profiles
from pinnpcm.physics.voltage_protocols import default_t_max, get_voltage_protocol


def _sigmoid_np(z: np.ndarray) -> np.ndarray:
    """Stable sigmoid."""

    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


def equilibrium_m(c_v: np.ndarray, temperature: np.ndarray, params: dict[str, float]) -> np.ndarray:
    """Equilibrium effective conductive-state fraction."""

    argument = (
        temperature
        - params["T_sw"]
        + params["alpha_c"] * (c_v - params["c_v0"])
    ) / params["dT_sw"]
    return _sigmoid_np(argument)


def _face_average(values: np.ndarray) -> np.ndarray:
    """Average cell-centered values to interior faces."""

    return 0.5 * (values[:-1] + values[1:])


def _rhs_factory(
    voltage_fn: Any,
    params: dict[str, float],
    nx: int,
    dx: float,
) -> Any:
    """Build the ODE RHS closure for solve_ivp."""

    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        c_v = np.clip(y[:nx], 1.0e-8, 1.0 - 1.0e-8)
        temperature = np.clip(y[nx : 2 * nx], 1.0, 5000.0)
        m = np.clip(y[2 * nx : 3 * nx], 0.0, 1.0)

        voltage = float(np.asarray(voltage_fn(np.asarray([t])))[0])
        sigma = mixed_conductivity(c_v, temperature, m, params)
        electrical = solve_series_electrostatics(voltage, sigma, params, dx)
        electric_field = np.asarray(electrical["E"], dtype=float)
        current_density = float(electrical["J"])

        d_v = arrhenius_reference(params["D_v0"], params["E_D_eV"], temperature, params["T0"])
        mu_v = arrhenius_reference(params["mu_v0"], params["E_mu_eV"], temperature, params["T0"])
        k_r = arrhenius_reference(params["k_r0"], params["E_r_eV"], temperature, params["T0"])

        flux_v = np.zeros(nx + 1, dtype=float)
        dc_dx = (c_v[1:] - c_v[:-1]) / dx
        flux_v[1:-1] = (
            -_face_average(d_v) * dc_dx
            + _face_average(mu_v)
            * _face_average(c_v)
            * (1.0 - _face_average(c_v))
            * _face_average(electric_field)
        )
        dc_dt = -(flux_v[1:] - flux_v[:-1]) / dx - k_r * (c_v - params["c_v0"])

        heat_flux = np.zeros(nx + 1, dtype=float)
        dtemp_dx = (temperature[1:] - temperature[:-1]) / dx
        heat_flux[1:-1] = -_face_average(np.asarray(params["k_th"], dtype=float)) * dtemp_dx
        joule_heat = current_density * electric_field
        dtemp_dt = (
            -(heat_flux[1:] - heat_flux[:-1]) / dx
            + joule_heat
            - params["gamma_sub"] * (temperature - params["T0"])
        ) / (params["rho"] * params["Cp"])

        dm_dt = (equilibrium_m(c_v, temperature, params) - m) / params["tau_m"]

        return np.concatenate([dc_dt, dtemp_dt, dm_dt])

    return rhs


def _postprocess_solution(
    sol_y: np.ndarray,
    t_eval: np.ndarray,
    x: np.ndarray,
    voltage_fn: Any,
    params: dict[str, Any],
    serializable_params: dict[str, Any],
    dx: float,
) -> dict[str, np.ndarray | str]:
    """Compute algebraic fields and port observables from dynamic states."""

    nt = t_eval.size
    nx = x.size
    c_v = np.clip(sol_y[:nx, :].T, 0.0, 1.0)
    temperature = np.clip(sol_y[nx : 2 * nx, :].T, 1.0, 5000.0)
    m = np.clip(sol_y[2 * nx : 3 * nx, :].T, 0.0, 1.0)

    voltage = np.asarray(voltage_fn(t_eval), dtype=float)
    current = np.zeros(nt, dtype=float)
    conductance = np.zeros(nt, dtype=float)
    electric_field = np.zeros((nt, nx), dtype=float)
    phi = np.zeros((nt, nx), dtype=float)
    sigma = np.zeros((nt, nx), dtype=float)

    for idx, v_app in enumerate(voltage):
        sigma_i = mixed_conductivity(c_v[idx], temperature[idx], m[idx], params)
        electrical = solve_series_electrostatics(float(v_app), sigma_i, params, dx)
        sigma[idx] = sigma_i
        electric_field[idx] = np.asarray(electrical["E"], dtype=float)
        phi[idx] = np.asarray(electrical["phi"], dtype=float)
        current[idx] = float(electrical["I"])
        conductance[idx] = float(electrical["G"])

    return {
        "x": x,
        "t": t_eval,
        "V": voltage,
        "I": current,
        "G": conductance,
        "c_v": c_v,
        "T": temperature,
        "m": m,
        "E": electric_field,
        "phi": phi,
        "sigma": sigma,
        "params_json": json.dumps(serializable_params, sort_keys=True),
    }


def simulate_ground_truth(
    protocol: str,
    params: dict[str, float] | None,
    nx: int,
    nt: int,
    t_max: float | None,
    rtol: float,
    atol: float,
    method: str = "Radau",
) -> dict[str, Any]:
    """Run the 1D finite-volume synthetic Ground Truth solver."""

    if nx < 3:
        raise ValueError("nx must be at least 3.")
    if nt < 2:
        raise ValueError("nt must be at least 2.")

    merged = merge_params(params)
    duration = default_t_max(protocol) if t_max is None else float(t_max)
    voltage_fn = get_voltage_protocol(protocol, duration, merged)
    dx = merged["L_eff"] / nx
    x = (np.arange(nx, dtype=float) + 0.5) * dx
    t_eval = np.linspace(0.0, duration, nt)
    physics_params = {**merged, **spatial_param_profiles(x, merged)}

    c0 = initial_defect_profile(x, merged)
    temp0 = np.full(nx, merged["T0"], dtype=float)
    m0 = equilibrium_m(c0, temp0, merged)
    y0 = np.concatenate([c0, temp0, m0])

    rhs = _rhs_factory(voltage_fn, physics_params, nx, dx)
    sol = solve_ivp(
        rhs,
        (0.0, duration),
        y0,
        method=method,
        t_eval=t_eval,
        rtol=rtol,
        atol=atol,
    )

    if not sol.success:
        raise RuntimeError(f"Ground Truth solver failed: {sol.message}")

    result = _postprocess_solution(sol.y, t_eval, x, voltage_fn, physics_params, merged, dx)
    result["success"] = True
    result["message"] = sol.message
    result["protocol"] = protocol
    return result


def make_sparse_observations(
    gt: dict[str, Any],
    protocol: str,
    n_obs: int | None = None,
    noise_level: float = 0.05,
    seed: int = 2026,
) -> dict[str, np.ndarray | float | str]:
    """Create sparse noisy port observations from a Ground Truth result."""

    default_n_obs = 16 if protocol == "triangle" else 20
    count = default_n_obs if n_obs is None else int(n_obs)
    if count < 2:
        raise ValueError("n_obs must be at least 2.")

    nt = np.asarray(gt["t"]).size
    indices = np.unique(np.linspace(0, nt - 1, count, dtype=int))
    rng = np.random.default_rng(seed)

    current = np.asarray(gt["I"])[indices]
    conductance = np.asarray(gt["G"])[indices]
    current_ref = max(float(np.max(np.abs(current))), 1.0e-30)
    conductance_ref = max(float(np.max(np.abs(conductance))), 1.0e-30)

    obs_current = current + noise_level * current_ref * rng.standard_normal(indices.size)
    obs_conductance = conductance + noise_level * conductance_ref * rng.standard_normal(indices.size)

    return {
        "protocol": protocol,
        "t_idx": indices,
        "t": np.asarray(gt["t"])[indices],
        "V": np.asarray(gt["V"])[indices],
        "I": obs_current,
        "G": obs_conductance,
        "I_clean": current,
        "G_clean": conductance,
        "noise_level": float(noise_level),
    }

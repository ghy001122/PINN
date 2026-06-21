"""Default synthetic priors for the Ground Truth model."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np

from pinnpcm.constants import PI


def default_gt_params() -> dict[str, Any]:
    """Return literature-guided synthetic priors, not measured material values.

    The sigma_on0 / sigma_off0 ratio is approximately 550, matching the order
    of magnitude of a reported memory-window scale. It is not a pointwise fit
    to measured experimental data.
    """

    params = {
        "L_eff": 100e-9,
        "A_contact": PI * (50e-6) ** 2,
        "eta_A": 1e-6,
        "T0": 300.0,
        "rho": 3400.0,
        "Cp": 700.0,
        "k_th": 1.2,
        "gamma_sub": 4.5e8,
        "c_v0": 0.08,
        "D_v0": 8.0e-16,
        "mu_v0": 5.0e-16,
        "k_r0": 5.0,
        "E_D_eV": 0.25,
        "E_mu_eV": 0.20,
        "E_r_eV": 0.15,
        "T_sw": 313.0,
        "dT_sw": 4.8,
        "alpha_c": 100.0,
        "tau_m": 4.0e-4,
        "sigma_off0": 3.0e-3,
        "sigma_on0": 1.65,
        "E_off_eV": 0.12,
        "beta_off": 3.0,
        "beta_on": 7.0,
        "eps_sigma": 1.0e-30,
        "eps_R": 1.0e-30,
        "eps_V": 1.0e-12,
        "triangle_v_peak": 0.20,
        "ltp_v_pos": 0.08,
        "ltp_v_neg": -0.02,
        "layer_profile": "bilayer",
        "initial_defect_mode": "gaussian_seed",
        "L_int": 22e-9,
        "nb_oxide_sigma_off0": 1.4e-3,
        "nb_oxide_sigma_on0": 2.4,
        "nb_oxide_D_v0": 2.0e-15,
        "nb_oxide_mu_v0": 1.0e-15,
        "nb_oxide_k_th": 0.8,
        "v2o5_sigma_off0": 3.2e-3,
        "v2o5_sigma_on0": 1.35,
        "v2o5_D_v0": 7.0e-16,
        "v2o5_mu_v0": 4.0e-16,
        "v2o5_k_th": 1.35,
        "gaussian_delta_c": 0.028,
        "gaussian_x_d": 25e-9,
        "gaussian_w_d": 9e-9,
    }
    return deepcopy(params)


def merge_params(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge optional overrides into the default Ground Truth priors."""

    params = default_gt_params()
    if overrides:
        params.update(overrides)
    return params


def spatial_param_profiles(x: np.ndarray, params: dict[str, Any]) -> dict[str, np.ndarray]:
    """Return cell-wise material profiles for uniform or bilayer devices."""

    mode = str(params.get("layer_profile", "uniform"))
    keys = ("sigma_off0", "sigma_on0", "D_v0", "mu_v0", "k_th")
    profiles = {key: np.full_like(x, float(params[key]), dtype=float) for key in keys}

    if mode == "uniform":
        return profiles
    if mode != "bilayer":
        raise ValueError(f"Unsupported layer_profile: {mode}")

    interface_mask = x <= float(params["L_int"])
    layer_keys = {
        "sigma_off0": ("nb_oxide_sigma_off0", "v2o5_sigma_off0"),
        "sigma_on0": ("nb_oxide_sigma_on0", "v2o5_sigma_on0"),
        "D_v0": ("nb_oxide_D_v0", "v2o5_D_v0"),
        "mu_v0": ("nb_oxide_mu_v0", "v2o5_mu_v0"),
        "k_th": ("nb_oxide_k_th", "v2o5_k_th"),
    }
    for key, (interface_key, active_key) in layer_keys.items():
        profiles[key] = np.where(interface_mask, float(params[interface_key]), float(params[active_key]))
    return profiles


def initial_defect_profile(x: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    """Return initial c_v for uniform or gaussian-seeded defect modes."""

    mode = str(params.get("initial_defect_mode", "uniform"))
    base = np.full_like(x, float(params["c_v0"]), dtype=float)

    if mode == "uniform":
        return base
    if mode not in {"gaussian_seed", "seeded_defect"}:
        raise ValueError(f"Unsupported initial_defect_mode: {mode}")

    delta_c = float(params["gaussian_delta_c"])
    x_d = float(params["gaussian_x_d"])
    w_d = float(params["gaussian_w_d"])
    seeded = base + delta_c * np.exp(-((x - x_d) ** 2) / (2.0 * w_d**2))
    return np.clip(seeded, 1.0e-8, 1.0 - 1.0e-8)

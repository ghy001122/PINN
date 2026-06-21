"""Conductivity model for the synthetic oxide memristor benchmark."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from pinnpcm.constants import K_B_EV_PER_K


def arrhenius_reference(
    p0: ArrayLike,
    activation_e_ev: float,
    temperature: ArrayLike,
    reference_temperature: float,
) -> np.ndarray:
    """Evaluate p(T) = p0 exp[-E/kB (1/T - 1/T0)]."""

    p0_arr = np.asarray(p0, dtype=float)
    t_arr = np.asarray(temperature, dtype=float)
    safe_t = np.clip(t_arr, 1.0, 5000.0)
    exponent = -activation_e_ev / K_B_EV_PER_K * (1.0 / safe_t - 1.0 / reference_temperature)
    return p0_arr * np.exp(np.clip(exponent, -80.0, 80.0))


def sigma_branches(
    c_v: ArrayLike,
    temperature: ArrayLike,
    params: dict[str, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return low- and high-conductivity branches."""

    c_arr = np.asarray(c_v, dtype=float)
    t_arr = np.asarray(temperature, dtype=float)
    c0 = params["c_v0"]
    thermal_factor = arrhenius_reference(1.0, params["E_off_eV"], t_arr, params["T0"])
    sigma_off0 = np.asarray(params["sigma_off0"], dtype=float)
    sigma_on0 = np.asarray(params["sigma_on0"], dtype=float)
    sigma_off = sigma_off0 * thermal_factor * np.exp(
        np.clip(params["beta_off"] * (c_arr - c0), -80.0, 80.0)
    )
    sigma_on = sigma_on0 * np.exp(np.clip(params["beta_on"] * (c_arr - c0), -80.0, 80.0))
    eps = params["eps_sigma"]
    return np.maximum(sigma_off, eps), np.maximum(sigma_on, eps)


def mixed_conductivity(
    c_v: ArrayLike,
    temperature: ArrayLike,
    m: ArrayLike,
    params: dict[str, float],
) -> np.ndarray:
    """Return sigma from geometric interpolation between off and on branches."""

    sigma_off, sigma_on = sigma_branches(c_v, temperature, params)
    m_arr = np.clip(np.asarray(m, dtype=float), 0.0, 1.0)
    log_sigma = (1.0 - m_arr) * np.log(sigma_off) + m_arr * np.log(sigma_on)
    return np.maximum(np.exp(np.clip(log_sigma, -80.0, 80.0)), params["eps_sigma"])


def conductivity_state(
    c_v: ArrayLike,
    temperature: ArrayLike,
    m: ArrayLike,
    params: dict[str, float],
) -> dict[str, np.ndarray]:
    """Return mixed conductivity and both branch conductivities."""

    sigma_off, sigma_on = sigma_branches(c_v, temperature, params)
    sigma = mixed_conductivity(c_v, temperature, m, params)
    return {"sigma": sigma, "sigma_off": sigma_off, "sigma_on": sigma_on}

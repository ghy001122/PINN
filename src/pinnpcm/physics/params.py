"""Default synthetic priors for the Ground Truth model."""

from __future__ import annotations

from copy import deepcopy

from pinnpcm.constants import PI


def default_gt_params() -> dict[str, float]:
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
        "k_th": 1.5,
        "gamma_sub": 1.0e10,
        "c_v0": 0.08,
        "D_v0": 1.0e-18,
        "mu_v0": 1.0e-16,
        "k_r0": 1.0e2,
        "E_D_eV": 0.25,
        "E_mu_eV": 0.20,
        "E_r_eV": 0.15,
        "T_sw": 305.0,
        "dT_sw": 8.0,
        "alpha_c": 80.0,
        "tau_m": 1.0e-3,
        "sigma_off0": 2.0e-3,
        "sigma_on0": 1.1,
        "E_off_eV": 0.12,
        "beta_off": 2.0,
        "beta_on": 5.0,
        "eps_sigma": 1.0e-30,
        "eps_R": 1.0e-30,
        "eps_V": 1.0e-12,
    }
    return deepcopy(params)


def merge_params(overrides: dict[str, float] | None = None) -> dict[str, float]:
    """Merge optional overrides into the default Ground Truth priors."""

    params = default_gt_params()
    if overrides:
        params.update(overrides)
    return params

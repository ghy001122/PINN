"""Ground Truth v1.1 profile tests."""

from __future__ import annotations

import numpy as np

from pinnpcm.physics.params import default_gt_params, initial_defect_profile, spatial_param_profiles


def test_bilayer_spatial_profiles_are_cell_wise() -> None:
    """Bilayer mode should assign distinct interface and active-layer values."""

    params = default_gt_params()
    x = np.linspace(5e-9, 95e-9, 10)
    profiles = spatial_param_profiles(x, params)
    interface_mask = x <= params["L_int"]

    assert np.any(interface_mask)
    assert np.any(~interface_mask)
    assert profiles["sigma_off0"].shape == x.shape
    assert np.all(profiles["sigma_off0"][interface_mask] == params["nb_oxide_sigma_off0"])
    assert np.all(profiles["sigma_off0"][~interface_mask] == params["v2o5_sigma_off0"])
    assert np.all(profiles["k_th"][interface_mask] == params["nb_oxide_k_th"])
    assert np.all(profiles["k_th"][~interface_mask] == params["v2o5_k_th"])


def test_gaussian_seed_initial_defect_profile() -> None:
    """Gaussian seed mode should create a localized defect enhancement."""

    params = default_gt_params()
    x = np.linspace(0.0, params["L_eff"], 101)
    seeded = initial_defect_profile(x, params)
    uniform = initial_defect_profile(x, {**params, "initial_defect_mode": "uniform"})

    assert seeded.shape == x.shape
    assert np.allclose(uniform, params["c_v0"])
    assert np.max(seeded) > params["c_v0"] + 0.5 * params["gaussian_delta_c"]
    assert seeded[np.argmax(seeded)] > seeded[0]
    assert seeded[np.argmax(seeded)] > seeded[-1]

"""Ground Truth solver smoke tests."""

from __future__ import annotations

import json

import numpy as np

from pinnpcm.physics.gt_solver import equilibrium_m, simulate_ground_truth


def test_gt_solver_smoke_shapes_and_finite() -> None:
    """Tiny Radau run should succeed on CPU and return finite arrays."""

    result = simulate_ground_truth(
        protocol="triangle",
        params=None,
        nx=7,
        nt=20,
        t_max=1.0e-4,
        rtol=1.0e-5,
        atol=1.0e-7,
    )
    assert result["success"] is True
    assert result["x"].shape == (7,)
    assert result["t"].shape == (20,)
    assert result["V"].shape == (20,)
    assert result["I"].shape == (20,)
    assert result["G"].shape == (20,)

    for key in ("c_v", "T", "m", "E", "phi", "sigma"):
        assert result[key].shape == (20, 7)
        assert np.all(np.isfinite(result[key]))


def test_gt_solver_initial_m_matches_equilibrium() -> None:
    """Initial conductive-state fraction should start from local equilibrium."""

    result = simulate_ground_truth(
        protocol="triangle",
        params=None,
        nx=7,
        nt=20,
        t_max=1.0e-4,
        rtol=1.0e-5,
        atol=1.0e-7,
    )
    params = json.loads(str(result["params_json"]))
    expected_m0 = equilibrium_m(result["c_v"][0], result["T"][0], params)
    np.testing.assert_allclose(result["m"][0], expected_m0, rtol=1.0e-10, atol=1.0e-12)

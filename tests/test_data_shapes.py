"""Sparse observation shape tests."""

from __future__ import annotations

import numpy as np

from pinnpcm.physics.gt_solver import make_sparse_observations, simulate_ground_truth


def test_sparse_observation_shapes() -> None:
    """Sparse observation helper should return aligned 1D arrays."""

    result = simulate_ground_truth(
        protocol="triangle",
        params=None,
        nx=7,
        nt=20,
        t_max=1.0e-4,
        rtol=1.0e-5,
        atol=1.0e-7,
    )
    obs = make_sparse_observations(result, protocol="triangle", n_obs=5, noise_level=0.05, seed=123)

    for key in ("t_idx", "t", "V", "I", "G", "I_clean", "G_clean"):
        assert obs[key].shape == (5,)
        assert np.all(np.isfinite(obs[key]))
    assert float(obs["noise_level"]) == 0.05

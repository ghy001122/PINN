"""Conductivity model tests."""

from __future__ import annotations

import numpy as np

from pinnpcm.physics.conductivity import conductivity_state
from pinnpcm.physics.params import default_gt_params


def test_conductivity_positive_and_shaped() -> None:
    """Conductivity branches and mixed state should be positive and shaped."""

    params = default_gt_params()
    c_v = np.full(5, params["c_v0"])
    temperature = np.full(5, params["T0"])
    m = np.linspace(0.0, 1.0, 5)
    state = conductivity_state(c_v, temperature, m, params)

    assert state["sigma"].shape == c_v.shape
    assert np.all(state["sigma"] > 0.0)
    assert np.all(state["sigma_on"] > state["sigma_off"])

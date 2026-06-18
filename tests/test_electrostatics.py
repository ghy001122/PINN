"""Electrostatics reconstruction tests."""

from __future__ import annotations

import numpy as np

from pinnpcm.physics.electrostatics import solve_series_electrostatics
from pinnpcm.physics.params import default_gt_params


def test_cell_centered_phi_matches_voltage_drop_integral() -> None:
    """Cell-centered phi should reconstruct the integrated voltage drop."""

    params = default_gt_params()
    voltage = 0.1
    nx = 101
    dx = params["L_eff"] / nx
    sigma = np.ones(nx, dtype=float)

    electrical = solve_series_electrostatics(voltage, sigma, params, dx)
    electric_field = np.asarray(electrical["E"], dtype=float)
    phi = np.asarray(electrical["phi"], dtype=float)
    cell_drop = electric_field * dx

    left_edge_phi = phi[0] + 0.5 * cell_drop[0]
    right_edge_phi = phi[-1] - 0.5 * cell_drop[-1]
    total_drop = float(np.sum(cell_drop))

    np.testing.assert_allclose(left_edge_phi - right_edge_phi, total_drop, rtol=1.0e-12, atol=1.0e-12)
    np.testing.assert_allclose(total_drop, voltage, rtol=1.0e-10, atol=1.0e-12)


def test_phi_decreases_from_left_high_potential_to_right_low_potential() -> None:
    """Positive voltage should place phi cell centers high on the left and low on the right."""

    params = default_gt_params()
    voltage = 0.1
    nx = 101
    dx = params["L_eff"] / nx
    sigma = np.ones(nx, dtype=float)

    electrical = solve_series_electrostatics(voltage, sigma, params, dx)
    phi = np.asarray(electrical["phi"], dtype=float)

    assert phi[0] > 0.99 * voltage
    assert phi[-1] < 0.01 * voltage
    assert phi[0] > phi[-1]

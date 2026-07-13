from __future__ import annotations

import numpy as np

from pinnpcm.physics.multiterminal_yz import ElectrodeSegment, solve_multiterminal_yz, uniform_series_current


def test_uniform_limit_matches_series_stack() -> None:
    sigma = np.repeat(np.asarray([1e5, 50.0, 1e5])[:, None], 8, axis=1)
    dz = np.asarray([10e-9, 20e-9, 10e-9])
    depth = 8e-7; dy = 8e-7 / 7
    result = solve_multiterminal_yz(sigma, dz, dy, [ElectrodeSegment("top", "top", 0, 8, 1.0), ElectrodeSegment("bottom", "bottom", 0, 8, 0.0)], depth_m=depth)
    reference = uniform_series_current(sigma[:, 0], dz, 1.0, 8 * dy * depth)
    assert abs(result["terminal_currents_a"]["top"] - reference) / abs(reference) < 0.05
    assert result["current_balance_error"] < 1e-8


def test_segmented_top_and_side_terminals_are_finite() -> None:
    sigma = np.ones((3, 9)) * 100.0
    result = solve_multiterminal_yz(
        sigma, np.asarray([10e-9, 20e-9, 10e-9]), 1e-7,
        [ElectrodeSegment("a", "top", 0, 3, 1.0), ElectrodeSegment("b", "top", 3, 9, 0.5), ElectrodeSegment("g", "bottom", 0, 9, 0.0), ElectrodeSegment("side", "right", 1, 2, 0.2)],
    )
    assert result["finite"] is True
    assert set(result["terminal_currents_a"]) == {"a", "b", "g", "side"}

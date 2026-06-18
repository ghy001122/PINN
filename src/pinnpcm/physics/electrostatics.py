"""Quasi-static one-dimensional series electrical relation."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def solve_series_electrostatics(
    voltage: float,
    sigma: ArrayLike,
    params: dict[str, float],
    dx: float,
) -> dict[str, np.ndarray | float]:
    """Compute series electrical fields and port observables.

    The returned `phi` is a cell-centered potential reconstructed with the
    left electrode potential `V_app` as the reference.
    """

    sigma_arr = np.maximum(np.asarray(sigma, dtype=float), params["eps_sigma"])
    r_area = float(np.sum(dx / sigma_arr) + params["eps_R"])
    current_density = float(voltage / r_area)
    electric_field = current_density / sigma_arr
    active_area = params["eta_A"] * params["A_contact"]
    current = float(active_area * current_density)
    conductance = float(current / (voltage + params["eps_V"]))

    cell_drop = electric_field * dx
    phi = voltage - (np.cumsum(cell_drop) - 0.5 * cell_drop)
    return {
        "R_area": r_area,
        "J": current_density,
        "E": electric_field,
        "I": current,
        "G": conductance,
        "phi": phi,
    }

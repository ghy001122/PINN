from __future__ import annotations

import numpy as np

from pinnpcm.solvers.m42_qiu_thermal_closure import (
    build_grid,
    run_constant_power_transient,
)


def test_m42_thermal_closure_is_finite_conservative_and_source_resolved() -> None:
    grid = build_grid(
        source_length_m=1.0e-7,
        source_width_m=5.0e-7,
        diffusion_length_m=1.0e-6,
        domain_multiplier=1.0,
        source_half_cells=1,
        outer_cells=2,
        near_depth_cells=1,
        depth_outer_cells=2,
        extruded_2d=False,
    )
    result = run_constant_power_transient(
        grid,
        source_length_m=1.0e-7,
        source_width_m=5.0e-7,
        total_power_W=1.0e-6,
        thermal_conductivity_W_mK=35.0,
        volumetric_heat_capacity_J_m3K=3.0e6,
        duration_s=1.0e-7,
        dt_s=1.0e-8,
    )
    assert result["finite"] is True
    assert result["source_cell_count"] > 0
    assert result["Tmax_rise_K"] >= result["Tmean_rise_K"] > 0.0
    assert result["maximum_enthalpy_imbalance"] <= 1.0e-10
    assert result["cumulative_enthalpy_imbalance"] <= 1.0e-10
    assert result["maximum_boundary_flux_disagreement"] <= 1.0e-12
    assert result["clip_count"] == 0
    assert np.prod(result["grid_shape"]) == result["cell_count"]

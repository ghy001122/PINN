from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.solvers.m43_finite_width_thermal import (
    _axis_stiffness,
    _prepare_system,
    build_quarter_grid,
    run_steady_case,
    run_transient_case,
)


CONFIG = Path(__file__).resolve().parents[1] / "configs" / "m43_finite_width_thermal_spreading.yaml"


def _small_config() -> dict:
    config = deepcopy(yaml.safe_load(CONFIG.read_text(encoding="utf-8")))
    config["time"]["maximum_diffusion_length_m"] = 2.0e-7
    config["grid"]["domain_multipliers_of_maximum_diffusion_length"] = [1.0, 2.0, 3.0]
    return config


def test_steady_quarter_case_closes_power_and_reconstructs_source_face() -> None:
    config = _small_config()
    grid = build_quarter_grid(config, "rho5", "M1", "D1", mode="3d")
    result = run_steady_case(config, grid)

    assert result["finite"] is True
    assert result["grid"]["cell_count"] == np.prod(result["grid"]["shape"])
    assert result["grid"]["source_edge_aligned_x"] is True
    assert result["grid"]["source_edge_aligned_y"] is True
    assert result["source"]["source_smearing"] is False
    assert result["source"]["expected_model_power_W"] == pytest.approx(0.25)
    assert result["source"]["integrated_input_power_W"] == pytest.approx(0.25)
    assert result["source"]["source_area_integral_relative_error"] <= 1.0e-12
    assert result["source"]["source_power_integral_relative_error"] <= 1.0e-12
    assert result["ledger"]["normalized_power_imbalance"] <= 1.0e-9
    assert result["metrics"]["Theta"] > 0.0
    assert result["metrics"]["source_surface_mean_rise_K"] > result["metrics"]["source_cell_mean_rise_K"]
    assert (
        result["metrics"]["source_surface_mean_rise_K"]
        - result["metrics"]["source_cell_mean_rise_K"]
    ) == pytest.approx(result["metrics"]["surface_reconstruction_rise_K"], rel=1.0e-12)


def test_transient_modal_be_is_monotone_and_closes_sensible_ledger() -> None:
    config = _small_config()
    grid = build_quarter_grid(config, "rho5", "M1", "D1", mode="3d")
    result = run_transient_case(
        config,
        grid,
        times_s=np.asarray([1.0e-10, 3.0e-10, 1.0e-9]),
        steps_per_output=8,
    )

    zth = np.asarray(result["metrics"]["source_Zth_K_W"])
    assert result["finite"] is True
    assert np.all(np.diff(zth) >= 0.0)
    assert np.all(zth > 0.0)
    assert result["ledger"]["maximum_normalized_sensible_energy_imbalance"] <= 1.0e-9
    assert len(result["ledger"]["boundary_outflow_W"]) == zth.size
    assert len(result["ledger"]["stored_sensible_energy_J"]) == zth.size
    assert len(result["ledger"]["cumulative_outward_heat_J"]) == zth.size
    assert len(result["ledger"]["normalized_sensible_energy_imbalance"]) == zth.size


def test_xz_comparator_uses_half_power_and_full_width() -> None:
    config = _small_config()
    grid = build_quarter_grid(config, "rho5", "M1", "D1", mode="xz")
    result = run_steady_case(config, grid)

    assert result["finite"] is True
    assert result["source"]["expected_model_power_W"] == pytest.approx(0.5)
    assert result["source"]["integrated_input_power_W"] == pytest.approx(0.5)
    assert result["source"]["model_source_area_m2"] == pytest.approx(2.5e-14)
    assert result["ledger"]["far_y_outward_power_W"] == 0.0
    assert result["ledger"]["normalized_power_imbalance"] <= 1.0e-9


def test_square_development_solver_is_finite_and_power_conservative() -> None:
    config = _small_config()
    grid = build_quarter_grid(config, "rho1", "M1", "D1", mode="3d")
    result = run_steady_case(config, grid)
    assert result["finite"] is True
    assert result["metrics"]["Theta"] > 0.0
    assert result["ledger"]["normalized_power_imbalance"] <= 1.0e-9


def test_modal_steady_solution_matches_direct_control_volume_matrix() -> None:
    config = _small_config()
    config["time"]["maximum_diffusion_length_m"] = 6.0e-8
    config["grid"]["domain_multipliers_of_maximum_diffusion_length"] = [
        1.0,
        2.0,
        3.0,
    ]
    grid = build_quarter_grid(config, "rho5", "M1", "D1", mode="3d")
    system = _prepare_system(config, grid)
    dx, dy, dz = system.widths_x_m, system.widths_y_m, system.widths_z_m
    mx, my, mz = np.diag(dx), np.diag(dy), np.diag(dz)
    kx = _axis_stiffness(dx, far_dirichlet=True)
    ky = _axis_stiffness(dy, far_dirichlet=True)
    kz = _axis_stiffness(dz, far_dirichlet=True)
    operator = (
        np.kron(mz, np.kron(my, kx))
        + np.kron(mz, np.kron(ky, mx))
        + np.kron(kz, np.kron(my, mx))
    )
    conductivity = config["material"]["thermal_conductivity_W_mK"]
    direct_temperature = np.linalg.solve(
        conductivity * operator, system.source_W.reshape(-1)
    ).reshape(grid.shape)
    source_area = dy[:, None] * dx[None, :]
    source_xy = system.source_mask[0]
    cell_mean = float(
        np.sum(direct_temperature[0][source_xy] * source_area[source_xy])
        / np.sum(source_area[source_xy])
    )
    surface_mean = cell_mean + (
        system.source_flux_W_m2 * dz[0] / (2.0 * conductivity)
    )
    theta_direct = (
        conductivity
        * np.sqrt(config["geometry"]["source_area_m2"])
        * surface_mean
        / config["geometry"]["full_power_W"]
    )
    modal = run_steady_case(config, grid)
    assert modal["metrics"]["Theta"] == pytest.approx(theta_direct, rel=1.0e-12)
def test_steady_fvm_resistance_is_invariant_to_registered_full_power() -> None:
    config = _small_config()
    grid = build_quarter_grid(config, "rho5", "M1", "D1", mode="3d")
    baseline = run_steady_case(config, grid)

    factor = 3.7
    scaled_config = deepcopy(config)
    scaled_config["geometry"]["full_power_W"] *= factor
    scaled_config["geometry"]["quarter_power_W"] *= factor
    scaled_config["geometry"]["xz_half_domain_power_W"] *= factor
    scaled = run_steady_case(scaled_config, grid)

    assert scaled["metrics"]["Rs_K_W"] == pytest.approx(
        baseline["metrics"]["Rs_K_W"], rel=2.0e-13
    )
    assert scaled["metrics"]["Theta"] == pytest.approx(
        baseline["metrics"]["Theta"], rel=2.0e-13
    )
    assert scaled["metrics"]["source_surface_mean_rise_K"] == pytest.approx(
        factor * baseline["metrics"]["source_surface_mean_rise_K"], rel=2.0e-13
    )
    assert scaled["source"]["integrated_input_power_W"] == pytest.approx(
        factor * baseline["source"]["integrated_input_power_W"], rel=2.0e-13
    )
    assert scaled["ledger"]["total_outward_power_W"] == pytest.approx(
        factor * baseline["ledger"]["total_outward_power_W"], rel=2.0e-13
    )
    assert scaled["ledger"]["normalized_power_imbalance"] <= 1.0e-9
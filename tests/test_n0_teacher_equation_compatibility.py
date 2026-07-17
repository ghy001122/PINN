"""Non-trivial manufactured and frozen-FVM conservation tests for N0-R."""

from __future__ import annotations

import numpy as np
import yaml

from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.n0_compatibility import (
    bilayer_piecewise_manufactured,
    defect_manufactured,
    frozen_fvm_conservation_audit,
    heat_manufactured,
    interface_discretization_audit,
    uniform_conduction_manufactured,
)


def _params() -> dict[str, object]:
    config = yaml.safe_load(open("configs/gt_v1_acceptance_triangle.yaml", encoding="utf-8"))
    return merge_params(config.get("params"))


def test_nonzero_voltage_uniform_conduction_matches_analytic_solution() -> None:
    case = uniform_conduction_manufactured(_params())
    assert case["potential_left_error_V"] < 1.0e-14
    assert case["potential_right_error_V"] < 1.0e-14
    assert case["current_density_relative_rms_error"] < 1.0e-10
    assert case["port_current_relative_error"] < 1.0e-14


def test_heat_manufactured_case_exercises_storage_conduction_source_and_sink() -> None:
    case = heat_manufactured(_params(), 3.0e-3)
    assert case["storage_rms_W_per_m3"] > 0.0
    assert case["conduction_rms_W_per_m3"] > 0.0
    assert case["sink_rms_W_per_m3"] > 0.0
    assert case["manufactured_source_rms_W_per_m3"] > 0.0
    assert case["normalized_residual_rms"] < 1.0e-12


def test_defect_manufactured_case_exercises_diffusion_drift_and_reaction() -> None:
    case = defect_manufactured(_params(), 3.0e-3)
    assert case["diffusion_divergence_rms_per_s"] > 0.0
    assert case["drift_divergence_rms_per_s"] > 0.0
    assert case["reaction_rms_per_s"] > 0.0
    assert case["normalized_residual_rms"] < 1.0e-12


def test_bilayer_piecewise_solution_has_state_continuity_and_flux_continuity() -> None:
    case = bilayer_piecewise_manufactured(_params())
    assert case["phi_jump_normalized"] < 1.0e-12
    assert case["temperature_jump_normalized"] < 1.0e-12
    assert case["current_flux_jump_normalized"] < 1.0e-12
    assert case["heat_flux_jump_normalized"] < 1.0e-12
    assert case["potential_derivative_ratio"] != 1.0
    assert case["temperature_derivative_ratio"] != 1.0


def test_frozen_fvm_discrete_ledgers_close_without_differentiating_saved_fields() -> None:
    params = _params()
    with np.load("data/processed/gt_v1_acceptance/gt_triangle.npz") as archive:
        gt = {key: np.asarray(archive[key]) for key in archive.files if key != "params_json"}
    audit = frozen_fvm_conservation_audit(gt, params, sample_count=7)
    assert audit["max_defect_mass_normalized_imbalance"] < 1.0e-10
    assert audit["max_global_energy_normalized_imbalance"] < 1.0e-10
    assert audit["max_current_normalized_spread"] < 1.0e-10
    assert audit["max_port_current_relative_error"] < 1.0e-10


def test_frozen_cell_centres_do_not_place_face_exactly_at_declared_interface() -> None:
    params = _params()
    with np.load("data/processed/gt_v1_acceptance/gt_triangle.npz") as archive:
        x = np.asarray(archive["x"])
    audit = interface_discretization_audit(x, params)
    assert audit["face_offset_from_declared_m"] != 0.0
    assert abs(audit["face_offset_over_dx"]) < 0.5

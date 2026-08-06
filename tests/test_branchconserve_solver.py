from __future__ import annotations

from pathlib import Path

import numpy as np

from pinnpcm.branchconserve.contract import load_branchconserve_contract
from pinnpcm.branchconserve.solver import solve_steady_equilibrium
from pinnpcm.branchconserve.steady_model import build_branchconserve_model


ROOT = Path(__file__).resolve().parents[1]


def _model():
    contract = load_branchconserve_contract(
        ROOT / "configs/q2_branchconserve_2d_steady_mve_v1.yaml",
        repository_root=ROOT,
    )
    return build_branchconserve_model(contract, spatial_level=1)


def test_unique_solver_certifies_zero_drive_equilibrium() -> None:
    model = _model()
    outcome = solve_steady_equilibrium(
        model,
        device_voltage_V=0.0,
        branch_memory=1.0,
        initial_temperature_K=np.full(model.grid.shape, model.ambient_temperature_K),
    )
    assert outcome.success
    assert outcome.code == "PASS"
    assert outcome.evaluation is not None
    assert outcome.evaluation.postcertified
    assert outcome.evaluation.scaled_thermal_residual_inf <= 1.0e-8
    assert outcome.last_scaled_update_inf <= 1.0e-8
    assert outcome.telemetry.electrical_subsolves == outcome.telemetry.full_residual_evaluations


def test_invalid_initial_field_has_structured_failure() -> None:
    model = _model()
    invalid = np.full(model.grid.shape, 500.0)
    outcome = solve_steady_equilibrium(
        model,
        device_voltage_V=1.0,
        branch_memory=1.0,
        initial_temperature_K=invalid,
    )
    assert not outcome.success
    assert outcome.code == "STEADY_NONFINITE_OR_RANGE"


def test_lgmres_outer_limit_does_not_spend_only_budget_divided_by_inner_m() -> None:
    """Regression for the first invalid 9 V smoke's premature info=18 exit."""

    model = _model()
    outcome = solve_steady_equilibrium(
        model,
        device_voltage_V=0.28125,
        branch_memory=1.0,
    )
    assert outcome.success, outcome.telemetry.failure_detail
    assert outcome.telemetry.jv_evaluations <= 512
    assert outcome.telemetry.full_residual_evaluations <= 640


def test_small_second_newton_correction_retains_jv_homogeneity() -> None:
    """Regression for the second invalid smoke at the next load-line bracket."""

    model = _model()
    first = solve_steady_equilibrium(
        model, device_voltage_V=0.28125, branch_memory=1.0
    )
    assert first.success
    outcome = solve_steady_equilibrium(
        model,
        device_voltage_V=0.5625,
        branch_memory=1.0,
        initial_temperature_K=first.temperature_K,
    )
    assert outcome.success, outcome.telemetry.failure_detail
    assert outcome.last_scaled_update_inf <= 1.0e-8


def test_solver_contract_has_no_fallback_or_portfolio() -> None:
    model = _model()
    solver = model.contract.solver
    assert solver["identity"] == "temperature_primary_damped_newton_krylov_v1"
    assert solver["initialization"]["alternate_solver_after_failure"] == "forbidden"
    assert solver["jv"]["method"] == "central_difference"
    assert solver["jv"]["subtraction"] == (
        "conservative_termwise_linear_thermal_plus_central_joule"
    )
    assert solver["jv"]["direction_normalization"] == (
        "infinity_norm_unit_direction_with_homogeneous_rescaling"
    )
    assert solver["lgmres"]["initial_guess"] == (
        "frozen_joule_preconditioner_applied_to_newton_rhs"
    )
    assert solver["jv_evaluations_max"] == 512
    assert solver["full_residual_evaluations_max"] == 640

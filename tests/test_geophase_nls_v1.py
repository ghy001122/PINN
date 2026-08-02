from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation.geophase_s0_direct_physics import resolved_s2_config
from pinnpcm.evaluation import geophase_nls_v1_qualification as qualification
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as implicit
from pinnpcm.solvers import geophase_nls_v1 as nls
from pinnpcm.solvers.geophase_nls_v1_streaming import (
    run_s2_streaming_protocol_nls_v1,
)


pytestmark = [pytest.mark.phase1, pytest.mark.current]

ROOT = Path(__file__).resolve().parents[1]
GOAL_CONFIG = ROOT / "configs" / "geophase_nls_v1_s0_c01_c06_r1.yaml"
TERMINAL_SUMMARY = (
    ROOT / "outputs" / "tables" / "geophase_nls_v1" / "nls_v1_terminal_summary.json"
)


@pytest.fixture(scope="module")
def runtime_context():
    config = resolved_s2_config()
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    return config, grid, fields, closure


def _unit_grid():
    return type("UnitGrid", (), {"nx": 1, "ny": 1})()


def test_relaxed_increment_cannot_hide_full_fixed_point_defect() -> None:
    (
        _vector,
        iterations,
        relaxed_increment,
        fixed_point_defect,
        residual,
        _blocks,
        history,
    ) = nls._picard_nls_v1(
        np.zeros(4),
        lambda vector: vector + 1.0,
        lambda _vector: np.zeros(4),
        grid=_unit_grid(),
        maximum_iterations=1,
        relaxation=0.5,
        update_tolerance=0.75,
        residual_tolerance=1.0e-8,
    )

    assert iterations == 1
    assert relaxed_increment == pytest.approx(0.5)
    assert relaxed_increment <= 0.75
    assert fixed_point_defect == pytest.approx(1.0)
    assert fixed_point_defect > 0.75
    assert residual == 0.0
    assert history[-1].fixed_point_defect_inf == fixed_point_defect


def test_full_defect_cannot_hide_failed_scaled_residual() -> None:
    (
        _vector,
        iterations,
        _relaxed_increment,
        fixed_point_defect,
        residual,
        blocks,
        _history,
    ) = nls._picard_nls_v1(
        np.zeros(4),
        lambda vector: vector,
        lambda _vector: np.asarray([0.0, 0.0, 0.0, 2.0]),
        grid=_unit_grid(),
        maximum_iterations=2,
        relaxation=0.5,
        update_tolerance=1.0e-8,
        residual_tolerance=1.0e-8,
    )

    assert iterations == 2
    assert fixed_point_defect == 0.0
    assert residual == 2.0
    assert blocks["circuit"] == 2.0


def test_newton_failure_is_preserved_when_nls_v1_fallback_succeeds(
    monkeypatch: pytest.MonkeyPatch, runtime_context
) -> None:
    config, grid, fields, closure = runtime_context
    initial = implicit.initial_s2_state(grid, closure, fields, config)

    def fail_newton(*_args, telemetry=None, **_kwargs):
        assert telemetry is not None
        telemetry.update(
            {
                "iteration_endpoint": 3,
                "stage": "krylov_linear_solve",
                "scaled_residual_inf": 2.5e-4,
                "scaled_update_inf": 4.0e-5,
                "krylov_matvecs": 7,
                "armijo_backtracks": 2,
            }
        )
        raise np.linalg.LinAlgError("synthetic Krylov breakdown")

    monkeypatch.setattr(nls, "_newton_krylov_nls_v1", fail_newton)
    step = nls.advance_s2_backward_euler_nls_v1(
        initial,
        input_voltage_V=9.0,
        dt_s=float(config["reference_solver"]["time_grid"]["base_max_step_s"]),
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )

    diagnostics = step.nonlinear
    assert diagnostics.method == "nls_v1_fail_closed_fixed_point_fallback"
    assert diagnostics.newton_failure is not None
    assert diagnostics.newton_failure["exception_class"] == "LinAlgError"
    assert diagnostics.newton_failure["exception_message"] == (
        "synthetic Krylov breakdown"
    )
    assert diagnostics.newton_failure["iteration_endpoint"] == 3
    assert diagnostics.newton_failure["krylov_matvecs"] == 7
    assert diagnostics.newton_failure["armijo_backtracks"] == 2
    assert diagnostics.fixed_point_defect_inf is not None
    assert diagnostics.fixed_point_defect_inf <= float(
        config["reference_solver"]["nonlinear_tolerances"][
            "scaled_update_relative"
        ]
    )
    assert diagnostics.scaled_residual_inf <= max(
        float(
            config["reference_solver"]["nonlinear_tolerances"][
                "scaled_residual_absolute"
            ]
        ),
        float(
            config["reference_solver"]["nonlinear_tolerances"][
                "scaled_residual_relative"
            ]
        ),
    )
    implicit.validate_s2_state(step.state, grid, closure)


def test_controller_config_selects_nls_v1_without_changing_legacy_default(
    runtime_context,
) -> None:
    config, grid, fields, closure = runtime_context
    initial = implicit.initial_s2_state(grid, closure, fields, config)
    legacy = implicit.advance_s2_backward_euler(
        initial,
        input_voltage_V=0.0,
        dt_s=float(config["reference_solver"]["time_grid"]["base_max_step_s"]),
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )
    nls_v1 = nls.advance_s2_backward_euler_nls_v1(
        initial,
        input_voltage_V=0.0,
        dt_s=float(config["reference_solver"]["time_grid"]["base_max_step_s"]),
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )

    assert legacy.nonlinear.method == "analytic_zero_drive_equilibrium"
    assert nls_v1.nonlinear.method == "nls_v1_analytic_zero_drive_equilibrium"


def test_real_embedded_protocol_uses_nls_v1_on_every_path(runtime_context) -> None:
    config, grid, fields, closure = runtime_context
    initial = implicit.initial_s2_state(grid, closure, fields, config)
    result = nls.simulate_s2_protocol_nls_v1(
        initial,
        case_id="TEST-NLS-V1-QUIESCENT",
        protocol=config["formal_protocols"]["protocols"]["quiescent_9V"],
        protocol_id="quiescent_9V",
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=1.0e-8,
        cache=implicit.build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )

    assert result.completed is True
    assert result.achieved_final_time_s == pytest.approx(1.0e-8)
    assert len(result.steps) == 1
    accepted = result.steps[0]
    assert accepted.nonlinear.solver_identity == nls.NLS_V1_ID
    assert accepted.accepted_first_half.nonlinear.solver_identity == nls.NLS_V1_ID
    assert accepted.controller.full_nonlinear.solver_identity == nls.NLS_V1_ID
    assert accepted.controller.second_half_nonlinear.solver_identity == nls.NLS_V1_ID


def test_streaming_projection_preserves_nls_v1_identity(runtime_context) -> None:
    config, grid, fields, closure = runtime_context
    initial = implicit.initial_s2_state(grid, closure, fields, config)
    result = run_s2_streaming_protocol_nls_v1(
        "TEST-NLS-V1-STREAMING",
        initial,
        protocol=config["formal_protocols"]["protocols"]["quiescent_9V"],
        protocol_id="quiescent_9V",
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=1.0e-8,
        cache=implicit.build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )

    assert result.protocol_result.completed is True
    assert result.scalar_records
    assert all(
        record["nonlinear_solver_identity"] == nls.NLS_V1_ID
        for record in result.scalar_records
    )


def test_final_time_landing_tolerance_skips_nonphysical_subfloor_residue(
    runtime_context, monkeypatch
) -> None:
    config, grid, fields, closure = runtime_context
    stop = 2.0e-5
    residue = 1.73133534418779e-17
    initial = replace(
        implicit.initial_s2_state(grid, closure, fields, config),
        time_s=stop - residue,
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a within-tolerance endpoint must not invoke a solver")

    monkeypatch.setattr(
        nls,
        "attempt_s2_embedded_interval_nls_v1",
        fail_if_called,
    )
    result = nls.simulate_s2_protocol_nls_v1(
        initial,
        case_id="TEST-NLS-V1-ENDPOINT-TOLERANCE",
        protocol=config["formal_protocols"]["protocols"]["quiescent_9V"],
        protocol_id="quiescent_9V",
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=stop,
        cache=implicit.build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )

    tolerance = max(
        1.0e-18,
        stop * nls.NLS_V1_TIME_LANDING_RELATIVE_TOLERANCE,
    )
    assert result.completed is True
    assert result.diagnostics.accepted_steps == 0
    assert abs(result.achieved_final_time_s - stop) <= tolerance


def test_nls_v1_config_freezes_dual_gate_identity_and_source_hashes() -> None:
    config = yaml.safe_load(GOAL_CONFIG.read_text(encoding="utf-8"))
    assert config["identity"]["nonlinear_solver_id"] == nls.NLS_V1_ID
    assert config["implementation"]["scaled_update_relative"] == 1.0e-8
    assert config["implementation"]["scaled_residual_absolute"] == 1.0e-8
    assert config["implementation"]["success_requires_both_gates"] is True
    assert config["implementation"]["fallback_maximum_iterations"] == 80
    assert config["implementation"]["fallback_200_iteration_upgrade"].startswith(
        "forbidden"
    )
    assert (
        config["implementation"]["endpoint_landing_relative_tolerance"]
        == nls.NLS_V1_TIME_LANDING_RELATIVE_TOLERANCE
    )
    assert config["implementation"]["schur_reduced_upgrade"].startswith(
        "not_activated"
    )
    assert config["identity"]["qualification_id"] == "NLSV1-QUAL-20260802-V2"
    assert config["prior_invalid_qualification"]["scientific_vote"] is False
    assert config["formal_s0"]["formal_execution_count"] == 0
    for item in (
        *config["frozen_authority"],
        *config["implementation"]["source_files"],
    ):
        observed = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
        assert observed == item["sha256"]


@pytest.mark.parametrize(
    "relative_path",
    [
        "outputs/tables/geophase_controller_v3/qualification/"
        "CTRLV3-QUAL-20260801-V2/failures/"
        "CTRLV3-QUAL-QUIESCENT-9V-T1.json",
        "outputs/tables/geophase_controller_v3/qualification/"
        "CTRLV3-QUAL-20260801-V4/failures/"
        "CTRLV3-QUAL-QUIESCENT-9V-T1.json",
    ],
)
def test_frozen_controller_failure_states_pass_nls_v1_replay(
    relative_path: str,
) -> None:
    payload = qualification._replay_failure_state(ROOT / relative_path)
    assert payload["passed"] is True
    assert payload["scaled_residual_inf"] <= 1.0e-8
    assert payload["fixed_point_defect_inf"] <= 1.0e-8
    assert payload["iterations"] <= 6


def test_nls_v1_terminal_summary_preserves_fail_closed_downstream_boundary() -> None:
    summary = json.loads(TERMINAL_SUMMARY.read_text(encoding="utf-8"))
    run = summary["qualification_v1"]["standard_quiescent_run"]
    assert summary["terminal_state"] == "GOAL_UNSUCCESSFUL_NLS_V1"
    assert summary["scientific_vote"] is False
    assert run["completed"] is False
    assert run["stop_reason"] == "maximum_wall_clock_reached"
    assert run["wall_time_s"] > run["per_run_wall_time_limit_s"]
    assert summary["qualification_disposition"]["schur_eligibility_condition_met"] is False
    assert summary["endpoint_correction"]["full_qualification_invoked"] is False
    assert summary["downstream"]["formal_execution_count"] == 0
    assert summary["downstream"]["phase2_dataset_generated"] is False
    assert summary["downstream"]["c01_trained"] is False
    assert summary["downstream"]["c06_trained"] is False

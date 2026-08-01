from __future__ import annotations

from pathlib import Path
import hashlib
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation import geophase_controller_v3_qualification as qualification
from pinnpcm.evaluation.geophase_s0_direct_physics import resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_controller_v3 as controller_v3
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    build_s2_solver_cache,
    initial_s2_state,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming_v3 import (
    DENSE_OUTPUT_ID,
    run_s2_streaming_protocol_v3,
)


pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def v3_context():
    config = resolved_s2_config()
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    return config, grid, fields, closure


def test_v3_output_grid_is_reconstructed_without_forced_solver_landings(
    v3_context,
) -> None:
    config, grid, fields, closure = v3_context
    initial = initial_s2_state(grid, closure, fields, config)
    protocol_id = "transition_probe_12p5V"
    result = run_s2_streaming_protocol_v3(
        "DEV-V3-OUTPUT-DECOUPLING",
        initial,
        protocol=config["formal_protocols"]["protocols"][protocol_id],
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=2.0e-8,
        cache=build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )

    assert result.protocol_result.completed is True
    assert result.protocol_result.diagnostics.accepted_steps == 2
    assert len(result.scalar_records) == 5
    np.testing.assert_allclose(
        [row["time_s"] for row in result.scalar_records],
        np.linspace(0.0, 2.0e-8, 5),
        rtol=0.0,
        atol=1.0e-20,
    )
    assert all(
        row["time_controller"] == controller_v3.CONTROLLER_V3_ID
        for row in result.scalar_records
    )
    assert all(row["dense_output"] == DENSE_OUTPUT_ID for row in result.scalar_records)
    assert all(
        row["ledger_output_semantics"] == "accepted_fine_interval_not_interpolated"
        for row in result.scalar_records
    )
    assert all(bool(row["aggregate_overall_pass"]) for row in result.scalar_records[1:])


def test_v3_terminal_failure_contains_atomic_replay_payload(
    monkeypatch: pytest.MonkeyPatch, v3_context
) -> None:
    config, grid, fields, closure = v3_context
    initial = initial_s2_state(grid, closure, fields, config)
    protocol_id = "transition_probe_12p5V"

    def rejected_observation(state, **kwargs):
        del kwargs
        path = SimpleNamespace(overall_pass=False)
        diagnostics = SimpleNamespace(
            outer_interval_s=5.0e-9,
            full_input_voltage_V=12.5,
            first_half_input_voltage_V=12.5,
            second_half_input_voltage_V=12.5,
            below_floor_remainder=False,
            at_outer_floor=True,
            rejection_index=1,
            coupled_solve_count=0,
            embedded_error=None,
            aggregate=None,
            full_step=path,
            first_half_step=None,
            second_half_step=None,
        )
        return SimpleNamespace(
            previous_state=state,
            step=None,
            full_candidate=None,
            first_half_candidate=None,
            second_half_candidate=None,
            diagnostics=diagnostics,
            error_class="RuntimeError",
            error_message="synthetic fail-closed attempt",
        )

    monkeypatch.setattr(controller_v3, "attempt_s2_embedded_interval", rejected_observation)
    monkeypatch.setattr(controller_v3, "controller_v2_limits", lambda *_: (1.0e-8, 5.0e-9))
    failures: list[dict] = []
    with pytest.raises(controller_v3.ControllerV3ExecutionError) as raised:
        controller_v3.simulate_s2_protocol_v3(
            initial,
            case_id="DEV-V3-FAILURE-REPLAY",
            protocol=config["formal_protocols"]["protocols"][protocol_id],
            protocol_id=protocol_id,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            final_time_s=1.0e-8,
            failure_callback=failures.append,
        )

    assert len(failures) == 1
    assert raised.value.record == failures[0]
    record = failures[0]
    assert record["terminal"] is True
    assert record["rejection_class"] == "integrity_or_solver"
    assert record["candidate_presence"] == {
        "full_step": False,
        "first_half_step": False,
        "second_half_step": False,
    }
    assert record["last_valid_state_sha256"]
    assert record["exception_message"] == "controller-v3 sub-floor recovery exhausted"
    assert record["minimum_recoverable_interval_s"] == pytest.approx(5.0e-9 / 16.0)
    assert record["traceback"]
    assert record["replay"]["previous_state"]["temperature_K"]


def test_v3_subfloor_recovery_runs_the_full_embedded_attempt(
    monkeypatch: pytest.MonkeyPatch, v3_context
) -> None:
    config, grid, fields, closure = v3_context
    initial = initial_s2_state(grid, closure, fields, config)
    protocol_id = "transition_probe_12p5V"
    original_attempt = controller_v3.attempt_s2_embedded_interval
    calls: list[float] = []

    def reject_once_then_real(state, **kwargs):
        calls.append(float(kwargs["outer_interval_s"]))
        if len(calls) == 1:
            path = SimpleNamespace(overall_pass=False)
            diagnostics = SimpleNamespace(
                outer_interval_s=kwargs["outer_interval_s"],
                full_input_voltage_V=12.5,
                first_half_input_voltage_V=12.5,
                second_half_input_voltage_V=12.5,
                below_floor_remainder=False,
                at_outer_floor=True,
                rejection_index=0,
                coupled_solve_count=0,
                embedded_error=None,
                aggregate=None,
                full_step=path,
                first_half_step=None,
                second_half_step=None,
            )
            return SimpleNamespace(
                previous_state=state,
                step=None,
                full_candidate=None,
                first_half_candidate=None,
                second_half_candidate=None,
                diagnostics=diagnostics,
                error_class="RuntimeError",
                error_message="synthetic locked-floor failure",
            )
        return original_attempt(state, **kwargs)

    monkeypatch.setattr(controller_v3, "attempt_s2_embedded_interval", reject_once_then_real)
    monkeypatch.setattr(controller_v3, "controller_v2_limits", lambda *_: (1.0e-8, 1.0e-8))
    result = controller_v3.simulate_s2_protocol_v3(
        initial,
        case_id="DEV-V3-SUBFLOOR-RECOVERY",
        protocol=config["formal_protocols"]["protocols"][protocol_id],
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=1.0e-8,
        cache=build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )

    assert result.completed is True
    assert result.diagnostics.accepted_steps == 2
    assert result.diagnostics.locked_floor_failures == 1
    assert result.diagnostics.minimum_accepted_step_s == pytest.approx(5.0e-9)
    assert calls[:2] == pytest.approx([1.0e-8, 5.0e-9])


def test_v3_source_does_not_import_historical_execution_control_planes() -> None:
    for module in (controller_v3,):
        source = module.__file__
        assert source is not None
        text = Path(source).read_text(encoding="utf-8")
        assert "equivalence" not in text
        assert "readiness" not in text
        assert "geophase_s0_formal" not in text


def test_v3_goal_config_freezes_new_identity_without_one_defect_stop_policy() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "configs" / "geophase_controller_v3_s0_c01_c06_r1.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert config["identity"]["base_main_commit"] == (
        "b28aa97ccbdbc1b03b43e8deb13b3bbc35c71ead"
    )
    assert config["identity"]["controller_id"] == controller_v3.CONTROLLER_V3_ID
    assert config["identity"]["old_s0_v1_v2_reuse"] == "forbidden"
    assert config["qualification"]["fixed_output_points"] == 4001
    assert config["qualification"]["stricter_time_divisor"] == 4
    assert len(config["qualification"]["cases"]) == 4
    assert config["identity"]["qualification_invocation_count"] == 3
    assert config["identity"]["prior_invalid_qualification_invocation"].endswith("-V1")
    assert config["identity"]["prior_rejected_controller_candidate"].endswith("-V2")
    assert config["implementation"]["subfloor_recovery"]["forced_acceptance"] == "forbidden"
    assert [item["spatial_level"] for item in config["qualification"]["runtime_profiles"]] == [1, 2, 4]
    serialized = path.read_text(encoding="utf-8")
    assert "implementation_repair_limit" not in serialized
    assert "execution_attempt_limit" not in serialized
    for item in config["implementation"]["source_files"]:
        observed = hashlib.sha256((root / item["path"]).read_bytes()).hexdigest()
        assert observed == item["sha256"]


def test_v3_qualification_rejection_metrics_remain_canonical_json_finite() -> None:
    penalty = qualification._nrmse(np.asarray([np.nan]), np.asarray([1.0]))
    event_penalty = qualification._event_relative_error(
        [{"direction": "up", "crossing_time_s": 1.0}],
        [{"direction": "down", "crossing_time_s": 1.0}],
    )
    assert np.isfinite(penalty)
    assert np.isfinite(event_penalty)
    assert penalty > 1.0
    assert event_penalty > 1.0

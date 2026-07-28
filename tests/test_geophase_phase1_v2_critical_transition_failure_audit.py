from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as implicit
from scripts import run_geophase_phase1_v2_critical_transition_failure_audit as audit


ROOT = Path(__file__).resolve().parents[1]
AUDIT_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_critical_transition_failure_audit.yaml"
)
S2_CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
TELEMETRY_PATH = OUTPUT_DIR / "critical_transition_failure_telemetry.json"
ATTEMPTS_PATH = OUTPUT_DIR / "critical_transition_attempts.csv"
DIAGNOSIS_PATH = OUTPUT_DIR / "critical_transition_diagnosis.json"
REPORT_PATH = (
    ROOT
    / "docs"
    / "codex_reports"
    / "geophase_phase1_v2_critical_transition_failure_audit.md"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def context():
    config = yaml.safe_load(S2_CONFIG_PATH.read_text(encoding="utf-8"))
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    initial = implicit.S2State(
        time_s=0.0,
        temperature_K=np.full(grid.shape, closure.T_c_up_K),
        conductive_state=np.full(grid.shape, 0.5),
        branch_memory=np.ones(grid.shape),
        device_voltage_V=0.0,
    )
    protocol = config["formal_protocols"]["protocols"]["transition_probe_12p5V"]
    return config, grid, fields, closure, initial, protocol


def _fake_step(old_state: implicit.S2State, dt_s: float, increment: float):
    return SimpleNamespace(
        state=implicit.S2State(
            time_s=old_state.time_s + dt_s,
            temperature_K=old_state.temperature_K.copy(),
            conductive_state=old_state.conductive_state + increment,
            branch_memory=old_state.branch_memory.copy(),
            device_voltage_V=old_state.device_voltage_V,
        ),
        nonlinear=SimpleNamespace(
            method="damped_newton_krylov",
            iterations=1,
            krylov_matvecs=1,
            armijo_backtracks=0,
            fallback_picard_iterations=0,
        ),
    )


def _run_synthetic(
    context,
    monkeypatch: pytest.MonkeyPatch,
    *,
    increment: float,
    observer=None,
    attempted_dts: list[float] | None = None,
):
    config, grid, fields, closure, initial, protocol = context
    dt_records = [] if attempted_dts is None else attempted_dts

    def fake_advance(old_state, *, dt_s, **_kwargs):
        dt_records.append(float(dt_s))
        return _fake_step(old_state, float(dt_s), increment)

    monkeypatch.setattr(implicit, "advance_s2_backward_euler", fake_advance)
    result = implicit.simulate_s2_protocol(
        initial,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=2.0e-8,
        forced_times_s=(0.0, 5.0e-9, 1.0e-8, 1.5e-8, 2.0e-8),
        attempted_candidate_callback=observer,
    )
    return result, dt_records


def test_preregistration_locks_one_full_history_replay_and_zero_formal_work() -> None:
    config = yaml.safe_load(AUDIT_CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["execution_boundary"]["merged_main_commit"] == (
        "6a7c9e0ba7be2b5bc89f751c0751110af2bab7ef"
    )
    assert config["execution_boundary"]["real_numerical_replay_limit"] == 1
    assert config["execution_boundary"]["formal_execution_count"] == 0
    assert config["execution_boundary"]["formal_artifact_count"] == 0
    replay = config["single_locked_replay"]
    assert replay["sample_id"] == "PRE-PARITY-STREAM"
    assert replay["execution_path"] == "full_history_control"
    assert replay["streaming_execution"] == "forbidden"
    assert replay["streaming_status_after_reproduced_failure"] == (
        "not_reached_by_preregistered_stop"
    )
    assert replay["grid"] == {"spatial_level": 1, "nx": 10, "ny": 25}
    assert replay["initial_state"] == {
        "temperature_K": 336.4,
        "branch_memory_b": 1.0,
        "conductive_state_s": 0.5,
        "device_voltage_V": 0.0,
    }
    assert config["locked_controller"]["transition_increment_gate"] == 0.02
    assert config["locked_controller"]["transition_floor_s"] == 2.5e-10


def test_attempt_observer_preserves_synthetic_locked_floor_ladder(
    context, monkeypatch: pytest.MonkeyPatch
) -> None:
    observations: list[implicit.S2AttemptObservation] = []
    with pytest.raises(
        RuntimeError, match="S2 transition increment failed at locked floor"
    ):
        _run_synthetic(
            context,
            monkeypatch,
            increment=0.03,
            observer=observations.append,
        )
    observed_dts = [item.dt_s for item in observations]
    assert observed_dts == pytest.approx(
        [5.0e-9, 2.5e-9, 1.25e-9, 6.25e-10, 3.125e-10, 2.5e-10],
        rel=0.0,
        abs=1.0e-22,
    )
    assert observations[-1].at_locked_floor is True
    assert all(item.candidate is not None for item in observations)
    assert all(item.transition_increment == pytest.approx(0.03) for item in observations)

    control_dts: list[float] = []
    with pytest.raises(
        RuntimeError, match="S2 transition increment failed at locked floor"
    ):
        _run_synthetic(
            context,
            monkeypatch,
            increment=0.03,
            observer=None,
            attempted_dts=control_dts,
        )
    assert control_dts == pytest.approx(observed_dts, rel=0.0, abs=1.0e-22)


def test_attempt_observer_preserves_successful_synthetic_control_flow(
    context, monkeypatch: pytest.MonkeyPatch
) -> None:
    observations: list[implicit.S2AttemptObservation] = []
    observed, observed_dts = _run_synthetic(
        context,
        monkeypatch,
        increment=0.015,
        observer=observations.append,
    )
    control, control_dts = _run_synthetic(
        context,
        monkeypatch,
        increment=0.015,
        observer=None,
    )

    assert observed.completed is control.completed is True
    assert observed_dts == pytest.approx(control_dts, rel=0.0, abs=1.0e-22)
    for field in (
        "accepted_steps",
        "rejected_steps",
        "transition_rejections",
        "nonlinear_rejections",
        "minimum_accepted_step_s",
        "maximum_accepted_step_s",
        "maximum_transition_increment",
        "accepted_dt_p10_s",
        "accepted_dt_p50_s",
        "accepted_dt_p90_s",
    ):
        assert getattr(observed.diagnostics, field) == pytest.approx(
            getattr(control.diagnostics, field)
        )
    np.testing.assert_array_equal(
        observed.steps[-1].state.conductive_state,
        control.steps[-1].state.conductive_state,
    )
    assert len(observations) == len(observed_dts)


def test_synthetic_failure_bundle_is_validated_and_atomically_published(
    tmp_path: Path,
) -> None:
    row = {field: None for field in audit.ATTEMPT_FIELDS}
    row.update(
        {
            "attempt_index": 1,
            "execution_path": "full_history_control",
            "candidate_available": True,
            "candidate_integrity_pass": True,
        }
    )
    telemetry = {
        "task_id": "Q2_PHASE1_V2_CRITICAL_TRANSITION_FAILURE_MECHANISM_AUDIT",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    diagnosis = {
        "task_id": telemetry["task_id"],
        "disposition": "AUDIT_INVALID_NO_SCIENTIFIC_DECISION",
    }

    outputs = audit.publish_audit_bundle(
        tmp_path,
        telemetry=telemetry,
        attempt_rows=[row],
        diagnosis=diagnosis,
    )
    assert all(path.exists() for path in outputs)
    assert not list(tmp_path.glob("*.tmp-*"))
    assert json.loads(outputs[0].read_text(encoding="utf-8"))[
        "formal_execution_count"
    ] == 0

    tampered_root = tmp_path / "tampered"
    with pytest.raises(ValueError, match="formal execution"):
        audit.publish_audit_bundle(
            tampered_root,
            telemetry={**telemetry, "formal_execution_count": 1},
            attempt_rows=[row],
            diagnosis=diagnosis,
        )
    assert not list(tampered_root.glob("critical_transition_*"))
    assert not list(tampered_root.glob("*.tmp-*"))


def test_real_replay_atomically_identifies_branch_memory_as_the_only_trigger() -> None:
    telemetry = json.loads(TELEMETRY_PATH.read_text(encoding="utf-8"))
    diagnosis = json.loads(DIAGNOSIS_PATH.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(ATTEMPTS_PATH.read_text(encoding="utf-8").splitlines()))

    assert telemetry["real_numerical_replay_count"] == 1
    assert telemetry["real_numerical_replay_limit"] == 1
    assert telemetry["original_failure_reproduced"] is True
    assert telemetry["execution_path"] == "full_history_control"
    assert telemetry["streaming_status"] == "not_reached_by_preregistered_stop"
    assert telemetry["observed_error_message"] == (
        "S2 transition increment failed at locked floor"
    )
    assert telemetry["formal_execution_count"] == 0
    assert telemetry["formal_artifact_count"] == 0

    assert len(rows) == telemetry["successful_candidate_count"] == 6
    assert [float(row["dt_s"]) for row in rows] == pytest.approx(
        [5.0e-9, 2.5e-9, 1.25e-9, 6.25e-10, 3.125e-10, 2.5e-10],
        rel=0.0,
        abs=1.0e-22,
    )
    assert all(row["candidate_available"] == "True" for row in rows)
    assert all(row["candidate_integrity_pass"] == "True" for row in rows)
    assert all(row["finite_state"] == "True" for row in rows)
    assert all(row["nonlinear_gate_pass"] == "True" for row in rows)
    assert all(row["four_ledgers_pass"] == "True" for row in rows)
    assert all(row["lateral_audit_pass"] == "True" for row in rows)
    assert all(row["armijo_backtracks"] == "0" for row in rows)
    assert all(row["fallback_picard_iterations"] == "0" for row in rows)

    locked = rows[-1]
    assert locked["at_locked_floor"] == "True"
    assert locked["actual_trigger_component"] == "branch_memory_b"
    assert float(locked["max_absolute_delta_b"]) == pytest.approx(
        0.3999002930674579
    )
    assert float(locked["max_absolute_delta_s"]) == pytest.approx(
        0.009896685349114254
    )
    assert (int(locked["trigger_cell_row"]), int(locked["trigger_cell_column"])) == (
        4,
        4,
    )

    assert diagnosis["disposition"] == (
        "GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION"
    )
    assert diagnosis["all_successful_candidates_integrity_pass"] is True
    assert diagnosis["actual_trigger_component"] == "branch_memory_b"
    assert diagnosis["conditional_frozen_activation_dt_max_b"] == pytest.approx(
        1.010415820055618e-11
    )
    assert diagnosis["conditional_observed_candidate_dt_max_s"] == pytest.approx(
        6.783481071445014e-10
    )
    assert diagnosis["production_floor_determined"] is False
    assert diagnosis["time_controller_changed"] is False
    assert diagnosis["phase1_scientific_result"] == "forbidden_unassessed"


def test_real_replay_hashes_and_claim_boundary_are_locked() -> None:
    assert _sha256(TELEMETRY_PATH) == (
        "d58c8aefb3db51a157dd9eb16c6856e9e211822df81559abad265950c72cfa45"
    )
    assert _sha256(ATTEMPTS_PATH) == (
        "361e804f622998883719a9103c15e697b0c8f3337b41eefda06dc673e238c1f2"
    )
    assert _sha256(DIAGNOSIS_PATH) == (
        "5e30843f0e91c36a50a36e9c19297806ecd0c84a3aa09bc683a74069fd2522a5"
    )

    report = REPORT_PATH.read_text(encoding="utf-8")
    assert "GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION" in report
    assert "Phase 1 and S2 scientific results remain" in report
    assert "`forbidden` and unassessed" in report
    assert "not a production floor" in report
    assert "Phase 2, R1" in report

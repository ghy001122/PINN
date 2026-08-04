from __future__ import annotations

from pathlib import Path

import numpy as np

from pinnpcm.evaluation.geophase_b3v2_solution_level import (
    FINITE_REJECTION_PENALTY,
    _macro_events,
    _reference_envelope,
    _run_solution_window,
    _window_sample_times,
    assess_anderson,
    assess_reference_refinement,
    field_error_metrics,
    load_contract,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import resolved_s2_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/geophase_b3v2_solution_level.yaml"


def _field_block(value: float = 0.0) -> dict[str, dict[str, float]]:
    return {
        name: {
            "rmse": value,
            "p95": value,
            "terminal_p95": value,
            "maximum": value,
        }
        for name in ("temperature_K", "conductive_state", "branch_memory")
    }


def _comparison(*, value: float = 0.0, events: list[dict] | None = None) -> dict:
    macro = [] if events is None else events
    return {
        "passed": True,
        "reference_local_pass": True,
        "candidate_local_pass": True,
        "fields": _field_block(value),
        "terminal_current_nrmse": 0.0,
        "device_voltage_nrmse": 0.0,
        "macro_events": {
            "reference": macro,
            "candidate": macro,
            "comparison": {
                "sequence_equal": True,
                "maximum_absolute_error_s": 0.0,
                "maximum_relative_error": 0.0,
            },
        },
        "total_variation": {
            name: {"reference": 1.0, "candidate": 1.0}
            for name in ("temperature_K", "conductive_state", "branch_memory")
        },
        "loops": {
            "reference_I_Vd": 0.2,
            "candidate_I_Vd": 0.2,
            "reference_s_T": 0.3,
            "candidate_s_T": 0.3,
        },
        "raw_reversal_voting": False,
    }


def test_passive_full_field_capture_does_not_change_real_short_trajectory(tmp_path: Path) -> None:
    scientific = resolved_s2_config()
    common = {
        "case_id": "B3V2-PASSIVE-RECORDER-TEST",
        "role": "test",
        "solver": "nls_v1",
        "protocol_id": "zero_drive",
        "spatial_level": 1,
        "time_divisor": 1,
        "initial_state_mode": "equilibrium",
        "final_time_s": 1.0e-8,
        "sample_interval_s": 5.0e-9,
        "maximum_wall_clock_s": 120.0,
    }
    without = _run_solution_window(
        {**common, "capture_full_fields": False}, scientific, None
    )
    with_fields = _run_solution_window(
        {**common, "capture_full_fields": True},
        scientific,
        tmp_path / "fields.npz",
    )
    assert without["local_pass"] and with_fields["local_pass"]
    assert without["trajectory_signature_sha256"] == with_fields["trajectory_signature_sha256"]
    stable_diagnostics = lambda item: {
        key: value
        for key, value in item["diagnostics"].items()
        if "wall_time" not in key and "cpu_time" not in key
    }
    assert stable_diagnostics(without) == stable_diagnostics(with_fields)
    assert without["scalar_records"] == with_fields["scalar_records"]
    assert without["event_records"] == with_fields["event_records"]
    assert without["reversal_records"] == with_fields["reversal_records"]


def test_common_grid_endpoints_and_area_weighted_metrics() -> None:
    times = _window_sample_times(1.0e-6, 1.02e-6, 5.0e-9)
    assert times[0] == 1.0e-6
    assert times[-1] == 1.02e-6
    reference = np.zeros((2, 1, 2))
    candidate = np.asarray([[[1.0, 3.0]], [[1.0, 3.0]]])
    weights = np.asarray([[1.0, 3.0]])
    metrics = field_error_metrics(reference, candidate, weights)
    assert np.isclose(metrics["rmse"], np.sqrt(7.0))
    assert metrics["p95"] == 3.0
    assert metrics["terminal_p95"] == 3.0
    bad = candidate.copy()
    bad[0, 0, 0] = np.nan
    assert field_error_metrics(reference, bad, weights)["rmse"] == FINITE_REJECTION_PENALTY


def test_reference_envelope_and_nls_fail_closed_route() -> None:
    contract = load_contract(CONFIG)
    comparisons = {
        "quiescent_9V": _comparison(
            value=1.0e-5,
            events=[{"direction": "upward", "crossing_time_s": 1.0e-6}],
        ),
        "transition_12p5V": _comparison(
            value=1.0e-5,
            events=[{"direction": "upward", "crossing_time_s": 1.0e-6}],
        ),
    }
    assessment = assess_reference_refinement(comparisons, contract)
    assert assessment["passed"]
    assert not assessment["regimes"]["quiescent_9V"]["event_gate_applicable"]
    assert assessment["regimes"]["quiescent_9V"]["macro_crossing_counts"] == {
        "reference": 1,
        "candidate": 1,
    }
    envelope = _reference_envelope(assessment, contract)
    assert envelope["regimes"]["quiescent_9V"]["field_thresholds"]["temperature_K"]["rmse"] == 0.05
    comparisons["quiescent_9V"]["fields"]["temperature_K"]["rmse"] = 0.051
    assert not assess_reference_refinement(comparisons, contract)["passed"]


def test_macro_event_tv_loop_and_anderson_routing() -> None:
    contract = load_contract(CONFIG)
    times = np.asarray([0.0, 1.0, 2.0, 3.0])
    events = _macro_events(times, np.asarray([0.4, 0.6, 0.6, 0.4]), 0.5)
    assert [item["direction"] for item in events] == ["upward", "downward"]
    reference_assessment = {
        "passed": True,
        "regimes": {
            "quiescent_9V": {"comparison": _comparison()},
            "transition_12p5V": {"comparison": _comparison(events=events)},
        },
    }
    envelope = _reference_envelope(reference_assessment, contract)
    self_comparisons = {
        "quiescent_9V": _comparison(),
        "transition_12p5V": _comparison(events=events),
    }
    cross_comparisons = {
        "quiescent_9V": _comparison(),
        "transition_12p5V": _comparison(events=events),
    }
    passed = assess_anderson(
        self_comparisons=self_comparisons,
        cross_comparisons=cross_comparisons,
        envelope=envelope,
        contract=contract,
    )
    assert passed["passed"]
    assert passed["route"] == "ANDERSON_HELDOUT_AND_COST"
    assert self_comparisons["quiescent_9V"]["raw_reversal_voting"] is False
    cross_comparisons["transition_12p5V"]["loops"]["candidate_I_Vd"] = 0.5
    failed = assess_anderson(
        self_comparisons=self_comparisons,
        cross_comparisons=cross_comparisons,
        envelope=envelope,
        contract=contract,
    )
    assert not failed["passed"]
    assert failed["route"] == "NLS_ONLY_HELDOUT_AND_COST"
    assert failed["speed_acceleration_claim"] == "forbidden"

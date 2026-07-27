from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
ADDENDUM_PATH = ROOT / "configs" / "geophase_phase1_v2_execution_addendum.yaml"
S2_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
MANIFEST_PATH = ROOT / "configs" / "geophase_phase1_v2_formal_manifest.yaml"
STAGE_PATH = ROOT / "configs" / "geo2p5d_stage.yaml"
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
READINESS_DIR = OUTPUT_DIR / "runtime_readiness"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_execution_addendum_preserves_every_locked_scientific_authority() -> None:
    cfg = _yaml(ADDENDUM_PATH)
    authority = cfg["authority_lock"]

    assert cfg["task_id"] == "Q2_PHASE1_V2_RUNTIME_AND_FORMAL_RUNNER_READINESS"
    assert cfg["schema_version"] == "geophase_phase1_v2_execution_addendum_v1"
    assert cfg["status"] == "preregistered_pending_push_no_runtime_preflight_executed"
    assert authority["formal_execution_count"] == 0
    assert authority["formal_execution_consumed"] is False
    assert authority["formal_campaign_authorized"] is False
    assert authority["formal_case_execution_in_readiness"] == "forbidden"

    for key in (
        "S2_config",
        "formal_manifest_contract",
        "expanded_manifest_csv",
        "expanded_manifest_json",
        "unchanged_source_contract",
    ):
        record = authority[key]
        assert _sha256(ROOT / record["path"]) == record["sha256"]

    s2 = _yaml(S2_PATH)
    manifest = _yaml(MANIFEST_PATH)
    stage = _yaml(STAGE_PATH)
    assert s2["execution_contract"]["formal_execution_count"] == 0
    assert manifest["formal_execution_count"] == 0
    assert manifest["total_evaluation_items"] == 63
    assert manifest["unique_execution_units"] == 60
    assert manifest["reused_evaluation_items"] == 3
    assert stage["authority"]["phase1_execution_addendum"] == str(
        ADDENDUM_PATH.relative_to(ROOT)
    ).replace("\\", "/")


def test_generated_execution_dag_maps_exactly_60_units_to_63_evaluations() -> None:
    cfg = _yaml(ADDENDUM_PATH)
    dag = json.loads(
        (READINESS_DIR / "execution_dag.json").read_text(encoding="utf-8")
    )
    rows = list(
        csv.DictReader(
            (READINESS_DIR / "execution_dag.csv")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )

    assert dag["status"] == "config_only_preregistered_not_executed"
    assert dag["formal_execution_count"] == 0
    assert dag["formal_execution_consumed"] is False
    assert dag["formal_artifacts_created"] is False
    assert dag["addendum_sha256"] == _sha256(ADDENDUM_PATH)
    assert dag["evaluation_item_count"] == len(rows) == 63
    assert dag["unique_execution_unit_count"] == 60
    assert len(dag["execution_units"]) == 60
    assert dag["reused_evaluation_count"] == 3
    assert sum(row["is_reused_evaluation"] == "true" for row in rows) == 3
    assert dag["reuse_map"] == {
        item["evaluation_id"]: item["dependency_id"]
        for item in cfg["execution_dependency_graph"]["reuse_rows"]
    }
    assert all(row["evaluation_status"] == "planned_not_executed" for row in rows)


def test_ref_pairs_and_missing_group_execution_semantics_are_closed() -> None:
    cfg = _yaml(ADDENDUM_PATH)
    groups = cfg["group_execution_semantics"]

    assert groups["REF"]["spatial_pairing"]["voting_fine_pair"] == [
        "S2T4",
        "S4T4",
    ]
    assert groups["REF"]["temporal_pairing"]["voting_fine_pair"] == [
        "S4T2",
        "S4T4",
    ]
    assert groups["TOP"]["spatial_level"] == 4
    assert groups["TOP"]["time_divisor"] == 4
    assert groups["TOP"]["final_time_s"] == pytest.approx(2.0e-5)
    assert groups["TOP"]["O20_rule"].startswith("exact_reuse_")

    dual = groups["DUAL0"]
    assert (dual["spatial_level"], dual["time_divisor"]) == (1, 1)
    assert dual["final_time_s"] == pytest.approx(2.0e-5)
    assert dual["fixtures"]["A_only_drive"]["voltage_A_V"] == pytest.approx(12.5)
    assert dual["fixtures"]["A_only_drive"]["voltage_B_V"] == pytest.approx(0.0)
    assert dual["fixtures"]["B_only_drive"]["voltage_A_V"] == pytest.approx(0.0)
    assert dual["fixtures"]["B_only_drive"]["voltage_B_V"] == pytest.approx(12.5)

    failure = groups["FAIL"]
    assert (failure["spatial_level"], failure["time_divisor"]) == (1, 1)
    assert failure["stop"].startswith("immediately_")
    assert set(failure["fixtures"]) == {
        "negative_effective_capacity",
        "negative_vertical_conductance",
        "nonfinite_newton",
        "ledger_tamper",
        "coordinate_swap",
    }
    limits = groups["LIM"]["fixtures"]
    assert limits["zero_drive_equilibrium"]["final_time_s"] == pytest.approx(2.0e-5)
    assert all(
        item["execution"] != "trajectory_required_for_locked_drift_gate"
        for name, item in limits.items()
        if name != "zero_drive_equilibrium"
    )


def test_event_source_envelope_and_claim_rules_cannot_be_averaged_away() -> None:
    cfg = _yaml(ADDENDUM_PATH)
    event = cfg["event_comparison_contract"]
    assert event["both_zero_and_protocol_does_not_require_events"] == "NA"
    assert event["one_side_missing_events"] == "FAIL"
    assert event["event_count_mismatch"] == "FAIL"
    assert event["direction_or_order_mismatch"] == "FAIL"
    assert event["time_gate_s"] == pytest.approx(5.0e-8)
    assert event["protocol_requires_events"]["transition_probe_12p5V"] is True

    envelope = cfg["source_envelope_noise_contract"]
    assert envelope["evaluated_independently_per_protocol_and_qoi"] is True
    assert envelope["cross_protocol_or_cross_qoi_averaging"] == "forbidden"
    assert envelope["post_observation_epsilon_change"] == "forbidden"
    assert envelope["qois"]["terminal_current_A"]["epsilon_q"] == pytest.approx(1.0e-12)
    assert envelope["qois"]["temperature_rise_K"]["epsilon_q"] == pytest.approx(1.0e-3)
    assert envelope["qois"]["conductive_state_change"]["epsilon_q"] == pytest.approx(1.0e-6)
    assert envelope["vote_formula"].endswith("greater_than_or_equal_to_1")


def test_streaming_preflight_cost_and_dormant_runner_boundaries_are_locked() -> None:
    cfg = _yaml(ADDENDUM_PATH)
    streaming = cfg["streaming_contract"]
    assert streaming["fixed_scalar_sample_grid"] == {
        "start_s": 0.0,
        "stop_s": 2.0e-5,
        "points": 4001,
        "interval_s": 5.0e-9,
        "solver_must_land_exactly_on_each_sample": True,
    }
    assert streaming["accepted_step_full_field_history"] == "forbidden"
    assert streaming["event_full_field_snapshots"]["maximum_snapshots"] == 16
    assert streaming["per_case_output"]["publish_with_atomic_rename"] is True

    audit = cfg["mathematically_equivalent_optimization_contract"][
        "lateral_matrix_face_audit"
    ]
    assert audit["formula_id"] == "lateral_matrix_face_parity_v1"
    assert audit["tamper_must_fail_both_paths"] is True
    assert audit["third_acceptance_criterion"] == "forbidden"

    preflight = cfg["runtime_preflight"]
    assert preflight["id_prefix"] == "PRE-"
    assert preflight["wall_clock_s_max"] == 900
    assert preflight["single_step_matrix"]["expected_samples"] == 18
    assert preflight["short_trajectory_matrix"]["expected_samples"] == 9
    assert preflight["optional_coarse_transition_trajectory"][
        "early_wall_clock_stop_alone_is_not_NO_GO"
    ] is True

    forecast = cfg["campaign_cost_forecast"]
    assert forecast["unit_count"] == 60
    assert forecast["scheduler"] == "deterministic_longest_processing_time_first"
    assert forecast["GO_gates"]["safety_margin_LPT_makespan_s_max"] == 11520
    assert forecast["GO_gates"]["unreserved_LPT_makespan_s_max"] == 14400
    assert forecast["GO_gates"]["aggregate_worker_RSS_fraction_of_launch_available_RAM_max"] == pytest.approx(0.70)
    assert forecast["GO_gates"]["disk_free_fraction_after_forecast_min"] == pytest.approx(0.20)

    runner = cfg["dormant_formal_runner"]
    assert runner["real_formal_run_ID"] == "forbidden"
    assert runner["formal_execution_unit_call"] == "forbidden"
    assert runner["states"] == [
        "PREPARED",
        "RUNNING",
        "INTERRUPTED_RESUMABLE",
        "COMPLETED_PASS",
        "COMPLETED_SCIENTIFIC_FAIL",
        "INVALID_CONTRACT",
        "BUDGET_EXHAUSTED",
    ]
    assert runner["future_real_registry_semantics"][
        "same_run_ID_resume_does_not_increment_count"
    ] is True


def test_readiness_outputs_do_not_exist_as_formal_artifacts() -> None:
    cfg = _yaml(ADDENDUM_PATH)
    assert cfg["readiness_disposition"]["allowed"] == [
        "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "NO_GO_RUNTIME",
    ]
    assert cfg["readiness_disposition"]["formal_execution_count_must_remain_zero"] is True
    assert cfg["readiness_disposition"]["formal_artifact_count_must_remain_zero"] is True
    assert not (OUTPUT_DIR / "formal_summary.json").exists()
    assert not (OUTPUT_DIR / "formal_convergence.csv").exists()

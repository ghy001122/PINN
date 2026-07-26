from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
V8_CONFIG = ROOT / "configs" / "geophase_phase1_vertical_shape_scale_v8.yaml"
OUTPUT_ROOT = ROOT / "outputs" / "tables" / "geophase_phase1" / "readiness_v8"
PREREGISTRATION_SHA = "a32375b74772da8192d390f4233ed0b15e23ae80"
IMPLEMENTATION_SHA = "dc06a52fa990d6cd4af2f1dc84537de5e52bef0e"
V8_CONFIG_SHA256 = "e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _json(name: str) -> dict:
    return json.loads((OUTPUT_ROOT / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT_ROOT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_v8_vertical_no_go_identity_and_formal_boundary_are_locked() -> None:
    summary = _json("preregistration.json")
    environment = _json("environment_manifest.json")
    assert hashlib.sha256(V8_CONFIG.read_bytes()).hexdigest() == V8_CONFIG_SHA256
    assert summary["preregistration_sha"] == PREREGISTRATION_SHA
    assert summary["repair_yaml_sha256"] == V8_CONFIG_SHA256
    assert summary["head_at_screening"] == IMPLEMENTATION_SHA
    assert summary["origin_branch_head_at_screening"] == IMPLEMENTATION_SHA
    assert summary["vertical_status"] == "NO_GO_VERTICAL_REFERENCE"
    assert summary["final_disposition"] == "NO_GO_VERTICAL_REFERENCE"
    assert summary["stop_reason"] == "fallback_depth_failure"
    assert summary["formal_execution_count"] == 0
    assert summary["formal_case_results_generated"] == 0
    assert summary["formal_campaign_executed"] is False
    assert summary["formal_case_ids_used"] == []
    assert summary["selected_production_depth_m"] is None
    assert summary["production_normalization"] is None
    assert summary["k_state_status"] == "BLOCKED_BY_NO_GO_VERTICAL_REFERENCE"
    assert summary["formal_v8_config_created"] is False
    authority_paths = {
        "formal_v6_config_sha256": ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml",
        "source_contract_sha256": ROOT / "configs" / "qiu_vo2_phase1_source_contract.yaml",
        "formal_inventory_sha256": OUTPUT_ROOT.parent / "formal_case_inventory.csv",
    }
    for key, path in authority_paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == summary[key]
    assert environment["preregistration_sha"] == summary["preregistration_sha"]
    assert environment["repair_yaml_sha256"] == summary["repair_yaml_sha256"]
    assert environment["formal_execution_count"] == 0
    assert environment["formal_case_results_generated"] == 0


def test_v8_fallback_and_raw_build_registry_follow_the_locked_stop_rule() -> None:
    summary = _json("preregistration.json")
    decisions = summary["pair_decisions"]
    assert summary["conditional_second_pair_triggered"] is True
    assert [row["pair_id"] for row in decisions] == [
        "primary_51p2um_vs_102p4um",
        "conditional_maximum_102p4um_vs_204p8um",
    ]
    for decision in decisions:
        assert decision["foundation_pass"] is True
        assert decision["depth_pass"] is False
        assert decision["failure_metric_ids"] == [
            "formal_window_pullback:bare_vo2:depth",
            "formal_window_pullback:electrode_covered_vo2:depth",
        ]
    assert summary["actual_unique_raw_build_count"] == 8
    assert summary["raw_build_registry_integrity_pass"] is True
    assert all(
        row["builder_invocation_count"] == row["request_count"] == 1
        for row in summary["raw_build_manifest"]
    )


def test_v8_candidate_rows_keep_grid_families_separate() -> None:
    rows = _csv("vertical_candidate_summary.csv")
    assert len(rows) == 24
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        assert row["raw_unnormalized"] == "True"
        assert row["voting"] == row["formal_case"] == "False"
        grouped[(row["grid_family"], row["comparison_role"])].append(row)
    mesh_rows = [
        row for key, values in grouped.items() if key[1].startswith("mesh") for row in values
    ]
    assert len(mesh_rows) == 16 and all(row["passed"] == "True" for row in mesh_rows)
    assert all(row["passed"] == "True" for row in grouped[("inherited_raw", "depth")])
    pullback_depth = grouped[("formal_window_pullback", "depth")]
    assert len(pullback_depth) == 4
    assert all(row["passed"] == "False" for row in pullback_depth)
    assert min(float(row["frequency_log_magnitude_rmse"]) for row in pullback_depth) > 0.4


def test_v8_pointwise_rows_reaggregate_without_cross_family_dilution() -> None:
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in _csv("vertical_pointwise.csv"):
        groups[(row["pair_id"], row["grid_family"], row["region"], row["comparison_role"])].append(row)
    assert len(groups) == 24
    for row in _csv("vertical_candidate_summary.csv"):
        key = (row["pair_id"], row["grid_family"], row["region"], row["comparison_role"])
        records = groups[key]
        time_rows = [record for record in records if record["axis"] == "time"]
        frequency_rows = [record for record in records if record["axis"] == "frequency"]
        assert len(time_rows) == 127 and len(frequency_rows) == 63
        for field, source in (
            ("step_response_nrmse", ("step_error", time_rows)),
            ("impulse_response_nrmse", ("impulse_error", time_rows)),
            ("frequency_log_magnitude_rmse", ("frequency_log_magnitude_error", frequency_rows)),
        ):
            values = np.asarray([float(item[source[0]]) for item in source[1]])
            assert np.sqrt(np.mean(values**2)) == pytest.approx(float(row[field]), abs=5.0e-15)


def test_v8_pullback_coordinates_and_passivity_evidence_are_exact() -> None:
    ratios = {
        row["pair_id"]: float(row["temporary_ratio_r"])
        for row in _json("preregistration.json")["pair_decisions"]
    }
    for row in _csv("vertical_pointwise.csv"):
        raw = float(row["raw_coordinate"])
        effective = float(row["effective_coordinate"])
        if row["grid_family"] == "inherited_raw":
            assert raw == effective
        elif row["axis"] == "time":
            assert raw == pytest.approx(effective / ratios[row["pair_id"]], rel=1.0e-15)
        else:
            assert raw == pytest.approx(effective * ratios[row["pair_id"]], rel=1.0e-15)

    passivity = _csv("vertical_passivity_identity.csv")
    assert len(passivity) == 32
    assert all(row["passed"] == "True" for row in passivity)
    assert max(float(row["impulse_step_derivative_relative_error"]) for row in passivity) <= 1.0e-10
    assert max(float(row["frequency_state_space_relative_error"]) for row in passivity) <= 1.0e-10


def test_v8_no_go_blocks_k_runtime_and_formal_artifacts() -> None:
    expected = {
        "environment_manifest.json",
        "k_state_multistart.csv",
        "k_state_selection.csv",
        "preregistration.json",
        "vertical_candidate_summary.csv",
        "vertical_passivity_identity.csv",
        "vertical_pointwise.csv",
    }
    assert {path.name for path in OUTPUT_ROOT.iterdir()} == expected
    for name in ("k_state_multistart.csv", "k_state_selection.csv"):
        rows = _csv(name)
        assert len(rows) == 1
        assert rows[0]["status"] == "BLOCKED_BY_NO_GO_VERTICAL_REFERENCE"
    assert not (ROOT / "configs" / "geophase_phase1_2p5d_reference_v8.yaml").exists()
    assert not any("P1-" in path.read_text(encoding="utf-8") for path in OUTPUT_ROOT.iterdir())

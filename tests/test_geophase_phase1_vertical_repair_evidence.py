from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "tables" / "geophase_phase1" / "readiness_v7"
SOURCE = ROOT / "configs" / "qiu_vo2_phase1_source_contract.yaml"
EXPECTED_SOURCE_SHA256 = (
    "857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252"
)


def _json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_vertical_repair_writes_only_the_five_bounded_artifacts() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == {
        "repair_preregistration.json",
        "vertical_reference_pointwise.csv",
        "vertical_candidate_summary.csv",
        "vertical_passivity_and_identity.csv",
        "k_state_selection.csv",
    }


def test_repair_identity_and_formal_boundary_are_fail_closed() -> None:
    evidence = _json("repair_preregistration.json")
    assert evidence["repair_protocol_commit_sha"] == (
        "d6a386a77b79f186a75fbe12c06be0666f46d067"
    )
    assert evidence["initial_preregistration_commit_sha"] == (
        "68d0577f42f7932d2a0b0ccfb5b020de1983ab9e"
    )
    assert evidence["repair_yaml_sha256"] == (
        "5ab66fb41b9af6fd605c351a86fa5928712528fcad8c9bc26cc55d18a0a92a18"
    )
    assert evidence["formal_execution_count"] == 0
    assert evidence["formal_case_results_generated"] == 0
    assert evidence["formal_campaign_executed"] is False
    assert evidence["phase1_scientific_claim"] == "forbidden_pending_formal_campaign"
    assert evidence["voting"] is False
    assert evidence["unique_raw_build_count"] == 26
    assert len(evidence["unique_raw_build_ids"]) == 26
    assert all(
        row["builder_invocation_count"] == 1
        for row in evidence["raw_build_manifest"]
    )
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED_SOURCE_SHA256
    assert evidence["source_contract_sha256"] == EXPECTED_SOURCE_SHA256
    assert evidence["formal_v6_config_sha256"] == (
        "0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1"
    )
    assert evidence["formal_inventory_sha256"] == (
        "a617284bd8890adcab105851095801b6067307e5c85acfeb9b8a84c8467be045"
    )
    assert set(evidence["screening_code_sha256"]) == {
        "runner",
        "vertical_solver",
        "vertical_evaluator",
    }


def test_maximum_pair_enforces_vertical_no_go_and_blocks_k_state() -> None:
    evidence = _json("repair_preregistration.json")
    rows = _csv("vertical_candidate_summary.csv")
    maximum = max(rows, key=lambda row: float(row["depth_m"]))
    assert float(maximum["depth_m"]) == 1.024e-4
    assert float(maximum["comparator_depth_m"]) == 2.048e-4
    assert maximum["passed_all_required_vertical_gates"] == "False"
    assert float(maximum["anchor_G_relative_error"]) <= 1.0e-12
    assert float(maximum["anchor_C_relative_error"]) <= 1.0e-12
    assert float(maximum["H4_pure_substrate_frequency_rmse"]) < 0.05
    assert float(maximum["H5_substrate_plus_overlay_frequency_rmse"]) > 0.05
    assert float(maximum["electrode_covered_vo2_depth_frequency_log_magnitude_rmse"]) > 0.05
    assert float(maximum["effective_penetration_depth_1kHz_m"]) > 2.048e-4
    assert evidence["maximum_pair_passed"] is False
    assert evidence["selected_production_depth_m"] is None
    assert evidence["vertical_status"] == "NO_GO_VERTICAL_REFERENCE"
    assert evidence["k_state_status"] == "BLOCKED_BY_VERTICAL_REFERENCE"
    assert evidence["ready_for_formal_v7_freeze"] is False
    k_rows = _csv("k_state_selection.csv")
    assert len(k_rows) == 1
    assert k_rows[0]["status"] == "blocked_by_NO_GO_VERTICAL_REFERENCE"


def test_pointwise_frequency_rows_reaggregate_to_max_pair_summary() -> None:
    rows = [
        row
        for row in _csv("vertical_reference_pointwise.csv")
        if row["depth_m"] == "0.0001024"
        and row["region"] == "electrode_covered_vo2"
        and row["comparison_id"] == "depth"
        and row["axis"] == "frequency"
    ]
    assert rows
    contribution = sum(
        float(row["frequency_squared_rmse_contribution"]) for row in rows
    )
    reaggregated = contribution**0.5
    maximum = max(
        _csv("vertical_candidate_summary.csv"), key=lambda row: float(row["depth_m"])
    )
    expected = float(
        maximum["electrode_covered_vo2_depth_frequency_log_magnitude_rmse"]
    )
    assert abs(reaggregated - expected) <= 1.0e-14
    assert all(row["voting"] == "False" and row["formal_case"] == "False" for row in rows)


def test_registered_v6_reproduction_has_pointwise_complex_diagnostics() -> None:
    evidence = _json("repair_preregistration.json")
    rows = [
        row
        for row in _csv("vertical_reference_pointwise.csv")
        if row["comparison_id"] == "v6_warning_reproduction"
        and row["region"] == "electrode_covered_vo2"
        and row["axis"] == "frequency"
    ]
    assert rows
    reaggregated = sum(
        float(row["frequency_squared_rmse_contribution"]) for row in rows
    ) ** 0.5
    assert abs(reaggregated - evidence["v6_warning_reproduced_value"]) <= 1.0e-14
    for key in (
        "candidate_frequency_real_W_m2K",
        "candidate_frequency_imag_W_m2K",
        "candidate_frequency_magnitude_W_m2K",
        "candidate_frequency_phase_rad",
        "reference_frequency_real_W_m2K",
        "reference_frequency_imag_W_m2K",
        "reference_frequency_magnitude_W_m2K",
        "reference_frequency_phase_rad",
        "absolute_frequency_log_magnitude_error",
    ):
        assert all(row[key] != "" for row in rows)
    assert evidence["v6_warning_relative_error"] <= 1.0e-10


def test_every_vertical_passivity_and_identity_row_passes() -> None:
    rows = _csv("vertical_passivity_and_identity.csv")
    assert len(rows) == 72
    assert {row["passed"] for row in rows} == {"True"}


def test_all_bounded_csv_rows_are_nonvoting_and_nonformal() -> None:
    for name in (
        "vertical_reference_pointwise.csv",
        "vertical_candidate_summary.csv",
        "vertical_passivity_and_identity.csv",
        "k_state_selection.csv",
    ):
        rows = _csv(name)
        assert rows
        assert {row["voting"] for row in rows} == {"False"}
        assert {row["formal_case"] for row in rows} == {"False"}

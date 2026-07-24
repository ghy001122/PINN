from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "outputs" / "tables" / "m44_qiu_heterogeneous_3d_thermal_summary.json"
RECEIPT = ROOT / "outputs" / "tables" / "m44_execution_receipt.json"
CASES = ROOT / "outputs" / "tables" / "m44_qiu_heterogeneous_3d_thermal_cases.csv"
ATTESTATION = ROOT / "outputs" / "tables" / "m43_postcommit_attestation.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_m44_terminal_result_is_fail_closed_and_complete() -> None:
    summary = _load(SUMMARY)
    assert summary["status"] == "failed_but_informative"
    assert summary["decision"] == "M44_STOP_REAL_GEOMETRY_UPGRADE"
    assert summary["gate_total_count"] == 22
    assert summary["gate_pass_count"] == 19
    assert set(summary["failed_gates"]) == {
        "vo2_mean_temperature_pair_change",
        "zth_mesh_pair_change",
        "zth_time_pair_change",
    }
    assert summary["forward_accounting"]["unique_thermal_forwards"] == 31
    assert summary["forward_accounting"]["formal_runner_invocations"] == 1
    assert summary["protected_evidence_unchanged"] is True
    assert summary["protected_evidence_mtime_unchanged"] is True
    assert all(value in (0, False) for value in summary["prohibited_run_accounting"].values())


def test_m44_key_gate_values_and_boundaries_are_locked() -> None:
    summary = _load(SUMMARY)
    gates = summary["gates"]
    assert gates["homogeneous_transient_recovery_error"]["value"] == pytest.approx(
        0.013232849723381906
    )
    assert gates["layered_1d_transient_reference_error"]["value"] == pytest.approx(
        0.000969844493325245
    )
    assert gates["zth_domain_pair_change"]["value"] == pytest.approx(
        2.0478190828374415e-7
    )
    assert gates["zth_mesh_pair_change"]["value"] == pytest.approx(
        0.06324641077402296
    )
    assert gates["zth_time_pair_change"]["value"] == pytest.approx(
        0.0544910227619362
    )
    assert summary["source_envelope"]["value"] == pytest.approx(
        0.03357903168816547
    )
    assert summary["diagnostics"]["maximum_heterogeneity_departure"] == pytest.approx(
        3.2496439005408013
    )
    for intervals in summary["diagnostics"]["xz_quantitative_forbidden_intervals"].values():
        assert intervals == [
            {"start_time_s": 1.2857142857142857e-8, "end_time_s": 5.22e-6}
        ]


def test_m44_receipt_cases_and_m43_identity_are_consistent() -> None:
    receipt = _load(RECEIPT)
    assert receipt["status"] == "completed"
    assert receipt["formal_runner_invocations"] == 1
    assert receipt["forward_invocations_attempted"] == 31
    assert receipt["forward_invocations_completed"] == 31
    assert len(receipt["case_ids"]) == len(set(receipt["case_ids"])) == 31
    assert len(receipt["canonical_case_sha256"]) == 31
    assert receipt["m43_postcommit_attestation_identity"]["passed"] is True
    assert receipt["m43_postcommit_attestation_identity"]["artifact_count"] == 7

    with CASES.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 31
    assert {row["case_id"] for row in rows} == set(receipt["case_ids"])

    attestation = _load(ATTESTATION)
    for relative, expected in attestation["artifact_sha256"].items():
        assert _sha256(ROOT / relative) == expected


def test_m44_artifacts_preserve_component_only_claim_boundary() -> None:
    summary = _load(SUMMARY)
    assert summary["upstream_blockers"] == {
        "latent_heat_status": "outside_validated_scope_unresolved",
        "m42_source_local_resistance_error": 1.330233207545514,
        "resolved_by_m44": False,
    }
    forbidden = " ".join(summary["forbidden_claims"])
    assert "unique Qiu device thermal kernel" in forbidden
    assert "inverse identification or PINN success" in forbidden
    assert (ROOT / "outputs" / "figures" / "m44" / "m44_qiu_heterogeneous_3d_thermal_bridge.png").is_file()
    report = (ROOT / "docs" / "codex_reports" / "m44_qiu_heterogeneous_3d_thermal_bridge.md").read_text(
        encoding="utf-8"
    )
    assert "no M44 repair round" in report
    assert "stopped before receipt creation" in report
    assert "threshold-only" in report and "non-voting" in report
    assert "does not independently establish its time-step convergence" in report

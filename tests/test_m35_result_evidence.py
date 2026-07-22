"""Integrity tests for generated M35 evidence; absent future stages are skipped."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.external_data.vo2_zhang import (
    require_fit_lock_for_sealed_access,
)
from pinnpcm.audit.evidence_identity import assert_evidence_lock


CONFIG_PATH = Path("configs/m35_public_multivoltage_fit.yaml")
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
PREREG_PATH = Path(CONFIG["outputs"]["preregistration"])
M34A_PATH = Path(CONFIG["outputs"]["m34a_summary"])
SUMMARY_PATH = Path(CONFIG["outputs"]["fit_summary"])
LOCK_PATH = Path(CONFIG["outputs"]["fit_lock"])


@pytest.mark.skipif(not PREREG_PATH.exists(), reason="M35 preregistration not generated yet")
def test_preregistration_hashes_and_sealed_boundary_are_valid() -> None:
    payload = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m35_public_multivoltage_preregistration_v1"
    assert payload["all_preflight_checks_pass"] is True
    assert payload["fit_authorized_after_preregistration_commit"] is True
    assert payload["sealed_13v_access"] is False
    assert all(payload["preflight_checks"].values())
    provenance = Path(payload["provenance_manifest"])
    assert_evidence_lock(provenance, payload["provenance_manifest_sha256"])
    for path, expected in payload["locked_files"].items():
        definition = path == ".gitignore" or path.startswith(
            ("configs/", "scripts/", "src/", "tests/")
        )
        assert_evidence_lock(
            path,
            expected,
            allow_historical_revision=definition,
        )


@pytest.mark.skipif(not M34A_PATH.exists(), reason="M34-A amendment not generated yet")
def test_m34a_result_cannot_change_training_authorization() -> None:
    payload = json.loads(M34A_PATH.read_text(encoding="utf-8"))
    assert payload["post_hoc_diagnostic_amendment"] is True
    assert payload["training_authorized"] is False
    assert payload["sealed_13v_access"] is False
    assert payload["summary"]["scientific_vote"] is False
    assert payload["summary"]["direction_count"] == 32


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M35 D-FIT evidence not generated yet")
def test_fit_result_obeys_fail_closed_outputs_and_lock_semantics() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["fit_data_voltages_V"] == [9.0, 11.0, 15.0, 17.0]
    assert summary["sealed_13v_access"] is False
    assert summary["pinn_training_performed"] is False
    assert summary["solver_convergence"]["historical_d0a_gate_passed"] is False
    if not summary["solver_convergence"]["all_operational_gates_pass"]:
        assert summary["fit_executed"] is False
        assert summary["fit_lock_created"] is False
        assert not LOCK_PATH.exists()
        return
    if not summary["jacobian_audit"]["all_coordinate_systems_stable"]:
        assert summary["fit_executed"] is False
        assert summary["fit_lock_created"] is False
        assert not LOCK_PATH.exists()
        return

    assert summary["fit_executed"] is True
    assert summary["all_start_result_count"] == 80
    assert summary["all_trace_metric_count"] == 320
    starts_path = Path(CONFIG["outputs"]["all_multistarts"])
    metrics_path = Path(CONFIG["outputs"]["lovo_metrics"])
    with starts_path.open(encoding="utf-8", newline="") as handle:
        starts = list(csv.DictReader(handle))
    with metrics_path.open(encoding="utf-8", newline="") as handle:
        metrics = list(csv.DictReader(handle))
    assert len(starts) == 80
    assert len(metrics) == 320
    assert {float(row["voltage_V"]) for row in metrics} == {9.0, 11.0, 15.0, 17.0}
    assert LOCK_PATH.exists()
    lock = require_fit_lock_for_sealed_access(LOCK_PATH)
    assert lock["sealed_13v_access"] is False
    assert lock["future_13v_requires_new_explicit_user_authorization"] is True
    assert lock["fit_data_voltages_V"] == [9.0, 11.0, 15.0, 17.0]

"""Integrity tests for M36 preregistration and generated evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.audit.evidence_identity import assert_evidence_lock


CONFIG_PATH = Path("configs/m36_event_resolved_orbit_convergence.yaml")
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
PREREG_PATH = Path(CONFIG["outputs"]["preregistration"])
SUMMARY_PATH = Path(CONFIG["outputs"]["summary"])
LOCK_PATH = Path(CONFIG["outputs"]["fit_lock"])


@pytest.mark.skipif(not PREREG_PATH.exists(), reason="M36 preregistration not generated yet")
def test_m36_preregistration_is_hash_locked_and_sealed() -> None:
    payload = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m36_event_resolved_orbit_preregistration_v1"
    assert payload["all_preflight_checks_pass"] is True
    assert payload["solver_authorized_after_preregistration_commit"] is True
    assert payload["sealed_13v_access"] is False
    assert payload["pinn_training_performed"] is False
    assert all(payload["preflight_checks"].values())
    for path, expected in payload["locked_files"].items():
        assert_evidence_lock(
            path,
            expected,
            allow_historical_revision=path == ".gitignore"
            or path.startswith(("configs/", "scripts/", "src/", "tests/")),
        )


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M36 evidence not generated yet")
def test_m36_result_is_complete_and_conditionally_fail_closed() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "m36_event_resolved_orbit_evidence_v1"
    assert summary["open_public_voltages_V"] == [9.0, 11.0, 15.0, 17.0]
    assert summary["sealed_13v_access"] is False
    assert summary["pinn_training_performed"] is False
    assert summary["m35_artifacts_rerun_or_overwritten"] is False
    assert summary["historical_d0a_failure_preserved"] is True
    assert set(summary["voltage_results"]) == {"9", "11", "15", "17"}
    metrics_path = Path(CONFIG["outputs"]["convergence_metrics"])
    events_path = Path(CONFIG["outputs"]["event_table"])
    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with events_path.open(encoding="utf-8", newline="") as handle:
        event_rows = list(csv.DictReader(handle))
    assert len(rows) == 20
    assert {float(row["voltage_V"]) for row in rows} == {9.0, 11.0, 15.0, 17.0}
    assert event_rows
    if not summary["m36_primary_gates_pass"]:
        assert summary["jacobian_executed"] is False
        assert summary["fit_executed"] is False
        assert summary["fit_lock_created"] is False
        assert not LOCK_PATH.exists()
        return
    assert summary["jacobian_executed"] is True
    if not summary["jacobian_audit"]["conditional_fit_authorized"]:
        assert summary["fit_executed"] is False
        assert not LOCK_PATH.exists()
        return
    assert summary["fit_executed"] is True
    assert summary["all_start_result_count"] == 128
    assert summary["all_lovo_metric_count"] == 512
    if summary["fit_result"]["fit_lock_gate_passed"]:
        assert summary["fit_lock_created"] is True
        assert LOCK_PATH.exists()
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        assert lock["sealed_13v_access"] is False
        assert lock["future_13v_requires_new_explicit_user_authorization"] is True
    else:
        assert summary["fit_lock_created"] is False
        assert not LOCK_PATH.exists()


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M36 evidence not generated yet")
def test_voltage_classifications_use_only_preregistered_categories() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    allowed = {
        "normalization_artifact_resolved_by_absolute_noise_floor_metrics",
        "phase_shadowing_failure_not_orbit_failure",
        "event_semantic_nonconvergence",
        "true_numerical_nonconvergence",
        "normalization_and_orbit_metrics_converged",
    }
    assert {
        row["classification"] for row in summary["voltage_results"].values()
    } <= allowed

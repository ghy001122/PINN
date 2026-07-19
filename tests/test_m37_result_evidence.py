"""Integrity and fail-closed tests for generated M37 evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.external_data.vo2_zhang import compute_sha256


CONFIG_PATH = Path("configs/m37_continuous_event_observability.yaml")
CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
PREREG_PATH = Path(CONFIG["outputs"]["preregistration"])
AUDIT_PATH = Path(CONFIG["outputs"]["semantic_audit"])
SUMMARY_PATH = Path(CONFIG["outputs"]["jacobian_summary"])
SPECTRA_PATH = Path(CONFIG["outputs"]["jacobian_spectra"])


@pytest.mark.skipif(not PREREG_PATH.exists(), reason="M37 preregistration not generated")
def test_m37_preregistration_is_complete_hash_locked_and_sealed() -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    assert prereg["schema_version"] == "m37_continuous_event_observability_preregistration_v1"
    assert prereg["all_preflight_checks_pass"] is True
    assert prereg["solver_authorized_after_preregistration_commit"] is True
    assert prereg["fit_authorized"] is False
    assert prereg["fit_lock_authorized"] is False
    assert prereg["pinn_training_authorized"] is False
    assert prereg["sealed_13v_access"] is False
    assert all(prereg["preflight_checks"].values())
    for path, expected in prereg["locked_files"].items():
        assert compute_sha256(Path(path)) == expected


@pytest.mark.skipif(not AUDIT_PATH.exists(), reason="M37 semantic audit not generated")
def test_m36_semantic_audit_supersedes_wording_but_not_vote_or_artifacts() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["broad_primary_failure_classifier_detected"] is True
    assert audit["source_m36_outputs_modified"] is False
    assert audit["source_m36_failure_vote_unchanged"] is True
    assert audit["m36_primary_gates_pass"] is False
    assert audit["voltage_audit"]["11"]["strict_pairwise_decrease"] is False
    for voltage in ("11", "15", "17"):
        record = audit["voltage_audit"][voltage]
        assert record["m36_primary_gate_passed"] is False
        assert record["observed_convergence_trend"] is True
        assert record["superseding_semantic_wording"].startswith(
            "finite_step_accuracy_gate_failed"
        )
    assert compute_sha256(Path(CONFIG["historical_inputs"]["m36_summary"])) == audit[
        "source_summary_sha256"
    ]
    assert compute_sha256(Path(CONFIG["historical_inputs"]["m36_metrics"])) == audit[
        "source_metrics_sha256"
    ]


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37 result not generated")
def test_m37_result_obeys_gates_and_cannot_authorize_fit_or_13v() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "m37_continuous_event_observability_evidence_v1"
    assert summary["sealed_13v_access"] is False
    assert summary["fit_executed"] is False
    assert summary["fit_lock_created"] is False
    assert summary["pinn_training_performed"] is False
    assert summary["m35_or_m36_full_workflow_rerun"] is False
    assert summary["m36_failure_vote_unchanged"] is True
    assert summary["m38_authorized"] is summary["m37_all_gates_pass"]
    if summary["m38_authorized"]:
        assert summary["claim_status"] == "qualified_supported"
        assert summary["groups"]["joint"]["threshold_rank"] == 2
        assert summary["joint_condition_gate_passed"] is True
        assert summary["complementarity_gate_passed"] is True
    else:
        assert summary["claim_status"] == "failed_but_informative"
        assert summary["next_single_action"] == "Q2_MANUSCRIPT_EVIDENCE_COMPRESSION"


@pytest.mark.skipif(not SUMMARY_PATH.exists(), reason="M37 result not generated")
def test_spectra_and_analytic_transform_are_complete_and_non_novelty_claiming() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    with SPECTRA_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert summary["analytic_quotient_transform"]["resimulation_performed"] is False
    assert summary["analytic_quotient_transform"]["rank_increase_claim"] == "forbidden"
    if summary["groups"]:
        assert {row["observation_group"] for row in rows} >= {
            "static_only",
            "oscillatory_only",
            "joint",
        }
        assert summary["forward_evaluations"]["total"] <= int(
            CONFIG["solvers"]["maximum_total_forward_evaluations"]
        )

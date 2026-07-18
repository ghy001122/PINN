"""Result-lock tests for the completed zero-training M34 audit."""

from __future__ import annotations

import csv
import json
from pathlib import Path


BASE_SNAPSHOT = "84bc5c5db2f5233b70bf97756734272c3eae36ca"
PREREG_COMMIT = "ee83d73a16a219e02a19a5d7f6419dea3d224bb6"


def _json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_m34_fails_closed_without_corrected_training() -> None:
    result = _json("outputs/tables/m34_contract_audit_summary.json")
    assert result["base_snapshot"] == BASE_SNAPSHOT
    assert result["preregistration_commit"] == PREREG_COMMIT
    assert result["status"] == "failed_but_informative"
    assert result["corrected_training_authorized"] is False
    assert result["authorization_disposition"] == "M33-v1 contract closed; no corrected run authorized"
    assert result["sealed_13v_access"] is False
    assert not Path("outputs/tables/m34_corrected_training_history.json").exists()
    assert not Path("outputs/tables/m34_corrected_final_summary.json").exists()
    assert not Path("outputs/tables/m34_corrected_v3r_m33_comparison.csv").exists()
    assert not Path("outputs/checkpoints/m34_corrected_mixed_flux").exists()


def test_m34_alm_classification_and_signed_dual_counterexample_are_locked() -> None:
    result = _json("outputs/tables/m34_contract_audit_summary.json")
    alm = result["alm"]
    assert alm["faithful_signed_vector_alm"] is False
    assert alm["m33_classification"] == "adaptive_group_norm_exact_penalty_with_nonnegative_scalar_accumulators"
    assert alm["unconditional_penalty_growth"] is True
    assert alm["multiplier_cap"] == 100.0
    assert alm["gradient_clip_norm"] == 100.0
    signed = [row for row in alm["toy"] if row["method"] == "signed_vector_alm"]
    group_rms = [row for row in alm["toy"] if row["method"] == "group_rms_scalar_multiplier"]
    assert max(row["constraint_abs"] for row in signed) <= 1.0e-6
    assert max(row["dual_abs_error"] for row in signed) <= 1.0e-6
    negative = next(row for row in group_rms if row["case_id"] == "negative_dual")
    assert negative["reported_multiplier"] > 0.0
    assert negative["true_signed_dual"] < 0.0
    assert negative["dual_abs_error"] > 3.9


def test_gradient_parity_failure_cannot_be_hidden_by_pass_count() -> None:
    result = _json("outputs/tables/m34_contract_audit_summary.json")
    parity = result["gradient_geometry"]["coordinate_parity"]
    assert parity["candidate_count"] == 48
    assert parity["nonzero_count"] == 44
    assert parity["all_nonzero_pass"] is False
    assert parity["maximum_nonzero_relative_error"] > 1.0e-4
    with Path("outputs/tables/m34_gradient_geometry.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    coordinates = [row for row in rows if row["row_type"] == "coordinate_parity" and row["nonzero"] == "True"]
    assert len(coordinates) == 44
    assert sum(row["pass"] == "True" for row in coordinates) == 30
    assert sum(row["pass"] == "False" for row in coordinates) == 14
    failures = {row["module"] for row in coordinates if row["pass"] == "False"}
    assert failures == {"state_head", "defect_flux_head"}
    assert result["authorization_conditions"]["at_least_20_nonzero_gradient_directions_pass_parity"] is False
    assert result["corrected_preflight"]["all_pass"] is False


def test_ledger_reconciliation_preserves_historical_failure() -> None:
    result = _json("outputs/tables/m34_contract_audit_summary.json")
    ledger = result["ledger_reconciliation"]
    assert ledger["historical_gate_preserved"] is True
    assert ledger["maximum_training_independent_implementation_difference"] <= 2.0e-14
    votes = ledger["root_cause_votes"]
    assert votes == {
        "normalization_mismatch": True,
        "low_activity_denominator_pathology": False,
        "state_flux_or_local_residual_incompatibility": True,
        "time_sampling_primary": True,
        "sign_unit_boundary_implementation_error": False,
    }
    coarse = ledger["grids"]["32"]
    fine = ledger["grids"]["400"]
    assert fine["energy"]["fixed_scale_rms"] < coarse["energy"]["fixed_scale_rms"]
    assert fine["defect"]["fixed_scale_rms"] < coarse["defect"]["fixed_scale_rms"]
    assert fine["energy"]["prefix_fixed_scale_max"] > 1.0
    assert fine["defect"]["prefix_fixed_scale_max"] > 0.02
    assert abs(fine["energy"]["prefix_fixed_scale_max"] - fine["energy"]["local_residual_prefix_fixed_scale_max"]) < 2.0e-7
    assert abs(fine["defect"]["prefix_fixed_scale_max"] - fine["defect"]["local_residual_prefix_fixed_scale_max"]) < 1.0e-7


def test_representability_smoke_has_no_scientific_vote() -> None:
    result = _json("outputs/tables/m34_contract_audit_summary.json")
    assert result["architecture_classification"] == (
        "fixed-grid neural temporal trajectory with control-volume physics; not a continuous (x,t,mu) PINN"
    )
    assert result["generalization_forbidden"] == ["cross_grid", "cross_geometry", "cross_material", "cross_waveform"]
    smoke = result["representability_smoke"]
    assert smoke["steps"] == 200
    assert smoke["diagnostic_only"] is True
    assert smoke["scientific_vote"] is False
    assert smoke["hidden_field_labels_used"] == ["c_v", "T", "m"]
    assert all(smoke["after_field_nrmse95"][name] < smoke["before_field_nrmse95"][name] for name in ("T", "c_v", "m"))

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_gamma_sub_evidence_lock import ALLOWED_STATUSES, build_gamma_sub_evidence_lock


def test_gamma_sub_evidence_lock_builds_without_touching_tracked_outputs(tmp_path: Path) -> None:
    summary = build_gamma_sub_evidence_lock(
        output_json=tmp_path / "summary.json",
        lock_md=tmp_path / "lock.md",
        claim_matrix_md=tmp_path / "claims.md",
        figure_list_md=tmp_path / "figures.md",
    )
    assert summary["all_declared_sources_exist"] is True
    assert summary["lock_commit_sha"] == "d1121e16fa5015a297da468e3e6f0504b9e97d17"
    assert summary["status_vocabulary_valid"] is True
    assert summary["all_main_positive_claims_allowed"] is True
    assert summary["external_quantitative_validation_completed"] is False
    assert summary["figure_5_decision"]["primary_figure_5_cases"] == 720
    assert summary["figure_5_decision"]["primary_figure_5_success_rate"] == 1.0
    assert summary["figure_5_decision"]["stress_figure_ready"] is False
    assert summary["figure_5_decision"]["primary_source"].endswith("gamma_sub_calibrated_sequential_protocol_validation_summary.json")

    stored = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    statuses = {item["status"] for item in stored["claims"]}
    assert statuses <= ALLOWED_STATUSES
    assert "qualified_supported as implementation" not in (tmp_path / "claims.md").read_text(encoding="utf-8")
    assert "whether_ready_as_main_figure = false" in (tmp_path / "lock.md").read_text(encoding="utf-8")
    assert "Figure 5" in (tmp_path / "figures.md").read_text(encoding="utf-8")


def test_gamma_sub_evidence_lock_has_complete_mainline_chain(tmp_path: Path) -> None:
    summary = build_gamma_sub_evidence_lock(
        output_json=tmp_path / "summary.json",
        lock_md=tmp_path / "lock.md",
        claim_matrix_md=tmp_path / "claims.md",
        figure_list_md=tmp_path / "figures.md",
    )
    assert summary["main_claim_count"] == 5
    assert summary["boundary_claim_count"] == 5
    assert summary["main_figure_count"] == 6
    ids = {item["id"] for item in summary["claims"]}
    assert {
        "C1_identifiability_boundary",
        "C2_constrained_gamma_sub",
        "C3_calibration_gate",
        "C4_conditional_robustness",
        "C5_protocol_after_calibration",
        "B1_external_validation",
        "B2_p1_neural_solver",
        "B3_p2_active_inverse",
        "B4_p3_segmented_forward",
        "B5_p4_algorithms",
    } == ids

def test_gamma_sub_evidence_lock_maps_direct_recovery_visual(tmp_path: Path) -> None:
    summary = build_gamma_sub_evidence_lock(
        output_json=tmp_path / "summary.json",
        lock_md=tmp_path / "lock.md",
        claim_matrix_md=tmp_path / "claims.md",
        figure_list_md=tmp_path / "figures.md",
    )
    figures = {item["id"]: item for item in summary["figures"]}
    assert figures["Figure 1"]["title"] == "Sparse-port identifiability boundary"
    assert figures["Figure 2"]["title"] == "Constrained gamma_sub recovery and T_sw confounding"
    assert "outputs/tables/gamma_sub_continuous_refinement_cases.csv" in figures["Figure 2"]["evidence_paths"]
    assert "directly compares true and continuously estimated off-grid gamma_sub" in figures["Figure 2"]["caption"]

"""Evidence-lock tests for the completed N0-R bounded repair."""

from __future__ import annotations

import json
from pathlib import Path


def test_failed_repair_does_not_upgrade_n0_or_authorize_anchor() -> None:
    path = Path("outputs/tables/full_pinn_n0_repair_data_free_seed_20260715_v2.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload["result"]
    assert result["status"] == "gate_fail"
    assert result["gates"]["all_pass"] is False
    assert result["gates"]["checks"]["current_conservation"] is False
    assert result["gates"]["checks"]["energy_conservation"] is False
    assert not Path("outputs/tables/full_pinn_n0_repair_sparse_anchor_seed_20260715_v2.json").exists()
    assert not Path("outputs/tables/full_pinn_n0_repair_full_seeds_v2.json").exists()


def test_preregistration_hashes_bind_config_points_and_scientific_files() -> None:
    lock = json.loads(Path("outputs/tables/full_pinn_n0_repair_v2_preregistration.json").read_text(encoding="utf-8"))
    assert len(lock["config_sha256"]) == 64
    assert len(lock["fixed_points"]["content_sha256"]) == 64
    assert len(lock["locked_file_sha256"]) >= 15
    assert lock["status"] == "locked_before_repair_training"


def test_compatibility_and_repair_claim_boundaries_are_explicit() -> None:
    compatibility = json.loads(Path("outputs/tables/n0_teacher_equation_compatibility_v1.json").read_text(encoding="utf-8"))
    assert compatibility["v1_electrical_orientation_mismatch"] is True
    assert compatibility["frozen_discrete_conservation_pass"] is True
    report = Path("docs/codex_reports/n0_full_pinn_bounded_repair_v2_report.md")
    if report.exists():
        text = report.read_text(encoding="utf-8")
        assert "N0 remains `failed_but_informative`" in text
        assert "Do not enter solver-first SC-LOS" in text

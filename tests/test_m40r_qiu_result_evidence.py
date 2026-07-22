"""Regression locks for the consumed M40R formal result."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.audit.evidence_identity import assert_evidence_lock

ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_m40r_formal_result_fails_closed_without_rewriting_m40() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/m40r_qiu_e0_repair.yaml").read_text(encoding="utf-8")
    )
    prereg = _json(config["outputs"]["preregistration"])
    summary = _json(config["outputs"]["summary"])

    assert summary["formal_execution_attempt"] == 1
    assert summary["preregistration_commit"] == "b935631c13ca288961e1bf72ed37782418693e54"
    assert summary["old_m40_byte_for_byte_unchanged"] is True
    assert summary["frozen_gt_unchanged"] is True
    assert summary["original_numeric_e0_all_pass"] is True
    assert all(summary["original_gate_results"].values())
    assert summary["active_transient_all_pass"] is False
    assert summary["m41_conservative_reduction_authorized"] is False
    assert summary["return_to_manuscript_fallback"] is True
    assert summary["status"] == "failed_but_informative"
    assert summary["gate_values"]["main_qoi_mesh_change"] <= 0.01
    assert summary["gate_values"]["peak_field_mesh_change"] <= 0.02
    assert summary["gate_values"]["nominal_duration_Rload_C_multiple"] < 3.0
    assert summary["gate_values"]["nominal_Tmax_K"] > 360.0
    assert summary["gate_values"]["transient_current_nrmse"] > 0.02

    for name, expected in prereg["old_m40_protected_hashes"].items():
        assert_evidence_lock(
            name,
            expected,
            root=ROOT,
            allow_historical_revision=name.startswith(
                ("configs/", "scripts/", "src/", "tests/")
            ),
        )


def test_m40r_required_outputs_and_active_stop_semantics_exist() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/m40r_qiu_e0_repair.yaml").read_text(encoding="utf-8")
    )
    for key in (
        "mesh_convergence",
        "active_transient",
        "summary",
        "mesh_figure",
        "transient_figure",
        "report",
    ):
        assert (ROOT / config["outputs"][key]).is_file()

    active = _json(config["outputs"]["active_transient"])
    fine = active["fine"]["metrics"]
    assert fine["termination_reason"] == "source_R_T_domain_exceeded"
    assert fine["target_duration_reached"] is False
    assert fine["duration_Rload_C_multiple"] == pytest.approx(
        0.09206838794607335
    )
    assert fine["Tmax_K"] == pytest.approx(360.2249397936913)
    assert fine["switching_window_exercised"] is True
    assert fine["nominal_smooth_max_energy_imbalance"] <= 1.0e-4
    assert fine["nominal_switching_max_energy_imbalance"] <= 1.0e-3

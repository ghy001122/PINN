from __future__ import annotations

import math
from pathlib import Path

from pinnpcm.experiments.claim_resolution_2d_field import PROTOCOLS, run_claim_resolution_2d_field
import scripts.audit_claim_resolution_2d_field as audit


def test_claim_resolution_2d_field_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_ERROR", tmp_path / "error.png")
    monkeypatch.setattr(audit, "FIG_RANK", tmp_path / "rank.png")
    rows, summary = run_claim_resolution_2d_field(noise_values=[0.0], seeds=[2026])
    assert len(rows) == len(PROTOCOLS)
    assert summary["uses_holdout_target"] is True
    assert summary["no_target_leakage"] is True
    assert summary["terminal_only_status"] == "forbidden"
    assert summary["terminal_only_full_field_status"] == "forbidden"
    assert set(summary["basis_mode_results"]) == set(PROTOCOLS)
    for value in summary["median_field_error_by_protocol"].values():
        assert math.isfinite(float(value))
    full = audit.run_audit()
    assert full["field_recovery_status"] in {"qualified_supported", "failed_but_informative", "forbidden"}
    assert (tmp_path / "summary.json").exists()

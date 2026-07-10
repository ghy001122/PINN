from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_phase_aware_stl_repair as audit


def test_phase_aware_stl_repair_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_GAIN", tmp_path / "gain.png")
    summary = audit.run_phase_aware_stl_repair()
    assert summary["full_stl_pinn_reproduction_status"] == "forbidden"
    assert summary["phase_aware_stl_status"] in {"qualified_supported", "failed_but_informative"}
    for value in summary["transfer_gain_by_algorithm"].values():
        assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()

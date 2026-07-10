from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_multilayer_sandwich_low_dim_inverse as audit


def test_multilayer_sandwich_low_dim_inverse_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    summary = audit.run_low_dim_inverse()
    assert summary["low_dim_sandwich_inverse_status"] in {"qualified_supported", "failed_but_informative"}
    assert "Rth_pcm_sub" in summary["parameters"]
    for value in summary["median_parameter_error_by_protocol"].values():
        assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()

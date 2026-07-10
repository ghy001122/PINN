from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_terminal_only_active_protocol_rescue as audit


def test_terminal_only_active_protocol_rescue_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_GAIN", tmp_path / "gain.png")
    summary = audit.run_terminal_only_active_protocol_rescue()
    assert summary["single_trace_arbitrary_full_field_status"] == "forbidden"
    assert summary["parameter_recovery_status"] in {"qualified_supported", "failed_but_informative"}
    for value in summary["median_parameter_error_by_protocol"].values():
        assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()

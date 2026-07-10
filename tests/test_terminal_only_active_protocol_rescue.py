from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_terminal_only_active_protocol_rescue as audit


def test_terminal_only_active_protocol_rescue_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_GAIN", tmp_path / "gain.png")
    summary = audit.run_terminal_only_active_protocol_rescue()
    assert summary["is_simulator_backed"] is True
    assert summary["legacy_feature_matrix_only"] is False
    assert summary["single_trace_arbitrary_full_field_status"] == "forbidden"
    assert summary["parameter_recovery_status"] in {"qualified_supported", "failed_but_informative"}
    for group_name in ["parameter_error_by_protocol", "condition_number_by_protocol", "sensitivity_norm_by_protocol"]:
        for value in summary[group_name].values():
            assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()

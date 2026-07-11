from __future__ import annotations

from pathlib import Path

import scripts.audit_oasis_2d_field_resolution as audit


def test_oasis_2d_field_resolution_blocks_without_electrode_bc(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "_p0_summary", lambda: {"P0_gate_passed": True})
    summary = audit.run_oasis_2d_field_resolution()
    assert summary["P0_gate_passed"] is True
    assert summary["actual_electrode_bc_multi_terminal_supported"] is False
    assert summary["uses_sigma_half_means"] is False
    assert summary["status"] == "blocked"
    assert summary["blocked_reason"] == "blocked_until_actual_electrode_BC_multi_terminal_solver_is_implemented"
    assert (tmp_path / "summary.json").exists()


def test_oasis_2d_field_resolution_blocks_if_p0_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "_p0_summary", lambda: {"P0_gate_passed": False})
    summary = audit.run_oasis_2d_field_resolution()
    assert summary["status"] == "blocked"
    assert summary["blocked_reason"] == "blocked_until_conservative_P0_gate_passes"

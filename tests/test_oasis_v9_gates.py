from __future__ import annotations

from pathlib import Path

import scripts.audit_oasis_2d_field_resolution_v2 as field
import scripts.audit_phase_activated_algorithms_v9 as alg


def test_oasis_2d_v2_blocks_without_electrode_solver(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(field, "SUMMARY_JSON", tmp_path / "field.json")
    monkeypatch.setattr(field, "_read", lambda path: {"P0_activation_gate_passed": True} if "phase" in str(path) else {"P1_gate_passed": True})
    summary = field.run_oasis_2d_field_resolution_v2()
    assert summary["status"] == "blocked"
    assert summary["uses_sigma_half_means"] is False
    assert summary["actual_electrode_bc_multi_terminal_yz_solver_supported"] is False


def test_phase_activated_algorithms_v9_blocks_unimplemented_claims(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(alg, "SUMMARY_JSON", tmp_path / "alg.json")
    summary = alg.run_phase_activated_algorithms_v9()
    assert summary["true_pareto_dominance_required"] is True
    assert summary["STL_status"] == "blocked"
    assert summary["Fourier_FSPS_status"] == "blocked"
    assert summary["canonical_seiler_reproduction_run"] is False

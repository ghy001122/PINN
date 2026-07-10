from __future__ import annotations

import math
from pathlib import Path

import yaml

from pinnpcm.physics.multilayer_sandwich import simulate_multilayer_case, summarize_cases
import scripts.audit_multilayer_sandwich_device as audit


def test_multilayer_single_case_finite() -> None:
    result = simulate_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", 0.1, "short_pulse", 2026, {"ny": 8, "nt": 6})
    assert result["finite_result"] is True
    assert math.isfinite(result["interface_bc_residual"])
    assert math.isfinite(result["current_continuity_error"])
    assert result["current_continuity_error"] <= 1.0e-10
    summary = summarize_cases([result])
    assert summary["finite_rate"] == 1.0


def test_multilayer_audit_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_TEMP", tmp_path / "temp.png")
    monkeypatch.setattr(audit, "FIG_J", tmp_path / "j.png")
    monkeypatch.setattr(audit, "FIG_BC", tmp_path / "bc.png")
    monkeypatch.setattr(audit, "FIG_ABL", tmp_path / "abl.png")
    cfg = {"claim_gate": {"interface_bc_residual_threshold": 0.35, "current_continuity_threshold": 0.05}, "quick_profile": {"structures": ["pcm_only", "full_stack_with_SnSe_barrier"], "geometry": ["uniform_crossbar"], "transition_width": [0.2], "pulse": ["short_pulse"], "seeds": [2026]}, "numerics": {"ny": 8, "nt": 6}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    summary = audit.run_multilayer_sandwich_device(path)
    assert summary["finite_rate"] == 1.0
    assert summary["boundary_aware_multilayer_forward_status"] in {"qualified_supported", "failed_but_informative"}
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()

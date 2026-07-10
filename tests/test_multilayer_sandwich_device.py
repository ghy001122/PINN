from __future__ import annotations

import math
from pathlib import Path

import yaml

from pinnpcm.physics.multilayer_sandwich import simulate_multilayer_case, summarize_cases
import scripts.audit_multilayer_sandwich_device as audit


def test_multilayer_single_case_finite_and_residuals_computed() -> None:
    result = simulate_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", 0.1, "short_pulse", 2026, {"ny": 8, "nt": 6})
    assert result["finite_result"] is True
    for key in [
        "interface_bc_residual",
        "current_continuity_error",
        "normal_current_mismatch",
        "potential_jump_residual",
        "temperature_jump_residual",
        "heat_flux_mismatch",
        "substrate_robin_residual",
        "joule_input_energy",
        "thermal_storage_energy",
        "sink_loss_energy",
        "boundary_loss_energy",
        "energy_balance_error",
    ]:
        assert math.isfinite(float(result[key]))
    assert result["current_continuity_error"] <= 1.0e-10
    summary = summarize_cases([result])
    assert summary["finite_rate"] == 1.0
    assert summary["residuals_are_computed_not_stubbed"] is True
    assert "energy_balance_gate_passed" in summary
    if not summary["energy_balance_gate_passed"]:
        assert summary["boundary_aware_multilayer_forward_status"] == "failed_but_informative"


def test_multilayer_audit_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_TEMP", tmp_path / "temp.png")
    monkeypatch.setattr(audit, "FIG_J", tmp_path / "j.png")
    monkeypatch.setattr(audit, "FIG_BC", tmp_path / "bc.png")
    monkeypatch.setattr(audit, "FIG_ABL", tmp_path / "abl.png")
    cfg = {"claim_gate": {"interface_bc_residual_threshold": 0.35, "current_continuity_threshold": 0.05, "energy_balance_threshold": 0.35}, "quick_profile": {"structures": ["pcm_only", "full_stack_with_SnSe_barrier"], "geometry": ["uniform_crossbar"], "transition_width": [0.2], "pulse": ["short_pulse"], "seeds": [2026]}, "numerics": {"ny": 8, "nt": 6}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    summary = audit.run_multilayer_sandwich_device(path)
    assert summary["finite_rate"] == 1.0
    assert summary["residuals_are_computed_not_stubbed"] is True
    assert summary["boundary_aware_multilayer_forward_status"] in {"qualified_supported", "failed_but_informative"}
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()

from __future__ import annotations

import math
from pathlib import Path

from pinnpcm.physics.multilayer_sandwich import manufactured_energy_conservation_test, simulate_conservative_multilayer_case, zero_source_conservation_test
import scripts.audit_conservative_multilayer_forward as audit


def test_conservative_case_has_no_artificial_shortcuts() -> None:
    result = simulate_conservative_multilayer_case(
        "full_stack_with_thermal_boundary_resistance",
        "localized_filament",
        0.08,
        "short_pulse",
        2026,
        {"ny": 8, "nt": 8, "material_family": "vo2"},
    )
    assert result["finite_result"] is True
    assert result["used_artificial_lateral_factor"] is False
    assert result["used_temperature_clip"] is False
    assert result["used_global_sink"] is False
    assert result["adaptive_substeps_enabled"] is True
    assert result["semi_implicit_boundary_enabled"] is True
    for key in ["potential_jump_residual", "normal_current_mismatch", "temperature_jump_residual", "heat_flux_mismatch", "substrate_robin_residual", "energy_balance_error"]:
        assert math.isfinite(float(result[key]))


def test_conservation_checks_pass() -> None:
    zero = zero_source_conservation_test()
    manufactured = manufactured_energy_conservation_test()
    assert zero["passed"] is True
    assert manufactured["passed"] is True


def test_conservative_audit_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "_case_rows", lambda: [simulate_conservative_multilayer_case("pcm_plus_electrodes", "uniform_crossbar", 0.2, "short_pulse", 2026, {"ny": 6, "nt": 6, "material_family": "generic"})])
    summary = audit.run_conservative_multilayer_forward()
    assert summary["residuals_are_computed_not_stubbed"] is True
    assert summary["per_interface_Rc_Rth"] is True
    assert summary["all_conservation_tests_passed"] is True
    assert summary["P0_gate_passed"] in {True, False}
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()

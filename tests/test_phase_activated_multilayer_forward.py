from __future__ import annotations

from pathlib import Path

from pinnpcm.physics.multilayer_sandwich import phase_activated_manufactured_solution_test, phase_activated_refinement_test, simulate_phase_activated_multilayer_case, summarize_phase_activated_cases
import scripts.audit_phase_activated_multilayer_forward as audit


def test_phase_activated_case_uses_realistic_v9_switching_priors() -> None:
    result = simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "vo2", "activation_triangle", 2026, audit.VO2_CFG)
    assert result["finite_result"] is True
    assert result["used_coupled_yz_lateral_conduction"] is True
    assert result["used_snse_low_k_high_sigma_prior"] is True
    assert result["used_material_family_specific_kernel"] is True
    assert result["used_independent_interface_map"] is True
    assert result["shared_pcm_neighbor_parameter"] is False
    assert result["snse_prior"]["k_w_mk"] < 1.0
    assert result["snse_prior"]["sigma_s_m"] >= 1.0e3


def test_phase_activated_summary_gate_and_independent_checks() -> None:
    rows = [
        simulate_phase_activated_multilayer_case("pcm_plus_electrodes", "localized_filament", "vo2", "activation_triangle", 2026, audit.VO2_CFG),
        simulate_phase_activated_multilayer_case("pcm_plus_electrodes", "localized_filament", "nbo2", "activation_triangle", 2026, audit.NBO2_CFG),
    ]
    summary = summarize_phase_activated_cases(rows)
    assert summary["vo2_activation_gate_passed"] is True
    assert summary["nbo2_activation_gate_passed"] is True
    assert phase_activated_manufactured_solution_test()["passed"] is True
    assert phase_activated_refinement_test()["passed"] is True


def test_phase_activated_forward_script_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "_case_rows", lambda: [
        simulate_phase_activated_multilayer_case("pcm_plus_electrodes", "localized_filament", "vo2", "activation_triangle", 2026, audit.VO2_CFG),
        simulate_phase_activated_multilayer_case("pcm_plus_electrodes", "localized_filament", "nbo2", "activation_triangle", 2026, audit.NBO2_CFG),
    ])
    summary = audit.run_phase_activated_multilayer_forward()
    assert summary["P0_activation_gate_passed"] is True
    assert summary["analytic_manufactured_solution"]["passed"] is True
    assert summary["mesh_time_refinement"]["passed"] is True
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()

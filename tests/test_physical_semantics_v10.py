from __future__ import annotations

import numpy as np

from pinnpcm.physics.multilayer_sandwich import (
    extract_switching_thresholds,
    simulate_phase_activated_multilayer_case,
    vo2_benchmark_profile,
)


def test_electrical_and_thermal_domains_are_separate() -> None:
    result = simulate_phase_activated_multilayer_case(
        "full_stack_with_SnSe_barrier", "localized_filament", "nbo2", "activation_triangle", 1,
        {"ny": 5, "nt": 8, "V_peak": 2.1, "nbo2_effective_fraction_ablation": False},
    )
    assert result["substrate_is_thermal_only"] is True
    assert result["electrical_domain_layers"][-1] == "BE"
    assert result["thermal_domain_layers"][-1] == "substrate"
    assert np.all(result["sigma"][:, -1] == 0.0)
    assert np.ptp(result["state_m"]) == 0.0


def test_vo2_profiles_are_not_mixed() -> None:
    normalized = vo2_benchmark_profile("normalized_activated")
    anchored = vo2_benchmark_profile("literature_anchored")
    assert normalized["vo2_Tc_up_K"] != anchored["vo2_Tc_up_K"]
    assert "not a quantitatively calibrated" in normalized["claim_boundary"]
    assert "literature-shape prior" in anchored["claim_boundary"]


def test_zero_thresholds_never_pass() -> None:
    result = extract_switching_thresholds(np.zeros(8), np.ones(8))
    assert result["Vth"] == 0.0
    assert result["Vhold"] == 0.0
    assert result["valid"] is False


def test_rc_protocol_uses_constant_source_and_dynamic_device_voltage() -> None:
    result = simulate_phase_activated_multilayer_case(
        "pcm_plus_electrodes", "localized_filament", "vo2", "rc_oscillator", 2,
        {"ny": 5, "nt": 10, "V_bias": 8.0, "R_load_ohm": 8e3, "C_circuit_F": 145e-12},
    )
    assert result["used_autonomous_rc_circuit"] is True
    assert np.ptp(result["voltage_app"]) == 0.0
    assert np.ptp(result["voltage_device"]) > 0.0

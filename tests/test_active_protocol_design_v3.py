from __future__ import annotations

import scripts.audit_active_protocol_design_v3 as audit


def test_protocol_candidates_include_real_rc_parameters() -> None:
    candidates = audit._candidate_protocols("vo2")
    oscillator = next(row for row in candidates if row["pulse"] == "rc_oscillator")
    assert oscillator["C_circuit_F"] > 0.0
    assert oscillator["R_load_ohm"] > 0.0


def test_noisy_target_is_reinverted() -> None:
    protocol = audit._candidate_protocols("nbo2")[0]
    clean = audit._linearized_inverse("nbo2", protocol, 0.0, 4000)
    noisy = audit._linearized_inverse("nbo2", protocol, 0.05, 4001)
    assert clean["re_inverted_noisy_target"] is True
    assert noisy["re_inverted_noisy_target"] is True
    assert clean["estimate"] != noisy["estimate"]

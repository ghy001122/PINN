from __future__ import annotations

from pathlib import Path

import numpy as np

import scripts.audit_active_protocol_identifiability as audit


def test_terminal_feature_vector_is_finite() -> None:
    result = {"current": np.array([0.0, 1.0e-6, -0.5e-6]), "conductance": np.array([1.0e-5, 2.0e-5, 1.5e-5]), "time": np.array([0.0, 0.5, 1.0])}
    features = audit._terminal_features(result)
    assert features.shape == (8,)
    assert np.isfinite(features).all()


def test_active_protocol_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "ACTIVE_SUMMARY_JSON", tmp_path / "active.json")
    monkeypatch.setattr(audit, "SEQUENTIAL_SUMMARY_JSON", tmp_path / "seq.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "_protocol_runs", lambda protocol: [("short_pulse", {"V_short": 0.22, "nt": 6}, "pcm_plus_electrodes", "uniform_crossbar")])
    active, seq = audit.run_active_protocol_identifiability()
    assert active["is_simulator_backed"] is True
    assert active["uses_only_terminal_features"] is True
    assert "best_d_optimal_protocol" in active
    assert seq["uses_only_terminal_features"] is True
    assert seq["sequential_inverse_status"] in {"qualified_supported", "failed_but_informative"}
    if not active["all_parameters_pass_best_protocol_gate"]:
        assert seq["sequential_result"]["blocked_by_identifiability_gate"] is True
    assert (tmp_path / "active.json").exists()
    assert (tmp_path / "seq.json").exists()

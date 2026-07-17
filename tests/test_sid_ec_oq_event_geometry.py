from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pinnpcm.identifiability import (
    derivative_convergence,
    event_window_indices,
    sid_decision,
)


def test_event_windows_are_deterministic_nonempty_and_physically_routed() -> None:
    t = np.linspace(0.0, 1.0, 80)
    phase = np.tile((1.0 / (1.0 + np.exp(-(t - 0.5) / 0.025)))[:, None], (1, 5))
    current = np.tanh((t - 0.5) / 0.02)
    temperature = np.tile((300.0 + 12.0 * np.sin(np.pi * t))[:, None], (1, 5))
    kwargs = dict(
        switch_threshold_fraction=0.5,
        cooling_temperature_rate_fraction=-0.1,
        minimum_points=8,
        fallback_half_width_points=6,
    )
    first = event_window_indices(t, current, phase, temperature, **kwargs)
    second = event_window_indices(t, current, phase, temperature, **kwargs)
    assert set(first) == {"pre_switch", "switch", "post_switch", "cooling_recovery"}
    assert all(values.size >= 8 for values in first.values())
    assert all(np.array_equal(first[name], second[name]) for name in first)
    assert np.median(first["pre_switch"]) < np.median(first["switch"]) < np.median(first["post_switch"])


def test_h_over_two_and_richardson_gate_passes_for_second_order_error() -> None:
    exact = np.arange(20, dtype=float).reshape(5, 4) / 7.0 + 0.1
    error = np.ones_like(exact) * 1.0e-3
    audit = derivative_convergence(exact + error, exact + error / 4.0, maximum_relative_difference=0.05)
    assert audit["pass"] is True
    assert np.allclose(audit["richardson_jacobian"], exact)


def test_sid_and_ec_oq_decisions_are_independent_and_fail_closed() -> None:
    gates = {
        "ec_oq_angle_bootstrap_lower_deg_min": 15.0,
        "ec_oq_rank_change_bootstrap_consistency_min": 0.8,
        "switch_information_ratio_min": 2.0,
        "switch_training_condition_ratio_min": 10.0,
        "direction_stability_min_protocols": 3,
    }
    metrics = {
        "derivative_pass": True,
        "angle_ci_lower_deg": 20.0,
        "rank_change_consistency": 0.2,
        "switch_information_ratio": 2.5,
        "training_geometry_available": True,
        "switch_training_condition_ratio": 2.0,
        "stable_protocol_count": 3,
        "neighborhood_direction_stable": True,
    }
    result = sid_decision(metrics, gates)
    assert result["ec_oq_retained"] is True
    assert result["sid_retained"] is False
    assert result["disposition"] == "delete_sid_retain_ec_oq_candidate"
    metrics["derivative_pass"] = False
    failed = sid_decision(metrics, gates)
    assert failed["ec_oq_retained"] is False
    assert failed["sid_retained"] is False


def test_recorded_discovery_result_deletes_both_labels() -> None:
    payload = json.loads(Path("outputs/tables/sid_ec_oq_summary.json").read_text(encoding="utf-8"))
    assert payload["decision"]["claim_status"] == "failed_but_informative"
    assert payload["decision"]["sid_retained"] is False
    assert payload["decision"]["ec_oq_retained"] is False
    assert payload["derivative_audit"]["passing_cases"] == 3
    assert payload["derivative_audit"]["total_cases"] == 9

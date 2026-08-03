from __future__ import annotations

import numpy as np

from pinnpcm.evaluation.geophase_controller_relevance_b3 import (
    _event_comparison,
    _trajectory_nrmse,
    _window_sample_times,
    _run_window,
    compare_window_payloads,
)
from pinnpcm.evaluation.geophase_controller_relevance_final_rescue import _state_payload
from pinnpcm.evaluation.geophase_s0_direct_physics import resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import initial_s2_state


def test_b3_window_grid_preserves_arbitrary_start_and_exact_stop() -> None:
    values = _window_sample_times(1.706015625e-5, 1.706015625e-5 + 1.2e-8, 5.0e-9)
    assert values[0] == 1.706015625e-5
    assert values[-1] == 1.706015625e-5 + 1.2e-8
    assert np.all(np.diff(values) > 0.0)
    assert len(values) == 4


def test_b3_nrmse_uses_frozen_reference_rms_and_floor() -> None:
    reference = np.asarray([0.0, 2.0])
    candidate = np.asarray([0.0, 2.2])
    expected = np.sqrt((0.2**2) / 2.0) / np.sqrt((2.0**2) / 2.0)
    assert np.isclose(_trajectory_nrmse(candidate, reference, 1.0e-12), expected)
    assert _trajectory_nrmse(np.asarray([1.0]), np.asarray([0.0]), 0.5) == 2.0


def test_b3_event_comparison_is_fail_closed_on_topology() -> None:
    reference = [{"direction": "upward", "crossing_time_s": 1.0e-6}]
    equal = _event_comparison(
        [{"direction": "upward", "crossing_time_s": 1.01e-6}], reference
    )
    assert equal["sequence_equal"] is True
    assert np.isclose(equal["maximum_absolute_error_s"], 1.0e-8)
    changed = _event_comparison(
        [{"direction": "downward", "crossing_time_s": 1.0e-6}], reference
    )
    assert changed["sequence_equal"] is False
    assert changed["maximum_absolute_error_s"] >= 1.0e299


def _payload(*, solver: str, current: list[float], growth: int = 1) -> dict:
    records = [
        {"time_s": 0.0, "terminal_current_A": 0.0, "device_voltage_V": 0.0},
        {"time_s": 5.0e-9, "terminal_current_A": current[0], "device_voltage_V": 1.0},
        {"time_s": 1.0e-8, "terminal_current_A": current[1], "device_voltage_V": 2.0},
    ]
    return {
        "case_id": solver,
        "local_pass": True,
        "scalar_records": records,
        "event_records": [{"direction": "upward", "crossing_time_s": 7.5e-9}],
        "reversal_records": [{"direction": "heating_to_cooling"}],
        "diagnostics": {"growth_events": growth, "fallback_steps": 0},
    }


def test_b3_comparison_requires_metrics_topology_and_zero_fallback() -> None:
    contract = {
        "terminal_current_absolute_floor_A": 1.0e-12,
        "device_voltage_absolute_floor_V": 1.0e-12,
        "correctness": {
            "terminal_current_nrmse_max": 0.01,
            "device_voltage_nrmse_max": 0.005,
            "event_absolute_error_s_max": 5.0e-8,
            "event_relative_error_max": 0.01,
            "exact_fallback_steps_required": 0,
        },
    }
    reference = _payload(solver="nls", current=[1.0, 2.0])
    candidate = _payload(solver="aa", current=[1.0, 2.0])
    result = compare_window_payloads(reference, candidate, contract)
    assert result["passed"] is True
    candidate["diagnostics"]["fallback_steps"] = 1
    assert compare_window_payloads(reference, candidate, contract)["passed"] is False


def test_b3_real_payload_zero_drive_smoke() -> None:
    scientific = resolved_s2_config()
    grid = build_geophase_grid(scientific, spatial_level=1)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    initial = initial_s2_state(grid, closure, fields, scientific)
    payload = _run_window(
        {
            "case_id": "B3-REAL-ZERO-SMOKE",
            "role": "test_smoke",
            "solver": "anderson_v1",
            "protocol_id": "zero_drive",
            "time_divisor": 1,
            "initial_state": _state_payload(initial),
            "final_time_s": 1.0e-11,
            "sample_interval_s": 5.0e-12,
            "maximum_wall_clock_s": 30.0,
            "spatial_level": 1,
        },
        scientific,
    )
    assert payload["local_pass"] is True
    assert payload["sample_count"] == 3
    assert payload["diagnostics"]["fallback_steps"] == 0

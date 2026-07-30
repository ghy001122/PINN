from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from pinnpcm.solvers import geophase_phase1_v2_source_corrected_performance as adapter
from pinnpcm.solvers.geophase_phase1_v2_implicit import PERFORMANCE_TIMING_SEMANTICS


pytestmark = [pytest.mark.phase1, pytest.mark.current]


_SHA = "a" * 64


def _plan(**overrides) -> dict:
    row = {
        "plan_index": 0,
        "sample_id": "PRE-C3-L1-high_conductive-base",
        "sample_kind": "single_interval",
        "spatial_level": 1,
        "state_id": "high_conductive",
        "interval_class": "base",
        "protocol": "high_bias_lock_15p8V",
        "protocol_V_scale_V": 15.8,
        "input_sha256": _SHA,
    }
    row.update(overrides)
    return row


def test_adapter_exposes_only_the_locked_readiness_hook_surface() -> None:
    hooks = adapter.task_adapter(
        mode="readiness_hooks",
        payload={
            "equivalence": {"candidate_identity_sha256": _SHA},
            "worker_rss": {"measured_peak_worker_RSS_bytes": 1024},
        },
    )

    assert set(hooks) == {
        "run_c1",
        "run_c2",
        "measure_launch_environment",
        "c3_worker_entrypoint",
        "run_dormant_runner",
        "build_forecast",
    }
    assert hooks["c3_worker_entrypoint"] == (
        "pinnpcm.solvers.geophase_phase1_v2_source_corrected_performance:"
        "run_c3_sample"
    )
    assert all(
        callable(hooks[name])
        for name in set(hooks) - {"c3_worker_entrypoint"}
    )


def test_equivalence_is_deliberately_not_wired_and_rss_requires_candidate() -> None:
    with pytest.raises(RuntimeError, match="not wired"):
        adapter.task_adapter(mode="equivalence", payload={})
    with pytest.raises(ValueError, match="candidate_identity_sha256"):
        adapter.task_adapter(mode="measure_worker_rss", payload={})


def test_resolved_contract_uses_only_zero_12p5_and_source_corrected_15p8() -> None:
    config = adapter._resolved_config()
    protocols = config["formal_protocols"]["protocols"]
    scales = config["reference_solver"]["active_time_controller"]["voltage_scale"]

    assert "high_bias_15V" not in protocols
    assert "high_bias_lock_15p8V" in protocols
    assert adapter._PROTOCOL_BY_STATE == {
        "equilibrium": "zero_drive",
        "legal_critical": "transition_probe_12p5V",
        "high_conductive": "high_bias_lock_15p8V",
    }
    assert {
        key: float(scales["protocol_V_scale_V"][key])
        for key in adapter._PROTOCOL_SCALE_V
    } == adapter._PROTOCOL_SCALE_V
    assert config["execution_contract"]["formal_execution_count"] == 0


def test_high_conductive_state_is_exactly_380K_b1_and_s_equilibrium() -> None:
    grid = SimpleNamespace(shape=(2, 3))
    fields = SimpleNamespace(ambient_temperature_K=325.0)

    class Closure:
        T_c_up_K = 336.4

        @staticmethod
        def equilibrium_state(temperature, branch):
            assert np.all(branch == 1.0)
            return 0.25 + 0.001 * np.asarray(temperature)

    state = adapter._deterministic_state(
        "high_conductive", grid=grid, fields=fields, closure=Closure()
    )

    assert np.array_equal(state.temperature_K, np.full((2, 3), 380.0))
    assert np.array_equal(state.branch_memory, np.ones((2, 3)))
    assert np.array_equal(state.conductive_state, np.full((2, 3), 0.63))
    assert state.device_voltage_V == 0.0
    assert state.time_s == 0.0


def test_c3_plan_rejects_historical_15V_alias_and_formal_ids() -> None:
    with pytest.raises(ValueError, match="state/protocol"):
        adapter._validate_plan(_plan(protocol="high_bias_15V"))
    with pytest.raises(ValueError, match="non-formal PRE"):
        adapter._validate_plan(_plan(sample_id="P1V2-REF-S1T1-high_bias_lock_15p8V"))


def test_c3_worker_returns_one_payload_without_a_parity_double_run(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_interval(plan):
        calls.append(dict(plan))
        return {
            "sample_id": plan["sample_id"],
            "sample_kind": "single_interval",
            "spatial_level": 1,
            "state_id": "high_conductive",
            "status": "pass",
            "timing_semantics": PERFORMANCE_TIMING_SEMANTICS,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }

    monkeypatch.setattr(adapter, "_single_interval_payload", fake_interval)
    result = adapter.run_c3_sample(_plan())

    assert result["status"] == "PASS"
    assert len(calls) == 1
    assert result["payload"]["timing_semantics"] == PERFORMANCE_TIMING_SEMANTICS
    assert result["payload"]["formal_execution_count"] == 0
    assert result["payload"]["formal_artifact_count"] == 0


def test_forecast_consumes_validated_worker_payload_and_c2_reuse(monkeypatch) -> None:
    adapter._LAUNCH_ENVIRONMENT = {
        "physical_core_count": 8,
        "launch_available_RAM_bytes": 10_000,
        "available_ram_bytes_at_launch": 10_000,
        "disk_total_bytes": 100_000,
        "disk_free_bytes_at_launch": 90_000,
    }
    adapter._READINESS_CONTEXT.clear()
    adapter._READINESS_CONTEXT.update(
        {
            "candidate_identity_sha256": _SHA,
            "worker_rss": {"measured_peak_worker_RSS_bytes": 1_000},
        }
    )
    observed: dict = {}

    def fake_forecast(**kwargs):
        observed.update(kwargs)
        return [
            {"execution_unit_id": "X", "safety_wall_clock_s": 1.0}
        ], {
            "predicted_p95_makespan_s": 1.0,
            "hard_makespan_s": 0.8,
            "disk_free_fraction_after_forecast": 0.8,
        }

    monkeypatch.setattr(adapter, "build_campaign_cost_forecast", fake_forecast)
    worker_payload = {
        "sample_kind": "single_interval",
        "spatial_level": 1,
        "state_id": "equilibrium",
        "timing_semantics": PERFORMANCE_TIMING_SEMANTICS,
        "peak_rss_bytes": 900,
    }
    c2_row = {
        "sample_kind": "short_trajectory",
        "spatial_level": 1,
        "state_id": "legal_critical",
        "status": "pass",
    }
    result = adapter._build_forecast(
        ({"plan_index": 0, "payload": worker_payload},),
        {"forecast_sample_row": c2_row},
        worker_count=4,
    )

    assert observed["sample_rows"] == [
        {"plan_index": 0, **worker_payload},
        c2_row,
    ]
    assert observed["environment"]["physical_core_count"] == 4
    assert result["predicted_hard_makespan_s"] == 0.8
    assert result["RSS_gate_pass"] is True
    assert result["disk_gate_pass"] is True
    assert result["formal_execution_count"] == 0
    assert result["formal_artifact_count"] == 0

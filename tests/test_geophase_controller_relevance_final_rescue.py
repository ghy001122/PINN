from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pinnpcm.evaluation import geophase_controller_relevance_final_rescue as rescue
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config


CONFIG = ROOT / "configs/geophase_controller_relevance_final_rescue.yaml"


def test_contract_locks_authority_limits_routes_and_corrected_r1_step() -> None:
    contract = rescue.load_contract(CONFIG)
    assert contract["identity"]["base_main_commit"] == (
        "1c9758ef151299a4694b4edcc81dd48feec704ba"
    )
    assert contract["identity"]["scientific_vote"] is False
    assert contract["identity"]["formal_execution_count"] == 0
    assert contract["scope"]["d0_rerun_or_completion"] == "forbidden"
    assert contract["scope"]["exact_condensed_v1_modification"] == "forbidden"
    assert contract["scope"]["controller_v2_modification"] == "forbidden"
    assert contract["r1"]["central_difference_step"] == (
        "eps_to_one_third_times_max_1_and_temperature_inf"
    )
    assert contract["r2"]["map"]["maximum_map_evaluations_per_root"] == 80
    assert contract["r2"]["map"]["sufficient_decrease_c1"] == pytest.approx(
        1.0e-4
    )
    assert contract["r2"]["map"]["all_actual_map_calls_count"] is True
    assert contract["timebox"]["started_utc"] == "2026-08-03T17:14:35Z"
    assert contract["timebox"]["r0_r1_r2_cumulative_wall_s_max"] == 86400

    scientific = resolved_s2_config()
    assert rescue.resolve_and_validate_limits(scientific, contract) == {
        "T1_standard": {
            "time_divisor": 1,
            "Hmax_s": 1.0e-8,
            "Hmin_s": 9.765625e-12,
        },
        "T4_strict_div4": {
            "time_divisor": 4,
            "Hmax_s": 2.5e-9,
            "Hmin_s": 2.44140625e-12,
        },
    }


def test_frozen_inputs_are_byte_identical_and_production_controller_is_called() -> None:
    contract = rescue.load_contract(CONFIG)
    verified = rescue.verify_frozen_inputs(contract)
    assert len(verified) == len(contract["frozen_inputs"])
    paths = {item["path"] for item in verified}
    assert "src/pinnpcm/solvers/geophase_exact_condensed.py" in paths
    assert "src/pinnpcm/solvers/geophase_exact_condensed_controller_v2.py" in paths

    source = inspect.getsource(rescue.run_r0_case)
    assert "simulate_exact_condensed_protocol_v2(" in source
    assert "attempt_exact_condensed_embedded_interval(" not in source
    assert "final_time_s=float(state.time_s + maximum_H)" in source
    assert "maximum_accepted_steps=1" in source
    assert "forced_times_s=()" in source


def test_canonical_publication_handles_numpy_and_rejects_nonfinite(
    tmp_path: Path,
) -> None:
    payload = {
        "flag": np.bool_(True),
        "count": np.int64(3),
        "value": np.float64(0.25),
        "array": np.asarray([1.0, 2.0]),
        "path": Path("cases/result.json"),
    }
    path = tmp_path / "result.json"
    rescue._atomic_json(path, payload)
    published = json.loads(path.read_text(encoding="utf-8"))
    assert published == {
        "array": [1.0, 2.0],
        "count": 3,
        "flag": True,
        "path": "cases/result.json",
        "value": 0.25,
    }
    with pytest.raises(ValueError, match="nonfinite"):
        rescue._canonical_bytes({"bad": np.float64(np.nan)})


def test_thread_contract_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = rescue.load_contract(CONFIG)
    required = contract["runtime"]["required_thread_environment"]
    for name, value in required.items():
        monkeypatch.setenv(name, str(value))
    assert rescue.validate_thread_environment(contract) == {
        str(name): str(value) for name, value in required.items()
    }
    first = next(iter(required))
    monkeypatch.setenv(first, "2")
    with pytest.raises(ValueError, match="single-thread"):
        rescue.validate_thread_environment(contract)


def test_terminal_routing_distinguishes_root_from_nonsolver_failure() -> None:
    integrity = SimpleNamespace(overall_pass=True)
    root_failure = SimpleNamespace(
        diagnostics=SimpleNamespace(
            at_outer_floor=True,
            aggregate=integrity,
            full_step=integrity,
            first_half_step=None,
            second_half_step=None,
            embedded_error=None,
            accepted=False,
        ),
        root_telemetry=(SimpleNamespace(status="FAIL"),),
    )
    assert rescue._classify_terminal_failure(root_failure) == (
        "R0_TERMINAL_NONLINEAR_ROOT_FAILURE",
        True,
    )

    failed_integrity = SimpleNamespace(overall_pass=False)
    nonsolver_failure = SimpleNamespace(
        diagnostics=SimpleNamespace(
            at_outer_floor=True,
            aggregate=failed_integrity,
            full_step=integrity,
            first_half_step=integrity,
            second_half_step=integrity,
            embedded_error=None,
            accepted=False,
        ),
        root_telemetry=(SimpleNamespace(status="PASS"),) * 3,
    )
    assert rescue._classify_terminal_failure(nonsolver_failure) == (
        "R0_VALID_NONSOLVER_INTEGRITY_FAILURE",
        False,
    )

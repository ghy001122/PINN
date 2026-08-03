from __future__ import annotations

import inspect
import json
from pathlib import Path
from time import perf_counter
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
    assert contract["identity"]["r0_run_id"].endswith("-V2")
    assert contract["identity"]["r0_invocation_count"] == 2
    assert contract["identity"]["r0_invalid_invocation_count"] == 1
    assert contract["identity"]["runner_repair_count"] == 1
    assert contract["scope"]["d0_rerun_or_completion"] == "forbidden"
    assert contract["scope"]["exact_condensed_v1_modification"] == "forbidden"
    assert contract["scope"]["controller_v2_modification"] == "forbidden"
    assert contract["r1"]["central_difference_step"] == (
        "eps_to_one_third_times_max_1_and_temperature_inf"
    )
    assert contract["r1"]["parent_r0_summary_sha256"] == (
        "e37eb472b6bd6ce4ddcb0d54b3ef17c1bcf7110cf1b39878062ab18d7c839b05"
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

    signature = inspect.signature(rescue.run_r0_case)
    assert signature.parameters["simulate_protocol"].default is (
        rescue.simulate_exact_condensed_protocol_v2
    )
    source = inspect.getsource(rescue.run_r0_case)
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


def test_attempt_csv_atomic_publication_keeps_destination_path(tmp_path: Path) -> None:
    destination = tmp_path / "attempts.csv"
    cases = [
        {
            "case": {"case_id": "writer-regression"},
            "attempts": [
                {
                    "rejection_index": 0,
                    "attempted_outer_interval_s": 1.0e-9,
                    "at_outer_floor": False,
                    "accepted": False,
                    "embedded_error": None,
                    "wall_time_s": 0.1,
                    "paths": [
                        {
                            "path": "full_step",
                            "root": None,
                            "candidate": None,
                        }
                    ],
                }
            ],
        }
    ]
    rescue._write_attempts_csv(destination, cases)
    assert destination.is_file()
    assert not destination.with_suffix(".csv.tmp").exists()
    assert "writer-regression" in destination.read_text(encoding="utf-8")


def test_r1_central_difference_recovers_contracting_relaxed_linear_map() -> None:
    initial = np.asarray([[4.0, -2.0]], dtype=float)
    metrics = rescue.audit_unscaled_fixed_point_contraction(
        lambda temperature: 0.5 * temperature,
        initial,
        relaxation=0.5,
        iteration_count=8,
        gates={
            "last_four_geometric_mean_max": 0.90,
            "step_8_defect_relative_to_initial_max": 0.5,
            "spectral_radius_max_exclusive": 1.0,
            "maximum_power_norm_k_1_to_8": 2.0,
        },
        validate_temperature=lambda _: None,
        deadline=perf_counter() + 10.0,
    )
    assert metrics["contraction_ratios"] == pytest.approx([0.75] * 8)
    assert metrics["step_8_relative_defect"] == pytest.approx(0.75**8)
    assert metrics["spectral_radius"] == pytest.approx(0.75, abs=1.0e-9)
    assert metrics["operator_norm_2"] == pytest.approx(0.75, abs=1.0e-9)
    assert metrics["maximum_power_norm_k_1_to_8"] == pytest.approx(
        0.75, abs=1.0e-9
    )
    assert metrics["map_evaluations"] == 13
    assert metrics["gates"]["all_required"] is True


def test_r1_gate_rejects_expanding_relaxed_map() -> None:
    metrics = rescue.audit_unscaled_fixed_point_contraction(
        lambda temperature: 2.0 * temperature,
        np.asarray([[1.0]], dtype=float),
        relaxation=0.5,
        iteration_count=8,
        gates={
            "last_four_geometric_mean_max": 0.90,
            "step_8_defect_relative_to_initial_max": 0.5,
            "spectral_radius_max_exclusive": 1.0,
            "maximum_power_norm_k_1_to_8": 2.0,
        },
        validate_temperature=lambda _: None,
        deadline=perf_counter() + 10.0,
    )
    assert metrics["last_four_ratios"] == pytest.approx([1.5] * 4)
    assert metrics["spectral_radius"] == pytest.approx(1.5, abs=1.0e-9)
    assert metrics["gates"]["all_required"] is False

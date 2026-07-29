from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_geophase_phase1_v2_source_corrected_performance_readiness.py"
)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _runner_module():
    specification = importlib.util.spec_from_file_location(
        "source_corrected_performance_closure_runner", RUNNER_PATH
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _equivalence(module) -> dict[str, Any]:
    return {
        "status": "strict_equivalence_pass_pending_runtime_readiness",
        "all_equivalence_votes_pass": True,
        "maximum_normalized_relative_difference": 1.0e-13,
        "candidate_identity_sha256": HASH_B,
        "performance_repair_preregistration_sha256": (
            module.PERFORMANCE_PREREGISTRATION_SHA256
        ),
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "file_sha256": HASH_A,
    }


def _worker_rss() -> dict[str, Any]:
    return {
        "status": "PASS",
        "candidate_identity_sha256": HASH_B,
        "measured_peak_worker_RSS_bytes": 1_000,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }


def _passing_hooks(module, calls: list[str]) -> dict[str, Any]:
    def run_c1(remaining_s: float) -> dict[str, Any]:
        calls.append("C1")
        assert remaining_s == pytest.approx(900.0)
        return {
            "status": "PASS",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }

    def run_c2(remaining_s: float) -> dict[str, Any]:
        calls.append("C2")
        assert 0.0 <= remaining_s <= 900.0
        return {
            "status": "PASS",
            "sample_id": "PRE-CTRL-CRITICAL-TRAJECTORY",
            "input_sha256": HASH_A,
            "output_sha256": HASH_C,
            "observed_sample_wall_time_s": 2.0,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }

    def measure_launch_environment() -> dict[str, Any]:
        calls.append("environment")
        return {
            "physical_core_count": 4,
            "launch_available_RAM_bytes": 10_000,
        }

    def run_dormant_runner() -> dict[str, Any]:
        calls.append("dormant")
        return {
            "status": "PASS",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }

    def build_forecast(
        completed: tuple[dict[str, Any], ...],
        C2: dict[str, Any],
        worker_count: int,
    ) -> dict[str, Any]:
        calls.append("forecast")
        assert len(completed) == 26
        assert all(row["observed_sample_wall_time_s"] > 0.0 for row in completed)
        assert all(row["payload"]["accepted_steps"] == 1 for row in completed)
        assert all(row["payload"]["peak_RSS_bytes"] > 0 for row in completed)
        assert C2["observed_sample_wall_time_s"] == 2.0
        assert worker_count == 4
        return {
            "timing_semantics": module.PERFORMANCE_TIMING_SEMANTICS,
            "uses_observed_sample_wall_time_only": True,
            "stage_timings_summed_for_forecast": False,
            "predicted_p95_makespan_s": 10_000.0,
            "predicted_hard_makespan_s": 13_000.0,
            "RSS_gate_pass": True,
            "disk_gate_pass": True,
        }

    return {
        "run_c1": run_c1,
        "run_c2": run_c2,
        "measure_launch_environment": measure_launch_environment,
        "c3_worker_entrypoint": (
            "pinnpcm.solvers.geophase_phase1_v2_source_corrected_performance:"
            "run_c3_sample"
        ),
        "run_dormant_runner": run_dormant_runner,
        "build_forecast": build_forecast,
    }


def _passing_fake_pool(module, calls: list[str]):
    def run(
        plans,
        *,
        worker_count,
        worker_entrypoint,
        output_dir,
        preflight_started_s,
        clock,
        backstop_s,
    ):
        del output_dir, preflight_started_s, clock
        calls.append("C3_pool")
        submitted = [dict(row) for row in plans if row["pool_submit"]]
        assert len(submitted) == 26
        assert [row["plan_index"] for row in submitted] == sorted(
            row["plan_index"] for row in submitted
        )
        assert worker_count == 4
        assert worker_entrypoint.endswith(":run_c3_sample")
        assert backstop_s == pytest.approx(880.0)
        completed = [
            {
                **row,
                "output_sha256": HASH_C,
                "observed_sample_wall_time_s": 1.0 + row["plan_index"] / 100.0,
                "timing_semantics": module.PERFORMANCE_TIMING_SEMANTICS,
                "payload": {
                    "accepted_steps": 1,
                    "achieved_time_s": 1.0e-8,
                    "peak_RSS_bytes": 2_000,
                    "streaming_output_bytes": 256,
                    "timing_telemetry": {"sample_wall_time_s": 1.0},
                },
            }
            for row in submitted
        ]
        return {
            "status": "PASS",
            "completed_samples": tuple(completed),
            "submitted_sample_count": 26,
            "worker_count": worker_count,
            "start_method": "spawn",
        }

    return run


def test_c3_plan_has_18_intervals_9_trajectories_and_only_26_submissions() -> None:
    module = _runner_module()
    plans = module.build_source_corrected_c3_plan()

    assert len(plans) == 27
    assert [row["plan_index"] for row in plans] == list(range(27))
    assert sum(row["sample_kind"] == "single_interval" for row in plans) == 18
    assert sum(row["sample_kind"] == "short_trajectory" for row in plans) == 9
    assert sum(row["pool_submit"] for row in plans) == 26
    reused = [row for row in plans if row["reuse_C2"]]
    assert len(reused) == 1
    assert reused[0]["sample_id"] == "PRE-CTRL-CRITICAL-TRAJECTORY"
    assert reused[0]["pool_submit"] is False
    assert all(row["sample_id"].startswith("PRE-") for row in plans)

    high = [row for row in plans if row["state_id"] == "high_conductive"]
    assert high
    assert all(row["protocol"] == "high_bias_lock_15p8V" for row in high)
    assert all(row["protocol_V_scale_V"] == 15.8 for row in high)
    assert not any(row["protocol"] == "high_bias_15V" for row in plans)


def test_runner_modes_are_explicit_and_the_production_adapter_is_not_cli_selectable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _runner_module()

    with pytest.raises(SystemExit, match="no execution mode selected"):
        module.main([])
    module.main(["--check-route"])
    route = json.loads(capsys.readouterr().out)
    assert route["C3_countable_plan_count"] == 27
    assert route["C3_independent_pool_samples"] == 26
    assert route["numerical_execution_performed"] is False

    parser_help = module._parser().format_help()
    assert "--write-candidate-identity" in parser_help
    assert "--run-equivalence" in parser_help
    assert "--measure-worker-rss" in parser_help
    assert "--run-readiness" in parser_help
    assert "--task-entrypoint" not in parser_help
    assert module.TASK_ADAPTER_ENTRYPOINT == (
        "pinnpcm.solvers.geophase_phase1_v2_source_corrected_performance:"
        "task_adapter"
    )


def test_candidate_identity_mode_is_explicit_and_non_numerical(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _runner_module()
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        module,
        "write_optimized_candidate_identity",
        lambda *, route: calls.append(dict(route))
        or {
            "status": "optimized_candidate_identity_written_and_verified",
            "numerical_execution_performed": False,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        },
    )

    module.main(["--write-candidate-identity"])
    payload = json.loads(capsys.readouterr().out)

    assert len(calls) == 1
    assert payload["numerical_execution_performed"] is False
    assert payload["formal_execution_count"] == 0
    assert payload["formal_artifact_count"] == 0


def test_equivalence_and_RSS_modes_require_and_bind_candidate_identity(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _runner_module()
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def adapter(entrypoint: str, *, mode: str, payload: dict[str, Any]):
        calls.append((entrypoint, mode, payload))
        return {"status": "synthetic_interface_check"}

    monkeypatch.setattr(module, "_invoke_task_adapter", adapter)
    equivalence_calls: list[str] = []
    monkeypatch.setattr(
        module,
        "_run_frozen_equivalence",
        lambda candidate: equivalence_calls.append(candidate)
        or {"status": "synthetic_interface_check"},
    )
    with pytest.raises(SystemExit, match="candidate-identity"):
        module.main(["--measure-worker-rss"])
    module.main(
        ["--measure-worker-rss", "--candidate-identity-sha256", HASH_B]
    )
    capsys.readouterr()
    assert calls[-1][0] == module.TASK_ADAPTER_ENTRYPOINT
    assert calls[-1][1] == "measure_worker_rss"
    assert calls[-1][2]["candidate_identity_sha256"] == HASH_B

    module.main(["--run-equivalence", "--candidate-identity-sha256", HASH_B])
    capsys.readouterr()
    assert equivalence_calls == [HASH_B]


def test_frozen_equivalence_requires_content_candidate_and_file_hashes(
    tmp_path: Path,
) -> None:
    module = _runner_module()
    summary = _equivalence(module)
    summary.pop("file_sha256")
    path = tmp_path / "equivalence.json"
    path.write_text(
        json.dumps(summary, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    validated = module.validate_frozen_equivalence_summary(
        path,
        expected_file_sha256=file_hash,
        expected_candidate_identity_sha256=HASH_B,
    )
    assert validated["status"] == (
        "strict_equivalence_pass_pending_runtime_readiness"
    )
    assert validated["file_sha256"] == file_hash

    with pytest.raises(RuntimeError, match="candidate identity"):
        module.validate_frozen_equivalence_summary(
            path,
            expected_file_sha256=file_hash,
            expected_candidate_identity_sha256=HASH_C,
        )
    with pytest.raises(RuntimeError, match="file hash"):
        module.validate_frozen_equivalence_summary(
            path,
            expected_file_sha256=HASH_A,
            expected_candidate_identity_sha256=HASH_B,
        )


@pytest.mark.parametrize("failed_gate", ["C1", "C2"])
def test_serial_barriers_prevent_pool_creation_and_publish_the_failure(
    tmp_path: Path, failed_gate: str
) -> None:
    module = _runner_module()
    calls: list[str] = []
    hooks = _passing_hooks(module, calls)

    def fail(_remaining_s: float) -> dict[str, Any]:
        calls.append(f"{failed_gate}_FAIL")
        return {
            "status": "FAIL",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }

    hooks[f"run_{failed_gate.lower()}"] = fail

    def forbidden_pool(*args, **kwargs):
        del args, kwargs
        raise AssertionError("C3 pool must not exist after a serial barrier fails")

    result = module.execute_readiness_orchestration(
        hooks,
        route=module.validate_active_route(),
        equivalence=_equivalence(module),
        worker_rss=_worker_rss(),
        output_dir=tmp_path,
        clock=lambda: 0.0,
        c3_pool_runner=forbidden_pool,
    )

    assert result["disposition"] == "NO_GO_RUNTIME"
    assert result["failure_class"] == "numerical_integrity"
    assert result["C3"]["status"] == "NOT_REACHED"
    published = json.loads((tmp_path / "readiness_summary.json").read_text())
    assert published == result
    assert result["formal_execution_count"] == 0
    assert result["formal_artifact_count"] == 0


def test_orchestration_uses_one_26_sample_pool_and_counts_C2_reuse(
    tmp_path: Path,
) -> None:
    module = _runner_module()
    calls: list[str] = []
    hooks = _passing_hooks(module, calls)

    result = module.execute_readiness_orchestration(
        hooks,
        route=module.validate_active_route(),
        equivalence=_equivalence(module),
        worker_rss=_worker_rss(),
        output_dir=tmp_path,
        clock=lambda: 0.0,
        c3_pool_runner=_passing_fake_pool(module, calls),
    )

    assert calls == ["C1", "C2", "environment", "C3_pool", "dormant", "forecast"]
    assert result["disposition"] == "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION"
    assert result["C3"]["single_intervals_completed"] == 18
    assert result["C3"]["short_trajectories_completed_in_pool"] == 8
    assert result["C3"]["short_trajectories_completed_with_C2_reuse"] == 9
    assert result["C3"]["C2_reuse_count"] == 1
    assert result["C3"]["worker_count"] == 4
    assert result["performance_timing_semantics"] == (
        module.PERFORMANCE_TIMING_SEMANTICS
    )
    assert result["formal_execution_count"] == 0
    assert result["formal_artifact_count"] == 0
    assert result["formal_campaign_authorized"] is False


def test_valid_C3_failure_stops_dormant_runner_and_forecast(
    tmp_path: Path,
) -> None:
    module = _runner_module()
    calls: list[str] = []
    hooks = _passing_hooks(module, calls)

    def failing_pool(*args, **kwargs):
        del args, kwargs
        calls.append("C3_pool_FAIL")
        return {
            "status": "FAIL",
            "disposition": "NO_GO_RUNTIME",
            "failure_class": "numerical_integrity",
            "completed_samples": (),
        }

    result = module.execute_readiness_orchestration(
        hooks,
        route=module.validate_active_route(),
        equivalence=_equivalence(module),
        worker_rss=_worker_rss(),
        output_dir=tmp_path,
        clock=lambda: 0.0,
        c3_pool_runner=failing_pool,
    )

    assert result["disposition"] == "NO_GO_RUNTIME"
    assert result["failure_class"] == "numerical_integrity"
    assert "dormant" not in calls
    assert "forecast" not in calls


def test_forecast_rejects_additive_stage_timing_semantics(
    tmp_path: Path,
) -> None:
    module = _runner_module()
    calls: list[str] = []
    hooks = _passing_hooks(module, calls)

    def additive_forecast(*args) -> dict[str, Any]:
        del args
        return {
            "timing_semantics": "sum_stage_timings",
            "uses_observed_sample_wall_time_only": False,
            "stage_timings_summed_for_forecast": True,
            "predicted_p95_makespan_s": 1.0,
            "predicted_hard_makespan_s": 1.0,
            "RSS_gate_pass": True,
            "disk_gate_pass": True,
        }

    hooks["build_forecast"] = additive_forecast
    result = module.execute_readiness_orchestration(
        hooks,
        route=module.validate_active_route(),
        equivalence=_equivalence(module),
        worker_rss=_worker_rss(),
        output_dir=tmp_path,
        clock=lambda: 0.0,
        c3_pool_runner=_passing_fake_pool(module, calls),
    )

    assert result["disposition"] == "INVALID_PREFLIGHT_INFRASTRUCTURE"
    assert result["failure_class"] == "forecast_timing_semantics_invalid"


def test_900_second_gate_includes_forecast_and_atomic_publication_boundary(
    tmp_path: Path,
) -> None:
    module = _runner_module()
    calls: list[str] = []
    hooks = _passing_hooks(module, calls)
    times = iter((0.0, 1.0, 2.0, 3.0, 879.0, 881.0))

    result = module.execute_readiness_orchestration(
        hooks,
        route=module.validate_active_route(),
        equivalence=_equivalence(module),
        worker_rss=_worker_rss(),
        output_dir=tmp_path,
        clock=lambda: next(times),
        c3_pool_runner=_passing_fake_pool(module, calls),
    )

    assert result["disposition"] == "NO_GO_RUNTIME"
    assert result["failure_class"] == "performance_budget"
    assert result["preflight_wall_clock_before_atomic_publication_s"] == 881.0
    assert result["preflight_wall_clock_s"] == 901.0
    assert result["preflight_wall_clock_measurement"] == (
        "conservative_upper_bound_including_parent_atomic_finalization_reserve"
    )
    assert result["parent_atomic_finalization_reserve_s"] == 20.0
    assert json.loads((tmp_path / "readiness_summary.json").read_text()) == result


def test_worker_backstop_is_valid_runtime_budget_failure_before_pool(
    tmp_path: Path,
) -> None:
    module = _runner_module()
    calls: list[str] = []
    hooks = _passing_hooks(module, calls)
    times = iter((0.0, 1.0, 881.0, 882.0, 883.0))

    def forbidden_pool(*args, **kwargs):
        del args, kwargs
        raise AssertionError("pool must not start after the 880 s backstop")

    result = module.execute_readiness_orchestration(
        hooks,
        route=module.validate_active_route(),
        equivalence=_equivalence(module),
        worker_rss=_worker_rss(),
        output_dir=tmp_path,
        clock=lambda: next(times),
        c3_pool_runner=forbidden_pool,
    )

    assert result["disposition"] == "NO_GO_RUNTIME"
    assert result["failure_class"] == "performance_budget"
    assert "environment" not in calls


def test_concrete_C3_pool_is_one_spawn_executor_with_parent_tree_termination() -> None:
    module = _runner_module()
    source = inspect.getsource(module.run_c3_persistent_spawn_pool)

    assert source.count("ProcessPoolExecutor(") == 1
    assert 'multiprocessing.get_context("spawn")' in source
    assert "_terminate_executor_process_tree" in source
    assert "schedule_one()" in source
    assert "cancelled_after_valid_sample_failure" in source
    assert module._THREAD_ENVIRONMENT["OMP_NUM_THREADS"] == "1"
    assert module._THREAD_ENVIRONMENT["OPENBLAS_NUM_THREADS"] == "1"

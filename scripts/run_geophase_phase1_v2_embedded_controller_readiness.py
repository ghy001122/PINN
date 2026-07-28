from __future__ import annotations

import os

# The locked readiness contract requires one math-library thread per worker.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import argparse
from contextlib import nullcontext
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Any, Callable

import numpy as np
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_overlay import (
    resolve_controller_v2,
)
from pinnpcm.solvers.geophase_phase1_v2_controller_v2 import (
    attempt_s2_embedded_interval,
    controller_v2_limits,
)
from pinnpcm.solvers.geophase_phase1_v2_formal_runner import (
    InvalidContractError,
    begin_running,
    complete_pass,
    create_partial_case_work,
    create_prepared_registry,
    interrupt_resumable,
    load_registry,
    publish_synthetic_case,
    record_foundation_failure,
    resume_same_run,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    protocol_discontinuities,
    protocol_voltage,
)
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    build_campaign_cost_forecast,
    measure_launch_environment,
    process_memory,
)
from pinnpcm.solvers.geophase_phase1_v2_streaming import (
    fixed_scalar_sample_times,
    publish_pre_streaming_case,
    published_case_bytes,
    run_s2_streaming_protocol_v2,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
OVERLAY_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_embedded_time_controller_v2.yaml"
)
ADDENDUM_PATH = ROOT / "configs" / "geophase_phase1_v2_execution_addendum.yaml"
MANIFEST_PATH = ROOT / "configs" / "geophase_phase1_v2_formal_manifest.yaml"
EXPANDED_MANIFEST_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "formal_evaluation_manifest.json"
)
DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
    / "execution_dag.json"
)
OUTPUT_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "controller_v2_readiness"
)
PREREG_PATH = OUTPUT_DIR / "preregistration.json"
C1_PATH = OUTPUT_DIR / "C1_summary.json"
C2_PATH = OUTPUT_DIR / "C2_summary.json"
SAMPLES_PATH = OUTPUT_DIR / "preflight_samples.csv"
PREFLIGHT_PATH = OUTPUT_DIR / "preflight_summary.json"
COST_PATH = OUTPUT_DIR / "campaign_cost_forecast.csv"
RUNNER_PATH = OUTPUT_DIR / "runner_dry_run.json"
READINESS_PATH = OUTPUT_DIR / "readiness_summary.json"
REPORT_PATH = (
    ROOT
    / "docs"
    / "codex_reports"
    / "geophase_phase1_v2_embedded_controller_readiness.md"
)
DRIVER_RELATIVE_PATH = (
    "scripts/run_geophase_phase1_v2_embedded_controller_readiness.py"
)

# Updated after the final controller/readiness core commit and before the
# execution driver itself is committed and pushed.
IMPLEMENTATION_COMMIT = "cc00eab50c5c4ca98e11ce2763e92d635c9fcd2f"
IMPLEMENTATION_TREE = "29c4c51d7aef3a9f95ad2867b2d84dcc1b54c02f"
IMPLEMENTATION_PATHS = (
    "src/pinnpcm/physics/geophase_geometry.py",
    "src/pinnpcm/physics/geophase_s2_ledgers.py",
    "src/pinnpcm/physics/geophase_s2_thermal.py",
    "src/pinnpcm/physics/vo2_effective_conductivity.py",
    "src/pinnpcm/solvers/geophase_2p5d_fvm.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_controller_overlay.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_controller_v2.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_formal_runner.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_fvm.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_implicit.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_runtime.py",
    "src/pinnpcm/solvers/geophase_phase1_v2_streaming.py",
)
PREFLIGHT_LIMIT_S = 900.0
OUTPUT_RESERVE_S = 5.0
GLOBAL_WORKER_TIMEOUT_S = 880.0
OUTER_FLOOR_BASE_S = 9.765625e-12
_INTERNAL_WORKER_ENV = "PINNPCM_CONTROLLER_V2_READINESS_INTERNAL_WORKER"
_SUPERVISED_IO_ROOT_ENV = "PINNPCM_CONTROLLER_V2_SUPERVISED_IO_ROOT"

DISPOSITIONS = {
    "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
    "NO_GO_TIME_CONTROLLER_REVISION",
    "NO_GO_RUNTIME_PERFORMANCE_ONLY",
}

SAMPLE_FIELDS = [
    "sample_id",
    "sample_kind",
    "spatial_level",
    "nx",
    "ny",
    "state_id",
    "interval_class",
    "outer_interval_s",
    "protocol_id",
    "status",
    "failure_class",
    "error_class",
    "error_message",
    "accepted_steps",
    "rejected_steps",
    "coupled_solve_count",
    "newton_iterations",
    "krylov_matvecs",
    "armijo_backtracks",
    "fallback_steps",
    "fallback_picard_iterations",
    "step_wall_time_p50_s",
    "step_wall_time_p90_s",
    "step_wall_time_max_s",
    "accepted_dt_p10_s",
    "accepted_dt_p50_s",
    "accepted_dt_p90_s",
    "achieved_simulated_time_s",
    "completed",
    "stop_reason",
    "finite",
    "ledgers_pass",
    "lateral_pass",
    "embedded_error_max",
    "legacy_delta_s_max",
    "legacy_delta_b_max",
    "thermal_relative_residual_max",
    "circuit_relative_residual_max",
    "combined_relative_residual_max",
    "device_power_relative_residual_max",
    "lateral_relative_mismatch_max",
    "lateral_roundoff_ratio_max",
    "peak_rss_bytes",
    "streaming_output_bytes",
    "scalar_record_count",
    "predicted_full_streaming_bytes",
    "predicted_full_streaming_io_s",
    "parity_max_relative_error",
    "cached_uncached_parity_pass",
    "cached_uncached_parity_max_relative_error",
    "cached_uncached_parity_worst_component",
    "uncached_parity_wall_s",
    "streaming_publish_wall_s",
    "streaming_io_measurement_status",
    "event_observation",
]


@dataclass(frozen=True)
class ReadinessHooks:
    run_c1: Callable[[float], dict[str, Any]]
    run_c2: Callable[[float, int, float], dict[str, Any]]
    run_c3: Callable[[float, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class LockedAuthority:
    config: dict[str, Any]
    overlay: dict[str, Any]
    preregistration: dict[str, Any]
    execution_dag: dict[str, Any]
    identity_hashes: dict[str, str]
    environment: dict[str, Any]
    environment_sha256: str
    implementation_path_hashes: dict[str, str]
    execution_commit: str
    execution_tree: str
    driver_sha256: str


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a mapping")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """Return identity fields; launch capacity remains volatile telemetry."""

    keys = (
        "platform",
        "machine",
        "processor",
        "physical_core_count",
        "logical_core_count",
        "python_version",
        "numpy_version",
        "scipy_version",
        "thread_environment",
    )
    return {key: environment[key] for key in keys}


def _json_safe(payload: Any) -> Any:
    """Represent unavailable non-finite diagnostics as explicit JSON null."""

    if isinstance(payload, dict):
        return {key: _json_safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_json_safe(value) for value in payload]
    if isinstance(payload, (float, np.floating)) and not math.isfinite(float(payload)):
        return None
    if isinstance(payload, np.integer):
        return int(payload)
    if isinstance(payload, np.floating):
        return float(payload)
    return payload


def _git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def _git_blob_sha256(commit: str, relative_path: str) -> str:
    payload = subprocess.check_output(
        ["git", "show", f"{commit}:{relative_path}"], cwd=ROOT
    )
    return hashlib.sha256(payload).hexdigest()


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: Any) -> None:
    _atomic_text(
        path,
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
    )


def _atomic_csv(
    path: Path, rows: list[dict[str, Any]], fields: list[str] | tuple[str, ...]
) -> None:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    _atomic_text(path, stream.getvalue())


def c2_event_observation(
    events: tuple[dict[str, Any], ...],
    reversals: tuple[dict[str, Any], ...] = (),
) -> str:
    return (
        "observed"
        if events or reversals
        else "NA_not_observed_within_bounded_C2_window"
    )


def build_c3_plan() -> dict[str, list[dict[str, Any]]]:
    states = ("equilibrium", "legal_critical", "high_conductive")
    single = [
        {
            "sample_id": f"PRE-CTRL-STEP-L{level}-{state}-{interval_class}",
            "spatial_level": level,
            "state_id": state,
            "interval_class": interval_class,
        }
        for level in (1, 2, 4)
        for state in states
        for interval_class in ("base", "floor")
    ]
    trajectories = [
        {
            "sample_id": (
                "PRE-CTRL-C2-L1-legal_critical"
                if level == 1 and state == "legal_critical"
                else f"PRE-CTRL-TRAJ-L{level}-{state}"
            ),
            "spatial_level": level,
            "state_id": state,
            "reuse_C2": bool(level == 1 and state == "legal_critical"),
        }
        for level in (1, 2, 4)
        for state in states
    ]
    return {"single_intervals": single, "short_trajectories": trajectories}


def _not_reached(reason: str = "prior_gate_not_passed") -> dict[str, Any]:
    return {"status": "not_reached", "reason": reason}


def _disposition_for(stage: dict[str, Any]) -> str:
    if stage.get("status") == "pass":
        return "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION"
    if stage.get("failure_class") == "performance_only":
        return "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    return "NO_GO_TIME_CONTROLLER_REVISION"


_OBSERVED_CONTROLLER_FAILURE_MESSAGES = {
    "controller-v2 forced remainder failed closed",
    "controller-v2 failed at locked outer floor",
    "controller-v2 per-case rejection cap exceeded",
    "controller-v2 outer rejection cap exceeded",
}


def _is_observed_controller_failure(error: Exception) -> bool:
    """Distinguish solver fail-closed outcomes from driver/I/O failures."""

    return isinstance(error, RuntimeError) and str(error) in (
        _OBSERVED_CONTROLLER_FAILURE_MESSAGES
    )


def execute_readiness_pipeline(
    hooks: ReadinessHooks,
    *,
    preflight_limit_s: float = PREFLIGHT_LIMIT_S,
    clock: Callable[[], float] = perf_counter,
    preflight_started_s: float | None = None,
) -> dict[str, Any]:
    """Execute C1, C2, C3 exactly once and stop at the first invalid gate."""

    started = clock() if preflight_started_s is None else float(preflight_started_s)

    def remaining() -> float:
        return max(0.0, float(preflight_limit_s) - (clock() - started))

    C1 = hooks.run_c1(remaining())
    if C1.get("status") != "pass":
        C2 = _not_reached("C1_failed")
        C3 = _not_reached("C1_failed")
        disposition = _disposition_for(C1)
    else:
        C2 = hooks.run_c2(remaining(), 128, 1.0e-6)
        if C2.get("status") != "pass":
            C3 = _not_reached("C2_failed")
            disposition = _disposition_for(C2)
        elif C2.get("runtime_evidence_sufficient") is not True:
            C3 = {
                "status": "runtime_evidence_insufficient",
                "failure_class": "performance_only",
            }
            disposition = "NO_GO_RUNTIME_PERFORMANCE_ONLY"
        else:
            C3 = hooks.run_c3(remaining(), dict(C2["forecast_sample_row"]))
            disposition = _disposition_for(C3)
    if disposition not in DISPOSITIONS:
        raise RuntimeError("readiness produced a forbidden disposition")
    return {
        "task_id": "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION",
        "schema_version": "geophase_phase1_v2_readiness_pipeline_v1",
        "C1": C1,
        "C2": C2,
        "C3": C3,
        "disposition": disposition,
        "preflight_wall_clock_s": clock() - started,
        "preflight_wall_clock_limit_s": float(preflight_limit_s),
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifact_count": 0,
        "formal_campaign_authorized": False,
    }


def _load_authority() -> LockedAuthority:
    resolved = resolve_controller_v2(BASE_CONFIG_PATH, OVERLAY_PATH)
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    dag = json.loads(DAG_PATH.read_text(encoding="utf-8"))
    if prereg["status"] != "preregistered_not_executed":
        raise RuntimeError("controller-v2 preregistration is not executable")
    if prereg["preregistration_commit"] != "406207b02adaa37953ff4d3813aaeee3235c004f":
        raise RuntimeError("controller-v2 preregistration anchor changed")
    if prereg["base_S2_config_sha256"] != resolved.base_sha256:
        raise RuntimeError("controller-v2 base hash differs from preregistration")
    if prereg["controller_v2_overlay_sha256"] != resolved.overlay_sha256:
        raise RuntimeError("controller-v2 overlay hash differs from preregistration")
    if prereg["resolved_runtime_identity_sha256"] != resolved.identity_sha256:
        raise RuntimeError("resolved controller identity differs from preregistration")
    if prereg["formal_execution_count"] != 0 or prereg["formal_artifact_count"] != 0:
        raise RuntimeError("controller-v2 preregistration consumed formal state")
    if dag.get("evaluation_item_count") != 63 or dag.get("unique_execution_unit_count") != 60:
        raise RuntimeError("execution DAG no longer carries the locked 63/60 identity")
    if (
        dag.get("reused_evaluation_count") != 3
        or len(dag.get("reuse_map", {})) != 3
    ):
        raise RuntimeError("execution DAG no longer carries three legal reuses")

    if _git("show", "-s", "--format=%T", IMPLEMENTATION_COMMIT) != IMPLEMENTATION_TREE:
        raise RuntimeError("controller-v2 implementation tree lock is unavailable")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", IMPLEMENTATION_COMMIT, "HEAD"],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("controller-v2 implementation commit is not an ancestor")
    implementation_hashes: dict[str, str] = {}
    for relative in IMPLEMENTATION_PATHS:
        locked = _git_blob_sha256(IMPLEMENTATION_COMMIT, relative)
        current = _sha256(ROOT / relative)
        if current != locked:
            raise RuntimeError(f"implementation path drifted after lock: {relative}")
        implementation_hashes[relative] = locked

    if _git("status", "--porcelain"):
        raise RuntimeError("readiness execution requires a clean committed worktree")
    branch = _git("branch", "--show-current")
    upstream = _git(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    execution_commit = _git("rev-parse", "HEAD")
    if execution_commit != _git("rev-parse", upstream):
        raise RuntimeError("readiness execution commit is not pushed to its upstream")
    execution_tree = _git("show", "-s", "--format=%T", execution_commit)
    driver_locked = _git_blob_sha256(execution_commit, DRIVER_RELATIVE_PATH)
    driver_current = _sha256(ROOT / DRIVER_RELATIVE_PATH)
    if driver_current != driver_locked:
        raise RuntimeError("readiness driver differs from its pushed execution commit")

    environment = measure_launch_environment(ROOT)
    environment_hash = _canonical_hash(_stable_environment(environment))
    code_tree_hash = _canonical_hash(
        {
            "implementation_commit": IMPLEMENTATION_COMMIT,
            "implementation_tree": IMPLEMENTATION_TREE,
            "implementation_path_hashes_sha256": implementation_hashes,
            "readiness_execution_commit": execution_commit,
            "readiness_execution_tree": execution_tree,
            "readiness_driver_sha256": driver_locked,
            "readiness_branch": branch,
        }
    )
    identity_hashes = {
        "code_tree": code_tree_hash,
        "S2_config": resolved.base_sha256,
        "controller_v2_overlay": resolved.overlay_sha256,
        "resolved_runtime_identity": resolved.identity_sha256,
        "formal_manifest_contract": _sha256(MANIFEST_PATH),
        "expanded_manifest": _sha256(EXPANDED_MANIFEST_PATH),
        "execution_addendum": _sha256(ADDENDUM_PATH),
        "execution_DAG": _sha256(DAG_PATH),
        "environment": environment_hash,
    }
    return LockedAuthority(
        config=resolved.resolved_config,
        overlay=resolved.overlay_document,
        preregistration=prereg,
        execution_dag=dag,
        identity_hashes=identity_hashes,
        environment=environment,
        environment_sha256=environment_hash,
        implementation_path_hashes=implementation_hashes,
        execution_commit=execution_commit,
        execution_tree=execution_tree,
        driver_sha256=driver_locked,
    )


def _protocol_id(state_id: str) -> str:
    return {
        "equilibrium": "zero_drive",
        "legal_critical": "transition_probe_12p5V",
        "high_conductive": "high_bias_15V",
    }[state_id]


def _deterministic_state(
    state_id: str, *, grid: Any, closure: Any, fields: Any
) -> S2State:
    if state_id == "equilibrium":
        temperature = float(fields.ambient_temperature_K)
        branch = 1.0
        conductive = float(
            np.asarray(
                closure.equilibrium_state(
                    np.asarray(temperature), np.asarray(branch)
                )
            ).item()
        )
    elif state_id == "legal_critical":
        temperature = float(closure.T_c_up_K)
        branch = 1.0
        conductive = 0.5
    elif state_id == "high_conductive":
        temperature = float(closure.temperature_max_K)
        branch = 1.0
        conductive = float(
            np.asarray(
                closure.equilibrium_state(
                    np.asarray(temperature), np.asarray(branch)
                )
            ).item()
        )
    else:
        raise ValueError(f"unknown deterministic state {state_id}")
    return S2State(
        time_s=0.0,
        temperature_K=np.full(grid.shape, temperature, dtype=float),
        conductive_state=np.full(grid.shape, conductive, dtype=float),
        branch_memory=np.full(grid.shape, branch, dtype=float),
        device_voltage_V=0.0,
    )


def _finite_step(step: Any) -> bool:
    arrays = (
        step.state.temperature_K,
        step.state.conductive_state,
        step.state.branch_memory,
        step.electrical.potential_V,
        step.electrical.cell_joule_power_W,
    )
    scalars = (
        step.state.time_s,
        step.state.device_voltage_V,
        step.electrical.source_current_A,
        step.electrical.terminal_device_power_W,
    )
    return bool(
        all(np.isfinite(np.asarray(value, dtype=float)).all() for value in arrays)
        and np.isfinite(np.asarray(scalars, dtype=float)).all()
    )


def _ledger_lateral_values(step: Any, config: dict[str, Any]) -> dict[str, Any]:
    residuals = {
        name: float(getattr(step.ledgers, name).relative_residual)
        for name in ("thermal", "circuit", "combined", "device_power")
    }
    gates = config["gates"]
    ledgers_pass = bool(
        residuals["thermal"]
        <= float(gates["thermal_ledger_relative_residual_max"])
        and residuals["circuit"]
        <= float(gates["circuit_ledger_relative_residual_max"])
        and residuals["combined"]
        <= float(gates["combined_ledger_relative_residual_max"])
        and residuals["device_power"]
        <= float(gates["device_power_identity_relative_residual_max"])
    )
    relative = float(step.lateral_flux.matrix_face_relative_mismatch)
    roundoff = float(step.lateral_flux.matrix_face_roundoff_ratio)
    lateral_pass = bool(relative <= 1.0e-10 or roundoff <= 1.0)
    return {
        "thermal_relative_residual_max": residuals["thermal"],
        "circuit_relative_residual_max": residuals["circuit"],
        "combined_relative_residual_max": residuals["combined"],
        "device_power_relative_residual_max": residuals["device_power"],
        "lateral_relative_mismatch_max": relative,
        "lateral_roundoff_ratio_max": roundoff,
        "ledgers_pass": ledgers_pass,
        "lateral_pass": lateral_pass,
    }


def _embedded_step_integrity(step: Any, config: dict[str, Any]) -> bool:
    controller = step.controller
    embedded = controller.embedded_error
    paths = (
        controller.full_step,
        controller.first_half_step,
        controller.second_half_step,
        controller.aggregate,
    )
    ledger = _ledger_lateral_values(step, config)
    return bool(
        _finite_step(step)
        and embedded is not None
        and float(embedded.e_max) <= 0.02
        and all(path is not None and path.overall_pass for path in paths)
        and ledger["ledgers_pass"]
        and ledger["lateral_pass"]
    )


def _attempt_integrity_values(
    observation: Any, config: dict[str, Any]
) -> dict[str, Any]:
    diagnostics = observation.diagnostics
    paths = (
        diagnostics.full_step,
        diagnostics.first_half_step,
        diagnostics.second_half_step,
    )
    aggregate = diagnostics.aggregate
    complete = bool(all(path is not None for path in paths) and aggregate is not None)
    ledger_names = ("thermal", "circuit", "combined", "device_power")
    maxima = {name: 0.0 for name in ledger_names}
    lateral_relative = 0.0
    lateral_roundoff = 0.0
    if complete:
        for path in paths:
            assert path is not None
            lateral_relative = max(
                lateral_relative, float(path.lateral_relative_mismatch)
            )
            lateral_roundoff = max(
                lateral_roundoff, float(path.lateral_roundoff_ratio)
            )
            for name, residual in path.ledger_relative_residuals.items():
                maxima[name] = max(maxima[name], float(residual))
        assert aggregate is not None
        for name, residual in aggregate.ledger_relative_residuals.items():
            maxima[name] = max(maxima[name], float(residual))
    gates = config["gates"]
    limits = {
        "thermal": float(gates["thermal_ledger_relative_residual_max"]),
        "circuit": float(gates["circuit_ledger_relative_residual_max"]),
        "combined": float(gates["combined_ledger_relative_residual_max"]),
        "device_power": float(gates["device_power_identity_relative_residual_max"]),
    }
    finite = bool(
        complete
        and all(path is not None and path.finite for path in paths)
        and aggregate is not None
        and aggregate.finite
    )
    nonlinear = bool(
        complete and all(path is not None and path.nonlinear_pass for path in paths)
    )
    ledger_pass = bool(
        complete
        and all(path is not None and path.ledger_pass for path in paths)
        and aggregate is not None
        and aggregate.ledger_pass
        and all(maxima[name] <= limits[name] for name in ledger_names)
    )
    lateral_pass = bool(
        complete
        and all(path is not None and path.lateral_pass for path in paths)
        and (lateral_relative <= 1.0e-10 or lateral_roundoff <= 1.0)
    )
    overall = bool(
        finite
        and nonlinear
        and ledger_pass
        and lateral_pass
        and all(path is not None and path.overall_pass for path in paths)
        and aggregate is not None
        and aggregate.overall_pass
    )
    return {
        "overall_pass": overall,
        "finite": finite,
        "nonlinear_pass": nonlinear,
        "ledgers_pass": ledger_pass,
        "lateral_pass": lateral_pass,
        "thermal_relative_residual_max": maxima["thermal"],
        "circuit_relative_residual_max": maxima["circuit"],
        "combined_relative_residual_max": maxima["combined"],
        "device_power_relative_residual_max": maxima["device_power"],
        "lateral_relative_mismatch_max": lateral_relative,
        "lateral_roundoff_ratio_max": lateral_roundoff,
    }


def _compare_exact(
    errors: list[tuple[str, float]], name: str, left: Any, right: Any
) -> None:
    if left != right:
        errors.append((name, math.inf))


def _compare_nonlinear(
    errors: list[tuple[str, float]], prefix: str, left: Any, right: Any
) -> None:
    for name in (
        "method",
        "iterations",
        "converged",
        "krylov_matvecs",
        "armijo_backtracks",
        "predictor_picard_iterations",
        "fallback_picard_iterations",
    ):
        _compare_exact(errors, f"{prefix}.{name}", getattr(left, name), getattr(right, name))
    for name in ("scaled_residual_inf", "scaled_update_inf"):
        _record_parity(
            errors,
            f"{prefix}.{name}",
            getattr(left, name),
            getattr(right, name),
            1.0e-30,
        )


def _compare_ledger_balance(
    errors: list[tuple[str, float]], prefix: str, left: Any, right: Any
) -> None:
    _compare_exact(errors, f"{prefix}.name", left.name, right.name)
    if set(left.terms_W) != set(right.terms_W):
        errors.append((f"{prefix}.terms.keys", math.inf))
        return
    scale = max(
        abs(float(left.input_power_W)),
        abs(float(right.input_power_W)),
        *(abs(float(value)) for value in left.terms_W.values()),
        *(abs(float(value)) for value in right.terms_W.values()),
        1.0e-30,
    )
    for name in (
        "input_power_W",
        "accounted_power_W",
        "signed_residual_W",
        "relative_residual",
    ):
        _record_parity(
            errors,
            f"{prefix}.{name}",
            getattr(left, name),
            getattr(right, name),
            1.0 if name == "relative_residual" else scale,
        )
    for name in sorted(left.terms_W):
        _record_parity(
            errors,
            f"{prefix}.terms.{name}",
            left.terms_W[name],
            right.terms_W[name],
            scale,
        )


def _compare_ledger_bundle(
    errors: list[tuple[str, float]], prefix: str, left: Any, right: Any
) -> None:
    if (left is None) != (right is None):
        errors.append((f"{prefix}.presence", math.inf))
        return
    if left is None:
        return
    for name in (
        "explicit_plane_storage_rate_W",
        "closure_storage_rate_W",
        "effective_storage_rate_W",
        "vertical_sink_power_W",
        "lateral_boundary_outflow_W",
    ):
        _record_parity(
            errors,
            f"{prefix}.storage.{name}",
            getattr(left.storage, name),
            getattr(right.storage, name),
            1.0e-30,
        )
    for ledger_name in ("thermal", "circuit", "combined", "device_power"):
        _compare_ledger_balance(
            errors,
            f"{prefix}.{ledger_name}",
            getattr(left, ledger_name),
            getattr(right, ledger_name),
        )


def _compare_step_result(
    errors: list[tuple[str, float]], prefix: str, left: Any, right: Any, voltage_scale: float
) -> None:
    if (left is None) != (right is None):
        errors.append((f"{prefix}.presence", math.inf))
        return
    if left is None:
        return
    for name, scale in (
        ("time_s", 1.0e-9),
        ("temperature_K", 7.19),
        ("conductive_state", 1.0),
        ("branch_memory", 1.0),
        ("device_voltage_V", voltage_scale),
    ):
        _record_parity(
            errors,
            f"{prefix}.state.{name}",
            getattr(left.state, name),
            getattr(right.state, name),
            scale,
        )
    for name, scale in (
        ("potential_V", voltage_scale),
        ("source_current_A", 1.0e-12),
        ("ground_current_A", 1.0e-12),
        ("cell_joule_power_W", 1.0e-30),
        ("joule_power_W", 1.0e-30),
        ("terminal_device_power_W", 1.0e-30),
        ("relative_current_imbalance", 1.0),
        ("relative_power_imbalance", 1.0),
    ):
        _record_parity(
            errors,
            f"{prefix}.electrical.{name}",
            getattr(left.electrical, name),
            getattr(right.electrical, name),
            scale,
        )
    for name in (
        "net_cell_outflow_W",
        "x_face_flux_W",
        "y_face_flux_W",
        "boundary_face_flux_W",
        "boundary_outflow_W",
        "internal_pair_cancellation_W",
        "face_to_cell_global_residual_W",
        "matrix_face_relative_mismatch",
        "matrix_face_roundoff_ratio",
    ):
        _record_parity(
            errors,
            f"{prefix}.lateral.{name}",
            getattr(left.lateral_flux, name),
            getattr(right.lateral_flux, name),
            1.0e-30,
        )
    _compare_ledger_bundle(errors, f"{prefix}.ledgers", left.ledgers, right.ledgers)
    _compare_nonlinear(errors, f"{prefix}.nonlinear", left.nonlinear, right.nonlinear)


def _compare_attempt_observations(
    cached: Any, uncached: Any, *, voltage_scale: float
) -> dict[str, Any]:
    errors: list[tuple[str, float]] = []
    for name in ("error_class", "error_message"):
        _compare_exact(
            errors, f"observation.{name}", getattr(cached, name), getattr(uncached, name)
        )
    for name in (
        "full_candidate",
        "first_half_candidate",
        "second_half_candidate",
        "step",
    ):
        _compare_step_result(
            errors,
            name,
            getattr(cached, name),
            getattr(uncached, name),
            voltage_scale,
        )
    _compare_ledger_bundle(
        errors,
        "aggregate_ledgers",
        cached.aggregate_ledgers,
        uncached.aggregate_ledgers,
    )
    if (cached.aggregate_energy is None) != (uncached.aggregate_energy is None):
        errors.append(("aggregate_energy.presence", math.inf))
    elif cached.aggregate_energy is not None:
        for name in cached.aggregate_energy.__dataclass_fields__:
            _record_parity(
                errors,
                f"aggregate_energy.{name}",
                getattr(cached.aggregate_energy, name),
                getattr(uncached.aggregate_energy, name),
                1.0e-30,
            )
    left = cached.diagnostics
    right = uncached.diagnostics
    for path_name in ("full_step", "first_half_step", "second_half_step"):
        left_path = getattr(left, path_name)
        right_path = getattr(right, path_name)
        if (left_path is None) != (right_path is None):
            errors.append((f"diagnostics.{path_name}.presence", math.inf))
            continue
        if left_path is None:
            continue
        for name in (
            "finite",
            "nonlinear_pass",
            "ledger_pass",
            "lateral_pass",
            "overall_pass",
            "error_class",
            "error_message",
        ):
            _compare_exact(
                errors,
                f"diagnostics.{path_name}.{name}",
                getattr(left_path, name),
                getattr(right_path, name),
            )
        for name in ("lateral_relative_mismatch", "lateral_roundoff_ratio"):
            _record_parity(
                errors,
                f"diagnostics.{path_name}.{name}",
                getattr(left_path, name),
                getattr(right_path, name),
                1.0e-30,
            )
        if set(left_path.ledger_relative_residuals) != set(
            right_path.ledger_relative_residuals
        ):
            errors.append((f"diagnostics.{path_name}.ledger_keys", math.inf))
        else:
            for name in left_path.ledger_relative_residuals:
                _record_parity(
                    errors,
                    f"diagnostics.{path_name}.{name}",
                    left_path.ledger_relative_residuals[name],
                    right_path.ledger_relative_residuals[name],
                    1.0,
                )
    left_aggregate = left.aggregate
    right_aggregate = right.aggregate
    if (left_aggregate is None) != (right_aggregate is None):
        errors.append(("diagnostics.aggregate.presence", math.inf))
    elif left_aggregate is not None:
        for name in (
            "finite",
            "ledger_pass",
            "overall_pass",
            "error_class",
            "error_message",
        ):
            _compare_exact(
                errors,
                f"diagnostics.aggregate.{name}",
                getattr(left_aggregate, name),
                getattr(right_aggregate, name),
            )
        for name in left_aggregate.ledger_relative_residuals:
            _record_parity(
                errors,
                f"diagnostics.aggregate.{name}",
                left_aggregate.ledger_relative_residuals[name],
                right_aggregate.ledger_relative_residuals[name],
                1.0,
            )
    for name in (
        "rejection_index",
        "below_floor_remainder",
        "at_outer_floor",
        "accepted",
        "coupled_solve_count",
        "any_fallback",
    ):
        _compare_exact(errors, f"diagnostics.{name}", getattr(left, name), getattr(right, name))
    for name in (
        "outer_interval_s",
        "half_interval_s",
        "voltage_scale_V",
        "full_input_voltage_V",
        "first_half_input_voltage_V",
        "second_half_input_voltage_V",
        "legacy_conductive_increment",
        "legacy_branch_increment",
    ):
        _record_parity(
            errors,
            f"diagnostics.{name}",
            getattr(left, name),
            getattr(right, name),
            voltage_scale if "voltage" in name else 1.0,
        )
    if (left.embedded_error is None) != (right.embedded_error is None):
        errors.append(("embedded_error.presence", math.inf))
    elif left.embedded_error is not None:
        for name in ("e_T", "e_s", "e_b", "e_V", "e_max", "voltage_scale_V"):
            _record_parity(
                errors,
                f"embedded_error.{name}",
                getattr(left.embedded_error, name),
                getattr(right.embedded_error, name),
                voltage_scale if name == "voltage_scale_V" else 1.0,
            )
    return _parity_summary(errors)

def _mean(values: np.ndarray) -> float:
    return float(np.mean(np.asarray(values, dtype=float)))


def _area_mean(values: np.ndarray, grid: Any) -> float:
    array = np.asarray(values, dtype=float)
    cell_area = float(grid.cell_area_m2)
    area = float(getattr(grid, "area_m2", cell_area * array.size))
    return float(np.sum(array) * cell_area / area)


def _parity_error(candidate: Any, reference: Any, scale: float) -> float:
    left = np.asarray(candidate, dtype=float)
    right = np.asarray(reference, dtype=float)
    if left.shape != right.shape or not np.isfinite(left).all() or not np.isfinite(right).all():
        return math.inf
    denominator = max(
        float(scale),
        float(np.max(np.abs(left), initial=0.0)),
        float(np.max(np.abs(right), initial=0.0)),
    )
    return float(np.max(np.abs(left - right), initial=0.0) / denominator)


def _record_parity(
    errors: list[tuple[str, float]], name: str, candidate: Any, reference: Any, scale: float
) -> None:
    errors.append((name, _parity_error(candidate, reference, scale)))


def _parity_summary(errors: list[tuple[str, float]]) -> dict[str, Any]:
    if not errors:
        return {"pass": True, "maximum_relative_error": 0.0, "worst_component": ""}
    worst, maximum = max(errors, key=lambda item: item[1])
    return {
        "pass": bool(math.isfinite(maximum) and maximum <= 1.0e-12),
        "maximum_relative_error": float(maximum),
        "worst_component": worst,
    }


def _history_streaming_parity(
    initial_state: S2State,
    result: Any,
    grid: Any,
    config: dict[str, Any],
    protocol_id: str,
) -> dict[str, Any]:
    """Compare all fixed accepted-path output against the retained same run."""

    history = tuple(result.protocol_result.steps)
    if not history:
        return {
            "pass": False,
            "maximum_relative_error": math.inf,
            "worst_component": "missing_retained_history",
        }
    errors: list[tuple[str, float]] = []
    expected_sample_times = fixed_scalar_sample_times(
        config, float(result.protocol_result.achieved_final_time_s)
    )
    scalar_records = tuple(result.scalar_records)
    if len(scalar_records) != len(expected_sample_times):
        return {
            "pass": False,
            "maximum_relative_error": math.inf,
            "worst_component": "fixed_scalar_record_count",
        }
    expected_voltage_scale = float(
        config["reference_solver"]["active_time_controller"]["voltage_scale"]
        ["protocol_V_scale_V"][protocol_id]
    )
    protocol = config["formal_protocols"]["protocols"][protocol_id]
    for index, (record, expected_time) in enumerate(
        zip(scalar_records, expected_sample_times, strict=True)
    ):
        exact_identity = {
            "case_id": result.case_id,
            "sample_index": index,
            "sample_kind": "initial_no_interval" if index == 0 else "fixed_grid",
            "time_controller": "embedded_time_consistency_v2_only",
        }
        for name, expected in exact_identity.items():
            if record.get(name) != expected:
                errors.append((f"scalar.{index}.{name}", math.inf))
        _record_parity(
            errors,
            f"scalar.{index}.time_s",
            record.get("time_s"),
            expected_time,
            1.0e-30,
        )
        _record_parity(
            errors,
            f"scalar.{index}.voltage_scale_V",
            record.get("voltage_scale_V"),
            expected_voltage_scale,
            expected_voltage_scale,
        )
        events_to_date = tuple(
            event
            for event in result.event_records
            if float(event["after_sample_time_s"])
            <= float(expected_time) + max(1.0e-18, abs(float(expected_time)) * 1.0e-12)
        )
        last_event = events_to_date[-1] if events_to_date else None
        if record.get("event_count_to_date") != len(events_to_date):
            errors.append((f"scalar.{index}.event_count_to_date", math.inf))
        expected_direction = "" if last_event is None else last_event["direction"]
        if record.get("last_event_direction") != expected_direction:
            errors.append((f"scalar.{index}.last_event_direction", math.inf))
        expected_event_time: float | str = (
            "" if last_event is None else float(last_event["crossing_time_s"])
        )
        if isinstance(expected_event_time, str):
            if record.get("last_event_time_s") != expected_event_time:
                errors.append((f"scalar.{index}.last_event_time_s", math.inf))
        else:
            _record_parity(
                errors,
                f"scalar.{index}.last_event_time_s",
                record.get("last_event_time_s"),
                expected_event_time,
                1.0e-9,
            )
    initial_record = scalar_records[0]
    initial_expected = {
        "input_voltage_V": float(protocol_voltage(protocol, initial_state.time_s)),
        "device_voltage_V": float(initial_state.device_voltage_V),
        "terminal_current_A": 0.0,
        "terminal_device_power_W": 0.0,
        "maximum_temperature_K": float(np.max(initial_state.temperature_K)),
        "minimum_temperature_K": float(np.min(initial_state.temperature_K)),
        "mean_temperature_K": _area_mean(initial_state.temperature_K, grid),
        "mean_conductive_state": _area_mean(initial_state.conductive_state, grid),
        "mean_branch_memory": _area_mean(initial_state.branch_memory, grid),
    }
    initial_scales = {
        "input_voltage_V": expected_voltage_scale,
        "device_voltage_V": expected_voltage_scale,
        "terminal_current_A": 1.0e-12,
        "terminal_device_power_W": 1.0e-30,
        "maximum_temperature_K": 7.19,
        "minimum_temperature_K": 7.19,
        "mean_temperature_K": 7.19,
        "mean_conductive_state": 1.0,
        "mean_branch_memory": 1.0,
    }
    for name, expected in initial_expected.items():
        _record_parity(
            errors,
            f"scalar.0.{name}",
            initial_record.get(name),
            expected,
            initial_scales[name],
        )
    for record in scalar_records[1:]:
        target = float(record["time_s"])
        matches = [
            step
            for step in history
            if abs(float(step.state.time_s) - target)
            <= max(1.0e-18, abs(target) * 1.0e-12)
        ]
        if len(matches) != 1:
            return {
                "pass": False,
                "maximum_relative_error": math.inf,
                "worst_component": f"scalar_time_match_{target:.17g}",
            }
        step = matches[0]
        state = step.state
        voltage_scale = expected_voltage_scale
        scalar_expected = {
            "input_voltage_V": float(step.controller.second_half_input_voltage_V),
            "device_voltage_V": float(state.device_voltage_V),
            "terminal_current_A": float(step.electrical.source_current_A),
            "terminal_device_power_W": float(step.electrical.terminal_device_power_W),
            "maximum_temperature_K": float(np.max(state.temperature_K)),
            "minimum_temperature_K": float(np.min(state.temperature_K)),
            "mean_temperature_K": _area_mean(state.temperature_K, grid),
            "mean_conductive_state": _area_mean(state.conductive_state, grid),
            "mean_branch_memory": _area_mean(state.branch_memory, grid),
            "lateral_matrix_face_relative_mismatch": float(
                step.lateral_flux.matrix_face_relative_mismatch
            ),
            "lateral_matrix_face_roundoff_ratio": float(
                step.lateral_flux.matrix_face_roundoff_ratio
            ),
            "lateral_face_to_cell_global_residual_W": float(
                step.lateral_flux.face_to_cell_global_residual_W
            ),
        }
        scales = {
            "input_voltage_V": voltage_scale,
            "device_voltage_V": voltage_scale,
            "terminal_current_A": 1.0e-12,
            "terminal_device_power_W": 1.0e-30,
            "maximum_temperature_K": 7.19,
            "minimum_temperature_K": 7.19,
            "mean_temperature_K": 7.19,
            "mean_conductive_state": 1.0,
            "mean_branch_memory": 1.0,
            "lateral_matrix_face_relative_mismatch": 1.0e-30,
            "lateral_matrix_face_roundoff_ratio": 1.0e-30,
            "lateral_face_to_cell_global_residual_W": 1.0e-30,
        }
        for name, expected in scalar_expected.items():
            _record_parity(errors, f"scalar.{name}", record[name], expected, scales[name])
        nonlinear = step.nonlinear
        exact_nonlinear = {
            "nonlinear_method": nonlinear.method,
            "newton_iterations": nonlinear.iterations,
            "krylov_matvecs": nonlinear.krylov_matvecs,
            "armijo_backtracks": nonlinear.armijo_backtracks,
            "fallback_picard_iterations": nonlinear.fallback_picard_iterations,
        }
        for name, expected in exact_nonlinear.items():
            if record[name] != expected:
                errors.append((f"scalar.{name}", math.inf))
        for ledger_name in ("thermal", "circuit", "combined", "device_power"):
            ledger = getattr(step.ledgers, ledger_name)
            for suffix, expected in (
                ("input_power_W", ledger.input_power_W),
                ("accounted_power_W", ledger.accounted_power_W),
                ("signed_residual_W", ledger.signed_residual_W),
                ("relative_residual", ledger.relative_residual),
            ):
                _record_parity(
                    errors,
                    f"scalar.{ledger_name}_{suffix}",
                    record[f"{ledger_name}_{suffix}"],
                    expected,
                    1.0e-30,
                )
        embedded = step.controller.embedded_error
        if embedded is None:
            errors.append(("controller.embedded_error", math.inf))
        else:
            for name in ("e_T", "e_s", "e_b", "e_V", "e_max"):
                _record_parity(
                    errors,
                    f"controller.{name}",
                    record[name],
                    getattr(embedded, name),
                    1.0,
                )
        for name, expected in (
            ("outer_interval_s", step.controller.outer_interval_s),
            ("outer_rejections", step.controller.rejection_index),
            ("accepted_bundle_coupled_solve_count", step.controller.coupled_solve_count),
            ("legacy_max_absolute_delta_s", step.controller.legacy_conductive_increment or 0.0),
            ("legacy_max_absolute_delta_b", step.controller.legacy_branch_increment or 0.0),
        ):
            scale = 1.0e-30 if name == "outer_interval_s" else 1.0
            _record_parity(errors, f"controller.{name}", record[name], expected, scale)
        if int(record["coupled_solve_count"]) < int(
            record["accepted_bundle_coupled_solve_count"]
        ):
            errors.append(("controller.coupled_solve_count", math.inf))
        for prefix, path, path_nonlinear in (
            ("full", step.controller.full_step, step.controller.full_nonlinear),
            (
                "first_half",
                step.controller.first_half_step,
                step.controller.first_half_nonlinear,
            ),
            (
                "second_half",
                step.controller.second_half_step,
                step.controller.second_half_nonlinear,
            ),
        ):
            if path is None or path_nonlinear is None:
                errors.append((f"{prefix}.missing", math.inf))
                continue
            exact = {
                "finite": path.finite,
                "nonlinear_pass": path.nonlinear_pass,
                "ledger_pass": path.ledger_pass,
                "lateral_pass": path.lateral_pass,
                "overall_pass": path.overall_pass,
                "nonlinear_method": path_nonlinear.method,
                "nonlinear_iterations": path_nonlinear.iterations,
                "krylov_matvecs": path_nonlinear.krylov_matvecs,
                "armijo_backtracks": path_nonlinear.armijo_backtracks,
                "predictor_picard_iterations": path_nonlinear.predictor_picard_iterations,
                "fallback_picard_iterations": path_nonlinear.fallback_picard_iterations,
                "converged": path_nonlinear.converged,
            }
            for suffix, expected in exact.items():
                if record[f"{prefix}_{suffix}"] != expected:
                    errors.append((f"{prefix}.{suffix}", math.inf))
            for suffix, expected in (
                ("lateral_relative_mismatch", path.lateral_relative_mismatch),
                ("lateral_roundoff_ratio", path.lateral_roundoff_ratio),
                ("scaled_residual_inf", path_nonlinear.scaled_residual_inf),
                ("scaled_update_inf", path_nonlinear.scaled_update_inf),
            ):
                _record_parity(
                    errors,
                    f"{prefix}.{suffix}",
                    record[f"{prefix}_{suffix}"],
                    expected,
                    1.0e-30,
                )
            for ledger_name, expected in path.ledger_relative_residuals.items():
                _record_parity(
                    errors,
                    f"{prefix}.{ledger_name}",
                    record[f"{prefix}_{ledger_name}_relative_residual"],
                    expected,
                    1.0e-30,
                )
        aggregate = step.controller.aggregate
        if aggregate is None:
            errors.append(("aggregate.missing", math.inf))
        else:
            for suffix in ("finite", "ledger_pass", "overall_pass"):
                if record[f"aggregate_{suffix}"] != getattr(aggregate, suffix):
                    errors.append((f"aggregate.{suffix}", math.inf))
            for ledger_name, expected in aggregate.ledger_relative_residuals.items():
                _record_parity(
                    errors,
                    f"aggregate.{ledger_name}",
                    record[f"aggregate_{ledger_name}_relative_residual"],
                    expected,
                    1.0e-30,
                )
    final = history[-1].state
    for name, scale in (
        ("temperature_K", 7.19),
        ("conductive_state", 1.0),
        ("branch_memory", 1.0),
        ("device_voltage_V", 12.5),
    ):
        _record_parity(
            errors,
            f"final.{name}",
            getattr(result.final_state, name),
            getattr(final, name),
            scale,
        )
    references: list[tuple[float, Any, Any, Any]] = [
        (
            float(initial_state.time_s),
            initial_state,
            np.zeros(grid.shape, dtype=float),
            np.zeros(grid.shape, dtype=float),
        )
    ]
    references.extend(
        (
            float(step.state.time_s),
            step.state,
            step.electrical.potential_V,
            step.electrical.cell_joule_power_W,
        )
        for step in history
    )
    achieved_final = float(result.protocol_result.achieved_final_time_s)
    fixed_times = tuple(
        sorted(
            {
                float(value)
                for value in (
                    0.0,
                    5.0e-6,
                    1.0e-5,
                    1.5e-5,
                    2.0e-5,
                    *protocol_discontinuities(protocol),
                )
                if float(initial_state.time_s) <= float(value) <= achieved_final
            }
        )
    )
    selected_events = tuple(result.event_records)
    if len(selected_events) > 8:
        selected_events = selected_events[:4] + selected_events[-4:]
    expected_snapshot_descriptors: list[tuple[float, str, int | None, str | None]] = [
        (time_s, "fixed", None, None) for time_s in fixed_times
    ]
    for event in selected_events:
        expected_snapshot_descriptors.extend(
            (
                (
                    float(event["before_sample_time_s"]),
                    "event_before",
                    int(event["event_index"]),
                    str(event["direction"]),
                ),
                (
                    float(event["after_sample_time_s"]),
                    "event_after",
                    int(event["event_index"]),
                    str(event["direction"]),
                ),
            )
        )
    snapshots = tuple(result.field_snapshots)
    if len(snapshots) != len(expected_snapshot_descriptors):
        errors.append(("snapshot.descriptor_count", math.inf))
    for index, (snapshot, descriptor) in enumerate(
        zip(snapshots, expected_snapshot_descriptors)
    ):
        expected_time, expected_kind, expected_event_index, expected_direction = descriptor
        _record_parity(
            errors,
            f"snapshot.{index}.descriptor_time",
            snapshot.time_s,
            expected_time,
            1.0e-30,
        )
        if snapshot.snapshot_kind != expected_kind:
            errors.append((f"snapshot.{index}.snapshot_kind", math.inf))
        if snapshot.event_index != expected_event_index:
            errors.append((f"snapshot.{index}.event_index", math.inf))
        if snapshot.event_direction != expected_direction:
            errors.append((f"snapshot.{index}.event_direction", math.inf))
    for index, snapshot in enumerate(snapshots):
        matches = [
            item
            for item in references
            if abs(item[0] - float(snapshot.time_s))
            <= max(1.0e-18, abs(float(snapshot.time_s)) * 1.0e-12)
        ]
        if len(matches) != 1:
            errors.append((f"snapshot.{index}.time_match", math.inf))
            continue
        _, state, potential, joule = matches[0]
        for name, candidate, reference, scale in (
            ("temperature_K", snapshot.temperature_K, state.temperature_K, 7.19),
            ("conductive_state", snapshot.conductive_state, state.conductive_state, 1.0),
            ("branch_memory", snapshot.branch_memory, state.branch_memory, 1.0),
            ("potential_V", snapshot.potential_V, potential, 12.5),
            ("cell_joule_power_W", snapshot.cell_joule_power_W, joule, 1.0e-30),
        ):
            _record_parity(
                errors, f"snapshot.{index}.{name}", candidate, reference, scale
            )
    return _parity_summary(errors)


def _history_streaming_event_parity(
    initial_state: S2State,
    result: Any,
    config: dict[str, Any],
    grid: Any,
) -> dict[str, Any]:
    """Reconstruct locked fixed-grid events from the retained accepted path."""

    event_definition = config["metric_contract"]["event_definition"]
    threshold = float(event_definition["threshold"])
    separation = float(event_definition["minimum_separation_s"])
    previous_time = float(initial_state.time_s)
    previous_signal = _area_mean(initial_state.conductive_state, grid)
    reconstructed: list[dict[str, Any]] = []
    history = tuple(result.protocol_result.steps)
    for scalar in result.scalar_records[1:]:
        current_time = float(scalar["time_s"])
        matches = [
            step
            for step in history
            if abs(float(step.state.time_s) - current_time)
            <= max(1.0e-18, abs(current_time) * 1.0e-12)
        ]
        if len(matches) != 1:
            return {
                "pass": False,
                "reconstructed_count": len(reconstructed),
                "streamed_count": len(result.event_records),
                "maximum_relative_error": math.inf,
                "worst_component": "fixed_grid_history_match",
            }
        candidate = matches[0]
        current_signal = _area_mean(candidate.state.conductive_state, grid)
        direction: str | None = None
        if previous_signal < threshold <= current_signal:
            direction = "upward"
        elif previous_signal > threshold >= current_signal:
            direction = "downward"
        denominator = current_signal - previous_signal
        if direction is not None and denominator != 0.0:
            fraction = (threshold - previous_signal) / denominator
            crossing = previous_time + fraction * (current_time - previous_time)
            if not reconstructed or (
                crossing - float(reconstructed[-1]["crossing_time_s"])
                >= separation - 1.0e-18
            ):
                nonlinear = candidate.nonlinear
                reconstructed.append(
                    {
                        "case_id": result.case_id,
                        "event_index": len(reconstructed) + 1,
                        "direction": direction,
                        "crossing_time_s": float(crossing),
                        "before_sample_time_s": float(previous_time),
                        "after_sample_time_s": float(current_time),
                        "before_signal": float(previous_signal),
                        "after_signal": float(current_signal),
                        "nonlinear_method": str(nonlinear.method),
                        "nonlinear_iterations": int(nonlinear.iterations),
                        "krylov_matvecs": int(nonlinear.krylov_matvecs),
                        "armijo_backtracks": int(nonlinear.armijo_backtracks),
                        "predictor_picard_iterations": int(
                            nonlinear.predictor_picard_iterations
                        ),
                        "fallback_picard_iterations": int(
                            nonlinear.fallback_picard_iterations
                        ),
                        "scaled_residual_inf": float(nonlinear.scaled_residual_inf),
                        "scaled_update_inf": float(nonlinear.scaled_update_inf),
                        "nonlinear_converged": bool(nonlinear.converged),
                    }
                )
        previous_time = current_time
        previous_signal = current_signal
    streamed = tuple(result.event_records)
    if len(reconstructed) != len(streamed):
        return {
            "pass": False,
            "reconstructed_count": len(reconstructed),
            "streamed_count": len(streamed),
            "maximum_relative_error": math.inf,
            "worst_component": "event_count",
        }
    errors: list[tuple[str, float]] = []
    for index, (expected, observed) in enumerate(
        zip(reconstructed, streamed, strict=True)
    ):
        if set(expected) != set(observed):
            errors.append((f"event.{index}.field_set", math.inf))
            continue
        for name, value in expected.items():
            if isinstance(value, (bool, str, int)):
                if observed[name] != value:
                    errors.append((f"event.{index}.{name}", math.inf))
            else:
                scale = 1.0 if "signal" in name else 1.0e-9 if "time" in name else 1.0e-30
                _record_parity(
                    errors, f"event.{index}.{name}", observed[name], value, scale
                )
    parity = _parity_summary(errors)
    return {
        **parity,
        "reconstructed_count": len(reconstructed),
        "streamed_count": len(streamed),
    }


def _history_streaming_reversal_parity(
    initial_state: S2State,
    result: Any,
    closure: Any,
    grid: Any,
) -> dict[str, Any]:
    """Independently reconstruct accepted-fine branch reversals, without a solve."""

    previous_temperature = np.asarray(initial_state.temperature_K, dtype=float)
    previous_s = np.asarray(initial_state.conductive_state, dtype=float)
    previous_b = np.asarray(initial_state.branch_memory, dtype=float)
    previous_voltage = float(initial_state.device_voltage_V)
    previous_time = float(initial_state.time_s)
    previous_direction = np.zeros(grid.shape, dtype=np.int8)
    last_nonneutral_stop = np.full(grid.shape, previous_time, dtype=float)
    expected: list[dict[str, Any]] = []
    for accepted in result.protocol_result.steps:
        for candidate, nonlinear in (
            (accepted.accepted_first_half, accepted.accepted_first_half.nonlinear),
            (accepted, accepted.controller.second_half_nonlinear),
        ):
            current_time = float(candidate.state.time_s)
            dt = current_time - previous_time
            heating, cooling = closure.branch_activations(
                candidate.state.temperature_K, previous_temperature, dt
            )
            heating_mask = np.asarray(heating > 0.0, dtype=bool)
            cooling_mask = np.asarray(cooling > 0.0, dtype=bool)
            if np.any(heating_mask & cooling_mask):
                return {
                    "pass": False,
                    "maximum_relative_error": math.inf,
                    "worst_component": "direction_ambiguous",
                    "reconstructed_count": len(expected),
                    "streamed_count": len(result.reversal_records),
                }
            direction = np.zeros(grid.shape, dtype=np.int8)
            direction[heating_mask] = 1
            direction[cooling_mask] = -1
            h_to_c = (previous_direction == 1) & (direction == -1)
            c_to_h = (previous_direction == -1) & (direction == 1)
            mask = h_to_c | c_to_h
            if np.any(mask):
                magnitude = np.maximum(heating, cooling)
                flat_index = int(np.argmax(np.where(mask, magnitude, -1.0)))
                iy, ix = np.unravel_index(flat_index, grid.shape)

                def mask_hash(value: np.ndarray) -> str:
                    packed = np.packbits(
                        value.reshape(-1).astype(np.uint8), bitorder="little"
                    ).tobytes()
                    return hashlib.sha256(packed).hexdigest()

                expected.append(
                    {
                        "case_id": result.case_id,
                        "reversal_index": len(expected) + 1,
                        "direction": (
                            "mixed_local_reversals"
                            if np.any(h_to_c) and np.any(c_to_h)
                            else "heating_to_cooling"
                            if np.any(h_to_c)
                            else "cooling_to_heating"
                        ),
                        "heating_to_cooling_cell_count": int(np.count_nonzero(h_to_c)),
                        "cooling_to_heating_cell_count": int(np.count_nonzero(c_to_h)),
                        "affected_cell_count": int(np.count_nonzero(mask)),
                        "affected_mask_sha256": mask_hash(mask),
                        "heating_to_cooling_mask_sha256": mask_hash(h_to_c),
                        "cooling_to_heating_mask_sha256": mask_hash(c_to_h),
                        "detection_interval_start_s": previous_time,
                        "detection_interval_stop_s": current_time,
                        "detection_time_s": current_time,
                        "representative_prior_nonneutral_stop_s": float(
                            last_nonneutral_stop[iy, ix]
                        ),
                        "time_semantics": (
                            "accepted_fine_path_detection_interval; no subinterval "
                            "reversal-time interpolation"
                        ),
                        "representative_cell_iy": int(iy),
                        "representative_cell_ix": int(ix),
                        "representative_cell_x_m": float(grid.x_centers_m[ix]),
                        "representative_cell_y_m": float(grid.y_centers_m[iy]),
                        "representative_T_before_K": float(previous_temperature[iy, ix]),
                        "representative_T_after_K": float(
                            candidate.state.temperature_K[iy, ix]
                        ),
                        "representative_s_before": float(previous_s[iy, ix]),
                        "representative_s_after": float(
                            candidate.state.conductive_state[iy, ix]
                        ),
                        "representative_b_before": float(previous_b[iy, ix]),
                        "representative_b_after": float(
                            candidate.state.branch_memory[iy, ix]
                        ),
                        "representative_heating_activation": float(heating[iy, ix]),
                        "representative_cooling_activation": float(cooling[iy, ix]),
                        "device_voltage_before_V": previous_voltage,
                        "device_voltage_after_V": float(candidate.state.device_voltage_V),
                        "nonlinear_method": str(nonlinear.method),
                        "nonlinear_iterations": int(nonlinear.iterations),
                        "krylov_matvecs": int(nonlinear.krylov_matvecs),
                        "armijo_backtracks": int(nonlinear.armijo_backtracks),
                        "fallback_picard_iterations": int(
                            nonlinear.fallback_picard_iterations
                        ),
                        "predictor_picard_iterations": int(
                            nonlinear.predictor_picard_iterations
                        ),
                        "scaled_residual_inf": float(nonlinear.scaled_residual_inf),
                        "scaled_update_inf": float(nonlinear.scaled_update_inf),
                        "nonlinear_converged": bool(nonlinear.converged),
                    }
                )
            nonneutral = direction != 0
            last_nonneutral_stop = np.where(
                nonneutral, current_time, last_nonneutral_stop
            )
            previous_direction = np.where(
                nonneutral, direction, previous_direction
            ).astype(np.int8, copy=False)
            previous_temperature = np.asarray(candidate.state.temperature_K, dtype=float)
            previous_s = np.asarray(candidate.state.conductive_state, dtype=float)
            previous_b = np.asarray(candidate.state.branch_memory, dtype=float)
            previous_voltage = float(candidate.state.device_voltage_V)
            previous_time = current_time
    observed = tuple(result.reversal_records)
    if len(expected) != len(observed):
        return {
            "pass": False,
            "maximum_relative_error": math.inf,
            "worst_component": "reversal_count",
            "reconstructed_count": len(expected),
            "streamed_count": len(observed),
        }
    errors: list[tuple[str, float]] = []
    for index, (left, right) in enumerate(zip(expected, observed, strict=True)):
        if set(left) != set(right):
            errors.append((f"reversal.{index}.field_set", math.inf))
            continue
        for name, value in left.items():
            if isinstance(value, (bool, str, int)):
                if right[name] != value:
                    errors.append((f"reversal.{index}.{name}", math.inf))
            else:
                scale = 7.19 if "T_" in name else 12.5 if "voltage" in name else 1.0
                _record_parity(
                    errors, f"reversal.{index}.{name}", right[name], value, scale
                )
    parity = _parity_summary(errors)
    return {
        **parity,
        "reconstructed_count": len(expected),
        "streamed_count": len(observed),
    }


def _streamed_path_integrity(
    scalar_rows: tuple[dict[str, Any], ...], config: dict[str, Any]
) -> dict[str, Any]:
    """Audit all path telemetry emitted at fixed accepted-path records."""

    path_prefixes = ("full", "first_half", "second_half")
    ledger_names = ("thermal", "circuit", "combined", "device_power")
    gates = config["gates"]
    limits = {
        "thermal": float(gates["thermal_ledger_relative_residual_max"]),
        "circuit": float(gates["circuit_ledger_relative_residual_max"]),
        "combined": float(gates["combined_ledger_relative_residual_max"]),
        "device_power": float(gates["device_power_identity_relative_residual_max"]),
    }
    maxima = {name: 0.0 for name in ledger_names}
    lateral_relative = 0.0
    lateral_roundoff = 0.0
    passed = True
    for row in scalar_rows:
        for prefix in path_prefixes:
            passed = passed and all(
                row.get(f"{prefix}_{name}") is True
                for name in (
                    "finite",
                    "nonlinear_pass",
                    "ledger_pass",
                    "lateral_pass",
                    "overall_pass",
                )
            )
            relative = float(row[f"{prefix}_lateral_relative_mismatch"])
            roundoff = float(row[f"{prefix}_lateral_roundoff_ratio"])
            lateral_relative = max(lateral_relative, relative)
            lateral_roundoff = max(lateral_roundoff, roundoff)
            passed = passed and bool(relative <= 1.0e-10 or roundoff <= 1.0)
            for ledger in ledger_names:
                residual = float(row[f"{prefix}_{ledger}_relative_residual"])
                maxima[ledger] = max(maxima[ledger], residual)
                passed = passed and residual <= limits[ledger]
        passed = passed and all(
            row.get(f"aggregate_{name}") is True
            for name in ("finite", "ledger_pass", "overall_pass")
        )
        for ledger in ledger_names:
            residual = float(row[f"aggregate_{ledger}_relative_residual"])
            maxima[ledger] = max(maxima[ledger], residual)
            passed = passed and residual <= limits[ledger]
        passed = passed and float(row["e_max"]) <= 0.02
    return {
        "pass": bool(passed),
        "ledger_maxima": maxima,
        "lateral_relative_max": lateral_relative,
        "lateral_roundoff_max": lateral_roundoff,
    }


def _streaming_output_bytes(result: Any) -> int:
    scalar = json.dumps(result.scalar_records, default=str, allow_nan=False).encode()
    events = json.dumps(result.event_records, default=str, allow_nan=False).encode()
    reversals = json.dumps(
        result.reversal_records, default=str, allow_nan=False
    ).encode()
    arrays = sum(
        int(array.nbytes)
        for snapshot in result.field_snapshots
        for array in (
            snapshot.temperature_K,
            snapshot.conductive_state,
            snapshot.branch_memory,
            snapshot.potential_V,
            snapshot.cell_joule_power_W,
        )
    )
    return len(scalar) + len(events) + len(reversals) + arrays


def _trajectory_row(
    *,
    sample_id: str,
    level: int,
    state_id: str,
    result: Any,
    config: dict[str, Any],
    grid: Any,
    initial_state: S2State,
    wall_clock_s: float,
    require_history_parity: bool,
    actual_streaming_output_bytes: int | None = None,
    streaming_publish_wall_s: float | None = None,
    streaming_io_measurement_status: str = "not_measured",
) -> dict[str, Any]:
    diagnostics = result.protocol_result.diagnostics
    steps = tuple(result.protocol_result.steps)
    finite = bool(
        np.isfinite(result.final_state.temperature_K).all()
        and np.isfinite(result.final_state.conductive_state).all()
        and np.isfinite(result.final_state.branch_memory).all()
        and np.isfinite(result.final_state.device_voltage_V)
    )
    scalar_rows = tuple(result.scalar_records[1:])
    streamed_integrity = _streamed_path_integrity(scalar_rows, config)
    history_integrity = bool(
        not require_history_parity
        or (steps and all(_embedded_step_integrity(step, config) for step in steps))
    )
    parity = (
        _history_streaming_parity(
            initial_state, result, grid, config, _protocol_id(state_id)
        )
        if require_history_parity
        else {"pass": True, "maximum_relative_error": 0.0, "worst_component": ""}
    )
    output_bytes = int(actual_streaming_output_bytes or 0)
    scale = max(1, math.ceil(4001.0 / max(len(result.scalar_records), 1)))
    publish_wall = float(streaming_publish_wall_s or 0.0)
    embedded_max = max(
        (float(row["e_max"]) for row in scalar_rows),
        default=float(getattr(diagnostics, "maximum_e_max", 0.0)),
    )
    progression = bool(
        int(diagnostics.accepted_steps) > 0
        and float(result.protocol_result.achieved_final_time_s) > 0.0
    )
    status = (
        "pass"
        if finite
        and history_integrity
        and streamed_integrity["pass"]
        and parity["pass"]
        and progression
        else "fail"
    )
    return {
        "sample_id": sample_id,
        "sample_kind": "short_trajectory",
        "spatial_level": level,
        "nx": grid.nx,
        "ny": grid.ny,
        "state_id": state_id,
        "interval_class": "adaptive_controller_v2",
        "protocol_id": _protocol_id(state_id),
        "status": status,
        "failure_class": "" if status == "pass" else "controller_integrity",
        "error_class": "" if status == "pass" else "trajectory_integrity_or_parity_failure",
        "error_message": "",
        "accepted_steps": int(diagnostics.accepted_steps),
        "rejected_steps": int(diagnostics.rejected_steps),
        "coupled_solve_count": int(diagnostics.total_coupled_solves),
        "newton_iterations": int(diagnostics.newton_iterations),
        "krylov_matvecs": int(diagnostics.krylov_matvecs),
        "armijo_backtracks": int(diagnostics.armijo_backtracks),
        "fallback_steps": int(diagnostics.fallback_steps),
        "fallback_picard_iterations": int(diagnostics.fallback_picard_iterations),
        "step_wall_time_p50_s": float(diagnostics.step_wall_time_p50_s),
        "step_wall_time_p90_s": float(diagnostics.step_wall_time_p90_s),
        "step_wall_time_max_s": float(diagnostics.step_wall_time_max_s),
        "accepted_dt_p10_s": float(diagnostics.accepted_dt_p10_s),
        "accepted_dt_p50_s": float(diagnostics.accepted_dt_p50_s),
        "accepted_dt_p90_s": float(diagnostics.accepted_dt_p90_s),
        "achieved_simulated_time_s": float(result.protocol_result.achieved_final_time_s),
        "completed": bool(result.protocol_result.completed),
        "stop_reason": str(result.protocol_result.stop_reason),
        "finite": finite,
        "ledgers_pass": bool(history_integrity and streamed_integrity["pass"]),
        "lateral_pass": bool(history_integrity and streamed_integrity["pass"]),
        "embedded_error_max": embedded_max,
        "legacy_delta_s_max": float(diagnostics.maximum_transition_increment),
        "legacy_delta_b_max": max(
            (float(row["legacy_max_absolute_delta_b"]) for row in scalar_rows),
            default=0.0,
        ),
        "thermal_relative_residual_max": streamed_integrity["ledger_maxima"]["thermal"],
        "circuit_relative_residual_max": streamed_integrity["ledger_maxima"]["circuit"],
        "combined_relative_residual_max": streamed_integrity["ledger_maxima"]["combined"],
        "device_power_relative_residual_max": streamed_integrity["ledger_maxima"]["device_power"],
        "lateral_relative_mismatch_max": streamed_integrity["lateral_relative_max"],
        "lateral_roundoff_ratio_max": streamed_integrity["lateral_roundoff_max"],
        "peak_rss_bytes": int(process_memory().peak_working_set_bytes),
        "streaming_output_bytes": output_bytes,
        "scalar_record_count": len(result.scalar_records),
        "predicted_full_streaming_bytes": int(math.ceil(output_bytes * scale)),
        "predicted_full_streaming_io_s": publish_wall * scale,
        "parity_max_relative_error": parity["maximum_relative_error"],
        "cached_uncached_parity_pass": "",
        "cached_uncached_parity_max_relative_error": "",
        "cached_uncached_parity_worst_component": "",
        "uncached_parity_wall_s": "",
        "streaming_publish_wall_s": publish_wall,
        "streaming_io_measurement_status": streaming_io_measurement_status,
        "event_observation": c2_event_observation(
            result.event_records, result.reversal_records
        ),
    }


def _dormant_runner_dry_run(authority: LockedAuthority) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pinn-phase1v2-controller-runner-") as directory:
        root = Path(directory)
        prepared = create_prepared_registry(
            root,
            run_id="PRE-CTRL-RUNNER-PASS",
            identity_hashes=authority.identity_hashes,
            execution_dag=authority.execution_dag,
            environment_summary=authority.environment,
        )
        begin_running(prepared.path)
        partial = create_partial_case_work(
            prepared.path, "PRE-CTRL-UNIT-A", {"synthetic_step": 1}
        )
        interrupt_resumable(
            prepared.path,
            reason="injected interruption",
            partial_case_id="PRE-CTRL-UNIT-A",
        )
        unpublished = not (
            prepared.path / "cases" / "PRE-CTRL-UNIT-A.json"
        ).exists()
        resume_same_run(
            prepared.path,
            run_id="PRE-CTRL-RUNNER-PASS",
            expected_identity_hashes=authority.identity_hashes,
        )
        publish_synthetic_case(
            prepared.path,
            case_id="PRE-CTRL-UNIT-A",
            outcome="pass",
            classification="synthetic_pass",
            payload={"synthetic_step": 2},
        )
        passed = complete_pass(prepared.path)

        mismatch = create_prepared_registry(
            root,
            run_id="PRE-CTRL-RUNNER-HASH",
            identity_hashes=authority.identity_hashes,
            execution_dag=authority.execution_dag,
            environment_summary=authority.environment,
        )
        begin_running(mismatch.path)
        interrupt_resumable(mismatch.path, reason="injected interruption")
        changed = dict(authority.identity_hashes)
        changed["resolved_runtime_identity"] = "0" * 64
        mismatch_rejected = False
        try:
            resume_same_run(
                mismatch.path,
                run_id="PRE-CTRL-RUNNER-HASH",
                expected_identity_hashes=changed,
            )
        except InvalidContractError:
            mismatch_rejected = True
        mismatch_state = load_registry(mismatch.path).state

        foundation = create_prepared_registry(
            root,
            run_id="PRE-CTRL-RUNNER-FOUNDATION",
            identity_hashes=authority.identity_hashes,
            execution_dag=authority.execution_dag,
            environment_summary=authority.environment,
        )
        begin_running(foundation.path)
        foundation_view = record_foundation_failure(
            foundation.path,
            failing_case_id="PRE-CTRL-FOUNDATION-FAIL",
            remaining_case_ids=["PRE-CTRL-BLOCKED-A", "PRE-CTRL-BLOCKED-B"],
            reason="injected foundation failure",
        )
        blocked = json.loads(
            (
                foundation.path / "blocked" / "foundation_fail_fast.json"
            ).read_text(encoding="utf-8")
        )
        checks = {
            "coverage_63_60_3": passed.identity["coverage"]
            == {"evaluation_items": 63, "execution_units": 60, "legal_reuses": 3},
            "same_run_ID_resume": passed.state == "COMPLETED_PASS",
            "partial_case_not_published": unpublished,
            "per_case_atomic_completion": (
                prepared.path / "cases" / "PRE-CTRL-UNIT-A.json"
            ).exists()
            and not partial.exists(),
            "hash_mismatch_rejected": mismatch_rejected
            and mismatch_state == "INVALID_CONTRACT",
            "foundation_fail_fast": foundation_view.state
            == "COMPLETED_SCIENTIFIC_FAIL"
            and blocked["blocked_case_ids"]
            == ["PRE-CTRL-BLOCKED-A", "PRE-CTRL-BLOCKED-B"],
            "formal_count_zero": passed.identity["formal_execution_count"] == 0,
            "formal_dispatch_disabled": passed.identity[
                "formal_unit_dispatch_enabled"
            ]
            is False,
        }
        return {
            "task_id": "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION",
            "schema_version": "geophase_phase1_v2_controller_runner_dry_run_v1",
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "registry_location": "temporary_directory_only",
            "run_ID_prefix": "PRE-CTRL-",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }


class _RealReadinessExecution:
    def __init__(
        self, authority: LockedAuthority, started_s: float, io_measurement_root: Path
    ) -> None:
        self.authority = authority
        self.config = authority.config
        self.started_s = started_s
        self.deadline_s = started_s + PREFLIGHT_LIMIT_S
        self.io_measurement_root = Path(io_measurement_root)
        self.contexts: dict[int, tuple[Any, Any, Any, Any]] = {}
        self.samples: list[dict[str, Any]] = []
        self.cost_rows: list[dict[str, Any]] = []
        self.forecast: dict[str, Any] = {}
        self.runner: dict[str, Any] = {"status": "not_reached"}
        self.c2_sample: dict[str, Any] | None = None

    def remaining_budget_s(self) -> float:
        return max(0.0, self.deadline_s - perf_counter())

    def context(self, level: int) -> tuple[Any, Any, Any, Any]:
        if level not in self.contexts:
            grid = build_geophase_grid(self.config, spatial_level=level)
            fields = build_s2_thermal_fields(grid, self.config)
            closure = effective_vo2_closure_from_v2_config(self.config)
            cache = build_s2_solver_cache(grid, fields)
            self.contexts[level] = (grid, fields, closure, cache)
        return self.contexts[level]

    def _budget_exhausted_sample(
        self,
        spec: dict[str, Any],
        *,
        sample_kind: str,
        reason: str,
        grid: Any | None = None,
        cached_wall_s: float = 0.0,
        uncached_wall_s: float = 0.0,
    ) -> dict[str, Any]:
        level = int(spec["spatial_level"])
        state_id = str(spec["state_id"])
        return {
            "sample_id": str(spec["sample_id"]),
            "sample_kind": sample_kind,
            "spatial_level": level,
            "nx": "" if grid is None else int(grid.nx),
            "ny": "" if grid is None else int(grid.ny),
            "state_id": state_id,
            "interval_class": str(
                spec.get("interval_class", "adaptive_controller_v2")
            ),
            "protocol_id": _protocol_id(state_id),
            "status": "budget_exhausted",
            "failure_class": "performance_only",
            "error_class": "runtime_evidence_insufficient",
            "error_message": reason,
            "accepted_steps": 0,
            "rejected_steps": 0,
            "coupled_solve_count": 0,
            "step_wall_time_p50_s": float(cached_wall_s),
            "step_wall_time_p90_s": float(cached_wall_s),
            "step_wall_time_max_s": float(cached_wall_s),
            "achieved_simulated_time_s": 0.0,
            "completed": False,
            "stop_reason": reason,
            "finite": "",
            "ledgers_pass": "",
            "lateral_pass": "",
            "peak_rss_bytes": int(process_memory().peak_working_set_bytes),
            "uncached_parity_wall_s": float(uncached_wall_s),
            "streaming_publish_wall_s": 0.0,
            "streaming_io_measurement_status": "not_reached_by_runtime_budget",
        }

    def run_c1(self, remaining_s: float) -> dict[str, Any]:
        available = min(float(remaining_s), self.remaining_budget_s()) - OUTPUT_RESERVE_S
        if available <= 0.0:
            return {
                "status": "fail",
                "failure_class": "performance_only",
                "reason": "readiness_budget_exhausted_before_C1",
            }
        grid, fields, closure, cache = self.context(1)
        initial = _deterministic_state(
            "legal_critical", grid=grid, closure=closure, fields=fields
        )
        protocol_id = "transition_probe_12p5V"
        started = perf_counter()
        try:
            result = run_s2_streaming_protocol_v2(
                "PRE-CTRL-LEGAL-CRITICAL",
                initial,
                protocol=self.config["formal_protocols"]["protocols"][protocol_id],
                protocol_id=protocol_id,
                grid=grid,
                closure=closure,
                fields=fields,
                config=self.config,
                time_divisor=1,
                final_time_s=2.0e-8,
                maximum_wall_clock_s=available,
                retain_full_history=True,
                cache=cache,
                use_equivalent_optimizations=True,
                use_unit_voltage_scaling=False,
            )
            parity = _history_streaming_parity(
                initial, result, grid, self.config, protocol_id
            )
            event_parity = _history_streaming_event_parity(
                initial, result, self.config, grid
            )
            reversal_parity = _history_streaming_reversal_parity(
                initial, result, closure, grid
            )
            steps = tuple(result.protocol_result.steps)
            integrity = bool(
                steps
                and all(_embedded_step_integrity(step, self.config) for step in steps)
            )
            path_integrity = {
                "full_step": all(step.controller.full_step.overall_pass for step in steps),
                "first_half_step": all(
                    step.controller.first_half_step is not None
                    and step.controller.first_half_step.overall_pass
                    for step in steps
                ),
                "second_half_step": all(
                    step.controller.second_half_step is not None
                    and step.controller.second_half_step.overall_pass
                    for step in steps
                ),
                "aggregate": all(
                    step.controller.aggregate is not None
                    and step.controller.aggregate.overall_pass
                    for step in steps
                ),
            }
            voltage_scales = sorted(
                {
                    float(step.controller.embedded_error.voltage_scale_V)
                    for step in steps
                    if step.controller.embedded_error is not None
                }
            )
            budget_exceeded = self.remaining_budget_s() <= OUTPUT_RESERVE_S
            passed = bool(
                result.protocol_result.completed
                and int(result.protocol_result.diagnostics.accepted_steps) > 0
                and integrity
                and parity["pass"]
                and event_parity["pass"]
                and reversal_parity["pass"]
                and voltage_scales == [12.5]
                and not budget_exceeded
            )
            timed_out = (
                result.protocol_result.stop_reason == "maximum_wall_clock_reached"
                or budget_exceeded
            )
            observed_integrity_failure = bool(
                steps
                and (
                    not integrity
                    or not parity["pass"]
                    or not event_parity["pass"]
                    or not reversal_parity["pass"]
                )
            )
            return {
                "status": "pass" if passed else "fail",
                "failure_class": None
                if passed
                else "performance_only"
                if timed_out and not observed_integrity_failure
                else "controller_integrity",
                "sample_id": "PRE-CTRL-LEGAL-CRITICAL",
                "single_numerical_run": True,
                "accepted_interval_count": int(
                    result.protocol_result.diagnostics.accepted_steps
                ),
                "full_history_and_streaming_same_run": True,
                "full_history_streaming_parity": parity,
                "accepted_fine_event_parity": event_parity,
                "accepted_fine_reversal_parity": reversal_parity,
                "maximum_embedded_error": float(
                    result.protocol_result.diagnostics.maximum_e_max
                ),
                "path_integrity": path_integrity,
                "protocol_voltage_scale_V": voltage_scales,
                "finite_nonlinear_ledger_lateral_pass": integrity,
                "completed": bool(result.protocol_result.completed),
                "stop_reason": str(result.protocol_result.stop_reason),
                "wall_clock_s": perf_counter() - started,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }
        except Exception as error:
            if not _is_observed_controller_failure(error):
                raise
            return {
                "status": "fail",
                "failure_class": "controller_integrity",
                "sample_id": "PRE-CTRL-LEGAL-CRITICAL",
                "single_numerical_run": True,
                "error_class": type(error).__name__,
                "error_message": str(error),
                "wall_clock_s": perf_counter() - started,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }

    def run_c2(
        self, remaining_s: float, maximum_intervals: int, stop_s: float
    ) -> dict[str, Any]:
        available = min(float(remaining_s), self.remaining_budget_s()) - OUTPUT_RESERVE_S
        if available <= 0.0:
            return {
                "status": "pass",
                "failure_class": None,
                "stop_reason": "C2_truncated_by_readiness_budget",
                "runtime_evidence_sufficient": False,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }
        grid, fields, closure, cache = self.context(1)
        initial = _deterministic_state(
            "legal_critical", grid=grid, closure=closure, fields=fields
        )
        protocol_id = "transition_probe_12p5V"
        started = perf_counter()
        try:
            result = run_s2_streaming_protocol_v2(
                "PRE-CTRL-C2-L1-legal_critical",
                initial,
                protocol=self.config["formal_protocols"]["protocols"][protocol_id],
                protocol_id=protocol_id,
                grid=grid,
                closure=closure,
                fields=fields,
                config=self.config,
                final_time_s=stop_s,
                maximum_accepted_steps=maximum_intervals,
                maximum_wall_clock_s=available,
                retain_full_history=True,
                cache=cache,
                use_equivalent_optimizations=True,
                use_unit_voltage_scaling=False,
            )
            wall = perf_counter() - started
            row = _trajectory_row(
                sample_id="PRE-CTRL-C2-L1-legal_critical",
                level=1,
                state_id="legal_critical",
                result=result,
                config=self.config,
                grid=grid,
                initial_state=initial,
                wall_clock_s=wall,
                require_history_parity=True,
                actual_streaming_output_bytes=0,
                streaming_publish_wall_s=0.0,
                streaming_io_measurement_status="not_measured_C2_reuse_with_history",
            )
            event_parity = _history_streaming_event_parity(
                initial, result, self.config, grid
            )
            reversal_parity = _history_streaming_reversal_parity(
                initial, result, closure, grid
            )
            if not event_parity["pass"] or not reversal_parity["pass"]:
                row["status"] = "fail"
                row["failure_class"] = "controller_integrity"
                row["error_class"] = "accepted_fine_event_or_reversal_parity_failure"
            states = [initial, *(step.state for step in result.protocol_result.steps)]
            bounded = all(
                np.all(state.conductive_state >= -1.0e-12)
                and np.all(state.conductive_state <= 1.0 + 1.0e-12)
                and np.all(state.branch_memory >= -1.0 - 1.0e-12)
                and np.all(state.branch_memory <= 1.0 + 1.0e-12)
                and np.all(
                    state.temperature_K
                    >= float(closure.temperature_min_K) - 1.0e-9
                )
                and np.all(
                    state.temperature_K
                    <= float(closure.temperature_max_K) + 1.0e-9
                )
                and -1.0e-12 <= float(state.device_voltage_V) <= 12.5 + 1.0e-9
                for state in states
            )
            if not bounded:
                row["status"] = "fail"
                row["failure_class"] = "controller_integrity"
                row["error_class"] = "bounded_state_failure"
            self.c2_sample = dict(row)
            self.samples.append(dict(row))
            truncated = bool(
                result.protocol_result.stop_reason == "maximum_wall_clock_reached"
                or self.remaining_budget_s() <= OUTPUT_RESERVE_S
            )
            stop_reason = (
                "C2_truncated_by_readiness_budget"
                if truncated
                else str(result.protocol_result.stop_reason)
            )
            sufficient = bool(
                row["status"] == "pass"
                and int(row["accepted_steps"]) > 0
                and float(row["achieved_simulated_time_s"]) > 0.0
                and float(row["step_wall_time_p90_s"]) > 0.0
            )
            if truncated and not result.protocol_result.steps:
                row["status"] = "budget_truncated"
                row["failure_class"] = "performance_only"
                row["error_class"] = "runtime_evidence_insufficient"
                self.c2_sample = dict(row)
                self.samples[-1] = dict(row)
                sufficient = False
            return {
                "status": "pass" if truncated and not result.protocol_result.steps else str(row["status"]),
                "failure_class": None
                if row["status"] in {"pass", "budget_truncated"}
                else "controller_integrity",
                "sample_id": row["sample_id"],
                "maximum_accepted_intervals": maximum_intervals,
                "maximum_simulated_time_s": stop_s,
                "accepted_interval_count": row["accepted_steps"],
                "achieved_simulated_time_s": row["achieved_simulated_time_s"],
                "stop_reason": stop_reason,
                "event_observation": c2_event_observation(
                    result.event_records, result.reversal_records
                ),
                "events": list(result.event_records),
                "reversals": list(result.reversal_records),
                "accepted_fine_event_parity": event_parity,
                "accepted_fine_reversal_parity": reversal_parity,
                "state_bounds_pass": bounded,
                "runtime_evidence_sufficient": sufficient,
                "forecast_sample_row": row,
                "wall_clock_s": wall,
                "formal_event_or_trend_vote": False,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }
        except Exception as error:
            if not _is_observed_controller_failure(error):
                raise
            return {
                "status": "fail",
                "failure_class": "controller_integrity",
                "sample_id": "PRE-CTRL-C2-L1-legal_critical",
                "error_class": type(error).__name__,
                "error_message": str(error),
                "runtime_evidence_sufficient": False,
                "wall_clock_s": perf_counter() - started,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }

    def _single_interval_row(self, spec: dict[str, Any]) -> dict[str, Any]:
        level = int(spec["spatial_level"])
        state_id = str(spec["state_id"])
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return self._budget_exhausted_sample(
                spec,
                sample_kind="single_interval",
                reason="runtime_budget_exhausted_before_single_interval_context",
            )
        grid, fields, closure, cache = self.context(level)
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return self._budget_exhausted_sample(
                spec,
                sample_kind="single_interval",
                reason="runtime_budget_exhausted_after_single_interval_context",
                grid=grid,
            )
        initial = _deterministic_state(
            state_id, grid=grid, closure=closure, fields=fields
        )
        protocol_id = _protocol_id(state_id)
        maximum_H, floor_H = controller_v2_limits(self.config, 1)
        H = maximum_H if spec["interval_class"] == "base" else floor_H
        protocol = self.config["formal_protocols"]["protocols"][protocol_id]
        cached_started = perf_counter()
        try:
            observation = attempt_s2_embedded_interval(
                initial,
                protocol=protocol,
                protocol_id=protocol_id,
                outer_interval_s=H,
                grid=grid,
                closure=closure,
                fields=fields,
                config=self.config,
                at_outer_floor=bool(spec["interval_class"] == "floor"),
                cache=cache,
                use_equivalent_optimizations=True,
                use_unit_voltage_scaling=False,
            )
            wall = perf_counter() - cached_started
            cached_error: Exception | None = None
        except Exception as error:
            raise RuntimeError(
                "cached single-interval execution infrastructure failed"
            ) from error
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return self._budget_exhausted_sample(
                spec,
                sample_kind="single_interval",
                reason="runtime_budget_exhausted_after_cached_interval",
                grid=grid,
                cached_wall_s=wall,
            )
        uncached_initial = _deterministic_state(
            state_id, grid=grid, closure=closure, fields=fields
        )
        uncached_started = perf_counter()
        try:
            uncached = attempt_s2_embedded_interval(
                uncached_initial,
                protocol=protocol,
                protocol_id=protocol_id,
                outer_interval_s=H,
                grid=grid,
                closure=closure,
                fields=fields,
                config=self.config,
                at_outer_floor=bool(spec["interval_class"] == "floor"),
                cache=None,
                use_equivalent_optimizations=False,
                use_unit_voltage_scaling=False,
            )
            uncached_error: Exception | None = None
        except Exception as error:
            raise RuntimeError(
                "uncached single-interval execution infrastructure failed"
            ) from error
        uncached_wall = perf_counter() - uncached_started
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return self._budget_exhausted_sample(
                spec,
                sample_kind="single_interval",
                reason="runtime_budget_exhausted_after_uncached_interval",
                grid=grid,
                cached_wall_s=wall,
                uncached_wall_s=uncached_wall,
            )
        try:
            if cached_error is not None or uncached_error is not None:
                raise RuntimeError(
                    "cached_or_uncached_interval_exception: "
                    f"cached={cached_error!r}; uncached={uncached_error!r}"
                )
            assert observation is not None and uncached is not None
            parity = _compare_attempt_observations(
                observation,
                uncached,
                voltage_scale=float(
                    self.config["reference_solver"]["active_time_controller"]
                    ["voltage_scale"]["protocol_V_scale_V"][protocol_id]
                ),
            )
            step = observation.step
            integrity = _attempt_integrity_values(observation, self.config)
            uncached_integrity = _attempt_integrity_values(uncached, self.config)
            embedded = observation.diagnostics.embedded_error
            uncached_embedded = uncached.diagnostics.embedded_error
            error_pass = bool(
                integrity["overall_pass"]
                and embedded is not None
                and float(embedded.e_max) <= 0.02
                and step is not None
            )
            valid_rejection = bool(
                spec["interval_class"] == "base"
                and integrity["overall_pass"]
                and embedded is not None
                and float(embedded.e_max) > 0.02
                and observation.error_class is None
            )
            uncached_error_pass = bool(
                uncached_integrity["overall_pass"]
                and uncached_embedded is not None
                and float(uncached_embedded.e_max) <= 0.02
                and uncached.step is not None
            )
            uncached_valid_rejection = bool(
                spec["interval_class"] == "base"
                and uncached_integrity["overall_pass"]
                and uncached_embedded is not None
                and float(uncached_embedded.e_max) > 0.02
                and uncached.error_class is None
            )
            cached_status = (
                "pass" if error_pass else "valid_rejection" if valid_rejection else "fail"
            )
            uncached_status = (
                "pass"
                if uncached_error_pass
                else "valid_rejection"
                if uncached_valid_rejection
                else "fail"
            )
            status = (
                cached_status
                if parity["pass"] and cached_status == uncached_status
                else "fail"
            )
            candidates = tuple(
                candidate
                for candidate in (
                    observation.full_candidate,
                    observation.first_half_candidate,
                    observation.second_half_candidate,
                )
                if candidate is not None
            )
            return {
                "sample_id": spec["sample_id"],
                "sample_kind": "single_interval",
                "spatial_level": level,
                "nx": grid.nx,
                "ny": grid.ny,
                "state_id": state_id,
                "interval_class": spec["interval_class"],
                "outer_interval_s": H,
                "protocol_id": protocol_id,
                "status": status,
                "failure_class": "" if status != "fail" else "controller_integrity",
                "error_class": (
                    ""
                    if status != "fail"
                    else "cached_uncached_parity_or_interval_failure"
                ),
                "error_message": (
                    observation.error_message
                    or uncached.error_message
                    or (
                        ""
                        if status != "fail"
                        else f"cached={cached_status}; uncached={uncached_status}; "
                        f"worst={parity['worst_component']}"
                    )
                ),
                "accepted_steps": int(error_pass),
                "rejected_steps": int(not error_pass),
                "coupled_solve_count": observation.diagnostics.coupled_solve_count,
                "newton_iterations": sum(item.nonlinear.iterations for item in candidates),
                "krylov_matvecs": sum(item.nonlinear.krylov_matvecs for item in candidates),
                "armijo_backtracks": sum(item.nonlinear.armijo_backtracks for item in candidates),
                "fallback_steps": int(observation.diagnostics.any_fallback),
                "fallback_picard_iterations": sum(
                    item.nonlinear.fallback_picard_iterations for item in candidates
                ),
                "step_wall_time_p50_s": wall,
                "step_wall_time_p90_s": wall,
                "step_wall_time_max_s": wall,
                "accepted_dt_p10_s": H if error_pass else 0.0,
                "accepted_dt_p50_s": H if error_pass else 0.0,
                "accepted_dt_p90_s": H if error_pass else 0.0,
                "achieved_simulated_time_s": H if error_pass else 0.0,
                "completed": status != "fail",
                "stop_reason": "single_embedded_interval_completed"
                if error_pass
                else "valid_error_driven_rejection"
                if valid_rejection
                else "single_embedded_interval_failed",
                "finite": integrity["finite"],
                "embedded_error_max": math.inf if embedded is None else embedded.e_max,
                "legacy_delta_s_max": observation.diagnostics.legacy_conductive_increment,
                "legacy_delta_b_max": observation.diagnostics.legacy_branch_increment,
                "peak_rss_bytes": int(process_memory().peak_working_set_bytes),
                "cached_uncached_parity_pass": parity["pass"],
                "cached_uncached_parity_max_relative_error": parity[
                    "maximum_relative_error"
                ],
                "cached_uncached_parity_worst_component": parity["worst_component"],
                "uncached_parity_wall_s": uncached_wall,
                "streaming_publish_wall_s": 0.0,
                "streaming_io_measurement_status": "not_applicable_single_interval",
                **{
                    key: value
                    for key, value in integrity.items()
                    if key != "overall_pass" and key != "nonlinear_pass"
                },
            }
        except Exception as error:
            raise RuntimeError(
                "single-interval parity/evidence processing failed"
            ) from error

    def _short_trajectory_row(
        self, spec: dict[str, Any], remaining_s: float
    ) -> dict[str, Any]:
        level = int(spec["spatial_level"])
        state_id = str(spec["state_id"])
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return self._budget_exhausted_sample(
                spec,
                sample_kind="short_trajectory",
                reason="runtime_budget_exhausted_before_short_trajectory_context",
            )
        grid, fields, closure, cache = self.context(level)
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return self._budget_exhausted_sample(
                spec,
                sample_kind="short_trajectory",
                reason="runtime_budget_exhausted_after_short_trajectory_context",
                grid=grid,
            )
        initial = _deterministic_state(
            state_id, grid=grid, closure=closure, fields=fields
        )
        protocol_id = _protocol_id(state_id)
        started = perf_counter()
        try:
            result = run_s2_streaming_protocol_v2(
                str(spec["sample_id"]),
                initial,
                protocol=self.config["formal_protocols"]["protocols"][protocol_id],
                protocol_id=protocol_id,
                grid=grid,
                closure=closure,
                fields=fields,
                config=self.config,
                final_time_s=1.0e-6,
                maximum_accepted_steps=128,
                maximum_wall_clock_s=remaining_s,
                retain_full_history=False,
                cache=cache,
                use_equivalent_optimizations=True,
                use_unit_voltage_scaling=False,
            )
            solve_wall = perf_counter() - started
            if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
                return self._budget_exhausted_sample(
                    spec,
                    sample_kind="short_trajectory",
                    reason="runtime_budget_exhausted_before_streaming_publish",
                    grid=grid,
                    cached_wall_s=solve_wall,
                )
            publish_started = perf_counter()
            published = publish_pre_streaming_case(
                self.io_measurement_root,
                result,
                identity_hashes=self.authority.identity_hashes,
            )
            measured_bytes = published_case_bytes(published)
            publish_wall = perf_counter() - publish_started
            if self.remaining_budget_s() <= 0.0:
                return self._budget_exhausted_sample(
                    spec,
                    sample_kind="short_trajectory",
                    reason="runtime_budget_exhausted_after_streaming_publish",
                    grid=grid,
                    cached_wall_s=solve_wall,
                )
            return _trajectory_row(
                sample_id=str(spec["sample_id"]),
                level=level,
                state_id=state_id,
                result=result,
                config=self.config,
                grid=grid,
                initial_state=initial,
                wall_clock_s=solve_wall,
                require_history_parity=False,
                actual_streaming_output_bytes=measured_bytes,
                streaming_publish_wall_s=publish_wall,
                streaming_io_measurement_status="measured_atomic_publish",
            )
        except Exception as error:
            if not _is_observed_controller_failure(error):
                raise
            wall = perf_counter() - started
            return {
                "sample_id": spec["sample_id"],
                "sample_kind": "short_trajectory",
                "spatial_level": level,
                "nx": grid.nx,
                "ny": grid.ny,
                "state_id": state_id,
                "interval_class": "adaptive_controller_v2",
                "protocol_id": protocol_id,
                "status": "fail",
                "failure_class": "controller_integrity",
                "error_class": type(error).__name__,
                "error_message": str(error),
                "accepted_steps": 0,
                "coupled_solve_count": 0,
                "step_wall_time_p50_s": wall,
                "step_wall_time_p90_s": wall,
                "step_wall_time_max_s": wall,
                "achieved_simulated_time_s": 0.0,
                "completed": False,
                "stop_reason": "trajectory_exception",
                "finite": False,
                "ledgers_pass": False,
                "lateral_pass": False,
                "peak_rss_bytes": int(process_memory().peak_working_set_bytes),
            }

    def run_c3(
        self, remaining_s: float, reused_c2_row: dict[str, Any]
    ) -> dict[str, Any]:
        plan = build_c3_plan()
        for spec in plan["single_intervals"]:
            if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
                return {
                    "status": "fail",
                    "failure_class": "performance_only",
                    "reason": "runtime_evidence_insufficient_before_18_interval_matrix_completed",
                    "completed_single_intervals": len(self.samples),
                }
            row = self._single_interval_row(spec)
            self.samples.append(row)
            if row["status"] not in {"pass", "valid_rejection"}:
                return {
                    "status": "fail",
                    "failure_class": row.get(
                        "failure_class", "controller_integrity"
                    ),
                    "reason": f"{row['sample_id']}: {row.get('error_class')}",
                    "completed_single_intervals": sum(
                        item["sample_kind"] == "single_interval"
                        for item in self.samples
                    ),
                }

        for spec in plan["short_trajectories"]:
            if spec["reuse_C2"]:
                row = dict(reused_c2_row)
                existing = [
                    item
                    for item in self.samples
                    if item.get("sample_id") == row.get("sample_id")
                ]
                if len(existing) != 1 or existing[0] != row:
                    raise RuntimeError("C2 readiness reuse identity mismatch")
            else:
                remaining = (
                    self.remaining_budget_s() - OUTPUT_RESERVE_S
                )
                if remaining <= 0.0:
                    return {
                        "status": "fail",
                        "failure_class": "performance_only",
                        "reason": "runtime_evidence_insufficient_before_9_trajectory_matrix_completed",
                    }
                row = self._short_trajectory_row(
                    spec, min(remaining, float(remaining_s))
                )
                self.samples.append(row)
            if row.get("status") != "pass":
                return {
                    "status": "fail",
                    "failure_class": row.get(
                        "failure_class", "controller_integrity"
                    ),
                    "reason": f"{row['sample_id']}: {row.get('error_class')}",
                }

        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return {
                "status": "fail",
                "failure_class": "performance_only",
                "reason": "runtime_evidence_insufficient_before_dormant_runner",
            }
        try:
            self.runner = _dormant_runner_dry_run(self.authority)
        except Exception as error:
            raise RuntimeError("dormant runner dry-run infrastructure failed") from error
        if self.runner["status"] != "pass":
            return {
                "status": "fail",
                "failure_class": "controller_integrity",
                "reason": "dormant_runner_dry_run_failed",
            }

        measured_levels = {
            int(row["spatial_level"])
            for row in self.samples
            if row.get("sample_kind") == "short_trajectory"
            and row.get("streaming_io_measurement_status")
            == "measured_atomic_publish"
            and int(row.get("streaming_output_bytes", 0)) > 0
            and float(row.get("streaming_publish_wall_s", 0.0)) > 0.0
        }
        if measured_levels != {1, 2, 4}:
            return {
                "status": "fail",
                "failure_class": "performance_only",
                "reason": "actual_streaming_IO_evidence_incomplete_for_L1_L2_L4",
            }
        if self.remaining_budget_s() <= OUTPUT_RESERVE_S:
            return {
                "status": "fail",
                "failure_class": "performance_only",
                "reason": "runtime_evidence_insufficient_before_cost_forecast",
            }
        try:
            self.cost_rows, self.forecast = build_campaign_cost_forecast(
                execution_dag=self.authority.execution_dag,
                sample_rows=self.samples,
                environment=self.authority.environment,
                disk_free_fraction_min=0.20,
                outer_interval_floor_s=OUTER_FLOOR_BASE_S,
                coupled_solves_per_clean_outer_interval=3,
                measured_interval_wall_time_includes_all_coupled_solves=True,
            )
        except ValueError as error:
            if "missing passing trajectory telemetry" not in str(error):
                raise
            return {
                "status": "fail",
                "failure_class": "performance_only",
                "reason": f"campaign_cost_forecast_unavailable: {type(error).__name__}: {error}",
            }

        performance_failures: list[str] = []
        predicted_p95 = float(self.forecast["predicted_p95_makespan_s"])
        if predicted_p95 > 11520.0:
            performance_failures.append("predicted_p95_makespan_exceeds_11520_s")
        if float(self.forecast["hard_makespan_s"]) > 14400.0:
            performance_failures.append("hard_makespan_exceeds_14400_s")
        if (
            float(
                self.forecast[
                    "aggregate_worker_rss_fraction_of_launch_available_ram"
                ]
            )
            > 0.70
        ):
            performance_failures.append("worker_RSS_exceeds_70_percent")
        if float(self.forecast["disk_free_fraction_after_forecast"]) < 0.20:
            performance_failures.append("disk_reserve_below_20_percent")
        if perf_counter() - self.started_s > PREFLIGHT_LIMIT_S:
            performance_failures.append("runtime_preflight_exceeds_900_s")
        if not self.authority.environment.get("physical_core_measurement_available"):
            performance_failures.append("physical_core_measurement_unavailable")
        if not self.authority.environment.get("all_worker_math_thread_limits_equal_one"):
            performance_failures.append("worker_math_thread_limit_not_one")

        return {
            "status": "pass" if not performance_failures else "fail",
            "failure_class": None if not performance_failures else "performance_only",
            "single_interval_count": sum(
                row["sample_kind"] == "single_interval" for row in self.samples
            ),
            "short_trajectory_count": sum(
                row["sample_kind"] == "short_trajectory" for row in self.samples
            ),
            "C2_reused_for_L1_legal_critical": True,
            "performance_failures": performance_failures,
            "predicted_p95_makespan_s": predicted_p95,
            "hard_makespan_s": float(self.forecast["hard_makespan_s"]),
            "peak_worker_rss_bytes": int(self.forecast["peak_worker_rss_bytes"]),
            "predicted_campaign_output_bytes": int(
                self.forecast["predicted_campaign_output_bytes"]
            ),
            "dormant_runner_status": self.runner["status"],
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }


def _readiness_report(
    summary: dict[str, Any],
    C1: dict[str, Any],
    C2: dict[str, Any],
    C3: dict[str, Any],
    runner: dict[str, Any],
) -> str:
    forecast = summary.get("campaign_cost_forecast", {})
    lines = [
        "# Phase 1-v2 embedded-controller readiness",
        "",
        f"Disposition: `{summary['disposition']}`",
        "",
        "This report records a non-formal, CPU-only controller and runtime ",
        "readiness preflight. It is not a Phase 1 scientific result and does ",
        "not authorize the 63-item formal campaign.",
        "",
        "## Sequential gates",
        "",
        "| Gate | Status | Boundary |",
        "|---|---|---|",
        f"| C1 | `{C1.get('status', 'unknown')}` | locked legal-critical fixture |",
        f"| C2 | `{C2.get('status', 'unknown')}` | bounded 128-interval/1 us trajectory |",
        f"| C3 | `{C3.get('status', 'unknown')}` | 18 intervals, 9 trajectories, forecast, dormant runner |",
        "",
        "## Runtime",
        "",
        f"- Runtime-preflight wall clock: `{summary.get('preflight_wall_clock_s')}` s (limit 900 s).",
        f"- Predicted p95 proxy makespan: `{forecast.get('predicted_p95_makespan_s')}` s.",
        f"- Predicted hard makespan: `{forecast.get('hard_makespan_s')}` s.",
        f"- Peak worker RSS: `{forecast.get('peak_worker_rss_bytes')}` bytes.",
        f"- Predicted campaign output: `{forecast.get('predicted_campaign_output_bytes')}` bytes.",
        f"- Dormant runner: `{runner.get('status', 'not_reached')}`.",
        "",
        "## Evidence boundary",
        "",
        f"- `formal_execution_count={summary.get('formal_execution_count', 0)}`",
        f"- `formal_artifact_count={summary.get('formal_artifact_count', 0)}`",
        "- No formal evaluation ID was dispatched and no formal trend/event gate voted.",
        "- Even a GO disposition requires fresh user authorization before formal execution.",
        "",
    ]
    return "\n".join(lines)


def publish_readiness_evidence(
    output_root: Path,
    *,
    samples: list[dict[str, Any]],
    cost_rows: list[dict[str, Any]],
    C1: dict[str, Any],
    C2: dict[str, Any],
    C3: dict[str, Any],
    summary: dict[str, Any],
    runner: dict[str, Any],
) -> None:
    """Publish the two CSV files before any JSON or report artifact."""

    if summary.get("disposition") not in DISPOSITIONS:
        raise ValueError("readiness evidence has an invalid disposition")
    if summary.get("formal_execution_count", 0) != 0:
        raise ValueError("readiness evidence crossed the formal execution boundary")
    if summary.get("formal_artifact_count", 0) != 0:
        raise ValueError("readiness evidence created a formal artifact")
    if any(
        row.get("sample_id")
        and not str(row["sample_id"]).startswith("PRE-CTRL-")
        for row in samples
    ):
        raise ValueError("readiness sample lacks the PRE-CTRL prefix")

    samples_path = output_root / "preflight_samples.csv"
    cost_path = output_root / "campaign_cost_forecast.csv"
    cost_fields = list(cost_rows[0]) if cost_rows else [
        "execution_unit_id",
        "execution_group",
        "spatial_level",
        "time_divisor",
        "full_trajectory",
        "unreserved_accepted_steps",
        "safety_accepted_steps",
        "unreserved_wall_clock_s",
        "safety_wall_clock_s",
        "predicted_output_bytes",
    ]
    _atomic_csv(samples_path, samples, SAMPLE_FIELDS)
    _atomic_csv(cost_path, cost_rows, cost_fields)

    preflight = {
        "task_id": "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION",
        "schema_version": "geophase_phase1_v2_controller_v2_preflight_v1",
        "status": C3.get("status", "not_reached"),
        "C3": C3,
        "sample_count": len(samples),
        "passing_sample_count": sum(row.get("status") == "pass" for row in samples),
        "failing_sample_count": sum(row.get("status") == "fail" for row in samples),
        "required_single_interval_expected": 18,
        "required_single_interval_completed": sum(
            row.get("sample_kind") == "single_interval" for row in samples
        ),
        "required_short_trajectory_expected": 9,
        "required_short_trajectory_completed": sum(
            row.get("sample_kind") == "short_trajectory" for row in samples
        ),
        "C2_reuse_count": sum(
            row.get("sample_id") == "PRE-CTRL-C2-L1-legal_critical"
            for row in samples
        ),
        "wall_clock_s": summary.get("preflight_wall_clock_s"),
        "wall_clock_limit_s": PREFLIGHT_LIMIT_S,
        "peak_rss_bytes": max(
            (int(row.get("peak_rss_bytes", 0)) for row in samples), default=0
        ),
        "performance_repair_consumed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    _atomic_json(output_root / "C1_summary.json", C1)
    _atomic_json(output_root / "C2_summary.json", C2)
    _atomic_json(output_root / "preflight_summary.json", preflight)
    _atomic_json(output_root / "runner_dry_run.json", runner)
    _atomic_json(output_root / "readiness_summary.json", summary)
    report_path = (
        REPORT_PATH
        if output_root.resolve() == OUTPUT_DIR.resolve()
        else output_root / "readiness_report.md"
    )
    _atomic_text(report_path, _readiness_report(summary, C1, C2, C3, runner))


def _primary_cause(pipeline: dict[str, Any]) -> str | None:
    if pipeline["disposition"] == "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION":
        return None
    for gate_name in ("C1", "C2", "C3"):
        gate = pipeline[gate_name]
        if gate.get("status") in {"pass", "not_reached"}:
            continue
        return str(
            gate.get("reason")
            or gate.get("error_class")
            or gate.get("performance_failures", ["readiness_gate_failed"])[0]
        )
    return "runtime_evidence_insufficient"


def _single_attempt_stage(
    *,
    stage: str,
    path: Path,
    authority: LockedAuthority,
    deadline_utc: str,
    callback: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """Write a fail-closed marker before a numerical stage is invoked once."""

    def execute(*args: Any) -> dict[str, Any]:
        if path.exists():
            raise RuntimeError(f"{stage} numerical attempt marker already exists")
        started_utc = datetime.now(timezone.utc).isoformat()
        _atomic_json(
            path,
            {
                "task_id": "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION",
                "schema_version": "controller_v2_single_attempt_marker_v1",
                "stage": stage,
                "status": "RUNNING_SINGLE_ATTEMPT_DO_NOT_REPLAY",
                "numerical_attempt_count": 1,
                "attempt_started_utc": started_utc,
                "preflight_deadline_utc": deadline_utc,
                "identity_hashes_sha256": authority.identity_hashes,
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            },
        )
        result = callback(*args)
        completed = {
            **result,
            "numerical_attempt_count": 1,
            "attempt_marker_created_before_numerics": True,
            "attempt_started_utc": started_utc,
            "preflight_deadline_utc": deadline_utc,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
        _atomic_json(path, completed)
        return completed

    return execute


def run_readiness() -> dict[str, Any]:
    forbidden_existing = (
        C1_PATH,
        C2_PATH,
        SAMPLES_PATH,
        PREFLIGHT_PATH,
        COST_PATH,
        RUNNER_PATH,
        READINESS_PATH,
        REPORT_PATH,
    )
    if any(path.exists() for path in forbidden_existing):
        raise RuntimeError("controller-v2 readiness evidence already exists")

    authority = _load_authority()
    preflight_started = perf_counter()
    deadline_utc = (
        datetime.now(timezone.utc) + timedelta(seconds=PREFLIGHT_LIMIT_S)
    ).isoformat()
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    supervised_io_root = os.environ.get(_SUPERVISED_IO_ROOT_ENV)
    io_context = (
        nullcontext(Path(supervised_io_root))
        if supervised_io_root
        else tempfile.TemporaryDirectory(
            dir=OUTPUT_DIR.parent, prefix=".controller-v2-io-measurement-"
        )
    )
    with io_context as io_directory:
        execution = _RealReadinessExecution(
            authority, preflight_started, Path(io_directory)
        )
        pipeline = execute_readiness_pipeline(
            ReadinessHooks(
                run_c1=_single_attempt_stage(
                    stage="C1",
                    path=C1_PATH,
                    authority=authority,
                    deadline_utc=deadline_utc,
                    callback=execution.run_c1,
                ),
                run_c2=_single_attempt_stage(
                    stage="C2",
                    path=C2_PATH,
                    authority=authority,
                    deadline_utc=deadline_utc,
                    callback=execution.run_c2,
                ),
                run_c3=_single_attempt_stage(
                    stage="C3",
                    path=PREFLIGHT_PATH,
                    authority=authority,
                    deadline_utc=deadline_utc,
                    callback=execution.run_c3,
                ),
            ),
            preflight_started_s=preflight_started,
        )
    samples = list(execution.samples)
    if execution.c2_sample is not None and not any(
        row.get("sample_id") == execution.c2_sample.get("sample_id")
        for row in samples
    ):
        samples.append(dict(execution.c2_sample))
    runner = {
        **execution.runner,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    summary = {
        **pipeline,
        "schema_version": "geophase_phase1_v2_controller_v2_readiness_v1",
        "unique_primary_cause": _primary_cause(pipeline),
        "performance_only_failure": pipeline["disposition"]
        == "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        "performance_repair_consumed": False,
        "performance_repair_opportunity_remaining": pipeline["disposition"]
        == "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        "controller_revision_opportunity_remaining": False,
        "global_process_supervisor_timeout_s": GLOBAL_WORKER_TIMEOUT_S,
        "base_S2_config_sha256": authority.identity_hashes["S2_config"],
        "controller_v2_overlay_sha256": authority.identity_hashes[
            "controller_v2_overlay"
        ],
        "resolved_runtime_identity_sha256": authority.identity_hashes[
            "resolved_runtime_identity"
        ],
        "core_implementation_commit": IMPLEMENTATION_COMMIT,
        "core_implementation_tree": IMPLEMENTATION_TREE,
        "core_implementation_path_hashes_sha256": (
            authority.implementation_path_hashes
        ),
        "readiness_execution_commit": authority.execution_commit,
        "readiness_execution_tree": authority.execution_tree,
        "readiness_driver_sha256": authority.driver_sha256,
        "identity_hashes_sha256": authority.identity_hashes,
        "environment": authority.environment,
        "stable_environment": _stable_environment(authority.environment),
        "environment_identity_scope": "stable_machine_and_software_fields_only",
        "volatile_environment_telemetry": {
            key: authority.environment[key]
            for key in (
                "total_ram_bytes",
                "available_ram_bytes_at_launch",
                "process_working_set_bytes_at_launch",
                "process_peak_working_set_bytes_at_launch",
                "disk_total_bytes",
                "disk_free_bytes_at_launch",
            )
        },
        "environment_sha256": authority.environment_sha256,
        "campaign_cost_forecast": execution.forecast,
        "dormant_runner_status": runner["status"],
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifact_count": 0,
        "formal_campaign_authorized": False,
        "claim_status": "forbidden_pending_separately_authorized_formal_campaign",
    }
    publish_readiness_evidence(
        OUTPUT_DIR,
        samples=samples,
        cost_rows=execution.cost_rows,
        C1=pipeline["C1"],
        C2=pipeline["C2"],
        C3=pipeline["C3"],
        summary=summary,
        runner=runner,
    )
    return summary


def _stage_payload_at_global_timeout(path: Path, stage: str) -> dict[str, Any]:
    if not path.is_file():
        return {
            "status": "not_reached",
            "reason": "global_runtime_preflight_deadline_reached",
            "stage": stage,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if stage == "C3" and isinstance(payload.get("C3"), dict):
        payload = dict(payload["C3"])
    if payload.get("status") == "RUNNING_SINGLE_ATTEMPT_DO_NOT_REPLAY":
        return {
            **payload,
            "status": "not_completed_by_global_runtime_preflight_deadline",
            "failure_class": "performance_only",
            "reason": "global_runtime_preflight_deadline_reached",
        }
    return payload


def _timeout_disposition_and_cause(
    C1: dict[str, Any], C2: dict[str, Any], C3: dict[str, Any]
) -> tuple[str, str]:
    completed_scientific_failure = next(
        (
            gate
            for gate in (C1, C2, C3)
            if gate.get("status") == "fail"
            and gate.get("failure_class") == "controller_integrity"
        ),
        None,
    )
    if completed_scientific_failure is None:
        return (
            "NO_GO_RUNTIME_PERFORMANCE_ONLY",
            "global_runtime_preflight_deadline_reached",
        )
    cause = str(
        completed_scientific_failure.get("reason")
        or completed_scientific_failure.get("error_class")
        or "completed_controller_integrity_failure"
    )
    return "NO_GO_TIME_CONTROLLER_REVISION", cause


def _publish_global_timeout_evidence(
    authority: LockedAuthority, supervisor_started_s: float
) -> dict[str, Any]:
    """Close an externally terminated preflight without a scientific verdict."""

    C1 = _stage_payload_at_global_timeout(C1_PATH, "C1")
    C2 = _stage_payload_at_global_timeout(C2_PATH, "C2")
    C3 = _stage_payload_at_global_timeout(PREFLIGHT_PATH, "C3")
    if C3.get("status") in {
        "not_reached",
        "not_completed_by_global_runtime_preflight_deadline",
    }:
        C3 = {
            **C3,
            "status": "fail",
            "failure_class": "performance_only",
            "reason": "global_runtime_preflight_deadline_reached",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    disposition, primary_cause = _timeout_disposition_and_cause(C1, C2, C3)
    runner = {
        "status": "not_reached",
        "reason": "global_runtime_preflight_deadline_reached",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }
    samples: list[dict[str, Any]] = []
    forecast_row = C2.get("forecast_sample_row")
    if isinstance(forecast_row, dict):
        samples.append(dict(forecast_row))
    volatile_keys = (
        "total_ram_bytes",
        "available_ram_bytes_at_launch",
        "process_working_set_bytes_at_launch",
        "process_peak_working_set_bytes_at_launch",
        "disk_total_bytes",
        "disk_free_bytes_at_launch",
    )
    summary = {
        "task_id": "Q2_PHASE1_V2_EMBEDDED_TIME_CONTROLLER_REVISION",
        "schema_version": "geophase_phase1_v2_controller_v2_readiness_v1",
        "C1": C1,
        "C2": C2,
        "C3": C3,
        "disposition": disposition,
        "unique_primary_cause": primary_cause,
        "preflight_wall_clock_s": float(perf_counter() - supervisor_started_s),
        "preflight_wall_clock_limit_s": PREFLIGHT_LIMIT_S,
        "global_process_supervisor_timeout_s": GLOBAL_WORKER_TIMEOUT_S,
        "performance_only_failure": disposition
        == "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        "performance_repair_consumed": False,
        "performance_repair_opportunity_remaining": disposition
        == "NO_GO_RUNTIME_PERFORMANCE_ONLY",
        "controller_revision_opportunity_remaining": False,
        "base_S2_config_sha256": authority.identity_hashes["S2_config"],
        "controller_v2_overlay_sha256": authority.identity_hashes[
            "controller_v2_overlay"
        ],
        "resolved_runtime_identity_sha256": authority.identity_hashes[
            "resolved_runtime_identity"
        ],
        "core_implementation_commit": IMPLEMENTATION_COMMIT,
        "core_implementation_tree": IMPLEMENTATION_TREE,
        "core_implementation_path_hashes_sha256": (
            authority.implementation_path_hashes
        ),
        "readiness_execution_commit": authority.execution_commit,
        "readiness_execution_tree": authority.execution_tree,
        "readiness_driver_sha256": authority.driver_sha256,
        "identity_hashes_sha256": authority.identity_hashes,
        "environment": authority.environment,
        "stable_environment": _stable_environment(authority.environment),
        "environment_identity_scope": "stable_machine_and_software_fields_only",
        "volatile_environment_telemetry": {
            key: authority.environment[key] for key in volatile_keys
        },
        "environment_sha256": authority.environment_sha256,
        "campaign_cost_forecast": {},
        "dormant_runner_status": "not_reached",
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifact_count": 0,
        "formal_campaign_authorized": False,
        "claim_status": "forbidden_pending_separately_authorized_formal_campaign",
    }
    publish_readiness_evidence(
        OUTPUT_DIR,
        samples=samples,
        cost_rows=[],
        C1=C1,
        C2=C2,
        C3=C3,
        summary=summary,
        runner=runner,
    )
    final_elapsed = float(perf_counter() - supervisor_started_s)
    summary["preflight_wall_clock_s"] = final_elapsed
    _atomic_json(READINESS_PATH, summary)
    preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    preflight["wall_clock_s"] = final_elapsed
    _atomic_json(PREFLIGHT_PATH, preflight)
    _atomic_text(REPORT_PATH, _readiness_report(summary, C1, C2, C3, runner))
    return summary


def _finalize_supervised_wall_clock(
    summary: dict[str, Any], supervisor_started_s: float
) -> dict[str, Any]:
    """Apply the parent wall gate after worker exit and temp-root cleanup."""

    elapsed = float(perf_counter() - supervisor_started_s)
    summary = dict(summary)
    summary["preflight_wall_clock_s"] = elapsed
    summary["parent_wall_clock_measurement_scope"] = (
        "after_worker_exit_evidence_publish_and_supervised_temp_cleanup; "
        "before_final_metadata_timestamp_commit"
    )
    if (
        elapsed > PREFLIGHT_LIMIT_S
        and summary.get("disposition")
        == "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION"
    ):
        C3 = dict(summary.get("C3", {}))
        C3.update(
            {
                "status": "fail",
                "failure_class": "performance_only",
                "reason": "parent_end_to_end_runtime_preflight_exceeds_900_s",
                "formal_execution_count": 0,
                "formal_artifact_count": 0,
            }
        )
        summary["C3"] = C3
        summary["disposition"] = "NO_GO_RUNTIME_PERFORMANCE_ONLY"
        summary["unique_primary_cause"] = (
            "parent_end_to_end_runtime_preflight_exceeds_900_s"
        )
        summary["performance_only_failure"] = True
        summary["performance_repair_opportunity_remaining"] = True

    C1 = dict(summary.get("C1", _not_reached("missing_C1_summary")))
    C2 = dict(summary.get("C2", _not_reached("missing_C2_summary")))
    C3 = dict(summary.get("C3", _not_reached("missing_C3_summary")))
    runner = (
        json.loads(RUNNER_PATH.read_text(encoding="utf-8"))
        if RUNNER_PATH.is_file()
        else {
            "status": "not_reached",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    )
    preflight = (
        json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
        if PREFLIGHT_PATH.is_file()
        else {}
    )
    preflight.update(
        {
            "status": C3.get("status", "not_reached"),
            "C3": C3,
            "wall_clock_s": elapsed,
            "wall_clock_limit_s": PREFLIGHT_LIMIT_S,
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        }
    )
    _atomic_json(PREFLIGHT_PATH, preflight)
    _atomic_json(READINESS_PATH, summary)
    _atomic_text(REPORT_PATH, _readiness_report(summary, C1, C2, C3, runner))
    return summary


def run_readiness_with_global_supervisor() -> dict[str, Any]:
    """Run the only numerical preflight in a terminable child process."""

    authority = _load_authority()
    started = perf_counter()
    environment = os.environ.copy()
    environment[_INTERNAL_WORKER_ENV] = "1"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--execute-preregistered-readiness",
    ]
    timeout_s = GLOBAL_WORKER_TIMEOUT_S
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    completed: subprocess.CompletedProcess[str] | None = None
    with tempfile.TemporaryDirectory(
        dir=OUTPUT_DIR.parent, prefix=".controller-v2-supervised-io-"
    ) as io_directory:
        environment[_SUPERVISED_IO_ROOT_ENV] = io_directory
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
    if timed_out:
        summary = _publish_global_timeout_evidence(authority, started)
        return _finalize_supervised_wall_clock(summary, started)
    if completed is None:
        raise RuntimeError("readiness worker supervisor lost its completion state")
    if completed.returncode != 0:
        raise RuntimeError(
            "readiness worker failed before a valid scientific/runtime disposition: "
            f"{completed.stderr[-2000:]}"
        )
    if not READINESS_PATH.is_file():
        raise RuntimeError("readiness worker exited without atomic readiness evidence")
    summary = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    if summary.get("disposition") not in DISPOSITIONS:
        raise RuntimeError("readiness worker published an invalid disposition")
    return _finalize_supervised_wall_clock(summary, started)


def check_evidence() -> None:
    required = (
        C1_PATH,
        C2_PATH,
        SAMPLES_PATH,
        PREFLIGHT_PATH,
        COST_PATH,
        RUNNER_PATH,
        READINESS_PATH,
        REPORT_PATH,
    )
    if any(not path.is_file() for path in required):
        raise SystemExit("controller-v2 readiness evidence is incomplete")
    summary = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    C1 = json.loads(C1_PATH.read_text(encoding="utf-8"))
    C2 = json.loads(C2_PATH.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    runner = json.loads(RUNNER_PATH.read_text(encoding="utf-8"))
    with SAMPLES_PATH.open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle))
    if summary.get("disposition") not in DISPOSITIONS:
        raise SystemExit("controller-v2 readiness disposition is invalid")
    for payload in (summary, C1, C2, preflight, runner):
        if int(payload.get("formal_execution_count", 0)) != 0:
            raise SystemExit("controller-v2 readiness consumed formal execution")
        if int(payload.get("formal_artifact_count", 0)) != 0:
            raise SystemExit("controller-v2 readiness created a formal artifact")
    if any(not row["sample_id"].startswith("PRE-CTRL-") for row in samples):
        raise SystemExit("controller-v2 sample lacks PRE-CTRL prefix")
    if runner.get("status") == "pass" and (
        runner.get("registry_location") != "temporary_directory_only"
        or runner.get("run_ID_prefix") != "PRE-CTRL-"
    ):
        raise SystemExit("dormant runner escaped the PRE temporary boundary")
    if summary.get("base_S2_config_sha256") != _sha256(BASE_CONFIG_PATH):
        raise SystemExit("controller-v2 readiness base config hash drifted")
    if summary.get("controller_v2_overlay_sha256") != _sha256(OVERLAY_PATH):
        raise SystemExit("controller-v2 readiness overlay hash drifted")
    if any(
        (OUTPUT_DIR.parent / name).exists()
        for name in ("formal_summary.json", "formal_convergence.csv")
    ):
        raise SystemExit("formal Phase 1-v2 artifact exists")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Execute or validate the one-shot non-formal Phase 1-v2 "
            "embedded-controller readiness sequence."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--execute-preregistered-readiness", action="store_true")
    group.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        check_evidence()
        return
    summary = (
        run_readiness()
        if os.environ.get(_INTERNAL_WORKER_ENV) == "1"
        else run_readiness_with_global_supervisor()
    )
    print(
        json.dumps(
            _json_safe(summary), indent=2, sort_keys=True, allow_nan=False
        )
    )


if __name__ == "__main__":
    main()

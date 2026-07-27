from __future__ import annotations

import os

# The readiness contract requires one math-library thread per future worker.
# These assignments occur before NumPy/SciPy import in this process.
for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_thread_variable] = "1"

import argparse
import csv
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import subprocess
import tempfile
from time import perf_counter
from typing import Any

import numpy as np
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
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
    advance_s2_backward_euler,
    build_s2_solver_cache,
    simulate_s2_protocol,
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
    run_s2_streaming_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
ADDENDUM_PATH = ROOT / "configs" / "geophase_phase1_v2_execution_addendum.yaml"
MANIFEST_CONTRACT_PATH = ROOT / "configs" / "geophase_phase1_v2_formal_manifest.yaml"
MANIFEST_JSON_PATH = (
    ROOT / "outputs" / "tables" / "geophase_phase1_v2" / "formal_evaluation_manifest.json"
)
PREREG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
    / "preregistration.json"
)
DAG_PATH = PREREG_PATH.parent / "execution_dag.json"
OUTPUT_DIR = PREREG_PATH.parent
ENVIRONMENT_PATH = OUTPUT_DIR / "environment.json"
SAMPLES_PATH = OUTPUT_DIR / "preflight_samples.csv"
PREFLIGHT_PATH = OUTPUT_DIR / "preflight_summary.json"
COST_PATH = OUTPUT_DIR / "campaign_cost_forecast.csv"
RUNNER_PATH = OUTPUT_DIR / "runner_dry_run.json"
READINESS_PATH = OUTPUT_DIR / "readiness_summary.json"
REPORT_PATH = (
    ROOT
    / "docs"
    / "codex_reports"
    / "geophase_phase1_v2_runtime_formal_runner_readiness.md"
)

PRE_FLIGHT_LIMIT_S = 900.0
OUTPUT_RESERVE_S = 5.0

SAMPLE_FIELDS = [
    "sample_id",
    "sample_kind",
    "spatial_level",
    "nx",
    "ny",
    "state_id",
    "dt_class",
    "dt_s",
    "protocol_id",
    "status",
    "error_class",
    "error_message",
    "accepted_steps",
    "rejected_steps",
    "transition_rejections",
    "nonlinear_rejections",
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
    "thermal_relative_residual_max",
    "circuit_relative_residual_max",
    "combined_relative_residual_max",
    "device_power_relative_residual_max",
    "lateral_relative_mismatch_max",
    "lateral_roundoff_ratio_max",
    "peak_rss_bytes",
    "streaming_output_bytes",
    "streaming_write_wall_s",
    "scalar_record_count",
    "predicted_full_streaming_bytes",
    "predicted_full_streaming_io_s",
    "parity_max_relative_error",
    "parity_worst_component",
]


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


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    _atomic_text(path, stream.getvalue())


def _authority() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = _load_yaml(CONFIG_PATH)
    addendum = _load_yaml(ADDENDUM_PATH)
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    dag = json.loads(DAG_PATH.read_text(encoding="utf-8"))
    expected = {
        CONFIG_PATH: addendum["authority_lock"]["S2_config"]["sha256"],
        MANIFEST_CONTRACT_PATH: addendum["authority_lock"]["formal_manifest_contract"]["sha256"],
        MANIFEST_JSON_PATH: addendum["authority_lock"]["expanded_manifest_json"]["sha256"],
    }
    for path, digest in expected.items():
        if _sha256(path) != digest:
            raise RuntimeError(f"locked authority hash mismatch: {path.relative_to(ROOT)}")
    if _sha256(ADDENDUM_PATH) != prereg["addendum_config_sha256"]:
        raise RuntimeError("execution addendum hash differs from pushed preregistration")
    if _sha256(DAG_PATH) != prereg["execution_dag_json_sha256"]:
        raise RuntimeError("execution DAG hash differs from pushed preregistration")
    if prereg["formal_execution_count"] != 0 or prereg["runtime_preflight_executed"] is not False:
        raise RuntimeError("runtime preregistration boundary is invalid")
    if dag["formal_execution_count"] != 0 or dag["unique_execution_unit_count"] != 60:
        raise RuntimeError("execution DAG no longer carries the 60-unit zero-count lock")
    return config, addendum, prereg, dag


def _code_tree_hash() -> tuple[str, dict[str, str]]:
    paths = (
        Path("src/pinnpcm/solvers/geophase_phase1_v2_fvm.py"),
        Path("src/pinnpcm/solvers/geophase_phase1_v2_implicit.py"),
        Path("src/pinnpcm/solvers/geophase_phase1_v2_streaming.py"),
        Path("src/pinnpcm/solvers/geophase_phase1_v2_formal_runner.py"),
        Path("src/pinnpcm/solvers/geophase_phase1_v2_runtime.py"),
        Path("scripts/run_geophase_phase1_v2_runtime_readiness.py"),
    )
    hashes = {path.as_posix(): _sha256(ROOT / path) for path in paths}
    return _canonical_hash(hashes), hashes


def _state(
    state_id: str,
    *,
    grid,
    closure,
    fields,
) -> S2State:
    if state_id == "equilibrium":
        temperature_value = fields.ambient_temperature_K
        branch_value = 1.0
        conductive_value = closure.equilibrium_state(
            np.asarray(temperature_value), np.asarray(branch_value)
        ).item()
    elif state_id == "legal_critical":
        temperature_value = closure.T_c_up_K
        branch_value = 1.0
        conductive_value = 0.5
    elif state_id == "high_conductive":
        temperature_value = closure.temperature_max_K
        branch_value = 1.0
        conductive_value = closure.equilibrium_state(
            np.asarray(temperature_value), np.asarray(branch_value)
        ).item()
    else:
        raise ValueError(f"unknown deterministic state {state_id}")
    return S2State(
        time_s=0.0,
        temperature_K=np.full(grid.shape, temperature_value, dtype=float),
        conductive_state=np.full(grid.shape, conductive_value, dtype=float),
        branch_memory=np.full(grid.shape, branch_value, dtype=float),
        device_voltage_V=0.0,
    )


def _protocol_id(state_id: str) -> str:
    return {
        "equilibrium": "zero_drive",
        "legal_critical": "transition_probe_12p5V",
        "high_conductive": "high_bias_15V",
    }[state_id]


def _ledger_and_lateral(step, config: dict) -> tuple[dict[str, float], bool, bool]:
    values = {
        "thermal_relative_residual_max": float(step.ledgers.thermal.relative_residual),
        "circuit_relative_residual_max": float(step.ledgers.circuit.relative_residual),
        "combined_relative_residual_max": float(step.ledgers.combined.relative_residual),
        "device_power_relative_residual_max": float(step.ledgers.device_power.relative_residual),
        "lateral_relative_mismatch_max": float(step.lateral_flux.matrix_face_relative_mismatch),
        "lateral_roundoff_ratio_max": float(step.lateral_flux.matrix_face_roundoff_ratio),
    }
    gates = config["gates"]
    ledgers_pass = bool(
        values["thermal_relative_residual_max"] <= gates["thermal_ledger_relative_residual_max"]
        and values["circuit_relative_residual_max"] <= gates["circuit_ledger_relative_residual_max"]
        and values["combined_relative_residual_max"] <= gates["combined_ledger_relative_residual_max"]
        and values["device_power_relative_residual_max"] <= gates["device_power_identity_relative_residual_max"]
    )
    lateral_pass = bool(
        values["lateral_relative_mismatch_max"] <= 1.0e-10
        or values["lateral_roundoff_ratio_max"] <= 1.0
    )
    return values, ledgers_pass, lateral_pass


def _finite_step(step) -> bool:
    arrays = (
        step.state.temperature_K,
        step.state.conductive_state,
        step.state.branch_memory,
        step.electrical.potential_V,
        step.electrical.cell_joule_power_W,
    )
    scalars = (
        step.state.device_voltage_V,
        step.electrical.source_current_A,
        step.electrical.joule_power_W,
    )
    return all(np.isfinite(item).all() for item in arrays) and bool(np.isfinite(scalars).all())


def _normalized_difference(left: np.ndarray | float, right: np.ndarray | float, floor: float) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return float(np.linalg.norm(a - b) / max(float(np.linalg.norm(a)), float(np.linalg.norm(b)), floor))


def _step_parity_details(left, right) -> dict[str, float]:
    errors = {
        "temperature_K": _normalized_difference(left.state.temperature_K, right.state.temperature_K, 1.0e-3),
        "conductive_state": _normalized_difference(left.state.conductive_state, right.state.conductive_state, 1.0e-6),
        "branch_memory": _normalized_difference(left.state.branch_memory, right.state.branch_memory, 1.0e-6),
        "device_voltage_V": _normalized_difference(left.state.device_voltage_V, right.state.device_voltage_V, 1.0e-12),
        "potential_V": _normalized_difference(left.electrical.potential_V, right.electrical.potential_V, 1.0e-12),
        "source_current_A": _normalized_difference(left.electrical.source_current_A, right.electrical.source_current_A, 1.0e-12),
        "cell_joule_power_W": _normalized_difference(left.electrical.cell_joule_power_W, right.electrical.cell_joule_power_W, 1.0e-30),
    }
    for name in ("thermal", "circuit", "combined", "device_power"):
        a = getattr(left.ledgers, name)
        b = getattr(right.ledgers, name)
        scale = max(abs(a.input_power_W), abs(b.input_power_W), abs(a.accounted_power_W), abs(b.accounted_power_W), 1.0e-30)
        errors[f"{name}.input_power_W"] = abs(a.input_power_W - b.input_power_W) / scale
        errors[f"{name}.accounted_power_W"] = abs(a.accounted_power_W - b.accounted_power_W) / scale
        errors[f"{name}.signed_residual_W"] = abs(a.signed_residual_W - b.signed_residual_W) / scale
        errors[f"{name}.relative_residual"] = abs(a.relative_residual - b.relative_residual)
    return errors


def _step_parity(left, right) -> float:
    return max(_step_parity_details(left, right).values())


def _single_step_row(
    *,
    sample_id: str,
    sample_kind: str,
    level: int,
    state_id: str,
    dt_class: str,
    dt_s: float,
    protocol_id: str,
    state: S2State,
    grid,
    closure,
    fields,
    config: dict,
    cache,
) -> tuple[dict[str, Any], Any | None]:
    started = perf_counter()
    try:
        step = advance_s2_backward_euler(
            state,
            input_voltage_V=float(config["formal_protocols"]["protocols"][protocol_id].get("input_voltage_V", 0.0)),
            dt_s=dt_s,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            cache=cache,
            use_equivalent_optimizations=True,
        )
        wall = perf_counter() - started
        ledger_values, ledgers_pass, lateral_pass = _ledger_and_lateral(step, config)
        finite = _finite_step(step)
        status = "pass" if finite and ledgers_pass and lateral_pass else "fail"
        row = {
            "sample_id": sample_id,
            "sample_kind": sample_kind,
            "spatial_level": level,
            "nx": grid.nx,
            "ny": grid.ny,
            "state_id": state_id,
            "dt_class": dt_class,
            "dt_s": dt_s,
            "protocol_id": protocol_id,
            "status": status,
            "error_class": "" if status == "pass" else "ledger_lateral_or_nonfinite_failure",
            "error_message": "",
            "accepted_steps": 1,
            "rejected_steps": 0,
            "transition_rejections": 0,
            "nonlinear_rejections": 0,
            "newton_iterations": step.nonlinear.iterations,
            "krylov_matvecs": step.nonlinear.krylov_matvecs,
            "armijo_backtracks": step.nonlinear.armijo_backtracks,
            "fallback_steps": int(step.nonlinear.method == "fail_closed_fixed_point_fallback"),
            "fallback_picard_iterations": step.nonlinear.fallback_picard_iterations,
            "step_wall_time_p50_s": wall,
            "step_wall_time_p90_s": wall,
            "step_wall_time_max_s": wall,
            "accepted_dt_p10_s": dt_s,
            "accepted_dt_p50_s": dt_s,
            "accepted_dt_p90_s": dt_s,
            "achieved_simulated_time_s": dt_s,
            "completed": True,
            "stop_reason": "single_step_completed",
            "finite": finite,
            "ledgers_pass": ledgers_pass,
            "lateral_pass": lateral_pass,
            "peak_rss_bytes": process_memory().peak_working_set_bytes,
            **ledger_values,
        }
        return row, step
    except Exception as error:
        wall = perf_counter() - started
        return (
            {
                "sample_id": sample_id,
                "sample_kind": sample_kind,
                "spatial_level": level,
                "nx": grid.nx,
                "ny": grid.ny,
                "state_id": state_id,
                "dt_class": dt_class,
                "dt_s": dt_s,
                "protocol_id": protocol_id,
                "status": "fail",
                "error_class": type(error).__name__,
                "error_message": str(error),
                "accepted_steps": 0,
                "step_wall_time_p50_s": wall,
                "step_wall_time_p90_s": wall,
                "step_wall_time_max_s": wall,
                "achieved_simulated_time_s": 0.0,
                "completed": False,
                "stop_reason": "single_step_exception",
                "finite": False,
                "ledgers_pass": False,
                "lateral_pass": False,
                "peak_rss_bytes": process_memory().peak_working_set_bytes,
            },
            None,
        )


def _trajectory_row(
    *,
    sample_id: str,
    sample_kind: str,
    level: int,
    state_id: str,
    protocol_id: str,
    initial_state: S2State,
    grid,
    closure,
    fields,
    config: dict,
    cache,
    temporary_root: Path,
    maximum_accepted_steps: int | None,
    final_time_s: float,
    maximum_wall_clock_s: float,
    identity_hashes: dict[str, str],
) -> dict[str, Any]:
    started = perf_counter()
    try:
        result = run_s2_streaming_protocol(
            sample_id,
            initial_state,
            protocol=config["formal_protocols"]["protocols"][protocol_id],
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            final_time_s=final_time_s,
            maximum_accepted_steps=maximum_accepted_steps,
            maximum_wall_clock_s=maximum_wall_clock_s,
            cache=cache,
        )
        compute_wall = perf_counter() - started
        publish_started = perf_counter()
        published = publish_pre_streaming_case(
            temporary_root, result, identity_hashes=identity_hashes
        )
        write_wall = perf_counter() - publish_started
        output_bytes = published_case_bytes(published)
        rows = list(result.scalar_records[1:])
        maxima = {
            name: max((float(row[name]) for row in rows), default=0.0)
            for name in (
                "thermal_relative_residual",
                "circuit_relative_residual",
                "combined_relative_residual",
                "device_power_relative_residual",
                "lateral_matrix_face_relative_mismatch",
                "lateral_matrix_face_roundoff_ratio",
            )
        }
        gates = config["gates"]
        ledgers_pass = bool(
            maxima["thermal_relative_residual"] <= gates["thermal_ledger_relative_residual_max"]
            and maxima["circuit_relative_residual"] <= gates["circuit_ledger_relative_residual_max"]
            and maxima["combined_relative_residual"] <= gates["combined_ledger_relative_residual_max"]
            and maxima["device_power_relative_residual"] <= gates["device_power_identity_relative_residual_max"]
        )
        lateral_pass = bool(
            maxima["lateral_matrix_face_relative_mismatch"] <= 1.0e-10
            or maxima["lateral_matrix_face_roundoff_ratio"] <= 1.0
        )
        final = result.final_state
        finite = bool(
            np.isfinite(final.temperature_K).all()
            and np.isfinite(final.conductive_state).all()
            and np.isfinite(final.branch_memory).all()
            and np.isfinite(final.device_voltage_V)
        )
        diagnostics = result.protocol_result.diagnostics
        expected_stop = result.protocol_result.completed or (
            maximum_accepted_steps is not None
            and diagnostics.accepted_steps >= maximum_accepted_steps
            and result.protocol_result.stop_reason == "maximum_accepted_steps_reached"
        )
        status = "pass" if finite and ledgers_pass and lateral_pass and expected_stop else "fail"
        scale = 4001.0 / max(len(result.scalar_records), 1)
        return {
            "sample_id": sample_id,
            "sample_kind": sample_kind,
            "spatial_level": level,
            "nx": grid.nx,
            "ny": grid.ny,
            "state_id": state_id,
            "dt_class": "adaptive_T1",
            "dt_s": "",
            "protocol_id": protocol_id,
            "status": status,
            "error_class": "" if status == "pass" else "trajectory_integrity_or_stop_failure",
            "error_message": "",
            "accepted_steps": diagnostics.accepted_steps,
            "rejected_steps": diagnostics.rejected_steps,
            "transition_rejections": diagnostics.transition_rejections,
            "nonlinear_rejections": diagnostics.nonlinear_rejections,
            "newton_iterations": diagnostics.newton_iterations,
            "krylov_matvecs": diagnostics.krylov_matvecs,
            "armijo_backtracks": diagnostics.armijo_backtracks,
            "fallback_steps": diagnostics.fallback_steps,
            "fallback_picard_iterations": diagnostics.fallback_picard_iterations,
            "step_wall_time_p50_s": diagnostics.step_wall_time_p50_s,
            "step_wall_time_p90_s": diagnostics.step_wall_time_p90_s,
            "step_wall_time_max_s": diagnostics.step_wall_time_max_s,
            "accepted_dt_p10_s": diagnostics.accepted_dt_p10_s,
            "accepted_dt_p50_s": diagnostics.accepted_dt_p50_s,
            "accepted_dt_p90_s": diagnostics.accepted_dt_p90_s,
            "achieved_simulated_time_s": result.protocol_result.achieved_final_time_s,
            "completed": result.protocol_result.completed,
            "stop_reason": result.protocol_result.stop_reason,
            "finite": finite,
            "ledgers_pass": ledgers_pass,
            "lateral_pass": lateral_pass,
            "thermal_relative_residual_max": maxima["thermal_relative_residual"],
            "circuit_relative_residual_max": maxima["circuit_relative_residual"],
            "combined_relative_residual_max": maxima["combined_relative_residual"],
            "device_power_relative_residual_max": maxima["device_power_relative_residual"],
            "lateral_relative_mismatch_max": maxima["lateral_matrix_face_relative_mismatch"],
            "lateral_roundoff_ratio_max": maxima["lateral_matrix_face_roundoff_ratio"],
            "peak_rss_bytes": process_memory().peak_working_set_bytes,
            "streaming_output_bytes": output_bytes,
            "streaming_write_wall_s": write_wall,
            "scalar_record_count": len(result.scalar_records),
            "predicted_full_streaming_bytes": int(math.ceil(output_bytes * scale)),
            "predicted_full_streaming_io_s": write_wall * scale,
            "compute_wall_clock_s": compute_wall,
        }
    except Exception as error:
        wall = perf_counter() - started
        return {
            "sample_id": sample_id,
            "sample_kind": sample_kind,
            "spatial_level": level,
            "nx": grid.nx,
            "ny": grid.ny,
            "state_id": state_id,
            "protocol_id": protocol_id,
            "status": "fail",
            "error_class": type(error).__name__,
            "error_message": str(error),
            "accepted_steps": 0,
            "step_wall_time_p50_s": wall,
            "step_wall_time_p90_s": wall,
            "step_wall_time_max_s": wall,
            "achieved_simulated_time_s": 0.0,
            "completed": False,
            "stop_reason": "trajectory_exception",
            "finite": False,
            "ledgers_pass": False,
            "lateral_pass": False,
            "peak_rss_bytes": process_memory().peak_working_set_bytes,
        }


def _runner_dry_run(
    *,
    dag: dict[str, Any],
    identity_hashes: dict[str, str],
    environment: dict[str, Any],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pinn-phase1v2-runner-") as directory:
        root = Path(directory)
        passing = create_prepared_registry(
            root,
            run_id="PRE-RUNNER-PASS",
            identity_hashes=identity_hashes,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(passing.path)
        partial = create_partial_case_work(passing.path, "PRE-UNIT-A", {"step": 1})
        interrupt_resumable(
            passing.path,
            reason="injected interruption",
            partial_case_id="PRE-UNIT-A",
        )
        unpublished_during_interruption = not (
            passing.path / "cases" / "PRE-UNIT-A.json"
        ).exists()
        resume_same_run(
            passing.path,
            run_id="PRE-RUNNER-PASS",
            expected_identity_hashes=identity_hashes,
        )
        publish_synthetic_case(
            passing.path,
            case_id="PRE-UNIT-A",
            outcome="pass",
            classification="synthetic_pass",
            payload={"step": 2},
        )
        passed = complete_pass(passing.path)

        mismatch = create_prepared_registry(
            root,
            run_id="PRE-RUNNER-HASH",
            identity_hashes=identity_hashes,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(mismatch.path)
        interrupt_resumable(mismatch.path, reason="injected interruption")
        changed = dict(identity_hashes)
        changed["environment"] = "0" * 64 if changed["environment"] != "0" * 64 else "1" * 64
        mismatch_rejected = False
        try:
            resume_same_run(
                mismatch.path,
                run_id="PRE-RUNNER-HASH",
                expected_identity_hashes=changed,
            )
        except InvalidContractError:
            mismatch_rejected = True
        mismatch_state = load_registry(mismatch.path).state

        foundation = create_prepared_registry(
            root,
            run_id="PRE-RUNNER-FOUNDATION",
            identity_hashes=identity_hashes,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(foundation.path)
        foundation_view = record_foundation_failure(
            foundation.path,
            failing_case_id="PRE-FOUNDATION-FAIL",
            remaining_case_ids=["PRE-BLOCKED-A", "PRE-BLOCKED-B"],
            reason="injected foundation failure",
        )
        blocked = json.loads(
            (foundation.path / "blocked" / "foundation_fail_fast.json").read_text(
                encoding="utf-8"
            )
        )

        infrastructure = create_prepared_registry(
            root,
            run_id="PRE-RUNNER-INFRA",
            identity_hashes=identity_hashes,
            execution_dag=dag,
            environment_summary=environment,
        )
        begin_running(infrastructure.path)
        infra_view = interrupt_resumable(
            infrastructure.path, reason="injected worker loss"
        )

        checks = {
            "coverage_63_60_3": passed.identity["coverage"]
            == {"evaluation_items": 63, "execution_units": 60, "legal_reuses": 3},
            "immutable_identity_and_hash_chain_valid": len(passed.events) == 5,
            "same_run_id_resume": passed.state == "COMPLETED_PASS",
            "partial_case_not_published": unpublished_during_interruption,
            "per_case_atomic_completion": (passing.path / "cases" / "PRE-UNIT-A.json").exists() and not partial.exists(),
            "hash_mismatch_rejected": mismatch_rejected and mismatch_state == "INVALID_CONTRACT",
            "foundation_fail_fast_blocks_remaining": foundation_view.state == "COMPLETED_SCIENTIFIC_FAIL" and blocked["blocked_case_ids"] == ["PRE-BLOCKED-A", "PRE-BLOCKED-B"],
            "scientific_and_infrastructure_failure_separated": infra_view.state == "INTERRUPTED_RESUMABLE" and foundation_view.state != infra_view.state,
            "formal_count_zero": passed.identity["formal_execution_count"] == 0,
            "real_formal_dispatch_disabled": passed.identity["formal_unit_dispatch_enabled"] is False,
        }
        return {
            "task_id": "Q2_PHASE1_V2_RUNTIME_AND_FORMAL_RUNNER_READINESS",
            "schema_version": "geophase_phase1_v2_dormant_runner_dry_run_v1",
            "status": "pass" if all(checks.values()) else "fail",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
            "registry_location": "temporary_directory_only",
            "run_id_prefix": "PRE-",
            "checks": checks,
            "terminal_states_observed": {
                "pass_path": passed.state,
                "hash_mismatch_path": mismatch_state,
                "foundation_path": foundation_view.state,
                "infrastructure_path": infra_view.state,
            },
        }


def _report(summary: dict[str, Any], preflight: dict[str, Any], runner: dict[str, Any]) -> str:
    forecast = summary.get("campaign_cost_forecast", {})
    wall_clock = (
        "not atomically captured before fail-closed exception"
        if preflight["wall_clock_s"] is None
        else f"{preflight['wall_clock_s']:.6f} s"
    )
    lines = [
        "# Phase 1-v2 runtime and dormant formal-runner readiness",
        "",
        f"Disposition: `{summary['disposition']}`",
        "",
        "This round executed only non-formal `PRE-*` runtime probes and synthetic",
        "runner-state injections. It did not execute a formal evaluation item,",
        "create a real formal run ID, or change the formal execution count.",
        "",
        "## Locked identities",
        "",
        f"- Execution addendum SHA-256: `{summary['execution_addendum_sha256']}`",
        f"- Execution DAG SHA-256: `{summary['execution_dag_sha256']}`",
        f"- Environment SHA-256: `{summary['environment_sha256']}`",
        f"- Code-tree content SHA-256: `{summary['code_tree_sha256']}`",
        "",
        "## Runtime result",
        "",
        f"- Preflight wall clock: `{wall_clock}`.",
        f"- Passing samples: `{preflight['passing_sample_count']}`; failing samples: `{preflight['failing_sample_count']}`.",
        f"- Peak RSS: `{preflight['peak_rss_bytes']}` bytes.",
        f"- Performance repair consumed: `{str(summary['performance_repair_consumed']).lower()}`.",
        "- Unit-voltage scaling: `disabled`; its L1 thermal-ledger parity was",
        "  `4.410635541795736e-12 > 1e-12`, so it is not part of the runner.",
        f"- Dormant runner dry-run: `{runner['status']}`.",
    ]
    if forecast:
        lines.extend(
            [
                f"- Selected workers: `{forecast.get('selected_worker_count')}`.",
                f"- Safety LPT makespan: `{forecast.get('safety_lpt_makespan_s', float('nan')):.6f} s`.",
                f"- Unreserved LPT makespan: `{forecast.get('unreserved_lpt_makespan_s', float('nan')):.6f} s`.",
                f"- Predicted campaign output: `{forecast.get('predicted_campaign_output_bytes')}` bytes.",
            ]
        )
    if summary.get("unique_primary_cause"):
        lines.extend(
            [
                "",
                "## Stop cause",
                "",
                summary["unique_primary_cause"],
            ]
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "Allowed: runtime readiness was assessed on the named workstation under",
            "the locked S2 contract using non-voting PRE probes.",
            "",
            "Forbidden: Phase 1-v2 passed, any formal scientific gate passed, the",
            "Qiu device was reproduced, or Phase 2/PINN work is unlocked.",
            "",
            "`formal_execution_count=0`; formal artifact count is `0`.",
            "",
        ]
    )
    return "\n".join(lines)


def record_observed_critical_failure() -> dict[str, Any]:
    """Persist the already observed fail-closed exception without rerunning it."""

    _config, _addendum, prereg, dag = _authority()
    environment = measure_launch_environment(ROOT)
    environment["measurement_role"] = (
        "post_failure_evidence_recorder_environment_not_failed_process_peak_RSS"
    )
    environment_hash = _canonical_hash(environment)
    environment["environment_sha256"] = environment_hash
    code_tree_hash, code_hashes = _code_tree_hash()
    identity_hashes = {
        "code_tree": code_tree_hash,
        "S2_config": _sha256(CONFIG_PATH),
        "formal_manifest_contract": _sha256(MANIFEST_CONTRACT_PATH),
        "expanded_manifest": _sha256(MANIFEST_JSON_PATH),
        "execution_addendum": _sha256(ADDENDUM_PATH),
        "execution_DAG": _sha256(DAG_PATH),
        "environment": environment_hash,
    }
    runner_summary = _runner_dry_run(
        dag=dag, identity_hashes=identity_hashes, environment=environment
    )
    cause = "RuntimeError: S2 transition increment failed at locked floor"
    samples = [
        {
            "sample_id": "PRE-PARITY-STREAM",
            "sample_kind": "streaming_parity",
            "spatial_level": 1,
            "nx": 10,
            "ny": 25,
            "state_id": "legal_critical",
            "dt_class": "adaptive_T1",
            "protocol_id": "transition_probe_12p5V",
            "status": "fail",
            "error_class": "RuntimeError",
            "error_message": "S2 transition increment failed at locked floor",
            "accepted_steps": "",
            "completed": False,
            "stop_reason": "fail_closed_exception_before_atomic_partial_telemetry",
            "finite": "",
            "ledgers_pass": "",
            "lateral_pass": "",
            "peak_rss_bytes": "",
        }
    ]
    preflight_summary = {
        "task_id": "Q2_PHASE1_V2_RUNTIME_AND_FORMAL_RUNNER_READINESS",
        "schema_version": "geophase_phase1_v2_runtime_preflight_v1",
        "status": "fail",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "id_prefix": "PRE-",
        "temporary_case_artifacts_persisted": False,
        "wall_clock_s": None,
        "wall_clock_limit_s": PRE_FLIGHT_LIMIT_S,
        "wall_clock_measurement_status": (
            "not_atomically_published_before_fail_closed_exception"
        ),
        "passing_sample_count": 0,
        "failing_sample_count": 1,
        "sample_count": 1,
        "required_single_step_expected": 18,
        "required_single_step_completed": 0,
        "required_short_trajectory_expected": 9,
        "required_short_trajectory_completed": 0,
        "optional_coarse_trajectory_status": "not_attempted_due_to_required_failure",
        "failures": [{"sample_id": "PRE-PARITY-STREAM", "cause": cause}],
        "peak_rss_bytes": None,
        "partial_telemetry_status": (
            "accepted_rejected_Newton_Krylov_Armijo_dt_ledger_and_RSS_counts_"
            "were_not_atomically_returned_by_the_fail_closed_solver_exception"
        ),
        "non_atomic_precursor_observation": (
            "cache parity control flow for L1 L2 and L4 completed before the "
            "critical streaming trajectory; exact metrics were not published "
            "and therefore do not vote"
        ),
        "performance_repair_consumed": False,
        "baseline_optimization_disposition": {
            "streaming": "blocked_by_legal_critical_locked_floor_failure",
            "sparse_structure_and_factorization_cache": (
                "focused_parity_tests_pass_but_preflight_metrics_non_atomic"
            ),
            "unit_voltage_scaling": (
                "disabled_after_L1_thermal_ledger_parity_4p410635541795736e-12_"
                "exceeded_1e-12"
            ),
            "case_level_CPU_parallelism": "not_reached",
        },
        "prior_attempt_history": [
            {
                "attempt": "startup_instrumentation",
                "numerical_samples_executed": 0,
                "disposition": "Windows_RSS_API_signature_fixed_before_numerical_work",
            },
            {
                "attempt": "baseline_unit_voltage_scaling_candidate",
                "numerical_samples_executed": 1,
                "sample_id": "PRE-PARITY-CACHED-L1",
                "disposition": "candidate_disabled_not_deployed",
                "worst_component": "thermal.signed_residual_W",
                "maximum_normalized_difference": 4.410635541795736e-12,
                "locked_parity_limit": 1.0e-12,
            },
            {
                "attempt": "locked_baseline_critical_streaming_parity",
                "sample_id": "PRE-PARITY-STREAM",
                "disposition": "fail_closed_no_rerun",
                "cause": cause,
            },
        ],
        "code_file_hashes_sha256": code_hashes,
    }
    readiness_summary = {
        "task_id": "Q2_PHASE1_V2_RUNTIME_AND_FORMAL_RUNNER_READINESS",
        "schema_version": "geophase_phase1_v2_runtime_readiness_v1",
        "disposition": "NO_GO_RUNTIME",
        "unique_primary_cause": cause,
        "all_runtime_gate_failures": [cause],
        "performance_repair_consumed": False,
        "performance_repair_opportunity_remaining": True,
        "performance_only_failure": False,
        "unit_voltage_scaling_active": False,
        "unit_voltage_scaling_candidate_disposition": (
            "rejected_before_required_matrix_after_locked_parity_failure"
        ),
        "execution_addendum_sha256": _sha256(ADDENDUM_PATH),
        "execution_addendum_preregistration_commit": prereg["preregistration_commit"],
        "execution_dag_sha256": _sha256(DAG_PATH),
        "environment_sha256": environment_hash,
        "code_tree_sha256": code_tree_hash,
        "campaign_cost_forecast": {},
        "campaign_cost_forecast_status": (
            "not_computed_because_required_critical_stability_gate_failed"
        ),
        "dormant_runner_status": runner_summary["status"],
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifact_count": 0,
        "formal_campaign_authorized": False,
        "validation_status": "pending_post_failure_focused_validation",
        "claim_status": "forbidden",
    }
    _atomic_json(ENVIRONMENT_PATH, environment)
    _atomic_csv(SAMPLES_PATH, samples, SAMPLE_FIELDS)
    _atomic_json(PREFLIGHT_PATH, preflight_summary)
    _atomic_csv(
        COST_PATH,
        [],
        [
            "execution_unit_id",
            "execution_group",
            "spatial_level",
            "time_divisor",
            "full_trajectory",
            "unreserved_accepted_steps",
            "safety_accepted_steps",
            "absolute_floor_accepted_steps",
            "unreserved_wall_clock_s",
            "safety_wall_clock_s",
            "predicted_output_bytes",
        ],
    )
    _atomic_json(RUNNER_PATH, runner_summary)
    _atomic_json(READINESS_PATH, readiness_summary)
    _atomic_text(
        REPORT_PATH,
        _report(readiness_summary, preflight_summary, runner_summary),
    )
    return readiness_summary


def run_readiness() -> dict[str, Any]:
    preflight_started = perf_counter()
    config, addendum, prereg, dag = _authority()
    environment = measure_launch_environment(ROOT)
    environment_hash = _canonical_hash(environment)
    environment["environment_sha256"] = environment_hash
    code_tree_hash, code_hashes = _code_tree_hash()
    identity_hashes = {
        "code_tree": code_tree_hash,
        "S2_config": _sha256(CONFIG_PATH),
        "formal_manifest_contract": _sha256(MANIFEST_CONTRACT_PATH),
        "expanded_manifest": _sha256(MANIFEST_JSON_PATH),
        "execution_addendum": _sha256(ADDENDUM_PATH),
        "execution_DAG": _sha256(DAG_PATH),
        "environment": environment_hash,
    }
    samples: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    grid_contexts: dict[int, tuple[Any, Any, Any, Any]] = {}
    levels = (1, 2, 4)
    states = ("equilibrium", "legal_critical", "high_conductive")
    base_dt = float(config["reference_solver"]["time_grid"]["base_max_step_s"])
    floor_dt = float(config["reference_solver"]["time_grid"]["transition_max_step_s"])

    with tempfile.TemporaryDirectory(prefix="pinn-phase1v2-preflight-") as directory:
        temporary_root = Path(directory)
        for level in levels:
            build_started = perf_counter()
            grid = build_geophase_grid(config, spatial_level=level)
            fields = build_s2_thermal_fields(grid, config)
            closure = effective_vo2_closure_from_v2_config(config)
            cache = build_s2_solver_cache(grid, fields)
            build_wall = perf_counter() - build_started
            grid_contexts[level] = (grid, fields, closure, cache)
            samples.append(
                {
                    "sample_id": f"PRE-CACHE-L{level}",
                    "sample_kind": "cache_build",
                    "spatial_level": level,
                    "nx": grid.nx,
                    "ny": grid.ny,
                    "state_id": "NA",
                    "protocol_id": "NA",
                    "status": "pass",
                    "accepted_steps": 0,
                    "step_wall_time_p50_s": build_wall,
                    "step_wall_time_p90_s": build_wall,
                    "step_wall_time_max_s": build_wall,
                    "achieved_simulated_time_s": 0.0,
                    "completed": True,
                    "stop_reason": "cache_built",
                    "finite": True,
                    "ledgers_pass": True,
                    "lateral_pass": True,
                    "peak_rss_bytes": process_memory().peak_working_set_bytes,
                }
            )

        # Cached/uncached equivalence on the legal critical state for every grid.
        for level in levels:
            grid, fields, closure, cache = grid_contexts[level]
            initial = _state("legal_critical", grid=grid, closure=closure, fields=fields)
            protocol_id = "transition_probe_12p5V"
            cached_row, cached = _single_step_row(
                sample_id=f"PRE-PARITY-CACHED-L{level}",
                sample_kind="equivalence_parity",
                level=level,
                state_id="legal_critical",
                dt_class="base",
                dt_s=base_dt,
                protocol_id=protocol_id,
                state=initial,
                grid=grid,
                closure=closure,
                fields=fields,
                config=config,
                cache=cache,
            )
            if cached is None:
                samples.append(cached_row)
                failures.append({"sample_id": cached_row["sample_id"], "cause": f"{cached_row['error_class']}: {cached_row['error_message']}"})
                break
            direct_started = perf_counter()
            try:
                direct = advance_s2_backward_euler(
                    initial,
                    input_voltage_V=12.5,
                    dt_s=base_dt,
                    grid=grid,
                    closure=closure,
                    fields=fields,
                    config=config,
                    use_equivalent_optimizations=False,
                )
                direct_wall = perf_counter() - direct_started
                parity_details = _step_parity_details(cached, direct)
                parity_worst = max(parity_details, key=parity_details.get)
                parity = parity_details[parity_worst]
                cached_row["parity_max_relative_error"] = parity
                cached_row["parity_worst_component"] = parity_worst
                cached_row["step_wall_time_max_s"] = max(float(cached_row["step_wall_time_max_s"]), direct_wall)
                if parity > 1.0e-12:
                    cached_row["status"] = "fail"
                    cached_row["error_class"] = "equivalence_parity_failure"
                    cached_row["error_message"] = f"max normalized difference {parity:.6e}"
                    failures.append({"sample_id": cached_row["sample_id"], "cause": cached_row["error_message"]})
            except Exception as error:
                cached_row["status"] = "fail"
                cached_row["error_class"] = type(error).__name__
                cached_row["error_message"] = str(error)
                failures.append({"sample_id": cached_row["sample_id"], "cause": f"{type(error).__name__}: {error}"})
            samples.append(cached_row)
            if failures:
                break

        # Streaming/full-history parity uses exactly the same forced grid.
        if not failures:
            level = 1
            grid, fields, closure, cache = grid_contexts[level]
            initial = _state("legal_critical", grid=grid, closure=closure, fields=fields)
            protocol = config["formal_protocols"]["protocols"]["transition_probe_12p5V"]
            parity_stop = 2.0e-8
            forced = fixed_scalar_sample_times(config, parity_stop)
            try:
                history = simulate_s2_protocol(
                    initial,
                    protocol=protocol,
                    grid=grid,
                    closure=closure,
                    fields=fields,
                    config=config,
                    final_time_s=parity_stop,
                    forced_times_s=tuple(forced),
                    cache=cache,
                )
                streamed = run_s2_streaming_protocol(
                    "PRE-PARITY-STREAM",
                    initial,
                    protocol=protocol,
                    grid=grid,
                    closure=closure,
                    fields=fields,
                    config=config,
                    final_time_s=parity_stop,
                    cache=cache,
                )
                parity = max(
                    _normalized_difference(streamed.final_state.temperature_K, history.steps[-1].state.temperature_K, 1.0e-3),
                    _normalized_difference(streamed.final_state.conductive_state, history.steps[-1].state.conductive_state, 1.0e-6),
                    _normalized_difference(streamed.final_state.branch_memory, history.steps[-1].state.branch_memory, 1.0e-6),
                )
                parity_row = {
                    "sample_id": "PRE-PARITY-STREAM",
                    "sample_kind": "streaming_parity",
                    "spatial_level": 1,
                    "nx": grid.nx,
                    "ny": grid.ny,
                    "state_id": "legal_critical",
                    "protocol_id": "transition_probe_12p5V",
                    "status": "pass" if parity <= 1.0e-12 and not streamed.protocol_result.steps else "fail",
                    "accepted_steps": streamed.protocol_result.diagnostics.accepted_steps,
                    "step_wall_time_p50_s": streamed.protocol_result.diagnostics.step_wall_time_p50_s,
                    "step_wall_time_p90_s": streamed.protocol_result.diagnostics.step_wall_time_p90_s,
                    "step_wall_time_max_s": streamed.protocol_result.diagnostics.step_wall_time_max_s,
                    "achieved_simulated_time_s": streamed.protocol_result.achieved_final_time_s,
                    "completed": streamed.protocol_result.completed,
                    "stop_reason": streamed.protocol_result.stop_reason,
                    "finite": True,
                    "ledgers_pass": True,
                    "lateral_pass": True,
                    "peak_rss_bytes": process_memory().peak_working_set_bytes,
                    "parity_max_relative_error": parity,
                }
            except Exception as error:
                parity_row = {
                    "sample_id": "PRE-PARITY-STREAM",
                    "sample_kind": "streaming_parity",
                    "spatial_level": 1,
                    "nx": grid.nx,
                    "ny": grid.ny,
                    "state_id": "legal_critical",
                    "protocol_id": "transition_probe_12p5V",
                    "status": "fail",
                    "error_class": type(error).__name__,
                    "error_message": str(error),
                    "accepted_steps": "",
                    "completed": False,
                    "stop_reason": "fail_closed_exception_before_atomic_partial_telemetry",
                    "finite": "",
                    "ledgers_pass": "",
                    "lateral_pass": "",
                    "peak_rss_bytes": process_memory().peak_working_set_bytes,
                }
            samples.append(parity_row)
            if parity_row["status"] != "pass":
                failures.append(
                    {
                        "sample_id": parity_row["sample_id"],
                        "cause": (
                            f"{parity_row.get('error_class')}: {parity_row.get('error_message')}"
                            if parity_row.get("error_class")
                            else f"streaming parity {parity_row['parity_max_relative_error']:.6e}"
                        ),
                    }
                )

        # Locked 18 single-step samples. Stop immediately on an integrity failure.
        if not failures:
            for level in levels:
                grid, fields, closure, cache = grid_contexts[level]
                for state_id in states:
                    initial = _state(state_id, grid=grid, closure=closure, fields=fields)
                    protocol_id = _protocol_id(state_id)
                    for dt_class, dt_s in (("base", base_dt), ("floor", floor_dt)):
                        row, _step = _single_step_row(
                            sample_id=f"PRE-STEP-L{level}-{state_id}-{dt_class}",
                            sample_kind="single_step",
                            level=level,
                            state_id=state_id,
                            dt_class=dt_class,
                            dt_s=dt_s,
                            protocol_id=protocol_id,
                            state=initial,
                            grid=grid,
                            closure=closure,
                            fields=fields,
                            config=config,
                            cache=cache,
                        )
                        samples.append(row)
                        if row["status"] != "pass":
                            failures.append({"sample_id": row["sample_id"], "cause": f"{row['error_class']}: {row['error_message']}"})
                            break
                    if failures:
                        break
                if failures:
                    break

        # Locked nine bounded trajectories. The total preflight timer remains authoritative.
        if not failures:
            for level in levels:
                grid, fields, closure, cache = grid_contexts[level]
                for state_id in states:
                    elapsed = perf_counter() - preflight_started
                    remaining = PRE_FLIGHT_LIMIT_S - elapsed - OUTPUT_RESERVE_S
                    if remaining <= 0.0:
                        failures.append({"sample_id": f"PRE-TRAJ-L{level}-{state_id}", "cause": "preflight wall-clock budget exhausted before mandatory trajectory"})
                        break
                    row = _trajectory_row(
                        sample_id=f"PRE-TRAJ-L{level}-{state_id}",
                        sample_kind="short_trajectory",
                        level=level,
                        state_id=state_id,
                        protocol_id=_protocol_id(state_id),
                        initial_state=_state(state_id, grid=grid, closure=closure, fields=fields),
                        grid=grid,
                        closure=closure,
                        fields=fields,
                        config=config,
                        cache=cache,
                        temporary_root=temporary_root,
                        maximum_accepted_steps=128,
                        final_time_s=1.0e-6,
                        maximum_wall_clock_s=remaining,
                        identity_hashes=identity_hashes,
                    )
                    samples.append(row)
                    if row["status"] != "pass":
                        failures.append({"sample_id": row["sample_id"], "cause": f"{row['error_class']}: {row['error_message'] or row['stop_reason']}"})
                        break
                if failures:
                    break

        optional_status = "not_attempted_due_to_required_failure"
        if not failures:
            elapsed = perf_counter() - preflight_started
            remaining = PRE_FLIGHT_LIMIT_S - elapsed - OUTPUT_RESERVE_S
            if remaining > 30.0:
                level = 1
                grid, fields, closure, cache = grid_contexts[level]
                row = _trajectory_row(
                    sample_id="PRE-OPTIONAL-L1-12P5V-20US",
                    sample_kind="optional_long_prefix",
                    level=level,
                    state_id="legal_critical",
                    protocol_id="transition_probe_12p5V",
                    initial_state=_state("legal_critical", grid=grid, closure=closure, fields=fields),
                    grid=grid,
                    closure=closure,
                    fields=fields,
                    config=config,
                    cache=cache,
                    temporary_root=temporary_root,
                    maximum_accepted_steps=None,
                    final_time_s=2.0e-5,
                    maximum_wall_clock_s=min(600.0, remaining),
                    identity_hashes=identity_hashes,
                )
                if row["stop_reason"] == "maximum_wall_clock_reached" and row["finite"] and row["ledgers_pass"] and row["lateral_pass"]:
                    row["status"] = "pass"
                    row["error_class"] = ""
                    row["error_message"] = "optional wall-clock truncation is nonvoting"
                    optional_status = "wall_clock_truncated_nonvoting"
                else:
                    optional_status = "completed" if row["status"] == "pass" else "failed"
                samples.append(row)
                if row["status"] != "pass":
                    failures.append({"sample_id": row["sample_id"], "cause": f"{row['error_class']}: {row['error_message'] or row['stop_reason']}"})
            else:
                optional_status = "not_attempted_insufficient_remaining_budget_nonvoting"

        preflight_wall = perf_counter() - preflight_started

    runner_summary = _runner_dry_run(
        dag=dag, identity_hashes=identity_hashes, environment=environment
    )
    cost_rows: list[dict[str, Any]] = []
    forecast: dict[str, Any] = {}
    if not failures:
        try:
            cost_rows, forecast = build_campaign_cost_forecast(
                execution_dag=dag,
                sample_rows=samples,
                environment=environment,
                floor_dt_s=floor_dt,
                disk_free_fraction_min=0.20,
            )
        except Exception as error:
            failures.append({"sample_id": "PRE-COST-FORECAST", "cause": f"{type(error).__name__}: {error}"})

    peak_rss = max((int(row.get("peak_rss_bytes", 0)) for row in samples), default=process_memory().peak_working_set_bytes)
    environment["process_peak_working_set_bytes_after_preflight"] = peak_rss
    environment["preflight_target_machine_binding"] = environment_hash
    preflight_summary = {
        "task_id": "Q2_PHASE1_V2_RUNTIME_AND_FORMAL_RUNNER_READINESS",
        "schema_version": "geophase_phase1_v2_runtime_preflight_v1",
        "status": "pass" if not failures and preflight_wall <= PRE_FLIGHT_LIMIT_S else "fail",
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "id_prefix": "PRE-",
        "temporary_case_artifacts_persisted": False,
        "wall_clock_s": preflight_wall,
        "wall_clock_limit_s": PRE_FLIGHT_LIMIT_S,
        "passing_sample_count": sum(row.get("status") == "pass" for row in samples),
        "failing_sample_count": sum(row.get("status") == "fail" for row in samples),
        "sample_count": len(samples),
        "required_single_step_expected": 18,
        "required_single_step_completed": sum(row.get("sample_kind") == "single_step" for row in samples),
        "required_short_trajectory_expected": 9,
        "required_short_trajectory_completed": sum(row.get("sample_kind") == "short_trajectory" for row in samples),
        "optional_coarse_trajectory_status": optional_status,
        "failures": failures,
        "peak_rss_bytes": peak_rss,
        "performance_repair_consumed": False,
        "baseline_optimization_disposition": {
            "streaming": "active_parity_required",
            "sparse_structure_and_factorization_cache": "active_parity_required",
            "unit_voltage_scaling": (
                "disabled_after_L1_thermal_ledger_parity_4p410635541795736e-12_"
                "exceeded_1e-12"
            ),
            "case_level_CPU_parallelism": "forecast_only_dormant_dispatch",
        },
        "prior_attempt_history": [
            {
                "attempt": "startup_instrumentation",
                "numerical_samples_executed": 0,
                "disposition": "Windows_RSS_API_signature_fixed_before_numerical_work",
            },
            {
                "attempt": "baseline_unit_voltage_scaling_candidate",
                "numerical_samples_executed": 1,
                "sample_id": "PRE-PARITY-CACHED-L1",
                "disposition": "candidate_disabled_not_deployed",
                "worst_component": "thermal.signed_residual_W",
                "maximum_normalized_difference": 4.410635541795736e-12,
                "locked_parity_limit": 1.0e-12,
            },
        ],
        "code_file_hashes_sha256": code_hashes,
    }

    runtime_gate_failures: list[str] = []
    if failures:
        runtime_gate_failures.append(failures[0]["cause"])
    if preflight_wall > PRE_FLIGHT_LIMIT_S:
        runtime_gate_failures.append("preflight_wall_clock_exceeds_900_s")
    if not environment["physical_core_measurement_available"]:
        runtime_gate_failures.append("physical_core_measurement_unavailable")
    if not environment["all_worker_math_thread_limits_equal_one"]:
        runtime_gate_failures.append("worker_math_thread_limit_not_one")
    if runner_summary["status"] != "pass":
        runtime_gate_failures.append("dormant_runner_dry_run_failed")
    if forecast:
        if forecast["safety_lpt_makespan_s"] > 11520.0:
            runtime_gate_failures.append("safety_LPT_makespan_exceeds_11520_s")
        if forecast["unreserved_lpt_makespan_s"] > 14400.0:
            runtime_gate_failures.append("unreserved_LPT_makespan_exceeds_14400_s")
        if forecast["aggregate_worker_rss_fraction_of_launch_available_ram"] > 0.70:
            runtime_gate_failures.append("aggregate_worker_RSS_exceeds_70_percent")
        if forecast["disk_free_fraction_after_forecast"] < 0.20:
            runtime_gate_failures.append("disk_reserve_below_20_percent")
    elif not failures:
        runtime_gate_failures.append("campaign_cost_forecast_unavailable")

    disposition = (
        "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION"
        if not runtime_gate_failures
        else "NO_GO_RUNTIME"
    )
    readiness_summary = {
        "task_id": "Q2_PHASE1_V2_RUNTIME_AND_FORMAL_RUNNER_READINESS",
        "schema_version": "geophase_phase1_v2_runtime_readiness_v1",
        "disposition": disposition,
        "unique_primary_cause": None if not runtime_gate_failures else runtime_gate_failures[0],
        "all_runtime_gate_failures": runtime_gate_failures,
        "performance_repair_consumed": False,
        "performance_repair_opportunity_remaining": True,
        "unit_voltage_scaling_active": False,
        "unit_voltage_scaling_candidate_disposition": (
            "rejected_before_required_matrix_after_locked_parity_failure"
        ),
        "performance_only_failure": bool(
            runtime_gate_failures
            and all(
                cause
                in {
                    "safety_LPT_makespan_exceeds_11520_s",
                    "unreserved_LPT_makespan_exceeds_14400_s",
                    "aggregate_worker_RSS_exceeds_70_percent",
                    "disk_reserve_below_20_percent",
                }
                for cause in runtime_gate_failures
            )
        ),
        "execution_addendum_sha256": _sha256(ADDENDUM_PATH),
        "execution_addendum_preregistration_commit": prereg["preregistration_commit"],
        "execution_dag_sha256": _sha256(DAG_PATH),
        "environment_sha256": environment_hash,
        "code_tree_sha256": code_tree_hash,
        "campaign_cost_forecast": forecast,
        "dormant_runner_status": runner_summary["status"],
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifact_count": 0,
        "formal_campaign_authorized": False,
        "validation_status": "pending_post_preflight_focused_and_full_tests",
        "claim_status": "forbidden_pending_separately_authorized_formal_campaign",
    }

    _atomic_json(ENVIRONMENT_PATH, environment)
    _atomic_csv(SAMPLES_PATH, samples, SAMPLE_FIELDS)
    _atomic_json(PREFLIGHT_PATH, preflight_summary)
    cost_fields = list(cost_rows[0]) if cost_rows else [
        "execution_unit_id",
        "execution_group",
        "spatial_level",
        "time_divisor",
        "full_trajectory",
        "unreserved_accepted_steps",
        "safety_accepted_steps",
        "absolute_floor_accepted_steps",
        "unreserved_wall_clock_s",
        "safety_wall_clock_s",
        "predicted_output_bytes",
    ]
    _atomic_csv(COST_PATH, cost_rows, cost_fields)
    _atomic_json(RUNNER_PATH, runner_summary)
    _atomic_json(READINESS_PATH, readiness_summary)
    _atomic_text(REPORT_PATH, _report(readiness_summary, preflight_summary, runner_summary))
    return readiness_summary


def check_evidence() -> None:
    config, addendum, prereg, dag = _authority()
    del config, addendum, dag
    required = (
        ENVIRONMENT_PATH,
        SAMPLES_PATH,
        PREFLIGHT_PATH,
        COST_PATH,
        RUNNER_PATH,
        READINESS_PATH,
        REPORT_PATH,
    )
    if any(not path.is_file() for path in required):
        raise SystemExit("runtime readiness evidence is incomplete")
    readiness = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    runner = json.loads(RUNNER_PATH.read_text(encoding="utf-8"))
    with SAMPLES_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if readiness["formal_execution_count"] != 0 or readiness["formal_artifact_count"] != 0:
        raise SystemExit("readiness evidence crossed the formal boundary")
    if prereg["formal_execution_count"] != 0:
        raise SystemExit("preregistration formal count changed")
    if any(not row["sample_id"].startswith("PRE-") for row in rows):
        raise SystemExit("a runtime sample lacks the PRE prefix")
    if preflight["temporary_case_artifacts_persisted"] is not False:
        raise SystemExit("temporary PRE case artifacts were retained")
    if runner["registry_location"] != "temporary_directory_only":
        raise SystemExit("dormant runner escaped its temporary directory")
    if readiness["disposition"] not in {
        "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "NO_GO_RUNTIME",
    }:
        raise SystemExit("runtime readiness disposition is invalid")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run or validate the non-formal Phase 1-v2 runtime readiness preflight."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--execute-preflight", action="store_true")
    group.add_argument("--record-observed-critical-failure", action="store_true")
    group.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.check:
        check_evidence()
        return
    summary = (
        record_observed_critical_failure()
        if arguments.record_observed_critical_failure
        else run_readiness()
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

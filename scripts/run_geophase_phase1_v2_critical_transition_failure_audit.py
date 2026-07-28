from __future__ import annotations

import os

# Stable environment identity requires one math-library thread. These values
# are assigned before NumPy/SciPy import, matching the locked readiness setup.
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
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any
from uuid import uuid4

import numpy as np
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2AttemptObservation,
    S2State,
    build_s2_solver_cache,
    simulate_s2_protocol,
)
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    measure_launch_environment,
    process_memory,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_critical_transition_failure_audit.yaml"
)
S2_CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
TELEMETRY_PATH = OUTPUT_DIR / "critical_transition_failure_telemetry.json"
ATTEMPTS_PATH = OUTPUT_DIR / "critical_transition_attempts.csv"
DIAGNOSIS_PATH = OUTPUT_DIR / "critical_transition_diagnosis.json"
REPLAY_LOCK_PATH = OUTPUT_DIR / ".critical_transition_failure_audit.replay.lock"


ATTEMPT_FIELDS = [
    "attempt_index",
    "execution_path",
    "state_time_s",
    "dt_s",
    "candidate_time_s",
    "rejection_index",
    "at_locked_floor",
    "endpoint_remainder",
    "candidate_available",
    "candidate_wall_time_s",
    "process_working_set_bytes",
    "process_peak_working_set_bytes",
    "error_class",
    "error_message",
    "max_absolute_delta_s",
    "max_absolute_delta_b",
    "transition_increment",
    "transition_threshold",
    "actual_trigger_component",
    "trigger_cell_row",
    "trigger_cell_column",
    "trigger_cell_x_m",
    "trigger_cell_y_m",
    "T_n_K",
    "T_candidate_K",
    "s_n",
    "s_equilibrium_candidate",
    "s_candidate",
    "b_n",
    "b_candidate",
    "heating_activation",
    "cooling_activation",
    "observed_d_s",
    "conditional_observed_candidate_dt_max_s",
    "branch_H",
    "branch_A",
    "conditional_frozen_activation_dt_max_b",
    "branch_dt_constraint_status",
    "state_BE_identity_max_abs",
    "branch_BE_identity_max_abs",
    "input_voltage_V",
    "device_voltage_V",
    "source_current_A",
    "total_joule_power_W",
    "terminal_device_power_W",
    "nonlinear_method",
    "nonlinear_iterations",
    "nonlinear_converged",
    "krylov_matvecs",
    "armijo_backtracks",
    "predictor_picard_iterations",
    "fallback_picard_iterations",
    "scaled_residual_inf",
    "scaled_update_inf",
    "finite_state",
    "nonlinear_gate_pass",
    "thermal_ledger_relative_residual",
    "circuit_ledger_relative_residual",
    "combined_ledger_relative_residual",
    "device_power_ledger_relative_residual",
    "four_ledgers_pass",
    "lateral_matrix_face_relative_mismatch",
    "lateral_matrix_face_roundoff_ratio",
    "lateral_face_to_cell_global_residual_W",
    "lateral_audit_pass",
    "candidate_integrity_pass",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a mapping")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _stable_environment(environment: dict[str, Any]) -> dict[str, Any]:
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


def verify_execution_identity(
    audit: dict[str, Any],
    *,
    preregistration_commit: str,
    implementation_commit: str,
) -> dict[str, Any]:
    """Verify both immutable layers before the sole numerical replay."""

    if len(preregistration_commit) != 40 or len(implementation_commit) != 40:
        raise ValueError("full 40-character preregistration and implementation SHAs required")
    head = _git("rev-parse", "HEAD")
    if head != implementation_commit:
        raise RuntimeError("HEAD does not equal the locked instrumentation commit")
    if _git("rev-parse", "@{upstream}") != head:
        raise RuntimeError("instrumentation commit is not confirmed on the tracked remote")
    if _git("status", "--porcelain"):
        raise RuntimeError("worktree must be clean before the sole numerical replay")

    base = audit["execution_boundary"]["merged_main_commit"]
    for ancestor, descendant, label in (
        (base, preregistration_commit, "merged main -> preregistration"),
        (preregistration_commit, implementation_commit, "preregistration -> implementation"),
    ):
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"missing required ancestry: {label}")

    base_tree = _git("rev-parse", f"{base}^{{tree}}")
    if base_tree != audit["execution_boundary"]["merged_main_tree"]:
        raise RuntimeError("merged-main scientific tree identity mismatch")
    for path, expected_blob in audit["baseline_scientific_identity"]["key_blobs"].items():
        if _git("rev-parse", f"{base}:{path}") != expected_blob:
            raise RuntimeError(f"baseline scientific blob mismatch: {path}")
    for relative, expected_hash in audit["baseline_scientific_identity"][
        "locked_bytes_sha256"
    ].items():
        if _sha256(ROOT / relative) != expected_hash:
            raise RuntimeError(f"locked authority byte hash mismatch: {relative}")

    prereg_relative = AUDIT_CONFIG_PATH.relative_to(ROOT).as_posix()
    if _git_bytes("show", f"{preregistration_commit}:{prereg_relative}") != AUDIT_CONFIG_PATH.read_bytes():
        raise RuntimeError("audit preregistration bytes changed after their anchor")
    changed = set(
        filter(
            None,
            _git("diff", "--name-only", f"{preregistration_commit}..{implementation_commit}").splitlines(),
        )
    )
    allowed = set(audit["instrumentation_lock"]["allowed_paths"])
    if not changed or not changed <= allowed:
        raise RuntimeError(
            "instrumentation diff escaped its preregistered path allowlist: "
            + ", ".join(sorted(changed - allowed))
        )

    environment = measure_launch_environment(ROOT)
    stable = _stable_environment(environment)
    expected_stable = audit["stable_environment_identity"]["fields"]
    if stable != expected_stable:
        raise RuntimeError("stable machine fingerprint fields changed")
    stable_hash = _canonical_sha256(stable)
    if stable_hash != audit["stable_environment_identity"]["sha256"]:
        raise RuntimeError("stable machine fingerprint hash changed")

    stage = _load_yaml(ROOT / "configs" / "geo2p5d_stage.yaml")
    if int(stage["formal_execution_count"]) != 0:
        raise RuntimeError("formal execution count is no longer zero")
    for output in (TELEMETRY_PATH, ATTEMPTS_PATH, DIAGNOSIS_PATH):
        if output.exists():
            raise FileExistsError(f"audit output already exists: {output}")
    return {
        "merged_main_commit": base,
        "merged_main_tree": base_tree,
        "preregistration_commit": preregistration_commit,
        "preregistration_config_sha256": _sha256(AUDIT_CONFIG_PATH),
        "implementation_commit": implementation_commit,
        "implementation_tree": _git("rev-parse", f"{implementation_commit}^{{tree}}"),
        "instrumentation_changed_paths": sorted(changed),
        "stable_environment": stable,
        "stable_environment_sha256": stable_hash,
        "volatile_environment": {
            "total_ram_bytes": environment["total_ram_bytes"],
            "available_ram_bytes_at_launch": environment["available_ram_bytes_at_launch"],
            "disk_total_bytes": environment["disk_total_bytes"],
            "disk_free_bytes_at_launch": environment["disk_free_bytes_at_launch"],
            "process_working_set_bytes_at_launch": environment[
                "process_working_set_bytes_at_launch"
            ],
            "process_peak_working_set_bytes_at_launch": environment[
                "process_peak_working_set_bytes_at_launch"
            ],
        },
    }


def _ledger_relative_residuals(candidate: Any) -> dict[str, float]:
    return {
        name: float(getattr(candidate.ledgers, name).relative_residual)
        for name in ("thermal", "circuit", "combined", "device_power")
    }


class CriticalAttemptRecorder:
    """Convert immutable candidate observations into the locked audit schema."""

    def __init__(self, *, grid: Any, closure: Any, config: dict[str, Any]) -> None:
        self.grid = grid
        self.closure = closure
        self.config = config
        self.rows: list[dict[str, Any]] = []

    def __call__(self, observation: S2AttemptObservation) -> None:
        memory = process_memory()
        row = {field: None for field in ATTEMPT_FIELDS}
        row.update(
            {
                "attempt_index": len(self.rows) + 1,
                "execution_path": "full_history_control",
                "state_time_s": float(observation.previous_state.time_s),
                "dt_s": float(observation.dt_s),
                "candidate_time_s": None,
                "rejection_index": int(observation.rejection_index),
                "at_locked_floor": bool(observation.at_locked_floor),
                "endpoint_remainder": bool(observation.endpoint_remainder),
                "candidate_available": observation.candidate is not None,
                "candidate_wall_time_s": float(observation.candidate_wall_time_s),
                "process_working_set_bytes": memory.working_set_bytes,
                "process_peak_working_set_bytes": memory.peak_working_set_bytes,
                "error_class": observation.error_class,
                "error_message": observation.error_message,
                "max_absolute_delta_s": observation.conductive_increment,
                "max_absolute_delta_b": observation.branch_increment,
                "transition_increment": observation.transition_increment,
                "transition_threshold": float(observation.transition_threshold),
                "input_voltage_V": float(observation.input_voltage_V),
            }
        )
        candidate = observation.candidate
        if candidate is None:
            self.rows.append(row)
            return

        previous = observation.previous_state
        delta_s = np.abs(candidate.state.conductive_state - previous.conductive_state)
        delta_b = np.abs(candidate.state.branch_memory - previous.branch_memory)
        max_s = float(np.max(delta_s))
        max_b = float(np.max(delta_b))
        if max_s > max_b:
            component = "conductive_state_s"
            index = np.unravel_index(int(np.argmax(delta_s)), delta_s.shape)
        elif max_b > max_s:
            component = "branch_memory_b"
            index = np.unravel_index(int(np.argmax(delta_b)), delta_b.shape)
        else:
            component = "tie_s_and_b"
            index = np.unravel_index(int(np.argmax(np.maximum(delta_s, delta_b))), delta_s.shape)
        iy, ix = (int(index[0]), int(index[1]))

        equilibrium = self.closure.equilibrium_state(
            candidate.state.temperature_K, candidate.state.branch_memory
        )
        heating, cooling = self.closure.branch_activations(
            candidate.state.temperature_K,
            previous.temperature_K,
            observation.dt_s,
        )
        ratio_s = observation.dt_s / self.closure.state_relaxation_s
        predicted_s = (
            previous.conductive_state + ratio_s * equilibrium
        ) / (1.0 + ratio_s)
        ratio_b = observation.dt_s / self.closure.branch_relaxation_s
        predicted_b = (
            previous.branch_memory + ratio_b * (heating - cooling)
        ) / (1.0 + ratio_b * (heating + cooling))

        q = float(observation.transition_threshold)
        observed_d_s = float(abs(equilibrium[iy, ix] - previous.conductive_state[iy, ix]))
        dt_max_s = (
            q * self.closure.state_relaxation_s / (observed_d_s - q)
            if observed_d_s > q
            else None
        )
        h = float(heating[iy, ix])
        c = float(cooling[iy, ix])
        b_n = float(previous.branch_memory[iy, ix])
        branch_H = h + c
        branch_A = h * (1.0 - b_n) - c * (1.0 + b_n)
        branch_denominator = abs(branch_A) - q * branch_H
        dt_max_b = (
            q * self.closure.branch_relaxation_s / branch_denominator
            if branch_denominator > 0.0
            else None
        )
        branch_status = (
            "finite_conditional_frozen_activation_bound"
            if dt_max_b is not None
            else "no_finite_branch_dt_constraint_under_observed_activation"
        )

        arrays = (
            candidate.state.temperature_K,
            candidate.state.conductive_state,
            candidate.state.branch_memory,
            candidate.electrical.potential_V,
            candidate.electrical.cell_joule_power_W,
        )
        finite = bool(
            all(np.isfinite(np.asarray(values, dtype=float)).all() for values in arrays)
            and np.isfinite(
                [
                    candidate.state.device_voltage_V,
                    candidate.electrical.source_current_A,
                    candidate.electrical.terminal_device_power_W,
                ]
            ).all()
        )
        nonlinear_config = self.config["reference_solver"]["nonlinear_tolerances"]
        residual_limit = max(
            float(nonlinear_config["scaled_residual_absolute"]),
            float(nonlinear_config["scaled_residual_relative"]),
        )
        nonlinear_pass = bool(
            candidate.nonlinear.converged
            and candidate.nonlinear.scaled_residual_inf <= residual_limit
            and candidate.nonlinear.scaled_update_inf
            <= float(nonlinear_config["scaled_update_relative"])
        )
        ledger_residuals = _ledger_relative_residuals(candidate)
        gates = self.config["gates"]
        ledger_pass = bool(
            ledger_residuals["thermal"]
            <= float(gates["thermal_ledger_relative_residual_max"])
            and ledger_residuals["circuit"]
            <= float(gates["circuit_ledger_relative_residual_max"])
            and ledger_residuals["combined"]
            <= float(gates["combined_ledger_relative_residual_max"])
            and ledger_residuals["device_power"]
            <= float(gates["device_power_identity_relative_residual_max"])
        )
        lateral_pass = bool(
            candidate.lateral_flux.matrix_face_relative_mismatch <= 1.0e-10
            or candidate.lateral_flux.matrix_face_roundoff_ratio <= 1.0
        )

        row.update(
            {
                "candidate_time_s": float(candidate.state.time_s),
                "actual_trigger_component": component,
                "trigger_cell_row": iy,
                "trigger_cell_column": ix,
                "trigger_cell_x_m": float(self.grid.x_centers_m[ix]),
                "trigger_cell_y_m": float(self.grid.y_centers_m[iy]),
                "T_n_K": float(previous.temperature_K[iy, ix]),
                "T_candidate_K": float(candidate.state.temperature_K[iy, ix]),
                "s_n": float(previous.conductive_state[iy, ix]),
                "s_equilibrium_candidate": float(equilibrium[iy, ix]),
                "s_candidate": float(candidate.state.conductive_state[iy, ix]),
                "b_n": b_n,
                "b_candidate": float(candidate.state.branch_memory[iy, ix]),
                "heating_activation": h,
                "cooling_activation": c,
                "observed_d_s": observed_d_s,
                "conditional_observed_candidate_dt_max_s": dt_max_s,
                "branch_H": branch_H,
                "branch_A": branch_A,
                "conditional_frozen_activation_dt_max_b": dt_max_b,
                "branch_dt_constraint_status": branch_status,
                "state_BE_identity_max_abs": float(
                    np.max(np.abs(candidate.state.conductive_state - predicted_s))
                ),
                "branch_BE_identity_max_abs": float(
                    np.max(np.abs(candidate.state.branch_memory - predicted_b))
                ),
                "device_voltage_V": float(candidate.state.device_voltage_V),
                "source_current_A": float(candidate.electrical.source_current_A),
                "total_joule_power_W": float(
                    np.sum(candidate.electrical.cell_joule_power_W)
                ),
                "terminal_device_power_W": float(
                    candidate.electrical.terminal_device_power_W
                ),
                "nonlinear_method": candidate.nonlinear.method,
                "nonlinear_iterations": int(candidate.nonlinear.iterations),
                "nonlinear_converged": bool(candidate.nonlinear.converged),
                "krylov_matvecs": int(candidate.nonlinear.krylov_matvecs),
                "armijo_backtracks": int(candidate.nonlinear.armijo_backtracks),
                "predictor_picard_iterations": int(
                    candidate.nonlinear.predictor_picard_iterations
                ),
                "fallback_picard_iterations": int(
                    candidate.nonlinear.fallback_picard_iterations
                ),
                "scaled_residual_inf": float(candidate.nonlinear.scaled_residual_inf),
                "scaled_update_inf": float(candidate.nonlinear.scaled_update_inf),
                "finite_state": finite,
                "nonlinear_gate_pass": nonlinear_pass,
                "thermal_ledger_relative_residual": ledger_residuals["thermal"],
                "circuit_ledger_relative_residual": ledger_residuals["circuit"],
                "combined_ledger_relative_residual": ledger_residuals["combined"],
                "device_power_ledger_relative_residual": ledger_residuals[
                    "device_power"
                ],
                "four_ledgers_pass": ledger_pass,
                "lateral_matrix_face_relative_mismatch": float(
                    candidate.lateral_flux.matrix_face_relative_mismatch
                ),
                "lateral_matrix_face_roundoff_ratio": float(
                    candidate.lateral_flux.matrix_face_roundoff_ratio
                ),
                "lateral_face_to_cell_global_residual_W": float(
                    candidate.lateral_flux.face_to_cell_global_residual_W
                ),
                "lateral_audit_pass": lateral_pass,
                "candidate_integrity_pass": bool(
                    finite and nonlinear_pass and ledger_pass and lateral_pass
                ),
            }
        )
        self.rows.append(row)


def _csv_text(rows: list[dict[str, Any]]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ATTEMPT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def publish_audit_bundle(
    output_dir: Path,
    *,
    telemetry: dict[str, Any],
    attempt_rows: list[dict[str, Any]],
    diagnosis: dict[str, Any],
) -> tuple[Path, Path, Path]:
    """Validate all payloads, then atomically replace each final path."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    finals = (
        root / TELEMETRY_PATH.name,
        root / ATTEMPTS_PATH.name,
        root / DIAGNOSIS_PATH.name,
    )
    if any(path.exists() for path in finals):
        raise FileExistsError("critical-transition audit evidence is immutable")
    token = uuid4().hex
    temporaries = tuple(path.with_name(f".{path.name}.tmp-{token}") for path in finals)
    try:
        telemetry_text = json.dumps(telemetry, indent=2, sort_keys=True, allow_nan=False) + "\n"
        attempts_text = _csv_text(attempt_rows)
        diagnosis_text = json.dumps(diagnosis, indent=2, sort_keys=True, allow_nan=False) + "\n"
        for path, content in zip(
            temporaries,
            (telemetry_text, attempts_text, diagnosis_text),
            strict=True,
        ):
            path.write_text(content, encoding="utf-8", newline="\n")

        loaded_telemetry = json.loads(temporaries[0].read_text(encoding="utf-8"))
        loaded_attempts = list(
            csv.DictReader(temporaries[1].read_text(encoding="utf-8").splitlines())
        )
        loaded_diagnosis = json.loads(temporaries[2].read_text(encoding="utf-8"))
        if loaded_telemetry["formal_execution_count"] != 0:
            raise ValueError("telemetry attempted to consume formal execution")
        if loaded_telemetry["formal_artifact_count"] != 0:
            raise ValueError("telemetry attempted to create a formal artifact")
        if len(loaded_attempts) != len(attempt_rows):
            raise ValueError("attempt CSV row-count validation failed")
        if loaded_diagnosis["disposition"] not in {
            "GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION",
            "NO_GO_S2_POSITIVE_ROUTE",
            "AUDIT_INVALID_NO_SCIENTIFIC_DECISION",
        }:
            raise ValueError("invalid audit disposition")
        for temporary, final in zip(temporaries, finals, strict=True):
            os.replace(temporary, final)
    finally:
        for temporary in temporaries:
            if temporary.exists():
                temporary.unlink()
    return finals


def _diagnose_reproduced_failure(
    audit: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    successful = [row for row in rows if row["candidate_available"]]
    required_fields = (
        "actual_trigger_component",
        "finite_state",
        "nonlinear_gate_pass",
        "four_ledgers_pass",
        "lateral_audit_pass",
        "candidate_integrity_pass",
    )
    if (
        not successful
        or len(successful) != len(rows)
        or any(row[field] is None for row in successful for field in required_fields)
    ):
        return _invalid_diagnosis(
            audit,
            "required_candidate_telemetry_missing_due_to_instrumentation",
            rows,
        )
    if any(not row["candidate_integrity_pass"] for row in successful):
        disposition = "NO_GO_S2_POSITIVE_ROUTE"
        reason = "one_or_more_successful_candidates_failed_integrity_gates"
    else:
        final = successful[-1]
        floor = float(audit["locked_controller"]["transition_floor_s"])
        trigger = final["actual_trigger_component"]
        if not final["at_locked_floor"] or trigger not in {
            "conductive_state_s",
            "branch_memory_b",
            "tie_s_and_b",
        }:
            disposition = "NO_GO_S2_POSITIVE_ROUTE"
            reason = "locked_discrete_equations_do_not_uniquely_explain_failure"
        else:
            bounds: list[float] = []
            if trigger in {"conductive_state_s", "tie_s_and_b"}:
                value = final["conditional_observed_candidate_dt_max_s"]
                if value is not None:
                    bounds.append(float(value))
            if trigger in {"branch_memory_b", "tie_s_and_b"}:
                value = final["conditional_frozen_activation_dt_max_b"]
                if value is not None:
                    bounds.append(float(value))
            if not bounds or min(bounds) >= floor:
                disposition = "NO_GO_S2_POSITIVE_ROUTE"
                reason = "conditional_bound_does_not_explain_locked_floor_failure"
            else:
                disposition = "GO_FOR_ONE_VERSIONED_TIME_CONTROLLER_REVISION"
                reason = "sole_failure_is_locked_floor_time_resolution"
    final = successful[-1] if successful else None
    return {
        "task_id": audit["task_id"],
        "schema_version": "geophase_phase1_v2_critical_transition_diagnosis_v1",
        "status": "completed_valid_mechanism_audit",
        "disposition": disposition,
        "primary_reason": reason,
        "actual_trigger_component": None if final is None else final["actual_trigger_component"],
        "failure_time_s": None if final is None else final["state_time_s"],
        "trigger_cell": None
        if final is None
        else {
            "row": final["trigger_cell_row"],
            "column": final["trigger_cell_column"],
            "x_m": final["trigger_cell_x_m"],
            "y_m": final["trigger_cell_y_m"],
        },
        "max_absolute_delta_s": None if final is None else final["max_absolute_delta_s"],
        "max_absolute_delta_b": None if final is None else final["max_absolute_delta_b"],
        "conditional_observed_candidate_dt_max_s": None
        if final is None
        else final["conditional_observed_candidate_dt_max_s"],
        "conditional_frozen_activation_dt_max_b": None
        if final is None
        else final["conditional_frozen_activation_dt_max_b"],
        "branch_dt_constraint_status": None
        if final is None
        else final["branch_dt_constraint_status"],
        "locked_floor_s": audit["locked_controller"]["transition_floor_s"],
        "conservative_branch_worst_case_dt_bound_s": (
            float(audit["analytic_diagnosis"]["transition_gate_q"])
            * float(audit["locked_controller"]["branch_relaxation_s"])
            / (2.0 - float(audit["analytic_diagnosis"]["transition_gate_q"]))
        ),
        "conservative_branch_worst_case_bound_role": "diagnostic_nonvoting_only",
        "all_successful_candidates_integrity_pass": bool(
            successful and all(row["candidate_integrity_pass"] for row in successful)
        ),
        "successful_candidate_count": len(successful),
        "candidate_attempt_count": len(rows),
        "streaming_status": "not_reached_by_preregistered_stop",
        "production_floor_determined": False,
        "time_controller_changed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "phase1_scientific_result": "forbidden_unassessed",
    }


def _invalid_diagnosis(
    audit: dict[str, Any], reason: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "task_id": audit["task_id"],
        "schema_version": "geophase_phase1_v2_critical_transition_diagnosis_v1",
        "status": "audit_invalid",
        "disposition": "AUDIT_INVALID_NO_SCIENTIFIC_DECISION",
        "primary_reason": reason,
        "candidate_attempt_count": len(rows),
        "streaming_status": "not_reached_by_preregistered_stop",
        "production_floor_determined": False,
        "time_controller_changed": False,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "phase1_scientific_result": "forbidden_unassessed",
    }


def run_once(
    *, preregistration_commit: str, implementation_commit: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    audit = _load_yaml(AUDIT_CONFIG_PATH)
    identity = verify_execution_identity(
        audit,
        preregistration_commit=preregistration_commit,
        implementation_commit=implementation_commit,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lock_payload = {
        "task_id": audit["task_id"],
        "status": "sole_real_replay_started",
        "preregistration_commit": preregistration_commit,
        "implementation_commit": implementation_commit,
    }
    descriptor = os.open(REPLAY_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(lock_payload, indent=2, sort_keys=True) + "\n")

    config = _load_yaml(S2_CONFIG_PATH)
    grid = build_geophase_grid(config, spatial_level=1)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    sample = audit["single_locked_replay"]
    initial = S2State(
        time_s=float(sample["start_time_s"]),
        temperature_K=np.full(grid.shape, float(sample["initial_state"]["temperature_K"])),
        conductive_state=np.full(
            grid.shape, float(sample["initial_state"]["conductive_state_s"])
        ),
        branch_memory=np.full(
            grid.shape, float(sample["initial_state"]["branch_memory_b"])
        ),
        device_voltage_V=float(sample["initial_state"]["device_voltage_V"]),
    )
    protocol = config["formal_protocols"]["protocols"][sample["protocol_id"]]
    recorder = CriticalAttemptRecorder(grid=grid, closure=closure, config=config)
    replay_wall_start = perf_counter()
    observed_error: Exception | None = None
    completed_without_expected_failure = False
    try:
        simulate_s2_protocol(
            initial,
            protocol=protocol,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            time_divisor=int(sample["time_divisor"]),
            final_time_s=float(sample["parity_short_window_stop_s"]),
            forced_times_s=tuple(float(value) for value in sample["forced_landing_times_s"]),
            retain_full_history=True,
            cache=build_s2_solver_cache(grid, fields),
            use_equivalent_optimizations=bool(sample["use_equivalent_optimizations"]),
            use_unit_voltage_scaling=bool(sample["use_unit_voltage_scaling"]),
            attempted_candidate_callback=recorder,
        )
        completed_without_expected_failure = True
    except Exception as error:  # one-shot evidence must preserve the exact path
        observed_error = error
    replay_wall_s = perf_counter() - replay_wall_start
    reproduced = bool(
        isinstance(observed_error, RuntimeError)
        and str(observed_error) == "S2 transition increment failed at locked floor"
    )
    if reproduced:
        diagnosis = _diagnose_reproduced_failure(audit, recorder.rows)
        telemetry_status = "completed_expected_locked_floor_failure_reproduced"
    else:
        reason = (
            "full_history_control_completed_without_original_failure"
            if completed_without_expected_failure
            else "full_history_control_did_not_reproduce_original_failure"
        )
        diagnosis = _invalid_diagnosis(audit, reason, recorder.rows)
        telemetry_status = "audit_invalid_original_failure_not_reproduced"
    memory = process_memory()
    telemetry = {
        "task_id": audit["task_id"],
        "schema_version": "geophase_phase1_v2_critical_transition_failure_telemetry_v1",
        "status": telemetry_status,
        "evidence_type": audit["evidence_type"],
        "identity": identity,
        "real_numerical_replay_count": 1,
        "real_numerical_replay_limit": 1,
        "sample_id": sample["sample_id"],
        "execution_path": "full_history_control",
        "streaming_status": "not_reached_by_preregistered_stop",
        "original_failure_reproduced": reproduced,
        "observed_error_class": None if observed_error is None else type(observed_error).__name__,
        "observed_error_message": None if observed_error is None else str(observed_error),
        "failure_time_s": None
        if not recorder.rows
        else recorder.rows[-1]["state_time_s"],
        "attempt_count": len(recorder.rows),
        "successful_candidate_count": sum(
            bool(row["candidate_available"]) for row in recorder.rows
        ),
        "replay_wall_clock_s": float(replay_wall_s),
        "process_working_set_bytes_after_replay": memory.working_set_bytes,
        "process_peak_working_set_bytes_after_replay": memory.peak_working_set_bytes,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "formal_case_generated": False,
        "readiness_rerun": False,
        "time_controller_changed": False,
    }
    return telemetry, recorder.rows, diagnosis


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the sole preregistered Phase 1-v2 critical-transition replay."
    )
    parser.add_argument("--preregistration-commit", required=True)
    parser.add_argument("--implementation-commit", required=True)
    arguments = parser.parse_args()
    telemetry, rows, diagnosis = run_once(
        preregistration_commit=arguments.preregistration_commit,
        implementation_commit=arguments.implementation_commit,
    )
    try:
        publish_audit_bundle(
            OUTPUT_DIR,
            telemetry=telemetry,
            attempt_rows=rows,
            diagnosis=diagnosis,
        )
    except Exception:
        # Keep the exclusive marker: this execution may never be replayed.
        raise
    REPLAY_LOCK_PATH.unlink()
    print(json.dumps(diagnosis, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

"""Prospective NLS reference time-convergence closure.

The contract and metric reformulation in this module are frozen after the
PR #27 T1/T2 diagnosis and before any T4 result is generated.  Historical
T1/T2 artifacts are consumed read-only; this module never reruns them.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter, process_time
from typing import Any, Iterable, Mapping

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_b3v2_solution_level import (
    FINITE_REJECTION_PENALTY,
    _load_fields,
    _macro_events,
    _run_solution_window,
    _weighted_mean_trajectory,
    compare_solution_runs,
    field_error_metrics,
    load_contract as load_b3v2_contract,
)
from pinnpcm.evaluation.geophase_controller_relevance_b3 import (
    _pin_process_to_one_cpu,
)
from pinnpcm.evaluation.geophase_controller_relevance_final_rescue import (
    _atomic_bytes,
    _atomic_json,
    _sha256,
    _to_builtin,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_s2_thermal import (
    effective_vo2_closure_from_v2_config,
)


SCHEMA_VERSION = "geophase_nls_time_convergence_v2"
OVERLAY_SCHEMA_VERSION = "geophase_nls_t8_qualification_overlay_v1"
WORKER_SCHEMA_VERSION = "geophase_nls_time_convergence_worker_v2"
SUMMARY_SCHEMA_VERSION = "geophase_nls_time_convergence_summary_v2"
CONFIG_PATH = ROOT / "configs/geophase_nls_time_convergence_v2.yaml"
B3V2_CONFIG_PATH = ROOT / "configs/geophase_b3v2_solution_level.yaml"
THREAD_NAMES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def load_contract(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected NLS time-convergence contract")
    return payload


def verify_frozen_inputs(contract: Mapping[str, Any]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in contract["frozen_inputs"]:
        relative = Path(str(item["path"]))
        observed = _sha256(ROOT / relative)
        expected = str(item["sha256"])
        if observed != expected:
            raise ValueError(f"frozen time-convergence input drifted: {relative}")
        verified.append({"path": relative.as_posix(), "sha256": observed})
    return verified


def load_t8_overlay(contract: Mapping[str, Any]) -> dict[str, Any]:
    path = ROOT / str(contract["paths"]["overlay"])
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != OVERLAY_SCHEMA_VERSION:
        raise ValueError("unexpected T8 qualification overlay")
    base_path = ROOT / str(payload["base_config"])
    if _sha256(base_path) != str(payload["base_config_sha256"]):
        raise ValueError("T8 overlay base config hash drifted")
    if payload.get("allowed_changes") != [
        "qualification_overlay_identity",
        "reference_solver.formal_time_step_divisors",
    ]:
        raise ValueError("T8 overlay change allowlist drifted")
    return payload


def _without_allowed_overlay_fields(config: Mapping[str, Any]) -> dict[str, Any]:
    clean = deepcopy(dict(config))
    clean.pop("qualification_overlay_identity", None)
    reference = clean.get("reference_solver")
    if not isinstance(reference, dict):
        raise ValueError("resolved S2 config lacks reference_solver")
    reference.pop("formal_time_step_divisors", None)
    return clean


def qualification_scientific_config(
    contract: Mapping[str, Any], time_divisor: int
) -> dict[str, Any]:
    base = resolved_s2_config()
    divisors = list(base["reference_solver"]["formal_time_step_divisors"])
    if divisors != [1, 2, 4]:
        raise ValueError("production time-divisor whitelist drifted")
    if int(time_divisor) != 8:
        if int(time_divisor) not in divisors:
            raise ValueError("undeclared production time divisor")
        return base
    overlay = load_t8_overlay(contract)
    qualified = deepcopy(base)
    overrides = overlay["overrides"]
    qualified["qualification_overlay_identity"] = str(
        overrides["qualification_overlay_identity"]
    )
    qualified["reference_solver"]["formal_time_step_divisors"] = list(
        overrides["reference_solver"]["formal_time_step_divisors"]
    )
    if qualified["reference_solver"]["formal_time_step_divisors"] != [1, 2, 4, 8]:
        raise ValueError("T8 qualification whitelist drifted")
    if _without_allowed_overlay_fields(qualified) != _without_allowed_overlay_fields(base):
        raise ValueError("T8 overlay changed a scientific field")
    return qualified


def _thread_environment(values: Mapping[str, str] | None = None) -> dict[str, str | None]:
    source = os.environ if values is None else values
    return {name: source.get(name) for name in THREAD_NAMES}


def _worker_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in THREAD_NAMES:
        environment[name] = "1"
    return environment


def _published_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload is not a mapping: {path}")
    return payload


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    records = [_to_builtin(dict(row)) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        _atomic_bytes(path, b"\n")
        return
    fieldnames = sorted({key for row in records for key in row})
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in records:
        writer.writerow(
            {
                key: json.dumps(value, sort_keys=True)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
        )
    _atomic_bytes(path, buffer.getvalue().encode("utf-8"))


def run_worker(
    *, contract_path: Path, spec_path: Path, output_path: Path, field_path: Path | None
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    spec = _load_json(spec_path)
    affinity = _pin_process_to_one_cpu()
    started_wall = perf_counter()
    started_cpu = process_time()
    try:
        scientific = qualification_scientific_config(contract, int(spec["time_divisor"]))
        payload = _run_solution_window(spec, scientific, field_path)
        payload.update(
            schema_version=WORKER_SCHEMA_VERSION,
            validity="valid",
            error_class=None,
            error_message=None,
            qualification_contract_sha256=_sha256(contract_path),
            qualification_overlay_sha256=(
                _sha256(ROOT / str(contract["paths"]["overlay"]))
                if int(spec["time_divisor"]) == 8
                else None
            ),
        )
    except Exception as error:
        payload = {
            "schema_version": WORKER_SCHEMA_VERSION,
            "case_id": str(spec.get("case_id", "unknown")),
            "role": str(spec.get("role", "unknown")),
            "solver": str(spec.get("solver", "nls_v1")),
            "time_divisor": spec.get("time_divisor"),
            "validity": "invalid",
            "local_pass": False,
            "error_class": type(error).__name__,
            "error_message": str(error),
            "wall_time_s": float(perf_counter() - started_wall),
            "cpu_time_s": float(process_time() - started_cpu),
        }
    payload["affinity"] = affinity
    payload["thread_environment"] = _thread_environment()
    _atomic_json(output_path, payload)
    return payload


def _invoke_worker(
    *,
    contract_path: Path,
    spec: Mapping[str, Any],
    output_path: Path,
    field_path: Path | None,
    timeout_s: float,
) -> dict[str, Any]:
    spec_path = output_path.with_suffix(".spec.json")
    _atomic_json(spec_path, dict(spec))
    command = [
        str(ROOT / ".venv/Scripts/python.exe"),
        "-m",
        "pinnpcm.evaluation.geophase_nls_time_convergence_v2",
        "--stage",
        "worker",
        "--config",
        str(contract_path),
        "--worker-spec",
        str(spec_path),
        "--worker-output",
        str(output_path),
    ]
    if field_path is not None:
        command.extend(("--field-output", str(field_path)))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=_worker_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=float(timeout_s),
        check=False,
    )
    if not output_path.exists():
        return {
            "schema_version": WORKER_SCHEMA_VERSION,
            "case_id": str(spec["case_id"]),
            "validity": "invalid",
            "local_pass": False,
            "error_class": "WorkerDidNotPublish",
            "error_message": completed.stderr[-4000:],
            "cpu_time_s": 0.0,
            "wall_time_s": float(timeout_s),
        }
    payload = _load_json(output_path)
    payload["worker_command"] = command
    payload["worker_returncode"] = int(completed.returncode)
    payload["worker_stdout"] = completed.stdout[-4000:]
    payload["worker_stderr"] = completed.stderr[-4000:]
    _atomic_json(output_path, payload)
    return payload


def _prior_worker(contract: Mapping[str, Any], regime: str, divisor: int) -> dict[str, Any]:
    root = ROOT / str(contract["paths"]["prior_workers"])
    return _load_json(root / f"{regime}_nls_v1_T{int(divisor)}.json")


def _prior_spec(contract: Mapping[str, Any], key: str) -> dict[str, Any]:
    return _load_json(ROOT / str(contract[key]["initial_spec"]))


def _metric_thresholds(contract: Mapping[str, Any]) -> dict[str, float]:
    return {
        str(name): float(definition["threshold"])
        for name, definition in contract["metrics"].items()
    }


def _finite_metric(value: Any) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("metric is non-finite")
    return numeric


def derived_coordinates(
    fields: Mapping[str, np.ndarray], scientific: Mapping[str, Any]
) -> dict[str, np.ndarray]:
    temperature = np.asarray(fields["temperature_K"], dtype=float)
    state = np.asarray(fields["conductive_state"], dtype=float)
    branch = np.asarray(fields["branch_memory"], dtype=float)
    if temperature.shape != state.shape or temperature.shape != branch.shape:
        raise ValueError("field shapes differ")
    if not np.isfinite(temperature).all() or not np.isfinite(state).all() or not np.isfinite(branch).all():
        raise ValueError("field payload contains NaN or Inf")
    closure = effective_vo2_closure_from_v2_config(dict(scientific))
    transition = closure.transition_temperature_K(branch)
    conductivity = closure.conductivity_S_m(temperature, state)
    if not np.isfinite(conductivity).all() or np.any(conductivity <= 0.0):
        raise ValueError("white-box conductivity is non-positive or non-finite")
    return {
        "transition_temperature_K": transition,
        "log_conductivity": np.log(conductivity),
    }


def _signed_ivd_loop(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    ref_records = list(reference["scalar_records"])
    cand_records = list(candidate["scalar_records"])
    ref_current = np.asarray([row["terminal_current_A"] for row in ref_records], dtype=float)
    cand_current = np.asarray([row["terminal_current_A"] for row in cand_records], dtype=float)
    ref_voltage = np.asarray([row["device_voltage_V"] for row in ref_records], dtype=float)
    cand_voltage = np.asarray([row["device_voltage_V"] for row in cand_records], dtype=float)
    if ref_current.shape != cand_current.shape or ref_voltage.shape != cand_voltage.shape:
        raise ValueError("I-Vd loop arrays differ")
    if not all(np.isfinite(item).all() for item in (ref_current, cand_current, ref_voltage, cand_voltage)):
        raise ValueError("I-Vd loop contains NaN or Inf")
    current_min, current_max = float(np.min(ref_current)), float(np.max(ref_current))
    voltage_min, voltage_max = float(np.min(ref_voltage)), float(np.max(ref_voltage))
    current_span = current_max - current_min
    voltage_span = voltage_max - voltage_min
    if current_span <= 0.0 or voltage_span <= 0.0:
        return {"informative": False, "reference_area": 0.0, "candidate_area": 0.0}
    ref_i = (ref_current - current_min) / current_span
    cand_i = (cand_current - current_min) / current_span
    ref_v = (ref_voltage - voltage_min) / voltage_span
    cand_v = (cand_voltage - voltage_min) / voltage_span

    def area(voltage: np.ndarray, current: np.ndarray) -> float:
        return float(
            0.5
            * (
                np.dot(voltage, np.roll(current, -1))
                - np.dot(current, np.roll(voltage, -1))
            )
        )

    return {
        "informative": True,
        "reference_area": area(ref_v, ref_i),
        "candidate_area": area(cand_v, cand_i),
    }


def _loop_gate(loop: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    if not loop.get("informative", False):
        return {"passed": False, **dict(loop), "failure": "NONINFORMATIVE_FIXED_GRID_IVD_LOOP"}
    reference = _finite_metric(loop["reference_area"])
    candidate = _finite_metric(loop["candidate_area"])
    direction_equal = bool(
        (reference == 0.0 and candidate == 0.0)
        or (reference != 0.0 and candidate != 0.0 and math.copysign(1.0, reference) == math.copysign(1.0, candidate))
    )
    relative = abs(candidate - reference) / max(abs(reference), 1.0e-15)
    passed = direction_equal and relative <= float(
        contract["event_and_loop_gates"]["ivd_loop_relative_area_error_max"]
    )
    return {
        "passed": bool(passed),
        "direction_equal": direction_equal,
        "relative_area_error": float(relative),
        **dict(loop),
    }


def _event_gate(comparison: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    event = comparison["macro_events"]["comparison"]
    passed = bool(
        event["sequence_equal"]
        and _finite_metric(event["maximum_absolute_error_s"])
        <= float(contract["event_and_loop_gates"]["event_absolute_error_s_max"])
        and _finite_metric(event["maximum_relative_error"])
        <= float(contract["event_and_loop_gates"]["event_relative_error_max"])
    )
    return {"passed": passed, **dict(event)}


def compare_time_levels(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    b3_contract = load_b3v2_contract(B3V2_CONFIG_PATH)
    base = compare_solution_runs(reference, candidate, b3_contract)
    if not base.get("time_grid_equal", False):
        raise ValueError("time-level artifacts do not share a physical output grid")
    ref_fields = _load_fields(reference)
    cand_fields = _load_fields(candidate)
    scientific = resolved_s2_config()
    ref_derived = derived_coordinates(ref_fields, scientific)
    cand_derived = derived_coordinates(cand_fields, scientific)
    cell_area = float(np.asarray(ref_fields["cell_area_m2"]).reshape(-1)[0])
    full_weights = np.full(np.asarray(ref_fields["temperature_K"]).shape[1:], cell_area)
    active_mask = np.asarray(ref_fields["active_vo2_mask"], dtype=bool)
    active_weights = np.where(active_mask, cell_area, 0.0)
    if not np.any(active_mask):
        raise ValueError("active VO2 mask is empty")
    transition_metrics = field_error_metrics(
        ref_derived["transition_temperature_K"],
        cand_derived["transition_temperature_K"],
        active_weights,
    )
    log_sigma_metrics = field_error_metrics(
        ref_derived["log_conductivity"],
        cand_derived["log_conductivity"],
        active_weights,
    )
    voting = {
        "temperature_rmse_K": _finite_metric(base["fields"]["temperature_K"]["rmse"]),
        "temperature_p95_K": _finite_metric(base["fields"]["temperature_K"]["p95"]),
        "temperature_terminal_p95_K": _finite_metric(base["fields"]["temperature_K"]["terminal_p95"]),
        "transition_temperature_rmse_K": _finite_metric(transition_metrics["rmse"]),
        "log_conductivity_rmse": _finite_metric(log_sigma_metrics["rmse"]),
        "terminal_current_nrmse": _finite_metric(base["terminal_current_nrmse"]),
        "device_voltage_nrmse": _finite_metric(base["device_voltage_nrmse"]),
    }
    raw = {
        name: {key: _finite_metric(value) for key, value in base["fields"][name].items()}
        for name in ("conductive_state", "branch_memory")
    }
    report_only = {
        "transition_temperature_K": {
            key: _finite_metric(value) for key, value in transition_metrics.items()
        },
        "log_conductivity": {
            key: _finite_metric(value) for key, value in log_sigma_metrics.items()
        },
        "raw_fields": raw,
    }
    local_pass = bool(
        reference.get("validity") == "valid"
        and candidate.get("validity") == "valid"
        and reference.get("local_pass")
        and candidate.get("local_pass")
    )
    return {
        "passed": bool(base.get("passed", False)),
        "local_integrity_pass": local_pass,
        "voting_metrics": voting,
        "report_only": report_only,
        "event_gate": _event_gate(base, contract),
        "loop_gate": _loop_gate(_signed_ivd_loop(reference, candidate), contract),
        "macro_events": base["macro_events"],
        "raw_reversal_voting": False,
        "time_grid_equal": True,
    }


def richardson_metric(
    coarse_mid: float,
    mid_fine: float,
    threshold: float,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    e12 = _finite_metric(coarse_mid)
    e24 = _finite_metric(mid_fine)
    if e12 < 0.0 or e24 < 0.0:
        raise ValueError("Richardson errors must be non-negative")
    minimum_order = float(contract["richardson"]["minimum_order"])
    floor_resolved = bool(
        e12 <= float(contract["richardson"]["floor_fraction"]) * threshold
        and e24 <= float(contract["richardson"]["floor_fraction"]) * threshold
    )
    if floor_resolved:
        observed_order: float | None = None
        effective_order = minimum_order
        monotonic = True
        order_pass = True
    else:
        monotonic = bool(e24 < e12)
        observed_order = (
            float(math.log2(e12 / e24)) if e12 > 0.0 and e24 > 0.0 else math.inf
        )
        order_pass = bool(monotonic and observed_order >= minimum_order)
        effective_order = min(
            float(contract["richardson"]["maximum_effective_order"]),
            observed_order,
        )
    denominator = math.pow(2.0, effective_order) - 1.0
    estimate = e24 / denominator if denominator > 0.0 else FINITE_REJECTION_PENALTY
    return {
        "coarse_mid_error": e12,
        "mid_fine_error": e24,
        "threshold": float(threshold),
        "floor_resolved": floor_resolved,
        "observed_order": observed_order,
        "effective_order": float(effective_order),
        "monotonic": monotonic,
        "order_pass": order_pass,
        "fine_error_estimate": float(estimate),
        "estimate_pass": bool(estimate <= threshold),
        "passed": bool(order_pass and estimate <= threshold),
    }


def assess_three_levels(
    coarse_mid: Mapping[str, Any],
    mid_fine: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    require_event_loop: bool = True,
) -> dict[str, Any]:
    thresholds = _metric_thresholds(contract)
    metrics = {
        name: richardson_metric(
            coarse_mid["voting_metrics"][name],
            mid_fine["voting_metrics"][name],
            threshold,
            contract,
        )
        for name, threshold in thresholds.items()
    }
    local_pass = bool(
        coarse_mid["local_integrity_pass"] and mid_fine["local_integrity_pass"]
    )
    event_pass = bool(
        not require_event_loop
        or (coarse_mid["event_gate"]["passed"] and mid_fine["event_gate"]["passed"])
    )
    loop_pass = bool(
        not require_event_loop
        or (coarse_mid["loop_gate"]["passed"] and mid_fine["loop_gate"]["passed"])
    )
    convergence_pass = all(item["order_pass"] for item in metrics.values())
    estimate_pass = all(item["estimate_pass"] for item in metrics.values())
    return {
        "passed": bool(local_pass and event_pass and loop_pass and convergence_pass and estimate_pass),
        "local_integrity_pass": local_pass,
        "event_pass": event_pass,
        "loop_pass": loop_pass,
        "convergence_pass": convergence_pass,
        "estimate_pass": estimate_pass,
        "metrics": metrics,
    }


def assess_four_levels_t8(
    t12: Mapping[str, Any],
    t24: Mapping[str, Any],
    t48: Mapping[str, Any],
    t4_assessment: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    thresholds = _metric_thresholds(contract)
    minimum_order = float(contract["richardson"]["minimum_order"])
    results: dict[str, Any] = {}
    for name, threshold in thresholds.items():
        previous = t4_assessment["metrics"][name]
        e24 = _finite_metric(t24["voting_metrics"][name])
        e48 = _finite_metric(t48["voting_metrics"][name])
        if previous["floor_resolved"]:
            p248 = None
            effective = minimum_order
            order_pass = True
            monotonic = True
        else:
            p124 = _finite_metric(previous["observed_order"])
            monotonic = bool(e48 < e24)
            p248 = float(math.log2(e24 / e48)) if e24 > 0.0 and e48 > 0.0 else math.inf
            order_pass = bool(monotonic and p124 >= minimum_order and p248 >= minimum_order)
            effective = min(1.0, p124, p248)
        estimate = e48 / (math.pow(2.0, effective) - 1.0)
        results[name] = {
            "coarse_mid_error": _finite_metric(t12["voting_metrics"][name]),
            "mid_fine_error": e24,
            "fine_finer_error": e48,
            "p124": previous["observed_order"],
            "p248": p248,
            "effective_order": float(effective),
            "floor_resolved": bool(previous["floor_resolved"]),
            "monotonic": monotonic,
            "order_pass": order_pass,
            "fine_error_estimate": float(estimate),
            "threshold": float(threshold),
            "estimate_pass": bool(estimate <= threshold),
            "passed": bool(order_pass and estimate <= threshold),
        }
    local_pass = all(item["local_integrity_pass"] for item in (t12, t24, t48))
    event_pass = all(item["event_gate"]["passed"] for item in (t12, t24, t48))
    loop_pass = all(item["loop_gate"]["passed"] for item in (t12, t24, t48))
    return {
        "passed": bool(local_pass and event_pass and loop_pass and all(item["passed"] for item in results.values())),
        "local_integrity_pass": bool(local_pass),
        "event_pass": bool(event_pass),
        "loop_pass": bool(loop_pass),
        "convergence_pass": all(item["order_pass"] for item in results.values()),
        "estimate_pass": all(item["estimate_pass"] for item in results.values()),
        "metrics": results,
    }


def _development_spec(contract: Mapping[str, Any], divisor: int) -> dict[str, Any]:
    prior = _prior_spec(contract, "development")
    return {
        **prior,
        "case_id": f"NLS-TIME-DEV-TRANSITION-12P5V-T{int(divisor)}",
        "role": "development_time_refinement",
        "solver": "nls_v1",
        "time_divisor": int(divisor),
        "final_time_s": float(contract["development"]["frozen_window_stop_s"]),
        "sample_interval_s": float(contract["recording"]["sample_interval_s"]),
        "capture_full_fields": True,
        "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_s_max"]),
    }


def _output_root(contract: Mapping[str, Any]) -> Path:
    return ROOT / str(contract["paths"]["output_root"])


def _run_one(
    contract_path: Path,
    contract: Mapping[str, Any],
    directory: Path,
    label: str,
    spec: Mapping[str, Any],
    *,
    capture_fields: bool,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{label}.json"
    field = directory / f"{label}.fields.npz" if capture_fields else None
    return _invoke_worker(
        contract_path=contract_path,
        spec=spec,
        output_path=output,
        field_path=field,
        timeout_s=float(contract["runtime"]["worker_wall_s_max"]) + 60.0,
    )


def _invalid_summary(
    contract: Mapping[str, Any], stage: str, error: Exception, *, output: Path
) -> dict[str, Any]:
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": contract["task_id"],
        "run_id": contract["identity"]["run_id"],
        "stage": stage,
        "validity": "invalid",
        "disposition": str(contract["routes"]["invalid"]),
        "route": "STOP",
        "lifecycle_state": "executed",
        "claim_status": "forbidden",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "error_class": type(error).__name__,
        "error_message": str(error),
        "evidence_type": contract["evidence_type"],
    }
    _atomic_json(output, summary)
    return summary


def _metrics_rows(assessment: Mapping[str, Any], comparison: str) -> list[dict[str, Any]]:
    return [
        {"comparison": comparison, "metric": name, **dict(payload)}
        for name, payload in assessment.get("metrics", {}).items()
    ]


def run_t4(contract_path: Path = CONFIG_PATH) -> dict[str, Any]:
    contract = load_contract(contract_path)
    verify_frozen_inputs(contract)
    root = _output_root(contract) / "development"
    workers = root / "workers"
    summary_path = root / "development_summary.json"
    started = perf_counter()
    try:
        t1 = _prior_worker(contract, "transition_12p5V", 1)
        t2 = _prior_worker(contract, "transition_12p5V", 2)
        t4 = _run_one(contract_path, contract, workers, "transition_12p5V_nls_v1_T4", _development_spec(contract, 4), capture_fields=True)
        if t4.get("validity") != "valid":
            raise RuntimeError(f"T4 worker invalid: {t4.get('error_class')}: {t4.get('error_message')}")
        c12 = compare_time_levels(t1, t2, contract)
        c24 = compare_time_levels(t2, t4, contract)
        assessment = assess_three_levels(c12, c24, contract)
        if assessment["passed"]:
            disposition = str(contract["routes"]["t4_pass"])
            route = "SELECT_T4"
            selected = 4
        elif assessment["local_integrity_pass"] and assessment["event_pass"] and assessment["loop_pass"] and assessment["convergence_pass"]:
            disposition = str(contract["routes"]["t8_unlock"])
            route = "RUN_SINGLE_T8"
            selected = None
        else:
            disposition = str(contract["routes"]["t4_stop"])
            route = "STOP"
            selected = None
        rows = _metrics_rows(assessment, "T1_T2_T4")
        _write_csv(root / "development_richardson_metrics.csv", rows)
        summary = {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "task_id": contract["task_id"],
            "run_id": contract["identity"]["run_id"],
            "stage": "development_t4",
            "validity": "valid",
            "disposition": disposition,
            "route": route,
            "development_refinement": disposition if disposition == "PASS_T4" else None,
            "qualification_time_divisor": selected,
            "assessment": assessment,
            "comparisons": {"T1_T2": c12, "T2_T4": c24},
            "worker_paths": {
                "T1": _published_path(ROOT / str(contract["paths"]["prior_workers"]) / "transition_12p5V_nls_v1_T1.json"),
                "T2": _published_path(ROOT / str(contract["paths"]["prior_workers"]) / "transition_12p5V_nls_v1_T2.json"),
                "T4": _published_path(workers / "transition_12p5V_nls_v1_T4.json"),
            },
            "new_run_count": 1,
            "aggregate_cpu_time_s": float(t4.get("cpu_time_s", 0.0)),
            "wall_time_s": float(perf_counter() - started),
            "lifecycle_state": "numerically_validated",
            "claim_status": "qualified_supported" if selected else "failed_but_informative",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "prospective_reformulation_timing": "frozen_after_PR27_diagnosis_before_T4",
            "evidence_type": contract["evidence_type"],
        }
        _atomic_json(summary_path, summary)
        return summary
    except Exception as error:
        return _invalid_summary(contract, "development_t4", error, output=summary_path)


def run_t8(contract_path: Path = CONFIG_PATH) -> dict[str, Any]:
    contract = load_contract(contract_path)
    verify_frozen_inputs(contract)
    root = _output_root(contract) / "development"
    summary_path = root / "development_summary.json"
    previous = _load_json(summary_path)
    if previous.get("route") != "RUN_SINGLE_T8" or previous.get("validity") != "valid":
        raise ValueError("T8 is not unlocked by a valid T4 assessment")
    started = perf_counter()
    try:
        t1 = _prior_worker(contract, "transition_12p5V", 1)
        t2 = _prior_worker(contract, "transition_12p5V", 2)
        t4 = _load_json(root / "workers/transition_12p5V_nls_v1_T4.json")
        t8 = _run_one(contract_path, contract, root / "workers", "transition_12p5V_nls_v1_T8", _development_spec(contract, 8), capture_fields=True)
        if t8.get("validity") != "valid":
            raise RuntimeError(f"T8 worker invalid: {t8.get('error_class')}: {t8.get('error_message')}")
        c12 = compare_time_levels(t1, t2, contract)
        c24 = compare_time_levels(t2, t4, contract)
        c48 = compare_time_levels(t4, t8, contract)
        assessment = assess_four_levels_t8(c12, c24, c48, previous["assessment"], contract)
        passed = bool(assessment["passed"])
        disposition = str(contract["routes"]["t8_pass" if passed else "t8_stop"])
        summary = {
            **previous,
            "stage": "development_t8",
            "validity": "valid",
            "disposition": disposition,
            "route": "SELECT_T8" if passed else "STOP",
            "development_refinement": disposition if passed else None,
            "qualification_time_divisor": 8 if passed else None,
            "assessment": assessment,
            "comparisons": {"T1_T2": c12, "T2_T4": c24, "T4_T8": c48},
            "new_run_count": 2,
            "aggregate_cpu_time_s": float(previous.get("aggregate_cpu_time_s", 0.0)) + float(t8.get("cpu_time_s", 0.0)),
            "wall_time_s": float(previous.get("wall_time_s", 0.0)) + float(perf_counter() - started),
            "claim_status": "qualified_supported" if passed else "failed_but_informative",
        }
        summary["worker_paths"]["T8"] = _published_path(root / "workers/transition_12p5V_nls_v1_T8.json")
        _write_csv(root / "development_richardson_metrics.csv", _metrics_rows(assessment, "T1_T2_T4_T8"))
        _atomic_json(summary_path, summary)
        return summary
    except Exception as error:
        return _invalid_summary(contract, "development_t8", error, output=summary_path)


def _selected_development(contract: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _output_root(contract) / "development"
    summary = _load_json(root / "development_summary.json")
    divisor = summary.get("qualification_time_divisor")
    if summary.get("validity") != "valid" or divisor not in (4, 8):
        raise ValueError("development has no selected valid divisor")
    worker = _load_json(root / f"workers/transition_12p5V_nls_v1_T{int(divisor)}.json")
    return summary, worker


def _quiescent_spec(contract: Mapping[str, Any], divisor: int) -> dict[str, Any]:
    prior = _prior_spec(contract, "quiescent_check")
    initial_time = float(prior["initial_state"]["time_s"])
    return {
        **prior,
        "case_id": f"NLS-TIME-QUIESCENT-9V-T{int(divisor)}",
        "role": "selected_divisor_quiescent_check",
        "solver": "nls_v1",
        "time_divisor": int(divisor),
        "final_time_s": initial_time + float(contract["quiescent_check"]["relative_window_s"]),
        "sample_interval_s": float(contract["recording"]["sample_interval_s"]),
        "capture_full_fields": True,
        "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_s_max"]),
    }


def run_quiescent(contract_path: Path = CONFIG_PATH) -> dict[str, Any]:
    contract = load_contract(contract_path)
    verify_frozen_inputs(contract)
    root = _output_root(contract) / "quiescent_check"
    summary_path = root / "quiescent_summary.json"
    try:
        development, _ = _selected_development(contract)
        divisor = int(development["qualification_time_divisor"])
        worker = _run_one(contract_path, contract, root / "workers", f"quiescent_9V_nls_v1_T{divisor}", _quiescent_spec(contract, divisor), capture_fields=True)
        if worker.get("validity") != "valid":
            raise RuntimeError(f"selected quiescent worker invalid: {worker.get('error_message')}")
        reference = _prior_worker(contract, "quiescent_9V", 2)
        comparison = compare_time_levels(reference, worker, contract)
        thresholds = _metric_thresholds(contract)
        metric_pass = all(comparison["voting_metrics"][name] <= limit for name, limit in thresholds.items())
        events = comparison["macro_events"]["candidate"]
        event_pass = len(events) == int(contract["quiescent_check"]["required_crossing_count"])
        passed = bool(comparison["local_integrity_pass"] and metric_pass and event_pass)
        disposition = "PASS_SELECTED_LEVEL_QUIESCENT" if passed else str(contract["routes"]["quiescent_stop"])
        summary = {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "task_id": contract["task_id"],
            "run_id": contract["identity"]["run_id"],
            "stage": "quiescent_check",
            "validity": "valid",
            "disposition": disposition,
            "route": "HELDOUT" if passed else "STOP",
            "qualification_time_divisor": divisor,
            "comparison": comparison,
            "metric_pass": metric_pass,
            "macro_event_count": len(events),
            "event_pass": event_pass,
            "new_run_count": int(development["new_run_count"]) + 1,
            "aggregate_cpu_time_s": float(development.get("aggregate_cpu_time_s", 0.0)) + float(worker.get("cpu_time_s", 0.0)),
            "lifecycle_state": "numerically_validated",
            "claim_status": "qualified_supported" if passed else "failed_but_informative",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "evidence_type": contract["evidence_type"],
        }
        _atomic_json(summary_path, summary)
        return summary
    except Exception as error:
        return _invalid_summary(contract, "quiescent_check", error, output=summary_path)


def _complete_up_down(events: Iterable[Mapping[str, Any]]) -> bool:
    directions = [str(item["direction"]) for item in events]
    return any(
        direction == "upward" and "downward" in directions[index + 1 :]
        for index, direction in enumerate(directions)
    )


def write_heldout_unlock(
    path: Path,
    *,
    contract_hash: str,
    anchor_commit: str,
    selected_divisor: int,
    unlocked_at_utc: str,
) -> dict[str, Any]:
    if path.exists():
        raise ValueError("held-out has already been unlocked")
    payload = {
        "unlock_count": 1,
        "contract_sha256": str(contract_hash),
        "anchor_commit": str(anchor_commit),
        "selected_divisor": int(selected_divisor),
        "unlocked_at_utc": str(unlocked_at_utc),
    }
    _atomic_json(path, payload)
    return payload


def _prolong_state_payload(state: Mapping[str, Any], level: int) -> dict[str, Any]:
    factor = int(level)
    if factor not in (1, 2, 4):
        raise ValueError("unsupported nested spatial level")
    payload = deepcopy(dict(state))
    for name in ("temperature_K", "conductive_state", "branch_memory"):
        array = np.asarray(state[name], dtype=float)
        if array.ndim != 2 or not np.isfinite(array).all():
            raise ValueError("invalid L1 state for conservative prolongation")
        payload[name] = np.repeat(np.repeat(array, factor, axis=0), factor, axis=1).tolist()
    return payload


def _heldout_specs(
    contract: Mapping[str, Any], selected_worker: Mapping[str, Any], divisor: int
) -> list[tuple[str, dict[str, Any]]]:
    levels = [1, 2, 4] if divisor == 4 else [2, 4, 8]
    initial = dict(selected_worker["final_state"])
    start = float(initial["time_s"])
    specs: list[tuple[str, dict[str, Any]]] = []
    for regime in ("quiescent_9V", "transition_12p5V"):
        definition = contract["heldout"][regime]
        for time_divisor in levels:
            label = f"{regime}_nls_v1_T{time_divisor}"
            specs.append(
                (
                    label,
                    {
                        "case_id": f"NLS-TIME-HELDOUT-{regime.upper()}-T{time_divisor}",
                        "role": "nls_only_heldout_continuation",
                        "solver": "nls_v1",
                        "protocol_id": str(definition["protocol_id"]),
                        "spatial_level": 1,
                        "time_divisor": int(time_divisor),
                        "initial_state": initial,
                        "final_time_s": start + float(definition["relative_window_s"]),
                        "sample_interval_s": float(contract["recording"]["sample_interval_s"]),
                        "capture_full_fields": True,
                        "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_s_max"]),
                    },
                )
            )
    return specs


def run_heldout(contract_path: Path = CONFIG_PATH) -> dict[str, Any]:
    from datetime import datetime, timezone

    contract = load_contract(contract_path)
    verify_frozen_inputs(contract)
    root = _output_root(contract) / "heldout"
    summary_path = root / "heldout_summary.json"
    try:
        development, selected_worker = _selected_development(contract)
        quiescent = _load_json(_output_root(contract) / "quiescent_check/quiescent_summary.json")
        if quiescent.get("route") != "HELDOUT" or quiescent.get("validity") != "valid":
            raise ValueError("held-out requires a valid quiescent check")
        divisor = int(development["qualification_time_divisor"])
        anchor_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        write_heldout_unlock(
            root / "heldout_unlock.json",
            contract_hash=_sha256(contract_path),
            anchor_commit=anchor_commit,
            selected_divisor=divisor,
            unlocked_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        results: dict[str, dict[str, Any]] = {}
        aggregate_cpu = 0.0
        for label, spec in _heldout_specs(contract, selected_worker, divisor):
            result = _run_one(contract_path, contract, root / "workers", label, spec, capture_fields=True)
            results[label] = result
            aggregate_cpu += float(result.get("cpu_time_s", 0.0))
            if result.get("validity") != "valid":
                raise RuntimeError(f"held-out worker invalid: {label}: {result.get('error_message')}")
        levels = [1, 2, 4] if divisor == 4 else [2, 4, 8]
        assessments: dict[str, Any] = {}
        comparisons: dict[str, Any] = {}
        for regime in ("quiescent_9V", "transition_12p5V"):
            c1 = compare_time_levels(results[f"{regime}_nls_v1_T{levels[0]}"], results[f"{regime}_nls_v1_T{levels[1]}"], contract)
            c2 = compare_time_levels(results[f"{regime}_nls_v1_T{levels[1]}"], results[f"{regime}_nls_v1_T{levels[2]}"], contract)
            comparisons[regime] = {"coarse_mid": c1, "mid_fine": c2}
            assessments[regime] = assess_three_levels(
                c1,
                c2,
                contract,
                require_event_loop=regime == "transition_12p5V",
            )
        finest_transition = results[f"transition_12p5V_nls_v1_T{levels[2]}"]
        transition_fields = _load_fields(finest_transition)
        weights = np.asarray(transition_fields["active_vo2_mask"], dtype=float)
        mean_s = _weighted_mean_trajectory(transition_fields["conductive_state"], weights)
        transition_events = _macro_events(
            np.asarray(transition_fields["times_s"]), mean_s, float(contract["quiescent_check"]["mean_s_threshold"])
        )
        coverage = _complete_up_down(transition_events)
        finest_quiescent = results[f"quiescent_9V_nls_v1_T{levels[2]}"]
        quiescent_fields = _load_fields(finest_quiescent)
        qweights = np.asarray(quiescent_fields["active_vo2_mask"], dtype=float)
        qmean = _weighted_mean_trajectory(quiescent_fields["conductive_state"], qweights)
        qevents = _macro_events(np.asarray(quiescent_fields["times_s"]), qmean, float(contract["quiescent_check"]["mean_s_threshold"]))
        if not coverage:
            disposition, validity, route = str(contract["routes"]["heldout_noninformative"]), "invalid", "STOP"
        elif qevents or not all(item["passed"] for item in assessments.values()):
            disposition, validity, route = str(contract["routes"]["heldout_stop"]), "valid", "STOP"
        else:
            disposition, validity, route = "PASS_NLS_ONLY_HELDOUT_CONTINUATION", "valid", "COST_PREFLIGHT"
        rows: list[dict[str, Any]] = []
        for regime, assessment in assessments.items():
            rows.extend(_metrics_rows(assessment, regime))
        _write_csv(root / "heldout_richardson_metrics.csv", rows)
        summary = {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "task_id": contract["task_id"],
            "run_id": contract["identity"]["run_id"],
            "stage": "heldout",
            "validity": validity,
            "disposition": disposition,
            "route": route,
            "qualification_time_divisor": divisor,
            "time_levels": levels,
            "transition_complete_up_down_pair": coverage,
            "quiescent_macro_event_count": len(qevents),
            "assessments": assessments,
            "comparisons": comparisons,
            "new_run_count": int(quiescent["new_run_count"]) + 6,
            "aggregate_cpu_time_s": float(quiescent.get("aggregate_cpu_time_s", 0.0)) + aggregate_cpu,
            "lifecycle_state": "numerically_validated" if validity == "valid" else "executed",
            "claim_status": "qualified_supported" if route == "COST_PREFLIGHT" else "failed_but_informative" if validity == "valid" else "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "evidence_type": contract["evidence_type"],
        }
        _atomic_json(summary_path, summary)
        return summary
    except Exception as error:
        return _invalid_summary(contract, "heldout", error, output=summary_path)


def _profile_initial_state(contract: Mapping[str, Any], regime: str, level: int) -> dict[str, Any]:
    key = "quiescent_check" if regime == "quiescent_9V" else "development"
    spec = _prior_spec(contract, key)
    return _prolong_state_payload(spec["initial_state"], level)


def _profile_specs(
    contract: Mapping[str, Any], divisor: int
) -> list[tuple[str, dict[str, Any]]]:
    cost = contract["cost"]
    specs: list[tuple[str, dict[str, Any]]] = []
    for repetition in range(1, int(cost["repetitions"]) + 1):
        regimes = list(cost["regimes"])
        if repetition % 2 == 0:
            regimes.reverse()
        for regime in regimes:
            protocol_id = "quiescent_9V" if regime == "quiescent_9V" else "transition_probe_12p5V"
            for level in cost["spatial_levels"]:
                initial = _profile_initial_state(contract, regime, int(level))
                start = float(initial["time_s"])
                label = f"{regime}_L{int(level)}_R{repetition}"
                specs.append(
                    (
                        label,
                        {
                            "case_id": f"NLS-TIME-COST-{regime.upper()}-L{int(level)}-R{repetition}",
                            "role": "selected_divisor_cost_profile",
                            "solver": "nls_v1",
                            "protocol_id": protocol_id,
                            "spatial_level": int(level),
                            "time_divisor": int(divisor),
                            "initial_state": initial,
                            "final_time_s": start + float(cost["physical_duration_s"]),
                            "sample_interval_s": float(cost["physical_duration_s"]),
                            "capture_full_fields": False,
                            "maximum_wall_clock_s": float(contract["runtime"]["worker_wall_s_max"]),
                        },
                    )
                )
    return specs


def _lpt_makespan(costs: Iterable[float], worker_count: int) -> float:
    loads = [0.0] * int(worker_count)
    for value in sorted((float(item) for item in costs), reverse=True):
        index = min(range(len(loads)), key=loads.__getitem__)
        loads[index] += value
    return max(loads, default=0.0)


def project_costs(
    medians: Mapping[str, Mapping[str, Mapping[str, float]]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    cost = contract["cost"]
    factor = float(cost["projection_safety_factor"])
    scale = float(cost["single_trajectory_horizon_s"]) / float(cost["physical_duration_s"])
    worst_cpu = {
        int(level): max(
            float(medians[f"L{int(level)}"][regime]["cpu_time_s"])
            for regime in cost["regimes"]
        )
        * factor
        * scale
        for level in cost["spatial_levels"]
    }
    worst_wall = {
        int(level): max(
            float(medians[f"L{int(level)}"][regime]["wall_time_s"])
            for regime in cost["regimes"]
        )
        * factor
        * scale
        for level in cost["spatial_levels"]
    }
    single_wall = worst_wall[1]
    b4b_cpu = 4.0 * worst_cpu[1]
    s0_costs: list[float] = []
    for _ in range(6):
        s0_costs.extend(
            (worst_cpu[1], worst_cpu[2], worst_cpu[4], worst_cpu[4], worst_cpu[4])
        )
    s0_costs.extend([worst_cpu[4]] * 6)
    s0_costs.extend([2.0 * worst_cpu[1]] * 4)
    s0_costs.append(worst_cpu[1])
    fixed_cost = float(contract["cost"]["projection_safety_factor"]) * max(
        float(payload[regime]["cpu_time_s"])
        for payload in medians.values()
        for regime in contract["cost"]["regimes"]
    )
    s0_costs.extend([fixed_cost] * 19)
    if len(s0_costs) != 60:
        raise RuntimeError("fresh-S0 cost projection did not preserve 60 units")
    s0_cpu = float(sum(s0_costs))
    s0_calendar = _lpt_makespan(s0_costs, int(cost["fresh_s0_worker_count"]))
    phase2_cpu = float(cost["phase2_projection_trajectory_equivalents"]) * worst_cpu[4]
    gates = {
        "single_trajectory": single_wall <= float(cost["single_trajectory_wall_s_max"]),
        "b4b_aggregate_cpu": b4b_cpu <= float(cost["b4b_aggregate_cpu_s_max"]),
        "fresh_s0_aggregate_cpu": s0_cpu <= float(cost["fresh_s0_aggregate_cpu_s_max"]),
        "fresh_s0_calendar": s0_calendar <= float(cost["fresh_s0_calendar_s_max"]),
        "phase2_aggregate_cpu": phase2_cpu <= float(cost["phase2_aggregate_cpu_s_max"]),
    }
    return {
        "worst_regime_single_20us_wall_s_by_level": worst_wall,
        "worst_regime_single_20us_cpu_s_by_level": worst_cpu,
        "single_l1_20us_wall_s": single_wall,
        "b4b_aggregate_cpu_s": b4b_cpu,
        "fresh_s0_aggregate_cpu_s": s0_cpu,
        "fresh_s0_four_worker_calendar_s": s0_calendar,
        "phase2_minimal_aggregate_cpu_s": phase2_cpu,
        "gates": gates,
        "passed": all(gates.values()),
        "projection_semantics": "worse_quiescent_or_transition_centered_20ns_rate_by_level_with_1p10_safety",
    }


def run_cost(contract_path: Path = CONFIG_PATH) -> dict[str, Any]:
    contract = load_contract(contract_path)
    verify_frozen_inputs(contract)
    root = _output_root(contract) / "cost"
    summary_path = root / "cost_summary.json"
    try:
        heldout = _load_json(_output_root(contract) / "heldout/heldout_summary.json")
        if heldout.get("route") != "COST_PREFLIGHT" or heldout.get("validity") != "valid":
            raise ValueError("cost preflight requires a valid held-out pass")
        divisor = int(heldout["qualification_time_divisor"])
        rows: list[dict[str, Any]] = []
        aggregate_cpu = 0.0
        for label, spec in _profile_specs(contract, divisor):
            worker = _run_one(contract_path, contract, root / "workers", label, spec, capture_fields=False)
            if worker.get("validity") != "valid" or not worker.get("local_pass"):
                raise RuntimeError(f"cost worker invalid or locally failed: {label}: {worker.get('error_message')}")
            aggregate_cpu += float(worker.get("cpu_time_s", 0.0))
            regime = "quiescent_9V" if label.startswith("quiescent_9V") else "transition_centered_12p5V"
            rows.append(
                {
                    "label": label,
                    "regime": regime,
                    "spatial_level": int(spec["spatial_level"]),
                    "repetition": int(label.rsplit("R", 1)[1]),
                    "wall_time_s": float(worker["wall_time_s"]),
                    "cpu_time_s": float(worker["cpu_time_s"]),
                }
            )
        _write_csv(root / "cost_profiles.csv", rows)
        medians: dict[str, dict[str, dict[str, float]]] = {}
        for level in contract["cost"]["spatial_levels"]:
            medians[f"L{int(level)}"] = {}
            for regime in contract["cost"]["regimes"]:
                subset = [row for row in rows if row["regime"] == regime and int(row["spatial_level"]) == int(level)]
                if len(subset) != int(contract["cost"]["repetitions"]):
                    raise RuntimeError("cost profiling repetition matrix is incomplete")
                medians[f"L{int(level)}"][str(regime)] = {
                    "wall_time_s": statistics.median(float(row["wall_time_s"]) for row in subset),
                    "cpu_time_s": statistics.median(float(row["cpu_time_s"]) for row in subset),
                }
        projection = project_costs(medians, contract)
        passed = bool(projection["passed"])
        disposition = str(contract["routes"]["t4_go" if divisor == 4 else "t8_go"]) if passed else str(contract["routes"]["cost_stop"])
        summary = {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "task_id": contract["task_id"],
            "run_id": contract["identity"]["run_id"],
            "stage": "cost_preflight",
            "validity": "valid",
            "disposition": disposition,
            "route": disposition,
            "candidate_gt_solver": "full_state_nls_v1_dual_gate",
            "qualification_time_divisor": divisor,
            "selected_gt_solver": "none_pending_full_cycle_sentinel",
            "median_profiles": medians,
            "projection": projection,
            "new_run_count": int(heldout["new_run_count"]) + 18,
            "aggregate_cpu_time_s": float(heldout.get("aggregate_cpu_time_s", 0.0)) + aggregate_cpu,
            "lifecycle_state": "numerically_validated",
            "claim_status": "qualified_supported" if passed else "failed_but_informative",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "evidence_type": contract["evidence_type"],
        }
        _atomic_json(summary_path, summary)
        return summary
    except Exception as error:
        return _invalid_summary(contract, "cost_preflight", error, output=summary_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("worker", "t4", "t8", "quiescent", "heldout", "cost"))
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--worker-spec", type=Path)
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--field-output", type=Path)
    args = parser.parse_args(argv)
    if args.stage == "worker":
        if args.worker_spec is None or args.worker_output is None:
            parser.error("worker stage requires --worker-spec and --worker-output")
        payload = run_worker(
            contract_path=args.config,
            spec_path=args.worker_spec,
            output_path=args.worker_output,
            field_path=args.field_output,
        )
    else:
        payload = {
            "t4": run_t4,
            "t8": run_t8,
            "quiescent": run_quiescent,
            "heldout": run_heldout,
            "cost": run_cost,
        }[args.stage](args.config)
    print(json.dumps(_to_builtin(payload), sort_keys=True))
    return 0 if payload.get("validity") == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONFIG_PATH",
    "SCHEMA_VERSION",
    "assess_four_levels_t8",
    "assess_three_levels",
    "compare_time_levels",
    "derived_coordinates",
    "load_contract",
    "load_t8_overlay",
    "project_costs",
    "qualification_scientific_config",
    "richardson_metric",
    "run_cost",
    "run_heldout",
    "run_quiescent",
    "run_t4",
    "run_t8",
    "run_worker",
    "verify_frozen_inputs",
    "write_heldout_unlock",
]

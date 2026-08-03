"""B2 frozen reduced-root qualification for the exact-condensed solver."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_controller_v2 as frozen_controller
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_exact_condensed import (
    ExactCondensedRootFailure,
    solve_exact_condensed_step,
)


SCHEMA_VERSION = "geophase_exact_condensed_b2_v1"


@dataclass(frozen=True)
class B2RootCase:
    case_id: str
    source_kind: str
    source_path: str
    source_index: int | None
    spatial_level: int
    dt_s: float
    input_voltage_V: float
    wall_time_s: float
    prolongation_source_level: int | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("exact-condensed pipeline config must contain a mapping")
    return payload


def verify_frozen_inputs(config: Mapping[str, Any]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in config["frozen_inputs"]:
        relative = Path(str(item["path"]))
        path = ROOT / relative
        observed = _sha256(path)
        expected = str(item["sha256"])
        if observed != expected:
            raise ValueError(
                f"frozen exact-condensed input drifted: {relative}: "
                f"{observed} != {expected}"
            )
        verified.append({"path": relative.as_posix(), "sha256": observed})
    return verified


def build_b2_root_cases(config: Mapping[str, Any]) -> tuple[B2RootCase, ...]:
    b2 = config["b2"]
    caps = {int(level): float(value) for level, value in b2["root_wall_time_s_by_level"].items()}
    cases: list[B2RootCase] = []
    replay_paths = [str(value) for value in b2["failure_replay_paths"]]
    for source_index, source_path in enumerate(replay_paths):
        replay = json.loads((ROOT / source_path).read_text(encoding="utf-8"))["replay"]
        voltage = float(replay["full_input_voltage_V"])
        for family, values in (
            ("original", b2["original_dt_ns"]),
            ("small", b2["small_dt_ns"]),
        ):
            for dt_ns in values:
                label = str(dt_ns).replace(".", "p")
                cases.append(
                    B2RootCase(
                        case_id=f"B2-{family.upper()}-S{source_index + 1}-DT{label}NS",
                        source_kind="failure_replay_previous_state",
                        source_path=source_path,
                        source_index=source_index,
                        spatial_level=1,
                        dt_s=float(dt_ns) * 1.0e-9,
                        input_voltage_V=voltage,
                        wall_time_s=caps[1],
                    )
                )
    hardest = b2["hardest_state"]
    for dt_ns in hardest["dt_ns"]:
        label = str(dt_ns).replace(".", "p")
        cases.append(
            B2RootCase(
                case_id=f"B2-HARDEST-L1-DT{label}NS",
                source_kind="nls_last_accepted_state",
                source_path=str(hardest["source"]),
                source_index=None,
                spatial_level=1,
                dt_s=float(dt_ns) * 1.0e-9,
                input_voltage_V=9.0,
                wall_time_s=caps[1],
            )
        )
    nested = b2["nested_grid_roots"]
    with gzip.open(ROOT / str(hardest["source"]), "rt", encoding="utf-8") as handle:
        hardest_payload = json.load(handle)
    endpoints = np.asarray(hardest_payload["accepted_endpoint_times_s"], dtype=float)
    if endpoints.size < 2:
        raise ValueError("hardest-state trace has no accepted interval for nested roots")
    frozen_last_dt_ns = float((endpoints[-1] - endpoints[-2]) * 1.0e9)
    if not np.isclose(
        frozen_last_dt_ns,
        float(nested["dt_ns"]),
        rtol=0.0,
        atol=1.0e-9,
    ):
        raise ValueError("nested-grid dt does not match the frozen last accepted interval")
    for level in nested["target_levels"]:
        level = int(level)
        cases.append(
            B2RootCase(
                case_id=f"B2-HARDEST-L{level}-NATIVE",
                source_kind="nls_last_accepted_state_prolonged",
                source_path=str(hardest["source"]),
                source_index=None,
                spatial_level=level,
                dt_s=float(nested["dt_ns"]) * 1.0e-9,
                input_voltage_V=9.0,
                wall_time_s=caps[level],
                prolongation_source_level=int(nested["source_level"]),
            )
        )
    if len(cases) != 24 or len({case.case_id for case in cases}) != 24:
        raise ValueError("frozen B2 matrix must mechanically contain 24 unique roots")
    return tuple(cases)


def _hardest_state(path: Path) -> production.S2State:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = _state_from_replay(payload["final_state"])
    endpoints = np.asarray(payload["accepted_endpoint_times_s"], dtype=float)
    if endpoints.size < 2 or abs(state.time_s - endpoints[-1]) > 1.0e-15:
        raise ValueError("hardest-state trace does not end at its final accepted state")
    return state


def _prolong_piecewise_constant(
    state: production.S2State, source_level: int, target_level: int
) -> production.S2State:
    if target_level % source_level:
        raise ValueError("nested grid level must be an integer refinement")
    factor = target_level // source_level
    if factor <= 0:
        raise ValueError("nested grid refinement factor must be positive")

    def prolong(array: np.ndarray) -> np.ndarray:
        return np.repeat(np.repeat(np.asarray(array), factor, axis=0), factor, axis=1)

    return production.S2State(
        time_s=float(state.time_s),
        temperature_K=prolong(state.temperature_K),
        conductive_state=prolong(state.conductive_state),
        branch_memory=prolong(state.branch_memory),
        device_voltage_V=float(state.device_voltage_V),
    )


def load_b2_case_state(case: B2RootCase) -> production.S2State:
    path = ROOT / case.source_path
    if case.source_kind == "failure_replay_previous_state":
        replay = json.loads(path.read_text(encoding="utf-8"))["replay"]
        return _state_from_replay(replay["previous_state"])
    state = _hardest_state(path)
    if case.source_kind == "nls_last_accepted_state":
        return state
    if case.source_kind == "nls_last_accepted_state_prolonged":
        assert case.prolongation_source_level is not None
        return _prolong_piecewise_constant(
            state, case.prolongation_source_level, case.spatial_level
        )
    raise ValueError(f"unsupported B2 state source: {case.source_kind}")


def _finite_step(step: production.S2StepResult) -> bool:
    values = (
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
        step.electrical.ground_current_A,
        step.electrical.joule_power_W,
        step.electrical.terminal_device_power_W,
    )
    return bool(
        all(np.isfinite(np.asarray(value, dtype=float)).all() for value in values)
        and np.isfinite(np.asarray(scalars, dtype=float)).all()
    )


def run_b2_root_case(case: B2RootCase) -> dict[str, Any]:
    scientific = resolved_s2_config()
    grid = build_geophase_grid(scientific, spatial_level=case.spatial_level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    state = load_b2_case_state(case)
    production.validate_s2_state(state, grid, closure)
    timings = production.S2PerformanceTimings()
    started = perf_counter()
    try:
        outcome = solve_exact_condensed_step(
            state,
            input_voltage_V=case.input_voltage_V,
            dt_s=case.dt_s,
            grid=grid,
            closure=closure,
            fields=fields,
            config=scientific,
            cache=cache,
            performance_timings=timings,
        )
    except ExactCondensedRootFailure as error:
        return {
            "schema_version": SCHEMA_VERSION,
            "case": asdict(case),
            "validity": "valid",
            "status": "VALID_FAIL",
            "claim_status": "failed_but_informative",
            "scientific_vote": False,
            "failure_code": error.code,
            "failure_message": str(error),
            "telemetry": asdict(error.telemetry),
            "performance_timings": timings.as_dict(),
            "wall_time_s": float(perf_counter() - started),
            "gates": {"all_required": False},
        }
    step = outcome.step
    integrity = frozen_controller.evaluate_s2_step_integrity(step, scientific)
    gates = scientific["gates"]
    finite_pass = _finite_step(step)
    range_pass = True
    try:
        production.validate_s2_state(step.state, grid, closure)
    except (ValueError, FloatingPointError):
        range_pass = False
    current_pass = bool(
        step.electrical.relative_current_imbalance
        <= float(gates["terminal_current_relative_imbalance_max"])
    )
    power_pass = bool(
        step.electrical.relative_power_imbalance
        <= float(gates["device_power_identity_relative_residual_max"])
    )
    root_gates = {
        "reduced_residual": bool(outcome.telemetry.reduced_residual_inf <= 1.0e-8),
        "full_scaled_residual": bool(
            outcome.telemetry.full_scaled_residual_inf <= 1.0e-8
        ),
        "full_fixed_point_defect": bool(
            outcome.telemetry.full_fixed_point_defect_inf <= 1.0e-8
        ),
        "auxiliary_residual": bool(
            outcome.telemetry.auxiliary_scaled_residual_inf <= 1.0e-12
        ),
        "finite": finite_pass,
        "range": range_pass,
        "current": current_pass,
        "power": power_pass,
        "ledger": bool(integrity.ledger_pass),
        "lateral": bool(integrity.lateral_pass),
    }
    root_gates["all_required"] = bool(all(root_gates.values()))
    return {
        "schema_version": SCHEMA_VERSION,
        "case": asdict(case),
        "validity": "valid",
        "status": "PASS" if root_gates["all_required"] else "VALID_FAIL",
        "claim_status": (
            "qualified_supported"
            if root_gates["all_required"]
            else "failed_but_informative"
        ),
        "scientific_vote": False,
        "failure_code": None if root_gates["all_required"] else "POST_ROOT_GATE_FAILURE",
        "failure_message": None,
        "telemetry": asdict(outcome.telemetry),
        "performance_timings": timings.as_dict(),
        "electrical": {
            "relative_current_imbalance": float(
                step.electrical.relative_current_imbalance
            ),
            "relative_power_imbalance": float(
                step.electrical.relative_power_imbalance
            ),
        },
        "ledger_relative_residuals": integrity.ledger_relative_residuals,
        "lateral_relative_mismatch": integrity.lateral_relative_mismatch,
        "lateral_roundoff_ratio": integrity.lateral_roundoff_ratio,
        "wall_time_s": float(perf_counter() - started),
        "gates": root_gates,
    }


def _write_csv(path: Path, results: list[Mapping[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for result in results:
        telemetry = result.get("telemetry", {})
        rows.append(
            {
                "case_id": result["case"]["case_id"],
                "status": result["status"],
                "spatial_level": result["case"]["spatial_level"],
                "dt_s": result["case"]["dt_s"],
                "wall_time_s": result["wall_time_s"],
                "failure_code": result.get("failure_code"),
                "reduced_residual_inf": telemetry.get("reduced_residual_inf"),
                "full_scaled_residual_inf": telemetry.get(
                    "full_scaled_residual_inf"
                ),
                "full_fixed_point_defect_inf": telemetry.get(
                    "full_fixed_point_defect_inf"
                ),
                "auxiliary_scaled_residual_inf": telemetry.get(
                    "auxiliary_scaled_residual_inf"
                ),
                "newton_iterations": telemetry.get("newton_iterations"),
                "krylov_matvecs": telemetry.get("krylov_matvecs"),
                "reduced_residual_evaluations": telemetry.get(
                    "reduced_residual_evaluations"
                ),
                "line_search_backtracks": telemetry.get(
                    "line_search_backtracks"
                ),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_b2_matrix(
    *,
    config_path: Path,
    output_root: Path,
    script_path: Path,
) -> dict[str, Any]:
    config = _load_config(config_path)
    verified = verify_frozen_inputs(config)
    cases = build_b2_root_cases(config)
    result_root = output_root / "cases"
    result_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    started = perf_counter()
    environment = dict(**__import__("os").environ)
    for name in (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[name] = "1"
    for index, case in enumerate(cases):
        case_path = result_root / f"{case.case_id}.json"
        command = [
            sys.executable,
            str(script_path),
            "--config",
            str(config_path),
            "--output-root",
            str(output_root),
            "--case-id",
            case.case_id,
            "--child",
        ]
        case_started = perf_counter()
        try:
            subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                check=True,
                timeout=case.wall_time_s,
                capture_output=True,
                text=True,
            )
            result = json.loads(case_path.read_text(encoding="utf-8"))
        except subprocess.TimeoutExpired:
            result = {
                "schema_version": SCHEMA_VERSION,
                "case": asdict(case),
                "validity": "valid",
                "status": "VALID_FAIL",
                "claim_status": "failed_but_informative",
                "scientific_vote": False,
                "failure_code": "ROOT_WALL_TIME_EXHAUSTED",
                "failure_message": (
                    f"root exceeded frozen {case.wall_time_s:.0f} s wall cap"
                ),
                "wall_time_s": float(perf_counter() - case_started),
                "telemetry": {},
                "performance_timings": {},
                "gates": {"all_required": False},
            }
            _atomic_json(case_path, result)
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as error:
            result = {
                "schema_version": SCHEMA_VERSION,
                "case": asdict(case),
                "validity": "invalid",
                "status": "INVALID_EXECUTION",
                "claim_status": "forbidden",
                "scientific_vote": False,
                "failure_code": "B2_RUNNER_FAILURE",
                "failure_message": str(error),
                "wall_time_s": float(perf_counter() - case_started),
                "telemetry": {},
                "performance_timings": {},
                "gates": {"all_required": False},
            }
            _atomic_json(case_path, result)
        results.append(result)
        partial = {
            "schema_version": SCHEMA_VERSION,
            "disposition": "IN_PROGRESS",
            "planned_roots": len(cases),
            "executed_roots": len(results),
            "passed_roots": sum(item["status"] == "PASS" for item in results),
            "results": results,
        }
        _atomic_json(output_root / "b2_summary.partial.json", partial)
        if result["status"] != "PASS":
            break
    passed = sum(item["status"] == "PASS" for item in results)
    first_failure = next((item for item in results if item["status"] != "PASS"), None)
    disposition = (
        "GO_B2_FROZEN_REDUCED_ROOTS"
        if len(results) == len(cases) and passed == len(cases)
        else "B2_INVALID_EXECUTION"
        if first_failure is not None and first_failure["validity"] == "invalid"
        else "B2_REDUCED_ROOT_VALID_FAIL"
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": config["evidence_type"],
        "disposition": disposition,
        "lifecycle_state": "executed",
        "claim_status": (
            "qualified_supported"
            if disposition == "GO_B2_FROZEN_REDUCED_ROOTS"
            else "forbidden"
            if disposition == "B2_INVALID_EXECUTION"
            else "failed_but_informative"
        ),
        "scientific_vote": False,
        "planned_roots": len(cases),
        "executed_roots": len(results),
        "passed_roots": passed,
        "unassessed_roots": len(cases) - len(results),
        "all_24_required": True,
        "first_failure": first_failure,
        "verified_frozen_inputs": verified,
        "config_path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": _sha256(config_path),
        "wall_time_s": float(perf_counter() - started),
        "results": results,
    }
    _atomic_json(output_root / "b2_summary.json", summary)
    _write_csv(output_root / "b2_root_results.csv", results)
    return summary


__all__ = [
    "B2RootCase",
    "SCHEMA_VERSION",
    "build_b2_root_cases",
    "load_b2_case_state",
    "run_b2_matrix",
    "run_b2_root_case",
    "verify_frozen_inputs",
]

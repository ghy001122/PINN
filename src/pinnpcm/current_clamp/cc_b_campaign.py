"""Bounded staged execution of the current-clamped CC-B scientific gate."""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from pinnpcm.branchconserve.artifacts import current_process_rss_bytes, system_memory_bytes
from pinnpcm.current_clamp.artifacts import (
    atomic_write_csv,
    atomic_write_json,
    environment_record,
    file_sha256,
)
from pinnpcm.current_clamp.cc_b_artifacts import artifact_manifest, save_cc_b_equilibrium
from pinnpcm.current_clamp.cc_b_contract import CCBContract
from pinnpcm.current_clamp.cc_b_model import (
    build_cc_b_model,
    uniform_electrical_geometry_ratio,
)
from pinnpcm.current_clamp.cc_b_solver import (
    CCBSolveOutcome,
    prolong_temperature,
    restrict_area_average,
    solve_cc_b_equilibrium,
)
from pinnpcm.current_clamp.cc_b_stability import (
    CCBStabilityOutcome,
    certify_current_clamp_stability,
    uniform_mode_operator_regression,
)
from pinnpcm.current_clamp.source_oracle import discover_roots
from pinnpcm.evaluation.q2_qiu_source_oracle import OracleParameters, resistance_and_derivative


class CCBCampaignError(RuntimeError):
    pass


CASE_FIELDS = [
    "sequence_index",
    "identity",
    "defect",
    "branch",
    "current_A",
    "grid",
    "spatial_level",
    "solve_success",
    "solve_code",
    "solver_cpu_s",
    "solver_wall_s",
    "stability_success",
    "stable",
    "stability_cpu_s",
    "stability_wall_s",
    "device_voltage_V",
    "state_mean",
    "thermal_residual_inf",
    "electrical_residual_inf",
    "ledger_max",
    "npz_bytes",
]


def campaign_roots(contract: CCBContract) -> tuple[Path, Path]:
    compact = contract.repository_root / str(contract.raw["outputs"]["compact_root"]) / contract.run_id
    processed = contract.repository_root / str(contract.raw["outputs"]["processed_root"]) / contract.run_id
    return compact, processed


def _stage_path(compact: Path, stage: str) -> Path:
    return compact / "stages" / stage


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CCBCampaignError(f"{path} does not contain a JSON object")
    return payload


def _scalar_temperature(contract: CCBContract, branch: str, current_A: float) -> float:
    params = OracleParameters.from_config(contract.cc_a_config)
    discovery = discover_roots(
        branch=branch,
        current_A=float(current_A),
        params=params,
        config=contract.cc_a_config,
    )
    roots = [root for root in discovery.roots if root.certified]
    if len(roots) != 1:
        raise CCBCampaignError("CC-A scalar initialization root is no longer unique")
    return float(roots[0].temperature_K)


def _identity(defect: str, branch: str, current_A: float, grid: str, *, prefix: str = "") -> str:
    current = f"{current_A * 1.0e3:.1f}".replace(".", "p")
    stem = f"{defect}_{branch}_{current}mA_{grid}"
    return f"{prefix}_{stem}" if prefix else stem


def _ledger_max(solve: CCBSolveOutcome) -> float:
    if solve.evaluation is None:
        return float("nan")
    ledger = solve.evaluation.ledger
    return max(ledger.current_error, ledger.terminal_field_power_error, ledger.field_thermal_error)


def _case_row(
    *,
    index: int,
    identity: str,
    solve: CCBSolveOutcome,
    stability: CCBStabilityOutcome | None,
    npz_bytes: int,
    grid: str,
) -> dict[str, Any]:
    evaluation = solve.evaluation
    return {
        "sequence_index": index,
        "identity": identity,
        "defect": solve.defect,
        "branch": solve.branch,
        "current_A": solve.current_set_A,
        "grid": grid,
        "spatial_level": solve.spatial_level,
        "solve_success": solve.success,
        "solve_code": solve.code,
        "solver_cpu_s": solve.telemetry.cpu_time_s,
        "solver_wall_s": solve.telemetry.wall_time_s,
        "stability_success": None if stability is None else stability.success,
        "stable": None if stability is None else stability.stable,
        "stability_cpu_s": 0.0 if stability is None else stability.telemetry.cpu_time_s,
        "stability_wall_s": 0.0 if stability is None else stability.telemetry.wall_time_s,
        "device_voltage_V": None if evaluation is None else evaluation.device_voltage_V,
        "state_mean": None if evaluation is None else evaluation.active_area_mean_conductive_state,
        "thermal_residual_inf": None if evaluation is None else evaluation.scaled_thermal_residual_inf,
        "electrical_residual_inf": None if evaluation is None else evaluation.scaled_electrical_residual_inf,
        "ledger_max": None if evaluation is None else _ledger_max(solve),
        "npz_bytes": npz_bytes,
    }


def _save_case(
    contract: CCBContract,
    *,
    attempt: str,
    index: int,
    solve: CCBSolveOutcome,
    stability: CCBStabilityOutcome | None,
    grid: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    compact, processed = campaign_roots(contract)
    identity = _identity(
        solve.defect, solve.branch, solve.current_set_A, grid, prefix=attempt
    )
    artifact = save_cc_b_equilibrium(
        processed / attempt,
        compact / attempt,
        identity=identity,
        solve=solve,
        stability=stability,
        metadata={
            "attempt_type": attempt,
            "sequence_index": index,
            "grid": grid,
            "clamp_topology": "algebraic_conductive_sheet_current",
            "scientific_vote": attempt == "formal_matrix",
        },
    )
    return _case_row(
        index=index,
        identity=identity,
        solve=solve,
        stability=stability,
        npz_bytes=int(artifact["npz_bytes"]),
        grid=grid,
    ), artifact


def _write_terminal(
    contract: CCBContract,
    *,
    disposition: str,
    validity: str,
    lifecycle_state: str,
    claim_status: str,
    completed_grid_cases: int,
    matrix_complete: bool,
    cc_b_vote: bool,
    detail: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    compact, processed = campaign_roots(contract)
    payload: dict[str, Any] = {
        "schema_version": "q2_current_clamp_cc_b_terminal_v1",
        "task_id": contract.raw["task_id"],
        "run_id": contract.run_id,
        "validity": validity,
        "lifecycle_state": lifecycle_state,
        "claim_status": claim_status,
        "disposition": disposition,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "legacy_counter_semantics": "non_CC_B_historical_counters_remain_unchanged",
        "cc_b_scientific_vote": cc_b_vote,
        "cc_b_matrix_launch_count": int((compact / "formal_launch.json").exists()),
        "completed_grid_cases": completed_grid_cases,
        "matrix_complete": matrix_complete,
        "detail": detail,
        "evidence_type": contract.raw["evidence_type"],
        "cc_c_authorized": False,
        "pinn_executed": False,
    }
    if extra:
        payload.update(dict(extra))
    atomic_write_json(compact / "terminal.json", payload)
    atomic_write_json(
        compact / "artifact_manifest.json",
        artifact_manifest(compact, contract.repository_root, run_id=contract.run_id),
    )
    if processed.exists():
        atomic_write_json(
            processed / "artifact_manifest.json",
            artifact_manifest(processed, contract.repository_root, run_id=contract.run_id),
        )
    return payload


def run_smoke(contract: CCBContract) -> dict[str, Any]:
    compact, processed = campaign_roots(contract)
    compact.mkdir(parents=True, exist_ok=False)
    processed.mkdir(parents=True, exist_ok=False)
    stage = _stage_path(compact, "smoke")
    stage.mkdir(parents=True, exist_ok=False)
    atomic_write_json(
        compact / "identity.json",
        {
            "schema_version": "q2_current_clamp_cc_b_identity_v1",
            "run_id": contract.run_id,
            "config_path": contract.path.relative_to(contract.repository_root).as_posix(),
            "config_sha256": file_sha256(contract.path),
            "environment": environment_record(contract.repository_root, run_id=contract.run_id),
            "clamp_topology": contract.raw["clamp_topology"],
        },
    )
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    rows: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    outcomes: dict[tuple[float, str], CCBSolveOutcome] = {}
    maximum_rss = 0
    try:
        for index, (current_A, grid) in enumerate(
            ((2.0e-4, "L1"), (2.0e-4, "L2"), (4.0e-4, "L1"), (4.0e-4, "L2")),
            start=1,
        ):
            level = int(contract.raw["geometry_and_thermal"]["spatial_levels"][grid])
            model = build_cc_b_model(
                contract,
                spatial_level=level,
                current_set_A=current_A,
                branch="heating",
                defect="NOM",
            )
            if grid == "L2":
                coarse = outcomes[(current_A, "L1")]
                assert coarse.temperature_K is not None
                initial = prolong_temperature(coarse.temperature_K, model.grid.shape)
            elif current_A == 4.0e-4:
                previous = outcomes[(2.0e-4, "L1")]
                assert previous.temperature_K is not None
                initial = previous.temperature_K
            else:
                initial = np.full(
                    model.grid.shape,
                    _scalar_temperature(contract, "heating", current_A),
                    dtype=float,
                )
            solve = solve_cc_b_equilibrium(model, initial_temperature_K=initial)
            if not solve.success:
                raise CCBCampaignError(f"smoke equilibrium failed: {solve.code}")
            stability = (
                certify_current_clamp_stability(model, temperature_K=solve.temperature_K)
                if current_A == 4.0e-4
                else None
            )
            if stability is not None and not stability.success:
                raise CCBCampaignError(f"smoke stability invalid: {stability.code}")
            row, artifact = _save_case(
                contract,
                attempt="smoke",
                index=index,
                solve=solve,
                stability=stability,
                grid=grid,
            )
            rows.append(row)
            artifacts.append(artifact)
            outcomes[(current_A, grid)] = solve
            maximum_rss = max(maximum_rss, int(current_process_rss_bytes() or 0))
        wall = time.perf_counter() - wall_started
        cpu = time.process_time() - cpu_started
        if wall > float(contract.raw["smoke"]["wall_cap_s"]):
            raise CCBCampaignError("paired smoke exceeded its wall cap")
        atomic_write_csv(stage / "cases.csv", rows, fieldnames=CASE_FIELDS)
        summary = {
            "schema_version": "q2_current_clamp_cc_b_smoke_v1",
            "validity": "valid",
            "passed": True,
            "scientific_vote": False,
            "case_count": len(rows),
            "cases": rows,
            "artifacts": artifacts,
            "aggregate_cpu_s": cpu,
            "calendar_wall_s": wall,
            "maximum_observed_rss_bytes": maximum_rss,
        }
        atomic_write_json(stage / "summary.json", summary)
        return summary
    except Exception as exc:
        summary = {
            "schema_version": "q2_current_clamp_cc_b_smoke_v1",
            "validity": "invalid",
            "passed": False,
            "scientific_vote": False,
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "aggregate_cpu_s": time.process_time() - cpu_started,
            "calendar_wall_s": time.perf_counter() - wall_started,
        }
        atomic_write_json(stage / "summary.json", summary)
        _write_terminal(
            contract,
            disposition="INVALID_CC_B_EXECUTION",
            validity="invalid",
            lifecycle_state="executed",
            claim_status="forbidden",
            completed_grid_cases=0,
            matrix_complete=False,
            cc_b_vote=False,
            detail=str(exc),
        )
        return summary


def _temperature_for_state(contract: CCBContract, state: float, branch: str) -> float:
    params = OracleParameters.from_config(contract.cc_a_config)
    delta = 1 if branch == "heating" else -1
    return float(
        params.critical_temperature_K
        + delta * params.loop_width_K / 2.0
        - np.arctanh(1.0 - 2.0 * state) / params.beta_per_K
    )


def run_uniform_gate(contract: CCBContract) -> dict[str, Any]:
    compact, _processed = campaign_roots(contract)
    smoke = _read_json(_stage_path(compact, "smoke") / "summary.json")
    if smoke.get("validity") != "valid" or smoke.get("passed") is not True:
        raise CCBCampaignError("uniform gate requires a valid paired smoke")
    stage = _stage_path(compact, "uniform_gate")
    stage.mkdir(parents=True, exist_ok=False)
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        params = OracleParameters.from_config(contract.cc_a_config)
        geometry = float(contract.raw["source_mapping"]["geometry_factor_m"])
        electrical_rows: list[dict[str, Any]] = []
        for state in tuple(float(value) for value in contract.raw["uniform_gate"]["source_states"]):
            temperature = _temperature_for_state(contract, state, "heating")
            resistance, _ = resistance_and_derivative(temperature, 1, 1.0, params)
            conductivity = 1.0 / (geometry * float(resistance))
            errors: dict[str, float] = {}
            for grid, level in (("L1", 1), ("L2", 2)):
                ratio = uniform_electrical_geometry_ratio(
                    contract, spatial_level=level, conductivity_S_m=conductivity
                )
                error = abs(ratio - geometry) / geometry
                errors[grid] = error
                electrical_rows.append(
                    {
                        "state": state,
                        "temperature_K": temperature,
                        "grid": grid,
                        "conductivity_S_m": conductivity,
                        "G_over_sigma_m": ratio,
                        "relative_error": error,
                    }
                )
            threshold = float(contract.raw["uniform_gate"]["electrical_geometry_relative_error_max"])
            tie = 64.0 * np.finfo(float).eps
            if errors["L1"] > threshold or errors["L2"] > threshold:
                raise CCBCampaignError("uniform electrical geometry mapping gate failed")
            if errors["L2"] > errors["L1"] and not (
                errors["L1"] <= tie and errors["L2"] <= tie
            ):
                raise CCBCampaignError("L2 did not improve the uniform electrical mapping")

        operator_rows: list[dict[str, Any]] = []
        for branch in ("heating", "cooling"):
            delta = 1 if branch == "heating" else -1
            for current_A in tuple(
                float(value) for value in contract.cc_a_config["current_clamp"]["official_currents_A"]
            ):
                discovery = discover_roots(
                    branch=branch,
                    current_A=current_A,
                    params=params,
                    config=contract.cc_a_config,
                )
                roots = [root for root in discovery.roots if root.certified]
                if len(roots) != 1:
                    raise CCBCampaignError("CC-A root identity drifted during uniform regression")
                root = roots[0]
                model = build_cc_b_model(
                    contract,
                    spatial_level=1,
                    current_set_A=current_A,
                    branch=branch,
                    defect="NOM",
                    uniform_coefficients=True,
                )
                row = uniform_mode_operator_regression(
                    model,
                    equilibrium_temperature_K=root.temperature_K,
                    analytic_lambda_per_s=root.spectral_abscissa_per_s,
                )
                row.update({"branch": branch, "current_A": current_A})
                operator_rows.append(row)
                if row["passed"] is not True:
                    raise CCBCampaignError("uniform topology/operator regression failed")
        summary = {
            "schema_version": "q2_current_clamp_cc_b_uniform_gate_v1",
            "validity": "valid",
            "passed": True,
            "scientific_vote": False,
            "electrical_rows": electrical_rows,
            "operator_rows": operator_rows,
            "aggregate_cpu_s": time.process_time() - cpu_started,
            "calendar_wall_s": time.perf_counter() - wall_started,
        }
        atomic_write_json(stage / "summary.json", summary)
        atomic_write_csv(
            stage / "electrical_mapping.csv",
            electrical_rows,
            fieldnames=list(electrical_rows[0]),
        )
        atomic_write_csv(
            stage / "topology_operator.csv",
            operator_rows,
            fieldnames=list(operator_rows[0]),
        )
        return summary
    except Exception as exc:
        summary = {
            "schema_version": "q2_current_clamp_cc_b_uniform_gate_v1",
            "validity": "invalid",
            "passed": False,
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "aggregate_cpu_s": time.process_time() - cpu_started,
            "calendar_wall_s": time.perf_counter() - wall_started,
        }
        atomic_write_json(stage / "summary.json", summary)
        _write_terminal(
            contract,
            disposition="INVALID_CC_B_EXECUTION",
            validity="invalid",
            lifecycle_state="executed",
            claim_status="forbidden",
            completed_grid_cases=0,
            matrix_complete=False,
            cc_b_vote=False,
            detail=str(exc),
        )
        return summary


def run_budget_gate(
    contract: CCBContract,
    *,
    preexecution_cpu_s: float = 0.0,
    preexecution_wall_s: float = 0.0,
) -> dict[str, Any]:
    compact, processed = campaign_roots(contract)
    smoke = _read_json(_stage_path(compact, "smoke") / "summary.json")
    uniform = _read_json(_stage_path(compact, "uniform_gate") / "summary.json")
    if not (smoke.get("passed") is True and uniform.get("passed") is True):
        raise CCBCampaignError("budget gate requires valid smoke and uniform gates")
    stage = _stage_path(compact, "budget_gate")
    stage.mkdir(parents=True, exist_ok=False)
    rows = smoke["cases"]
    def maximum(grid: str, key: str) -> float:
        values = [float(row[key]) for row in rows if row["grid"] == grid]
        if not values:
            raise CCBCampaignError(f"missing measured {grid} cost: {key}")
        return max(values)
    c_e1 = maximum("L1", "solver_cpu_s")
    c_e2 = maximum("L2", "solver_cpu_s")
    w_e1 = maximum("L1", "solver_wall_s")
    w_e2 = maximum("L2", "solver_wall_s")
    c_s1 = maximum("L1", "stability_cpu_s")
    c_s2 = maximum("L2", "stability_cpu_s")
    w_s1 = maximum("L1", "stability_wall_s")
    w_s2 = maximum("L2", "stability_wall_s")
    if min(c_e1, c_e2, c_s1, c_s2, w_e1, w_e2, w_s1, w_s2) <= 0.0:
        raise CCBCampaignError("valid L1/L2 equilibrium and stability measures are required")
    safety = float(contract.raw["budget"]["safety_multiplier"])
    projected_cpu = safety * (
        18.0 * c_e1 + 18.0 * c_e2 + 18.0 * c_s2 + 4.0 * (10.0 / 6.0) * c_s2
    )
    projected_wall = safety * (
        18.0 * w_e1 + 18.0 * w_e2 + 18.0 * w_s2 + 4.0 * (10.0 / 6.0) * w_s2
    )
    spent_cpu = float(preexecution_cpu_s) + float(smoke["aggregate_cpu_s"]) + float(uniform["aggregate_cpu_s"])
    spent_wall = float(preexecution_wall_s) + float(smoke["calendar_wall_s"]) + float(uniform["calendar_wall_s"])
    memory = system_memory_bytes()
    m2 = int(smoke["maximum_observed_rss_bytes"])
    required_memory = int(
        float(contract.raw["budget"]["memory_multiplier"]) * m2
        + int(contract.raw["budget"]["system_memory_reserve_bytes"])
    )
    free_disk = shutil.disk_usage(contract.repository_root).free
    npz_sizes = [int(row["npz_bytes"]) for row in rows]
    projected_artifacts = int(max(sum(npz_sizes) / len(npz_sizes) * 36.0 * 1.2, 1.0))
    required_free_disk = (
        2 * projected_artifacts
        + int(contract.raw["budget"]["free_space_additional_floor_bytes"])
    )
    cpu_ok = spent_cpu + projected_cpu <= float(contract.raw["budget"]["aggregate_cpu_cap_s"])
    wall_ok = spent_wall + projected_wall <= float(contract.raw["budget"]["calendar_wall_cap_s"])
    memory_ok = memory["available"] is not None and int(memory["available"]) >= required_memory
    artifact_ok = projected_artifacts <= int(contract.raw["budget"]["artifact_bytes_max"])
    disk_ok = free_disk >= required_free_disk
    passed = bool(cpu_ok and wall_ok and memory_ok and artifact_ok and disk_ok)
    summary = {
        "schema_version": "q2_current_clamp_cc_b_budget_gate_v1",
        "validity": "valid",
        "passed": passed,
        "scientific_vote": False,
        "measured": {
            "cE1_cpu_s": c_e1,
            "cE2_cpu_s": c_e2,
            "cS1_cpu_s": c_s1,
            "cS2_cpu_s": c_s2,
            "wE1_s": w_e1,
            "wE2_s": w_e2,
            "wS1_s": w_s1,
            "wS2_s": w_s2,
            "l2_rss_bytes": m2,
        },
        "spent_cpu_s": spent_cpu,
        "spent_wall_s": spent_wall,
        "projected_formal_cpu_s": projected_cpu,
        "projected_formal_wall_s": projected_wall,
        "projected_artifact_bytes": projected_artifacts,
        "system_memory_available_bytes": memory["available"],
        "required_memory_bytes": required_memory,
        "workspace_free_bytes": free_disk,
        "required_free_bytes": required_free_disk,
        "gates": {
            "cpu": cpu_ok,
            "wall": wall_ok,
            "memory": memory_ok,
            "artifact": artifact_ok,
            "disk": disk_ok,
        },
    }
    atomic_write_json(stage / "summary.json", summary)
    if not passed:
        _write_terminal(
            contract,
            disposition="STOP_CC_B_BUDGET_NOT_ADMISSIBLE",
            validity="valid",
            lifecycle_state="executed",
            claim_status="forbidden",
            completed_grid_cases=0,
            matrix_complete=False,
            cc_b_vote=False,
            detail="the preregistered full matrix exceeded a resource gate",
            extra={"budget": summary},
        )
    return summary


def _exclusive_formal_launch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "schema_version": "q2_current_clamp_cc_b_formal_launch_v1",
            "cc_b_matrix_launch_count": 1,
            "launched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _initial_temperature(
    contract: CCBContract,
    model,
    results: Mapping[tuple[str, str, float, str], CCBSolveOutcome],
    key: tuple[str, str, float, str],
) -> np.ndarray:
    defect, branch, current_A, grid = key
    if grid == "L2":
        coarse = results[(defect, branch, current_A, "L1")]
        assert coarse.temperature_K is not None
        return prolong_temperature(coarse.temperature_K, model.grid.shape)
    if defect != "NOM":
        nominal = results[("NOM", branch, current_A, "L1")]
        assert nominal.temperature_K is not None
        return nominal.temperature_K.copy()
    prior = [
        (candidate_current, solve)
        for (candidate_defect, candidate_branch, candidate_current, candidate_grid), solve in results.items()
        if candidate_defect == "NOM" and candidate_branch == branch and candidate_grid == "L1"
        and ((branch == "heating" and candidate_current < current_A) or (branch == "cooling" and candidate_current > current_A))
    ]
    if prior:
        chosen = max(prior, key=lambda item: item[0]) if branch == "heating" else min(prior, key=lambda item: item[0])
        assert chosen[1].temperature_K is not None
        return chosen[1].temperature_K.copy()
    return np.full(
        model.grid.shape,
        _scalar_temperature(contract, branch, current_A),
        dtype=float,
    )


def _write_case_rows(stage: Path, rows: list[dict[str, Any]]) -> None:
    atomic_write_csv(stage / "cases.csv", rows, fieldnames=CASE_FIELDS)


def _compare_k6_k10(
    contract: CCBContract,
    results: Mapping[tuple[str, str, float, str], CCBSolveOutcome],
    k6: Mapping[tuple[str, str, float], CCBStabilityOutcome],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gate = float(contract.stability["comparison_alpha_tau_difference_max"])
    for defect, branch, current_A in tuple(
        (str(item[0]), str(item[1]), float(item[2]))
        for item in contract.stability["comparison_cases"]
    ):
        solve = results[(defect, branch, current_A, "L2")]
        assert solve.temperature_K is not None
        model = build_cc_b_model(
            contract,
            spatial_level=2,
            current_set_A=current_A,
            branch=branch,
            defect=defect,
        )
        k10 = certify_current_clamp_stability(
            model,
            temperature_K=solve.temperature_K,
            eigenpairs=int(contract.stability["comparison_eigenpairs"]),
        )
        if not k10.success:
            raise CCBCampaignError("k=10 comparison spectrum was invalid")
        base = k6[(defect, branch, current_A)]
        difference = abs(
            base.rightmost_spectral_abscissa_per_s - k10.rightmost_spectral_abscissa_per_s
        ) * model.tau0_s
        row = {
            "defect": defect,
            "branch": branch,
            "current_A": current_A,
            "alpha_k6_per_s": base.rightmost_spectral_abscissa_per_s,
            "alpha_k10_per_s": k10.rightmost_spectral_abscissa_per_s,
            "dimensionless_difference": difference,
            "pass": difference <= gate,
            "k10_cpu_s": k10.telemetry.cpu_time_s,
            "k10_wall_s": k10.telemetry.wall_time_s,
        }
        rows.append(row)
        if not row["pass"]:
            raise CCBCampaignError("k=6/k=10 rightmost-spectrum agreement failed")
    return rows


def _area_norm(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(values, dtype=float) ** 2)))


def _y_dependent(values: np.ndarray) -> np.ndarray:
    field = np.asarray(values, dtype=float)
    projection = np.mean(field, axis=0, keepdims=True)
    return field - np.repeat(projection, field.shape[0], axis=0)


def _aggregate_physics(
    contract: CCBContract,
    results: Mapping[tuple[str, str, float, str], CCBSolveOutcome],
) -> dict[str, Any]:
    transition_rows: list[dict[str, Any]] = []
    state_min, state_max = map(float, contract.raw["transition_gate"]["conductive_state_interval"])
    for branch in ("heating", "cooling"):
        for current_A in tuple(float(v) for v in contract.raw["matrix"]["official_currents_A"]):
            evaluation = results[("NOM", branch, current_A, "L2")].evaluation
            assert evaluation is not None
            fraction = float(np.mean((evaluation.conductive_state >= state_min) & (evaluation.conductive_state <= state_max)))
            transition_rows.append(
                {"branch": branch, "current_A": current_A, "transition_area_fraction": fraction}
            )
    threshold = float(contract.raw["transition_gate"]["nominal_l2_area_fraction_min"])
    transition_pass = all(
        max(row["transition_area_fraction"] for row in transition_rows if row["branch"] == branch) >= threshold
        for branch in ("heating", "cooling")
    )

    response_rows: list[dict[str, Any]] = []
    two_d = contract.raw["two_dimensional_gate"]
    for defect in ("LU", "RD"):
        for branch in ("heating", "cooling"):
            for current_A in tuple(float(v) for v in contract.raw["matrix"]["official_currents_A"]):
                nominal_l1 = results[("NOM", branch, current_A, "L1")].temperature_K
                nominal_l2 = results[("NOM", branch, current_A, "L2")].temperature_K
                defect_l1 = results[(defect, branch, current_A, "L1")].temperature_K
                defect_l2 = results[(defect, branch, current_A, "L2")].temperature_K
                assert nominal_l1 is not None and nominal_l2 is not None
                assert defect_l1 is not None and defect_l2 is not None
                delta_l1 = defect_l1 - nominal_l1
                delta_l2 = defect_l2 - nominal_l2
                y_l1 = _y_dependent(delta_l1)
                y_l2 = _y_dependent(delta_l2)
                restricted_y_l2 = restrict_area_average(y_l2, y_l1.shape)
                rms = _area_norm(delta_l2)
                y_norm = _area_norm(y_l2)
                r2d = y_norm / max(rms, 1.0e-300)
                grid_error = _area_norm(y_l1 - restricted_y_l2)
                passed = bool(
                    rms >= float(two_d["response_rms_K_min"])
                    and r2d >= float(two_d["r2d_min"])
                    and y_norm >= float(two_d["grid_uncertainty_multiplier_min"]) * grid_error
                )
                response_rows.append(
                    {
                        "defect": defect,
                        "branch": branch,
                        "current_A": current_A,
                        "response_rms_K": rms,
                        "y_dependent_rms_K": y_norm,
                        "r2d": r2d,
                        "grid_y_uncertainty_K": grid_error,
                        "same_case_pass": passed,
                    }
                )
    response_pass = any(row["same_case_pass"] for row in response_rows)
    return {
        "transition_rows": transition_rows,
        "transition_pass": transition_pass,
        "response_rows": response_rows,
        "two_dimensional_response_pass": response_pass,
        "pass": bool(transition_pass and response_pass),
    }


def run_formal_matrix(contract: CCBContract) -> dict[str, Any]:
    compact, _processed = campaign_roots(contract)
    budget = _read_json(_stage_path(compact, "budget_gate") / "summary.json")
    if budget.get("validity") != "valid" or budget.get("passed") is not True:
        raise CCBCampaignError("formal matrix requires a passed budget gate")
    if (compact / "terminal.json").exists():
        raise CCBCampaignError("a terminal result already exists; formal launch is forbidden")
    _exclusive_formal_launch(compact / "formal_launch.json")
    stage = _stage_path(compact, "formal_matrix")
    stage.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    results: dict[tuple[str, str, float, str], CCBSolveOutcome] = {}
    stability_k6: dict[tuple[str, str, float], CCBStabilityOutcome] = {}
    comparison_rows: list[dict[str, Any]] = []
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        for index, key in enumerate(contract.sequence, start=1):
            defect, branch, current_A, grid = key
            level = int(contract.raw["geometry_and_thermal"]["spatial_levels"][grid])
            model = build_cc_b_model(
                contract,
                spatial_level=level,
                current_set_A=current_A,
                branch=branch,
                defect=defect,
            )
            initial = _initial_temperature(contract, model, results, key)
            solve = solve_cc_b_equilibrium(model, initial_temperature_K=initial)
            if not solve.success:
                raise CCBCampaignError(
                    f"formal equilibrium {index}/36 failed: {solve.code}: {solve.telemetry.failure_detail}"
                )
            stability = None
            if grid == "L2":
                assert solve.temperature_K is not None
                stability = certify_current_clamp_stability(
                    model, temperature_K=solve.temperature_K
                )
                if not stability.success:
                    atomic_write_json(
                        stage / f"stability_invalid_{index:03d}.json", stability
                    )
                    raise CCBCampaignError(f"formal L2 stability invalid at case {index}")
            row, artifact = _save_case(
                contract,
                attempt="formal_matrix",
                index=index,
                solve=solve,
                stability=stability,
                grid=grid,
            )
            rows.append(row)
            artifacts.append(artifact)
            results[key] = solve
            if stability is not None:
                stability_k6[(defect, branch, current_A)] = stability
            _write_case_rows(stage, rows)
            atomic_write_json(stage / "progress.json", {
                "schema_version": "q2_current_clamp_cc_b_progress_v1",
                "cc_b_matrix_launch_count": 1,
                "completed_grid_cases": len(rows),
                "matrix_complete": len(rows) == 36,
                "last_identity": row["identity"],
            })
            if stability is not None and not stability.stable:
                summary = {
                    "schema_version": "q2_current_clamp_cc_b_formal_v1",
                    "validity": "valid",
                    "matrix_complete": False,
                    "completed_grid_cases": len(rows),
                    "cases": rows,
                    "artifacts": artifacts,
                    "aggregate_cpu_s": time.process_time() - cpu_started,
                    "calendar_wall_s": time.perf_counter() - wall_started,
                    "disposition": "STOP_CC_B_UNSTABLE",
                }
                atomic_write_json(stage / "summary.json", summary)
                _write_terminal(
                    contract,
                    disposition="STOP_CC_B_UNSTABLE",
                    validity="valid",
                    lifecycle_state="executed",
                    claim_status="failed_but_informative",
                    completed_grid_cases=len(rows),
                    matrix_complete=False,
                    cc_b_vote=True,
                    detail=f"case {index} had a valid but unstable constrained spectrum",
                    extra={"formal": summary},
                )
                return summary
            if index == 16:
                comparison_rows = _compare_k6_k10(contract, results, stability_k6)
                atomic_write_csv(
                    stage / "k6_k10_comparison.csv",
                    comparison_rows,
                    fieldnames=list(comparison_rows[0]),
                )

        if len(rows) != 36:
            raise CCBCampaignError("formal matrix cardinality was not 36")
        physics = _aggregate_physics(contract, results)
        atomic_write_csv(
            stage / "transition_fields.csv",
            physics["transition_rows"],
            fieldnames=list(physics["transition_rows"][0]),
        )
        atomic_write_csv(
            stage / "two_dimensional_responses.csv",
            physics["response_rows"],
            fieldnames=list(physics["response_rows"][0]),
        )
        disposition = (
            "PASS_CC_B_2D_GATE" if physics["pass"] else "STOP_CC_B_PHYSICS_DEGENERATE"
        )
        summary = {
            "schema_version": "q2_current_clamp_cc_b_formal_v1",
            "validity": "valid",
            "matrix_complete": True,
            "completed_grid_cases": 36,
            "cases": rows,
            "artifacts": artifacts,
            "k6_k10_comparison": comparison_rows,
            "physics": physics,
            "aggregate_cpu_s": time.process_time() - cpu_started,
            "calendar_wall_s": time.perf_counter() - wall_started,
            "disposition": disposition,
        }
        atomic_write_json(stage / "summary.json", summary)
        _write_terminal(
            contract,
            disposition=disposition,
            validity="valid",
            lifecycle_state="numerically_validated" if physics["pass"] else "executed",
            claim_status="qualified_supported" if physics["pass"] else "failed_but_informative",
            completed_grid_cases=36,
            matrix_complete=True,
            cc_b_vote=True,
            detail=(
                "all preregistered CC-B gates passed"
                if physics["pass"]
                else "the valid matrix lacked transition coverage or a nondegenerate 2D response"
            ),
            extra={"formal": summary},
        )
        return summary
    except Exception as exc:
        summary = {
            "schema_version": "q2_current_clamp_cc_b_formal_v1",
            "validity": "invalid",
            "matrix_complete": False,
            "completed_grid_cases": len(rows),
            "cases": rows,
            "artifacts": artifacts,
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "aggregate_cpu_s": time.process_time() - cpu_started,
            "calendar_wall_s": time.perf_counter() - wall_started,
            "disposition": "INVALID_CC_B_EXECUTION",
        }
        atomic_write_json(stage / "summary.json", summary)
        _write_terminal(
            contract,
            disposition="INVALID_CC_B_EXECUTION",
            validity="invalid",
            lifecycle_state="executed",
            claim_status="forbidden",
            completed_grid_cases=len(rows),
            matrix_complete=False,
            cc_b_vote=False,
            detail=str(exc),
            extra={"formal": summary},
        )
        return summary

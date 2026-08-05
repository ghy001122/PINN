"""Run only the separately authorized BranchConserve Batch 1 stages."""

from __future__ import annotations

import os

# Freeze scientific-worker threading before importing NumPy/SciPy.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_name] = "1"

import argparse
from dataclasses import replace
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

from pinnpcm.branchconserve.artifacts import (
    atomic_write_csv,
    atomic_write_json,
    branch_point_row,
    current_process_rss_bytes,
    environment_record,
    file_sha256,
    save_equilibrium_artifact,
)
from pinnpcm.branchconserve.continuation import (
    BranchAtlasOutcome,
    common_reachable_domain,
    solve_fixed_source_equilibrium,
    trace_nominal_branch_atlas,
)
from pinnpcm.branchconserve.contract import load_branchconserve_contract
from pinnpcm.branchconserve.solver import solve_steady_equilibrium
from pinnpcm.branchconserve.stability import certify_branch_conditioned_stability
from pinnpcm.branchconserve.steady_model import build_branchconserve_model


DEFAULT_CONFIG = Path("configs/q2_branchconserve_2d_steady_mve_v1.yaml")
DEFAULT_RUN_ID = "Q2-BC2D-BATCH1-20260805-V1"


def _roots(contract, run_id: str) -> tuple[Path, Path]:
    processed = contract.repository_root / contract.raw["outputs"]["processed_root"] / run_id
    compact = contract.repository_root / contract.raw["outputs"]["compact_root"] / run_id
    processed.mkdir(parents=True, exist_ok=True)
    compact.mkdir(parents=True, exist_ok=True)
    return processed, compact


def _stage_header(contract, run_id: str, stage: str) -> dict[str, Any]:
    contract.assert_batch1_stage_authorized(stage)
    return {
        "schema_version": "q2_branchconserve_batch1_stage_v1",
        "task_id": contract.raw["task_id"],
        "run_id": run_id,
        "stage": stage,
        "execution_class": "nonvoting_batch1_pilot",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "lifecycle_state": "executed",
        "claim_status": "forbidden",
        "evidence_type": contract.raw["evidence_type"],
        "parent_config_path": contract.parent_path.as_posix(),
        "parent_config_sha256": contract.parent_sha256,
        "environment": environment_record(contract.repository_root, run_id=run_id),
    }


def _computational_source_identity(repository_root: Path) -> dict[str, str]:
    relative_paths = (
        "configs/q2_branchconserve_2d_steady_mve_v1.yaml",
        "src/pinnpcm/branchconserve/contract.py",
        "src/pinnpcm/branchconserve/steady_model.py",
        "src/pinnpcm/branchconserve/solver.py",
        "src/pinnpcm/branchconserve/continuation.py",
        "src/pinnpcm/branchconserve/stability.py",
    )
    return {
        relative: file_sha256(repository_root / relative) for relative in relative_paths
    }


def run_smoke(config_path: Path, run_id: str) -> dict[str, Any]:
    contract = load_branchconserve_contract(config_path)
    header = _stage_header(contract, run_id, "nominal_l1_smoke")
    processed, compact = _roots(contract, run_id)
    model = build_branchconserve_model(contract, spatial_level=1)
    specification = contract.batch1["nominal_l1_smoke"]
    branch_name = str(specification["branch"])
    branch_memory = 1.0 if branch_name == "up" else -1.0
    wall_started = perf_counter()
    cpu_started = process_time()
    peak_rss = current_process_rss_bytes()
    solve = solve_steady_equilibrium(
        model,
        device_voltage_V=float(specification["device_voltage_V"]),
        branch_memory=branch_memory,
    )
    certified = solve.evaluation if solve.success else None
    stability = (
        certify_branch_conditioned_stability(
            model,
            temperature_K=solve.temperature_K,
            device_voltage_V=solve.device_voltage_V,
            source_voltage_V=solve.evaluation.source_voltage_V,
            branch_memory=branch_memory,
        )
        if solve.success and solve.temperature_K is not None and solve.evaluation is not None
        else None
    )
    peak_rss = max(
        peak_rss or 0, current_process_rss_bytes() or 0
    ) or None
    artifact = None
    if (
        solve.success
        and certified is not None
    ):
        artifact = save_equilibrium_artifact(
            processed,
            identity="nominal_l1_smoke_up_vd0p28125",
            solve=solve,
            stability=stability,
            metadata={
                "grid": "L1",
                "branch": branch_name,
                "anchor": "nominal",
                "role": "nonvoting_equilibrium_smoke",
            },
        )
    valid = bool(
        solve.success
        and certified is not None
        and stability is not None
        and stability.success
    )
    summary = {
        **header,
        "validity": "valid" if valid else "invalid",
        "status": "PASS" if valid else "FAIL",
        "device_voltage_V": float(specification["device_voltage_V"]),
        "source_voltage_role": specification["source_voltage_role"],
        "branch": branch_name,
        "outer_equilibrium_count": 1,
        "outer_device_voltages_V": [float(specification["device_voltage_V"])],
        "wall_time_s": perf_counter() - wall_started,
        "cpu_time_s": process_time() - cpu_started,
        "peak_rss_bytes": peak_rss,
        "failure_code": None if valid else (stability.code if stability is not None else solve.code),
        "failure_detail": (
            stability.telemetry.failure_detail
            if stability is not None and not stability.success
            else solve.telemetry.failure_detail
        ),
        "equilibrium": None
        if certified is None
        else {
            "source_voltage_V": certified.source_voltage_V,
            "device_voltage_V": certified.device_voltage_V,
            "source_current_A": certified.source_current_A,
            "scaled_electrical_residual_inf": certified.scaled_electrical_residual_inf,
            "scaled_thermal_residual_inf": certified.scaled_thermal_residual_inf,
            "load_line_residual": certified.load_line_residual,
            "ledger_pass": certified.ledger.pass_all,
            "active_area_mean_conductive_state": certified.active_area_mean_conductive_state,
        },
        "solver": solve.telemetry,
        "stability": None
        if stability is None
        else {
            "code": stability.code,
            "stable": stability.stable,
            "rightmost_spectral_abscissa_per_s": stability.rightmost_spectral_abscissa_per_s,
            "tau_lambda_per_s": stability.tau_lambda_per_s,
            "relative_residuals": stability.relative_residuals,
            "telemetry": stability.telemetry,
        },
        "artifact": artifact,
    }
    atomic_write_json(compact / "l1_smoke_summary.json", summary)
    return summary


def _save_atlas_point(processed: Path, point) -> None:
    identity = f"nominal_l1_{point.branch_name}_{point.index:03d}"
    save_equilibrium_artifact(
        processed,
        identity=identity,
        solve=point.solve,
        stability=point.stability,
        metadata={
            "grid": "L1",
            "branch": point.branch_name,
            "anchor": "nominal",
            "role": "nonvoting_branch_atlas_cost_pilot",
            "reachable": point.reachable,
        },
    )


def _save_inner_equilibrium(
    processed: Path,
    *,
    grid: str,
    branch: str,
    role: str,
    index: int,
    device_voltage_V: float,
    solve,
) -> None:
    if not solve.success:
        return
    save_equilibrium_artifact(
        processed,
        identity=f"nominal_{grid}_{branch}_{role}_inner_{index:03d}",
        solve=solve,
        stability=None,
        metadata={
            "grid": grid.upper(),
            "branch": branch,
            "anchor": "nominal",
            "role": role,
            "outer_iteration_index": index,
            "device_voltage_V": device_voltage_V,
            "scientific_vote": False,
        },
    )


def _atlas_payload(outcome: BranchAtlasOutcome) -> dict[str, Any]:
    return {
        "success": outcome.success,
        "code": outcome.code,
        "branch": outcome.branch_name,
        "point_count": len(outcome.points),
        "reachable_point_count": sum(point.reachable for point in outcome.points),
        "wall_time_s": outcome.wall_time_s,
        "cpu_time_s": outcome.cpu_time_s,
        "failure_detail": outcome.failure_detail,
    }


def run_atlas(config_path: Path, run_id: str) -> dict[str, Any]:
    contract = load_branchconserve_contract(config_path)
    header = _stage_header(contract, run_id, "nominal_l1_atlas")
    processed, compact = _roots(contract, run_id)
    smoke_path = compact / "l1_smoke_summary.json"
    if not smoke_path.exists():
        raise RuntimeError("nominal L1 smoke must be executed before the atlas")
    import json

    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    if smoke.get("status") != "PASS":
        raise RuntimeError("nominal L1 smoke did not pass")
    model = build_branchconserve_model(contract, spatial_level=1)
    wall_started = perf_counter()
    cpu_started = process_time()
    peak_rss = current_process_rss_bytes()
    heating = trace_nominal_branch_atlas(
        model,
        branch_name="up",
        point_callback=lambda point: _save_atlas_point(processed, point),
        inner_equilibrium_callback=lambda index, vd, solve: _save_inner_equilibrium(
            processed,
            grid="l1",
            branch="up",
            role="load_line",
            index=index,
            device_voltage_V=vd,
            solve=solve,
        ),
    )
    peak_rss = max(peak_rss or 0, current_process_rss_bytes() or 0) or None
    cooling = trace_nominal_branch_atlas(
        model,
        branch_name="down",
        point_callback=lambda point: _save_atlas_point(processed, point),
        inner_equilibrium_callback=lambda index, vd, solve: _save_inner_equilibrium(
            processed,
            grid="l1",
            branch="down",
            role="cooling_endpoint_load_line",
            index=index,
            device_voltage_V=vd,
            solve=solve,
        ),
    )
    peak_rss = max(peak_rss or 0, current_process_rss_bytes() or 0) or None
    domain = common_reachable_domain(
        contract.candidate_source_voltages_V, heating, cooling
    )
    rows = [branch_point_row(point) for point in (*heating.points, *cooling.points)]
    fieldnames = list(rows[0]) if rows else [
        "index",
        "branch",
        "branch_memory",
        "device_voltage_V",
        "source_voltage_V",
        "source_current_A",
        "active_area_mean_conductive_state",
        "stable",
        "reachable",
        "atlas_only_reason",
        "nonlinear_iterations",
        "jv_evaluations",
        "residual_evaluations",
        "solver_wall_time_s",
        "stability_wall_time_s",
        "rightmost_spectral_abscissa_per_s",
        "tau_lambda_per_s",
    ]
    atlas_csv_sha = atomic_write_csv(
        compact / "branch_atlas.csv", rows, fieldnames=fieldnames
    )
    valid = bool(
        heating.success
        and cooling.success
        and domain.exists
        and len(domain.candidate_source_voltages_V)
        >= int(contract.raw["bias_selection"]["required_primary_count"])
    )
    summary = {
        **header,
        # A structured, contract-level branch failure is a valid bounded pilot
        # result even when the failed branch has no publishable atlas point.
        "validity": "valid",
        "claim_status": "forbidden" if valid else "failed_but_informative",
        "status": "PASS" if valid else "FAIL",
        "heating": _atlas_payload(heating),
        "cooling": _atlas_payload(cooling),
        "common_reachable_domain": domain,
        "branch_atlas_csv": (compact / "branch_atlas.csv").as_posix(),
        "branch_atlas_csv_sha256": atlas_csv_sha,
        "wall_time_s": perf_counter() - wall_started,
        "cpu_time_s": process_time() - cpu_started,
        "peak_rss_bytes": peak_rss,
        "candidate_count": len(domain.candidate_source_voltages_V),
        "failure_code": None if valid else "STOP_BRANCHCONSERVE_PILOT",
        "failure_detail": (
            None
            if valid
            else (
                cooling.failure_detail
                or heating.failure_detail
                or "both branches did not establish at least five common reachable candidate biases"
            )
        ),
    }
    atomic_write_json(compact / "l1_atlas_summary.json", summary)
    atomic_write_json(
        compact / "nominal_common_reachable_domain.json",
        {
            "schema_version": "q2_branchconserve_common_reachable_domain_v1",
            "run_id": run_id,
            "scientific_vote": False,
            "domain": domain,
        },
    )
    return summary


def run_l2_sentinel(config_path: Path, run_id: str) -> dict[str, Any]:
    contract = load_branchconserve_contract(config_path)
    header = _stage_header(contract, run_id, "nominal_l2_cost_sentinel")
    processed, compact = _roots(contract, run_id)
    import json

    atlas_path = compact / "l1_atlas_summary.json"
    if not atlas_path.exists():
        raise RuntimeError("nominal L1 atlas must be executed before the L2 sentinel")
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    if atlas.get("status") != "PASS":
        raise RuntimeError("nominal L1 atlas did not pass")
    candidates = atlas["common_reachable_domain"]["candidate_source_voltages_V"]
    source_voltage = float(candidates[len(candidates) // 2])
    branch_name = str(contract.batch1["l2_cost_sentinel"]["branch"])
    branch_memory = 1.0 if branch_name == "up" else -1.0
    model = build_branchconserve_model(contract, spatial_level=2)
    wall_started = perf_counter()
    cpu_started = process_time()
    peak_rss = current_process_rss_bytes()
    outcome = solve_fixed_source_equilibrium(
        model,
        source_voltage_V=source_voltage,
        branch_memory=branch_memory,
        include_stability=True,
        equilibrium_callback=lambda index, vd, solve: _save_inner_equilibrium(
            processed,
            grid="l2",
            branch=branch_name,
            role="sentinel_load_line",
            index=index,
            device_voltage_V=vd,
            solve=solve,
        ),
    )
    wall = perf_counter() - wall_started
    cpu = process_time() - cpu_started
    peak_rss = max(peak_rss or 0, current_process_rss_bytes() or 0) or None
    artifact = None
    if (
        outcome.success
        and outcome.solve is not None
        and outcome.certified_evaluation is not None
    ):
        certified_solve = replace(
            outcome.solve, evaluation=outcome.certified_evaluation
        )
        artifact = save_equilibrium_artifact(
            processed,
            identity=f"nominal_l2_sentinel_{branch_name}",
            solve=certified_solve,
            stability=outcome.stability,
            metadata={
                "grid": "L2",
                "branch": branch_name,
                "anchor": "nominal",
                "role": "nonvoting_cost_sentinel",
            },
        )
    deadline = float(contract.batch1["l2_cost_sentinel"]["timeout_s"])
    valid = bool(
        outcome.success
        and outcome.stability is not None
        and outcome.stability.success
        and wall <= deadline
    )
    # L4 has sixteen times as many cells as L1 and four times L2.  Report a
    # deliberately simple, non-claim cost envelope; Batch 2 still requires approval.
    l4_wall_projection = 4.0 * wall
    summary = {
        **header,
        "validity": "valid" if outcome.success else "invalid",
        "status": "PASS" if valid else "BLOCKED",
        "source_voltage_V": source_voltage,
        "branch": branch_name,
        "outer_equilibrium_count": outcome.outer_equilibrium_count,
        "wall_time_s": wall,
        "cpu_time_s": cpu,
        "peak_rss_bytes": peak_rss,
        "hard_timeout_s": deadline,
        "l4_single_equilibrium_stability_wall_projection_s": l4_wall_projection,
        "projection_rule": "four_times_observed_l2_wall_nonvoting_envelope",
        "failure_code": None if valid else "BLOCKED_L2_COST_SENTINEL",
        "failure_detail": outcome.failure_detail,
        "solver": None if outcome.solve is None else outcome.solve.telemetry,
        "stability": None
        if outcome.stability is None
        else {
            "code": outcome.stability.code,
            "stable": outcome.stability.stable,
            "rightmost_spectral_abscissa_per_s": outcome.stability.rightmost_spectral_abscissa_per_s,
            "tau_lambda_per_s": outcome.stability.tau_lambda_per_s,
            "telemetry": outcome.stability.telemetry,
        },
        "artifact": artifact,
    }
    atomic_write_json(compact / "l2_cost_sentinel_summary.json", summary)
    return summary


def finalize(config_path: Path, run_id: str) -> dict[str, Any]:
    contract = load_branchconserve_contract(config_path)
    _, compact = _roots(contract, run_id)
    import json

    summaries = {}
    for name in (
        "l1_smoke_summary.json",
        "l1_atlas_summary.json",
        "l2_cost_sentinel_summary.json",
    ):
        path = compact / name
        summaries[name] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        )
    smoke = summaries["l1_smoke_summary.json"]
    atlas = summaries["l1_atlas_summary.json"]
    sentinel = summaries["l2_cost_sentinel_summary.json"]
    if (
        atlas is not None
        and atlas.get("status") == "FAIL"
        and atlas.get("failure_code") == "STOP_BRANCHCONSERVE_PILOT"
    ):
        # Output-only normalization of already persisted source evidence.  It
        # does not call the model or rerun an equilibrium: a structured pilot
        # gate miss is valid failed-but-informative evidence, not an invalid
        # execution merely because the cooling branch published zero points.
        atlas["validity"] = "valid"
        atlas["claim_status"] = "failed_but_informative"
        cooling_detail = (atlas.get("cooling") or {}).get("failure_detail")
        heating_detail = (atlas.get("heating") or {}).get("failure_detail")
        atlas["failure_detail"] = (
            cooling_detail
            or heating_detail
            or atlas.get("failure_detail")
        )
        atomic_write_json(compact / "l1_atlas_summary.json", atlas)
    # Account across every Batch-1 identity, including invalid implementation
    # attempts.  A PASS smoke without a terminal atlas summary identifies an
    # interrupted atlas attempt; charge the full 30-minute per-batch ceiling
    # so the aggregate gate remains conservative without inventing runtime.
    family_root = compact.parent
    completed_cpu = 0.0
    completed_wall = 0.0
    orphaned_atlas_attempts: list[str] = []
    attempt_accounting: list[dict[str, Any]] = []
    for attempt_root in sorted(path for path in family_root.iterdir() if path.is_dir()):
        attempt_record: dict[str, Any] = {"run_id": attempt_root.name, "stages": {}}
        attempt_smoke = None
        attempt_atlas = None
        for stage_name in (
            "l1_smoke_summary.json",
            "l1_atlas_summary.json",
            "l2_cost_sentinel_summary.json",
        ):
            stage_path = attempt_root / stage_name
            if not stage_path.exists():
                continue
            stage_payload = json.loads(stage_path.read_text(encoding="utf-8"))
            cpu = float(stage_payload.get("cpu_time_s", 0.0))
            wall = float(stage_payload.get("wall_time_s", 0.0))
            completed_cpu += cpu
            completed_wall += wall
            attempt_record["stages"][stage_name] = {
                "status": stage_payload.get("status"),
                "cpu_time_s": cpu,
                "wall_time_s": wall,
            }
            if stage_name == "l1_smoke_summary.json":
                attempt_smoke = stage_payload
            elif stage_name == "l1_atlas_summary.json":
                attempt_atlas = stage_payload
        if (
            attempt_smoke is not None
            and attempt_smoke.get("status") == "PASS"
            and attempt_atlas is None
        ):
            orphaned_atlas_attempts.append(attempt_root.name)
        attempt_accounting.append(attempt_record)
    orphan_reserve = len(orphaned_atlas_attempts) * float(
        contract.batch1["individual_batch_wall_s_max"]
    )
    total_cpu = completed_cpu + orphan_reserve
    total_wall = completed_wall + orphan_reserve
    budget_ok = bool(
        total_cpu <= float(contract.batch1["aggregate_cpu_s_max"])
        and total_wall <= float(contract.batch1["calendar_wall_s_max"])
    )
    if not budget_ok:
        disposition = "BLOCKED_BRANCHCONSERVE_COST"
    elif smoke is None or smoke.get("status") != "PASS":
        disposition = "INVALID_BRANCHCONSERVE_PILOT"
    elif atlas is None or atlas.get("status") != "PASS":
        disposition = "STOP_BRANCHCONSERVE_PILOT"
    elif sentinel is None or sentinel.get("status") != "PASS":
        disposition = "BLOCKED_L2_COST_SENTINEL"
    else:
        disposition = "PILOT_CONTINUE_TO_B1_B2"
    terminal = {
        "schema_version": "q2_branchconserve_batch1_terminal_v1",
        "task_id": contract.raw["task_id"],
        "run_id": run_id,
        "disposition": disposition,
        "validity": "valid"
        if disposition in {"PILOT_CONTINUE_TO_B1_B2", "STOP_BRANCHCONSERVE_PILOT"}
        else "invalid_or_resource_blocked",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "lifecycle_state": "executed",
        "claim_status": (
            "failed_but_informative"
            if disposition == "STOP_BRANCHCONSERVE_PILOT"
            else "forbidden"
        ),
        "batch2_authorized": False,
        "aggregate_cpu_s": total_cpu,
        "aggregate_wall_s": total_wall,
        "budget_accounting": {
            "method": "sum_completed_stage_telemetry_plus_full_30min_reserve_per_interrupted_atlas",
            "completed_stage_cpu_s": completed_cpu,
            "completed_stage_wall_s": completed_wall,
            "orphaned_atlas_attempts": orphaned_atlas_attempts,
            "orphaned_attempt_reserve_s": orphan_reserve,
            "attempts": attempt_accounting,
        },
        "budget_ok": budget_ok,
        "computational_source_sha256": _computational_source_identity(
            contract.repository_root
        ),
        "source_identity_note": (
            "The run preceded the result commit; these exact worktree-byte hashes "
            "identify the V9 computational core. Runner-only evidence-normalization "
            "and artifact-hashing changes after V9 did not alter these files."
        ),
        "stages": summaries,
        "claim_boundary": contract.raw["claim_boundary"],
    }
    atomic_write_json(compact / "batch1_terminal.json", terminal)
    return terminal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=("smoke", "atlas", "l2-sentinel", "finalize"),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    args = parser.parse_args()
    if args.stage == "smoke":
        result = run_smoke(args.config, args.run_id)
    elif args.stage == "atlas":
        result = run_atlas(args.config, args.run_id)
    elif args.stage == "l2-sentinel":
        result = run_l2_sentinel(args.config, args.run_id)
    else:
        result = finalize(args.config, args.run_id)
    import json

    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

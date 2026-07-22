"""Run the preregistered terminal M43 thermal-component closure.

M43 is a manufactured homogeneous-half-space audit.  It performs no Qiu
device forward, fit, inverse solve, PINN training, or sealed-data access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np
import yaml

from pinnpcm.physics.m43_thermal_spreading_reference import (
    spreading_resistance_K_W,
    steady_dimensionless_theta,
    transient_dimensionless_theta,
    transient_impedance_K_W,
)
from pinnpcm.solvers.m43_finite_width_thermal import (
    build_quarter_grid,
    run_steady_case,
    run_transient_case,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "research/m43-finite-width-thermal-closure"
PREREG_SUBJECT = "Preregister M43 finite-width thermal closure"
PREREG_FILES = (
    "configs/m43_finite_width_thermal_spreading.yaml",
    "docs/research_strategy/m43_finite_width_thermal_spreading_preregistration.md",
    "docs/physics/m43_thermal_spreading_source_contract.md",
)
ANALYTIC_GATE_NAMES = (
    "eq21_rho1_relative_error",
    "eq21_rho5_relative_error",
    "green_early_limit_error",
    "green_long_limit_error",
    "green_quadrature_refinement_change",
)
DYNAMIC_GATE_NAMES = (
    "steady_rho1_reference_error",
    "steady_rho5_reference_error",
    "rho5_mesh_pair_change",
    "rho5_domain_pair_change",
    "steady_normalized_power_imbalance",
    "transient_3d_green_normalized_max_error",
    "transient_time_pair_change",
    "transient_normalized_sensible_energy_imbalance",
    "finite_width_bias_mesh_pair_absolute_change",
    "finite_width_bias_domain_pair_absolute_change",
    "source_area_integral_error",
    "source_power_integral_error",
    "near_zero_outflow_normalized_change",
    "finite_nan_clip_source_smearing_unit_error",
)
BUDGET_GATE_NAMES = ("wall_clock_budget", "cpu_time_budget")
EXPECTED_GATE_NAMES = frozenset(ANALYTIC_GATE_NAMES + DYNAMIC_GATE_NAMES + BUDGET_GATE_NAMES)
GATE_THRESHOLD_KEYS = {
    "eq21_rho1_relative_error": "eq21_rho1_relative_error_max",
    "eq21_rho5_relative_error": "eq21_rho5_relative_error_max",
    "green_early_limit_error": "green_early_limit_error_max",
    "green_long_limit_error": "green_long_limit_error_max",
    "green_quadrature_refinement_change": "green_quadrature_refinement_change_max",
    "steady_rho1_reference_error": "steady_rho1_reference_error_max",
    "steady_rho5_reference_error": "steady_rho5_reference_error_max",
    "rho5_mesh_pair_change": "rho5_mesh_pair_change_max",
    "rho5_domain_pair_change": "rho5_domain_pair_change_max",
    "steady_normalized_power_imbalance": "steady_normalized_power_imbalance_max",
    "transient_3d_green_normalized_max_error": "transient_3d_green_normalized_max_error_max",
    "transient_time_pair_change": "transient_time_pair_change_max",
    "transient_normalized_sensible_energy_imbalance": "transient_normalized_sensible_energy_imbalance_max",
    "finite_width_bias_mesh_pair_absolute_change": "finite_width_bias_mesh_pair_absolute_change_max",
    "finite_width_bias_domain_pair_absolute_change": "finite_width_bias_domain_pair_absolute_change_max",
    "source_area_integral_error": "source_area_integral_error_max",
    "source_power_integral_error": "source_power_integral_error_max",
    "near_zero_outflow_normalized_change": "near_zero_outflow_normalized_change_max",
    "finite_nan_clip_source_smearing_unit_error": "finite_nan_clip_source_smearing_unit_error",
}
EXPECTED_OUTPUT_PATHS = {
    "summary": "outputs/tables/m43_finite_width_thermal_spreading_summary.json",
    "cases": "outputs/tables/m43_finite_width_thermal_spreading_cases.csv",
    "transient_reference": "outputs/tables/m43_transient_green_reference.csv",
    "figure": "outputs/figures/m43/m43_thermal_spreading_closure.png",
    "report": "docs/codex_reports/m43_finite_width_thermal_spreading_closure.md",
    "execution_receipt": "outputs/tables/m43_execution_receipt.json",
}
EXPECTED_CASE_IDS = (
    "square_steady_M1D3", "square_steady_M2D3", "square_steady_M3D3",
    "square_steady_M3D1", "square_steady_M3D2",
    "rho5_steady_M2D3", "rho5_steady_M3D3", "rho5_steady_M3D2",
    "rho5_transient_M2D3_base", "rho5_transient_M3D3_base",
    "rho5_transient_M3D2_base", "rho5_transient_M3D3_fine",
    "rho5_xz_M2D3_base", "rho5_xz_M3D3_base", "rho5_xz_M3D2_base",
)
EXPECTED_CASE_CONTRACTS = (
    ("square_steady_M1D3", "rho1", "steady", "M1", "D3", None),
    ("square_steady_M2D3", "rho1", "steady", "M2", "D3", None),
    ("square_steady_M3D3", "rho1", "steady", "M3", "D3", None),
    ("square_steady_M3D1", "rho1", "steady", "M3", "D1", None),
    ("square_steady_M3D2", "rho1", "steady", "M3", "D2", None),
    ("rho5_steady_M2D3", "rho5", "steady", "M2", "D3", None),
    ("rho5_steady_M3D3", "rho5", "steady", "M3", "D3", None),
    ("rho5_steady_M3D2", "rho5", "steady", "M3", "D2", None),
    ("rho5_transient_M2D3_base", "rho5", "transient_3d", "M2", "D3", "base"),
    ("rho5_transient_M3D3_base", "rho5", "transient_3d", "M3", "D3", "base"),
    ("rho5_transient_M3D2_base", "rho5", "transient_3d", "M3", "D2", "base"),
    ("rho5_transient_M3D3_fine", "rho5", "transient_3d", "M3", "D3", "fine"),
    ("rho5_xz_M2D3_base", "rho5", "transient_xz", "M2", "D3", "base"),
    ("rho5_xz_M3D3_base", "rho5", "transient_xz", "M3", "D3", "base"),
    ("rho5_xz_M3D2_base", "rho5", "transient_xz", "M3", "D2", "base"),
)
EXPECTED_GATE_CONFIG = {
    "eq21_rho1_relative_error_max": 1.0e-4,
    "eq21_rho5_relative_error_max": 1.0e-4,
    "steady_rho1_reference_error_max": 0.02,
    "steady_rho5_reference_error_max": 0.02,
    "rho5_mesh_pair_change_max": 0.02,
    "rho5_domain_pair_change_max": 0.02,
    "steady_normalized_power_imbalance_max": 1.0e-6,
    "green_early_limit_error_max": 0.01,
    "green_long_limit_error_max": 0.01,
    "green_quadrature_refinement_change_max": 1.0e-4,
    "transient_3d_green_normalized_max_error_max": 0.02,
    "transient_time_pair_change_max": 0.02,
    "transient_normalized_sensible_energy_imbalance_max": 1.0e-4,
    "finite_width_bias_mesh_pair_absolute_change_max": 0.02,
    "finite_width_bias_domain_pair_absolute_change_max": 0.02,
    "source_area_integral_error_max": 1.0e-10,
    "source_power_integral_error_max": 1.0e-10,
    "near_zero_outflow_normalized_change_max": 0.02,
    "finite_nan_clip_source_smearing_unit_error": False,
}


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _resolve(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(_jsonable(row.get(key)), separators=(",", ":"))
                    if isinstance(row.get(key), (dict, list, tuple, np.ndarray))
                    else _jsonable(row.get(key))
                    for key in fields
                }
            )


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _jsonable(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()



def _git_blob_sha256(commit: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, check=True
    )
    return hashlib.sha256(completed.stdout).hexdigest().upper()


def _find_and_verify_preregistration(config_path: Path) -> tuple[str, dict[str, str]]:
    head = _git("rev-parse", "HEAD")
    subject = _git("show", "-s", "--format=%s", head)
    if subject != PREREG_SUBJECT:
        raise RuntimeError("runtime HEAD is not the locked M43 preregistration commit")
    changed = set(
        line for line in _git("diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
        if line
    )
    if changed != set(PREREG_FILES):
        raise RuntimeError(f"preregistration commit path set changed: {sorted(changed)}")
    identities: dict[str, str] = {}
    for relative in PREREG_FILES:
        current = _sha256(relative)
        committed = _git_blob_sha256(head, relative)
        if current != committed:
            raise RuntimeError(f"dirty preregistration byte identity: {relative}")
        identities[relative] = current
    if config_path.resolve() != _resolve(PREREG_FILES[0]).resolve():
        raise RuntimeError("formal M43 must use the locked canonical config path")
    return head, identities


def _validate_config_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    geometry = config["geometry"]
    material = config["material"]
    time_cfg = config["time"]
    budget = config["budget"]
    matrix = list(config["forward_matrix"])
    area = float(geometry["source_area_m2"])
    full_x = float(geometry["source_full_x_m"])
    full_y = float(geometry["source_full_y_m"])
    half_a = float(geometry["source_half_long_a_m"])
    half_b = float(geometry["source_half_short_b_m"])
    rho_m_cp = float(material["mass_density_kg_m3"]) * float(material["specific_heat_J_kgK"])
    alpha = float(material["thermal_conductivity_W_mK"]) / float(material["volumetric_heat_capacity_J_m3K"])
    tmax = float(time_cfg["maximum_time_s"])
    ell = math.sqrt(alpha * tmax)
    Fo = np.asarray(time_cfg["fvm_comparison_Fo_A"], dtype=float)
    times = Fo * area / alpha
    expected_times = np.asarray(time_cfg["fvm_comparison_times_s"], dtype=float)
    normalized_cases = tuple(
        (
            str(case.get("case_id")), str(case.get("geometry")), str(case.get("mode")),
            str(case.get("mesh")), str(case.get("domain")), case.get("time"),
        )
        for case in matrix
    )
    boundary = config["boundary_contract"]
    checks = {
        "task_id": config.get("task_id") == "Q2_M43_FINITE_WIDTH_THERMAL_SPREADING_CLOSURE",
        "schema_version": config.get("schema_version") == "m43_finite_width_thermal_spreading_v1",
        "base_commit": config.get("base_commit") == "0dc103f391d1206fe02c100987ecab68ed1d741d",
        "required_ancestor": config.get("required_ancestor") == "3474499636165f7477ceceff3cf85da8a5adba08",
        "area_from_lengths": math.isclose(area, full_x * full_y, rel_tol=0.0, abs_tol=1.0e-28),
        "area_from_half_lengths": math.isclose(area, 4.0 * half_a * half_b, rel_tol=0.0, abs_tol=1.0e-28),
        "aspect_ratio": math.isclose(float(geometry["source_aspect_ratio_rho"]), half_a / half_b, rel_tol=0.0, abs_tol=1.0e-14),
        "quarter_area": math.isclose(float(geometry["quarter_source_area_m2"]), area / 4.0, rel_tol=0.0, abs_tol=1.0e-28),
        "quarter_power": math.isclose(float(geometry["quarter_power_W"]), float(geometry["full_power_W"]) / 4.0, rel_tol=0.0, abs_tol=1.0e-15),
        "xz_half_power": math.isclose(float(geometry["xz_half_domain_power_W"]), float(geometry["full_power_W"]) / 2.0, rel_tol=0.0, abs_tol=1.0e-15),
        "rho_cp_factorization": math.isclose(rho_m_cp, float(material["volumetric_heat_capacity_J_m3K"]), rel_tol=1.0e-14),
        "diffusivity": math.isclose(alpha, float(material["thermal_diffusivity_m2_s"]), rel_tol=1.0e-14),
        "diffusion_length": math.isclose(ell, float(time_cfg["maximum_diffusion_length_m"]), rel_tol=1.0e-12),
        "fourier_time_mapping": Fo.shape == expected_times.shape and bool(np.allclose(times, expected_times, rtol=1.0e-12, atol=0.0)),
        "fourier_order": Fo.size == 9 and bool(np.all(np.diff(Fo) > 0.0)),
        "case_matrix": normalized_cases == EXPECTED_CASE_CONTRACTS,
        "gate_values": dict(config["gates"]) == EXPECTED_GATE_CONFIG,
        "boundary_top_source": boundary.get("top_source") == "explicit_Neumann_heat_flux",
        "boundary_top_exterior": boundary.get("top_outside_source") == "adiabatic",
        "boundary_symmetry": boundary.get("symmetry_x0_y0") == "zero_flux",
        "boundary_far": boundary.get("far_x_y_bottom") == "fixed_T0",
        "boundary_surface_qoi": boundary.get("source_surface_temperature") == "T_first_cell_plus_qflux_dz_over_2k",
        "boundary_no_smearing": boundary.get("source_smearing_forbidden") is True,
        "case_count": len(matrix) == 15 == int(budget["preregistered_pde_forwards"]),
        "unique_case_ids": len({str(case["case_id"]) for case in matrix}) == len(matrix),
        "forward_ceiling": int(budget["maximum_unique_pde_forwards"]) == 16,
        "wall_budget": float(budget["maximum_wall_clock_s"]) == 28800.0,
        "cpu_budget": float(budget["maximum_cpu_time_s"]) == 28800.0,
        "single_attempt": int(budget["maximum_confirmatory_attempts"]) == 1,
        "decision_two_state": config["decision"] == {
            "all_mandatory_gates_pass": "M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY",
            "any_mandatory_gate_fails": "M43_STOP_C_FREEZE_1D",
            "threshold_change_after_results": "forbidden",
            "second_solver_after_failure": "forbidden",
            "m43_repair_round": "forbidden",
        },
        "output_paths": all(
            config["outputs"].get(key) == value
            for key, value in EXPECTED_OUTPUT_PATHS.items()
        ),
    }
    for mesh, nxy, nz in (("M1", 4, 4), ("M2", 8, 8), ("M3", 16, 16)):
        profile = config["grid"]["mesh_profiles"][mesh]
        checks[f"square_isotropic_{mesh}"] = list(profile["square_quarter_source_cells_xy"]) == [nxy, nxy] and int(profile["square_source_depth_cells"]) == nz
    for mesh, nx, ny, nz in (("M1", 2, 10, 2), ("M2", 4, 20, 4), ("M3", 8, 40, 8)):
        profile = config["grid"]["mesh_profiles"][mesh]
        checks[f"rho5_isotropic_{mesh}"] = list(profile["rho5_quarter_source_cells_xy"]) == [nx, ny] and int(profile["rho5_source_depth_cells"]) == nz
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "derived": {
            "source_area_m2": area,
            "rho_m_cp_J_m3K": rho_m_cp,
            "thermal_diffusivity_m2_s": alpha,
            "maximum_diffusion_length_m": ell,
            "comparison_times_s": times.tolist(),
        },
    }


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(path)


def _create_execution_receipt(
    path: Path,
    summary_path: Path,
    prereg: str,
    config_hash: str,
    preregistration_identities: Mapping[str, str],
    protected_before: Mapping[str, Mapping[str, Any]],
    *,
    wall_started: float,
    cpu_started: float,
) -> dict[str, Any]:
    if path.exists() or summary_path.exists():
        raise RuntimeError("M43 formal execution already has a receipt or summary; rerun forbidden")
    payload: dict[str, Any] = {
        "schema_version": "m43_one_shot_execution_receipt_v1",
        "status": "started",
        "preregistration_commit": prereg,
        "preregistration_file_sha256": dict(preregistration_identities),
        "config_sha256": config_hash,
        "formal_runner_invocations": 1,
        "forward_invocations_attempted": 0,
        "forward_invocations_completed": 0,
        "confirmatory_stage_entered": False,
        "confirmatory_completed": False,
        "cases": [],
        "protected_evidence_before": _jsonable(protected_before),
        "wall_started_perf_counter_s": float(wall_started),
        "cpu_started_process_time_s": float(cpu_started),
        "terminal_rerun_forbidden": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def _update_execution_receipt(path: Path, receipt: dict[str, Any]) -> None:
    _atomic_write_json(path, receipt)


def _fail_closed_gates(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    gates_cfg = config["gates"]
    records: dict[str, dict[str, Any]] = {}
    for name in ANALYTIC_GATE_NAMES + DYNAMIC_GATE_NAMES:
        relation = "equal" if name == "finite_nan_clip_source_smearing_unit_error" else "max"
        records[name] = _gate(None, gates_cfg[GATE_THRESHOLD_KEYS[name]], relation=relation)
    records["wall_clock_budget"] = _gate(
        None, float(config["budget"]["maximum_wall_clock_s"])
    )
    records["cpu_time_budget"] = _gate(
        None, float(config["budget"]["maximum_cpu_time_s"])
    )
    if set(records) != EXPECTED_GATE_NAMES:
        raise RuntimeError("terminal M43 summary does not cover all 21 registered gates")
    return records


def _atomic_write_failure_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("case_id", "canonical_case_sha256", "status", "cell_count"),
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _safe_git_value(*args: str) -> str | None:
    try:
        return _git(*args)
    except Exception:
        return None


def _terminalize_failed_formal_run(
    config_path: Path,
    failure: Exception,
) -> dict[str, Any] | None:
    """Persist terminal STOP-C evidence only after the one-shot receipt exists."""

    try:
        config = dict(yaml.safe_load(config_path.read_text(encoding="utf-8")))
        outputs = config["outputs"]
        receipt_path = _resolve(outputs["execution_receipt"])
        summary_path = _resolve(outputs["summary"])
        cases_path = _resolve(outputs["cases"])
    except Exception:
        return None
    if not receipt_path.is_file():
        return None

    try:
        receipt = dict(json.loads(receipt_path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise RuntimeError("M43 receipt exists but is unreadable; manual quarantine required") from exc

    # A later CLI invocation must not rewrite the original terminal evidence.
    if summary_path.is_file():
        try:
            existing = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("M43 terminal summary exists but is unreadable") from exc
        if receipt.get("terminal_rerun_forbidden") is not True:
            raise RuntimeError("M43 existing receipt does not forbid rerun")
        return dict(existing)

    if receipt.get("terminal_rerun_forbidden") is not True:
        raise RuntimeError("M43 receipt does not enforce terminal rerun prohibition")
    failure_record = receipt.get("failure")
    if not isinstance(failure_record, Mapping):
        failure_record = {
            "stage": "formal_runner",
            "type": type(failure).__name__,
            "message": str(failure),
        }
    receipt["status"] = "terminal_failed"
    receipt["failure"] = dict(failure_record)
    receipt["confirmatory_stage_entered"] = bool(
        receipt.get("confirmatory_stage_entered", False)
    )
    receipt["confirmatory_completed"] = False
    _update_execution_receipt(receipt_path, receipt)

    completed_cases = [
        {
            "case_id": str(record["case_id"]),
            "canonical_case_sha256": str(record["canonical_case_sha256"]),
            "status": "completed",
            "cell_count": int(record.get("cell_count", 0)),
        }
        for record in receipt.get("cases", [])
        if record.get("status") == "completed"
    ]
    _atomic_write_failure_cases(cases_path, completed_cases)

    protected_before = receipt.get("protected_evidence_before", {})
    protected_after: dict[str, dict[str, Any]] = {}
    protected_baseline: dict[str, Any] = {
        "verified": False,
        "record_count": 0,
        "failures": [{"reason": "terminal verification unavailable"}],
    }
    hashes_unchanged = False
    mtimes_unchanged = False
    try:
        protected = _protected_paths()
        protected_baseline = _verify_protected_baseline(protected)
        protected_after = _snapshot(protected)
        same_keys = bool(protected_before) and set(protected_before) == set(protected_after)
        hashes_unchanged = same_keys and all(
            protected_before[key]["sha256"] == protected_after[key]["sha256"]
            for key in protected_before
        )
        mtimes_unchanged = same_keys and all(
            int(protected_before[key]["mtime_ns"]) == int(protected_after[key]["mtime_ns"])
            for key in protected_before
        )
    except Exception as exc:
        protected_baseline = {
            "verified": False,
            "record_count": 0,
            "failures": [{"type": type(exc).__name__, "message": str(exc)}],
        }

    gates = _fail_closed_gates(config)
    wall_started = float(receipt.get("wall_started_perf_counter_s", time.perf_counter()))
    cpu_started = float(receipt.get("cpu_started_process_time_s", time.process_time()))
    wall_time = max(0.0, time.perf_counter() - wall_started)
    cpu_time = max(0.0, time.process_time() - cpu_started)
    completed_hashes = sorted(
        str(record["canonical_case_sha256"]) for record in completed_cases
    )
    maximum_cells = max((int(record["cell_count"]) for record in completed_cases), default=0)
    summary: dict[str, Any] = {
        "schema_version": config["schema_version"],
        "task_id": config["task_id"],
        "evidence_type": config["evidence_boundary"]["evidence_type"],
        "status": "failed_but_informative",
        "decision": "M43_STOP_C_FREEZE_1D",
        "terminal_failure": dict(failure_record),
        "base_commit": config["base_commit"],
        "preregistration_commit": receipt.get("preregistration_commit"),
        "runtime_head": _safe_git_value("rev-parse", "HEAD"),
        "runtime_branch": _safe_git_value("branch", "--show-current"),
        "result_commit": None,
        "config_sha256": _sha256(config_path),
        "preregistration_file_sha256": receipt.get("preregistration_file_sha256", {}),
        "config_contract": _validate_config_contract(config),
        "protected_baseline_identity": protected_baseline,
        "runtime_code_sha256": {
            "runner": _sha256("scripts/run_m43_finite_width_thermal_spreading.py"),
            "reference": _sha256("src/pinnpcm/physics/m43_thermal_spreading_reference.py"),
            "solver": _sha256("src/pinnpcm/solvers/m43_finite_width_thermal.py"),
        },
        "reference": {},
        "gates": gates,
        "gate_pass_count": 0,
        "gate_total_count": len(gates),
        "failed_gates": list(ANALYTIC_GATE_NAMES + DYNAMIC_GATE_NAMES + BUDGET_GATE_NAMES),
        "forward_accounting": {
            "unique_thermal_pde_forwards": len(completed_cases),
            "attempted_thermal_pde_forwards": int(receipt.get("forward_invocations_attempted", 0)),
            "preregistered_pde_forwards": int(config["budget"]["preregistered_pde_forwards"]),
            "maximum_unique_pde_forwards": int(config["budget"]["maximum_unique_pde_forwards"]),
            "canonical_case_sha256": completed_hashes,
            "maximum_cell_count": maximum_cells,
            "wall_clock_s": wall_time,
            "cpu_time_s": cpu_time,
            "maximum_wall_clock_s": float(config["budget"]["maximum_wall_clock_s"]),
            "formal_runner_invocations": 1,
            "confirmatory_stage_entered": bool(receipt.get("confirmatory_stage_entered", False)),
            "confirmatory_completed": False,
            "formal_confirmatory_attempts": 1 if receipt.get("confirmatory_stage_entered") else 0,
        },
        "prohibited_run_accounting": {
            "scientific_device_forwards": 0,
            "qiu_device_forwards": 0,
            "electrical_or_circuit_forwards": 0,
            "curve_fit_runs": 0,
            "inverse_runs": 0,
            "pinn_training_runs": 0,
            "gpu_runs": 0,
            "sealed_13V_accessed": False,
        },
        "upstream_blockers": {
            "m42_source_local_resistance_error": config["evidence_boundary"]["upstream_source_local_resistance_error"],
            "latent_heat": config["evidence_boundary"]["upstream_latent_heat_status"],
            "resolved_by_m43": False,
        },
        "protected_evidence_unchanged": hashes_unchanged,
        "protected_evidence_mtime_unchanged": mtimes_unchanged,
        "protected_evidence": protected_after,
        "allowed_claims": [
            "M43 terminated fail-closed after a formal runtime failure; no positive thermal-closure claim is allowed."
        ],
        "forbidden_claims": [
            "M43 thermal component closure",
            "Qiu coupled dynamic ground truth",
            "VO2/Ti/Au/Al2O3 multilayer validation",
            "pure x-z quantitative model",
            "gamma_sub or gamma_eff validation",
            "phase-change total enthalpy",
            "inverse identification or PINN success",
            "external or experimental validation",
        ],
    }
    summary["artifact_sha256"] = {
        "cases": _sha256(cases_path),
        "execution_receipt": _sha256(receipt_path),
    }
    _atomic_write_json(summary_path, summary)
    return summary


def _protected_manifest_expectations() -> dict[str, str]:
    manifest_path = _resolve("outputs/tables/submission_protected_evidence_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = "0dc103f391d1206fe02c100987ecab68ed1d741d"
    expected: dict[str, str] = {}
    for record in manifest["records"]:
        relative = str(record["path"])
        # The submission manifest predates legitimate portability repairs to
        # tracked tests.  For tracked bytes the M42 result commit is the
        # current authoritative baseline; ignored local evidence keeps the
        # manifest's recorded raw-byte identity.
        if bool(record.get("tracked")):
            current_blob_oid = _git("rev-parse", f"{base}:{relative}")
            if current_blob_oid == str(record.get("git_blob_oid")):
                expected[relative] = str(record["sha256"]).upper()
            else:
                expected[relative] = _git_blob_sha256(base, relative)
        else:
            expected[relative] = str(record["sha256"]).upper()
    m42 = json.loads(_resolve("outputs/tables/m42_qiu_2d_preflight_summary.json").read_text(encoding="utf-8"))
    for relative, digest in m42["protected_evidence_sha256"].items():
        previous = expected.get(relative)
        if previous is not None and previous != str(digest).upper():
            raise RuntimeError(f"protected M42 baseline disagrees for {relative}")
        expected[relative] = str(digest).upper()
    return expected


def _verify_protected_baseline(paths: list[Path]) -> dict[str, Any]:
    expected = _protected_manifest_expectations()
    failures: list[dict[str, str]] = []
    for relative, digest in expected.items():
        path = _resolve(relative)
        actual = _sha256(path) if path.is_file() else "MISSING"
        if actual != digest:
            failures.append({"path": relative, "expected": digest, "actual": actual})
    if failures:
        raise RuntimeError(f"protected evidence baseline identity failed: {failures[:3]}")
    return {"verified": True, "record_count": len(expected), "failures": failures}


def _case_contract_error(
    config: Mapping[str, Any], case: Mapping[str, Any], result: Mapping[str, Any], times_s: np.ndarray
) -> bool:
    grid = result["grid"]
    source = result["source"]
    expected_mode = "transient_xz" if case["mode"] == "transient_xz" else case["mode"]
    expected_power = float(config["geometry"]["xz_half_domain_power_W" if case["mode"] == "transient_xz" else "quarter_power_W"])
    checks = [
        result["mode"] == expected_mode,
        grid["geometry"] == case["geometry"],
        grid["mesh"] == case["mesh"],
        grid["domain"] == case["domain"],
        grid["mode"] == ("xz" if case["mode"] == "transient_xz" else "3d"),
        source["surface_reconstruction"] == "Tcell+qflux*dz/(2k)",
        math.isclose(float(source["full_source_area_m2"]), float(config["geometry"]["source_area_m2"]), rel_tol=1.0e-13),
        math.isclose(float(source["expected_model_power_W"]), expected_power, rel_tol=0.0, abs_tol=1.0e-15),
        int(result["clip_count"]) == 0,
        bool(result["finite"]),
        not bool(source["source_smearing"]),
        bool(source["source_support_exact"]),
        bool(source["source_only_top_face"]),
        int(source["unregistered_extrapolation_count"]) == 0,
    ]
    if case["mode"] != "steady":
        checks.append(np.array_equal(np.asarray(result["metrics"]["time_s"], dtype=float), times_s))
    return not all(checks)


def _protected_paths() -> list[Path]:
    fixed = {
        "configs/gt_v1_acceptance_triangle.yaml",
        "configs/gt_v1_acceptance_ltp_ltd.yaml",
        "docs/gt_v1_acceptance_report.md",
        "data/processed/gt_v1_acceptance/manifest.json",
        "configs/m42_qiu_2d_preflight.yaml",
        "docs/research_strategy/m42_reference_and_2d_preregistration.md",
        "docs/codex_reports/m42_qiu_2d_physics_foundation_preflight.md",
        "outputs/tables/m42_qiu_2d_preflight_summary.json",
        "outputs/tables/m42_qiu_2d_preflight_cases.csv",
        "outputs/figures/m42/qiu_scale_domain_mesh_preflight.png",
        "outputs/tables/gamma_sub_evidence_lock_summary.json",
        "docs/paper/gamma_sub_evidence_lock.md",
        "outputs/tables/main_submission_figure_manifest.json",
        "outputs/tables/submission_protected_evidence_manifest.json",
    }
    protected_manifest = json.loads(
        _resolve("outputs/tables/submission_protected_evidence_manifest.json").read_text(encoding="utf-8")
    )
    fixed.update(str(record["path"]) for record in protected_manifest["records"])
    for directory, patterns in (
        ("outputs/tables", ("m40_*", "m40r_*", "e1f_*", "e1fr_*")),
        ("docs/codex_reports", ("m40*", "e1f*", "e1fr*")),
    ):
        folder = _resolve(directory)
        for pattern in patterns:
            fixed.update(path.relative_to(ROOT).as_posix() for path in folder.glob(pattern))
    fixed.update(
        path.relative_to(ROOT).as_posix()
        for path in _resolve("data/processed/gt_v1_acceptance").glob("**/*")
        if path.is_file()
    )
    manifest_path = _resolve("outputs/tables/main_submission_figure_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for figure in manifest.get("figures", []):
        fixed.add(str(figure["path"]))
        fixed.update(str(item["path"]) for item in figure.get("source_data", []))
    paths = [_resolve(item) for item in sorted(fixed)]
    missing = [path.relative_to(ROOT).as_posix() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"protected evidence is missing: {missing}")
    return paths


def _snapshot(paths: list[Path]) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(ROOT).as_posix(): {
            "sha256": _sha256(path),
            "mtime_ns": path.stat().st_mtime_ns,
            "bytes": path.stat().st_size,
        }
        for path in paths
    }


def _gate(
    value: float | bool | None,
    threshold: float | bool,
    *,
    relation: str = "max",
) -> dict[str, Any]:
    finite = value is not None and (
        isinstance(value, (bool, np.bool_)) or math.isfinite(float(value))
    )
    if not finite:
        passed = False
    elif relation == "max":
        passed = float(value) <= float(threshold)
    elif relation == "min":
        passed = float(value) >= float(threshold)
    elif relation == "equal":
        passed = bool(value) is bool(threshold)
    else:
        raise ValueError(f"unsupported gate relation: {relation}")
    return {
        "value": _jsonable(value),
        "threshold": threshold,
        "relation": relation,
        "passed": bool(passed),
    }


def _relative_change(coarse: float, fine: float) -> float:
    denominator = max(abs(float(fine)), 1.0e-300)
    return abs(float(coarse) - float(fine)) / denominator


def _case_row(case: Mapping[str, Any], result: Mapping[str, Any], case_hash: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        **case,
        "canonical_case_sha256": case_hash,
        "finite": result["finite"],
        "cell_count": result["grid"]["cell_count"],
        "grid_shape": result["grid"]["shape"],
        "grid_edge_sha256": result["grid"]["edge_sha256"],
        "source_area_integral_relative_error": result["source"][
            "source_area_integral_relative_error"
        ],
        "source_power_integral_relative_error": result["source"][
            "source_power_integral_relative_error"
        ],
        "source_smearing": result["source"]["source_smearing"],
        "clip_count": result["clip_count"],
    }
    if result["mode"] == "steady":
        row.update(
            {
                "Theta": result["metrics"]["Theta"],
                "Rs_K_W": result["metrics"]["Rs_K_W"],
                "normalized_power_imbalance": result["ledger"][
                    "normalized_power_imbalance"
                ],
            }
        )
    else:
        row.update(
            {
                "steps_per_output": result["metrics"]["steps_per_output"],
                "maximum_normalized_sensible_energy_imbalance": result["ledger"][
                    "maximum_normalized_sensible_energy_imbalance"
                ],
                "Zth_K_W": result["metrics"]["Zth_K_W"],
                "boundary_outflow_W": result["ledger"]["boundary_outflow_W"],
                "cumulative_outward_heat_J": result["ledger"][
                    "cumulative_outward_heat_J"
                ],
            }
        )
    return row


def _write_figure(
    path: str | Path,
    reference_rows: list[dict[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.2), constrained_layout=True)

    rho_line = np.linspace(1.0, 5.0, 161)
    theta_line = np.asarray([steady_dimensionless_theta(value) for value in rho_line])
    axes[0].plot(rho_line, theta_line, color="black", label="Eq. (21)")
    markers = {
        "square_steady_M1D3": (0.94, "o"),
        "square_steady_M2D3": (0.97, "s"),
        "square_steady_M3D3": (1.00, "^"),
        "square_steady_M3D2": (1.03, "D"),
        "square_steady_M3D1": (1.06, "P"),
        "rho5_steady_M2D3": (4.94, "s"),
        "rho5_steady_M3D3": (5.00, "^"),
        "rho5_steady_M3D2": (5.06, "D"),
    }
    for case_id, (rho, marker) in markers.items():
        if case_id in results:
            axes[0].scatter(
                [rho], [results[case_id]["metrics"]["Theta"]], marker=marker,
                s=48, label=case_id.replace("_steady", ""),
            )
    axes[0].set(
        xlabel=r"aspect ratio $\rho$",
        ylabel=r"$\Theta=k\sqrt{A_s}R_s$",
        title="Steady independent-reference closure",
    )
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=7, ncol=2)

    times = np.asarray([row["time_s"] for row in reference_rows])
    reference = np.asarray([row["Z_green_K_W"] for row in reference_rows])
    axes[1].semilogx(times, reference, color="black", label="Green reference")
    if "rho5_transient_M3D3_fine" in results:
        three_d = np.asarray(
            results["rho5_transient_M3D3_fine"]["metrics"]["Zth_K_W"]
        )
        axes[1].semilogx(times, three_d, "o-", label="3D FVM (fine time)")
    if "rho5_xz_M3D3_base" in results:
        xz = np.asarray(results["rho5_xz_M3D3_base"]["metrics"]["Zth_K_W"])
        axes[1].semilogx(times, xz, "s--", label="x-z comparator")
        if "rho5_transient_M3D3_fine" in results:
            bias = np.abs(xz - three_d) / np.maximum(np.abs(three_d), 1.0e-300)
            twin = axes[1].twinx()
            bias_line = twin.semilogx(times, bias, color="#b55d47", linestyle=":", label="finite-width bias")[0]
            twin.set_ylabel("finite-width bias")
            twin.set_ylim(bottom=0.0)
            axes[1].legend(axes[1].lines + [bias_line], [line.get_label() for line in axes[1].lines] + [bias_line.get_label()], fontsize=8, loc="lower right")
    axes[1].set(
        xlabel="time (s)", ylabel=r"$Z_{th}$ (K/W)",
        title="Transient reference, 3D, and x-z comparator",
    )
    axes[1].grid(alpha=0.25)
    if "rho5_xz_M3D3_base" not in results:
        axes[1].legend(fontsize=8, loc="lower right")
    fig.savefig(target, dpi=180)
    plt.close(fig)


def _write_report(path: str | Path, summary: Mapping[str, Any]) -> None:
    gates = summary["gates"]
    gate_rows = "\n".join(
        f"| `{name}` | {record['value']} | {record['threshold']} | "
        f"{'pass' if record['passed'] else 'fail'} |"
        for name, record in gates.items()
    )
    failed = [name for name, record in gates.items() if not record["passed"]]
    text = f"""# M43 Finite-Width Thermal-Spreading Closure

## Outcome

M43 selected **{summary['decision']}** with evidence status
`{summary['status']}`. It executed
{summary['forward_accounting']['unique_thermal_pde_forwards']} unique
thermal-only PDE forwards in
{summary['forward_accounting']['wall_clock_s']:.3f} s wall time and
{summary['forward_accounting']['cpu_time_s']:.3f} s process CPU time. The
largest grid contained {summary['forward_accounting']['maximum_cell_count']}
cells. Failed or unassessed mandatory gates: {failed or ['none']}.

## Evidence boundary

This is solver-generated manufactured component evidence for a homogeneous,
isotropic, constant-property half-space and a 500 nm by 100 nm isoflux source.
It is not Qiu-device reproduction, calibrated multilayer physics, external or
experimental validation, phase-change enthalpy, a reduced thermal-parameter
fit, inverse identification, or PINN evidence. No device forward, fit, inverse,
PINN training, GPU calculation, or sealed 13 V access occurred.

The M42 source/local resistance error remains 1.330233207545514 and latent
heat remains unresolved and unassessed. M43 cannot repair either blocker.

## Independent reference and finite-volume contract

The steady reference independently implements Yovanovich--Muzychka--Culham
Eq. (21), DOI `10.2514/2.6467`. The transient reference independently
integrates the source-area Green step kernel documented by Yovanovich (1997),
DOI `10.2514/6.1997-2458`. Neither reference imports the FVM implementation.

The comparator uses quarter symmetry, an exactly aligned explicit top-face
Neumann source, fixed far-field temperature, zero-flux symmetry/top-exterior
faces, and a source-face temperature reconstructed from the first cell center.
Domain extension is append-only. The sensible-energy ledger is discrete
bookkeeping and is not a device heat-capacity measurement.

## Preregistered mandatory gates

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
{gate_rows}

## Claim and next-step disposition

`M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY` authorizes only a bounded M44
comparison of 1-RC, 2-RC, and causal thermal kernels, including validity and
abstention boundaries. `M43_STOP_C_FREEZE_1D` permanently closes quantitative
Qiu 2D/2.5D/3D rescue and routes directly to the frozen one-dimensional,
calibration-gated rank-1 `gamma_sub` submission package. No result authorizes
Qiu coupled dynamics, pure x-z quantitative use, `gamma_sub/gamma_eff`, total
phase enthalpy, inverse identification, or PINN training.

## Version and integrity

- Base SHA: `{summary['base_commit']}`
- Preregistration SHA: `{summary['preregistration_commit']}`
- Runtime HEAD before the self-referential result commit:
  `{summary['runtime_head']}`
- Result SHA: reported in the final Git handoff because a commit cannot contain
  its own SHA without changing it.
- Protected evidence SHA-256 and mtimes unchanged:
  `{summary['protected_evidence_unchanged']}` /
  `{summary['protected_evidence_mtime_unchanged']}`.
"""
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def run(config_path: Path) -> dict[str, Any]:
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    config = dict(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    if _git("branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError(f"M43 must run on {EXPECTED_BRANCH}")
    config_contract = _validate_config_contract(config)
    if not config_contract["passed"]:
        raise RuntimeError(f"M43 config contract failed: {config_contract['failed_checks']}")
    prereg, preregistration_identities = _find_and_verify_preregistration(config_path)
    base = str(config["base_commit"])
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=ROOT
    ).returncode != 0:
        raise RuntimeError("M43 base commit is not an ancestor of runtime HEAD")
    required = str(config["required_ancestor"])
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", required, "HEAD"], cwd=ROOT
    ).returncode != 0:
        raise RuntimeError("M42 preregistration is not an ancestor of runtime HEAD")

    protected = _protected_paths()
    protected_baseline = _verify_protected_baseline(protected)
    before = _snapshot(protected)
    receipt_path = _resolve(config["outputs"]["execution_receipt"])
    summary_path = _resolve(config["outputs"]["summary"])
    receipt = _create_execution_receipt(
        receipt_path,
        summary_path,
        prereg,
        _sha256(config_path),
        preregistration_identities,
        before,
        wall_started=wall_started,
        cpu_started=cpu_started,
    )
    gates_cfg = config["gates"]
    area = float(config["geometry"]["source_area_m2"])
    conductivity = float(config["material"]["thermal_conductivity_W_mK"])
    diffusivity = float(config["material"]["thermal_diffusivity_m2_s"])
    rho = float(config["geometry"]["source_aspect_ratio_rho"])
    Fo_values = np.asarray(config["time"]["fvm_comparison_Fo_A"], dtype=float)
    times_s = Fo_values * area / diffusivity
    steady_reference = {
        "rho1": steady_dimensionless_theta(1.0),
        "rho5": steady_dimensionless_theta(rho),
    }
    base_theta = transient_dimensionless_theta(
        rho,
        Fo_values,
        epsabs=float(config["reference"]["green_quadrature"]["base_epsabs"]),
        epsrel=float(config["reference"]["green_quadrature"]["base_epsrel"]),
    )
    fine_theta = transient_dimensionless_theta(
        rho,
        Fo_values,
        epsabs=float(config["reference"]["green_quadrature"]["fine_epsabs"]),
        epsrel=float(config["reference"]["green_quadrature"]["fine_epsrel"]),
    )
    base_Z = transient_impedance_K_W(
        rho, area, conductivity, diffusivity, times_s,
        epsabs=float(config["reference"]["green_quadrature"]["base_epsabs"]),
        epsrel=float(config["reference"]["green_quadrature"]["base_epsrel"]),
    )
    fine_Z = transient_impedance_K_W(
        rho, area, conductivity, diffusivity, times_s,
        epsabs=float(config["reference"]["green_quadrature"]["fine_epsabs"]),
        epsrel=float(config["reference"]["green_quadrature"]["fine_epsrel"]),
    )
    early_Fo = float(config["time"]["green_early_Fo_A"])
    long_Fo = float(config["time"]["green_long_Fo_A"])
    early_value = float(transient_dimensionless_theta(rho, early_Fo))
    early_limit = 2.0 * math.sqrt(early_Fo / math.pi)
    long_value = float(transient_dimensionless_theta(rho, long_Fo))
    Rs_reference = spreading_resistance_K_W(rho, area, conductivity)

    gates: dict[str, dict[str, Any]] = {
        "eq21_rho1_relative_error": _gate(
            abs(steady_reference["rho1"] - float(config["reference"]["golden"]["rho_1"]))
            / float(config["reference"]["golden"]["rho_1"]),
            gates_cfg["eq21_rho1_relative_error_max"],
        ),
        "eq21_rho5_relative_error": _gate(
            abs(steady_reference["rho5"] - float(config["reference"]["golden"]["rho_5"]))
            / float(config["reference"]["golden"]["rho_5"]),
            gates_cfg["eq21_rho5_relative_error_max"],
        ),
        "green_early_limit_error": _gate(
            abs(early_value - early_limit) / early_limit,
            gates_cfg["green_early_limit_error_max"],
        ),
        "green_long_limit_error": _gate(
            abs(long_value - steady_reference["rho5"]) / steady_reference["rho5"],
            gates_cfg["green_long_limit_error_max"],
        ),
        "green_quadrature_refinement_change": _gate(
            float(np.max(np.abs(base_theta - fine_theta))) / steady_reference["rho5"],
            gates_cfg["green_quadrature_refinement_change_max"],
        ),
    }
    gate_names = list(DYNAMIC_GATE_NAMES)
    for name in gate_names:
        relation = "equal" if name == "finite_nan_clip_source_smearing_unit_error" else "max"
        gates[name] = _gate(None, gates_cfg[GATE_THRESHOLD_KEYS[name]], relation=relation)


    results: dict[str, Mapping[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    case_hashes: set[str] = set()
    forward_count = 0
    maximum_cells = 0

    confirmatory_stage_entered = False

    def elapsed_budget() -> tuple[float, float]:
        return time.perf_counter() - wall_started, time.process_time() - cpu_started

    def execute(case: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal forward_count, maximum_cells
        wall_elapsed, cpu_elapsed = elapsed_budget()
        if forward_count >= int(config["budget"]["maximum_unique_pde_forwards"]):
            raise RuntimeError("M43 unique thermal-PDE forward budget exhausted before case")
        if wall_elapsed >= float(config["budget"]["maximum_wall_clock_s"]):
            raise RuntimeError("M43 wall-clock budget exhausted before case")
        if cpu_elapsed >= float(config["budget"]["maximum_cpu_time_s"]):
            raise RuntimeError("M43 CPU budget exhausted before case")
        physical = {
            "geometry": case["geometry"],
            "mode": case["mode"],
            "mesh": case["mesh"],
            "domain": case["domain"],
            "time": case.get("time"),
            "config_sha256": _sha256(config_path),
        }
        case_hash = _canonical_hash(physical)
        if case_hash in case_hashes:
            raise RuntimeError(f"identical M43 PDE case repeated: {case['case_id']}")
        case_hashes.add(case_hash)
        receipt["forward_invocations_attempted"] = int(receipt["forward_invocations_attempted"]) + 1
        receipt["cases"].append(
            {"case_id": str(case["case_id"]), "canonical_case_sha256": case_hash, "status": "running"}
        )
        _update_execution_receipt(receipt_path, receipt)
        solver_mode = "xz" if case["mode"] == "transient_xz" else "3d"
        try:
            grid = build_quarter_grid(
                config, str(case["geometry"]), str(case["mesh"]), str(case["domain"]),
                mode=solver_mode,
            )
            if case["mode"] == "steady":
                result = run_steady_case(config, grid)
            else:
                steps = int(config["time"]["backward_euler_steps_per_output"][str(case["time"])])
                result = run_transient_case(
                    config, grid, times_s=times_s, steps_per_output=steps
                )
        except Exception as exc:
            receipt["status"] = "terminal_failed"
            receipt["failure"] = {"case_id": str(case["case_id"]), "type": type(exc).__name__, "message": str(exc)}
            receipt["cases"][-1]["status"] = "failed"
            _update_execution_receipt(receipt_path, receipt)
            raise
        forward_count += 1
        maximum_cells = max(maximum_cells, int(result["grid"]["cell_count"]))
        receipt["forward_invocations_completed"] = forward_count
        receipt["cases"][-1]["status"] = "completed"
        receipt["cases"][-1]["cell_count"] = int(result["grid"]["cell_count"])
        _update_execution_receipt(receipt_path, receipt)
        results[str(case["case_id"])] = result
        rows.append(_case_row(case, result, case_hash))
        return result

    matrix = list(config["forward_matrix"])
    analytic_pass = all(gates[name]["passed"] for name in ANALYTIC_GATE_NAMES)
    if analytic_pass:
        for case in matrix[:5]:
            execute(case)
        square = results["square_steady_M3D3"]
        square_reference_error = abs(square["metrics"]["Theta"] - steady_reference["rho1"]) / steady_reference["rho1"]
        steady_power_max = max(
            float(result["ledger"]["normalized_power_imbalance"])
            for result in results.values()
        )
        source_area_max = max(
            float(result["source"]["source_area_integral_relative_error"])
            for result in results.values()
        )
        integrity_error = any(
            _case_contract_error(
                config,
                next(item for item in matrix if item["case_id"] == case_id),
                result,
                times_s,
            )
            for case_id, result in results.items()
        )
        gates["steady_rho1_reference_error"] = _gate(
            square_reference_error, gates_cfg["steady_rho1_reference_error_max"]
        )
        gates["steady_normalized_power_imbalance"] = _gate(
            steady_power_max, gates_cfg["steady_normalized_power_imbalance_max"]
        )
        gates["source_area_integral_error"] = _gate(
            source_area_max, gates_cfg["source_area_integral_error_max"]
        )
        gates["source_power_integral_error"] = _gate(
            max(float(result["source"]["source_power_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_power_integral_error_max"],
        )
        gates["finite_nan_clip_source_smearing_unit_error"] = _gate(
            integrity_error,
            gates_cfg["finite_nan_clip_source_smearing_unit_error"],
            relation="equal",
        )

    square_stage_pass = analytic_pass and all(
        gates[name]["passed"]
        for name in (
            "steady_rho1_reference_error",
            "steady_normalized_power_imbalance",
            "source_area_integral_error",
            "source_power_integral_error",
            "finite_nan_clip_source_smearing_unit_error",
        )
    )
    if square_stage_pass:
        for case in matrix[5:8]:
            execute(case)
        rho5_fine = results["rho5_steady_M3D3"]
        rho5_reference_error = abs(rho5_fine["metrics"]["Theta"] - steady_reference["rho5"]) / steady_reference["rho5"]
        mesh_change = _relative_change(
            results["rho5_steady_M2D3"]["metrics"]["Theta"],
            rho5_fine["metrics"]["Theta"],
        )
        domain_change = _relative_change(
            results["rho5_steady_M3D2"]["metrics"]["Theta"],
            rho5_fine["metrics"]["Theta"],
        )
        gates["steady_rho5_reference_error"] = _gate(
            rho5_reference_error, gates_cfg["steady_rho5_reference_error_max"]
        )
        gates["rho5_mesh_pair_change"] = _gate(
            mesh_change, gates_cfg["rho5_mesh_pair_change_max"]
        )
        gates["rho5_domain_pair_change"] = _gate(
            domain_change, gates_cfg["rho5_domain_pair_change_max"]
        )
        gates["steady_normalized_power_imbalance"] = _gate(
            max(float(result["ledger"]["normalized_power_imbalance"]) for result in results.values()),
            gates_cfg["steady_normalized_power_imbalance_max"],
        )
        gates["source_area_integral_error"] = _gate(
            max(float(result["source"]["source_area_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_area_integral_error_max"],
        )
        gates["source_power_integral_error"] = _gate(
            max(float(result["source"]["source_power_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_power_integral_error_max"],
        )
        integrity_error = any(
            _case_contract_error(
                config,
                next(item for item in matrix if item["case_id"] == case_id),
                result,
                times_s,
            )
            for case_id, result in results.items()
        )
        gates["finite_nan_clip_source_smearing_unit_error"] = _gate(
            integrity_error,
            gates_cfg["finite_nan_clip_source_smearing_unit_error"],
            relation="equal",
        )

    steady_stage_pass = square_stage_pass and all(
        gates[name]["passed"]
        for name in (
            "steady_rho5_reference_error",
            "rho5_mesh_pair_change",
            "rho5_domain_pair_change",
            "steady_normalized_power_imbalance",
            "source_area_integral_error",
            "source_power_integral_error",
            "finite_nan_clip_source_smearing_unit_error",
        )
    )
    if steady_stage_pass:
        confirmatory_stage_entered = True
        receipt["confirmatory_stage_entered"] = True
        _update_execution_receipt(receipt_path, receipt)
        for case in matrix[8:12]:
            execute(case)
        transient_base = np.asarray(results["rho5_transient_M3D3_base"]["metrics"]["Zth_K_W"])
        transient_fine = np.asarray(results["rho5_transient_M3D3_fine"]["metrics"]["Zth_K_W"])
        green_error = float(np.max(np.abs(transient_fine - fine_Z))) / Rs_reference
        time_change = float(np.max(np.abs(transient_base - transient_fine))) / Rs_reference
        energy_max = max(
            float(results[case["case_id"]]["ledger"]["maximum_normalized_sensible_energy_imbalance"])
            for case in matrix[8:12]
        )
        q_base = np.asarray(results["rho5_transient_M3D3_base"]["ledger"]["boundary_outflow_W"])
        q_fine = np.asarray(results["rho5_transient_M3D3_fine"]["ledger"]["boundary_outflow_W"])
        e_base = np.asarray(results["rho5_transient_M3D3_base"]["ledger"]["cumulative_outward_heat_J"])
        e_fine = np.asarray(results["rho5_transient_M3D3_fine"]["ledger"]["cumulative_outward_heat_J"])
        model_power = float(results["rho5_transient_M3D3_base"]["ledger"]["expected_model_power_W"])
        q_change = float(np.max(np.abs(q_base - q_fine))) / model_power
        e_change = float(np.max(np.abs(e_base - e_fine) / (model_power * times_s)))
        gates["transient_3d_green_normalized_max_error"] = _gate(
            green_error, gates_cfg["transient_3d_green_normalized_max_error_max"]
        )
        gates["transient_time_pair_change"] = _gate(
            time_change, gates_cfg["transient_time_pair_change_max"]
        )
        gates["transient_normalized_sensible_energy_imbalance"] = _gate(
            energy_max,
            gates_cfg["transient_normalized_sensible_energy_imbalance_max"],
        )
        gates["near_zero_outflow_normalized_change"] = _gate(
            max(q_change, e_change), gates_cfg["near_zero_outflow_normalized_change_max"]
        )
        gates["source_area_integral_error"] = _gate(
            max(float(result["source"]["source_area_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_area_integral_error_max"],
        )
        gates["source_power_integral_error"] = _gate(
            max(float(result["source"]["source_power_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_power_integral_error_max"],
        )
        integrity_error = any(
            _case_contract_error(
                config,
                next(item for item in matrix if item["case_id"] == case_id),
                result,
                times_s,
            )
            for case_id, result in results.items()
        )
        gates["finite_nan_clip_source_smearing_unit_error"] = _gate(
            integrity_error,
            gates_cfg["finite_nan_clip_source_smearing_unit_error"],
            relation="equal",
        )

    transient_stage_pass = steady_stage_pass and all(
        gates[name]["passed"]
        for name in (
            "transient_3d_green_normalized_max_error",
            "transient_time_pair_change",
            "transient_normalized_sensible_energy_imbalance",
            "near_zero_outflow_normalized_change",
            "source_area_integral_error",
            "source_power_integral_error",
            "finite_nan_clip_source_smearing_unit_error",
        )
    )
    if transient_stage_pass:
        for case in matrix[12:15]:
            execute(case)
        def bias(xz_id: str, three_d_id: str) -> np.ndarray:
            xz = np.asarray(results[xz_id]["metrics"]["Zth_K_W"])
            three_d = np.asarray(results[three_d_id]["metrics"]["Zth_K_W"])
            return np.abs(xz - three_d) / np.maximum(np.abs(three_d), 1.0e-300)

        bias_m2 = bias("rho5_xz_M2D3_base", "rho5_transient_M2D3_base")
        bias_m3 = bias("rho5_xz_M3D3_base", "rho5_transient_M3D3_base")
        bias_d2 = bias("rho5_xz_M3D2_base", "rho5_transient_M3D2_base")
        gates["finite_width_bias_mesh_pair_absolute_change"] = _gate(
            float(np.max(np.abs(bias_m2 - bias_m3))),
            gates_cfg["finite_width_bias_mesh_pair_absolute_change_max"],
        )
        gates["finite_width_bias_domain_pair_absolute_change"] = _gate(
            float(np.max(np.abs(bias_d2 - bias_m3))),
            gates_cfg["finite_width_bias_domain_pair_absolute_change_max"],
        )
        gates["source_area_integral_error"] = _gate(
            max(float(result["source"]["source_area_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_area_integral_error_max"],
        )
        gates["source_power_integral_error"] = _gate(
            max(float(result["source"]["source_power_integral_relative_error"]) for result in results.values()),
            gates_cfg["source_power_integral_error_max"],
        )
        energy_max = max(
            float(result["ledger"]["maximum_normalized_sensible_energy_imbalance"])
            for result in results.values()
            if result["mode"].startswith("transient")
        )
        gates["transient_normalized_sensible_energy_imbalance"] = _gate(
            energy_max,
            gates_cfg["transient_normalized_sensible_energy_imbalance_max"],
        )
        integrity_error = any(
            _case_contract_error(
                config,
                next(item for item in matrix if item["case_id"] == case_id),
                result,
                times_s,
            )
            for case_id, result in results.items()
        )
        gates["finite_nan_clip_source_smearing_unit_error"] = _gate(
            integrity_error,
            gates_cfg["finite_nan_clip_source_smearing_unit_error"],
            relation="equal",
        )

    receipt["status"] = "completed" if forward_count == int(config["budget"]["preregistered_pde_forwards"]) else "terminal_stopped"
    receipt["confirmatory_stage_entered"] = confirmatory_stage_entered
    receipt["confirmatory_completed"] = forward_count == int(config["budget"]["preregistered_pde_forwards"])
    _update_execution_receipt(receipt_path, receipt)

    after = _snapshot(protected)
    hashes_unchanged = all(before[key]["sha256"] == after[key]["sha256"] for key in before)
    mtimes_unchanged = all(before[key]["mtime_ns"] == after[key]["mtime_ns"] for key in before)
    if not hashes_unchanged or not mtimes_unchanged:
        raise RuntimeError("protected evidence changed during M43")

    wall_time = time.perf_counter() - wall_started
    cpu_time = time.process_time() - cpu_started
    gates["wall_clock_budget"] = _gate(
        wall_time, float(config["budget"]["maximum_wall_clock_s"])
    )
    gates["cpu_time_budget"] = _gate(
        cpu_time, float(config["budget"]["maximum_cpu_time_s"])
    )
    all_pass = bool(gates) and all(record["passed"] for record in gates.values())
    completed_confirmatory = forward_count == int(config["budget"]["preregistered_pde_forwards"])
    decision = (
        config["decision"]["all_mandatory_gates_pass"]
        if all_pass and completed_confirmatory
        else config["decision"]["any_mandatory_gate_fails"]
    )
    status = "qualified_supported" if decision == "M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY" else "failed_but_informative"

    reference_rows = [
        {
            "Fo_A": float(Fo),
            "time_s": float(t),
            "Theta_base": float(tb),
            "Theta_fine": float(tf),
            "Z_green_K_W": float(zb),
            "Z_green_fine_K_W": float(zf),
            "steady_Rs_K_W": Rs_reference,
        }
        for Fo, t, tb, tf, zb, zf in zip(
            Fo_values, times_s, base_theta, fine_theta, base_Z, fine_Z, strict=True
        )
    ]
    _write_csv(config["outputs"]["cases"], rows)
    _write_csv(config["outputs"]["transient_reference"], reference_rows)
    _write_figure(config["outputs"]["figure"], reference_rows, results)

    summary: dict[str, Any] = {
        "schema_version": config["schema_version"],
        "task_id": config["task_id"],
        "evidence_type": config["evidence_boundary"]["evidence_type"],
        "status": status,
        "decision": decision,
        "base_commit": base,
        "preregistration_commit": prereg,
        "runtime_head": _git("rev-parse", "HEAD"),
        "runtime_branch": _git("branch", "--show-current"),
        "result_commit": None,
        "config_sha256": _sha256(config_path),
        "preregistration_file_sha256": preregistration_identities,
        "config_contract": config_contract,
        "protected_baseline_identity": protected_baseline,
        "runtime_code_sha256": {
            "runner": _sha256("scripts/run_m43_finite_width_thermal_spreading.py"),
            "reference": _sha256("src/pinnpcm/physics/m43_thermal_spreading_reference.py"),
            "solver": _sha256("src/pinnpcm/solvers/m43_finite_width_thermal.py"),
        },
        "reference": {
            "rho1_Theta": steady_reference["rho1"],
            "rho5_Theta": steady_reference["rho5"],
            "rho5_Rs_K_W": Rs_reference,
            "green_early_Fo_A": early_Fo,
            "green_long_Fo_A": long_Fo,
        },
        "gates": gates,
        "gate_pass_count": sum(bool(record["passed"]) for record in gates.values()),
        "gate_total_count": len(gates),
        "failed_gates": [name for name, record in gates.items() if not record["passed"]],
        "forward_accounting": {
            "unique_thermal_pde_forwards": forward_count,
            "preregistered_pde_forwards": config["budget"]["preregistered_pde_forwards"],
            "maximum_unique_pde_forwards": config["budget"]["maximum_unique_pde_forwards"],
            "canonical_case_sha256": sorted(case_hashes),
            "maximum_cell_count": maximum_cells,
            "wall_clock_s": wall_time,
            "cpu_time_s": cpu_time,
            "maximum_wall_clock_s": config["budget"]["maximum_wall_clock_s"],
            "formal_runner_invocations": 1,
            "confirmatory_stage_entered": confirmatory_stage_entered,
            "confirmatory_completed": completed_confirmatory,
            "formal_confirmatory_attempts": 1 if confirmatory_stage_entered else 0,
        },
        "prohibited_run_accounting": {
            "scientific_device_forwards": 0,
            "qiu_device_forwards": 0,
            "electrical_or_circuit_forwards": 0,
            "curve_fit_runs": 0,
            "inverse_runs": 0,
            "pinn_training_runs": 0,
            "gpu_runs": 0,
            "sealed_13V_accessed": False,
        },
        "upstream_blockers": {
            "m42_source_local_resistance_error": config["evidence_boundary"]["upstream_source_local_resistance_error"],
            "latent_heat": config["evidence_boundary"]["upstream_latent_heat_status"],
            "resolved_by_m43": False,
        },
        "protected_evidence_unchanged": hashes_unchanged,
        "protected_evidence_mtime_unchanged": mtimes_unchanged,
        "protected_evidence": after,
        "allowed_claims": [
            "Only the selected terminal decision and its homogeneous-half-space manufactured numerical evidence.",
        ],
        "forbidden_claims": [
            "Qiu coupled dynamic ground truth",
            "VO2/Ti/Au/Al2O3 multilayer validation",
            "pure x-z quantitative model",
            "gamma_sub or gamma_eff validation",
            "phase-change total enthalpy",
            "inverse identification or PINN success",
            "external or experimental validation",
        ],
    }
    summary["artifact_sha256"] = {
        "cases": _sha256(config["outputs"]["cases"]),
        "transient_reference": _sha256(config["outputs"]["transient_reference"]),
        "figure": _sha256(config["outputs"]["figure"]),
    }
    _write_json(config["outputs"]["summary"], summary)
    _write_report(config["outputs"]["report"], summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/m43_finite_width_thermal_spreading.yaml"),
    )
    args = parser.parse_args()
    config_path = _resolve(args.config)
    try:
        summary = run(config_path)
    except Exception as exc:
        try:
            summary = _terminalize_failed_formal_run(config_path, exc)
        except Exception as terminal_exc:
            print(
                json.dumps(
                    {
                        "status": "terminal_evidence_write_failed",
                        "type": type(terminal_exc).__name__,
                        "message": str(terminal_exc),
                        "original_type": type(exc).__name__,
                        "original_message": str(exc),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        if summary is None:
            print(
                json.dumps(
                    {
                        "status": "failed_before_formal_receipt",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "decision": summary["decision"],
                    "forwards": summary["forward_accounting"]["unique_thermal_pde_forwards"],
                    "failed_gates": summary["failed_gates"],
                    "terminal_failure": summary.get("terminal_failure"),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": summary["status"],
                "decision": summary["decision"],
                "forwards": summary["forward_accounting"]["unique_thermal_pde_forwards"],
                "failed_gates": summary["failed_gates"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

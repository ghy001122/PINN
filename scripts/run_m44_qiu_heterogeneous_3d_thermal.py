"""Run the preregistered M44 heterogeneous thermal-component bridge.

M44 is a bounded, thermal-only source-location nuisance audit.  It never
solves an electrical problem, fits a Qiu curve, accesses sealed data, performs
an inverse solve, or trains a PINN.  A successful run certifies only the
registered small-signal sensible-heat component family.
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
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import yaml

from pinnpcm.physics.m44_layered_thermal_reference import (
    layered_modal_step_response_K_W,
    max_normalized_response_change,
    single_slab_surface_step_impedance_K_W,
    steady_series_resistance_K_W,
)
from pinnpcm.solvers import m44_heterogeneous_3d_thermal as thermal_solver


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "research/m44-qiu-heterogeneous-3d-thermal-bridge"
PREREG_SUBJECT = "Preregister heterogeneous 3D thermal bridge"
CANONICAL_CONFIG = "configs/m44_qiu_heterogeneous_3d_thermal.yaml"
PREREG_REQUIRED_FILES = frozenset(
    {
        CANONICAL_CONFIG,
        "docs/research_strategy/m44_qiu_heterogeneous_3d_thermal_preregistration.md",
        "docs/physics/m44_qiu_heterogeneous_thermal_contract.md",
        "docs/codex_reports/m43_postcommit_attestation.md",
        "outputs/tables/m43_postcommit_attestation.json",
        "docs/literature/m44_classic_reproduction_closeout_matrix.md",
        "outputs/tables/m44_classic_reproduction_closeout.json",
    }
)
FORBIDDEN_PREREG_IMPLEMENTATION_PATHS = frozenset(
    {
        "scripts/run_m44_qiu_heterogeneous_3d_thermal.py",
        "src/pinnpcm/physics/m44_layered_thermal_reference.py",
        "src/pinnpcm/solvers/m44_heterogeneous_3d_thermal.py",
    }
)
EXPECTED_OUTPUT_PATHS = {
    "summary": "outputs/tables/m44_qiu_heterogeneous_3d_thermal_summary.json",
    "cases": "outputs/tables/m44_qiu_heterogeneous_3d_thermal_cases.csv",
    "layered_reference": "outputs/tables/m44_layered_modal_reference.csv",
    "provenance": "outputs/tables/m44_geometry_material_source_provenance.csv",
    "execution_receipt": "outputs/tables/m44_execution_receipt.json",
    "final_validation": "outputs/tables/m44_final_validation.json",
    "full_test_log": "outputs/logs/m44_full_pytest.txt",
    "figure": "outputs/figures/m44/m44_qiu_heterogeneous_3d_thermal_bridge.png",
    "report": "docs/codex_reports/m44_qiu_heterogeneous_3d_thermal_bridge.md",
}
EXPECTED_GATE_NAMES = frozenset(
    {
        "homogeneous_steady_recovery_error",
        "homogeneous_transient_recovery_error",
        "layered_1d_steady_reference_error",
        "layered_1d_transient_reference_error",
        "layered_reference_self_refinement_change",
        "single_slab_reference_error",
        "source_geometry_integration_error",
        "source_power_integration_error",
        "steady_normalized_power_imbalance",
        "transient_normalized_sensible_energy_imbalance",
        "zth_mesh_pair_change",
        "zth_domain_pair_change",
        "zth_time_pair_change",
        "vo2_mean_temperature_pair_change",
        "vo2_tmax_pair_change",
        "xz_bias_mesh_pair_absolute_change",
        "xz_bias_domain_pair_absolute_change",
        "causal_positive_monotone_finite_steady",
        "missing_voting_provenance",
        "finite_nan_clip_negative_property_unit_source_smearing_error",
        "unique_forward_budget",
        "cpu_time_budget",
    }
)
EXPECTED_PROHIBITED_RUN_ACCOUNTING = {
    "electrical_forward_runs": 0,
    "qiu_device_coupled_forwards": 0,
    "curve_fit_runs": 0,
    "inverse_runs": 0,
    "pinn_training_runs": 0,
    "gpu_runs": 0,
    "sealed_13V_accessed": False,
    "latent_heat_runs": 0,
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


def _git_blob_sha256(commit: str, path: str) -> str:
    blob = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest().upper()


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


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _jsonable(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(target)


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if str(key) not in fields:
                fields.append(str(key))
    if not fields:
        raise ValueError("CSV output requires at least one field")
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


def _expand_case_matrix(config: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    matrix = config["forward_matrix"]
    cases: list[dict[str, Any]] = [dict(case) for case in matrix["fixed_cases"]]
    for source_id in matrix["heterogeneous_3d_templates"]["source_ids"]:
        for template in matrix["heterogeneous_3d_templates"]["cases"]:
            case = dict(template)
            case["id"] = f"{source_id}_{case.pop('suffix')}"
            case["mode"] = "heterogeneous_3d"
            case["source_id"] = source_id
            cases.append(case)
    for source_id in matrix["xz_templates"]["source_ids"]:
        for template in matrix["xz_templates"]["cases"]:
            case = dict(template)
            case["id"] = f"{source_id}_{case.pop('suffix')}"
            case["mode"] = "xz"
            case["source_id"] = source_id
            cases.append(case)
    return tuple(cases)


def _validate_config_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    budget = config["budget"]
    geometry = config["geometry"]
    interfaces = config["interfaces"]
    cases = _expand_case_matrix(config)
    ids = tuple(str(case["id"]) for case in cases)
    source_ids = tuple(
        str(item["id"]) for item in config["source_families"] if item.get("voting")
    )
    required_ancestors = tuple(str(item) for item in config["required_ancestors"])
    checks = {
        "task_id": config.get("task_id")
        == "Q2_M44_QIU_HETEROGENEOUS_3D_THERMAL_BRIDGE_AND_REPRODUCTION_CLOSEOUT",
        "schema_version": config.get("schema_version")
        == "m44_qiu_heterogeneous_3d_thermal_v1",
        "base_commit": config.get("base_commit")
        == "e433fe900cb4376b5e1d5cfe81333e527f5454a5",
        "required_ancestors": required_ancestors
        == (
            "a1f229a25b4392422af3ced7e354ada0b5605365",
            "0dc103f391d1206fe02c100987ecab68ed1d741d",
        ),
        "thermal_only_run_class": config.get("run_class")
        == "bounded_heterogeneous_thermal_component_bridge",
        "cpu_only": budget.get("cpu_only") is True,
        "exact_case_count": len(cases)
        == int(budget["preregistered_unique_thermal_forwards"])
        == 31,
        "unique_case_ids": len(set(ids)) == len(ids),
        "forward_ceiling": int(budget["maximum_unique_thermal_forwards"]) == 32,
        "single_attempt": int(budget["maximum_formal_attempts"]) == 1,
        "no_search_or_rescue": all(
            budget.get(key) is True
            for key in (
                "no_parameter_search",
                "no_rescue_round",
                "identical_case_rerun_forbidden",
            )
        ),
        "reported_footprint": math.isclose(
            float(geometry["vo2_full_x_m"]) * float(geometry["vo2_full_y_m"]),
            5.0e-14,
            rel_tol=0.0,
            abs_tol=1.0e-28,
        ),
        "quarter_power": math.isclose(
            float(geometry["quarter_power_W"]),
            0.25 * float(geometry["full_power_W"]),
            rel_tol=0.0,
            abs_tol=1.0e-18,
        ),
        "xz_power": math.isclose(
            float(geometry["xz_half_domain_power_W"]),
            0.5 * float(geometry["full_power_W"]),
            rel_tol=0.0,
            abs_tol=1.0e-18,
        ),
        "contact_prior_locked": float(geometry["contact_support_fraction_of_half_x"])
        == 0.20
        and list(geometry["contact_support_fraction_preregistered_bounds"])
        == [0.10, 0.30],
        "perfect_contact_voting": float(
            interfaces["voting_thermal_boundary_resistance_m2K_W"]
        )
        == 0.0,
        "voting_sources": source_ids == ("S_bulk", "S_contact", "S_mixed"),
        "source_mixture_contract": {
            item["id"]: (item.get("weight_bulk"), item.get("weight_contact"))
            for item in config["source_families"]
            if item.get("voting")
        }
        == {
            "S_bulk": (1.0, 0.0),
            "S_contact": (0.0, 1.0),
            "S_mixed": (0.5, 0.5),
        },
        "prohibited_accounting": all(
            config["evidence_boundary"].get(key) == value
            for key, value in {
                "electrical_forward_runs": 0,
                "inverse_runs": 0,
                "pinn_training_runs": 0,
                "sealed_13V_accessed": False,
            }.items()
        ),
        "output_paths": all(
            config["outputs"].get(key) == value
            for key, value in EXPECTED_OUTPUT_PATHS.items()
        ),
        "decision_fail_closed": config["decision"]
        == {
            "all_gates_pass_and_source_envelope_le_0p05": "M44_HET3D_GO_ROBUST",
            "all_gates_pass_and_source_envelope_gt_0p05": "M44_HET3D_GO_CONDITIONAL_OR_ABSTAIN",
            "any_gate_fails": "M44_STOP_REAL_GEOMETRY_UPGRADE",
            "threshold_change_after_results": "forbidden",
            "repair_round": "forbidden",
            "unique_Qiu_device_kernel_claim": "forbidden_for_all_outcomes",
        },
        "all_properties_positive": all(
            float(item["thermal_conductivity_W_mK"]) > 0.0
            and float(item["volumetric_heat_capacity_J_m3K"]) > 0.0
            for item in config["materials"].values()
        ),
        "no_missing_voting_provenance": all(
            bool(str(item.get("provenance", "")).strip())
            for item in config["materials"].values()
            if item.get("voting")
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "expanded_case_ids": list(ids),
        "expanded_case_count": len(ids),
    }


def _find_and_verify_preregistration(config_path: Path) -> tuple[str, dict[str, str]]:
    head = _git("rev-parse", "HEAD")
    if _git("branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("formal M44 must run on the registered research branch")
    if _git("show", "-s", "--format=%s", head) != PREREG_SUBJECT:
        raise RuntimeError("runtime HEAD is not the locked M44 preregistration commit")
    changed = {
        line
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", head
        ).splitlines()
        if line
    }
    if not PREREG_REQUIRED_FILES.issubset(changed):
        missing = sorted(PREREG_REQUIRED_FILES - changed)
        raise RuntimeError(f"M44 preregistration commit is missing paths: {missing}")
    forbidden = sorted(FORBIDDEN_PREREG_IMPLEMENTATION_PATHS & changed)
    if forbidden:
        raise RuntimeError(f"implementation was committed before preregistration: {forbidden}")
    if config_path.resolve() != _resolve(CANONICAL_CONFIG).resolve():
        raise RuntimeError("formal M44 must use the canonical locked config")
    identities: dict[str, str] = {}
    for path in sorted(PREREG_REQUIRED_FILES):
        current = _sha256(path)
        if current != _git_blob_sha256(head, path):
            raise RuntimeError(f"preregistration identity changed: {path}")
        identities[path] = current
    return head, identities


def _gate(value: Any, threshold: Any, *, relation: str = "max") -> dict[str, Any]:
    if value is None:
        passed = False
    elif relation == "max":
        passed = bool(math.isfinite(float(value)) and float(value) <= float(threshold))
    elif relation == "equal":
        passed = bool(value == threshold)
    else:
        raise ValueError(f"unsupported gate relation: {relation}")
    return {"value": _jsonable(value), "threshold": _jsonable(threshold), "relation": relation, "passed": passed}


def _fail_closed_gate_records(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    thresholds = config["gates"]
    direct = {
        "homogeneous_steady_recovery_error": "homogeneous_steady_recovery_error_max",
        "homogeneous_transient_recovery_error": "homogeneous_transient_recovery_error_max",
        "layered_1d_steady_reference_error": "layered_1d_steady_reference_error_max",
        "layered_1d_transient_reference_error": "layered_1d_transient_reference_error_max",
        "source_geometry_integration_error": "source_geometry_integration_error_max",
        "source_power_integration_error": "source_power_integration_error_max",
        "steady_normalized_power_imbalance": "steady_normalized_power_imbalance_max",
        "transient_normalized_sensible_energy_imbalance": "transient_normalized_sensible_energy_imbalance_max",
        "zth_mesh_pair_change": "zth_mesh_pair_change_max",
        "zth_domain_pair_change": "zth_domain_pair_change_max",
        "zth_time_pair_change": "zth_time_pair_change_max",
        "vo2_mean_temperature_pair_change": "vo2_mean_temperature_pair_change_max",
        "vo2_tmax_pair_change": "vo2_tmax_pair_change_max",
        "xz_bias_mesh_pair_absolute_change": "xz_bias_mesh_pair_absolute_change_max",
        "xz_bias_domain_pair_absolute_change": "xz_bias_domain_pair_absolute_change_max",
    }
    records = {name: _gate(None, thresholds[key]) for name, key in direct.items()}
    records["layered_reference_self_refinement_change"] = _gate(
        None, float(config["layered_reference"]["self_refinement_change_max"])
    )
    records["single_slab_reference_error"] = _gate(
        None, float(config["layered_reference"]["self_refinement_change_max"])
    )
    records["causal_positive_monotone_finite_steady"] = _gate(
        None, bool(thresholds["causal_positive_monotone_finite_steady_required"]), relation="equal"
    )
    records["missing_voting_provenance"] = _gate(
        None, bool(thresholds["missing_voting_provenance_allowed"]), relation="equal"
    )
    records["finite_nan_clip_negative_property_unit_source_smearing_error"] = _gate(
        None,
        bool(thresholds["finite_nan_clip_negative_property_unit_source_smearing_error"]),
        relation="equal",
    )
    records["unique_forward_budget"] = _gate(
        None, int(config["budget"]["maximum_unique_thermal_forwards"])
    )
    records["cpu_time_budget"] = _gate(
        None, float(config["budget"]["maximum_cpu_time_s"])
    )
    if set(records) != EXPECTED_GATE_NAMES:
        raise RuntimeError("M44 fail-closed gate schema is incomplete")
    return records


def _terminal_decision(
    config: Mapping[str, Any], gates: Mapping[str, Mapping[str, Any]], source_envelope: float | None
) -> tuple[str, str]:
    if set(gates) != EXPECTED_GATE_NAMES or not all(bool(item.get("passed")) for item in gates.values()):
        return "M44_STOP_REAL_GEOMETRY_UPGRADE", "failed_but_informative"
    if source_envelope is None or not math.isfinite(float(source_envelope)):
        return "M44_STOP_REAL_GEOMETRY_UPGRADE", "failed_but_informative"
    if float(source_envelope) <= float(config["source_envelope"]["robust_max"]):
        return "M44_HET3D_GO_ROBUST", "qualified_supported"
    return "M44_HET3D_GO_CONDITIONAL_OR_ABSTAIN", "qualified_supported"


def _create_execution_receipt(
    receipt_path: Path,
    summary_path: Path,
    preregistration_commit: str,
    config_sha256: str,
    identities: Mapping[str, str],
) -> dict[str, Any]:
    if receipt_path.exists() or summary_path.exists():
        raise RuntimeError("M44 formal result already exists; rerun is forbidden")
    payload = {
        "schema_version": "m44_one_shot_execution_receipt_v1",
        "status": "started",
        "preregistration_commit": preregistration_commit,
        "preregistration_file_sha256": dict(identities),
        "config_sha256": config_sha256,
        "formal_runner_invocations": 1,
        "forward_invocations_attempted": 0,
        "forward_invocations_completed": 0,
        "case_ids": [],
        "canonical_case_sha256": [],
        "terminal_rerun_forbidden": True,
        "prohibited_run_accounting": dict(EXPECTED_PROHIBITED_RUN_ACCOUNTING),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def _update_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    _write_json(path, payload)


def _relative_curve_change(first: Sequence[float], second: Sequence[float], reference: float) -> float:
    a = np.asarray(first, dtype=float)
    b = np.asarray(second, dtype=float)
    if a.shape != b.shape or a.ndim != 1 or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        return float("inf")
    return float(np.max(np.abs(a - b)) / max(abs(float(reference)), 1.0e-300))


def _strip_state(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in result.items() if key != "theta_active_K"}


def _case_time_settings(config: Mapping[str, Any], case: Mapping[str, Any]) -> tuple[np.ndarray, int]:
    profile = case.get("time")
    times = np.asarray(config["time"]["output_times_s"], dtype=float)
    steps = int(config["time"]["base_backward_euler_substeps_per_interval"])
    if profile == "fine":
        steps = int(config["time"]["fine_backward_euler_substeps_per_interval"])
    return times, steps


def _execute_case(config: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one registered thermal case through the public solver API."""

    case_id = str(case["id"])
    mode = str(case["mode"])
    kind = str(case["kind"])
    full_power = float(config["geometry"]["full_power_W"])
    if mode == "homogeneous":
        grid = thermal_solver.build_homogeneous_anchor_grid(
            config, mesh=str(case["mesh"]), domain=str(case["domain"])
        )
        system = thermal_solver.assemble_heterogeneous_system(config, grid)
        source, source_audit = thermal_solver.build_surface_anchor_source(config, system)
    elif mode == "layered1d":
        grid = thermal_solver.build_layered_1d_grid(config, resolution="fine")
        system = thermal_solver.assemble_heterogeneous_system(config, grid)
        source, source_audit = thermal_solver.build_layered_top_source(config, system)
    elif mode in {"heterogeneous_3d", "xz"}:
        grid = thermal_solver.build_heterogeneous_grid(
            config,
            mesh=str(case["mesh"]),
            domain=str(case["domain"]),
            mode="3d" if mode == "heterogeneous_3d" else "xz",
        )
        system = thermal_solver.assemble_heterogeneous_system(config, grid)
        source, source_audit = thermal_solver.build_source_vector(
            config, system, str(case["source_id"])
        )
    else:
        raise RuntimeError(f"unsupported registered M44 mode: {mode}")
    if kind == "steady":
        solved = thermal_solver.solve_steady(system, source, full_power_W=full_power)
    elif kind == "transient":
        if mode == "layered1d":
            times = np.asarray(config["layered_reference"]["comparison_times_s"], dtype=float)
            steps = int(config["time"]["fine_backward_euler_substeps_per_interval"])
        else:
            times, steps = _case_time_settings(config, case)
        solved = thermal_solver.solve_transient(
            system,
            source,
            full_power_W=full_power,
            times_s=times,
            steps_per_interval=steps,
        )
    else:
        raise RuntimeError(f"unsupported registered M44 kind: {kind}")
    return {
        "case_id": case_id,
        "mode": mode,
        "kind": kind,
        "mesh": case.get("mesh"),
        "domain": case.get("domain"),
        "time_profile": case.get("time"),
        "source_id": case.get("source_id", source_audit.get("source_id")),
        "source_audit": _jsonable(source_audit),
        **_strip_state(solved),
    }


def _protected_paths() -> list[Path]:
    """Reuse the M43 protection surface and add all locked M43 artifacts."""

    # Direct ``python scripts/run_m44_...py`` execution puts ``scripts/``
    # rather than the repository root on ``sys.path``.  Bind the import to
    # this file's already-resolved repository root so the command-line path
    # and the pytest module-import path use the same protected-artifact code.
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    from scripts.run_m43_finite_width_thermal_spreading import (
        _protected_paths as m43_protected_paths,
    )

    paths = {path.resolve() for path in m43_protected_paths()}
    for relative in (
        "configs/m43_finite_width_thermal_spreading.yaml",
        "docs/research_strategy/m43_finite_width_thermal_spreading_preregistration.md",
        "docs/physics/m43_thermal_spreading_source_contract.md",
        "docs/codex_reports/m43_finite_width_thermal_spreading_closure.md",
        "outputs/tables/m43_finite_width_thermal_spreading_summary.json",
        "outputs/tables/m43_finite_width_thermal_spreading_cases.csv",
        "outputs/tables/m43_transient_green_reference.csv",
        "outputs/tables/m43_execution_receipt.json",
        "outputs/tables/m43_final_validation.json",
        "outputs/tables/m43_postcommit_attestation.json",
        "outputs/figures/m43/m43_thermal_spreading_closure.png",
    ):
        path = _resolve(relative)
        if not path.is_file():
            raise FileNotFoundError(f"protected M43 evidence missing: {relative}")
        paths.add(path.resolve())
    return sorted(paths)


def _snapshot(paths: Sequence[Path]) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(ROOT).as_posix(): {
            "sha256": _sha256(path),
            "mtime_ns": path.stat().st_mtime_ns,
            "size_bytes": path.stat().st_size,
        }
        for path in paths
    }


def _load_m43_reference(config: Mapping[str, Any]) -> dict[str, Any]:
    summary_path = _resolve(config["sources"]["m43_locked"]["summary"])
    transient_path = _resolve(config["sources"]["m43_locked"]["transient"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "qualified_supported" or summary.get("decision") != "M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY":
        raise RuntimeError("locked M43 component evidence is not qualified-supported")
    with transient_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.asarray([float(row["time_s"]) for row in rows], dtype=float)
    impedance = np.asarray([float(row["Z_green_fine_K_W"]) for row in rows], dtype=float)
    registered_times = np.asarray(config["time"]["output_times_s"], dtype=float)
    if times.shape != registered_times.shape or not np.allclose(times, registered_times, rtol=1.0e-13, atol=0.0):
        raise RuntimeError("M44 output times do not match the locked M43 reference")
    reference = float(config["reference"]["m43_steady_R_ref_K_W"])
    if not math.isclose(float(rows[-1]["steady_Rs_K_W"]), reference, rel_tol=1.0e-13):
        raise RuntimeError("M43 steady reference identity changed")
    return {
        "summary_sha256": _sha256(summary_path),
        "transient_sha256": _sha256(transient_path),
        "times_s": times,
        "Zth_K_W": impedance,
        "steady_R_K_W": reference,
    }


def _verify_m43_postcommit_attestation() -> dict[str, Any]:
    """Verify every raw artifact identity frozen by the M43 attestation."""

    path = _resolve("outputs/tables/m43_postcommit_attestation.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifacts = payload.get("artifact_sha256")
    if not isinstance(artifacts, dict) or len(artifacts) != 7:
        raise RuntimeError("M43 postcommit attestation must contain exactly seven artifacts")
    records: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for relative, expected in artifacts.items():
        artifact = _resolve(str(relative))
        actual = _sha256(artifact) if artifact.is_file() else None
        passed = actual == str(expected).upper()
        records[str(relative)] = {
            "expected_sha256": str(expected).upper(),
            "actual_sha256": actual,
            "passed": passed,
        }
        if not passed:
            failures.append(str(relative))
    if failures:
        raise RuntimeError(f"M43 attested artifact identity failed: {failures}")
    return {
        "attestation_sha256": _sha256(path),
        "artifact_count": len(records),
        "records": records,
        "passed": True,
    }


def _build_layered_references(config: Mapping[str, Any]) -> dict[str, Any]:
    reference_cfg = config["layered_reference"]
    stack = list(reference_cfg["stack_top_to_bottom"])
    geometry = config["geometry"]
    material = config["materials"]
    thickness = {
        "au": float(geometry["au_thickness_m"]),
        "ti": float(geometry["ti_thickness_m"]),
        "vo2": float(geometry["vo2_thickness_m"]),
        "al2o3": float(reference_cfg["substrate_reference_depth_m"]),
    }
    thicknesses = np.asarray([thickness[name] for name in stack], dtype=float)
    conductivities = np.asarray(
        [float(material[name]["thermal_conductivity_W_mK"]) for name in stack]
    )
    capacities = np.asarray(
        [float(material[name]["volumetric_heat_capacity_J_m3K"]) for name in stack]
    )
    times = np.asarray(reference_cfg["comparison_times_s"], dtype=float)
    area = float(config["time"]["source_area_m2"])
    base = layered_modal_step_response_K_W(
        thicknesses,
        conductivities,
        capacities,
        reference_cfg["reference_mesh_elements_per_layer_base"],
        times,
        area_m2=area,
    )
    fine = layered_modal_step_response_K_W(
        thicknesses,
        conductivities,
        capacities,
        reference_cfg["reference_mesh_elements_per_layer_fine"],
        times,
        area_m2=area,
    )
    steady = steady_series_resistance_K_W(thicknesses, conductivities, area_m2=area)
    self_change = max_normalized_response_change(
        base.top_impedance_K_W, fine.top_impedance_K_W, steady
    )

    # Independent manufactured single-slab check.  These fixed values match
    # the preregistered analytic-series contract and do not count as a PDE run.
    slab_L = 2.0e-6
    slab_k = 7.0
    slab_cv = 2.8e6
    slab_area = 4.0e-10
    slab_times = np.logspace(-3.0, 1.0, 13) * slab_L**2 / (slab_k / slab_cv)
    slab_analytic = single_slab_surface_step_impedance_K_W(
        slab_L,
        slab_k,
        slab_cv,
        slab_times,
        area_m2=slab_area,
        series_terms=int(reference_cfg["single_slab_analytic_series_terms"]),
    )
    slab_modal = layered_modal_step_response_K_W(
        [slab_L], [slab_k], [slab_cv], [320], slab_times, area_m2=slab_area
    )
    slab_steady = slab_L / (slab_k * slab_area)
    slab_error = float(np.max(np.abs(slab_modal.top_impedance_K_W - slab_analytic)) / slab_steady)
    return {
        "stack": stack,
        "times_s": times,
        "base_Zth_K_W": base.top_impedance_K_W,
        "fine_Zth_K_W": fine.top_impedance_K_W,
        "steady_R_K_W": steady,
        "self_refinement_change": self_change,
        "single_slab_error": slab_error,
        "layer_thicknesses_m": thicknesses,
        "thermal_conductivities_W_mK": conductivities,
        "volumetric_heat_capacities_J_m3K": capacities,
    }


def _source_geometry_error(config: Mapping[str, Any], result: Mapping[str, Any]) -> float:
    audit = result["source_audit"]
    if "source_geometry_integration_relative_error" in audit:
        return abs(float(audit["source_geometry_integration_relative_error"]))
    mode = str(result["mode"])
    source_id = result.get("source_id")
    if mode == "homogeneous":
        expected = float(config["time"]["source_area_m2"]) / 4.0
        actual = float(audit["surface_source_area_m2"])
    elif mode in {"heterogeneous_3d", "xz"}:
        fraction = 0.25 if mode == "heterogeneous_3d" else 0.5
        expected = (
            float(config["geometry"]["vo2_full_x_m"])
            * float(config["geometry"]["vo2_full_y_m"])
            * float(config["geometry"]["vo2_thickness_m"])
            * fraction
        )
        if source_id == "S_contact":
            expected *= float(config["geometry"]["contact_support_fraction_of_half_x"])
        actual = float(audit["vo2_source_support_volume_m3"])
    elif mode == "layered1d":
        return abs(float(audit.get("source_geometry_integration_relative_error", 0.0)))
    else:
        return float("inf")
    return abs(actual - expected) / max(abs(expected), 1.0e-300)


def _result_curve(result: Mapping[str, Any], key: str) -> np.ndarray:
    return np.asarray(result["metrics"][key], dtype=float)


def _aggregate_gates(
    config: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
    m43: Mapping[str, Any],
    layered: Mapping[str, Any],
    *,
    forward_count: int,
    cpu_time_s: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    gates = _fail_closed_gate_records(config)
    limits = config["gates"]
    reference = float(m43["steady_R_K_W"])

    homogeneous_steady = results["homogeneous_steady_M3D3"]
    homogeneous_transient = results["homogeneous_transient_M3D3"]
    homogeneous_steady_error = abs(
        float(homogeneous_steady["metrics"]["source_surface_face_Zth_K_W"]) - reference
    ) / reference
    homogeneous_transient_error = _relative_curve_change(
        homogeneous_transient["metrics"]["source_surface_face_Zth_K_W"],
        m43["Zth_K_W"],
        reference,
    )
    gates["homogeneous_steady_recovery_error"] = _gate(
        homogeneous_steady_error, limits["homogeneous_steady_recovery_error_max"]
    )
    gates["homogeneous_transient_recovery_error"] = _gate(
        homogeneous_transient_error, limits["homogeneous_transient_recovery_error_max"]
    )

    layered_steady = results["layered1d_steady"]
    layered_transient = results["layered1d_transient"]
    layered_steady_error = abs(
        float(layered_steady["metrics"]["source_surface_face_Zth_K_W"])
        - float(layered["steady_R_K_W"])
    ) / float(layered["steady_R_K_W"])
    layered_transient_error = _relative_curve_change(
        layered_transient["metrics"]["source_surface_face_Zth_K_W"],
        layered["fine_Zth_K_W"],
        float(layered["steady_R_K_W"]),
    )
    gates["layered_1d_steady_reference_error"] = _gate(
        layered_steady_error, limits["layered_1d_steady_reference_error_max"]
    )
    gates["layered_1d_transient_reference_error"] = _gate(
        layered_transient_error, limits["layered_1d_transient_reference_error_max"]
    )
    gates["layered_reference_self_refinement_change"] = _gate(
        layered["self_refinement_change"],
        config["layered_reference"]["self_refinement_change_max"],
    )
    gates["single_slab_reference_error"] = _gate(
        layered["single_slab_error"],
        config["layered_reference"]["self_refinement_change_max"],
    )

    geometry_error = max(_source_geometry_error(config, item) for item in results.values())
    power_error = max(
        abs(float(item["source_audit"]["source_power_integration_relative_error"]))
        for item in results.values()
    )
    steady_imbalance = max(
        float(item["ledger"]["normalized_power_imbalance"])
        for item in results.values()
        if item["kind"] == "steady"
    )
    transient_imbalance = max(
        float(item["ledger"]["maximum_normalized_sensible_energy_imbalance"])
        for item in results.values()
        if item["kind"] == "transient"
    )
    gates["source_geometry_integration_error"] = _gate(
        geometry_error, limits["source_geometry_integration_error_max"]
    )
    gates["source_power_integration_error"] = _gate(
        power_error, limits["source_power_integration_error_max"]
    )
    gates["steady_normalized_power_imbalance"] = _gate(
        steady_imbalance, limits["steady_normalized_power_imbalance_max"]
    )
    gates["transient_normalized_sensible_energy_imbalance"] = _gate(
        transient_imbalance,
        limits["transient_normalized_sensible_energy_imbalance_max"],
    )

    mesh_changes: list[float] = []
    domain_changes: list[float] = []
    time_changes: list[float] = []
    mean_changes: list[float] = []
    tmax_changes: list[float] = []
    bias_mesh_changes: list[float] = []
    bias_domain_changes: list[float] = []
    source_curves: dict[str, np.ndarray] = {}
    bias_curves: dict[str, dict[str, np.ndarray]] = {}
    heterogeneity_departure: dict[str, float] = {}
    heterogeneity_nrmse: dict[str, float] = {}
    for source in ("S_bulk", "S_contact", "S_mixed"):
        m2 = _result_curve(results[f"{source}_transient_M2D2_base"], "vo2_mean_Zth_K_W")
        m3 = _result_curve(results[f"{source}_transient_M3D2_base"], "vo2_mean_Zth_K_W")
        d3 = _result_curve(results[f"{source}_transient_M3D3_base"], "vo2_mean_Zth_K_W")
        fine = _result_curve(results[f"{source}_transient_M3D2_fine"], "vo2_mean_Zth_K_W")
        mesh_changes.append(_relative_curve_change(m2, m3, reference))
        domain_changes.append(_relative_curve_change(m3, d3, reference))
        time_changes.append(_relative_curve_change(m3, fine, reference))
        mean_changes.extend((mesh_changes[-1], domain_changes[-1], time_changes[-1]))
        t_m2 = _result_curve(results[f"{source}_transient_M2D2_base"], "vo2_tmax_rise_K")
        t_m3 = _result_curve(results[f"{source}_transient_M3D2_base"], "vo2_tmax_rise_K")
        t_d3 = _result_curve(results[f"{source}_transient_M3D3_base"], "vo2_tmax_rise_K")
        t_fine = _result_curve(results[f"{source}_transient_M3D2_fine"], "vo2_tmax_rise_K")
        tnorm = max(float(np.max(np.abs(t_m3))), float(np.max(np.abs(t_d3))), 1.0e-300)
        tmax_changes.extend(
            (
                float(np.max(np.abs(t_m2 - t_m3))) / tnorm,
                float(np.max(np.abs(t_m3 - t_d3))) / tnorm,
                float(np.max(np.abs(t_m3 - t_fine))) / tnorm,
            )
        )
        xz_m2 = _result_curve(results[f"{source}_xz_transient_M2D2"], "vo2_mean_Zth_K_W")
        xz_m3 = _result_curve(results[f"{source}_xz_transient_M3D2"], "vo2_mean_Zth_K_W")
        xz_d3 = _result_curve(results[f"{source}_xz_transient_M3D3"], "vo2_mean_Zth_K_W")
        bias_m2 = np.abs(xz_m2 - m2) / reference
        bias_m3 = np.abs(xz_m3 - m3) / reference
        bias_d3 = np.abs(xz_d3 - d3) / reference
        bias_mesh_changes.append(float(np.max(np.abs(bias_m2 - bias_m3))))
        bias_domain_changes.append(float(np.max(np.abs(bias_m3 - bias_d3))))
        source_curves[source] = d3
        heterogeneity_departure[source] = _relative_curve_change(
            d3, m43["Zth_K_W"], reference
        )
        heterogeneity_nrmse[source] = float(
            np.sqrt(np.mean((d3 - np.asarray(m43["Zth_K_W"], dtype=float)) ** 2))
            / reference
        )
        bias_curves[source] = {"M2D2": bias_m2, "M3D2": bias_m3, "M3D3": bias_d3}

    convergence_values = {
        "zth_mesh_pair_change": max(mesh_changes),
        "zth_domain_pair_change": max(domain_changes),
        "zth_time_pair_change": max(time_changes),
        "vo2_mean_temperature_pair_change": max(mean_changes),
        "vo2_tmax_pair_change": max(tmax_changes),
        "xz_bias_mesh_pair_absolute_change": max(bias_mesh_changes),
        "xz_bias_domain_pair_absolute_change": max(bias_domain_changes),
    }
    for name, value in convergence_values.items():
        gates[name] = _gate(value, limits[f"{name}_max"])

    physical = all(bool(item.get("finite")) and bool(item.get("positive")) for item in results.values())
    for item in results.values():
        if item["kind"] == "transient":
            curve_key = "source_surface_face_Zth_K_W" if item["mode"] in {"homogeneous", "layered1d"} else "vo2_mean_Zth_K_W"
            curve = _result_curve(item, curve_key)
            physical = physical and bool(np.all(np.isfinite(curve))) and bool(np.all(curve >= -1.0e-12)) and bool(np.all(np.diff(curve) >= -1.0e-10 * max(float(np.max(np.abs(curve))), 1.0)))
    gates["causal_positive_monotone_finite_steady"] = _gate(
        physical,
        limits["causal_positive_monotone_finite_steady_required"],
        relation="equal",
    )
    provenance_rows = _provenance_rows(config)
    missing_provenance = not all(
        bool(str(item.get("provenance", "")).strip())
        for item in provenance_rows
        if item.get("voting")
    )
    gates["missing_voting_provenance"] = _gate(
        missing_provenance, limits["missing_voting_provenance_allowed"], relation="equal"
    )
    source_audits = [
        item["source_audit"]
        for item in results.values()
        if item["mode"] in {"heterogeneous_3d", "xz"}
    ]
    face_alignment_ok = all(
        audit.get("contact_support_face_aligned") is True for audit in source_audits
    )
    source_support_ok = all(
        int(audit.get("source_cell_count", 0)) > 0 for audit in source_audits
    )
    source_mix_ok = _validate_config_contract(config)["checks"][
        "source_mixture_contract"
    ]
    integration_ok = (
        geometry_error <= float(limits["source_geometry_integration_error_max"])
        and power_error <= float(limits["source_power_integration_error_max"])
    )
    integrity_error = (
        not physical
        or not face_alignment_ok
        or not source_support_ok
        or not source_mix_ok
        or not integration_ok
        or not math.isfinite(geometry_error)
        or not math.isfinite(power_error)
    )
    gates["finite_nan_clip_negative_property_unit_source_smearing_error"] = _gate(
        integrity_error,
        limits["finite_nan_clip_negative_property_unit_source_smearing_error"],
        relation="equal",
    )
    gates["unique_forward_budget"] = _gate(
        forward_count, config["budget"]["maximum_unique_thermal_forwards"]
    )
    gates["cpu_time_budget"] = _gate(
        cpu_time_s, config["budget"]["maximum_cpu_time_s"]
    )

    curves = list(source_curves.values())
    source_envelope = max(
        _relative_curve_change(curves[i], curves[j], reference)
        for i in range(len(curves))
        for j in range(i + 1, len(curves))
    )
    steady_values = [
        float(results[f"{source}_steady_M3D2"]["metrics"]["vo2_mean_Zth_K_W"])
        for source in ("S_bulk", "S_contact", "S_mixed")
    ]
    steady_source_envelope = (
        max(steady_values) - min(steady_values)
    ) / reference
    registered_times = np.asarray(config["time"]["output_times_s"], dtype=float)
    forbidden_intervals: dict[str, list[dict[str, float]]] = {}
    for source, ladders in bias_curves.items():
        mask = np.asarray(ladders["M3D3"], dtype=float) > 0.10
        intervals: list[dict[str, float]] = []
        start: int | None = None
        for index, active in enumerate(mask):
            if active and start is None:
                start = index
            if start is not None and (not active or index == mask.size - 1):
                end = index if active and index == mask.size - 1 else index - 1
                intervals.append(
                    {
                        "start_time_s": float(registered_times[start]),
                        "end_time_s": float(registered_times[end]),
                    }
                )
                start = None
        forbidden_intervals[source] = intervals
    diagnostics = {
        "source_envelope": source_envelope,
        "source_curves": source_curves,
        "heterogeneity_departure_by_source": heterogeneity_departure,
        "heterogeneity_normalized_rmse_by_source": heterogeneity_nrmse,
        "maximum_heterogeneity_departure": max(heterogeneity_departure.values()),
        "maximum_heterogeneity_normalized_rmse": max(heterogeneity_nrmse.values()),
        "non_voting_steady_source_envelope": steady_source_envelope,
        "non_voting_observation_operator_changes": "informative_only_not_a_terminal_gate",
        "xz_bias_curves": bias_curves,
        "xz_quantitative_forbidden_intervals": forbidden_intervals,
        "convergence": convergence_values,
        "maximum_geometry_error": geometry_error,
        "maximum_power_error": power_error,
        "maximum_steady_imbalance": steady_imbalance,
        "maximum_transient_energy_imbalance": transient_imbalance,
        "homogeneous_steady_error": homogeneous_steady_error,
        "homogeneous_transient_error": homogeneous_transient_error,
        "layered_steady_error": layered_steady_error,
        "layered_transient_error": layered_transient_error,
        "layered_transient_error_definition": "max_abs_waveform_error_normalized_by_steady_series_resistance",
        "contact_support_face_aligned": face_alignment_ok,
        "source_support_nonempty": source_support_ok,
    }
    return gates, diagnostics


def _case_rows(
    cases: Sequence[Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
    case_hashes: Mapping[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["id"])
        result = results[case_id]
        metrics = result["metrics"]
        ledger = result["ledger"]
        rows.append(
            {
                "case_id": case_id,
                "canonical_case_sha256": case_hashes[case_id],
                "mode": result["mode"],
                "kind": result["kind"],
                "source_id": result.get("source_id"),
                "mesh": result.get("mesh"),
                "domain": result.get("domain"),
                "time_profile": result.get("time_profile"),
                "active_cell_count": result.get("active_cell_count"),
                "finite": result.get("finite"),
                "positive": result.get("positive"),
                "source_audit": result.get("source_audit"),
                "time_s": metrics.get("time_s"),
                "vo2_mean_Zth_K_W": metrics.get("vo2_mean_Zth_K_W"),
                "source_mean_Zth_K_W": metrics.get("source_mean_Zth_K_W"),
                "source_surface_face_Zth_K_W": metrics.get(
                    "source_surface_face_Zth_K_W"
                ),
                "vo2_tmax_rise_K": metrics.get("vo2_tmax_rise_K"),
                "normalized_power_imbalance": ledger.get("normalized_power_imbalance"),
                "maximum_normalized_sensible_energy_imbalance": ledger.get(
                    "maximum_normalized_sensible_energy_imbalance"
                ),
            }
        )
    return rows


def _provenance_rows(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    geometry = config["geometry"]
    geometry_provenance_key = {
        "vo2_full_x_m": "footprint",
        "vo2_full_y_m": "footprint",
        "vo2_thickness_m": "vo2_thickness",
        "ti_thickness_m": "ti_au_thickness",
        "au_thickness_m": "ti_au_thickness",
    }
    for name, key in (
        ("vo2_full_x_m", "vo2_full_x_m"),
        ("vo2_full_y_m", "vo2_full_y_m"),
        ("vo2_thickness_m", "vo2_thickness_m"),
        ("ti_thickness_m", "ti_thickness_m"),
        ("au_thickness_m", "au_thickness_m"),
    ):
        rows.append(
            {
                "category": "geometry",
                "item": name,
                "value": geometry[key],
                "unit": "m",
                "provenance": geometry["reported_geometry_provenance"][
                    geometry_provenance_key[key]
                ],
                "voting": True,
            }
        )
    rows.append(
        {
            "category": "geometry",
            "item": "contact_support_fraction_of_half_x",
            "value": geometry["contact_support_fraction_of_half_x"],
            "unit": "1",
            "provenance": geometry["contact_support_provenance"],
            "voting": True,
        }
    )
    rows.extend(
        [
            {
                "category": "geometry",
                "item": "remote_domain_ladder",
                "value": config["grid"]["domain_multipliers_of_maximum_diffusion_length"],
                "unit": "multiples of registered diffusion length",
                "provenance": "preregistered numerical convergence contract",
                "voting": True,
            },
            {
                "category": "boundary",
                "item": "remote_x_y_bottom",
                "value": config["boundary_contract"]["far_x_y_bottom"],
                "unit": "boundary condition",
                "provenance": "preregistered numerical boundary contract",
                "voting": True,
            },
            {
                "category": "boundary",
                "item": "symmetry_x0_y0",
                "value": config["boundary_contract"]["symmetry_x0_y0"],
                "unit": "boundary condition",
                "provenance": "geometric symmetry and preregistered numerical contract",
                "voting": True,
            },
            {
                "category": "boundary",
                "item": "exposed_top_and_sides",
                "value": config["boundary_contract"]["exposed_top_and_material_sides"],
                "unit": "boundary condition",
                "provenance": "preregistered engineering boundary prior",
                "voting": True,
            },
            {
                "category": "interface",
                "item": "voting_thermal_boundary_resistance_m2K_W",
                "value": config["interfaces"][
                    "voting_thermal_boundary_resistance_m2K_W"
                ],
                "unit": "m^2 K W^-1",
                "provenance": "preregistered perfect-contact baseline; nonzero TBR excluded",
                "voting": True,
            },
        ]
    )
    for name, material in config["materials"].items():
        for quantity, unit in (
            ("thermal_conductivity_W_mK", "W m^-1 K^-1"),
            ("volumetric_heat_capacity_J_m3K", "J m^-3 K^-1"),
        ):
            rows.append(
                {
                    "category": "material",
                    "item": f"{name}.{quantity}",
                    "value": material[quantity],
                    "unit": unit,
                    "provenance": material["provenance"],
                    "voting": material["voting"],
                }
            )
    for source in config["source_families"]:
        rows.append(
            {
                "category": "source",
                "item": source["id"],
                "value": source["kind"],
                "unit": "equal registered total power",
                "provenance": "engineering-prior" if source.get("voting") else "manufactured solver anchor",
                "voting": bool(source.get("voting")),
            }
        )
    return rows


def _write_layered_reference(path: str | Path, layered: Mapping[str, Any]) -> None:
    rows = [
        {
            "time_s": float(time_s),
            "base_Zth_K_W": float(base),
            "fine_Zth_K_W": float(fine),
            "steady_R_K_W": float(layered["steady_R_K_W"]),
            "base_fine_normalized_change": float(layered["self_refinement_change"]),
        }
        for time_s, base, fine in zip(
            layered["times_s"],
            layered["base_Zth_K_W"],
            layered["fine_Zth_K_W"],
            strict=True,
        )
    ]
    _write_csv(path, rows)


def _write_figure(
    path: str | Path,
    config: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
    m43: Mapping[str, Any],
    layered: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 3, figsize=(13.8, 4.2), constrained_layout=True)

    axes[0].scatter(
        [0, 1],
        [
            100.0 * diagnostics["homogeneous_steady_error"],
            100.0 * diagnostics["layered_steady_error"],
        ],
        label="steady",
    )
    axes[0].scatter(
        [0, 1],
        [
            100.0 * diagnostics["homogeneous_transient_error"],
            100.0 * diagnostics["layered_transient_error"],
        ],
        marker="s",
        label="transient",
    )
    axes[0].axhline(2.0, color="black", linestyle="--", linewidth=1.0, label="2% gate")
    axes[0].set_xticks([0, 1], ["homogeneous", "layered 1D"])
    axes[0].set_ylabel("reference error (%)")
    axes[0].set_title("Independent-limit recovery")
    axes[0].legend(fontsize=8)

    times = np.asarray(config["time"]["output_times_s"], dtype=float)
    axes[1].semilogx(
        times,
        m43["Zth_K_W"],
        color="black",
        linestyle="--",
        linewidth=1.2,
        label="M43 homogeneous Green",
    )
    for source, curve in diagnostics["source_curves"].items():
        axes[1].semilogx(times, curve, marker="o", markersize=3, label=source)
    axes[1].set_xlabel("time (s)")
    axes[1].set_ylabel(r"$Z_{VO2}$ (K/W)")
    axes[1].set_title("Heterogeneous 3D source family")
    axes[1].legend(fontsize=8)

    for source, ladders in diagnostics["xz_bias_curves"].items():
        axes[2].semilogx(times, 100.0 * np.asarray(ladders["M3D3"]), label=source)
    axes[2].axhline(10.0, color="black", linestyle="--", linewidth=1.0, label="10% claim boundary")
    axes[2].set_xlabel("time (s)")
    axes[2].set_ylabel("x-z / 3D bias (% of M43 Rref)")
    axes[2].set_title("Resolved structural bias")
    axes[2].legend(fontsize=8)

    figure.savefig(target, dpi=180)
    plt.close(figure)


def _write_report(path: str | Path, summary: Mapping[str, Any]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    gates = summary["gates"]
    gate_rows = "\n".join(
        f"| `{name}` | {record['value']} | {record['threshold']} | {'pass' if record['passed'] else 'fail'} |"
        for name, record in sorted(gates.items())
    )
    text = f"""# M44 Qiu-scale heterogeneous 3D thermal bridge

## Decision

`{summary['decision']}` (`{summary['status']}`).

This is a thermal-only small-signal sensible-heat component result.  It is not
a Qiu device reproduction, experimental validation, identified Joule map,
phase-change enthalpy result, inverse result, or PINN result.

## Execution

- Preregistration commit: `{summary['preregistration_commit']}`
- Runtime branch / HEAD: `{summary['runtime_branch']}` / `{summary['runtime_head']}`
- Unique registered forwards: `{summary['forward_accounting']['unique_thermal_forwards']}` / `{summary['forward_accounting']['preregistered_thermal_forwards']}`
- CPU / wall time: `{summary['forward_accounting']['cpu_time_s']}` / `{summary['forward_accounting']['wall_clock_s']}` s
- Maximum active-cell count: `{summary['forward_accounting']['maximum_active_cell_count']}`
- Source envelope: `{summary['source_envelope']['value']}` (M43-Rref normalized)
- Maximum non-voting heterogeneous departure from M43 Green: `{summary['diagnostics']['maximum_heterogeneity_departure']}`
- Non-voting steady source envelope: `{summary['diagnostics']['non_voting_steady_source_envelope']}`

## Gates

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
{gate_rows}

## Evidence boundary

M42's source/local-resistance mismatch remains `{summary['upstream_blockers']['m42_source_local_resistance_error']}`.
Latent heat remains `{summary['upstream_blockers']['latent_heat_status']}`.  A
numerically passing M44 result cannot identify a unique Qiu thermal kernel;
source-location and geometry provenance remain explicit nuisance boundaries.
"""
    target.write_text(text, encoding="utf-8", newline="\n")


def _terminalize_failure(
    config_path: Path, failure: Exception
) -> dict[str, Any] | None:
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        receipt_path = _resolve(config["outputs"]["execution_receipt"])
        summary_path = _resolve(config["outputs"]["summary"])
    except Exception:
        return None
    if not receipt_path.is_file() or summary_path.exists():
        return None
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["status"] = "terminal_failed"
    receipt["terminal_failure"] = {
        "type": type(failure).__name__,
        "message": str(failure),
    }
    _update_receipt(receipt_path, receipt)
    gates = _fail_closed_gate_records(config)
    summary = {
        "schema_version": config["schema_version"],
        "task_id": config["task_id"],
        "status": "failed_but_informative",
        "decision": "M44_STOP_REAL_GEOMETRY_UPGRADE",
        "preregistration_commit": receipt["preregistration_commit"],
        "runtime_head": _git("rev-parse", "HEAD"),
        "runtime_branch": _git("branch", "--show-current"),
        "config_sha256": receipt["config_sha256"],
        "gates": gates,
        "gate_pass_count": 0,
        "gate_total_count": len(gates),
        "failed_gates": sorted(gates),
        "terminal_failure": receipt["terminal_failure"],
        "forward_accounting": {
            "attempted_thermal_forwards": receipt["forward_invocations_attempted"],
            "unique_thermal_forwards": receipt["forward_invocations_completed"],
            "preregistered_thermal_forwards": 31,
            "maximum_unique_thermal_forwards": 32,
        },
        "prohibited_run_accounting": dict(EXPECTED_PROHIBITED_RUN_ACCOUNTING),
        "source_envelope": {"value": None, "classification": "unassessed"},
    }
    _write_json(summary_path, summary)
    return summary


def run(config_path: Path) -> dict[str, Any]:
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    config_path = _resolve(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    contract = _validate_config_contract(config)
    if not contract["passed"]:
        raise RuntimeError(f"M44 config contract failed: {contract['failed_checks']}")
    preregistration_commit, preregistration_identities = _find_and_verify_preregistration(
        config_path
    )
    for ancestor in (config["base_commit"], *config["required_ancestors"]):
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(ancestor), preregistration_commit],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )

    protected_paths = _protected_paths()
    protected_before = _snapshot(protected_paths)
    m43_attestation_identity = _verify_m43_postcommit_attestation()
    outputs = config["outputs"]
    receipt_path = _resolve(outputs["execution_receipt"])
    summary_path = _resolve(outputs["summary"])
    receipt = _create_execution_receipt(
        receipt_path,
        summary_path,
        preregistration_commit,
        _sha256(config_path),
        preregistration_identities,
    )
    receipt["m43_postcommit_attestation_identity"] = m43_attestation_identity
    receipt["protected_evidence_before"] = protected_before
    _update_receipt(receipt_path, receipt)

    m43 = _load_m43_reference(config)
    layered = _build_layered_references(config)
    cases = _expand_case_matrix(config)
    results: dict[str, dict[str, Any]] = {}
    case_hashes: dict[str, str] = {}
    maximum_cells = 0
    for case in cases:
        case_id = str(case["id"])
        canonical_case = {
            "schema_version": config["schema_version"],
            "config_sha256": _sha256(config_path),
            "case": dict(case),
        }
        case_hash = _canonical_hash(canonical_case)
        if case_id in results or case_hash in case_hashes.values():
            raise RuntimeError(f"duplicate registered M44 case: {case_id}")
        receipt["forward_invocations_attempted"] += 1
        receipt["case_ids"].append(case_id)
        receipt["canonical_case_sha256"].append(case_hash)
        _update_receipt(receipt_path, receipt)
        result = _execute_case(config, case)
        results[case_id] = result
        case_hashes[case_id] = case_hash
        receipt["forward_invocations_completed"] += 1
        maximum_cells = max(maximum_cells, int(result.get("active_cell_count", 0)))
        _update_receipt(receipt_path, receipt)

    expected = int(config["budget"]["preregistered_unique_thermal_forwards"])
    if len(results) != expected or len(case_hashes) != expected:
        raise RuntimeError("M44 did not complete exactly 31 unique registered forwards")
    cpu_time_s = time.process_time() - cpu_started
    gates, diagnostics = _aggregate_gates(
        config,
        results,
        m43,
        layered,
        forward_count=len(results),
        cpu_time_s=cpu_time_s,
    )
    decision, status = _terminal_decision(
        config, gates, float(diagnostics["source_envelope"])
    )

    protected_after = _snapshot(protected_paths)
    protected_hash_unchanged = all(
        protected_before[key]["sha256"] == protected_after[key]["sha256"]
        for key in protected_before
    )
    protected_mtime_unchanged = all(
        protected_before[key]["mtime_ns"] == protected_after[key]["mtime_ns"]
        for key in protected_before
    )
    if not protected_hash_unchanged or not protected_mtime_unchanged:
        raise RuntimeError("protected M43/frozen/historical evidence changed during M44")

    rows = _case_rows(cases, results, case_hashes)
    provenance_rows = _provenance_rows(config)
    _write_csv(outputs["cases"], rows)
    _write_layered_reference(outputs["layered_reference"], layered)
    _write_csv(outputs["provenance"], provenance_rows)
    _write_figure(outputs["figure"], config, results, m43, layered, diagnostics)

    wall_time_s = time.perf_counter() - wall_started
    source_envelope = float(diagnostics["source_envelope"])
    source_classification = (
        "source_location_robust"
        if source_envelope <= float(config["source_envelope"]["robust_max"])
        else "source_location_conditional"
        if source_envelope <= float(config["source_envelope"]["conditional_max"])
        else "source_location_dominated"
    )
    failed_gates = sorted(name for name, item in gates.items() if not item["passed"])
    summary: dict[str, Any] = {
        "schema_version": config["schema_version"],
        "task_id": config["task_id"],
        "evidence_type": config["evidence_boundary"]["evidence_type"],
        "status": status,
        "decision": decision,
        "base_commit": config["base_commit"],
        "preregistration_commit": preregistration_commit,
        "runtime_head": _git("rev-parse", "HEAD"),
        "runtime_branch": _git("branch", "--show-current"),
        "result_commit": None,
        "config_sha256": _sha256(config_path),
        "preregistration_file_sha256": preregistration_identities,
        "m43_postcommit_attestation_identity": m43_attestation_identity,
        "config_contract": contract,
        "runtime_code_sha256": {
            "runner": _sha256("scripts/run_m44_qiu_heterogeneous_3d_thermal.py"),
            "layered_reference": _sha256(
                "src/pinnpcm/physics/m44_layered_thermal_reference.py"
            ),
            "heterogeneous_solver": _sha256(
                "src/pinnpcm/solvers/m44_heterogeneous_3d_thermal.py"
            ),
        },
        "references": {
            "m43_summary_sha256": m43["summary_sha256"],
            "m43_transient_sha256": m43["transient_sha256"],
            "m43_steady_R_ref_K_W": m43["steady_R_K_W"],
            "layered_steady_R_K_W": layered["steady_R_K_W"],
            "layered_self_refinement_change": layered["self_refinement_change"],
            "single_slab_reference_error": layered["single_slab_error"],
        },
        "gates": gates,
        "gate_pass_count": sum(bool(item["passed"]) for item in gates.values()),
        "gate_total_count": len(gates),
        "failed_gates": failed_gates,
        "diagnostics": diagnostics,
        "source_envelope": {
            "value": source_envelope,
            "robust_max": config["source_envelope"]["robust_max"],
            "conditional_max": config["source_envelope"]["conditional_max"],
            "classification": source_classification,
        },
        "forward_accounting": {
            "unique_thermal_forwards": len(results),
            "preregistered_thermal_forwards": expected,
            "maximum_unique_thermal_forwards": config["budget"][
                "maximum_unique_thermal_forwards"
            ],
            "canonical_case_sha256": sorted(case_hashes.values()),
            "maximum_active_cell_count": maximum_cells,
            "cpu_time_s": cpu_time_s,
            "wall_clock_s": wall_time_s,
            "maximum_cpu_time_s": config["budget"]["maximum_cpu_time_s"],
            "formal_runner_invocations": 1,
        },
        "prohibited_run_accounting": dict(EXPECTED_PROHIBITED_RUN_ACCOUNTING),
        "protected_evidence_unchanged": protected_hash_unchanged,
        "protected_evidence_mtime_unchanged": protected_mtime_unchanged,
        "protected_evidence_before": protected_before,
        "protected_evidence_after": protected_after,
        "upstream_blockers": {
            "m42_source_local_resistance_error": config["evidence_boundary"][
                "m42_source_local_resistance_error"
            ],
            "latent_heat_status": config["evidence_boundary"]["latent_heat_status"],
            "resolved_by_m44": False,
        },
        "allowed_claims": [
            "Only the registered heterogeneous sensible-thermal component result and its explicit source-location nuisance boundary.",
            "A numerically resolved x-z/3D structural bias may forbid x-z quantitative use.",
        ],
        "forbidden_claims": [
            "unique Qiu device thermal kernel",
            "Qiu coupled dynamic ground truth",
            "identified local Joule heat map",
            "phase-change enthalpy or latent-heat validation",
            "inverse identification or PINN success",
            "experimental or independent device validation",
        ],
    }
    summary["artifact_sha256"] = {
        "cases": _sha256(outputs["cases"]),
        "layered_reference": _sha256(outputs["layered_reference"]),
        "provenance": _sha256(outputs["provenance"]),
        "figure": _sha256(outputs["figure"]),
    }
    _write_json(outputs["summary"], summary)
    _write_report(outputs["report"], summary)
    receipt["status"] = "completed"
    receipt["decision"] = decision
    receipt["forward_invocations_attempted"] = len(results)
    receipt["forward_invocations_completed"] = len(results)
    receipt["summary_sha256"] = _sha256(outputs["summary"])
    receipt["terminal_rerun_forbidden"] = True
    _update_receipt(receipt_path, receipt)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(CANONICAL_CONFIG),
    )
    args = parser.parse_args()
    config_path = _resolve(args.config)
    try:
        summary = run(config_path)
    except Exception as exc:
        try:
            summary = _terminalize_failure(config_path, exc)
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
                    "forwards": summary["forward_accounting"][
                        "unique_thermal_forwards"
                    ],
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
                "forwards": summary["forward_accounting"]["unique_thermal_forwards"],
                "failed_gates": summary["failed_gates"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Preregister and execute the single bounded M40R Qiu E0 repair.

The original M40 formal run and every protected artifact remain immutable.
This runner consumes the non-voting forensic diagnosis, locks one repair,
executes the repaired formal verifier once, and fails closed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml
from scipy.interpolate import RegularGridInterpolator

try:  # package import under pytest
    from scripts import run_m40_qiu_vo2_2d_e0 as legacy
    from scripts.audit_m40r_qiu_mesh_forensics import _convergence, _protected_m40_paths
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    import run_m40_qiu_vo2_2d_e0 as legacy
    from audit_m40r_qiu_mesh_forensics import _convergence, _protected_m40_paths
from pinnpcm.physics.qiu_vo2_device import (
    QiuCircuit,
    QiuGeometry,
    QiuHysteresis,
    build_qiu_domain_masks,
    major_loop_targets,
    material_property_fields,
)
from pinnpcm.solvers.m40r_qiu_e0_repair import (
    ReferenceFieldSample,
    compare_active_transients,
    reconstruct_conservative_electric_field,
    relative_field_norms,
    run_active_transient,
    sample_vo2_field_on_fixed_grid,
)
from pinnpcm.solvers.qiu_vo2_2d_fvm import qiu_terminal_faces, solve_electrical


ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _resolve(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


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


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    records = list(rows)
    fields: list[str] = []
    for row in records:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({key: _jsonable(row.get(key)) for key in fields})


def _load_config(path: str | Path) -> dict[str, Any]:
    return dict(yaml.safe_load(_resolve(path).read_text(encoding="utf-8")))


def _frozen_files() -> list[Path]:
    fixed = [
        ROOT / "configs/gt_v1_acceptance_triangle.yaml",
        ROOT / "configs/gt_v1_acceptance_ltp_ltd.yaml",
        ROOT / "docs/gt_v1_acceptance_report.md",
        ROOT / "data/processed/gt_v1_acceptance/manifest.json",
    ]
    arrays = sorted((ROOT / "data/processed/gt_v1_acceptance").glob("**/*"))
    return sorted({path for path in [*fixed, *arrays] if path.is_file()})


def _hash_records(paths: Sequence[Path]) -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): _sha256(path)
        for path in paths
        if path.is_file()
    }


def _load_source_manifest() -> dict[str, Any]:
    return json.loads(
        _resolve("data/external/qiu_2024_thermal_neuristor/manifest.json").read_text(
            encoding="utf-8"
        )
    )


def _verify_sources() -> dict[str, str]:
    manifest = _load_source_manifest()
    hashes: dict[str, str] = {}
    for source in manifest["sources"][:2]:
        actual = _sha256(source["local_raw_path"])
        if actual != str(source["sha256"]):
            raise RuntimeError(f"Qiu source hash mismatch: {source['artifact_id']}")
        hashes[str(source["artifact_id"])] = actual
    return hashes


def _verify_old_m40(config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    old = json.loads(_resolve(config["old_m40"]["summary"]).read_text(encoding="utf-8"))
    if old["status"] != config["old_m40"]["required_status"]:
        raise RuntimeError("old M40 evidence status changed")
    if old["gate_values"]["main_qoi_mesh_change"] != float(
        config["old_m40"]["required_main_current_change"]
    ):
        raise RuntimeError("old M40 current failure value changed")
    if old["gate_values"]["peak_field_mesh_change"] != float(
        config["old_m40"]["required_field_p99_change"]
    ):
        raise RuntimeError("old M40 field failure value changed")
    hashes = {name: _sha256(name) for name in _protected_m40_paths(config)}
    return old, hashes


def _preregister(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    if _git("rev-parse", "HEAD") != str(config["base_snapshot"]):
        raise RuntimeError("M40R preregistration must start at the declared baseline")
    if _resolve(config["outputs"]["summary"]).exists():
        raise RuntimeError("M40R formal output already exists")
    source_hashes = _verify_sources()
    old_summary, old_hashes = _verify_old_m40(config)
    forensic = json.loads(
        _resolve(config["outputs"]["forensics_json"]).read_text(encoding="utf-8")
    )
    if (
        forensic.get("scientific_vote_generated") is not False
        or forensic.get("execution_class") != "non_voting_forensic"
    ):
        raise RuntimeError("M40R forensic artifact must remain non-voting")
    if forensic.get("old_m40_failure_preserved") is not True:
        raise RuntimeError("M40 protected artifacts changed during forensics")
    locked = [
        config_path.relative_to(ROOT).as_posix(),
        "src/pinnpcm/solvers/m40r_qiu_e0_repair.py",
        "scripts/audit_m40r_qiu_mesh_forensics.py",
        "scripts/run_m40r_qiu_e0_repair.py",
        "tests/test_m40r_qiu_field_reconstruction.py",
        "tests/test_m40r_qiu_mesh_convergence.py",
        "tests/test_m40r_qiu_active_transient.py",
        config["outputs"]["forensics_json"],
        config["outputs"]["forensics_csv"],
        config["outputs"]["forensics_report"],
    ]
    missing = [name for name in locked if not _resolve(name).is_file()]
    if missing:
        raise RuntimeError(f"M40R preregistration files missing: {missing}")
    payload = {
        "schema_version": "m40r_qiu_e0_preregistration_v1",
        "task_id": config["task_id"],
        "created_at_utc": _utc_now(),
        "base_snapshot": config["base_snapshot"],
        "head_before_preregistration_commit": _git("rev-parse", "HEAD"),
        "formal_execution_limit": 1,
        "formal_solver_executed": False,
        "non_voting_forensic_sha256": _sha256(config["outputs"]["forensics_json"]),
        "repair_contract": config["repair_contract"],
        "source_semantics": config["source_semantics"],
        "mesh_contract": config["mesh_forensics"],
        "active_transient_contract": config["active_transient"],
        "gate_thresholds": config["gates"],
        "locked_files": {name: _sha256(name) for name in locked},
        "old_m40_summary": {
            "status": old_summary["status"],
            "e0_all_gates_pass": old_summary["e0_all_gates_pass"],
            "main_qoi_mesh_change": old_summary["gate_values"]["main_qoi_mesh_change"],
            "peak_field_mesh_change": old_summary["gate_values"]["peak_field_mesh_change"],
        },
        "old_m40_protected_hashes": old_hashes,
        "frozen_gt_hashes": _hash_records(_frozen_files()),
        "raw_source_hashes": source_hashes,
        "forbidden_actions": [
            "M41 execution before every gate passes",
            "gamma_eff",
            "inverse",
            "PINN training",
            "parameter fitting or search",
            "public-curve digitization",
            "M38",
            "Zhang sealed 13 V access",
            "frozen-GT modification",
            "corner rounding without source evidence",
            "threshold, percentile, or exclusion-window relaxation",
        ],
    }
    _write_json(config["outputs"]["preregistration"], payload)
    return payload


def _verify_formal_lock(config: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    prereg_path = _resolve(config["outputs"]["preregistration"])
    if not prereg_path.is_file():
        raise RuntimeError("formal M40R requires a preregistration artifact")
    if _resolve(config["outputs"]["summary"]).exists():
        raise RuntimeError("formal M40R execution limit already consumed")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    if head == str(config["base_snapshot"]):
        raise RuntimeError("formal M40R requires a separate preregistration commit")
    if _git("status", "--short"):
        raise RuntimeError("formal M40R requires a clean preregistration commit")
    for group in ("locked_files", "old_m40_protected_hashes"):
        mismatches = {
            name: {"expected": expected, "actual": _sha256(name) if _resolve(name).is_file() else None}
            for name, expected in prereg[group].items()
            if not _resolve(name).is_file() or _sha256(name) != expected
        }
        if mismatches:
            raise RuntimeError(f"M40R {group} mismatch: {mismatches}")
    if _hash_records(_frozen_files()) != prereg["frozen_gt_hashes"]:
        raise RuntimeError("frozen GT changed before formal M40R")
    _verify_sources()
    return prereg, head


def _contact_area_m2(mesh: Any) -> float:
    area = 0.0
    for ix in range(mesh.shape[1]):
        for iz in range(mesh.shape[0] - 1):
            if {str(mesh.material[iz, ix]), str(mesh.material[iz + 1, ix])} == {
                "vo2",
                "ti",
            }:
                area += mesh.dx_m[ix] * mesh.depth_m
    return float(area)


def _probe_values(
    sample: ReferenceFieldSample, fractions: Sequence[Sequence[float]]
) -> dict[str, float]:
    ex_interp = RegularGridInterpolator((sample.z_m, sample.x_m), sample.ex_V_m)
    ez_interp = RegularGridInterpolator((sample.z_m, sample.x_m), sample.ez_V_m)
    values: dict[str, float] = {}
    for index, pair in enumerate(fractions):
        fx, fz = float(pair[0]), float(pair[1])
        x = float(sample.x_m[0] + fx * (sample.x_m[-1] - sample.x_m[0]))
        z = float(sample.z_m[0] + fz * (sample.z_m[-1] - sample.z_m[0]))
        point = np.asarray([[z, x]])
        values[f"probe_{index}_x_m"] = x
        values[f"probe_{index}_z_m"] = z
        values[f"probe_{index}_Ex_V_m"] = float(ex_interp(point)[0])
        values[f"probe_{index}_Ez_V_m"] = float(ez_interp(point)[0])
    return values


def _formal_mesh_refinement(
    repair: Mapping[str, Any], parent: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[int, ReferenceFieldSample]]:
    geometry = QiuGeometry.from_mapping(parent["geometry"])
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    circuit = QiuCircuit.from_mapping(parent["circuit"])
    contacts = {
        ("vo2", "ti"): float(
            parent["interfaces"]["electrical_contact_resistance_m2_ohm"]["vo2_ti"]
        )
    }
    peak = parent["verification"]["peak_field_definition"]
    x_exclusion = float(peak["x_exclusion_from_contact_edge_m"])
    z_exclusion = float(peak["z_exclusion_from_vo2_boundary_m"])
    reference = repair["mesh_forensics"]["reference_grid"]
    levels = [int(level) for level in repair["mesh_forensics"]["convergence_triplet"]]
    percentiles = [float(value) for value in repair["mesh_forensics"]["field_percentiles"]]
    rows: list[dict[str, Any]] = []
    samples: dict[int, ReferenceFieldSample] = {}
    for level in levels:
        mesh = build_qiu_domain_masks(geometry, level)
        temperature = np.full(mesh.shape, circuit.ambient_temperature_K)
        history, _ = major_loop_targets(temperature, hysteresis)
        sigma, _, _ = material_property_fields(
            mesh, temperature, history, geometry, hysteresis, parent["materials"]
        )
        terminals = qiu_terminal_faces(mesh, 1.0)
        result = solve_electrical(mesh, sigma, terminals, contacts)
        field = reconstruct_conservative_electric_field(
            mesh, result["potential_V"], sigma, terminals, contacts
        )
        sample = sample_vo2_field_on_fixed_grid(
            mesh,
            field,
            geometry,
            x_exclusion_m=x_exclusion,
            z_exclusion_m=z_exclusion,
            reference_nx=int(reference["nx"]),
            reference_nz=int(reference["nz"]),
        )
        samples[level] = sample
        vo2 = mesh.material == "vo2"
        x, z = np.meshgrid(mesh.x_centers_m, mesh.z_centers_m)
        raw_window = (
            vo2
            & (x >= geometry.electrode_overlap_m + x_exclusion)
            & (x <= geometry.device_length_m - geometry.electrode_overlap_m - x_exclusion)
            & (z >= z_exclusion)
            & (z <= geometry.vo2_thickness_m - z_exclusion)
        )
        raw_values = np.asarray(field.magnitude_cell_V_m)[raw_window]
        row: dict[str, Any] = {
            "refinement": level,
            "nx": mesh.shape[1],
            "nz": mesh.shape[0],
            "source_current_A_at_1V": float(result["terminal_currents_A"]["source"]),
            "relative_current_imbalance": float(result["relative_current_imbalance"]),
            "reconstructed_source_current_A_at_1V": float(
                field.terminal_currents_A["source"]
            ),
            "terminal_reconstruction_relative_error": abs(
                float(field.terminal_currents_A["source"])
                - float(result["terminal_currents_A"]["source"])
            )
            / max(abs(float(result["terminal_currents_A"]["source"])), 1.0e-30),
            "raw_unwindowed_field_max_V_m": float(np.nanmax(field.magnitude_cell_V_m[vo2])),
            "source_terminal_area_m2": float(
                sum(
                    mesh.dx_m[face.ix] * mesh.depth_m
                    for face in terminals
                    if face.name == "source" and face.side in {"top", "bottom"}
                )
            ),
            "vo2_ti_total_contact_area_m2": _contact_area_m2(mesh),
        }
        for percentile in percentiles:
            suffix = str(int(percentile))
            row[f"raw_grid_field_p{suffix}_V_m"] = float(
                np.percentile(raw_values, percentile)
            )
            row[f"fixed_grid_field_p{suffix}_V_m"] = float(
                np.percentile(sample.magnitude_V_m, percentile)
            )
        row.update(_probe_values(sample, repair["mesh_forensics"]["probe_points_fraction_xz"]))
        rows.append(row)
    current_convergence = _convergence(
        [float(row["source_current_A_at_1V"]) for row in rows],
        float(repair["mesh_forensics"]["safety_factor_gci"]),
    )
    fixed_p99_convergence = _convergence(
        [float(row["fixed_grid_field_p99_V_m"]) for row in rows],
        float(repair["mesh_forensics"]["safety_factor_gci"]),
    )
    medium_fine_norms = relative_field_norms(samples[levels[-2]], samples[levels[-1]])
    metrics: dict[str, Any] = {
        "mesh_levels": levels,
        "main_qoi_mesh_change": current_convergence["fine_pair_relative_change"],
        "peak_field_mesh_change": fixed_p99_convergence["fine_pair_relative_change"],
        "current_convergence": current_convergence,
        "repaired_fixed_grid_field_p99_convergence": fixed_p99_convergence,
        "medium_to_fine_fixed_grid_field_norms": medium_fine_norms,
        "maximum_mesh_current_imbalance": max(
            float(row["relative_current_imbalance"]) for row in rows
        ),
        "maximum_terminal_reconstruction_relative_error": max(
            float(row["terminal_reconstruction_relative_error"]) for row in rows
        ),
        "sharp_corner_raw_max_converged_claim_allowed": False,
        "exclusion_window_changed": False,
        "field_percentile_changed": False,
        "corner_rounding_added": False,
    }
    return rows, metrics, samples


def _interface_maps(parent: Mapping[str, Any]) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    electrical = {
        ("vo2", "ti"): float(
            parent["interfaces"]["electrical_contact_resistance_m2_ohm"]["vo2_ti"]
        )
    }
    thermal = {
        ("vo2", "ti"): float(
            parent["interfaces"]["thermal_boundary_resistance_m2K_W"]["vo2_ti"]
        ),
        ("ti", "au"): float(
            parent["interfaces"]["thermal_boundary_resistance_m2K_W"]["ti_au"]
        ),
        ("vo2", "al2o3"): float(
            parent["interfaces"]["thermal_boundary_resistance_m2K_W"]["vo2_al2o3"]
        ),
    }
    return electrical, thermal


def _run_active_pair(
    repair: Mapping[str, Any], parent: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    geometry = QiuGeometry.from_mapping(parent["geometry"])
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    circuit = QiuCircuit.from_mapping(parent["circuit"])
    electrical, thermal = _interface_maps(parent)
    active = dict(repair["active_transient"])
    controls = {**active, **dict(active["activity"])}
    kwargs = {
        "geometry": geometry,
        "hysteresis": hysteresis,
        "circuit": circuit,
        "materials": parent["materials"],
        "electrical_contacts": electrical,
        "thermal_contacts": thermal,
        "bottom_conductance_W_K": float(
            parent["interfaces"]["bottom_conductance_W_K"]
        ),
        "controls": controls,
        "maximum_steps": int(
            repair["execution_contract"]["maximum_accepted_transient_steps_per_run"]
        ),
        "maximum_reject_fraction": float(
            repair["execution_contract"]["maximum_reject_fraction"]
        ),
    }
    coarse = run_active_transient(profile=active["coarse"], **kwargs)
    fine = run_active_transient(profile=active["fine"], **kwargs)
    comparison = compare_active_transients(
        coarse,
        fine,
        ambient_temperature_K=circuit.ambient_temperature_K,
        comparison_grid_points=int(active["comparison_grid_points"]),
    )
    return coarse, fine, comparison


def _trace_payload(result: Mapping[str, Any], maximum_points: int = 2001) -> dict[str, Any]:
    time_values = np.asarray(result["time_s"])
    if time_values.size <= maximum_points:
        indices = np.arange(time_values.size)
    else:
        indices = np.unique(
            np.linspace(0, time_values.size - 1, maximum_points).round().astype(int)
        )
    trace_keys = [
        "time_s",
        "voltage_V",
        "current_A",
        "Tmean_K",
        "Tmax_K",
        "hmean",
        "joule_power_W",
        "storage_rate_W",
        "outward_heat_W",
        "energy_imbalance",
        "history_step_change",
        "switching_state_window",
    ]
    return {
        "metrics": result["metrics"],
        "trace_downsampling": {
            "original_points": int(time_values.size),
            "stored_points": int(indices.size),
            "method": "uniform_index_including_endpoints",
        },
        "trace": {
            key: np.asarray(result[key])[indices]
            for key in trace_keys
        },
    }


def _old_verifiers(parent: Mapping[str, Any]) -> tuple[dict[str, Any], Any, Mapping[str, np.ndarray]]:
    values: dict[str, Any] = {}
    values.update(legacy._manufactured_and_uniform(parent))
    values.update(legacy._layered_electrical())
    values.update(legacy._electrical_contact_jump())
    values.update(legacy._layered_thermal())
    values.update(legacy._substrate_tamper(parent))
    values.update(legacy._energy_ledgers(parent))
    nominal, fields, mesh = legacy._nominal_smoke(parent)
    values.update(nominal)
    return values, mesh, fields


def _original_gate_results(
    values: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> dict[str, bool]:
    return {
        "manufactured_electrical": float(values["manufactured_electrical_relative_l2"])
        <= float(thresholds["manufactured_electrical_relative_l2_max"]),
        "layered_electrical": float(values["layered_electrical_relative_error"])
        <= float(thresholds["layered_electrical_relative_error_max"]),
        "layered_thermal": float(values["layered_thermal_relative_error"])
        <= float(thresholds["layered_thermal_relative_error_max"]),
        "electrical_contact_jump": float(values["electrical_contact_jump_relative_error"])
        <= float(thresholds["electrical_contact_jump_relative_error_max"]),
        "thermal_interface_jump": float(values["thermal_interface_jump_relative_error"])
        <= float(thresholds["thermal_interface_jump_relative_error_max"]),
        "substrate_electrical_invariance": float(values["substrate_invariance_relative_error"])
        <= float(thresholds["substrate_invariance_relative_error_max"]),
        "substrate_leak_tamper_detection": float(values["substrate_tamper_effect_relative"])
        >= float(thresholds["substrate_tamper_effect_relative_min"]),
        "current_conservation": float(values["relative_current_imbalance"])
        <= float(thresholds["relative_current_imbalance_max"]),
        "smooth_window_energy_conservation": float(values["smooth_window_energy_imbalance"])
        <= float(thresholds["smooth_window_energy_imbalance_max"]),
        "switching_window_energy_conservation": bool(values["switching_fixture_exercised"])
        and float(values["switching_window_energy_imbalance"])
        <= float(thresholds["switching_window_energy_imbalance_max"]),
        "main_qoi_mesh_convergence": float(values["main_qoi_mesh_change"])
        <= float(thresholds["main_qoi_mesh_change_max"]),
        "peak_field_mesh_convergence": float(values["peak_field_mesh_change"])
        <= float(thresholds["peak_field_mesh_change_max"]),
        "uniform_2d_to_reduced": float(values["uniform_2d_to_reduced_error"])
        <= float(thresholds["uniform_2d_to_reduced_error_max"]),
        "nominal_qiu_startup_finite_diagnostic": bool(values["nominal_smoke_finite"])
        and float(values["nominal_max_rc_residual_A"])
        <= float(thresholds["nominal_rc_residual_A_max"]),
    }


def _transient_gate_results(
    values: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> dict[str, bool]:
    return {
        "nominal_transient_finite": bool(values["nominal_transient_finite"]),
        "nominal_duration": float(values["nominal_duration_Rload_C_multiple"])
        >= float(thresholds["nominal_duration_min_Rload_C_multiple"]),
        "nominal_reaches_Tc": float(values["nominal_Tmax_K"])
        >= float(values["critical_temperature_K"]),
        "nominal_history_active": float(values["nominal_h_range"])
        >= float(thresholds["nominal_history_range_min"]),
        "nominal_within_source_R_T_domain": float(values["nominal_Tmax_K"])
        <= float(values["source_R_T_domain_max_K"]),
        "transient_current_fine_pair": float(values["transient_current_nrmse"])
        <= float(thresholds["transient_current_nrmse_max"]),
        "transient_Tmax_fine_pair": float(values["transient_Tmax_relative_change"])
        <= float(thresholds["transient_Tmax_relative_change_max"]),
        "transient_Tmean_fine_pair": float(values["transient_Tmean_relative_change"])
        <= float(thresholds["transient_Tmean_relative_change_max"]),
        "transient_outward_heat_fine_pair": float(
            values["transient_outward_heat_relative_change"]
        )
        <= float(thresholds["transient_outward_heat_relative_change_max"]),
        "nominal_smooth_energy_conservation": float(
            values["nominal_smooth_energy_imbalance"]
        )
        <= float(thresholds["nominal_smooth_energy_imbalance_max"]),
        "nominal_switching_energy_conservation": bool(
            values["nominal_switching_window_exercised"]
        )
        and float(values["nominal_switching_energy_imbalance"])
        <= float(thresholds["nominal_switching_energy_imbalance_max"]),
    }


def _plot_mesh(
    repair: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
) -> None:
    target = _resolve(repair["outputs"]["mesh_figure"])
    target.parent.mkdir(parents=True, exist_ok=True)
    levels = np.asarray([row["refinement"] for row in rows], dtype=float)
    currents = np.asarray([row["source_current_A_at_1V"] for row in rows])
    p99 = np.asarray([row["fixed_grid_field_p99_V_m"] for row in rows])
    raw_p99 = np.asarray([row["raw_grid_field_p99_V_m"] for row in rows])
    raw_max = np.asarray([row["raw_unwindowed_field_max_V_m"] for row in rows])
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 3.8), constrained_layout=True)
    axes[0].plot(levels, currents * 1.0e6, "o-")
    axes[0].set(xlabel="refinement", ylabel="source current at 1 V (uA)")
    axes[0].set_title(
        f"fine change={float(metrics['main_qoi_mesh_change']):.3%}"
    )
    axes[1].plot(levels, p99 * 1.0e-6, "o-", label="fixed-grid repaired p99")
    axes[1].plot(levels, raw_p99 * 1.0e-6, "s--", label="raw-grid p99 diagnostic")
    axes[1].set(xlabel="refinement", ylabel="field (MV/m)")
    axes[1].legend(fontsize=8)
    axes[1].set_title(
        f"fine change={float(metrics['peak_field_mesh_change']):.3%}"
    )
    axes[2].plot(levels, raw_max * 1.0e-6, "o-", color="tab:red")
    axes[2].set(xlabel="refinement", ylabel="unwindowed max (MV/m)")
    axes[2].set_title("sharp-corner diagnostic; no convergence claim")
    fig.suptitle("M40R conservative mesh and field audit (solver-generated)")
    fig.savefig(target, dpi=180)
    plt.close(fig)


def _plot_transient(
    repair: Mapping[str, Any], coarse: Mapping[str, Any], fine: Mapping[str, Any]
) -> None:
    target = _resolve(repair["outputs"]["transient_figure"])
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.0), constrained_layout=True)
    for name, result, style in (("coarse", coarse, "--"), ("fine", fine, "-")):
        t = np.asarray(result["time_s"]) * 1.0e6
        axes[0, 0].plot(t, result["voltage_V"], style, label=f"V1 {name}")
        current_axis = axes[0, 0].twinx() if name == "coarse" else None
        if current_axis is not None:
            current_axis.plot(t, np.asarray(result["current_A"]) * 1.0e3, ":", color="tab:red", alpha=0.45)
            current_axis.set_ylabel("I coarse (mA)", color="tab:red")
        axes[0, 1].plot(t, result["Tmean_K"], style, label=f"Tmean {name}")
        axes[0, 1].plot(t, result["Tmax_K"], style, label=f"Tmax {name}")
        axes[1, 0].plot(t, result["hmean"], style, label=name)
    t_fine = np.asarray(fine["time_s"]) * 1.0e6
    axes[1, 1].plot(t_fine, fine["joule_power_W"], label="Joule")
    axes[1, 1].plot(t_fine, fine["storage_rate_W"], label="storage")
    axes[1, 1].plot(t_fine, fine["outward_heat_W"], label="outward")
    axes[0, 0].set(xlabel="time (us)", ylabel="V1 (V)")
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].set(xlabel="time (us)", ylabel="temperature (K)")
    axes[0, 1].legend(fontsize=8)
    axes[1, 0].set(xlabel="time (us)", ylabel="mean history h")
    axes[1, 0].legend(fontsize=8)
    axes[1, 1].set(xlabel="time (us)", ylabel="power (W)")
    axes[1, 1].legend(fontsize=8)
    fig.suptitle("M40R Qiu source-composed active transient (not measured)")
    fig.savefig(target, dpi=180)
    plt.close(fig)


def _plot_transient_failure(repair: Mapping[str, Any], error: str) -> None:
    target = _resolve(repair["outputs"]["transient_figure"])
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10.0, 4.0), constrained_layout=True)
    ax.axis("off")
    ax.text(
        0.02,
        0.95,
        "M40R active transient failed closed",
        va="top",
        fontsize=15,
        weight="bold",
    )
    ax.text(0.02, 0.78, error, va="top", wrap=True, family="monospace")
    ax.text(
        0.02,
        0.25,
        "No parameter fitting, threshold relaxation, or rescue rerun was performed.",
        va="top",
    )
    fig.savefig(target, dpi=180)
    plt.close(fig)


ORIGINAL_GATE_VALUE_KEYS = {
    "manufactured_electrical": "manufactured_electrical_relative_l2",
    "layered_electrical": "layered_electrical_relative_error",
    "layered_thermal": "layered_thermal_relative_error",
    "electrical_contact_jump": "electrical_contact_jump_relative_error",
    "thermal_interface_jump": "thermal_interface_jump_relative_error",
    "substrate_electrical_invariance": "substrate_invariance_relative_error",
    "substrate_leak_tamper_detection": "substrate_tamper_effect_relative",
    "current_conservation": "relative_current_imbalance",
    "smooth_window_energy_conservation": "smooth_window_energy_imbalance",
    "switching_window_energy_conservation": "switching_window_energy_imbalance",
    "main_qoi_mesh_convergence": "main_qoi_mesh_change",
    "peak_field_mesh_convergence": "peak_field_mesh_change",
    "uniform_2d_to_reduced": "uniform_2d_to_reduced_error",
    "nominal_qiu_startup_finite_diagnostic": "nominal_max_rc_residual_A",
}

TRANSIENT_GATE_VALUE_KEYS = {
    "nominal_transient_finite": "nominal_transient_finite",
    "nominal_duration": "nominal_duration_Rload_C_multiple",
    "nominal_reaches_Tc": "nominal_Tmax_K",
    "nominal_history_active": "nominal_h_range",
    "nominal_within_source_R_T_domain": "nominal_Tmax_K",
    "transient_current_fine_pair": "transient_current_nrmse",
    "transient_Tmax_fine_pair": "transient_Tmax_relative_change",
    "transient_Tmean_fine_pair": "transient_Tmean_relative_change",
    "transient_outward_heat_fine_pair": "transient_outward_heat_relative_change",
    "nominal_smooth_energy_conservation": "nominal_smooth_energy_imbalance",
    "nominal_switching_energy_conservation": "nominal_switching_energy_imbalance",
}


def _write_report(repair: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    lines = [
        "# M40R Qiu E0 Mesh and Active-Transient Repair Results",
        "",
        f"- Task: `{summary['task_id']}`",
        f"- Base snapshot: `{summary['base_snapshot']}`",
        f"- Preregistration commit: `{summary['preregistration_commit']}`",
        f"- Formal attempt: `{summary['formal_execution_attempt']}` of `1`",
        f"- Status: `{summary['status']}`",
        f"- Original numerical E0 gates pass: `{summary['original_numeric_e0_all_pass']}`",
        f"- New active-transient gates pass: `{summary['active_transient_all_pass']}`",
        f"- M41 authorized: `{summary['m41_conservative_reduction_authorized']}`",
        f"- Frozen GT unchanged: `{summary['frozen_gt_unchanged']}`",
        "",
        "## Non-voting forensic conclusion",
        "",
        summary["forensic_root_cause"],
        "",
        "The old M40 formal result and protected files remain byte-for-byte locked.",
        "The old sharp-corner failure remains a valid diagnostic; no rounding,",
        "exclusion-window enlargement, percentile reduction, fitting, or threshold",
        "relaxation was used.",
        "",
        "## Repaired original E0 gates",
        "",
        "| Gate | Value | Pass |",
        "| --- | ---: | :---: |",
    ]
    for name, passed in summary["original_gate_results"].items():
        value = summary["gate_values"][ORIGINAL_GATE_VALUE_KEYS[name]]
        lines.append(f"| {name} | {value:.9e} | {passed} |")
    lines.extend(
        [
            "",
            "## New active-transient gates",
            "",
            "| Gate | Value | Pass |",
            "| --- | ---: | :---: |",
        ]
    )
    for name, passed in summary["transient_gate_results"].items():
        value = summary["gate_values"][TRANSIENT_GATE_VALUE_KEYS[name]]
        if isinstance(value, bool):
            rendered = str(value)
        elif value is None:
            rendered = "not available"
        else:
            rendered = f"{float(value):.9e}"
        lines.append(f"| {name} | {rendered} | {passed} |")
    old = summary["old_m40_preserved_evidence"]
    lines.extend(
        [
            "",
            "## Preserved old M40 boundary",
            "",
            f"- Status: `{old['status']}`",
            f"- Old main-current mesh change: `{old['main_qoi_mesh_change']:.9e}`",
            f"- Old fixed-window field-p99 mesh change: `{old['peak_field_mesh_change']:.9e}`",
            f"- Old M41 authorization: `{old['m41_conservative_reduction_authorized']}`",
            "",
            "## Nominal transient interpretation",
            "",
            f"- Activity class: `{summary['nominal_transient'].get('activity_class')}`",
            f"- Event count: `{summary['nominal_transient'].get('event_count')}`",
            f"- Median period: `{summary['nominal_transient'].get('median_period_s')}` s",
            f"- Local 2D sensible heat capacity: `{summary['nominal_transient'].get('local_2d_heat_capacity_J_K')}` J/K",
            f"- Local bottom-conductance time constant: `{summary['nominal_transient'].get('local_2d_bottom_time_constant_s')}` s",
            "",
            "The active run is solver-generated under a source-composed illustrative",
            "protocol. It is not a measured trace, calibration, exact Qiu source-model",
            "reproduction, or experimental validation. The energy ledger covers sensible",
            "heat, Joule input, and bottom outflow only; it is not a latent-heat or full",
            "phase-change enthalpy balance.",
            "",
            "## Repository validation",
            "",
            f"- Command: `{summary['repository_validation']['command']}`",
            f"- Passed: `{summary['repository_validation']['passed']}`",
            f"- Failed: `{summary['repository_validation']['failed']}`",
            f"- Skipped: `{summary['repository_validation']['skipped']}`",
            f"- Validation complete: `{summary['repository_validation']['complete']}`",
            "",
            "## Claim decision",
            "",
            summary["allowed_claim"],
            "",
            "Forbidden: " + "; ".join(summary["forbidden_claims"]),
            "",
            f"Return to manuscript fallback: `{summary['return_to_manuscript_fallback']}`.",
        ]
    )
    target = _resolve(repair["outputs"]["report"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _formal(repair: Mapping[str, Any]) -> dict[str, Any]:
    prereg, prereg_commit = _verify_formal_lock(repair)
    parent = _load_config(repair["parent_m40_config"])
    old_summary, old_hashes_before = _verify_old_m40(repair)
    started = time.perf_counter()
    original_values, _, _ = _old_verifiers(parent)
    mesh_rows, mesh_metrics, _ = _formal_mesh_refinement(repair, parent)
    values: dict[str, Any] = {**original_values, **mesh_metrics}
    active_error: str | None = None
    coarse: dict[str, Any] | None = None
    fine: dict[str, Any] | None = None
    comparison: dict[str, float] | None = None
    try:
        coarse, fine, comparison = _run_active_pair(repair, parent)
        coarse_metrics = dict(coarse["metrics"])
        fine_metrics = dict(fine["metrics"])
        values.update(
            {
                "nominal_transient_finite": bool(
                    coarse_metrics["finite"] and fine_metrics["finite"]
                ),
                "nominal_duration_Rload_C_multiple": min(
                    float(coarse_metrics["duration_Rload_C_multiple"]),
                    float(fine_metrics["duration_Rload_C_multiple"]),
                ),
                "nominal_Tmax_K": float(fine_metrics["Tmax_K"]),
                "critical_temperature_K": float(parent["hysteresis"]["critical_temperature_K"]),
                "source_R_T_domain_max_K": float(
                    repair["active_transient"]["source_R_T_domain_max_K"]
                ),
                "nominal_h_range": float(fine_metrics["h_range"]),
                "transient_current_nrmse": float(
                    comparison["current_raw_time_rms_nrmse"]
                ),
                "transient_Tmax_relative_change": float(
                    comparison["Tmax_rise_relative_change"]
                ),
                "transient_Tmean_relative_change": float(
                    comparison["Tmean_rise_relative_change"]
                ),
                "transient_outward_heat_relative_change": float(
                    comparison["cumulative_outward_heat_relative_change"]
                ),
                "nominal_smooth_energy_imbalance": float(
                    fine_metrics["nominal_smooth_max_energy_imbalance"]
                ),
                "nominal_switching_energy_imbalance": (
                    float(fine_metrics["nominal_switching_max_energy_imbalance"])
                    if fine_metrics["nominal_switching_max_energy_imbalance"] is not None
                    else 1.0e300
                ),
                "nominal_switching_window_exercised": bool(
                    fine_metrics["switching_window_exercised"]
                ),
            }
        )
        values["relative_current_imbalance"] = max(
            float(values["manufactured_current_imbalance"]),
            float(values["layered_current_imbalance"]),
            float(values["maximum_mesh_current_imbalance"]),
            float(values["nominal_max_current_imbalance"]),
            float(coarse_metrics["maximum_current_imbalance"]),
            float(fine_metrics["maximum_current_imbalance"]),
        )
        active_payload = {
            "schema_version": "m40r_qiu_active_transient_v1",
            "semantics": "solver_generated_source_composed_illustrative_protocol",
            "coarse": _trace_payload(coarse),
            "fine": _trace_payload(fine),
            "fine_pair_comparison": comparison,
        }
        _plot_transient(repair, coarse, fine)
    except Exception as exc:  # formal failure must still produce an auditable artifact
        active_error = f"{type(exc).__name__}: {exc}"
        values.update(
            {
                "nominal_transient_finite": False,
                "nominal_duration_Rload_C_multiple": 0.0,
                "nominal_Tmax_K": float(parent["circuit"]["ambient_temperature_K"]),
                "critical_temperature_K": float(parent["hysteresis"]["critical_temperature_K"]),
                "source_R_T_domain_max_K": float(
                    repair["active_transient"]["source_R_T_domain_max_K"]
                ),
                "nominal_h_range": 0.0,
                "transient_current_nrmse": 1.0e300,
                "transient_Tmax_relative_change": 1.0e300,
                "transient_Tmean_relative_change": 1.0e300,
                "transient_outward_heat_relative_change": 1.0e300,
                "nominal_smooth_energy_imbalance": 1.0e300,
                "nominal_switching_energy_imbalance": 1.0e300,
                "nominal_switching_window_exercised": False,
            }
        )
        values["relative_current_imbalance"] = max(
            float(values["manufactured_current_imbalance"]),
            float(values["layered_current_imbalance"]),
            float(values["maximum_mesh_current_imbalance"]),
            float(values["nominal_max_current_imbalance"]),
        )
        active_payload = {
            "schema_version": "m40r_qiu_active_transient_v1",
            "semantics": "formal_run_failed_closed",
            "error": active_error,
        }
        _plot_transient_failure(repair, active_error)
    thresholds = {**dict(parent["gates"]), **dict(repair["gates"])}
    original_gates = _original_gate_results(values, thresholds)
    transient_gates = _transient_gate_results(values, thresholds)
    frozen_now = _hash_records(_frozen_files())
    frozen_unchanged = frozen_now == prereg["frozen_gt_hashes"]
    old_summary_now, old_hashes_after = _verify_old_m40(repair)
    old_unchanged = old_hashes_after == old_hashes_before == prereg["old_m40_protected_hashes"]
    original_all = bool(all(original_gates.values()))
    transient_all = bool(all(transient_gates.values()))
    elapsed = time.perf_counter() - started
    wall_clock_pass = elapsed <= float(
        repair["execution_contract"]["maximum_wall_clock_s"]
    )
    all_pass = bool(
        original_all and transient_all and frozen_unchanged and old_unchanged and wall_clock_pass
    )
    status = "qualified_supported" if all_pass else "failed_but_informative"
    if all_pass:
        allowed_claim = (
            "Qualified source-traceable Qiu-inspired conservative x-z E0 solver "
            "verification, including a source-domain-bounded active transient, under "
            "reported and explicitly labeled prior quantities."
        )
    elif original_all:
        allowed_claim = (
            "The repaired conservative x-z solver retains implementation-level numerical "
            "evidence, but the active-transient claim failed and M41 is not authorized."
        )
    else:
        allowed_claim = (
            "No positive M40R solver claim; the second failed numerical E0 boundary is "
            "retained and M40 rescue is permanently stopped."
        )
    fine_metrics = dict(fine["metrics"]) if fine is not None else {}
    summary = {
        "schema_version": "m40r_qiu_e0_summary_v1",
        "task_id": repair["task_id"],
        "base_snapshot": repair["base_snapshot"],
        "preregistration_commit": prereg_commit,
        "formal_execution_attempt": 1,
        "formal_completed_at_utc": _utc_now(),
        "wall_clock_s": elapsed,
        "wall_clock_budget_pass": wall_clock_pass,
        "machine_summary": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "forensic_root_cause": (
            "The old field estimator did not reconstruct conservative face fluxes, but "
            "the old p99 failure was dominated by changing discrete quantiles around the "
            "ideal top-contact sharp-corner field and first-order coplanar-contact current "
            "crowding. The repair uses face-current J/sigma on one fixed physical grid; "
            "the unwindowed sharp-corner maximum remains non-convergent and non-voting."
        ),
        "gate_thresholds": thresholds,
        "gate_values": values,
        "original_gate_results": original_gates,
        "transient_gate_results": transient_gates,
        "original_numeric_e0_all_pass": original_all,
        "active_transient_all_pass": transient_all,
        "frozen_gt_unchanged": frozen_unchanged,
        "old_m40_byte_for_byte_unchanged": old_unchanged,
        "formal_all_gates_pass": all_pass,
        "m41_conservative_reduction_authorized": all_pass,
        "permanent_m40_rescue_stop": not original_all,
        "return_to_manuscript_fallback": not all_pass,
        "status": status,
        "active_transient_error": active_error,
        "nominal_transient": fine_metrics,
        "old_m40_preserved_evidence": {
            "status": old_summary_now["status"],
            "e0_all_gates_pass": old_summary_now["e0_all_gates_pass"],
            "main_qoi_mesh_change": old_summary_now["gate_values"]["main_qoi_mesh_change"],
            "peak_field_mesh_change": old_summary_now["gate_values"]["peak_field_mesh_change"],
            "m41_conservative_reduction_authorized": old_summary_now[
                "m41_conservative_reduction_authorized"
            ],
            "protected_hashes": old_hashes_after,
        },
        "source_semantics": repair["source_semantics"],
        "source_hashes": _verify_sources(),
        "repository_validation": {
            "command": ".\\.venv\\Scripts\\python.exe -m pytest -q",
            "passed": None,
            "failed": None,
            "skipped": None,
            "complete": False,
        },
        "allowed_claim": allowed_claim,
        "forbidden_claims": [
            "Qiu real-device calibrated",
            "exact Qiu source-model reproduction",
            "experimental validation",
            "measured active-transient reproduction",
            "complete phase-change enthalpy conservation",
            "converged ideal sharp-corner maximum field",
            "inverse identification",
            "PINN training or sensitivity fidelity",
            "gamma_eff relation",
            "full 2D hidden-field recovery",
        ],
        "forbidden_actions": prereg["forbidden_actions"],
        "outputs": repair["outputs"],
    }
    _write_csv(repair["outputs"]["mesh_convergence"], mesh_rows)
    _write_json(repair["outputs"]["active_transient"], active_payload)
    _plot_mesh(repair, mesh_rows, mesh_metrics)
    _write_json(repair["outputs"]["summary"], summary)
    _write_report(repair, summary)
    return summary


def _record_validation(
    repair: Mapping[str, Any], *, passed: int, failed: int, skipped: int, duration_s: float
) -> dict[str, Any]:
    summary_path = _resolve(repair["outputs"]["summary"])
    if not summary_path.is_file():
        raise RuntimeError("validation recording requires the formal summary")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["repository_validation"]["complete"]:
        raise RuntimeError("repository validation has already been recorded")
    validation_pass = failed == 0
    summary["repository_validation"] = {
        "command": ".\\.venv\\Scripts\\python.exe -m pytest -q",
        "passed": int(passed),
        "failed": int(failed),
        "skipped": int(skipped),
        "duration_s": float(duration_s),
        "complete": True,
        "pass": validation_pass,
    }
    if not validation_pass:
        summary["m41_conservative_reduction_authorized"] = False
        summary["return_to_manuscript_fallback"] = True
        summary["status"] = "failed_but_informative"
        summary["allowed_claim"] = (
            "Repository validation failed; no positive M40R claim or M41 authorization."
        )
    _write_json(summary_path, summary)
    _write_report(repair, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--mode", choices=("preregister", "formal", "record-validation"), required=True
    )
    parser.add_argument("--passed", type=int)
    parser.add_argument("--failed", type=int)
    parser.add_argument("--skipped", type=int)
    parser.add_argument("--duration-s", type=float)
    args = parser.parse_args()
    config_path = _resolve(args.config)
    repair = _load_config(config_path)
    if args.mode == "preregister":
        result = _preregister(config_path, repair)
    elif args.mode == "formal":
        result = _formal(repair)
    else:
        required = (args.passed, args.failed, args.skipped, args.duration_s)
        if any(value is None for value in required):
            parser.error("record-validation requires passed, failed, skipped, and duration")
        result = _record_validation(
            repair,
            passed=int(args.passed),
            failed=int(args.failed),
            skipped=int(args.skipped),
            duration_s=float(args.duration_s),
        )
    print(json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

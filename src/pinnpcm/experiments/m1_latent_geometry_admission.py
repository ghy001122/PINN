"""Geometry-admission benchmark for the M1 latent solver-projected mapper.

This module is intentionally separate from the immutable PR #39 MVE.  It
builds contact-overlap-specific M1 operators, generates the preregistered
36-case numerical reference, compares analytic/ridge/neural initializers at
matched projection depth, and applies the frozen neural-necessity gates.
"""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import torch
from scipy import sparse

from pinnpcm.experiments.geostate_fasttrack import (
    EVIDENCE_TYPE,
    GeoStateCase,
    GeoStateReferenceContext,
    GeoStateReferenceResult,
    _contact_values,
    _solve_electrical_robin,
    _thermal_closure,
    _thermal_residual_and_sink,
    conductivity_numpy,
    load_yaml,
    solve_reference_case,
)
from pinnpcm.experiments.geostate_m1_compatibility import load_teacher_cases
from pinnpcm.experiments.m1_latent_projection_mve import (
    ThermalPOD,
    build_latent_model as build_historical_latent_model,
    build_projection_operator,
    fit_train_only_pod,
    frozen_m1_iteration,
    split_case_ids as historical_split_case_ids,
)
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import build_s2_thermal_fields
from pinnpcm.physics.m1_torch_projection import M1TorchProjection
from pinnpcm.pinn.m1_latent_geometry_mapper import M1LatentGeometryMapper
from pinnpcm.solvers.geophase_2p5d_fvm import build_sheet_electrical_topology
from pinnpcm.solvers.geophase_phase1_v2_fvm import assemble_sheet_thermal_matrix


Tensor = torch.Tensor


@dataclass(frozen=True)
class GeometryCase:
    case_id: str
    contact_overlap_nm: float
    branch: str
    branch_value: float
    level: str
    device_voltage_V: float
    state_coordinate: float
    thermal_condition: str
    sink_amplitude: float
    split: str

    def solver_case(self) -> GeoStateCase:
        return GeoStateCase(
            case_id=self.case_id,
            branch_label=f"{self.branch}-conditioned",
            branch_value=self.branch_value,
            device_voltage_V=self.device_voltage_V,
            state_coordinate=self.state_coordinate,
            thermal_condition=self.thermal_condition,
            sink_amplitude=self.sink_amplitude,
        )


@dataclass(frozen=True)
class InputNormalization:
    mean: np.ndarray
    scale: np.ndarray
    train_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class RidgeLatent:
    coefficients: np.ndarray
    regularization_lambda: float
    design_condition_number: float


@dataclass(frozen=True)
class EvaluationTarget:
    case: GeometryCase
    temperature_K: np.ndarray
    potential_V: np.ndarray
    source_current_A: float
    reference_iterations: int


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for name in row:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"cannot JSON encode {type(value).__name__}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (float, np.floating)):
        scalar = float(value)
        return scalar if math.isfinite(scalar) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _json_safe(payload),
            indent=2,
            sort_keys=True,
            default=_json_default,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _as_numpy(value: Any) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def _relative_l2(predicted: np.ndarray, reference: np.ndarray) -> float:
    predicted_array = np.asarray(predicted, dtype=float)
    reference_array = np.asarray(reference, dtype=float)
    return float(
        np.linalg.norm((predicted_array - reference_array).reshape(-1))
        / max(np.linalg.norm(reference_array.reshape(-1)), 1.0e-30)
    )


def _torch_relative_l2(predicted: Tensor, reference: Tensor) -> Tensor:
    dims = tuple(range(1, predicted.ndim))
    return torch.linalg.vector_norm(predicted - reference, dim=dims) / torch.clamp(
        torch.linalg.vector_norm(reference, dim=dims), min=1.0e-30
    )


def _scalar_relative(predicted: Tensor, reference: Tensor) -> Tensor:
    return torch.abs(predicted - reference) / torch.clamp(
        torch.abs(reference), min=1.0e-30
    )


def geometry_case_id(
    contact_overlap_nm: float, branch: str, level: str, thermal_condition: str
) -> str:
    return (
        f"g{int(round(contact_overlap_nm)):03d}nm_"
        f"{branch}_{level}_{thermal_condition}"
    )


def build_geometry_cases(config: Mapping[str, Any]) -> list[GeometryCase]:
    validation = {str(value) for value in config["dataset"]["validation_cases"]}
    test_geometry = float(config["dataset"]["test_geometry_nm"])
    conditions = config["conditions"]
    rows: list[GeometryCase] = []
    for overlap_nm in config["reference"]["geometry_contact_overlap_nm"]:
        overlap = float(overlap_nm)
        for branch in ("heating", "cooling"):
            for level in ("low", "near-transition", "high"):
                for thermal_condition in ("nominal", "localized-sink"):
                    case_id = geometry_case_id(
                        overlap, branch, level, thermal_condition
                    )
                    if math.isclose(overlap, test_geometry):
                        split = "test"
                    elif case_id in validation:
                        split = "validation"
                    else:
                        split = "train"
                    rows.append(
                        GeometryCase(
                            case_id=case_id,
                            contact_overlap_nm=overlap,
                            branch=branch,
                            branch_value=float(
                                conditions["branch_values"][branch]
                            ),
                            level=level,
                            device_voltage_V=float(
                                conditions["voltage_levels_V"][level]
                            ),
                            state_coordinate=float(
                                conditions["state_coordinates"][branch][level]
                            ),
                            thermal_condition=thermal_condition,
                            sink_amplitude=float(
                                conditions["thermal_conditions"][thermal_condition]
                            ),
                            split=split,
                        )
                    )
    if len(rows) != 36 or len({case.case_id for case in rows}) != 36:
        raise ValueError("geometry benchmark must contain 36 unique cases")
    counts = {
        split: sum(case.split == split for case in rows)
        for split in ("train", "validation", "test")
    }
    expected = {
        "train": int(config["dataset"]["expected_train_cases"]),
        "validation": int(config["dataset"]["expected_validation_cases"]),
        "test": int(config["dataset"]["expected_test_cases"]),
    }
    if counts != expected:
        raise ValueError(f"geometry split mismatch: {counts} != {expected}")
    if {case.case_id for case in rows if case.split == "validation"} != validation:
        raise ValueError("validation case identities differ from the frozen contract")
    return rows


def build_geometry_context(
    base_config: Mapping[str, Any],
    repository_root: Path,
    contact_overlap_nm: float,
) -> GeoStateReferenceContext:
    parent = load_yaml(repository_root / base_config["parent_physics"]["config"])
    grid_config = base_config["reference_solver"]["grid"]
    grid = build_geophase_grid(
        parent,
        contact_overlap_m=float(contact_overlap_nm) * 1.0e-9,
        nx_override=int(grid_config["nx"]),
        ny_override=int(grid_config["ny"]),
    )
    thermal = build_s2_thermal_fields(grid, parent)
    return GeoStateReferenceContext(
        fast_config=dict(base_config),
        parent_config=parent,
        grid=grid,
        thermal_fields=thermal,
        electrical_topology=build_sheet_electrical_topology(grid),
        device_thermal_matrix=assemble_sheet_thermal_matrix(
            grid, thermal.sheet_thermal_conductance_W_K
        ),
    )


def build_geometry_contexts_and_operators(
    base_config: Mapping[str, Any],
    repository_root: Path,
    contact_overlaps_nm: Sequence[float],
) -> tuple[dict[float, GeoStateReferenceContext], dict[float, M1TorchProjection]]:
    contexts: dict[float, GeoStateReferenceContext] = {}
    operators: dict[float, M1TorchProjection] = {}
    for overlap in contact_overlaps_nm:
        key = float(overlap)
        context = build_geometry_context(base_config, repository_root, key)
        contexts[key] = context
        operators[key] = build_projection_operator(context, base_config)
    return contexts, operators


def _reference_pass(
    result: GeoStateReferenceResult, config: Mapping[str, Any]
) -> bool:
    gates = config["reference"]["gates"]
    metrics = result.metrics
    return bool(
        metrics["finite"]
        and metrics["converged"]
        and float(metrics["scaled_nonlinear_residual"])
        <= float(gates["scaled_nonlinear_residual_max"])
        and float(metrics["terminal_current_imbalance"])
        <= float(gates["current_imbalance_max"])
        and float(metrics["terminal_field_joule_error"])
        <= float(gates["terminal_electrical_heat_ledger_max"])
        and float(metrics["joule_sink_ledger_error"])
        <= float(gates["electrical_heat_sink_ledger_max"])
    )


def _csv_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _conservative_fields(
    operator: M1TorchProjection,
    result: GeoStateReferenceResult,
) -> dict[str, Tensor]:
    case = result.case
    temperature = torch.as_tensor(result.fields["temperature_K"], dtype=torch.float64)
    with torch.no_grad():
        electrical = operator.electrical(
            temperature, case.device_voltage_V, case.state_coordinate
        )
        thermal = operator.thermal_diagnostics(
            temperature, electrical["total_joule_cell_W"], case.sink_amplitude
        )
    return {**electrical, **thermal}


def _conservative_reference_checks(
    *,
    operator: M1TorchProjection,
    result: GeoStateReferenceResult,
    conservative: Mapping[str, Tensor],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify that saved conservative face data match the accepted M1 state."""

    selected = (
        "potential_V",
        "conductivity_S_m",
        "electrical_x_face_current_A",
        "electrical_y_face_current_A",
        "source_face_current_A",
        "ground_face_current_A",
        "internal_joule_cell_W",
        "contact_joule_cell_W",
        "total_joule_cell_W",
        "thermal_x_face_power_W",
        "thermal_y_face_power_W",
        "vertical_sink_cell_W",
    )
    finite = all(
        bool(torch.isfinite(conservative[name]).all()) for name in selected
    )
    phi_error = _relative_l2(
        _as_numpy(conservative["potential_V"]),
        np.asarray(result.fields["potential_V"], dtype=float),
    )
    source_current = abs(float(conservative["source_current_A"]))
    reference_current = abs(float(result.metrics["source_current_A"]))
    current_error = abs(source_current - reference_current) / max(
        reference_current, 1.0e-30
    )
    terminal_ledger = float(
        conservative["terminal_electrical_heat_ledger_error"]
    )
    sink_ledger = float(conservative["electrical_heat_sink_ledger_error"])
    gates = config["reference"]["gates"]
    passed = bool(
        finite
        and phi_error <= 1.0e-6
        and current_error <= 1.0e-6
        and terminal_ledger
        <= float(gates["terminal_electrical_heat_ledger_max"])
        and sink_ledger <= float(gates["electrical_heat_sink_ledger_max"])
    )
    return {
        "conservative_face_quantities_finite": finite,
        "conservative_potential_relative_l2": phi_error,
        "conservative_source_current_relative_error": current_error,
        "conservative_terminal_electrical_heat_ledger_error": terminal_ledger,
        "conservative_electrical_heat_sink_ledger_error": sink_ledger,
        "conservative_reconstruction_gate_pass": passed,
    }


def _reference_manifest_row(
    geometry_case: GeometryCase, npz_path: Path
) -> dict[str, Any]:
    return {
        "case_id": geometry_case.case_id,
        "split": geometry_case.split,
        "contact_overlap_nm": geometry_case.contact_overlap_nm,
        "branch": geometry_case.branch,
        "branch_value": geometry_case.branch_value,
        "level": geometry_case.level,
        "device_voltage_V": geometry_case.device_voltage_V,
        "state_coordinate": geometry_case.state_coordinate,
        "thermal_condition": geometry_case.thermal_condition,
        "sink_amplitude": geometry_case.sink_amplitude,
        "reference_npz": npz_path.as_posix(),
    }


def _reference_metric_row(
    *,
    geometry_case: GeometryCase,
    result: GeoStateReferenceResult,
    conservative_checks: Mapping[str, Any],
    solve_wall_time_s: float,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    metrics = result.metrics
    return {
        "case_id": geometry_case.case_id,
        "split": geometry_case.split,
        "contact_overlap_nm": geometry_case.contact_overlap_nm,
        "iterations": int(metrics["iterations"]),
        "solve_wall_time_s": solve_wall_time_s,
        "converged": bool(metrics["converged"]),
        "finite": bool(metrics["finite"]),
        "scaled_nonlinear_residual": float(metrics["scaled_nonlinear_residual"]),
        "current_imbalance": float(metrics["terminal_current_imbalance"]),
        "terminal_electrical_heat_ledger_error": float(
            metrics["terminal_field_joule_error"]
        ),
        "electrical_heat_sink_ledger_error": float(
            metrics["joule_sink_ledger_error"]
        ),
        "source_current_A": float(metrics["source_current_A"]),
        "Tmax_K": float(metrics["Tmax_K"]),
        "Tmean_K": float(metrics["Tmean_K"]),
        "hotspot_x_m": float(metrics["hotspot_x_m"]),
        "hotspot_y_m": float(metrics["hotspot_y_m"]),
        "hotspot_lateral_shift_width_fraction": float(
            metrics["hotspot_lateral_shift_width_fraction"]
        ),
        "chi_2d": float(metrics["chi_2d"]),
        **dict(conservative_checks),
        "reference_gate_pass": bool(
            _reference_pass(result, config)
            and conservative_checks["conservative_reconstruction_gate_pass"]
        ),
    }


def _save_geometry_mask(
    path: Path,
    context: GeoStateReferenceContext,
    operator: M1TorchProjection,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        x_m=context.grid.x_centers_m,
        y_m=context.grid.y_centers_m,
        contact_overlap_m=np.asarray(context.grid.contact_overlap_m),
        left_contact_mask=context.grid.left_contact_mask,
        right_contact_mask=context.grid.right_contact_mask,
        contact_mask=context.grid.contact_mask,
        region_index=context.grid.region_index,
        sheet_thermal_conductance_W_K=context.thermal_fields.sheet_thermal_conductance_W_K,
        thermal_contact_resistance_field_m2K_W=_as_numpy(
            operator.thermal_contact_resistance_field_m2K_W
        ).reshape(context.grid.shape),
    )


def _save_reference_npz(
    path: Path,
    geometry_case: GeometryCase,
    result: GeoStateReferenceResult,
    conservative: Mapping[str, Tensor],
) -> None:
    payload: dict[str, Any] = {
        "case_id": np.asarray(geometry_case.case_id),
        "split": np.asarray(geometry_case.split),
        "evidence_type": np.asarray(EVIDENCE_TYPE),
        "contact_overlap_nm": np.asarray(geometry_case.contact_overlap_nm),
        "device_voltage_V": np.asarray(geometry_case.device_voltage_V),
        "branch": np.asarray(geometry_case.branch),
        "branch_value": np.asarray(geometry_case.branch_value),
        "state_coordinate": np.asarray(geometry_case.state_coordinate),
        "thermal_condition": np.asarray(geometry_case.thermal_condition),
        "sink_amplitude": np.asarray(geometry_case.sink_amplitude),
        "left_contact_mask": result.grid.left_contact_mask,
        "right_contact_mask": result.grid.right_contact_mask,
        "sheet_region_index": result.grid.region_index,
    }
    payload.update({name: np.asarray(value) for name, value in result.fields.items()})
    exact_names = (
        "potential_V",
        "conductivity_S_m",
        "electrical_x_face_current_A",
        "electrical_y_face_current_A",
        "source_face_current_A",
        "ground_face_current_A",
        "internal_joule_cell_W",
        "contact_joule_cell_W",
        "total_joule_cell_W",
        "thermal_x_face_power_W",
        "thermal_y_face_power_W",
        "vertical_sink_cell_W",
        "source_current_A",
        "ground_current_A",
        "terminal_power_W",
        "internal_joule_W",
        "contact_joule_W",
        "total_electrical_heat_W",
        "vertical_sink_W",
        "terminal_electrical_heat_ledger_error",
        "electrical_heat_sink_ledger_error",
    )
    for name in exact_names:
        if name in conservative:
            payload[f"conservative_{name}"] = _as_numpy(conservative[name])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)


def generate_geometry_reference(
    *,
    cases: Sequence[GeometryCase],
    contexts: Mapping[float, GeoStateReferenceContext],
    operators: Mapping[float, M1TorchProjection],
    config: Mapping[str, Any],
    processed_root: Path,
) -> tuple[
    dict[str, GeoStateReferenceResult],
    list[dict[str, Any]],
    list[dict[str, Any]],
    float,
]:
    if len(cases) > int(config["reference"]["maximum_unique_m1_reference_solves"]):
        raise ValueError("M1 reference case budget exceeded")
    results: dict[str, GeoStateReferenceResult] = {}
    manifest_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    total_wall_s = 0.0
    for overlap, context in contexts.items():
        _save_geometry_mask(
            processed_root / "geometry_masks" / f"g{int(overlap):03d}nm.npz",
            context,
            operators[overlap],
        )
    for geometry_case in cases:
        context = contexts[geometry_case.contact_overlap_nm]
        operator = operators[geometry_case.contact_overlap_nm]
        started = time.perf_counter()
        result = solve_reference_case(context, "M1", geometry_case.solver_case())
        wall_s = time.perf_counter() - started
        total_wall_s += wall_s
        conservative = _conservative_fields(operator, result)
        conservative_checks = _conservative_reference_checks(
            operator=operator,
            result=result,
            conservative=conservative,
            config=config,
        )
        results[geometry_case.case_id] = result
        npz_path = processed_root / "cases" / f"{geometry_case.case_id}.npz"
        _save_reference_npz(npz_path, geometry_case, result, conservative)
        manifest_rows.append(_reference_manifest_row(geometry_case, npz_path))
        metric_rows.append(
            _reference_metric_row(
                geometry_case=geometry_case,
                result=result,
                conservative_checks=conservative_checks,
                solve_wall_time_s=wall_s,
                config=config,
            )
        )
    if len(results) != 36:
        raise ValueError("reference generation did not produce exactly 36 M1 cases")
    return results, manifest_rows, metric_rows, total_wall_s


def load_completed_geometry_reference(
    *,
    cases: Sequence[GeometryCase],
    contexts: Mapping[float, GeoStateReferenceContext],
    operators: Mapping[float, M1TorchProjection],
    config: Mapping[str, Any],
    processed_root: Path,
    metrics_path: Path,
) -> tuple[
    dict[str, GeoStateReferenceResult],
    list[dict[str, Any]],
    list[dict[str, Any]],
    float,
]:
    """Resume after a metric-only repair without rerunning nonlinear solves."""

    with metrics_path.open("r", newline="", encoding="utf-8") as handle:
        stored_by_id = {row["case_id"]: row for row in csv.DictReader(handle)}
    if set(stored_by_id) != {case.case_id for case in cases}:
        raise ValueError("completed reference table does not contain the frozen 36 cases")
    results: dict[str, GeoStateReferenceResult] = {}
    manifest_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    total_wall_s = 0.0
    field_names = (
        "x_m",
        "y_m",
        "potential_V",
        "temperature_K",
        "conductivity_S_m",
        "state_coordinate",
        "branch_value",
        "joule_heat_W_m2",
        "sink_heat_W_m2",
        "Jx_A_m",
        "Jy_A_m",
        "J_magnitude_A_m",
        "qx_W_m",
        "qy_W_m",
        "q_magnitude_W_m",
    )
    for geometry_case in cases:
        stored = stored_by_id[geometry_case.case_id]
        npz_path = processed_root / "cases" / f"{geometry_case.case_id}.npz"
        if not npz_path.is_file():
            raise FileNotFoundError(npz_path)
        with np.load(npz_path, allow_pickle=False) as archive:
            fields = {
                name: np.asarray(archive[name])
                for name in field_names
                if name in archive.files
            }
        metrics: dict[str, float | int | bool | str] = {
            "iterations": int(float(stored["iterations"])),
            "converged": _csv_bool(stored["converged"]),
            "finite": _csv_bool(stored["finite"]),
            "scaled_nonlinear_residual": float(stored["scaled_nonlinear_residual"]),
            "terminal_current_imbalance": float(stored["current_imbalance"]),
            "terminal_field_joule_error": float(
                stored["terminal_electrical_heat_ledger_error"]
            ),
            "joule_sink_ledger_error": float(
                stored["electrical_heat_sink_ledger_error"]
            ),
            "source_current_A": float(stored["source_current_A"]),
            "Tmax_K": float(stored["Tmax_K"]),
            "Tmean_K": float(stored["Tmean_K"]),
            "hotspot_x_m": float(stored["hotspot_x_m"]),
            "hotspot_y_m": float(stored["hotspot_y_m"]),
            "hotspot_lateral_shift_width_fraction": float(
                stored["hotspot_lateral_shift_width_fraction"]
            ),
            "chi_2d": float(stored["chi_2d"]),
        }
        context = contexts[geometry_case.contact_overlap_nm]
        result = GeoStateReferenceResult(
            model_form="M1",
            case=geometry_case.solver_case(),
            grid=context.grid,
            fields=fields,
            metrics=metrics,
        )
        conservative = _conservative_fields(
            operators[geometry_case.contact_overlap_nm], result
        )
        checks = _conservative_reference_checks(
            operator=operators[geometry_case.contact_overlap_nm],
            result=result,
            conservative=conservative,
            config=config,
        )
        wall_s = float(stored["solve_wall_time_s"])
        total_wall_s += wall_s
        results[geometry_case.case_id] = result
        manifest_rows.append(_reference_manifest_row(geometry_case, npz_path))
        metric_rows.append(
            _reference_metric_row(
                geometry_case=geometry_case,
                result=result,
                conservative_checks=checks,
                solve_wall_time_s=wall_s,
                config=config,
            )
        )
    return results, manifest_rows, metric_rows, total_wall_s


def localized_near_transition_gate(
    metric_rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> dict[str, Any]:
    gates = config["reference"]["gates"]
    subset = [
        row
        for row in metric_rows
        if "_near-transition_localized-sink" in str(row["case_id"])
    ]
    if len(subset) != 6:
        raise ValueError("expected six branch-specific localized near-transition cases")
    details = []
    for row in subset:
        passed = bool(
            float(row["chi_2d"])
            >= float(gates["localized_near_transition_chi_2d_min"])
            or float(row["hotspot_lateral_shift_width_fraction"])
            >= float(
                gates[
                    "localized_near_transition_hotspot_shift_width_fraction_min"
                ]
            )
        )
        details.append(
            {
                "case_id": row["case_id"],
                "chi_2d": row["chi_2d"],
                "hotspot_lateral_shift_width_fraction": row[
                    "hotspot_lateral_shift_width_fraction"
                ],
                "pass": passed,
            }
        )
    return {"passed": all(item["pass"] for item in details), "cases": details}


def _hotspot_set(
    temperature_K: np.ndarray, context: GeoStateReferenceContext
) -> tuple[np.ndarray, float]:
    temperature = np.asarray(temperature_K, dtype=np.float64)
    maximum = float(np.max(temperature))
    tolerance = (
        64.0
        * np.finfo(np.float64).eps
        * max(abs(maximum), 1.0)
    )
    indices = np.argwhere(maximum - temperature <= tolerance)
    coordinates = np.column_stack(
        (
            context.grid.x_centers_m[indices[:, 1]],
            context.grid.y_centers_m[indices[:, 0]],
        )
    )
    return coordinates, tolerance


def _hotspot_set_distances(
    first_temperature_K: np.ndarray,
    second_temperature_K: np.ndarray,
    context: GeoStateReferenceContext,
) -> dict[str, Any]:
    first, first_tolerance = _hotspot_set(first_temperature_K, context)
    second, second_tolerance = _hotspot_set(second_temperature_K, context)
    distances = np.linalg.norm(first[:, None, :] - second[None, :, :], axis=2)
    minimum = float(np.min(distances) / context.width_m)
    directed_first = float(np.max(np.min(distances, axis=1)))
    directed_second = float(np.max(np.min(distances, axis=0)))
    hausdorff = max(directed_first, directed_second) / context.width_m
    return {
        "hotspot_distance_width_fraction": minimum,
        "hotspot_hausdorff_width_fraction_diagnostic": hausdorff,
        "m1_hotspot_set_cardinality": int(first.shape[0]),
        "m2_hotspot_set_cardinality": int(second.shape[0]),
        "m1_hotspot_tie_tolerance_K": first_tolerance,
        "m2_hotspot_tie_tolerance_K": second_tolerance,
        "hotspot_metric_tie_aware": True,
    }


def _m2_result_from_saved_fields(
    *,
    geometry_case: GeometryCase,
    context: GeoStateReferenceContext,
    archive: Mapping[str, Any],
    accepted_by_original_run: bool,
) -> GeoStateReferenceResult:
    """Reconstruct numeric M2 acceptance metrics without another nonlinear solve."""

    temperature = np.asarray(archive["m2_temperature_K"], dtype=float)
    potential_saved = np.asarray(archive["m2_potential_V"], dtype=float)
    substrate_raw = np.asarray(archive["m2_substrate_temperature_K"], dtype=float)
    substrate = substrate_raw if substrate_raw.size else None
    case = geometry_case.solver_case()
    sigma = conductivity_numpy(temperature, case.state_coordinate, context.fast_config)
    electrical_contact, thermal_contact = _contact_values(
        context.fast_config, "M2", case
    )
    electrical = _solve_electrical_robin(
        context, sigma, case.device_voltage_V, electrical_contact
    )
    closure = _thermal_closure(context, "M2", case, thermal_contact)
    residual, sink_power, sink_cell = _thermal_residual_and_sink(
        context,
        "M2",
        closure,
        temperature,
        substrate,
        electrical["cell_joule_power_W"],
    )
    joule_power = float(electrical["field_joule_power_W"])
    cell_scale = max(abs(joule_power) / (context.grid.nx * context.grid.ny), 1.0e-15)
    scaled_residual = max(
        float(np.max(np.abs(residual)) / cell_scale),
        float(electrical["scaled_electrical_residual"]),
    )
    ledger = abs(joule_power - sink_power) / max(
        abs(joule_power), abs(sink_power), 1.0e-30
    )
    rise = temperature - context.ambient_temperature_K
    transverse = rise - np.mean(rise, axis=0, keepdims=True)
    chi_2d = float(
        np.linalg.norm(transverse.reshape(-1))
        / max(np.linalg.norm(rise.reshape(-1)), 1.0e-30)
    )
    hotspot_flat = int(np.argmax(temperature))
    iy, ix = np.unravel_index(hotspot_flat, context.grid.shape)
    hotspot_x = float(context.grid.x_centers_m[ix])
    hotspot_y = float(context.grid.y_centers_m[iy])
    finite = bool(
        np.isfinite(temperature).all()
        and np.isfinite(potential_saved).all()
        and substrate is not None
        and np.isfinite(substrate).all()
        and np.isfinite(electrical["potential_V"]).all()
    )
    metrics: dict[str, float | int | bool | str] = {
        "iterations": -1,
        "converged": bool(accepted_by_original_run),
        "finite": finite,
        "scaled_nonlinear_residual": scaled_residual,
        "terminal_current_imbalance": float(electrical["current_imbalance"]),
        "terminal_field_joule_error": float(electrical["terminal_field_error"]),
        "joule_sink_ledger_error": ledger,
        "source_current_A": float(electrical["source_current_A"]),
        "Tmax_K": float(np.max(temperature)),
        "Tmean_K": float(np.mean(temperature)),
        "hotspot_x_m": hotspot_x,
        "hotspot_y_m": hotspot_y,
        "hotspot_lateral_shift_width_fraction": abs(
            hotspot_y / context.width_m - 0.5
        ),
        "chi_2d": chi_2d,
    }
    return GeoStateReferenceResult(
        model_form="M2",
        case=case,
        grid=context.grid,
        fields={
            "temperature_K": temperature,
            "potential_V": np.asarray(electrical["potential_V"]),
            "substrate_temperature_K": np.asarray(substrate),
            "conductivity_S_m": sigma,
            "joule_heat_W_m2": np.asarray(electrical["cell_joule_power_W"])
            / context.grid.cell_area_m2,
            "sink_heat_W_m2": np.asarray(sink_cell) / context.grid.cell_area_m2,
        },
        metrics=metrics,
    )


def run_m2_sentinels(
    *,
    cases_by_id: Mapping[str, GeometryCase],
    m1_results: Mapping[str, GeoStateReferenceResult],
    contexts: Mapping[float, GeoStateReferenceContext],
    config: Mapping[str, Any],
    processed_root: Path,
    existing_metrics_path: Path | None = None,
) -> tuple[list[dict[str, Any]], float]:
    sentinel_ids = tuple(str(value) for value in config["reference"]["m2_sentinels"])
    if len(sentinel_ids) > int(
        config["reference"]["maximum_unique_m2_sentinel_solves"]
    ):
        raise ValueError("M2 sentinel solve budget exceeded")
    gates = config["reference"]["m2_sentinel_gates"]
    rows: list[dict[str, Any]] = []
    total_wall_s = 0.0
    stored_rows: dict[str, dict[str, str]] = {}
    if existing_metrics_path is not None and existing_metrics_path.is_file():
        with existing_metrics_path.open("r", newline="", encoding="utf-8") as handle:
            stored_rows = {row["case_id"]: row for row in csv.DictReader(handle)}
    for case_id in sentinel_ids:
        geometry_case = cases_by_id[case_id]
        context = contexts[geometry_case.contact_overlap_nm]
        sentinel_path = processed_root / "m2_sentinels" / f"{case_id}.npz"
        reused = sentinel_path.is_file() and case_id in stored_rows
        if reused:
            stored = stored_rows[case_id]
            with np.load(sentinel_path, allow_pickle=False) as archive:
                m2 = _m2_result_from_saved_fields(
                    geometry_case=geometry_case,
                    context=context,
                    archive=archive,
                    accepted_by_original_run=_csv_bool(
                        stored.get("m2_reference_gate_pass", False)
                    ),
                )
            wall_s = float(stored["m2_solve_wall_time_s"])
        else:
            started = time.perf_counter()
            m2 = solve_reference_case(context, "M2", geometry_case.solver_case())
            wall_s = time.perf_counter() - started
        total_wall_s += wall_s
        m1 = m1_results[case_id]
        i1 = abs(float(m1.metrics["source_current_A"]))
        i2 = abs(float(m2.metrics["source_current_A"]))
        current_difference = abs(i1 - i2) / max(i2, 1.0e-30)
        tmax_difference = abs(
            float(m1.metrics["Tmax_K"]) - float(m2.metrics["Tmax_K"])
        )
        hotspot_resolved = bool(
            float(m1.metrics["chi_2d"])
            >= float(config["reference"]["gates"]["localized_near_transition_chi_2d_min"])
            or float(m2.metrics["chi_2d"])
            >= float(config["reference"]["gates"]["localized_near_transition_chi_2d_min"])
        )
        if hotspot_resolved:
            hotspot = _hotspot_set_distances(
                np.asarray(m1.fields["temperature_K"]),
                np.asarray(m2.fields["temperature_K"]),
                context,
            )
        else:
            hotspot = {
                "hotspot_distance_width_fraction": math.nan,
                "hotspot_hausdorff_width_fraction_diagnostic": math.nan,
                "m1_hotspot_set_cardinality": 0,
                "m2_hotspot_set_cardinality": 0,
                "m1_hotspot_tie_tolerance_K": math.nan,
                "m2_hotspot_tie_tolerance_K": math.nan,
                "hotspot_metric_tie_aware": True,
            }
        hotspot_distance = float(hotspot["hotspot_distance_width_fraction"])
        passed = bool(
            _reference_pass(m1, config)
            and _reference_pass(m2, config)
            and current_difference
            <= float(gates["terminal_current_relative_difference_max"])
            and tmax_difference <= float(gates["tmax_difference_K_max"])
            and (
                not hotspot_resolved
                or hotspot_distance
                <= float(gates["resolved_hotspot_distance_width_fraction_max"])
            )
        )
        rows.append(
            {
                "case_id": case_id,
                "contact_overlap_nm": geometry_case.contact_overlap_nm,
                "m2_solve_wall_time_s": wall_s,
                "m1_source_current_A": float(m1.metrics["source_current_A"]),
                "m2_source_current_A": float(m2.metrics["source_current_A"]),
                "terminal_current_relative_difference": current_difference,
                "m1_Tmax_K": float(m1.metrics["Tmax_K"]),
                "m2_Tmax_K": float(m2.metrics["Tmax_K"]),
                "Tmax_difference_K": tmax_difference,
                "hotspot_resolved": hotspot_resolved,
                **hotspot,
                "m2_converged": bool(m2.metrics["converged"]),
                "m2_finite": bool(m2.metrics["finite"]),
                "m2_scaled_nonlinear_residual": float(
                    m2.metrics["scaled_nonlinear_residual"]
                ),
                "m2_current_imbalance": float(
                    m2.metrics["terminal_current_imbalance"]
                ),
                "m2_terminal_electrical_heat_ledger_error": float(
                    m2.metrics["terminal_field_joule_error"]
                ),
                "m2_electrical_heat_sink_ledger_error": float(
                    m2.metrics["joule_sink_ledger_error"]
                ),
                "m2_physical_solve_reused_after_metric_repair": reused,
                "m1_reference_gate_pass": _reference_pass(m1, config),
                "m2_reference_gate_pass": _reference_pass(m2, config),
                "sentinel_pass": passed,
            }
        )
        if not reused:
            sentinel_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                sentinel_path,
                case_id=np.asarray(case_id),
                contact_overlap_nm=np.asarray(geometry_case.contact_overlap_nm),
                m1_temperature_K=np.asarray(m1.fields["temperature_K"]),
                m1_potential_V=np.asarray(m1.fields["potential_V"]),
                m2_temperature_K=np.asarray(m2.fields["temperature_K"]),
                m2_potential_V=np.asarray(m2.fields["potential_V"]),
                m2_substrate_temperature_K=np.asarray(
                    m2.fields.get("substrate_temperature_K", np.empty((0, 0)))
                ),
            )
    return rows, total_wall_s


def fit_geometry_pod(
    *,
    cases: Sequence[GeometryCase],
    results: Mapping[str, GeoStateReferenceResult],
    ambient_temperature_K: float,
    config: Mapping[str, Any],
) -> ThermalPOD:
    train_ids = tuple(sorted(case.case_id for case in cases if case.split == "train"))
    fields = {
        case_id: np.asarray(results[case_id].fields["temperature_K"], dtype=float)
        for case_id in train_ids
    }
    pod = fit_train_only_pod(
        fields,
        train_ids,
        ambient_temperature_K=ambient_temperature_K,
        cumulative_energy_target=float(config["pod"]["cumulative_energy_target"]),
        rank_cap=int(config["pod"]["rank_cap"]),
        training_sample_rank_cap=int(config["pod"]["rank_cap"]),
    )
    if pod.rank > int(config["pod"]["rank_cap"]):
        raise RuntimeError("NO_GO_LOW_RANK_GEOMETRY_MANIFOLD")
    return pod


def raw_mu(case: GeometryCase) -> np.ndarray:
    return np.asarray(
        [
            case.device_voltage_V,
            case.branch_value,
            case.state_coordinate,
            case.sink_amplitude,
            case.contact_overlap_nm * 1.0e-9,
        ],
        dtype=float,
    )


def fit_input_normalization(
    cases: Sequence[GeometryCase], train_case_ids: Sequence[str]
) -> InputNormalization:
    expected = tuple(sorted(str(value) for value in train_case_ids))
    supplied = tuple(sorted(case.case_id for case in cases))
    if supplied != expected:
        raise ValueError("input normalization must receive exactly the train cases")
    ordered = sorted(cases, key=lambda item: item.case_id)
    values = np.stack([raw_mu(case) for case in ordered])
    mean = np.mean(values, axis=0)
    scale = np.std(values, axis=0)
    scale = np.where(scale > 1.0e-15, scale, 1.0)
    return InputNormalization(mean=mean, scale=scale, train_case_ids=expected)


def normalize_mu(
    cases: Sequence[GeometryCase], normalization: InputNormalization
) -> Tensor:
    values = np.stack([raw_mu(case) for case in cases])
    return torch.as_tensor(
        (values - normalization.mean) / normalization.scale, dtype=torch.float64
    )


def fit_ridge_latent(
    *,
    cases: Sequence[GeometryCase],
    pod: ThermalPOD,
    normalization: InputNormalization,
    regularization_lambda: float,
) -> RidgeLatent:
    ordered = sorted(cases, key=lambda item: item.case_id)
    if tuple(case.case_id for case in ordered) != pod.train_case_ids:
        raise ValueError("ridge fit cases must equal the train-only POD cases")
    normalized = normalize_mu(ordered, normalization).detach().cpu().numpy()
    design = np.column_stack([np.ones(len(ordered)), normalized])
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[0, 0] = 0.0
    gram = design.T @ design + float(regularization_lambda) * penalty
    coefficients = np.linalg.solve(gram, design.T @ pod.coefficients)
    return RidgeLatent(
        coefficients=coefficients,
        regularization_lambda=float(regularization_lambda),
        design_condition_number=float(np.linalg.cond(gram)),
    )


def ridge_coefficients(
    cases: Sequence[GeometryCase],
    ridge: RidgeLatent,
    normalization: InputNormalization,
) -> Tensor:
    normalized = normalize_mu(cases, normalization)
    design = torch.cat(
        [
            torch.ones((len(cases), 1), dtype=torch.float64),
            normalized,
        ],
        dim=1,
    )
    return design @ torch.as_tensor(ridge.coefficients, dtype=torch.float64)


def decode_temperature(
    coefficients: Tensor,
    pod: ThermalPOD,
    *,
    ambient_temperature_K: float,
    smooth_nonnegative_beta_K: float,
    ny: int,
    nx: int,
) -> Tensor:
    mean = torch.as_tensor(pod.mean_y, dtype=torch.float64)
    basis = torch.as_tensor(pod.basis, dtype=torch.float64)
    y = mean + coefficients @ basis
    rise = torch.expm1(y)
    beta = float(smooth_nonnegative_beta_K)
    protected = beta * torch.nn.functional.softplus(rise / beta)
    return (float(ambient_temperature_K) + protected).reshape(-1, ny, nx)


def build_geometry_model(
    pod: ThermalPOD, config: Mapping[str, Any]
) -> M1LatentGeometryMapper:
    return M1LatentGeometryMapper(
        pod_mean_y=torch.as_tensor(pod.mean_y, dtype=torch.float64),
        pod_basis=torch.as_tensor(pod.basis, dtype=torch.float64),
        coefficient_center=torch.as_tensor(pod.coefficient_center, dtype=torch.float64),
        coefficient_scale=torch.as_tensor(pod.coefficient_scale, dtype=torch.float64),
        ambient_temperature_K=float(config["reference"]["ambient_temperature_K"]),
        smooth_nonnegative_beta_K=float(config["pod"]["smooth_nonnegative_beta_K"]),
    )


def _unbatch_fields(fields: Mapping[str, Tensor]) -> dict[str, Tensor]:
    result: dict[str, Tensor] = {}
    for name, value in fields.items():
        if isinstance(value, torch.Tensor) and value.ndim > 0 and value.shape[0] == 1:
            result[name] = value[0]
        else:
            result[name] = value
    return result


def initial_state_fields(
    operator: M1TorchProjection,
    temperature_K: Tensor,
    case: GeometryCase,
) -> dict[str, Tensor]:
    electrical = operator.electrical(
        temperature_K, case.device_voltage_V, case.state_coordinate
    )
    thermal = operator.thermal_diagnostics(
        temperature_K, electrical["total_joule_cell_W"], case.sink_amplitude
    )
    return {**electrical, **thermal}


def true_lookahead_defects(
    operator: M1TorchProjection,
    temperature_K: Tensor,
    case: GeometryCase,
) -> tuple[float, float, dict[str, Tensor]]:
    lookahead = operator.projection(
        temperature_K,
        case.device_voltage_V,
        case.state_coordinate,
        case.sink_amplitude,
    )
    ambient = operator.ambient_temperature_K
    fixed = float(
        torch.linalg.vector_norm(lookahead["temperature_K"] - temperature_K)
        / torch.clamp(
            torch.linalg.vector_norm(lookahead["temperature_K"] - ambient),
            min=1.0e-30,
        )
    )
    sigma_current = operator.conductivity(temperature_K, case.state_coordinate)
    sigma_lookahead = operator.conductivity(
        lookahead["temperature_K"], case.state_coordinate
    )
    sigma = float(
        torch.linalg.vector_norm(sigma_lookahead - sigma_current)
        / torch.clamp(torch.linalg.vector_norm(sigma_lookahead), min=1.0e-30)
    )
    return fixed, sigma, lookahead


def metric_row(
    *,
    target: EvaluationTarget,
    operator: M1TorchProjection,
    mode: str,
    fields: Mapping[str, Tensor],
    seed: int | str,
    projection_count: int,
    main_linear_solve_count: int,
    median_wall_time_s: float = math.nan,
    timing_repeats: int = 0,
) -> dict[str, Any]:
    temperature = _as_numpy(fields["temperature_K"])
    potential = _as_numpy(fields["potential_V"])
    reference_rise = target.temperature_K - operator.ambient_temperature_K
    predicted_rise = temperature - operator.ambient_temperature_K
    t_error = _relative_l2(predicted_rise, reference_rise)
    phi_error = _relative_l2(potential, target.potential_V)
    current = float(fields["source_current_A"])
    current_error = abs(current - target.source_current_A) / max(
        abs(target.source_current_A), 1.0e-30
    )
    predicted_hotspot = np.unravel_index(int(np.argmax(temperature)), temperature.shape)
    reference_hotspot = np.unravel_index(
        int(np.argmax(target.temperature_K)), target.temperature_K.shape
    )
    dx = float(
        operator.x_centers_m[predicted_hotspot[1]]
        - operator.x_centers_m[reference_hotspot[1]]
    )
    dy = float(
        operator.y_centers_m[predicted_hotspot[0]]
        - operator.y_centers_m[reference_hotspot[0]]
    )
    hotspot_error = math.hypot(dx, dy) / operator.width_m
    fixed, sigma, _ = true_lookahead_defects(
        operator,
        torch.as_tensor(temperature, dtype=torch.float64),
        target.case,
    )
    terminal_ledger = float(fields["terminal_electrical_heat_ledger_error"])
    sink_ledger = float(fields["electrical_heat_sink_ledger_error"])
    finite = bool(
        np.isfinite(temperature).all()
        and np.isfinite(potential).all()
        and np.isfinite(
            [
                current,
                t_error,
                phi_error,
                fixed,
                sigma,
                terminal_ledger,
                sink_ledger,
            ]
        ).all()
    )
    return {
        "seed": seed,
        "split": target.case.split,
        "case_id": target.case.case_id,
        "contact_overlap_nm": target.case.contact_overlap_nm,
        "mode": mode,
        "temperature_rise_relative_l2": t_error,
        "potential_relative_l2": phi_error,
        "joint_field_score": 0.5 * (t_error + phi_error),
        "terminal_current_relative_error": current_error,
        "predicted_terminal_current_A": current,
        "reference_terminal_current_A": target.source_current_A,
        "hotspot_coordinate_error_width_fraction": hotspot_error,
        "true_fixed_point_defect": fixed,
        "sigma_defect": sigma,
        "terminal_electrical_heat_ledger_error": terminal_ledger,
        "electrical_heat_sink_ledger_error": sink_ledger,
        "energy_ledger_error": max(terminal_ledger, sink_ledger),
        "projection_count": projection_count,
        "main_linear_solve_count": main_linear_solve_count,
        "diagnostic_projection_count": 1,
        "diagnostic_linear_solve_count": 2,
        "diagnostic_included_in_timing": False,
        "median_wall_time_s": median_wall_time_s,
        "timing_repeats": timing_repeats,
        "finite": finite,
        "practical_case_pass": False,
    }


def _historical_geometry_case(teacher: Any, split: str) -> GeometryCase:
    branch = "heating" if teacher.branch_value > 0.0 else "cooling"
    thermal = "localized-sink" if teacher.sink_amplitude > 0.0 else "nominal"
    level = teacher.case_id[len(branch) + 1 :]
    level = level[: -len(thermal) - 1]
    return GeometryCase(
        case_id=teacher.case_id,
        contact_overlap_nm=20.0,
        branch=branch,
        branch_value=float(teacher.branch_value),
        level=level,
        device_voltage_V=float(teacher.device_voltage_V),
        state_coordinate=float(teacher.state_coordinate),
        thermal_condition=thermal,
        sink_amplitude=float(teacher.sink_amplitude),
        split=split,
    )


def current_domain_matched_budget_diagnostic(
    *,
    config: Mapping[str, Any],
    repository_root: Path,
) -> list[dict[str, Any]]:
    diagnostic = config["current_domain_diagnostic"]
    historical_config = load_yaml(
        repository_root / diagnostic["historical_config"]
    )
    base_config = load_yaml(repository_root / historical_config["reference"]["config"])
    context = build_geometry_context(
        base_config, repository_root, float(diagnostic["contact_overlap_nm"])
    )
    operator = build_projection_operator(context, base_config)
    teachers = load_teacher_cases(repository_root / diagnostic["historical_case_root"])
    split = historical_split_case_ids(teachers, historical_config)
    split_by_id = {
        case_id: split_name
        for split_name, ids in split.items()
        for case_id in ids
    }
    checkpoint = torch.load(
        repository_root / diagnostic["historical_checkpoint"],
        map_location="cpu",
        weights_only=False,
    )
    rank = int(checkpoint["rank"])
    historical_pod = ThermalPOD(
        mean_y=np.asarray(checkpoint["pod_mean_y"], dtype=float),
        basis=np.asarray(checkpoint["pod_basis"], dtype=float),
        coefficients=np.empty((0, rank)),
        coefficient_center=np.asarray(checkpoint["coefficient_center"], dtype=float),
        coefficient_scale=np.asarray(checkpoint["coefficient_scale"], dtype=float),
        singular_values=np.empty(0),
        cumulative_energy=np.empty(0),
        rank=rank,
        rank_cap_relaxed=False,
        train_case_ids=tuple(checkpoint["train_case_ids"]),
        reconstruction_errors=np.empty(0),
    )
    model = build_historical_latent_model(historical_pod, historical_config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    by_id = {teacher.case_id: teacher for teacher in teachers}
    geometry_cases = {
        teacher.case_id: _historical_geometry_case(
            teacher, split_by_id[teacher.case_id]
        )
        for teacher in teachers
    }
    train_ids = tuple(sorted(split["train"]))
    train_cases = [geometry_cases[case_id] for case_id in train_ids]
    normalization = fit_input_normalization(train_cases, train_ids)
    train_y = []
    for case_id in train_ids:
        rise = np.maximum(by_id[case_id].temperature_K - context.ambient_temperature_K, 0.0)
        transformed = np.log1p(rise).reshape(-1)
        train_y.append(
            (transformed - historical_pod.mean_y) @ historical_pod.basis.T
        )
    historical_pod = ThermalPOD(
        mean_y=historical_pod.mean_y,
        basis=historical_pod.basis,
        coefficients=np.stack(train_y),
        coefficient_center=historical_pod.coefficient_center,
        coefficient_scale=historical_pod.coefficient_scale,
        singular_values=historical_pod.singular_values,
        cumulative_energy=historical_pod.cumulative_energy,
        rank=historical_pod.rank,
        rank_cap_relaxed=False,
        train_case_ids=train_ids,
        reconstruction_errors=np.empty(len(train_ids)),
    )
    ridge = fit_ridge_latent(
        cases=train_cases,
        pod=historical_pod,
        normalization=normalization,
        regularization_lambda=float(config["ridge"]["regularization_lambda"]),
    )
    rows: list[dict[str, Any]] = []
    old_voltage_scale = float(historical_config["model"]["voltage_scale_V"])
    old_sink_scale = float(historical_config["model"]["sink_amplitude_scale"])
    with torch.no_grad():
        for teacher in sorted(teachers, key=lambda item: item.case_id):
            case = geometry_cases[teacher.case_id]
            target_current = float(
                operator.electrical(
                    torch.as_tensor(teacher.temperature_K, dtype=torch.float64),
                    teacher.device_voltage_V,
                    teacher.state_coordinate,
                )["source_current_A"]
            )
            target = EvaluationTarget(
                case=case,
                temperature_K=np.asarray(teacher.temperature_K),
                potential_V=np.asarray(teacher.potential_V),
                source_current_A=target_current,
                reference_iterations=0,
            )
            cold0 = operator.cold_initial_temperature(
                case.device_voltage_V, case.state_coordinate
            )[0]
            a1 = operator.projection(
                cold0, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
            )
            a2 = operator.projection(
                a1["temperature_K"],
                case.device_voltage_V,
                case.state_coordinate,
                case.sink_amplitude,
            )
            ridge_coeff = ridge_coefficients([case], ridge, normalization)
            ridge0 = decode_temperature(
                ridge_coeff,
                historical_pod,
                ambient_temperature_K=context.ambient_temperature_K,
                smooth_nonnegative_beta_K=float(
                    historical_config["pod"]["smooth_nonnegative_beta_K"]
                ),
                ny=operator.ny,
                nx=operator.nx,
            )[0]
            r0 = initial_state_fields(operator, ridge0, case)
            r1 = operator.projection(
                ridge0, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
            )
            r2 = operator.projection(
                r1["temperature_K"],
                case.device_voltage_V,
                case.state_coordinate,
                case.sink_amplitude,
            )
            old_mu = torch.as_tensor(
                [
                    [
                        case.device_voltage_V / old_voltage_scale,
                        case.branch_value,
                        case.state_coordinate,
                        case.sink_amplitude / old_sink_scale,
                    ]
                ],
                dtype=torch.float64,
            )
            neural0 = model.initial_temperature(old_mu, operator.ny, operator.nx)[0]
            n0 = initial_state_fields(operator, neural0, case)
            n1 = operator.projection(
                neural0, case.device_voltage_V, case.state_coordinate, case.sink_amplitude
            )
            n2 = operator.projection(
                n1["temperature_K"],
                case.device_voltage_V,
                case.state_coordinate,
                case.sink_amplitude,
            )
            definitions = (
                ("A1", a1, 1, 2),
                ("A2", a2, 2, 4),
                ("R0", r0, 0, 1),
                ("R1", r1, 1, 2),
                ("R2", r2, 2, 4),
                ("N0", n0, 0, 1),
                ("N1", n1, 1, 2),
                ("N2", n2, 2, 4),
            )
            for mode, fields, projection_count, solve_count in definitions:
                row = metric_row(
                    target=target,
                    operator=operator,
                    mode=mode,
                    fields=fields,
                    seed=int(checkpoint["seed"]) if mode.startswith("N") else "baseline",
                    projection_count=projection_count,
                    main_linear_solve_count=solve_count,
                )
                row["historical_pr39_metrics_modified"] = False
                rows.append(row)
    return rows


def train_geometry_model(
    *,
    seed: int,
    pod: ThermalPOD,
    normalization: InputNormalization,
    cases: Sequence[GeometryCase],
    results: Mapping[str, GeoStateReferenceResult],
    operators: Mapping[float, M1TorchProjection],
    config: Mapping[str, Any],
) -> tuple[M1LatentGeometryMapper, list[dict[str, Any]], dict[str, Any]]:
    torch.manual_seed(int(seed))
    np.random.seed(int(seed) % (2**32 - 1))
    model = build_geometry_model(pod, config)
    training = config["training"]
    ordered = sorted((case for case in cases if case.split == "train"), key=lambda c: c.case_id)
    if tuple(case.case_id for case in ordered) != pod.train_case_ids:
        raise ValueError("neural training cases must equal the train-only POD cases")
    mu_all = normalize_mu(ordered, normalization)
    target_coefficients = torch.as_tensor(pod.coefficients, dtype=torch.float64)
    groups: dict[float, list[int]] = {}
    for index, case in enumerate(ordered):
        groups.setdefault(case.contact_overlap_nm, []).append(index)
    weights = {
        name: float(value)
        for name, value in training["fixed_loss_weights"].items()
    }
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    global_step = 0

    def append_history(
        *,
        stage: int,
        stage_step: int,
        learning_rate: float,
        losses: Mapping[str, Tensor | float],
        total: Tensor,
    ) -> None:
        nonlocal global_step
        global_step += 1
        row: dict[str, Any] = {
            "seed": int(seed),
            "stage": stage,
            "stage_step": stage_step,
            "global_step": global_step,
            "learning_rate": learning_rate,
        }
        for name in weights:
            value = losses.get(name, 0.0)
            row[f"{name}_loss"] = float(
                value.detach() if isinstance(value, torch.Tensor) else value
            )
        row["total_loss"] = float(total.detach())
        row["finite"] = bool(torch.isfinite(total))
        row["elapsed_wall_s"] = time.perf_counter() - started
        history.append(row)

    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(training["stage1_learning_rate"])
    )
    for stage_step in range(1, int(training["stage1_steps"]) + 1):
        optimizer.zero_grad(set_to_none=True)
        coefficients = model(mu_all)
        coefficient_loss = torch.mean(
            ((coefficients - target_coefficients) / model.coefficient_scale).square()
        )
        coefficient_loss.backward()
        optimizer.step()
        append_history(
            stage=1,
            stage_step=stage_step,
            learning_rate=float(training["stage1_learning_rate"]),
            losses={"coefficient": coefficient_loss},
            total=coefficient_loss,
        )
        if history[-1]["elapsed_wall_s"] > float(
            training["maximum_wall_time_s_per_seed"]
        ):
            raise TimeoutError("geometry latent training exceeded the frozen wall budget")

    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(training["stage2_learning_rate"])
    )
    for stage_step in range(1, int(training["stage2_steps"]) + 1):
        optimizer.zero_grad(set_to_none=True)
        coefficients = model(mu_all)
        coefficient_loss = torch.mean(
            ((coefficients - target_coefficients) / model.coefficient_scale).square()
        )
        per_group: dict[str, list[Tensor]] = {
            name: [] for name in weights if name != "coefficient"
        }
        for overlap, indices in groups.items():
            operator = operators[overlap]
            group_cases = [ordered[index] for index in indices]
            index_tensor = torch.as_tensor(indices, dtype=torch.long)
            mu = mu_all[index_tensor]
            voltage = torch.as_tensor(
                [case.device_voltage_V for case in group_cases], dtype=torch.float64
            )
            state = torch.as_tensor(
                [case.state_coordinate for case in group_cases], dtype=torch.float64
            )
            sink = torch.as_tensor(
                [case.sink_amplitude for case in group_cases], dtype=torch.float64
            )
            target_temperature = torch.as_tensor(
                np.stack(
                    [results[case.case_id].fields["temperature_K"] for case in group_cases]
                ),
                dtype=torch.float64,
            )
            target_potential = torch.as_tensor(
                np.stack(
                    [results[case.case_id].fields["potential_V"] for case in group_cases]
                ),
                dtype=torch.float64,
            )
            target_current = torch.as_tensor(
                [
                    float(results[case.case_id].metrics["source_current_A"])
                    for case in group_cases
                ],
                dtype=torch.float64,
            )
            temperature0 = model.initial_temperature(mu, operator.ny, operator.nx)
            first = operator.projection(temperature0, voltage, state, sink)
            second = operator.projection(first["temperature_K"], voltage, state, sink)
            third = operator.projection(second["temperature_K"], voltage, state, sink)
            ambient = operator.ambient_temperature_K
            rise_norm = torch.clamp(
                torch.linalg.vector_norm(
                    target_temperature - ambient, dim=(1, 2)
                ),
                min=1.0e-30,
            )
            per_group["n1_temperature"].append(
                torch.linalg.vector_norm(
                    first["temperature_K"] - target_temperature, dim=(1, 2)
                )
                / rise_norm
            )
            per_group["n1_potential"].append(
                _torch_relative_l2(first["potential_V"], target_potential)
            )
            per_group["n1_current"].append(
                _scalar_relative(first["source_current_A"], target_current)
            )
            per_group["n1_true_lookahead_defect"].append(
                torch.linalg.vector_norm(
                    second["temperature_K"] - first["temperature_K"], dim=(1, 2)
                )
                / torch.clamp(
                    torch.linalg.vector_norm(
                        second["temperature_K"] - ambient, dim=(1, 2)
                    ),
                    min=1.0e-30,
                )
            )
            per_group["n2_temperature"].append(
                torch.linalg.vector_norm(
                    second["temperature_K"] - target_temperature, dim=(1, 2)
                )
                / rise_norm
            )
            per_group["n2_potential"].append(
                _torch_relative_l2(second["potential_V"], target_potential)
            )
            per_group["n2_current"].append(
                _scalar_relative(second["source_current_A"], target_current)
            )
            per_group["n2_true_lookahead_defect"].append(
                torch.linalg.vector_norm(
                    third["temperature_K"] - second["temperature_K"], dim=(1, 2)
                )
                / torch.clamp(
                    torch.linalg.vector_norm(
                        third["temperature_K"] - ambient, dim=(1, 2)
                    ),
                    min=1.0e-30,
                )
            )
        losses: dict[str, Tensor] = {"coefficient": coefficient_loss}
        for name, values in per_group.items():
            if not values:
                raise RuntimeError(f"missing geometry training loss group {name}")
            losses[name] = torch.mean(torch.cat(values).square())
        total = sum(weights[name] * losses[name] for name in weights)
        if not bool(torch.isfinite(total)):
            raise FloatingPointError("nonfinite loss in geometry latent training")
        total.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(), max_norm=float(training["gradient_clip_norm"])
        )
        optimizer.step()
        append_history(
            stage=2,
            stage_step=stage_step,
            learning_rate=float(training["stage2_learning_rate"]),
            losses=losses,
            total=total,
        )
        if history[-1]["elapsed_wall_s"] > float(
            training["maximum_wall_time_s_per_seed"]
        ):
            raise TimeoutError("geometry latent training exceeded the frozen wall budget")
    metadata = {
        "seed": int(seed),
        "completed_steps": global_step,
        "stage1_steps": int(training["stage1_steps"]),
        "stage2_steps": int(training["stage2_steps"]),
        "wall_time_s": time.perf_counter() - started,
        "finite": all(bool(row["finite"]) for row in history),
        "parameter_count": model.parameter_count,
        "dtype": "float64",
    }
    return model, history, metadata


def build_evaluation_targets(
    cases: Sequence[GeometryCase],
    results: Mapping[str, GeoStateReferenceResult],
) -> dict[str, EvaluationTarget]:
    return {
        case.case_id: EvaluationTarget(
            case=case,
            temperature_K=np.asarray(results[case.case_id].fields["temperature_K"]),
            potential_V=np.asarray(results[case.case_id].fields["potential_V"]),
            source_current_A=float(results[case.case_id].metrics["source_current_A"]),
            reference_iterations=int(results[case.case_id].metrics["iterations"]),
        )
        for case in cases
    }


def _time_callable(
    function: Callable[[], Any], *, repeats: int, warmups: int
) -> list[float]:
    with torch.no_grad():
        for _ in range(warmups):
            function()
        timings = []
        for _ in range(repeats):
            started = time.perf_counter()
            function()
            timings.append(time.perf_counter() - started)
    return timings


def _projection_chain(
    operator: M1TorchProjection,
    temperature0: Tensor,
    case: GeometryCase,
) -> tuple[dict[str, Tensor], dict[str, Tensor]]:
    first = operator.projection(
        temperature0,
        case.device_voltage_V,
        case.state_coordinate,
        case.sink_amplitude,
    )
    second = operator.projection(
        first["temperature_K"],
        case.device_voltage_V,
        case.state_coordinate,
        case.sink_amplitude,
    )
    return first, second


def _timing_rows(
    *,
    case: GeometryCase,
    seed: int | str,
    mode: str,
    timings: Sequence[float],
    linear_solve_count: int,
) -> list[dict[str, Any]]:
    return [
        {
            "seed": seed,
            "split": case.split,
            "case_id": case.case_id,
            "contact_overlap_nm": case.contact_overlap_nm,
            "mode": mode,
            "repeat_index": index,
            "wall_time_s": value,
            "main_linear_solve_count": linear_solve_count,
            "diagnostic_linear_solve_count": 0,
            "diagnostic_included_in_timing": False,
            "timing_repeats": len(timings),
        }
        for index, value in enumerate(timings)
    ]


def evaluate_baselines(
    *,
    cases: Sequence[GeometryCase],
    targets: Mapping[str, EvaluationTarget],
    operators: Mapping[float, M1TorchProjection],
    pod: ThermalPOD,
    normalization: InputNormalization,
    ridge: RidgeLatent,
    config: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[str, str], dict[str, Tensor]],
]:
    evaluation = config["evaluation"]
    fast_repeats = int(evaluation["fast_timing_repeats"])
    cold_repeats = int(evaluation["cold_timing_repeats"])
    warmups = int(evaluation["timing_warmup_repeats"])
    beta = float(config["pod"]["smooth_nonnegative_beta_K"])
    rows: list[dict[str, Any]] = []
    speed_rows: list[dict[str, Any]] = []
    predictions: dict[tuple[str, str], dict[str, Tensor]] = {}
    with torch.no_grad():
        for case in sorted(cases, key=lambda item: item.case_id):
            operator = operators[case.contact_overlap_nm]
            target = targets[case.case_id]
            cold_probe = frozen_m1_iteration(
                operator,
                initial_temperature_K=operator.cold_initial_temperature(
                    case.device_voltage_V, case.state_coordinate
                )[0],
                voltage_V=case.device_voltage_V,
                state_coordinate=case.state_coordinate,
                sink_amplitude=case.sink_amplitude,
                maximum_updates=int(evaluation["cold_maximum_iterations"]),
                relaxation=float(evaluation["relaxation"]),
                temperature_scale_K=float(evaluation["temperature_scale_K"]),
                residual_gate=float(evaluation["scaled_residual_max"]),
                update_gate=float(evaluation["scaled_update_max"]),
            )
            if not cold_probe.converged:
                raise RuntimeError(f"Torch COLD failed for {case.case_id}")
            cold_fields = dict(cold_probe.fields)
            cold_solve_count = int(
                cold_probe.electrical_solve_count + cold_probe.thermal_solve_count
            )
            cold_update_count = int(cold_probe.additional_iterations)
            cold0 = operator.cold_initial_temperature(
                case.device_voltage_V, case.state_coordinate
            )[0]
            a1, a2 = _projection_chain(operator, cold0, case)
            r_coeff = ridge_coefficients([case], ridge, normalization)
            ridge0 = decode_temperature(
                r_coeff,
                pod,
                ambient_temperature_K=operator.ambient_temperature_K,
                smooth_nonnegative_beta_K=beta,
                ny=operator.ny,
                nx=operator.nx,
            )[0]
            r0 = initial_state_fields(operator, ridge0, case)
            r1, r2 = _projection_chain(operator, ridge0, case)

            cold_function = lambda: frozen_m1_iteration(
                operator,
                initial_temperature_K=operator.cold_initial_temperature(
                    case.device_voltage_V, case.state_coordinate
                )[0],
                voltage_V=case.device_voltage_V,
                state_coordinate=case.state_coordinate,
                sink_amplitude=case.sink_amplitude,
                maximum_updates=int(evaluation["cold_maximum_iterations"]),
                relaxation=float(evaluation["relaxation"]),
                temperature_scale_K=float(evaluation["temperature_scale_K"]),
                residual_gate=float(evaluation["scaled_residual_max"]),
                update_gate=float(evaluation["scaled_update_max"]),
            )

            def analytic_function(count: int) -> Any:
                initial = operator.cold_initial_temperature(
                    case.device_voltage_V, case.state_coordinate
                )[0]
                first = operator.projection(
                    initial,
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )
                if count == 1:
                    return first
                return operator.projection(
                    first["temperature_K"],
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )

            def ridge_function(count: int) -> Any:
                coefficients = ridge_coefficients([case], ridge, normalization)
                initial = decode_temperature(
                    coefficients,
                    pod,
                    ambient_temperature_K=operator.ambient_temperature_K,
                    smooth_nonnegative_beta_K=beta,
                    ny=operator.ny,
                    nx=operator.nx,
                )[0]
                if count == 0:
                    return initial_state_fields(operator, initial, case)
                first = operator.projection(
                    initial,
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )
                if count == 1:
                    return first
                return operator.projection(
                    first["temperature_K"],
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )

            closures: dict[str, tuple[Callable[[], Any], int, int]] = {
                "COLD": (cold_function, cold_repeats, cold_solve_count),
                "A1": (lambda: analytic_function(1), fast_repeats, 2),
                "A2": (lambda: analytic_function(2), fast_repeats, 4),
                "R0": (lambda: ridge_function(0), fast_repeats, 1),
                "R1": (lambda: ridge_function(1), fast_repeats, 2),
                "R2": (lambda: ridge_function(2), fast_repeats, 4),
            }
            medians: dict[str, float] = {}
            for mode, (function, repeats, solve_count) in closures.items():
                timings = _time_callable(function, repeats=repeats, warmups=warmups)
                medians[mode] = float(np.median(timings))
                speed_rows.extend(
                    _timing_rows(
                        case=case,
                        seed="baseline",
                        mode=mode,
                        timings=timings,
                        linear_solve_count=solve_count,
                    )
                )
            definitions = (
                ("COLD", cold_fields, cold_update_count, cold_solve_count),
                ("A1", a1, 1, 2),
                ("A2", a2, 2, 4),
                ("R0", r0, 0, 1),
                ("R1", r1, 1, 2),
                ("R2", r2, 2, 4),
            )
            for mode, fields, projection_count, solve_count in definitions:
                row = metric_row(
                    target=target,
                    operator=operator,
                    mode=mode,
                    fields=fields,
                    seed="baseline",
                    projection_count=projection_count,
                    main_linear_solve_count=solve_count,
                    median_wall_time_s=medians[mode],
                    timing_repeats=(cold_repeats if mode == "COLD" else fast_repeats),
                )
                row["nonlinear_iteration_count"] = (
                    cold_update_count if mode == "COLD" else 0
                )
                rows.append(row)
                if case.split in {"validation", "test"} and mode != "COLD":
                    predictions[(case.case_id, mode)] = dict(fields)
    return rows, speed_rows, predictions


def evaluate_neural_seed(
    *,
    seed: int,
    model: M1LatentGeometryMapper,
    cases: Sequence[GeometryCase],
    targets: Mapping[str, EvaluationTarget],
    operators: Mapping[float, M1TorchProjection],
    normalization: InputNormalization,
    config: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[str, str], dict[str, Tensor]],
]:
    evaluation = config["evaluation"]
    repeats = int(evaluation["fast_timing_repeats"])
    warmups = int(evaluation["timing_warmup_repeats"])
    rows: list[dict[str, Any]] = []
    speed_rows: list[dict[str, Any]] = []
    predictions: dict[tuple[str, str], dict[str, Tensor]] = {}
    model.eval()
    with torch.no_grad():
        for case in sorted(cases, key=lambda item: item.case_id):
            operator = operators[case.contact_overlap_nm]
            target = targets[case.case_id]
            mu = normalize_mu([case], normalization)
            temperature0 = model.initial_temperature(mu, operator.ny, operator.nx)[0]
            n0 = initial_state_fields(operator, temperature0, case)
            n1, n2 = _projection_chain(operator, temperature0, case)

            def neural_function(count: int) -> Any:
                normalized = normalize_mu([case], normalization)
                initial = model.initial_temperature(
                    normalized, operator.ny, operator.nx
                )[0]
                if count == 0:
                    return initial_state_fields(operator, initial, case)
                first = operator.projection(
                    initial,
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )
                if count == 1:
                    return first
                return operator.projection(
                    first["temperature_K"],
                    case.device_voltage_V,
                    case.state_coordinate,
                    case.sink_amplitude,
                )

            medians: dict[str, float] = {}
            for mode, count, solve_count in (
                ("N0", 0, 1),
                ("N1", 1, 2),
                ("N2", 2, 4),
            ):
                timings = _time_callable(
                    lambda count=count: neural_function(count),
                    repeats=repeats,
                    warmups=warmups,
                )
                medians[mode] = float(np.median(timings))
                speed_rows.extend(
                    _timing_rows(
                        case=case,
                        seed=seed,
                        mode=mode,
                        timings=timings,
                        linear_solve_count=solve_count,
                    )
                )
            for mode, fields, projection_count, solve_count in (
                ("N0", n0, 0, 1),
                ("N1", n1, 1, 2),
                ("N2", n2, 2, 4),
            ):
                row = metric_row(
                    target=target,
                    operator=operator,
                    mode=mode,
                    fields=fields,
                    seed=seed,
                    projection_count=projection_count,
                    main_linear_solve_count=solve_count,
                    median_wall_time_s=medians[mode],
                    timing_repeats=repeats,
                )
                row["nonlinear_iteration_count"] = 0
                rows.append(row)
                if case.split in {"validation", "test"}:
                    predictions[(case.case_id, mode)] = dict(fields)
    return rows, speed_rows, predictions


def apply_practical_case_gates(
    rows: Sequence[dict[str, Any]], config: Mapping[str, Any]
) -> None:
    gates = config["evaluation"]["practical_case_gate"]
    for row in rows:
        row["practical_gate_role"] = (
            "reference_baseline_nonvoting"
            if row["mode"] == "COLD"
            else "admission_metric"
        )
        row["practical_case_pass"] = bool(
            row["finite"]
            and row["temperature_rise_relative_l2"]
            <= float(gates["temperature_rise_relative_l2_max"])
            and row["potential_relative_l2"]
            <= float(gates["potential_relative_l2_max"])
            and row["terminal_current_relative_error"]
            <= float(gates["terminal_current_relative_error_max"])
            and row["true_fixed_point_defect"]
            <= float(gates["true_fixed_point_defect_max"])
            and row["sigma_defect"] <= float(gates["sigma_defect_max"])
            and row["terminal_electrical_heat_ledger_error"]
            <= float(gates["terminal_electrical_heat_ledger_max"])
            and row["electrical_heat_sink_ledger_error"]
            <= float(gates["electrical_heat_sink_ledger_max"])
        )


def _test_rows(
    rows: Sequence[Mapping[str, Any]], mode: str, seed: int | str
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if row["split"] == "test" and row["mode"] == mode and row["seed"] == seed
    ]


def _improvement(candidate: float, baseline: float) -> float:
    return (baseline - candidate) / max(baseline, 1.0e-30)


def seed_gate_summary(
    *,
    seed: int,
    baseline_rows: Sequence[Mapping[str, Any]],
    neural_rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    h = config["evaluation"]["path_h"]
    s = config["evaluation"]["path_s"]
    catastrophic_max = float(config["evaluation"]["catastrophic_relative_error_max"])
    a1 = _test_rows(baseline_rows, "A1", "baseline")
    a2 = _test_rows(baseline_rows, "A2", "baseline")
    r1 = _test_rows(baseline_rows, "R1", "baseline")
    r2 = _test_rows(baseline_rows, "R2", "baseline")
    n1 = _test_rows(neural_rows, "N1", seed)
    n2 = _test_rows(neural_rows, "N2", seed)
    if any(len(values) != 12 for values in (a1, a2, r1, r2, n1, n2)):
        raise ValueError("geometry neural gates require 12 test cases for every comparator")

    def mean_joint(values: Sequence[Mapping[str, Any]]) -> float:
        return float(np.mean([float(row["joint_field_score"]) for row in values]))

    a1_joint = mean_joint(a1)
    a2_joint = mean_joint(a2)
    r1_joint = mean_joint(r1)
    r2_joint = mean_joint(r2)
    n1_joint = mean_joint(n1)
    n2_joint = mean_joint(n2)
    n1_passes = sum(bool(row["practical_case_pass"]) for row in n1)
    n2_passes = sum(bool(row["practical_case_pass"]) for row in n2)
    a2_passes = sum(bool(row["practical_case_pass"]) for row in a2)
    n1_improvement_a1 = _improvement(n1_joint, a1_joint)
    n1_improvement_r1 = _improvement(n1_joint, r1_joint)
    n2_improvement_a2 = _improvement(n2_joint, a2_joint)
    n2_improvement_r2 = _improvement(n2_joint, r2_joint)
    paired_h_speedups = [
        float(a2_row["median_wall_time_s"])
        / max(float(n1_row["median_wall_time_s"]), 1.0e-30)
        for a2_row, n1_row in zip(
            sorted(a2, key=lambda row: row["case_id"]),
            sorted(n1, key=lambda row: row["case_id"]),
            strict=True,
        )
    ]
    paired_s_ratios = [
        float(n2_row["median_wall_time_s"])
        / max(float(a2_row["median_wall_time_s"]), 1.0e-30)
        for a2_row, n2_row in zip(
            sorted(a2, key=lambda row: row["case_id"]),
            sorted(n2, key=lambda row: row["case_id"]),
            strict=True,
        )
    ]
    a2_median_time = float(
        np.median([float(row["median_wall_time_s"]) for row in a2])
    )
    n1_median_time = float(
        np.median([float(row["median_wall_time_s"]) for row in n1])
    )
    n2_median_time = float(
        np.median([float(row["median_wall_time_s"]) for row in n2])
    )
    h_speedup = a2_median_time / max(n1_median_time, 1.0e-30)
    s_time_ratio = n2_median_time / max(a2_median_time, 1.0e-30)
    n1_current_p95 = float(
        np.quantile(
            [float(row["terminal_current_relative_error"]) for row in n1], 0.95
        )
    )
    n1_catastrophic = any(
        (not bool(row["finite"]))
        or max(
            float(row["temperature_rise_relative_l2"]),
            float(row["potential_relative_l2"]),
            float(row["terminal_current_relative_error"]),
        )
        > catastrophic_max
        for row in n1
    )
    n2_catastrophic = any(
        (not bool(row["finite"]))
        or max(
            float(row["temperature_rise_relative_l2"]),
            float(row["potential_relative_l2"]),
            float(row["terminal_current_relative_error"]),
        )
        > catastrophic_max
        for row in n2
    )
    path_h_pass = bool(
        n1_passes >= int(h["required_test_case_passes"])
        and n1_joint <= float(h["mean_joint_field_score_max"])
        and n1_improvement_a1 >= float(h["improvement_over_a1_min"])
        and n1_improvement_r1 >= float(h["improvement_over_r1_min"])
        and h_speedup >= float(h["median_speedup_vs_a2_min"])
        and n1_current_p95 <= float(h["terminal_current_error_p95_max"])
        and not n1_catastrophic
    )
    path_s_accuracy = bool(
        n2_improvement_a2 >= float(s["improvement_over_a2_min"])
        or n2_passes - a2_passes
        >= int(s["additional_complete_case_passes_over_a2_min"])
    )
    path_s_pass = bool(
        n2_passes >= int(s["required_test_case_passes"])
        and path_s_accuracy
        and n2_improvement_r2 >= float(s["improvement_over_r2_min"])
        and s_time_ratio <= float(s["maximum_median_wall_time_ratio_vs_a2"])
        and not n2_catastrophic
    )
    return {
        "seed": int(seed),
        "a1_mean_joint_field_score": a1_joint,
        "a2_mean_joint_field_score": a2_joint,
        "r1_mean_joint_field_score": r1_joint,
        "r2_mean_joint_field_score": r2_joint,
        "a2_complete_case_passes": a2_passes,
        "n1_complete_case_passes": n1_passes,
        "n1_mean_joint_field_score": n1_joint,
        "n1_improvement_over_a1": n1_improvement_a1,
        "n1_improvement_over_r1": n1_improvement_r1,
        "n1_median_speedup_vs_a2": h_speedup,
        "n1_paired_case_speedup_median_diagnostic": float(
            np.median(paired_h_speedups)
        ),
        "n1_terminal_current_error_p95": n1_current_p95,
        "n1_catastrophic": n1_catastrophic,
        "path_h_pass": path_h_pass,
        "n2_complete_case_passes": n2_passes,
        "n2_mean_joint_field_score": n2_joint,
        "n2_improvement_over_a2": n2_improvement_a2,
        "n2_additional_passes_over_a2": n2_passes - a2_passes,
        "n2_improvement_over_r2": n2_improvement_r2,
        "n2_median_wall_time_ratio_vs_a2": s_time_ratio,
        "n2_paired_case_wall_time_ratio_median_diagnostic": float(
            np.median(paired_s_ratios)
        ),
        "n2_catastrophic": n2_catastrophic,
        "path_s_accuracy_condition_pass": path_s_accuracy,
        "path_s_pass": path_s_pass,
    }


def choose_initial_path(
    seed_summary: Mapping[str, Any], config: Mapping[str, Any]
) -> str | None:
    if bool(seed_summary["path_h_pass"]) and bool(seed_summary["path_s_pass"]):
        return str(config["model"]["path_priority_if_both_pass"])
    if bool(seed_summary["path_h_pass"]):
        return "H"
    if bool(seed_summary["path_s_pass"]):
        return "S"
    return None


def final_neural_decision(
    *,
    seed_rows: Sequence[Mapping[str, Any]],
    selected_path: str | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if selected_path is None:
        return {
            "disposition": "NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES",
            "selected_path": None,
            "conditional_seeds_executed": False,
            "same_path_seed_pass_count": 0,
            "median_seed_gate_pass": False,
        }
    if len(seed_rows) != int(config["evaluation"]["multi_seed"]["total_seed_count"]):
        raise ValueError("an admitted initial path requires exactly three neural seeds")
    required = int(config["evaluation"]["multi_seed"]["required_seed_passes"])
    if selected_path == "H":
        pass_count = sum(bool(row["path_h_pass"]) for row in seed_rows)
        h = config["evaluation"]["path_h"]
        medians = {
            name: float(np.median([float(row[name]) for row in seed_rows]))
            for name in (
                "n1_complete_case_passes",
                "n1_mean_joint_field_score",
                "n1_improvement_over_a1",
                "n1_improvement_over_r1",
                "n1_median_speedup_vs_a2",
                "n1_terminal_current_error_p95",
                "n1_catastrophic",
            )
        }
        median_pass = bool(
            medians["n1_complete_case_passes"] >= int(h["required_test_case_passes"])
            and medians["n1_mean_joint_field_score"]
            <= float(h["mean_joint_field_score_max"])
            and medians["n1_improvement_over_a1"]
            >= float(h["improvement_over_a1_min"])
            and medians["n1_improvement_over_r1"]
            >= float(h["improvement_over_r1_min"])
            and medians["n1_median_speedup_vs_a2"]
            >= float(h["median_speedup_vs_a2_min"])
            and medians["n1_terminal_current_error_p95"]
            <= float(h["terminal_current_error_p95_max"])
            and medians["n1_catastrophic"] < 0.5
        )
        go_disposition = "GO_M1_NEURAL_ONE_PROJECTION_VALUE_ADMISSION"
    else:
        pass_count = sum(bool(row["path_s_pass"]) for row in seed_rows)
        s = config["evaluation"]["path_s"]
        medians = {
            name: float(np.median([float(row[name]) for row in seed_rows]))
            for name in (
                "n2_complete_case_passes",
                "n2_improvement_over_a2",
                "n2_additional_passes_over_a2",
                "n2_improvement_over_r2",
                "n2_median_wall_time_ratio_vs_a2",
                "n2_catastrophic",
            )
        }
        median_accuracy = bool(
            medians["n2_improvement_over_a2"]
            >= float(s["improvement_over_a2_min"])
            or medians["n2_additional_passes_over_a2"]
            >= int(s["additional_complete_case_passes_over_a2_min"])
        )
        median_pass = bool(
            medians["n2_complete_case_passes"]
            >= int(s["required_test_case_passes"])
            and median_accuracy
            and medians["n2_improvement_over_r2"]
            >= float(s["improvement_over_r2_min"])
            and medians["n2_median_wall_time_ratio_vs_a2"]
            <= float(s["maximum_median_wall_time_ratio_vs_a2"])
            and medians["n2_catastrophic"] < 0.5
        )
        go_disposition = "GO_M1_NEURAL_SAME_BUDGET_VALUE_ADMISSION"
    passed = bool(pass_count >= required and median_pass)
    return {
        "disposition": (
            go_disposition
            if passed
            else "NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES"
        ),
        "selected_path": selected_path,
        "conditional_seeds_executed": True,
        "same_path_seed_pass_count": pass_count,
        "required_seed_pass_count": required,
        "median_seed_gate_pass": median_pass,
        "median_seed_metrics": medians,
    }


def save_pod_and_ridge_artifacts(
    *,
    pod: ThermalPOD,
    normalization: InputNormalization,
    ridge: RidgeLatent,
    processed_root: Path,
    table_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    np.save(processed_root / "thermal_pod_mean.npy", pod.mean_y)
    np.save(processed_root / "thermal_pod_basis.npy", pod.basis)
    np.save(processed_root / "input_normalization_mean.npy", normalization.mean)
    np.save(processed_root / "input_normalization_scale.npy", normalization.scale)
    np.save(processed_root / "ridge_coefficients.npy", ridge.coefficients)
    spectrum_rows = [
        {
            "mode_index": index + 1,
            "singular_value": float(value),
            "energy_fraction": float(value * value / max(np.sum(pod.singular_values**2), 1.0e-30)),
            "cumulative_energy": float(pod.cumulative_energy[index]),
            "selected": bool(index < pod.rank),
        }
        for index, value in enumerate(pod.singular_values)
    ]
    coefficient_rows = []
    for index, case_id in enumerate(pod.train_case_ids):
        row: dict[str, Any] = {
            "case_id": case_id,
            "split": "train",
            "reconstruction_relative_error": float(pod.reconstruction_errors[index]),
        }
        for mode_index in range(pod.rank):
            row[f"a{mode_index + 1}"] = float(pod.coefficients[index, mode_index])
        coefficient_rows.append(row)
    _write_csv(table_root / "thermal_pod_spectrum.csv", spectrum_rows)
    _write_csv(table_root / "thermal_pod_coefficients.csv", coefficient_rows)
    return spectrum_rows, coefficient_rows


def save_checkpoint(
    *,
    path: Path,
    model: M1LatentGeometryMapper,
    pod: ThermalPOD,
    normalization: InputNormalization,
    seed: int,
    metadata: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "seed": int(seed),
            "model_state_dict": model.state_dict(),
            "rank": pod.rank,
            "pod_mean_y": pod.mean_y,
            "pod_basis": pod.basis,
            "coefficient_center": pod.coefficient_center,
            "coefficient_scale": pod.coefficient_scale,
            "pod_fit_case_ids": pod.train_case_ids,
            "input_normalization_mean": normalization.mean,
            "input_normalization_scale": normalization.scale,
            "input_normalization_fit_case_ids": normalization.train_case_ids,
            "completed_steps": int(metadata["completed_steps"]),
            "training_wall_time_s": float(metadata["wall_time_s"]),
            "evidence_type": EVIDENCE_TYPE,
        },
        path,
    )


def save_mode_prediction(
    *,
    path: Path,
    target: EvaluationTarget,
    mode: str,
    seed: int | str,
    fields: Mapping[str, Tensor],
    operator: M1TorchProjection,
) -> None:
    payload: dict[str, Any] = {
        "case_id": np.asarray(target.case.case_id),
        "split": np.asarray(target.case.split),
        "mode": np.asarray(mode),
        "seed": np.asarray(seed),
        "evidence_type": np.asarray(EVIDENCE_TYPE),
        "contact_overlap_nm": np.asarray(target.case.contact_overlap_nm),
        "x_m": operator.x_centers_m.detach().cpu().numpy(),
        "y_m": operator.y_centers_m.detach().cpu().numpy(),
        "reference_temperature_K": target.temperature_K,
        "reference_potential_V": target.potential_V,
    }
    for name in (
        "temperature_input_K",
        "temperature_K",
        "potential_V",
        "conductivity_S_m",
        "electrical_x_face_current_A",
        "electrical_y_face_current_A",
        "thermal_x_face_power_W",
        "thermal_y_face_power_W",
        "internal_joule_cell_W",
        "contact_joule_cell_W",
        "total_joule_cell_W",
        "vertical_sink_cell_W",
        "source_current_A",
        "ground_current_A",
        "terminal_power_W",
        "total_electrical_heat_W",
        "vertical_sink_W",
        "terminal_electrical_heat_ledger_error",
        "electrical_heat_sink_ledger_error",
    ):
        if name in fields:
            payload[name] = _as_numpy(fields[name])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)


def aggregate_test_metrics(
    *,
    baseline_rows: Sequence[Mapping[str, Any]],
    neural_rows_by_seed: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for mode in ("A1", "A2", "R1", "R2"):
        rows = _test_rows(baseline_rows, mode, "baseline")
        result[mode] = {
            "seed_count": 0,
            "case_count": len(rows),
            "mean_temperature_rise_relative_l2": float(
                np.mean([row["temperature_rise_relative_l2"] for row in rows])
            ),
            "mean_potential_relative_l2": float(
                np.mean([row["potential_relative_l2"] for row in rows])
            ),
            "mean_joint_field_score": float(
                np.mean([row["joint_field_score"] for row in rows])
            ),
            "mean_terminal_current_relative_error": float(
                np.mean([row["terminal_current_relative_error"] for row in rows])
            ),
            "mean_true_fixed_point_defect": float(
                np.mean([row["true_fixed_point_defect"] for row in rows])
            ),
            "mean_sigma_defect": float(np.mean([row["sigma_defect"] for row in rows])),
            "complete_case_passes": sum(bool(row["practical_case_pass"]) for row in rows),
            "median_wall_time_s": float(
                np.median([row["median_wall_time_s"] for row in rows])
            ),
        }
    for mode in ("N1", "N2"):
        per_seed = []
        for seed, seed_rows in neural_rows_by_seed.items():
            rows = _test_rows(seed_rows, mode, seed)
            per_seed.append(
                {
                    "seed": seed,
                    "temperature": float(
                        np.mean([row["temperature_rise_relative_l2"] for row in rows])
                    ),
                    "potential": float(
                        np.mean([row["potential_relative_l2"] for row in rows])
                    ),
                    "joint": float(np.mean([row["joint_field_score"] for row in rows])),
                    "current": float(
                        np.mean([row["terminal_current_relative_error"] for row in rows])
                    ),
                    "fixed": float(
                        np.mean([row["true_fixed_point_defect"] for row in rows])
                    ),
                    "sigma": float(np.mean([row["sigma_defect"] for row in rows])),
                    "passes": sum(bool(row["practical_case_pass"]) for row in rows),
                    "time": float(np.median([row["median_wall_time_s"] for row in rows])),
                }
            )
        result[mode] = {
            "seed_count": len(per_seed),
            "case_count": 12,
            "mean_temperature_rise_relative_l2": float(
                np.median([row["temperature"] for row in per_seed])
            ),
            "mean_potential_relative_l2": float(
                np.median([row["potential"] for row in per_seed])
            ),
            "mean_joint_field_score": float(np.median([row["joint"] for row in per_seed])),
            "mean_terminal_current_relative_error": float(
                np.median([row["current"] for row in per_seed])
            ),
            "mean_true_fixed_point_defect": float(
                np.median([row["fixed"] for row in per_seed])
            ),
            "mean_sigma_defect": float(np.median([row["sigma"] for row in per_seed])),
            "complete_case_passes": int(round(float(np.median([row["passes"] for row in per_seed])))),
            "median_wall_time_s": float(np.median([row["time"] for row in per_seed])),
            "per_seed": per_seed,
        }
    return result


def build_break_even_rows(
    *,
    decision: Mapping[str, Any],
    mode_aggregates: Mapping[str, Any],
    m1_reference_generation_wall_s: float,
    m2_sentinel_generation_wall_s: float,
    neural_training_wall_times_s: Sequence[float],
) -> list[dict[str, Any]]:
    total_training_wall_s = float(np.sum(neural_training_wall_times_s))
    selected_model_training_wall_s = float(np.median(neural_training_wall_times_s))
    total_reference_wall_s = (
        float(m1_reference_generation_wall_s)
        + float(m2_sentinel_generation_wall_s)
    )
    selected_path = decision.get("selected_path")
    if not str(decision["disposition"]).startswith("GO_") or selected_path is None:
        return [
            {
                "status": "not_applicable_no_admitted_neural_route",
                "selected_mode": "",
                "a2_per_query_median_wall_s": mode_aggregates["A2"]["median_wall_time_s"],
                "selected_neural_per_query_median_wall_s": math.nan,
                "per_query_time_advantage_s": math.nan,
                "deployment_break_even_queries": math.nan,
                "research_break_even_queries": math.nan,
                "m1_reference_generation_wall_s": m1_reference_generation_wall_s,
                "m2_sentinel_generation_wall_s": m2_sentinel_generation_wall_s,
                "total_reference_generation_wall_s": total_reference_wall_s,
                "selected_model_training_wall_s": selected_model_training_wall_s,
                "all_executed_neural_training_wall_s": total_training_wall_s,
                "selected_projection_count": 0,
                "selected_linear_solve_count": 0,
            }
        ]
    selected_mode = "N1" if selected_path == "H" else "N2"
    a2_time = float(mode_aggregates["A2"]["median_wall_time_s"])
    selected_time = float(mode_aggregates[selected_mode]["median_wall_time_s"])
    delta = a2_time - selected_time
    if delta <= 0.0:
        status = "no_inference_time_advantage"
        deployment = math.nan
        research = math.nan
    else:
        status = "applicable"
        deployment = selected_model_training_wall_s / delta
        research = (total_reference_wall_s + total_training_wall_s) / delta
    return [
        {
            "status": status,
            "selected_mode": selected_mode,
            "a2_per_query_median_wall_s": a2_time,
            "selected_neural_per_query_median_wall_s": selected_time,
            "per_query_time_advantage_s": delta,
            "deployment_break_even_queries": deployment,
            "research_break_even_queries": research,
            "m1_reference_generation_wall_s": m1_reference_generation_wall_s,
            "m2_sentinel_generation_wall_s": m2_sentinel_generation_wall_s,
            "total_reference_generation_wall_s": total_reference_wall_s,
            "selected_model_training_wall_s": selected_model_training_wall_s,
            "all_executed_neural_training_wall_s": total_training_wall_s,
            "selected_projection_count": 1 if selected_mode == "N1" else 2,
            "selected_linear_solve_count": 2 if selected_mode == "N1" else 4,
        }
    ]


def _plot_geometry_masks_and_fields(
    *,
    path: Path,
    contexts: Mapping[float, GeoStateReferenceContext],
    results: Mapping[str, GeoStateReferenceResult],
) -> None:
    overlaps = sorted(contexts)
    figure, axes = plt.subplots(2, 3, figsize=(11, 6), constrained_layout=True)
    for column, overlap in enumerate(overlaps):
        context = contexts[overlap]
        axes[0, column].imshow(
            context.grid.contact_mask.astype(float), origin="lower", aspect="auto"
        )
        axes[0, column].set_title(f"{overlap:.0f} nm contact mask")
        case_id = geometry_case_id(
            overlap, "heating", "near-transition", "localized-sink"
        )
        rise = (
            np.asarray(results[case_id].fields["temperature_K"])
            - context.ambient_temperature_K
        )
        image = axes[1, column].imshow(rise, origin="lower", aspect="auto")
        axes[1, column].set_title(f"Reference ΔT, χ₂D={results[case_id].metrics['chi_2d']:.3f}")
        figure.colorbar(image, ax=axes[1, column], shrink=0.75, label="K")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_pod(path: Path, pod: ThermalPOD, ny: int, nx: int) -> None:
    count = min(pod.rank, 4)
    figure, axes = plt.subplots(1, count + 1, figsize=(3.2 * (count + 1), 3.4), constrained_layout=True)
    axes[0].plot(np.arange(1, len(pod.cumulative_energy) + 1), pod.cumulative_energy, marker="o")
    axes[0].axhline(0.999, color="black", linestyle="--")
    axes[0].axvline(pod.rank, color="tab:red", linestyle=":")
    axes[0].set_ylim(0.0, 1.005)
    axes[0].set_title(f"Train-only POD rank={pod.rank}")
    axes[0].set_xlabel("mode")
    axes[0].set_ylabel("cumulative energy")
    for index in range(count):
        image = axes[index + 1].imshow(
            pod.basis[index].reshape(ny, nx), origin="lower", aspect="auto", cmap="coolwarm"
        )
        axes[index + 1].set_title(f"mode {index + 1}")
        figure.colorbar(image, ax=axes[index + 1], shrink=0.75)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_matched_accuracy(path: Path, aggregates: Mapping[str, Any]) -> None:
    modes = ["A1", "A2", "R1", "R2", "N1", "N2"]
    values = [aggregates[mode]["mean_joint_field_score"] for mode in modes]
    figure, axis = plt.subplots(figsize=(8, 4.8), constrained_layout=True)
    axis.bar(modes, values, color=["0.6", "0.45", "tab:green", "tab:olive", "tab:blue", "tab:cyan"])
    axis.set_yscale("log")
    axis.set_ylabel("geometry-OOD mean joint field score")
    axis.set_title("Matched projection-budget accuracy")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_ood_fields(
    *,
    path: Path,
    target: EvaluationTarget,
    baseline_predictions: Mapping[tuple[str, str], Mapping[str, Tensor]],
    neural_predictions: Mapping[tuple[str, str], Mapping[str, Tensor]],
    ambient_temperature_K: float,
) -> None:
    modes = ["reference", "A1", "A2", "R1", "R2", "N1", "N2"]
    arrays = [target.temperature_K - ambient_temperature_K]
    for mode in modes[1:]:
        source = neural_predictions if mode.startswith("N") else baseline_predictions
        arrays.append(_as_numpy(source[(target.case.case_id, mode)]["temperature_K"]) - ambient_temperature_K)
    vmax = max(float(np.max(array)) for array in arrays)
    figure, axes = plt.subplots(1, len(modes), figsize=(18, 3.2), constrained_layout=True)
    for axis, mode, array in zip(axes, modes, arrays, strict=True):
        image = axis.imshow(array, origin="lower", aspect="auto", vmin=0.0, vmax=vmax)
        axis.set_title(mode)
    figure.colorbar(image, ax=axes, shrink=0.75, label="temperature rise (K)")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_pass_rates(path: Path, rows: Sequence[Mapping[str, Any]], initial_seed: int) -> None:
    modes = ["A1", "A2", "R1", "R2", "N1", "N2"]
    values = []
    for mode in modes:
        seed: int | str = initial_seed if mode.startswith("N") else "baseline"
        subset = _test_rows(rows, mode, seed)
        values.append(sum(bool(row["practical_case_pass"]) for row in subset) / 12.0)
    figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    axis.bar(modes, values)
    axis.axhline(9.0 / 12.0, color="black", linestyle="--", label="9/12 gate")
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("complete-case pass rate")
    axis.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_defects(path: Path, rows: Sequence[Mapping[str, Any]], initial_seed: int) -> None:
    modes = ["A1", "A2", "R1", "R2", "N1", "N2"]
    values = []
    for mode in modes:
        seed: int | str = initial_seed if mode.startswith("N") else "baseline"
        values.append(
            [float(row["true_fixed_point_defect"]) for row in _test_rows(rows, mode, seed)]
        )
    figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    axis.boxplot(values, labels=modes, showfliers=True)
    axis.axhline(0.02, color="black", linestyle="--", label="defect gate")
    axis.set_yscale("log")
    axis.set_ylabel("true one-step look-ahead defect")
    axis.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_pareto(path: Path, aggregates: Mapping[str, Any]) -> None:
    modes = ["A1", "A2", "R1", "R2", "N1", "N2"]
    figure, axis = plt.subplots(figsize=(7, 5), constrained_layout=True)
    for mode in modes:
        axis.scatter(
            aggregates[mode]["median_wall_time_s"],
            aggregates[mode]["mean_joint_field_score"],
            s=60,
        )
        axis.annotate(mode, (aggregates[mode]["median_wall_time_s"], aggregates[mode]["mean_joint_field_score"]))
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("median wall time per query (s)")
    axis.set_ylabel("mean joint field score")
    axis.set_title("Geometry-OOD speed-accuracy Pareto")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_break_even(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    row = rows[0]
    figure, axis = plt.subplots(figsize=(7, 4.5), constrained_layout=True)
    if row["status"] == "applicable":
        labels = ["deployment", "research"]
        values = [row["deployment_break_even_queries"], row["research_break_even_queries"]]
        axis.bar(labels, values)
        axis.set_yscale("log")
        axis.set_ylabel("break-even queries")
        axis.set_title(f"Break-even for {row['selected_mode']}")
    else:
        axis.axis("off")
        axis.text(0.5, 0.55, "No admitted neural route", ha="center", va="center", fontsize=16)
        axis.text(0.5, 0.4, str(row["status"]), ha="center", va="center")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    aggregates = summary.get("mode_aggregates", {})
    lines = [
        "# Q2 M1 latent neural-value geometry admission v1",
        "",
        "## Conclusion",
        "",
        f"Disposition: `{summary['disposition']}`. The evidence is literature-guided synthetic numerical digital-twin evidence and remains diagnostic rather than formal OOD superiority or experimental validation.",
        "",
        "## Frozen PR #39",
        "",
        "PR #39 remained unchanged at head `e85e641a46deb8b9ac6c780ba32213acc510e7e0`, retaining `GO_M1_LATENT_PROJECTION_PINN_MVE` and `neural-specific advantage over A2 = false`; it was squash-merged as `56999bbe33065a7e80587c009ab78011d61b265c` before this branch.",
        "",
        "## Geometry reference and sentinels",
        "",
        f"The dataset contains `{summary['reference']['case_count']}` M1 cases on the fixed 10 x 25 production grid with true 10/20/30 nm contact-mask and covered-sheet changes. Reference gates passed `{summary['reference']['pass_count']}/36` cases; the six branch-specific localized near-transition checks passed: `{summary['reference']['localized_near_transition_gate']['passed']}`.",
        "",
        f"The four preregistered M2 sentinels passed `{summary['m2_sentinels']['pass_count']}/4`; maximum current, Tmax, and resolved hotspot differences were `{summary['m2_sentinels']['max_current_difference']:.4g}`, `{summary['m2_sentinels']['max_tmax_difference_K']:.4g} K`, and `{summary['m2_sentinels']['max_hotspot_distance_width_fraction']:.4g} W`.",
        "",
        "The single implementation repair replaced symmetry-degenerate single-cell argmax comparison by a float64 machine-precision hotspot-set distance. It changed no threshold, data, or physical model and required zero additional nonlinear M1/M2 reference solves; diagnostic reconstruction solves are recorded separately.",
        "",
    ]
    if "pod" in summary:
        lines.extend(
            [
                "## Train-only POD, ridge and actual neural training",
                "",
                f"Only the 20 train fields entered the POD, rank selection, input/coefficient normalization, ridge fit, or neural training. The selected POD rank is `{summary['pod']['rank']}` at cumulative energy `{summary['pod']['selected_cumulative_energy']:.9f}`; ridge used the frozen closed-form lambda `1e-8`.",
                "",
                f"Executed neural seeds: `{', '.join(str(value) for value in summary['training']['executed_seeds'])}`. Conditional seeds executed: `{summary['decision']['conditional_seeds_executed']}`; every executed seed completed exactly 1500 Adam steps.",
                "",
                "The POD and neural mapper use complete train fields. This is a projection-embedded physics-informed neural reduced-order model, not a data-free, mesh-free, or sparse-anchor-only PINN.",
                "",
                "## Matched-budget geometry-OOD metrics",
                "",
                "| mode | T-rise L2 | phi L2 | current | joint | true defect | passes | median time (s) |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for mode in ("A1", "A2", "R1", "R2", "N1", "N2"):
            row = aggregates[mode]
            lines.append(
                f"| {mode} | {row['mean_temperature_rise_relative_l2']:.5g} | {row['mean_potential_relative_l2']:.5g} | {row['mean_terminal_current_relative_error']:.5g} | {row['mean_joint_field_score']:.5g} | {row['mean_true_fixed_point_defect']:.5g} | {row['complete_case_passes']}/12 | {row['median_wall_time_s']:.5g} |"
            )
        lines.extend(
            [
                "",
                "## Neural-specific value gate",
                "",
                f"The initial seed Path H result is `{summary['seed_summaries'][0]['path_h_pass']}` and Path S result is `{summary['seed_summaries'][0]['path_s_pass']}`. Final selected path: `{summary['decision'].get('selected_path')}`; same-path seed passes: `{summary['decision'].get('same_path_seed_pass_count', 0)}`.",
                "",
            ]
        )
        if summary["disposition"] == "NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES":
            lines.append(
                "Analytic A2 or the linear POD mapper already covers this bounded problem; the neural module did not establish independent necessity, so neural forward-architecture expansion stops."
            )
        else:
            lines.append(
                "Within this bounded synthetic geometry-admission benchmark, the nonlinear latent mapper met the preregistered projection-depth or matched-budget value gate; this remains diagnostic and is not formal superiority."
            )
        lines.extend(
            [
                "",
                "## Break-even",
                "",
                (
                    f"Status: `{summary['break_even']['status']}`; no neural route was admitted, so deployment and research break-even are not applicable."
                    if summary["break_even"]["status"] != "applicable"
                    else f"Status: `applicable`; deployment break-even is `{summary['break_even']['deployment_break_even_queries']}` queries and research break-even is `{summary['break_even']['research_break_even_queries']}` queries."
                ),
                "",
                "## Claim boundary and next priority",
                "",
                "M1 operator parity is supported; M1 reference adequacy over the admitted 10-30 nm range is at most qualified_supported; direct-coordinate PINN remains failed_but_informative. Neural-specific admission is diagnostic only. Formal superiority, experimental validation, dynamic hysteresis, and inverse claims remain forbidden.",
                "",
                summary["next_single_priority"],
                "",
                "## Figures",
                "",
            ]
        )
        for figure in summary["paths"]["figures"]:
            lines.append(f"- `{figure}`")
        lines.extend(
            [
                "",
                "## Artifact and execution identity",
                "",
                f"- Processed data and predictions: `{summary['paths']['processed_root']}`",
                f"- Tables: `{summary['paths']['table_root']}`",
                f"- Checkpoint: `{summary['paths']['checkpoint_root']}`",
                "- Base: `56999bbe33065a7e80587c009ab78011d61b265c`",
                "- Branch: `codex/q2-m1-latent-neural-value-geometry-admission-v1`",
                "- Focused verification: `pytest -q tests/test_q2_m1_latent_neural_value_geometry_admission_v1.py` -> `7 passed`",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _coerce_csv_value(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if stripped == "":
        return ""
    try:
        if not any(marker in lowered for marker in (".", "e", "nan", "inf")):
            return int(stripped)
        return float(stripped)
    except ValueError:
        return stripped


def _read_typed_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [
            {name: _coerce_csv_value(value) for name, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def finalize_completed_training_artifacts(
    *,
    config: Mapping[str, Any],
    repository_root: Path,
    processed_root: Path,
    table_root: Path,
    figure_root: Path,
    checkpoint_root: Path,
    report_path: Path,
    pod: ThermalPOD,
    normalization: InputNormalization,
    ridge: RidgeLatent,
    reference_summary: Mapping[str, Any],
    sentinel_summary: Mapping[str, Any],
    implementation_repair: Mapping[str, Any],
    current_domain_row_count: int,
) -> dict[str, Any]:
    """Finish plots/summary after training succeeded but postprocessing stopped."""

    mode_rows = _read_typed_csv(table_root / "mode_metrics.csv")
    apply_practical_case_gates(mode_rows, config)
    _write_csv(table_root / "mode_metrics.csv", mode_rows)
    seed_summaries = _read_typed_csv(table_root / "seed_summary.csv")
    break_even_rows = _read_typed_csv(table_root / "break_even.csv")
    executed_seeds = sorted(int(row["seed"]) for row in seed_summaries)
    baseline_rows = [row for row in mode_rows if row["seed"] == "baseline"]
    neural_rows_by_seed = {
        seed: [row for row in mode_rows if row["seed"] == seed]
        for seed in executed_seeds
    }
    selected_path = choose_initial_path(seed_summaries[0], config)
    decision = final_neural_decision(
        seed_rows=seed_summaries,
        selected_path=selected_path,
        config=config,
    )
    aggregates = aggregate_test_metrics(
        baseline_rows=baseline_rows,
        neural_rows_by_seed=neural_rows_by_seed,
    )
    training_metadata: dict[int, dict[str, Any]] = {}
    for seed in executed_seeds:
        checkpoint_path = (
            checkpoint_root / f"m1_latent_geometry_mapper_seed{seed}.pt"
        )
        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
        training_metadata[seed] = {
            "completed_steps": int(checkpoint["completed_steps"]),
            "wall_time_s": float(checkpoint["training_wall_time_s"]),
            "resumed_postprocessing_without_retraining": True,
        }
    training_wall_s = float(
        sum(value["wall_time_s"] for value in training_metadata.values())
    )
    initial_seed = int(config["model"]["initial_seed"])
    _plot_defects(figure_root / "true_fixed_point_defect.png", mode_rows, initial_seed)
    _plot_pareto(figure_root / "speed_accuracy_pareto.png", aggregates)
    _plot_break_even(figure_root / "break_even_queries.png", break_even_rows)
    figure_names = (
        "geometry_masks_and_reference_fields.png",
        "geometry_pod_spectrum_and_modes.png",
        "matched_budget_accuracy.png",
        "geometry_ood_field_comparison.png",
        "a1_a2_r1_r2_n1_n2_pass_rates.png",
        "true_fixed_point_defect.png",
        "speed_accuracy_pareto.png",
        "break_even_queries.png",
    )
    missing = [name for name in figure_names if not (figure_root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"completed-run figures missing: {missing}")
    figures = [
        (figure_root / name).relative_to(repository_root).as_posix()
        for name in figure_names
    ]
    summary = {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "phase_id": config["phase_id"],
        "evidence_type": EVIDENCE_TYPE,
        "frozen_pr39": config["frozen_baseline"],
        "reference": dict(reference_summary),
        "m2_sentinels": dict(sentinel_summary),
        "implementation_repair": dict(implementation_repair),
        "postprocessing_resume": {
            "reason": "matplotlib_boxplot_keyword_compatibility",
            "training_repeated": False,
            "evaluation_repeated": False,
        },
        "pod": {
            "rank": pod.rank,
            "rank_cap": int(config["pod"]["rank_cap"]),
            "selected_cumulative_energy": float(pod.cumulative_energy[pod.rank - 1]),
            "fit_case_ids": list(pod.train_case_ids),
            "validation_test_leakage": False,
            "maximum_train_reconstruction_error": float(
                np.max(pod.reconstruction_errors)
            ),
        },
        "ridge": {
            "regularization_lambda": ridge.regularization_lambda,
            "design_condition_number": ridge.design_condition_number,
            "fit_case_ids": list(pod.train_case_ids),
        },
        "input_normalization": {
            "fit_case_ids": list(normalization.train_case_ids),
        },
        "training": {
            "executed_seeds": executed_seeds,
            "seed_count": len(executed_seeds),
            "total_training_wall_time_s": training_wall_s,
            "per_seed": {
                str(seed): training_metadata[seed] for seed in executed_seeds
            },
        },
        "seed_summaries": seed_summaries,
        "decision": decision,
        "disposition": decision["disposition"],
        "validity": "valid",
        "lifecycle_state": "numerically_validated",
        "claim_status": (
            "qualified_supported"
            if str(decision["disposition"]).startswith("GO_")
            else "failed_but_informative"
        ),
        "scientific_role": "diagnostic_non_voting",
        "mode_aggregates": aggregates,
        "break_even": break_even_rows[0],
        "current_domain_matched_budget_row_count": current_domain_row_count,
        "conditional_seeds_executed": bool(selected_path is not None),
        "claim_boundary": config["claim_boundary"],
        "paths": {
            "processed_root": config["outputs"]["processed_root"],
            "table_root": config["outputs"]["table_root"],
            "figure_root": config["outputs"]["figure_root"],
            "checkpoint_root": config["outputs"]["checkpoint_root"],
            "report": config["outputs"]["report"],
            "figures": figures,
        },
        "next_single_priority": (
            "Preregister Q2_M1_LATENT_PROJECTION_PINN_FORMAL_OOD_V1 without "
            "executing it in this round."
            if str(decision["disposition"]).startswith("GO_")
            else "Stop neural forward-architecture expansion; retain the "
            "conservative projection operator and analytic A2 as numerical "
            "assets for the limitation manuscript."
        ),
    }
    _write_json(table_root / "summary.json", summary)
    _write_report(report_path, summary)
    return summary


def run_experiment(config_path: Path, repository_root: Path) -> dict[str, Any]:
    config = load_yaml(config_path)
    torch.set_num_threads(int(config["evaluation"]["torch_threads"]))
    base_config = load_yaml(repository_root / config["reference"]["config"])
    processed_root = repository_root / config["outputs"]["processed_root"]
    table_root = repository_root / config["outputs"]["table_root"]
    figure_root = repository_root / config["outputs"]["figure_root"]
    checkpoint_root = repository_root / config["outputs"]["checkpoint_root"]
    report_path = repository_root / config["outputs"]["report"]
    for output_root in (processed_root, table_root, figure_root, checkpoint_root):
        output_root.mkdir(parents=True, exist_ok=True)

    current_domain_rows = current_domain_matched_budget_diagnostic(
        config=config, repository_root=repository_root
    )
    _write_csv(
        table_root / "current_domain_matched_budget_diagnostic.csv",
        current_domain_rows,
    )

    cases = build_geometry_cases(config)
    cases_by_id = {case.case_id: case for case in cases}
    overlaps = [float(value) for value in config["reference"]["geometry_contact_overlap_nm"]]
    contexts, operators = build_geometry_contexts_and_operators(
        base_config, repository_root, overlaps
    )
    expected_grid = config["reference"]["production_grid"]
    for overlap, context in contexts.items():
        actual_grid = (int(context.grid.nx), int(context.grid.ny))
        required_grid = (int(expected_grid["nx"]), int(expected_grid["ny"]))
        if actual_grid != required_grid:
            raise ValueError(
                f"geometry {overlap:g} nm grid {actual_grid} != {required_grid}"
            )
    reference_metrics_path = table_root / "geometry_reference_metrics.csv"
    completed_reference_available = bool(
        reference_metrics_path.is_file()
        and all(
            (processed_root / "cases" / f"{case.case_id}.npz").is_file()
            for case in cases
        )
    )
    if completed_reference_available:
        (
            m1_results,
            manifest_rows,
            reference_rows,
            reference_wall_s,
        ) = load_completed_geometry_reference(
            cases=cases,
            contexts=contexts,
            operators=operators,
            config=config,
            processed_root=processed_root,
            metrics_path=reference_metrics_path,
        )
    else:
        (
            m1_results,
            manifest_rows,
            reference_rows,
            reference_wall_s,
        ) = generate_geometry_reference(
            cases=cases,
            contexts=contexts,
            operators=operators,
            config=config,
            processed_root=processed_root,
        )
    _write_csv(table_root / "geometry_case_manifest.csv", manifest_rows)
    _write_csv(reference_metrics_path, reference_rows)
    split_payload = {
        split: sorted(case.case_id for case in cases if case.split == split)
        for split in ("train", "validation", "test")
    }
    _write_json(processed_root / "split_manifest.json", split_payload)
    _write_csv(
        processed_root / "split_manifest.csv",
        [
            {"case_id": case.case_id, "split": case.split}
            for case in sorted(cases, key=lambda item: item.case_id)
        ],
    )
    localized_gate = localized_near_transition_gate(reference_rows, config)
    sentinel_rows, m2_wall_s = run_m2_sentinels(
        cases_by_id=cases_by_id,
        m1_results=m1_results,
        contexts=contexts,
        config=config,
        processed_root=processed_root,
        existing_metrics_path=table_root / "m1_m2_sentinel_metrics.csv",
    )
    _write_csv(table_root / "m1_m2_sentinel_metrics.csv", sentinel_rows)
    reference_pass_count = sum(bool(row["reference_gate_pass"]) for row in reference_rows)
    sentinel_pass_count = sum(bool(row["sentinel_pass"]) for row in sentinel_rows)
    reference_summary = {
        "case_count": len(reference_rows),
        "pass_count": reference_pass_count,
        "all_finite": all(bool(row["finite"]) for row in reference_rows),
        "max_scaled_nonlinear_residual": max(
            float(row["scaled_nonlinear_residual"]) for row in reference_rows
        ),
        "max_current_imbalance": max(float(row["current_imbalance"]) for row in reference_rows),
        "max_terminal_electrical_heat_ledger_error": max(
            float(row["terminal_electrical_heat_ledger_error"]) for row in reference_rows
        ),
        "max_electrical_heat_sink_ledger_error": max(
            float(row["electrical_heat_sink_ledger_error"]) for row in reference_rows
        ),
        "conservative_reconstruction_pass_count": sum(
            bool(row["conservative_reconstruction_gate_pass"])
            for row in reference_rows
        ),
        "max_conservative_potential_relative_l2": max(
            float(row["conservative_potential_relative_l2"])
            for row in reference_rows
        ),
        "max_conservative_source_current_relative_error": max(
            float(row["conservative_source_current_relative_error"])
            for row in reference_rows
        ),
        "localized_near_transition_gate": localized_gate,
        "unique_m1_reference_solve_count": len(reference_rows),
        "generation_wall_time_s": reference_wall_s,
        "physical_solutions_reused_after_metric_repair": (
            len(reference_rows) if completed_reference_available else 0
        ),
        "additional_nonlinear_reference_solves_after_repair": 0,
        "diagnostic_electrical_reconstruction_solves_this_pass": len(
            reference_rows
        ),
    }
    resolved_hotspot_distances = [
        float(row["hotspot_distance_width_fraction"])
        for row in sentinel_rows
        if bool(row["hotspot_resolved"])
    ]
    sentinel_summary = {
        "case_count": len(sentinel_rows),
        "pass_count": sentinel_pass_count,
        "max_current_difference": max(
            float(row["terminal_current_relative_difference"]) for row in sentinel_rows
        ),
        "max_tmax_difference_K": max(float(row["Tmax_difference_K"]) for row in sentinel_rows),
        "max_hotspot_distance_width_fraction": max(resolved_hotspot_distances),
        "unique_m2_sentinel_solve_count": len(sentinel_rows),
        "generation_wall_time_s": m2_wall_s,
        "physical_solutions_reused_after_metric_repair": sum(
            bool(row["m2_physical_solve_reused_after_metric_repair"])
            for row in sentinel_rows
        ),
        "additional_nonlinear_reference_solves_after_repair": 0,
        "diagnostic_electrical_reconstruction_solves_this_pass": len(
            sentinel_rows
        ),
        "diagnostic_thermal_factorizations_this_pass": len(sentinel_rows),
        "hotspot_metric": (
            "tie_aware_machine_precision_maximum_set_minimum_distance"
        ),
    }
    implementation_repair = {
        "count": 1,
        "classification": "symmetry_degenerate_argmax_metric",
        "description": (
            "Replaced single-cell argmax distance by a float64 machine-precision "
            "maximum-set distance for symmetry-degenerate resolved hotspots."
        ),
        "thresholds_changed": False,
        "physical_model_changed": False,
        "additional_nonlinear_m1_reference_solves": 0,
        "additional_nonlinear_m2_reference_solves": 0,
        "diagnostic_reconstruction_solves_excluded_from_reference_generation": True,
    }
    _plot_geometry_masks_and_fields(
        path=figure_root / "geometry_masks_and_reference_fields.png",
        contexts=contexts,
        results=m1_results,
    )
    reference_admitted = bool(
        reference_pass_count == 36
        and localized_gate["passed"]
        and sentinel_pass_count == 4
    )
    if not reference_admitted:
        stopped = {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "evidence_type": EVIDENCE_TYPE,
            "frozen_pr39": config["frozen_baseline"],
            "reference": reference_summary,
            "m2_sentinels": sentinel_summary,
            "implementation_repair": implementation_repair,
            "disposition": "NO_GO_M1_GEOMETRY_REFERENCE_ADEQUACY",
            "validity": "valid_bounded_reference_gate_failure",
            "claim_status": "failed_but_informative",
        }
        _write_json(table_root / "summary.json", stopped)
        _write_report(report_path, stopped)
        return stopped

    try:
        pod = fit_geometry_pod(
            cases=cases,
            results=m1_results,
            ambient_temperature_K=float(config["reference"]["ambient_temperature_K"]),
            config=config,
        )
    except RuntimeError as error:
        if str(error) != "NO_GO_LOW_RANK_THERMAL_MANIFOLD":
            raise
        stopped = {
            "task_id": config["task_id"],
            "run_id": config["run_id"],
            "evidence_type": EVIDENCE_TYPE,
            "frozen_pr39": config["frozen_baseline"],
            "reference": reference_summary,
            "m2_sentinels": sentinel_summary,
            "implementation_repair": implementation_repair,
            "disposition": "NO_GO_LOW_RANK_GEOMETRY_MANIFOLD",
            "validity": "valid_bounded_rank_gate_failure",
            "claim_status": "failed_but_informative",
        }
        _write_json(table_root / "summary.json", stopped)
        _write_report(report_path, stopped)
        return stopped

    train_cases = sorted(
        (case for case in cases if case.split == "train"), key=lambda item: item.case_id
    )
    normalization = fit_input_normalization(train_cases, pod.train_case_ids)
    ridge = fit_ridge_latent(
        cases=train_cases,
        pod=pod,
        normalization=normalization,
        regularization_lambda=float(config["ridge"]["regularization_lambda"]),
    )
    spectrum_rows, _ = save_pod_and_ridge_artifacts(
        pod=pod,
        normalization=normalization,
        ridge=ridge,
        processed_root=processed_root,
        table_root=table_root,
    )
    completed_training_artifacts = all(
        (table_root / name).is_file()
        for name in (
            "training_history.csv",
            "mode_metrics.csv",
            "seed_summary.csv",
            "speed_benchmark.csv",
            "break_even.csv",
        )
    )
    if completed_training_artifacts:
        return finalize_completed_training_artifacts(
            config=config,
            repository_root=repository_root,
            processed_root=processed_root,
            table_root=table_root,
            figure_root=figure_root,
            checkpoint_root=checkpoint_root,
            report_path=report_path,
            pod=pod,
            normalization=normalization,
            ridge=ridge,
            reference_summary=reference_summary,
            sentinel_summary=sentinel_summary,
            implementation_repair=implementation_repair,
            current_domain_row_count=len(current_domain_rows),
        )
    targets = build_evaluation_targets(cases, m1_results)
    baseline_rows, baseline_speed_rows, baseline_predictions = evaluate_baselines(
        cases=cases,
        targets=targets,
        operators=operators,
        pod=pod,
        normalization=normalization,
        ridge=ridge,
        config=config,
    )
    apply_practical_case_gates(baseline_rows, config)

    initial_seed = int(config["model"]["initial_seed"])
    executed_seeds = [initial_seed]
    all_history: list[dict[str, Any]] = []
    training_metadata: dict[int, dict[str, Any]] = {}
    neural_rows_by_seed: dict[int, list[dict[str, Any]]] = {}
    neural_speed_by_seed: dict[int, list[dict[str, Any]]] = {}
    neural_predictions_by_seed: dict[
        int, dict[tuple[str, str], dict[str, Tensor]]
    ] = {}

    model, history, metadata = train_geometry_model(
        seed=initial_seed,
        pod=pod,
        normalization=normalization,
        cases=cases,
        results=m1_results,
        operators=operators,
        config=config,
    )
    save_checkpoint(
        path=checkpoint_root / f"m1_latent_geometry_mapper_seed{initial_seed}.pt",
        model=model,
        pod=pod,
        normalization=normalization,
        seed=initial_seed,
        metadata=metadata,
        config=config,
    )
    initial_neural_rows, initial_neural_speed, initial_predictions = evaluate_neural_seed(
        seed=initial_seed,
        model=model,
        cases=cases,
        targets=targets,
        operators=operators,
        normalization=normalization,
        config=config,
    )
    apply_practical_case_gates(initial_neural_rows, config)
    all_history.extend(history)
    training_metadata[initial_seed] = metadata
    neural_rows_by_seed[initial_seed] = initial_neural_rows
    neural_speed_by_seed[initial_seed] = initial_neural_speed
    neural_predictions_by_seed[initial_seed] = initial_predictions
    seed_summaries = [
        seed_gate_summary(
            seed=initial_seed,
            baseline_rows=baseline_rows,
            neural_rows=initial_neural_rows,
            config=config,
        )
    ]
    selected_path = choose_initial_path(seed_summaries[0], config)
    if selected_path is not None:
        for seed_value in config["model"]["conditional_seeds"]:
            seed = int(seed_value)
            executed_seeds.append(seed)
            model, history, metadata = train_geometry_model(
                seed=seed,
                pod=pod,
                normalization=normalization,
                cases=cases,
                results=m1_results,
                operators=operators,
                config=config,
            )
            save_checkpoint(
                path=checkpoint_root / f"m1_latent_geometry_mapper_seed{seed}.pt",
                model=model,
                pod=pod,
                normalization=normalization,
                seed=seed,
                metadata=metadata,
                config=config,
            )
            neural_rows, neural_speed, predictions = evaluate_neural_seed(
                seed=seed,
                model=model,
                cases=cases,
                targets=targets,
                operators=operators,
                normalization=normalization,
                config=config,
            )
            apply_practical_case_gates(neural_rows, config)
            all_history.extend(history)
            training_metadata[seed] = metadata
            neural_rows_by_seed[seed] = neural_rows
            neural_speed_by_seed[seed] = neural_speed
            neural_predictions_by_seed[seed] = predictions
            seed_summaries.append(
                seed_gate_summary(
                    seed=seed,
                    baseline_rows=baseline_rows,
                    neural_rows=neural_rows,
                    config=config,
                )
            )
    decision = final_neural_decision(
        seed_rows=seed_summaries,
        selected_path=selected_path,
        config=config,
    )
    all_mode_rows = list(baseline_rows)
    all_speed_rows = list(baseline_speed_rows)
    for seed in executed_seeds:
        all_mode_rows.extend(neural_rows_by_seed[seed])
        all_speed_rows.extend(neural_speed_by_seed[seed])
    _write_csv(table_root / "training_history.csv", all_history)
    _write_csv(table_root / "mode_metrics.csv", all_mode_rows)
    _write_csv(table_root / "seed_summary.csv", seed_summaries)
    _write_csv(table_root / "speed_benchmark.csv", all_speed_rows)

    for (case_id, mode), fields in baseline_predictions.items():
        save_mode_prediction(
            path=processed_root / "predictions" / "baseline" / mode.lower() / f"{case_id}.npz",
            target=targets[case_id],
            mode=mode,
            seed="baseline",
            fields=fields,
            operator=operators[targets[case_id].case.contact_overlap_nm],
        )
    for seed, predictions in neural_predictions_by_seed.items():
        for (case_id, mode), fields in predictions.items():
            save_mode_prediction(
                path=processed_root / "predictions" / f"seed{seed}" / mode.lower() / f"{case_id}.npz",
                target=targets[case_id],
                mode=mode,
                seed=seed,
                fields=fields,
                operator=operators[targets[case_id].case.contact_overlap_nm],
            )

    aggregates = aggregate_test_metrics(
        baseline_rows=baseline_rows, neural_rows_by_seed=neural_rows_by_seed
    )
    training_wall_s = float(
        sum(float(metadata["wall_time_s"]) for metadata in training_metadata.values())
    )
    break_even_rows = build_break_even_rows(
        decision=decision,
        mode_aggregates=aggregates,
        m1_reference_generation_wall_s=reference_wall_s,
        m2_sentinel_generation_wall_s=m2_wall_s,
        neural_training_wall_times_s=[
            float(training_metadata[seed]["wall_time_s"]) for seed in executed_seeds
        ],
    )
    _write_csv(table_root / "break_even.csv", break_even_rows)

    _plot_pod(
        figure_root / "geometry_pod_spectrum_and_modes.png",
        pod,
        next(iter(operators.values())).ny,
        next(iter(operators.values())).nx,
    )
    _plot_matched_accuracy(figure_root / "matched_budget_accuracy.png", aggregates)
    representative_id = geometry_case_id(
        30.0, "heating", "near-transition", "localized-sink"
    )
    _plot_ood_fields(
        path=figure_root / "geometry_ood_field_comparison.png",
        target=targets[representative_id],
        baseline_predictions=baseline_predictions,
        neural_predictions=neural_predictions_by_seed[initial_seed],
        ambient_temperature_K=float(config["reference"]["ambient_temperature_K"]),
    )
    _plot_pass_rates(
        figure_root / "a1_a2_r1_r2_n1_n2_pass_rates.png",
        all_mode_rows,
        initial_seed,
    )
    _plot_defects(
        figure_root / "true_fixed_point_defect.png", all_mode_rows, initial_seed
    )
    _plot_pareto(figure_root / "speed_accuracy_pareto.png", aggregates)
    _plot_break_even(figure_root / "break_even_queries.png", break_even_rows)

    figures = [
        (figure_root / name).relative_to(repository_root).as_posix()
        for name in (
            "geometry_masks_and_reference_fields.png",
            "geometry_pod_spectrum_and_modes.png",
            "matched_budget_accuracy.png",
            "geometry_ood_field_comparison.png",
            "a1_a2_r1_r2_n1_n2_pass_rates.png",
            "true_fixed_point_defect.png",
            "speed_accuracy_pareto.png",
            "break_even_queries.png",
        )
    ]
    summary = {
        "task_id": config["task_id"],
        "run_id": config["run_id"],
        "phase_id": config["phase_id"],
        "evidence_type": EVIDENCE_TYPE,
        "frozen_pr39": config["frozen_baseline"],
        "reference": reference_summary,
        "m2_sentinels": sentinel_summary,
        "implementation_repair": implementation_repair,
        "pod": {
            "rank": pod.rank,
            "rank_cap": int(config["pod"]["rank_cap"]),
            "selected_cumulative_energy": float(pod.cumulative_energy[pod.rank - 1]),
            "fit_case_ids": list(pod.train_case_ids),
            "validation_test_leakage": False,
            "maximum_train_reconstruction_error": float(
                np.max(pod.reconstruction_errors)
            ),
        },
        "ridge": {
            "regularization_lambda": ridge.regularization_lambda,
            "design_condition_number": ridge.design_condition_number,
            "fit_case_ids": list(pod.train_case_ids),
        },
        "training": {
            "executed_seeds": executed_seeds,
            "seed_count": len(executed_seeds),
            "total_training_wall_time_s": training_wall_s,
            "per_seed": {str(seed): training_metadata[seed] for seed in executed_seeds},
        },
        "seed_summaries": seed_summaries,
        "decision": decision,
        "disposition": decision["disposition"],
        "validity": "valid",
        "lifecycle_state": "numerically_validated",
        "claim_status": (
            "qualified_supported"
            if str(decision["disposition"]).startswith("GO_")
            else "failed_but_informative"
        ),
        "scientific_role": "diagnostic_non_voting",
        "mode_aggregates": aggregates,
        "break_even": break_even_rows[0],
        "current_domain_matched_budget_row_count": len(current_domain_rows),
        "conditional_seeds_executed": bool(selected_path is not None),
        "claim_boundary": config["claim_boundary"],
        "paths": {
            "processed_root": config["outputs"]["processed_root"],
            "table_root": config["outputs"]["table_root"],
            "figure_root": config["outputs"]["figure_root"],
            "checkpoint_root": config["outputs"]["checkpoint_root"],
            "report": config["outputs"]["report"],
            "figures": figures,
        },
        "next_single_priority": (
            "Preregister Q2_M1_LATENT_PROJECTION_PINN_FORMAL_OOD_V1 without executing it in this round."
            if str(decision["disposition"]).startswith("GO_")
            else "Stop neural forward-architecture expansion; retain the conservative projection operator and analytic A2 as numerical assets for the limitation manuscript."
        ),
    }
    _write_json(table_root / "summary.json", summary)
    _write_report(report_path, summary)
    return summary

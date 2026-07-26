"""Run only the bounded, non-formal Phase 1 v8 vertical shape/scale screen.

This entry point implements the raw vertical-reference and one-time production
normalization stages.  It deliberately contains no K-state fitting, runtime
preflight, formal-run registry, or formal-case execution path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import yaml

from pinnpcm.evaluation.geophase_phase1_gates import (
    held_out_vertical_response_grid,
    vertical_passivity_and_identity_metrics_on_grid,
    vertical_response_comparison_on_grid,
)
from pinnpcm.solvers.vertical_multilayer_reference import (
    RawVerticalComponents,
    VerticalRawBuildRegistry,
    VerticalReferenceModalEvaluator,
    apply_repair_normalization,
    build_repair_overlay_branch,
    build_repair_substrate_branch,
    repair_normalization_scales,
)


ROOT = Path(__file__).resolve().parents[1]
V8_REPAIR_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_vertical_shape_scale_v8.yaml"
)
REGIONS = ("bare_vo2", "electrode_covered_vo2")
LEVELS = ("coarse", "fine")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty v8 readiness CSV: {path}")
    fields = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def _verify_commit_exists(commit: str) -> None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git commit is unavailable: {commit}")


def _require_ancestor(ancestor: str, descendant: str, message: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(message)


def _verify_formal_inventory(path: Path, expected_count: int) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_count:
        raise RuntimeError("formal inventory count drifted from the locked 96 items")
    if {row.get("formal_status") for row in rows} != {"planned_not_executed"}:
        raise RuntimeError("a formal inventory row is no longer planned_not_executed")


def _verify_entry(
    repair_path: Path,
    repair: dict[str, Any],
    *,
    preregistration_sha: str,
    repair_yaml_sha256: str,
) -> dict[str, str]:
    if len(preregistration_sha) != 40 or len(repair_yaml_sha256) != 64:
        raise ValueError("full preregistration SHA and YAML SHA-256 are required")
    _verify_commit_exists(preregistration_sha)

    authority = repair["authority"]
    execution = repair["execution_boundary"]
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    required_branch = str(authority["required_branch"])
    if branch != required_branch or branch == "main":
        raise RuntimeError(
            f"v8 screening requires branch {required_branch!r}, found {branch!r}"
        )
    _require_ancestor(
        str(authority["starting_main_sha"]),
        preregistration_sha,
        "the locked starting main is not an ancestor of the preregistration",
    )
    _require_ancestor(
        preregistration_sha,
        head,
        "the v8 preregistration is not an ancestor of HEAD",
    )

    expected_subject = str(execution["required_repair_protocol_commit_message"])
    actual_subject = _git("show", "-s", "--format=%s", preregistration_sha)
    if actual_subject != expected_subject:
        raise RuntimeError("v8 preregistration commit subject is not locked")

    remote_branch = f"origin/{required_branch}"
    try:
        remote_head = _git("rev-parse", "--verify", remote_branch)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("the preregistered branch is not present on origin") from error
    _require_ancestor(
        preregistration_sha,
        remote_head,
        "the preregistration commit has not been pushed to the required branch",
    )

    actual_repair_hash = _sha256(repair_path)
    if actual_repair_hash != repair_yaml_sha256:
        raise RuntimeError("v8 repair YAML hash does not match the CLI argument")
    relative = repair_path.relative_to(ROOT).as_posix()
    committed = subprocess.check_output(
        ["git", "show", f"{preregistration_sha}:{relative}"], cwd=ROOT
    )
    if committed != repair_path.read_bytes():
        raise RuntimeError("current v8 YAML differs from its preregistered bytes")

    authority_paths = {
        "formal_v6_config_sha256": ROOT / authority["formal_v6_config_path"],
        "v7_repair_config_sha256": ROOT / authority["v7_repair_config_path"],
        "source_contract_sha256": ROOT / authority["source_contract_path"],
        "formal_inventory_sha256": ROOT / authority["formal_inventory_path"],
    }
    identities = {
        "preregistration_sha": preregistration_sha,
        "repair_yaml_sha256": actual_repair_hash,
        "head_at_screening": head,
        "branch_at_screening": branch,
        "origin_branch_head_at_screening": remote_head,
    }
    for key, path in authority_paths.items():
        actual = _sha256(path)
        if actual != str(authority[key]):
            raise RuntimeError(f"authority hash mismatch for {path}")
        identities[key] = actual

    _verify_formal_inventory(
        authority_paths["formal_inventory_sha256"],
        int(authority["formal_evaluation_item_count"]),
    )
    if (
        int(execution["formal_execution_count"]) != 0
        or int(execution["formal_case_results_generated"]) != 0
        or bool(execution["formal_campaign_executed"])
    ):
        raise RuntimeError("v8 entry requires an untouched formal execution count")
    return identities


def _areas(formal: dict[str, Any]) -> dict[str, float]:
    geometry = formal["geometry"]["primary_single_device"]
    length = float(geometry["vo2_length_m"])
    width = float(geometry["vo2_width_m"])
    overlap = float(geometry["contact_overlap_nominal_m"])
    return {
        "bare_vo2": (length - 2.0 * overlap) * width,
        "electrode_covered_vo2": 2.0 * overlap * width,
    }


def _compose_raw(
    substrate: tuple[object, np.ndarray],
    overlay: tuple[object, np.ndarray],
    *,
    areas: dict[str, float],
    depth_m: float,
    level: str,
) -> RawVerticalComponents:
    return RawVerticalComponents(
        substrate=substrate[0],
        overlay=overlay[0],
        region_areas_m2=areas,
        substrate_depth_m=depth_m,
        grid_level=level,
        substrate_cell_widths_m=substrate[1],
        overlay_cell_widths_m=overlay[1],
    )


def _raw_device_totals(raw: RawVerticalComponents) -> tuple[float, float]:
    references = raw.raw_region_references()
    conductance = sum(
        raw.region_areas_m2[region] * references[region].dc_conductance_W_m2K
        for region in REGIONS
    )
    capacity = sum(
        raw.region_areas_m2[region] * references[region].total_capacity_J_m2K
        for region in REGIONS
    )
    values = np.asarray([conductance, capacity], dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0.0):
        raise ValueError("raw device G/C totals must be finite and positive")
    return float(conductance), float(capacity)


def _targets(formal: dict[str, Any]) -> tuple[float, float]:
    normalization = formal["vertical_reference"]["device_effective_normalization"]
    return (
        float(normalization["nominal_total_thermal_conductance_W_K"]),
        float(normalization["nominal_memory_capacity_target_J_K"]),
    )


def _temporary_coordinate_ratio(
    raw_D_fine: RawVerticalComponents, formal: dict[str, Any]
) -> tuple[float, float, float]:
    raw_G, raw_C = _raw_device_totals(raw_D_fine)
    target_G, target_C = _targets(formal)
    ratio = target_C * raw_G / (target_G * raw_C)
    if not np.isfinite(ratio) or ratio <= 0.0:
        raise ValueError("temporary pullback ratio must be finite and positive")
    return float(ratio), raw_G, raw_C


def _passivity_pass(
    metrics: dict[str, float | bool], repair: dict[str, Any]
) -> bool:
    gates = repair["vertical_gates"]
    tolerances = gates["identity_relative_tolerances"]
    return bool(
        float(metrics["minimum_capacity_J_m2K"]) > 0.0
        and float(metrics["minimum_physical_conductance_W_m2K"]) > 0.0
        and float(metrics["maximum_pole_real_per_s"]) < 0.0
        and float(metrics["minimum_conductance_matrix_eigenvalue_W_m2K"]) > 0.0
        and float(metrics["minimum_real_admittance_relative_margin"])
        >= float(gates["minimum_real_admittance_relative_margin"])
        and float(metrics["step_initial_relative_error"])
        <= float(tolerances["step_initial"])
        and float(metrics["step_DC_relative_error"])
        <= float(tolerances["step_DC"])
        and float(metrics["impulse_integral_relative_error"])
        <= float(tolerances["impulse_integral"])
        and float(metrics["impulse_step_derivative_relative_error"])
        <= float(tolerances["impulse_step_derivative"])
        and float(metrics["frequency_state_space_relative_error"])
        <= float(tolerances["frequency_state_space"])
    )


def _response_pass(
    metrics: dict[str, float], repair: dict[str, Any], comparison_role: str
) -> bool:
    gates = repair["vertical_gates"]
    if comparison_role.startswith("mesh"):
        step_limit = float(gates["each_grid_family_mesh_step_error_max"])
        frequency_limit = float(gates["each_grid_family_mesh_frequency_error_max"])
    elif comparison_role == "depth":
        step_limit = float(gates["each_grid_family_depth_step_error_max"])
        frequency_limit = float(gates["each_grid_family_depth_frequency_error_max"])
    else:
        raise ValueError(f"unknown v8 comparison role: {comparison_role}")
    return bool(
        float(metrics["step_response_nrmse"]) <= step_limit
        and float(metrics["frequency_log_magnitude_rmse"]) <= frequency_limit
    )


def _pointwise_rows(
    comparison: dict[str, object],
    *,
    pair_id: str,
    production_depth_m: float,
    comparator_depth_m: float,
    region: str,
    grid_family: str,
    comparison_role: str,
    effective_times_s: np.ndarray,
    effective_frequencies_Hz: np.ndarray,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    raw_times = np.asarray(comparison["time_s"], dtype=float)
    raw_frequencies = np.asarray(comparison["frequency_Hz"], dtype=float)
    for index, raw_time in enumerate(raw_times):
        rows.append(
            {
                "pair_id": pair_id,
                "production_depth_m": production_depth_m,
                "comparator_depth_m": comparator_depth_m,
                "region": region,
                "grid_family": grid_family,
                "comparison_role": comparison_role,
                "axis": "time",
                "raw_coordinate": float(raw_time),
                "effective_coordinate": float(effective_times_s[index]),
                "step_error": float(np.asarray(comparison["step_error"])[index]),
                "impulse_error": float(
                    np.asarray(comparison["impulse_error"])[index]
                ),
                "frequency_log_magnitude_error": "",
                "frequency_squared_rmse_contribution": "",
                "frequency_cumulative_rmse": "",
                "raw_unnormalized": True,
                "voting": False,
                "formal_case": False,
            }
        )
    for index, raw_frequency in enumerate(raw_frequencies):
        signed_error = float(
            np.asarray(comparison["frequency_log_magnitude_error"])[index]
        )
        candidate = complex(
            np.asarray(comparison["candidate_frequency_W_m2K"])[index]
        )
        reference = complex(
            np.asarray(comparison["reference_frequency_W_m2K"])[index]
        )
        rows.append(
            {
                "pair_id": pair_id,
                "production_depth_m": production_depth_m,
                "comparator_depth_m": comparator_depth_m,
                "region": region,
                "grid_family": grid_family,
                "comparison_role": comparison_role,
                "axis": "frequency",
                "raw_coordinate": float(raw_frequency),
                "effective_coordinate": float(effective_frequencies_Hz[index]),
                "step_error": "",
                "impulse_error": "",
                "frequency_log_magnitude_error": signed_error,
                "absolute_frequency_log_magnitude_error": abs(signed_error),
                "frequency_squared_rmse_contribution": float(
                    np.asarray(comparison["frequency_squared_rmse_contribution"])[index]
                ),
                "frequency_cumulative_rmse": float(
                    np.asarray(comparison["frequency_cumulative_rmse"])[index]
                ),
                "candidate_frequency_real_W_m2K": candidate.real,
                "candidate_frequency_imag_W_m2K": candidate.imag,
                "reference_frequency_real_W_m2K": reference.real,
                "reference_frequency_imag_W_m2K": reference.imag,
                "raw_unnormalized": True,
                "voting": False,
                "formal_case": False,
            }
        )
    return rows


def _evaluate_pair(
    pair_id: str,
    pair: dict[str, Any],
    raws: dict[tuple[float, str], RawVerticalComponents],
    formal: dict[str, Any],
    repair: dict[str, Any],
    inherited_times_s: np.ndarray,
    inherited_frequencies_Hz: np.ndarray,
) -> dict[str, object]:
    depth = float(pair["production_depth_m"])
    comparator = float(pair["comparator_depth_m"])
    candidate_rows: list[dict[str, object]] = []
    pointwise_rows: list[dict[str, object]] = []
    passivity_rows: list[dict[str, object]] = []
    failure_metric_ids: list[str] = []

    try:
        ratio, raw_G, raw_C = _temporary_coordinate_ratio(
            raws[(depth, "fine")], formal
        )
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        candidate_rows.append(
            {
                "pair_id": pair_id,
                "production_depth_m": depth,
                "comparator_depth_m": comparator,
                "comparison_role": "temporary_coordinate_ratio",
                "attempted": True,
                "passed": False,
                "failure": f"{type(error).__name__}: {error}",
                "raw_unnormalized": True,
                "voting": False,
                "formal_case": False,
            }
        )
        return {
            "pair_id": pair_id,
            "production_depth_m": depth,
            "comparator_depth_m": comparator,
            "temporary_ratio_r": None,
            "raw_device_G_W_K": None,
            "raw_device_C_J_K": None,
            "foundation_pass": False,
            "depth_pass": False,
            "pair_pass": False,
            "failure_metric_ids": ["temporary_coordinate_ratio"],
            "candidate_rows": candidate_rows,
            "pointwise_rows": pointwise_rows,
            "passivity_rows": passivity_rows,
            "raws": raws,
        }

    grid_families = {
        "inherited_raw": (
            inherited_times_s,
            inherited_frequencies_Hz,
        ),
        "formal_window_pullback": (
            inherited_times_s / ratio,
            inherited_frequencies_Hz * ratio,
        ),
    }
    foundation_pass = True
    depth_pass = True
    raw_references = {
        key: components.raw_region_references() for key, components in raws.items()
    }

    for grid_family, (raw_times, raw_frequencies) in grid_families.items():
        for region in REGIONS:
            comparisons = {
                "mesh_D": (
                    raw_references[(depth, "coarse")][region],
                    raw_references[(depth, "fine")][region],
                ),
                "mesh_2D": (
                    raw_references[(comparator, "coarse")][region],
                    raw_references[(comparator, "fine")][region],
                ),
                "depth": (
                    raw_references[(depth, "fine")][region],
                    raw_references[(comparator, "fine")][region],
                ),
            }
            for comparison_role, (candidate, reference) in comparisons.items():
                metric_id = f"{grid_family}:{region}:{comparison_role}"
                try:
                    comparison = vertical_response_comparison_on_grid(
                        candidate,
                        reference,
                        times_s=raw_times,
                        frequencies_Hz=raw_frequencies,
                    )
                    metrics = {
                        key: float(value)
                        for key, value in comparison["metrics"].items()
                    }
                    passed = _response_pass(metrics, repair, comparison_role)
                    candidate_rows.append(
                        {
                            "pair_id": pair_id,
                            "production_depth_m": depth,
                            "comparator_depth_m": comparator,
                            "temporary_ratio_r": ratio,
                            "raw_device_G_W_K": raw_G,
                            "raw_device_C_J_K": raw_C,
                            "region": region,
                            "grid_family": grid_family,
                            "comparison_role": comparison_role,
                            **metrics,
                            "step_required": True,
                            "impulse_required": False,
                            "frequency_required": True,
                            "passed": passed,
                            "attempted": True,
                            "raw_unnormalized": True,
                            "voting": False,
                            "formal_case": False,
                        }
                    )
                    pointwise_rows.extend(
                        _pointwise_rows(
                            comparison,
                            pair_id=pair_id,
                            production_depth_m=depth,
                            comparator_depth_m=comparator,
                            region=region,
                            grid_family=grid_family,
                            comparison_role=comparison_role,
                            effective_times_s=inherited_times_s,
                            effective_frequencies_Hz=inherited_frequencies_Hz,
                        )
                    )
                except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                    passed = False
                    candidate_rows.append(
                        {
                            "pair_id": pair_id,
                            "production_depth_m": depth,
                            "comparator_depth_m": comparator,
                            "temporary_ratio_r": ratio,
                            "region": region,
                            "grid_family": grid_family,
                            "comparison_role": comparison_role,
                            "passed": False,
                            "attempted": True,
                            "failure": f"{type(error).__name__}: {error}",
                            "raw_unnormalized": True,
                            "voting": False,
                            "formal_case": False,
                        }
                    )
                if not passed:
                    failure_metric_ids.append(metric_id)
                    if comparison_role.startswith("mesh"):
                        foundation_pass = False
                    else:
                        depth_pass = False

            for physical_depth in (depth, comparator):
                for level in LEVELS:
                    audit_id = (
                        f"{grid_family}:{region}:passivity_identity:"
                        f"{physical_depth:.12e}:{level}"
                    )
                    try:
                        audit = vertical_passivity_and_identity_metrics_on_grid(
                            raw_references[(physical_depth, level)][region],
                            times_s=raw_times,
                            frequencies_Hz=raw_frequencies,
                        )
                        audit_pass = _passivity_pass(audit, repair)
                        passivity_rows.append(
                            {
                                "pair_id": pair_id,
                                "production_depth_m": depth,
                                "comparator_depth_m": comparator,
                                "physical_depth_m": physical_depth,
                                "grid_level": level,
                                "region": region,
                                "grid_family": grid_family,
                                "audit_stage": "raw_foundation",
                                **audit,
                                "passed": audit_pass,
                                "raw_unnormalized": True,
                                "voting": False,
                                "formal_case": False,
                            }
                        )
                    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                        audit_pass = False
                        passivity_rows.append(
                            {
                                "pair_id": pair_id,
                                "production_depth_m": depth,
                                "comparator_depth_m": comparator,
                                "physical_depth_m": physical_depth,
                                "grid_level": level,
                                "region": region,
                                "grid_family": grid_family,
                                "audit_stage": "raw_foundation",
                                "passed": False,
                                "failure": f"{type(error).__name__}: {error}",
                                "raw_unnormalized": True,
                                "voting": False,
                                "formal_case": False,
                            }
                        )
                    if not audit_pass:
                        foundation_pass = False
                        failure_metric_ids.append(audit_id)

    pair_pass = bool(foundation_pass and depth_pass)
    for row in candidate_rows:
        row["pair_foundation_pass"] = foundation_pass
        row["pair_depth_pass"] = depth_pass
        row["pair_pass"] = pair_pass
    for row in passivity_rows:
        row["pair_foundation_pass"] = foundation_pass
        row["pair_depth_pass"] = depth_pass
        row["pair_pass"] = pair_pass
    return {
        "pair_id": pair_id,
        "production_depth_m": depth,
        "comparator_depth_m": comparator,
        "temporary_ratio_r": ratio,
        "raw_device_G_W_K": raw_G,
        "raw_device_C_J_K": raw_C,
        "foundation_pass": foundation_pass,
        "depth_pass": depth_pass,
        "pair_pass": pair_pass,
        "failure_metric_ids": sorted(set(failure_metric_ids)),
        "candidate_rows": candidate_rows,
        "pointwise_rows": pointwise_rows,
        "passivity_rows": passivity_rows,
        "raws": raws,
    }


def _failed_pair_result(
    pair_id: str,
    pair: dict[str, Any],
    *,
    failure_stage: str,
    error: Exception,
) -> dict[str, object]:
    """Represent a raw-build/foundation exception as an auditable NO-GO."""

    depth = float(pair["production_depth_m"])
    comparator = float(pair["comparator_depth_m"])
    failure = f"{type(error).__name__}: {error}"
    return {
        "pair_id": pair_id,
        "production_depth_m": depth,
        "comparator_depth_m": comparator,
        "temporary_ratio_r": None,
        "raw_device_G_W_K": None,
        "raw_device_C_J_K": None,
        "foundation_pass": False,
        "depth_pass": False,
        "pair_pass": False,
        "failure_metric_ids": [failure_stage],
        "candidate_rows": [
            {
                "pair_id": pair_id,
                "production_depth_m": depth,
                "comparator_depth_m": comparator,
                "region": "all",
                "grid_family": "not_reached",
                "comparison_role": failure_stage,
                "attempted": True,
                "passed": False,
                "failure": failure,
                "pair_foundation_pass": False,
                "pair_depth_pass": False,
                "pair_pass": False,
                "raw_unnormalized": True,
                "voting": False,
                "formal_case": False,
            }
        ],
        "pointwise_rows": [],
        "passivity_rows": [],
        "raws": {},
    }


def _postscale_checks(
    raw_D_fine: RawVerticalComponents,
    formal: dict[str, Any],
    repair: dict[str, Any],
    times_s: np.ndarray,
    frequencies_Hz: np.ndarray,
) -> tuple[dict[str, object], list[dict[str, object]], object]:
    scales = repair_normalization_scales(raw_D_fine, formal)
    production = apply_repair_normalization(raw_D_fine, scales)
    target_G, target_C = _targets(formal)
    g_error = abs(production.integrated_dc_conductance_W_K - target_G) / target_G
    c_error = abs(production.integrated_memory_capacity_J_K - target_C) / target_C
    analytic_g_limit = float(
        formal["analytic_source_scale_preflights"][
            "area_integrated_dc_thermal_conductance_relative_error_max"
        ]
    )
    analytic_c_limit = float(
        formal["analytic_source_scale_preflights"][
            "active_plus_memory_capacity_relative_error_max"
        ]
    )
    anchor_pass = bool(g_error <= analytic_g_limit and c_error <= analytic_c_limit)

    raw_references = raw_D_fine.raw_region_references()
    omega = 2.0 * np.pi * frequencies_Hz
    ratio = float(scales.capacity_scale / scales.conductance_scale)
    tolerance = float(
        repair["vertical_gates"]["identity_relative_tolerances"][
            "frequency_state_space"
        ]
    )
    audit_rows: list[dict[str, object]] = []
    all_pass = anchor_pass
    equivalence_errors: dict[str, float] = {}
    for region in REGIONS:
        scaled_reference = production.references[region]
        audit = vertical_passivity_and_identity_metrics_on_grid(
            scaled_reference,
            times_s=times_s,
            frequencies_Hz=frequencies_Hz,
        )
        audit_pass = _passivity_pass(audit, repair)
        scaled_response = VerticalReferenceModalEvaluator(
            scaled_reference
        ).driving_admittance_W_m2K(omega)
        raw_response = VerticalReferenceModalEvaluator(
            raw_references[region]
        ).driving_admittance_W_m2K(omega * ratio)
        expected = float(scales.conductance_scale) * raw_response
        equivalence_error = float(
            np.sqrt(np.mean(np.abs(scaled_response - expected) ** 2))
            / max(float(np.sqrt(np.mean(np.abs(expected) ** 2))), 1.0e-30)
        )
        equivalence_errors[region] = equivalence_error
        row_pass = bool(audit_pass and equivalence_error <= tolerance)
        all_pass = all_pass and row_pass
        audit_rows.append(
            {
                "audit_stage": "postscale_production",
                "region": region,
                "physical_depth_m": raw_D_fine.substrate_depth_m,
                "grid_level": "fine",
                "grid_family": "formal_effective",
                **audit,
                "Y_eff_equivalence_relative_error": equivalence_error,
                "passed": row_pass,
                "raw_unnormalized": False,
                "voting": False,
                "formal_case": False,
            }
        )
    summary = {
        "conductance_scale_a_G": float(scales.conductance_scale),
        "capacity_scale_a_C": float(scales.capacity_scale),
        "scale_ratio_a_C_over_a_G": ratio,
        "raw_integrated_dc_conductance_W_K": float(
            scales.raw_integrated_dc_conductance_W_K
        ),
        "raw_integrated_memory_capacity_J_K": float(
            scales.raw_integrated_memory_capacity_J_K
        ),
        "anchor_G_relative_error": float(g_error),
        "anchor_C_relative_error": float(c_error),
        "Y_eff_equivalence_relative_error_by_region": equivalence_errors,
        "postscale_pass": bool(all_pass),
    }
    return summary, audit_rows, production


def _write_evidence(
    repair: dict[str, Any],
    *,
    summary: dict[str, object],
    candidate_rows: list[dict[str, object]],
    pointwise_rows: list[dict[str, object]],
    passivity_rows: list[dict[str, object]],
    k_status: str,
) -> None:
    outputs = repair["outputs"]
    blocked_row = {
        "region": "all",
        "order": "",
        "start_id": "",
        "status": k_status,
        "passed": False,
        "selected": False,
        "voting": False,
        "formal_case": False,
    }
    if not pointwise_rows:
        pointwise_rows = [
            {
                "status": "blocked_before_pointwise_evaluation",
                "voting": False,
                "formal_case": False,
            }
        ]
    if not passivity_rows:
        passivity_rows = [
            {
                "status": "blocked_before_passivity_evaluation",
                "passed": False,
                "voting": False,
                "formal_case": False,
            }
        ]

    environment = {
        "task_id": repair["task_id"],
        "schema_version": repair["schema_version"],
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "branch": summary["branch_at_screening"],
        "head": summary["head_at_screening"],
        "preregistration_sha": summary["preregistration_sha"],
        "repair_yaml_sha256": summary["repair_yaml_sha256"],
        "cpu_only": True,
        "formal_execution_count": 0,
        "formal_case_results_generated": 0,
        "voting": False,
    }

    # JSON/CSV evidence is written before the completion summary.  The final
    # preregistration JSON is the atomic completion marker for this screen.
    _atomic_csv(ROOT / outputs["vertical_candidate_summary_csv"], candidate_rows)
    _atomic_csv(ROOT / outputs["vertical_pointwise_csv"], pointwise_rows)
    _atomic_csv(ROOT / outputs["vertical_passivity_identity_csv"], passivity_rows)
    _atomic_csv(ROOT / outputs["k_state_multistart_csv"], [blocked_row])
    _atomic_csv(ROOT / outputs["k_state_selection_csv"], [blocked_row])
    _atomic_json(ROOT / outputs["environment_manifest_json"], environment)
    _atomic_json(ROOT / outputs["preregistration_json"], summary)


def run(
    formal_path: Path,
    repair_path: Path,
    *,
    preregistration_sha: str,
    repair_yaml_sha256: str,
) -> dict[str, object]:
    if repair_path.resolve() != V8_REPAIR_CONFIG_PATH.resolve():
        raise RuntimeError(
            "v8 runner must use configs/geophase_phase1_vertical_shape_scale_v8.yaml"
        )
    repair = _load_yaml(repair_path)
    formal = _load_yaml(formal_path)
    identities = _verify_entry(
        repair_path,
        repair,
        preregistration_sha=preregistration_sha,
        repair_yaml_sha256=repair_yaml_sha256,
    )
    authority = repair["authority"]
    expected_formal_path = (ROOT / authority["formal_v6_config_path"]).resolve()
    if formal_path.resolve() != expected_formal_path:
        raise RuntimeError("v8 runner must use the locked formal-v6 authority path")
    v7_repair = _load_yaml(ROOT / authority["v7_repair_config_path"])

    registry = VerticalRawBuildRegistry()
    overlays: dict[str, tuple[object, np.ndarray]] = {}
    overlay_build_error: Exception | None = None
    try:
        for level in LEVELS:
            build_id = f"ti_au_overlay_{level}"
            overlays[level] = registry.get_or_build(
                build_id,
                {
                    "kind": "overlay",
                    "grid_level": level,
                    "source_protocol": "v7",
                },
                lambda level=level: build_repair_overlay_branch(
                    formal, v7_repair, grid_level=level
                ),
            )
    except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as error:
        overlay_build_error = error

    substrates: dict[tuple[float, str], tuple[object, np.ndarray]] = {}

    def ensure_substrate(depth_m: float, level: str) -> tuple[object, np.ndarray]:
        key = (float(depth_m), level)
        if key not in substrates:
            build_id = f"substrate_depth_{depth_m:.12e}_{level}"
            substrates[key] = registry.get_or_build(
                build_id,
                {
                    "kind": "substrate",
                    "depth_m": float(depth_m),
                    "grid_level": level,
                    "source_protocol": "v7",
                },
                lambda depth_m=depth_m, level=level: build_repair_substrate_branch(
                    formal,
                    v7_repair,
                    substrate_depth_m=depth_m,
                    grid_level=level,
                ),
            )
        return substrates[key]

    areas = _areas(formal)

    def ensure_pair(pair: dict[str, Any]) -> dict[tuple[float, str], RawVerticalComponents]:
        depth = float(pair["production_depth_m"])
        comparator = float(pair["comparator_depth_m"])
        return {
            (physical_depth, level): _compose_raw(
                ensure_substrate(physical_depth, level),
                overlays[level],
                areas=areas,
                depth_m=physical_depth,
                level=level,
            )
            for physical_depth in (depth, comparator)
            for level in LEVELS
        }

    fit_contract = formal["vertical_reference"]["reduction_fit_contract"]
    inherited_times, inherited_frequencies = held_out_vertical_response_grid(
        fit_contract
    )
    schedule = list(repair["candidate_protocol"]["evaluation_order"])
    pairs = repair["candidate_protocol"]["pairs"]
    primary_id, fallback_id = schedule
    if overlay_build_error is not None:
        primary = _failed_pair_result(
            primary_id,
            pairs[primary_id],
            failure_stage="overlay_raw_build",
            error=overlay_build_error,
        )
    else:
        try:
            primary_raws = ensure_pair(pairs[primary_id])
            primary = _evaluate_pair(
                primary_id,
                pairs[primary_id],
                primary_raws,
                formal,
                repair,
                inherited_times,
                inherited_frequencies,
            )
        except (
            ValueError,
            RuntimeError,
            FloatingPointError,
            np.linalg.LinAlgError,
        ) as error:
            primary = _failed_pair_result(
                primary_id,
                pairs[primary_id],
                failure_stage="primary_raw_build",
                error=error,
            )
    evaluated = [primary]
    fallback_triggered = False
    selected_result: dict[str, object] | None = None

    if not bool(primary["foundation_pass"]):
        vertical_status = "NO_GO_VERTICAL_REFERENCE"
        stop_reason = "primary_foundation_failure"
    elif bool(primary["depth_pass"]):
        selected_result = primary
        vertical_status = "RAW_VERTICAL_REFERENCE_PASS_PENDING_POSTSCALE"
        stop_reason = "primary_pair_selected"
    else:
        fallback_triggered = True
        try:
            fallback_raws = ensure_pair(pairs[fallback_id])
            fallback = _evaluate_pair(
                fallback_id,
                pairs[fallback_id],
                fallback_raws,
                formal,
                repair,
                inherited_times,
                inherited_frequencies,
            )
        except (
            ValueError,
            RuntimeError,
            FloatingPointError,
            np.linalg.LinAlgError,
        ) as error:
            fallback = _failed_pair_result(
                fallback_id,
                pairs[fallback_id],
                failure_stage="fallback_raw_build",
                error=error,
            )
        evaluated.append(fallback)
        if bool(fallback["foundation_pass"]) and bool(fallback["depth_pass"]):
            selected_result = fallback
            vertical_status = "RAW_VERTICAL_REFERENCE_PASS_PENDING_POSTSCALE"
            stop_reason = "fallback_pair_selected"
        else:
            vertical_status = "NO_GO_VERTICAL_REFERENCE"
            stop_reason = (
                "fallback_foundation_failure"
                if not bool(fallback["foundation_pass"])
                else "fallback_depth_failure"
            )

    candidate_rows = [
        row for result in evaluated for row in result["candidate_rows"]
    ]
    pointwise_rows = [
        row for result in evaluated for row in result["pointwise_rows"]
    ]
    passivity_rows = [
        row for result in evaluated for row in result["passivity_rows"]
    ]

    postscale: dict[str, object] | None = None
    raw_selected_depth: float | None = None
    selected_depth: float | None = None
    if selected_result is not None:
        raw_selected_depth = float(selected_result["production_depth_m"])
        selected_raws = selected_result["raws"]
        try:
            postscale, postscale_rows, _production = _postscale_checks(
                selected_raws[(raw_selected_depth, "fine")],
                formal,
                repair,
                inherited_times,
                inherited_frequencies,
            )
            passivity_rows.extend(postscale_rows)
            candidate_rows.append(
                {
                    "pair_id": selected_result["pair_id"],
                    "production_depth_m": raw_selected_depth,
                    "comparison_role": "postscale_production",
                    **postscale,
                    "passed": bool(postscale["postscale_pass"]),
                    "voting": False,
                    "formal_case": False,
                }
            )
        except (
            ValueError,
            RuntimeError,
            FloatingPointError,
            np.linalg.LinAlgError,
        ) as error:
            postscale = {
                "postscale_pass": False,
                "failure": f"{type(error).__name__}: {error}",
            }
            candidate_rows.append(
                {
                    "pair_id": selected_result["pair_id"],
                    "production_depth_m": raw_selected_depth,
                    "comparison_role": "postscale_production",
                    **postscale,
                    "passed": False,
                    "voting": False,
                    "formal_case": False,
                }
            )
        if not bool(postscale["postscale_pass"]):
            vertical_status = "NO_GO_VERTICAL_REFERENCE"
            stop_reason = "postscale_anchor_passivity_or_equivalence_failure"
        else:
            selected_depth = raw_selected_depth
            vertical_status = "PASS_VERTICAL_REFERENCE"
            stop_reason = "vertical_pass_K_state_not_run_by_this_entrypoint"

    expected_depths = list(
        repair["raw_build_budget"]["primary_unique_substrate_depths_m"]
    )
    if fallback_triggered:
        expected_depths.extend(
            repair["raw_build_budget"]["conditional_additional_substrate_depths_m"]
        )
    declared_ids = list(repair["raw_build_budget"]["overlay_build_ids"])
    declared_ids.extend(
        f"substrate_depth_{float(depth):.12e}_{level}"
        for depth in expected_depths
        for level in LEVELS
    )
    actual_build_count = len(registry.unique_build_ids)
    expected_build_count = int(
        repair["raw_build_budget"][
            "maximum_unique_numerical_builds"
            if fallback_triggered
            else "primary_unique_numerical_builds"
        ]
    )
    registry_integrity_pass = True
    registry_failure: str | None = None
    try:
        registry.assert_exactly_once(declared_ids)
        if actual_build_count != expected_build_count:
            raise RuntimeError(
                "conditional raw build count drifted: "
                f"{actual_build_count} != {expected_build_count}"
            )
    except (ValueError, RuntimeError) as error:
        registry_integrity_pass = False
        registry_failure = f"{type(error).__name__}: {error}"
        vertical_status = "NO_GO_VERTICAL_REFERENCE"
        stop_reason = "raw_build_registry_failure"
        selected_depth = None
        candidate_rows.append(
            {
                "pair_id": "all",
                "comparison_role": "raw_build_registry",
                "attempted": True,
                "passed": False,
                "failure": registry_failure,
                "voting": False,
                "formal_case": False,
            }
        )

    k_status = (
        "BLOCKED_BY_NO_GO_VERTICAL_REFERENCE"
        if vertical_status == "NO_GO_VERTICAL_REFERENCE"
        else "PENDING_NOT_RUN_BY_VERTICAL_ONLY_ENTRYPOINT"
    )
    final_disposition = (
        "NO_GO_VERTICAL_REFERENCE"
        if vertical_status == "NO_GO_VERTICAL_REFERENCE"
        else None
    )
    summary: dict[str, object] = {
        **identities,
        "task_id": repair["task_id"],
        "schema_version": repair["schema_version"],
        "status": "vertical_shape_scale_screen_complete",
        "evidence_type": repair["evidence_type"],
        "formal_execution_count": 0,
        "formal_case_results_generated": 0,
        "formal_campaign_executed": False,
        "formal_case_ids_used": [],
        "phase1_scientific_claim": "forbidden_pending_formal_campaign",
        "vertical_status": vertical_status,
        "raw_selected_depth_m": raw_selected_depth,
        "selected_production_depth_m": selected_depth,
        "k_state_status": k_status,
        "runtime_preflight_status": "BLOCKED_NOT_IMPLEMENTED_BY_THIS_ENTRYPOINT",
        "formal_v8_config_created": False,
        "final_disposition": final_disposition,
        "final_disposition_reached": final_disposition is not None,
        "stage_disposition": (
            "NO_GO_VERTICAL_REFERENCE"
            if final_disposition is not None
            else "VERTICAL_PASS_PENDING_K_STATE"
        ),
        "stop_reason": stop_reason,
        "candidate_schedule": schedule,
        "evaluated_pair_ids": [result["pair_id"] for result in evaluated],
        "conditional_second_pair_triggered": fallback_triggered,
        "pair_decisions": [
            {
                "pair_id": result["pair_id"],
                "production_depth_m": result["production_depth_m"],
                "comparator_depth_m": result["comparator_depth_m"],
                "temporary_ratio_r": result["temporary_ratio_r"],
                "raw_device_G_W_K": result["raw_device_G_W_K"],
                "raw_device_C_J_K": result["raw_device_C_J_K"],
                "foundation_pass": result["foundation_pass"],
                "depth_pass": result["depth_pass"],
                "pair_pass": result["pair_pass"],
                "failure_metric_ids": result["failure_metric_ids"],
            }
            for result in evaluated
        ],
        "production_normalization": postscale,
        "planned_maximum_unique_raw_build_count": int(
            repair["raw_build_budget"]["maximum_unique_numerical_builds"]
        ),
        "actual_unique_raw_build_count": actual_build_count,
        "actual_unique_raw_build_ids": list(registry.unique_build_ids),
        "raw_build_registry_integrity_pass": registry_integrity_pass,
        "raw_build_registry_failure": registry_failure,
        "raw_build_manifest": [record.__dict__ for record in registry.records()],
        "branch_reuse_mapping": {
            "substrate": "one depth/grid branch reused by both regions",
            "overlay": "one grid-level branch reused by every evaluated depth",
        },
        "screening_code_sha256": {
            "runner": _sha256(Path(__file__).resolve()),
            "vertical_solver": _sha256(
                ROOT / "src" / "pinnpcm" / "solvers" / "vertical_multilayer_reference.py"
            ),
            "vertical_evaluator": _sha256(
                ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_phase1_gates.py"
            ),
        },
        "voting": False,
    }
    _write_evidence(
        repair,
        summary=summary,
        candidate_rows=candidate_rows,
        pointwise_rows=pointwise_rows,
        passivity_rows=passivity_rows,
        k_status=k_status,
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--formal-config",
        type=Path,
        default=ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml",
    )
    parser.add_argument(
        "--repair-config",
        type=Path,
        default=ROOT / "configs" / "geophase_phase1_vertical_shape_scale_v8.yaml",
    )
    parser.add_argument("--preregistration-sha", required=True)
    parser.add_argument("--repair-yaml-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(
        args.formal_config.resolve(),
        args.repair_config.resolve(),
        preregistration_sha=args.preregistration_sha,
        repair_yaml_sha256=args.repair_yaml_sha256,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

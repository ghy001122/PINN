"""Run the bounded, non-formal Phase 1 v7 vertical-reference repair screen."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_phase1_gates import (
    held_out_vertical_response_grid,
    vertical_passivity_and_identity_metrics,
    vertical_response_comparison,
)
from pinnpcm.solvers.vertical_multilayer_reference import (
    RawVerticalComponents,
    VerticalRawBuildRegistry,
    VerticalReferenceModalEvaluator,
    analytic_homogeneous_substrate_admittance_W_m2K,
    apply_repair_normalization,
    build_normalized_vertical_references,
    build_repair_overlay_branch,
    build_repair_substrate_branch,
    fit_passive_ladder,
    reduction_validation_metrics,
    repair_normalization_scales,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty readiness CSV: {path}")
    fields = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _load(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected mapping in {path}")
    return payload


def _verify_entry(
    repair_path: Path,
    repair: dict[str, Any],
    *,
    initial_preregistration_commit: str,
    repair_protocol_commit: str,
    repair_yaml_sha256: str,
) -> dict[str, str]:
    if (
        len(initial_preregistration_commit) != 40
        or len(repair_protocol_commit) != 40
        or len(repair_yaml_sha256) != 64
    ):
        raise ValueError("full repair commit and SHA-256 identities are required")
    head = _git("rev-parse", "HEAD")
    subject = _git("show", "-s", "--format=%s", initial_preregistration_commit)
    expected_subject = str(
        repair["execution_boundary"]["required_repair_protocol_commit_message"]
    )
    if subject != expected_subject:
        raise RuntimeError("initial repair preregistration commit subject is not locked")
    subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            initial_preregistration_commit,
            repair_protocol_commit,
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", repair_protocol_commit, head],
        cwd=ROOT,
        check=True,
    )
    actual_repair_hash = _sha256(repair_path)
    if actual_repair_hash != repair_yaml_sha256:
        raise RuntimeError("repair YAML hash does not match the screening argument")
    relative = repair_path.relative_to(ROOT).as_posix()
    committed = subprocess.check_output(
        ["git", "show", f"{repair_protocol_commit}:{relative}"], cwd=ROOT
    )
    if committed != repair_path.read_bytes():
        raise RuntimeError("current repair YAML bytes differ from the preregistered commit")
    authority = repair["authority"]
    paths = {
        "formal_v6_config_sha256": ROOT / authority["formal_v6_config_path"],
        "source_contract_sha256": ROOT / authority["source_contract_path"],
        "formal_inventory_sha256": ROOT / authority["formal_inventory_path"],
    }
    identities = {
        "initial_preregistration_commit_sha": initial_preregistration_commit,
        "repair_protocol_commit_sha": repair_protocol_commit,
        "repair_yaml_sha256": actual_repair_hash,
        "head_at_screening": head,
    }
    for key, path in paths.items():
        actual = _sha256(path)
        expected = str(authority[key])
        if actual != expected:
            raise RuntimeError(f"authority hash mismatch for {path}")
        identities[key] = actual
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


def _raw(
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


def _passivity_pass(metrics: dict[str, float | bool], repair: dict[str, Any]) -> bool:
    gates = repair["selection_gates"]
    tolerances = gates["identity_relative_tolerances"]
    return bool(
        float(metrics["minimum_capacity_J_m2K"]) > 0.0
        and float(metrics["minimum_physical_conductance_W_m2K"]) > 0.0
        and float(metrics["maximum_pole_real_per_s"]) < 0.0
        and float(metrics["minimum_conductance_matrix_eigenvalue_W_m2K"]) > 0.0
        and float(metrics["minimum_real_admittance_relative_margin"])
        >= float(gates["minimum_real_admittance_relative_margin"])
        and float(metrics["step_initial_relative_error"]) <= float(tolerances["step_initial"])
        and float(metrics["step_DC_relative_error"]) <= float(tolerances["step_DC"])
        and float(metrics["impulse_integral_relative_error"])
        <= float(tolerances["impulse_integral"])
        and float(metrics["impulse_step_derivative_relative_error"])
        <= float(tolerances["impulse_step_derivative"])
        and float(metrics["frequency_state_space_relative_error"])
        <= float(tolerances["frequency_state_space"])
    )


def _pointwise_rows(
    comparison: dict[str, object],
    *,
    depth_m: float,
    comparator_depth_m: float,
    region: str,
    comparison_id: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, time_s in enumerate(np.asarray(comparison["time_s"], dtype=float)):
        rows.append(
            {
                "comparison_id": comparison_id,
                "depth_m": depth_m,
                "comparator_depth_m": comparator_depth_m,
                "region": region,
                "axis": "time",
                "coordinate": float(time_s),
                "step_error": float(np.asarray(comparison["step_error"])[index]),
                "impulse_error": float(np.asarray(comparison["impulse_error"])[index]),
                "frequency_log_magnitude_error": "",
                "frequency_squared_rmse_contribution": "",
                "frequency_cumulative_rmse": "",
                "candidate_frequency_real_W_m2K": "",
                "candidate_frequency_imag_W_m2K": "",
                "candidate_frequency_magnitude_W_m2K": "",
                "candidate_frequency_phase_rad": "",
                "reference_frequency_real_W_m2K": "",
                "reference_frequency_imag_W_m2K": "",
                "reference_frequency_magnitude_W_m2K": "",
                "reference_frequency_phase_rad": "",
                "absolute_frequency_log_magnitude_error": "",
                "voting": False,
                "formal_case": False,
            }
        )
    for index, frequency in enumerate(np.asarray(comparison["frequency_Hz"], dtype=float)):
        candidate = complex(np.asarray(comparison["candidate_frequency_W_m2K"])[index])
        reference = complex(np.asarray(comparison["reference_frequency_W_m2K"])[index])
        signed_error = float(
            np.asarray(comparison["frequency_log_magnitude_error"])[index]
        )
        rows.append(
            {
                "comparison_id": comparison_id,
                "depth_m": depth_m,
                "comparator_depth_m": comparator_depth_m,
                "region": region,
                "axis": "frequency",
                "coordinate": float(frequency),
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
                "candidate_frequency_magnitude_W_m2K": abs(candidate),
                "candidate_frequency_phase_rad": float(np.angle(candidate)),
                "reference_frequency_real_W_m2K": reference.real,
                "reference_frequency_imag_W_m2K": reference.imag,
                "reference_frequency_magnitude_W_m2K": abs(reference),
                "reference_frequency_phase_rad": float(np.angle(reference)),
                "voting": False,
                "formal_case": False,
            }
        )
    return rows


def _metric_pass(metrics: dict[str, float], repair: dict[str, Any], kind: str) -> bool:
    gates = repair["selection_gates"]
    if kind == "mesh":
        return bool(
            metrics["step_response_nrmse"] <= float(gates["mesh_step_error_max"])
            and metrics["frequency_log_magnitude_rmse"]
            <= float(gates["mesh_frequency_error_max"])
        )
    return bool(
        metrics["step_response_nrmse"]
        <= float(gates["substrate_depth_step_error_max"])
        and metrics["frequency_log_magnitude_rmse"]
        <= float(gates["substrate_depth_frequency_error_max"])
    )


def _ladder_pass(metrics: dict[str, float], repair: dict[str, Any]) -> bool:
    gates = repair["k_state_contract"]
    return bool(
        metrics["step_response_nrmse"] <= float(gates["step_response_nrmse_max"])
        and metrics["impulse_response_nrmse"] <= float(gates["impulse_response_nrmse_max"])
        and metrics["frequency_log_magnitude_rmse"]
        <= float(gates["frequency_log_magnitude_rmse_max"])
        and metrics["maximum_pole_real_per_s"] < 0.0
        and metrics["minimum_capacity_J_m2K"] > 0.0
        and metrics["minimum_conductance_W_m2K"] > 0.0
    )


def run(
    formal_path: Path,
    repair_path: Path,
    *,
    initial_preregistration_commit: str,
    repair_protocol_commit: str,
    repair_yaml_sha256: str,
) -> dict[str, object]:
    formal = _load(formal_path)
    repair = _load(repair_path)
    identities = _verify_entry(
        repair_path,
        repair,
        initial_preregistration_commit=initial_preregistration_commit,
        repair_protocol_commit=repair_protocol_commit,
        repair_yaml_sha256=repair_yaml_sha256,
    )
    registry = VerticalRawBuildRegistry()
    levels = ("coarse", "fine")
    depths = [float(value) for value in repair["candidate_space"]["production_depths_m"]]
    comparator_only = float(repair["candidate_space"]["comparator_only_depth_m"])
    all_depths = [*depths, comparator_only]
    overlays: dict[str, tuple[object, np.ndarray]] = {}
    for level in levels:
        build_id = f"ti_au_overlay_{level}"
        overlays[level] = registry.get_or_build(
            build_id,
            {"kind": "overlay", "grid_level": level},
            lambda level=level: build_repair_overlay_branch(formal, repair, grid_level=level),
        )
    substrates: dict[tuple[float, str], tuple[object, np.ndarray]] = {}
    for depth in all_depths:
        for level in levels:
            build_id = f"substrate_depth_{depth:.12e}_{level}"
            substrates[(depth, level)] = registry.get_or_build(
                build_id,
                {"kind": "substrate", "depth_m": depth, "grid_level": level},
                lambda depth=depth, level=level: build_repair_substrate_branch(
                    formal, repair, substrate_depth_m=depth, grid_level=level
                ),
            )
    v6_packages: dict[tuple[float, str], object] = {}
    v6_references: dict[tuple[float, str], object] = {}
    for depth in (4.0e-7, 8.0e-7):
        for region in ("bare_vo2", "electrode_covered_vo2"):
            build_id = f"v6_uniform8_D{int(round(depth * 1e9))}nm_{region}"
            v6_packages[(depth, region)] = registry.get_or_build(
                build_id,
                {"kind": "v6_uniform8", "depth_m": depth, "region": region},
                lambda depth=depth: build_normalized_vertical_references(
                    formal, substrate_depth_m=depth, cells_per_layer=8
                ),
            )
            v6_references[(depth, region)] = v6_packages[(depth, region)].references[
                region
            ]
    declared = ["ti_au_overlay_coarse", "ti_au_overlay_fine"]
    declared.extend(
        f"substrate_depth_{depth:.12e}_{level}" for depth in all_depths for level in levels
    )
    declared.extend(repair["raw_numerical_build_budget"]["v6_reproduction_build_ids"])
    registry.assert_exactly_once(declared)
    if len(registry.unique_build_ids) != int(repair["raw_numerical_build_budget"]["total_raw_numerical_builds"]):
        raise RuntimeError("raw numerical build count drifted from 26")

    fit_contract = formal["vertical_reference"]["reduction_fit_contract"]
    pointwise_rows: list[dict[str, object]] = []
    v6_comparisons = {
        region: vertical_response_comparison(
            v6_references[(4.0e-7, region)],
            v6_references[(8.0e-7, region)],
            fit_contract,
        )
        for region in ("bare_vo2", "electrode_covered_vo2")
    }
    reproduced = float(
        v6_comparisons["electrode_covered_vo2"]["metrics"][
            "frequency_log_magnitude_rmse"
        ]
    )
    expected = float(repair["v6_warning_reproduction"]["expected_value"])
    relative = abs(reproduced - expected) / expected
    if relative > float(repair["v6_warning_reproduction"]["relative_error_max"]):
        raise RuntimeError("NO_GO_V6_WARNING_NOT_REPRODUCED")
    for region, comparison in v6_comparisons.items():
        pointwise_rows.extend(
            _pointwise_rows(
                comparison,
                depth_m=4.0e-7,
                comparator_depth_m=8.0e-7,
                region=region,
                comparison_id="v6_warning_reproduction",
            )
        )

    areas = _areas(formal)
    candidate_rows: list[dict[str, object]] = []
    passivity_rows: list[dict[str, object]] = []
    normalized_pairs: dict[float, dict[tuple[float, str], object]] = {}
    passing_depths: list[float] = []
    target_G = float(formal["vertical_reference"]["device_effective_normalization"]["nominal_total_thermal_conductance_W_K"])
    target_C = float(formal["vertical_reference"]["device_effective_normalization"]["nominal_memory_capacity_target_J_K"])

    for depth in depths:
        comparator = 2.0 * depth
        raws = {
            (physical_depth, level): _raw(
                substrates[(physical_depth, level)],
                overlays[level],
                areas=areas,
                depth_m=physical_depth,
                level=level,
            )
            for physical_depth in (depth, comparator)
            for level in levels
        }
        scales = repair_normalization_scales(raws[(depth, "fine")], formal)
        normalized = {key: apply_repair_normalization(value, scales) for key, value in raws.items()}
        normalized_pairs[depth] = normalized
        anchor = normalized[(depth, "fine")]
        g_error = abs(anchor.integrated_dc_conductance_W_K - target_G) / target_G
        c_error = abs(anchor.integrated_memory_capacity_J_K - target_C) / target_C
        pair_pass = bool(
            g_error <= float(repair["selection_gates"]["area_integrated_G_relative_error_max"])
            and c_error <= float(repair["selection_gates"]["area_integrated_C_relative_error_max"])
        )
        row: dict[str, object] = {
            "depth_m": depth,
            "comparator_depth_m": comparator,
            "conductance_scale": scales.conductance_scale,
            "capacity_scale": scales.capacity_scale,
            "anchor_G_relative_error": g_error,
            "anchor_C_relative_error": c_error,
            "voting": False,
            "formal_case": False,
        }
        material = formal["parameter_contract"]["passive_region_materials"]["al2o3"]
        raw_alpha = float(material["thermal_conductivity_W_mK"]) / float(
            material["volumetric_heat_capacity_J_m3K"]
        )
        effective_alpha = raw_alpha * scales.conductance_scale / scales.capacity_scale
        row["effective_diffusivity_scale_G_over_C"] = (
            scales.conductance_scale / scales.capacity_scale
        )
        row["effective_thermal_diffusivity_m2_s"] = effective_alpha
        row["effective_penetration_depth_1kHz_m"] = float(
            np.sqrt(effective_alpha / (np.pi * 1.0e3))
        )
        for region in ("bare_vo2", "electrode_covered_vo2"):
            comparisons = {
                "mesh_D": vertical_response_comparison(
                    normalized[(depth, "coarse")].references[region],
                    normalized[(depth, "fine")].references[region],
                    fit_contract,
                ),
                "mesh_2D": vertical_response_comparison(
                    normalized[(comparator, "coarse")].references[region],
                    normalized[(comparator, "fine")].references[region],
                    fit_contract,
                ),
                "depth": vertical_response_comparison(
                    normalized[(depth, "fine")].references[region],
                    normalized[(comparator, "fine")].references[region],
                    fit_contract,
                ),
            }
            for name, comparison in comparisons.items():
                metrics = comparison["metrics"]
                for metric_name, value in metrics.items():
                    row[f"{region}_{name}_{metric_name}"] = float(value)
                pair_pass = pair_pass and _metric_pass(
                    metrics, repair, "mesh" if name.startswith("mesh") else "depth"
                )
                pointwise_rows.extend(
                    _pointwise_rows(
                        comparison,
                        depth_m=depth,
                        comparator_depth_m=comparator,
                        region=region,
                        comparison_id=name,
                    )
                )
            for physical_depth in (depth, comparator):
                for level in levels:
                    audit = vertical_passivity_and_identity_metrics(
                        normalized[(physical_depth, level)].references[region], fit_contract
                    )
                    audit_pass = _passivity_pass(audit, repair)
                    pair_pass = pair_pass and audit_pass
                    passivity_rows.append(
                        {
                            "depth_m": depth,
                            "physical_depth_m": physical_depth,
                            "comparator_depth_m": comparator,
                            "grid_level": level,
                            "region": region,
                            **audit,
                            "passed": audit_pass,
                            "voting": False,
                            "formal_case": False,
                        }
                    )
        times, frequencies = held_out_vertical_response_grid(fit_contract)
        omega = 2.0 * np.pi * frequencies
        finite = analytic_homogeneous_substrate_admittance_W_m2K(
            formal, omega, substrate_depth_m=depth
        )
        semi = analytic_homogeneous_substrate_admittance_W_m2K(
            formal, omega, substrate_depth_m=None
        )
        row["analytic_finite_vs_semi_frequency_log_magnitude_rmse"] = float(
            np.sqrt(np.mean((np.log(np.abs(finite)) - np.log(np.abs(semi))) ** 2))
        )
        row["passed_all_required_vertical_gates"] = pair_pass
        row["H1_v6_independent_reanchor_frequency_rmse"] = reproduced
        row["H2_shared_global_scale_bare_depth_frequency_rmse"] = row[
            "bare_vo2_depth_frequency_log_magnitude_rmse"
        ]
        row["H3_unified_spatial_resolution_contact_mesh_D_frequency_rmse"] = row[
            "electrode_covered_vo2_mesh_D_frequency_log_magnitude_rmse"
        ]
        substrate_comparison = vertical_response_comparison(
            raws[(depth, "fine")].substrate,
            raws[(comparator, "fine")].substrate,
            fit_contract,
        )
        row["H4_pure_substrate_frequency_rmse"] = substrate_comparison["metrics"][
            "frequency_log_magnitude_rmse"
        ]
        pointwise_rows.extend(
            _pointwise_rows(
                substrate_comparison,
                depth_m=depth,
                comparator_depth_m=comparator,
                region="al2o3_substrate_raw",
                comparison_id="H4_raw_substrate_depth",
            )
        )
        row["H5_substrate_plus_overlay_frequency_rmse"] = row[
            "electrode_covered_vo2_depth_frequency_log_magnitude_rmse"
        ]
        row["H5_minus_H2_diagnostic_only_not_additive"] = (
            float(row["H5_substrate_plus_overlay_frequency_rmse"])
            - float(row["H2_shared_global_scale_bare_depth_frequency_rmse"])
        )
        candidate_rows.append(row)
        if pair_pass:
            passing_depths.append(depth)

    maximum_depth = max(depths)
    maximum_pass = bool(
        next(row for row in candidate_rows if float(row["depth_m"]) == maximum_depth)[
            "passed_all_required_vertical_gates"
        ]
    )
    selected_depth = min(passing_depths) if maximum_pass and passing_depths else None
    vertical_status = "PASS_VERTICAL_REFERENCE" if selected_depth is not None else "NO_GO_VERTICAL_REFERENCE"

    k_rows: list[dict[str, object]] = []
    selected_k_by_region: dict[str, int] = {}
    k_status = "BLOCKED_BY_VERTICAL_REFERENCE"
    if selected_depth is not None:
        selected_models = normalized_pairs[selected_depth][(selected_depth, "fine")].references
        region_results: dict[str, dict[int, bool]] = {}
        for region, reference in selected_models.items():
            region_results[region] = {}
            fitted: dict[int, tuple[object, dict[str, float]]] = {}
            for order in (1, 8, 2):
                ladder, optimizer = fit_passive_ladder(reference, order, fit_contract)
                metrics = reduction_validation_metrics(reference, ladder, fit_contract)
                passed = _ladder_pass(metrics, repair)
                fitted[order] = (ladder, {**optimizer, **metrics})
                region_results[region][order] = passed
                k_rows.append(
                    {"region": region, "order": order, **optimizer, **metrics,
                     "passed": passed, "selected": False, "status": "evaluated",
                     "voting": False, "formal_case": False}
                )
        k2_all = all(region_results[region][2] for region in region_results)
        if k2_all:
            selected_k_by_region = {region: 2 for region in region_results}
            for region in region_results:
                k_rows.append({"region": region, "order": 3, "status": "not_run_K2_passed",
                               "passed": "", "selected": False, "voting": False, "formal_case": False})
            k_status = "PASS_K_STATE"
        else:
            for region, reference in selected_models.items():
                ladder, optimizer = fit_passive_ladder(reference, 3, fit_contract)
                metrics = reduction_validation_metrics(reference, ladder, fit_contract)
                passed = _ladder_pass(metrics, repair)
                region_results[region][3] = passed
                k_rows.append(
                    {"region": region, "order": 3, **optimizer, **metrics,
                     "passed": passed, "selected": False, "status": "evaluated",
                     "voting": False, "formal_case": False}
                )
            if all(region_results[region][3] for region in region_results):
                selected_k_by_region = {
                    region: 2 if region_results[region][2] else 3 for region in region_results
                }
                k_status = "PASS_K_STATE"
            else:
                k_status = "NO_GO_K_STATE"
        for row in k_rows:
            if isinstance(row.get("order"), int) and selected_k_by_region.get(str(row["region"])) == row["order"]:
                row["selected"] = True
    else:
        k_rows.append(
            {"region": "all", "order": "", "status": "blocked_by_NO_GO_VERTICAL_REFERENCE",
             "passed": False, "selected": False, "voting": False, "formal_case": False}
        )

    material = formal["parameter_contract"]["passive_region_materials"]["al2o3"]
    alpha = float(material["thermal_conductivity_W_mK"]) / float(
        material["volumetric_heat_capacity_J_m3K"]
    )
    output_root = ROOT / repair["outputs"]["root"]
    prereg = {
        **identities,
        "task_id": repair["task_id"],
        "schema_version": repair["schema_version"],
        "status": "bounded_repair_screen_complete",
        "formal_execution_count": 0,
        "formal_case_results_generated": 0,
        "formal_campaign_executed": False,
        "phase1_scientific_claim": "forbidden_pending_formal_campaign",
        "v6_warning_reproduced_value": reproduced,
        "v6_warning_relative_error": relative,
        "v6_reproduction_scales": {
            str(depth): {
                "conductance_scale": float(
                    v6_packages[(depth, "bare_vo2")].conductance_scale
                ),
                "capacity_scale": float(v6_packages[(depth, "bare_vo2")].capacity_scale),
            }
            for depth in (4.0e-7, 8.0e-7)
        },
        "v6_worst_frequency_diagnostic": {
            "frequency_Hz": float(
                np.asarray(
                    v6_comparisons["electrode_covered_vo2"]["frequency_Hz"]
                )[
                    int(
                        np.argmax(
                            np.abs(
                                np.asarray(
                                    v6_comparisons["electrode_covered_vo2"][
                                        "frequency_log_magnitude_error"
                                    ]
                                )
                            )
                        )
                    )
                ]
            ),
            "signed_log_magnitude_error": float(
                np.asarray(
                    v6_comparisons["electrode_covered_vo2"][
                        "frequency_log_magnitude_error"
                    ]
                )[
                    int(
                        np.argmax(
                            np.abs(
                                np.asarray(
                                    v6_comparisons["electrode_covered_vo2"][
                                        "frequency_log_magnitude_error"
                                    ]
                                )
                            )
                        )
                    )
                ]
            ),
        },
        "unique_raw_build_count": len(registry.unique_build_ids),
        "unique_raw_build_ids": list(registry.unique_build_ids),
        "raw_build_manifest": [record.__dict__ for record in registry.records()],
        "screening_code_sha256": {
            "runner": _sha256(Path(__file__).resolve()),
            "vertical_solver": _sha256(
                ROOT / "src" / "pinnpcm" / "solvers" / "vertical_multilayer_reference.py"
            ),
            "vertical_evaluator": _sha256(
                ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_phase1_gates.py"
            ),
        },
        "branch_reuse_mapping": {
            "substrate": "one branch per depth/grid reused by both regions",
            "overlay": "one branch per grid reused by every depth contact region",
        },
        "al2o3_thermal_diffusivity_m2_s": alpha,
        "thermal_penetration_depth_m": {
            str(frequency): float(np.sqrt(alpha / (np.pi * frequency)))
            for frequency in (1.0e3, 1.0e10)
        },
        "vertical_status": vertical_status,
        "selected_production_depth_m": selected_depth,
        "maximum_pair_passed": maximum_pass,
        "k_state_status": k_status,
        "selected_k_by_region": selected_k_by_region,
        "ready_for_formal_v7_freeze": bool(
            vertical_status == "PASS_VERTICAL_REFERENCE" and k_status == "PASS_K_STATE"
        ),
        "voting": False,
    }
    _atomic_json(output_root / "repair_preregistration.json", prereg)
    _atomic_csv(output_root / "vertical_reference_pointwise.csv", pointwise_rows)
    _atomic_csv(output_root / "vertical_candidate_summary.csv", candidate_rows)
    _atomic_csv(output_root / "vertical_passivity_and_identity.csv", passivity_rows)
    _atomic_csv(output_root / "k_state_selection.csv", k_rows)
    return prereg


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
        default=ROOT / "configs" / "geophase_phase1_vertical_repair_v7.yaml",
    )
    parser.add_argument("--repair-protocol-commit", required=True)
    parser.add_argument("--initial-preregistration-commit", required=True)
    parser.add_argument("--repair-yaml-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(
        args.formal_config.resolve(),
        args.repair_config.resolve(),
        initial_preregistration_commit=args.initial_preregistration_commit,
        repair_protocol_commit=args.repair_protocol_commit,
        repair_yaml_sha256=args.repair_yaml_sha256,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

"""Preflight and inventory gates for Phase 1 Checkpoint A."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Mapping

import numpy as np

from pinnpcm.solvers.vertical_multilayer_reference import (
    NormalizedVerticalReferences,
    build_normalized_vertical_references,
)


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_formal_case_inventory(config: dict) -> list[dict[str, object]]:
    """Materialize the exact locked 96-case plan without executing a case."""

    contract = config["formal_case_inventory"]
    rows: list[dict[str, object]] = []

    def append(group: str, **axes: object) -> None:
        group_index = 1 + sum(row["case_group"] == group for row in rows)
        rows.append(
            {
                "case_id": f"P1-{len(rows) + 1:03d}",
                "case_group": group,
                "group_index": group_index,
                "formal_status": "planned_not_executed",
                "evidence_type": "preregistered_case_manifest_only",
                **axes,
            }
        )

    vertical = contract["vertical_reference_and_reduction"]
    for region in vertical["region_ids"]:
        for order in vertical["model_orders"]:
            for response in vertical["response_types"]:
                append(
                    "vertical_reference_and_reduction",
                    region_id=region,
                    model_order=int(order),
                    response_type=response,
                )

    manufactured = contract["manufactured_solutions"]
    for problem in manufactured["problem_ids"]:
        for refinement in manufactured["refinement_levels"]:
            append(
                "manufactured_solutions",
                problem_id=problem,
                spatial_level=int(refinement),
            )

    single = contract["single_device_refinement"]
    for protocol in single["protocol_ids"]:
        for pair in single["grid_time_pairs"]:
            append(
                "single_device_refinement",
                protocol_id=protocol,
                spatial_level=int(pair["spatial_level"]),
                time_divisor=int(pair["time_divisor"]),
            )

    topology = contract["topology_and_prior_audits"]
    for audit in topology["audit_ids"]:
        for protocol in topology["protocol_ids"]:
            append(
                "topology_and_prior_audits",
                audit_id=audit,
                protocol_id=protocol,
            )

    for case_id in contract["decoupled_dual_copy_limits"]["case_ids"]:
        append("decoupled_dual_copy_limits", fixture_id=case_id)
    for case_id in contract["fail_closed_negative_controls"]["case_ids"]:
        append("fail_closed_negative_controls", fixture_id=case_id)
    for case_id in contract["analytic_limits"]["case_ids"]:
        append("analytic_limits", fixture_id=case_id)

    expected_by_group = {
        key: int(value["expected_count"])
        for key, value in contract.items()
        if isinstance(value, dict) and "expected_count" in value
    }
    for group, expected in expected_by_group.items():
        actual = sum(row["case_group"] == group for row in rows)
        if actual != expected:
            raise ValueError(f"formal group {group} has {actual} cases, expected {expected}")
    expected_total = int(contract["total_expected_count"])
    maximum = int(config["execution_contract"]["maximum_solver_cases"])
    declared_total = int(config["execution_contract"]["formal_case_inventory_total"])
    if len(rows) != expected_total or len(rows) != declared_total or len(rows) > maximum:
        raise ValueError("formal case inventory violates its locked total")
    if len({str(row["case_id"]) for row in rows}) != len(rows):
        raise ValueError("formal case identifiers are not unique")
    return rows


def source_scale_preflight(
    config: dict,
    *,
    normalized_references: NormalizedVerticalReferences | None = None,
) -> dict[str, float | bool]:
    """Run zero-solver algebraic checks; these are not scientific results."""

    conductivity = config["parameter_contract"]["vo2_conductivity"]
    geometry = config["geometry"]["primary_single_device"]
    thermal = config["parameter_contract"]["active_plane_thermal"]
    normalization = config["vertical_reference"]["device_effective_normalization"]
    gates = config["analytic_source_scale_preflights"]
    length = float(conductivity["effective_current_path_m"])
    area = float(conductivity["effective_width_m"]) * float(
        conductivity["active_thickness_m"]
    )
    reference_temperature = float(conductivity["reference_temperature_K"])
    insulating_resistance = float(
        conductivity["source_resistance_prefactor_ohm"]
    ) * np.exp(
        float(conductivity["source_activation_temperature_K"])
        / reference_temperature
    ) + float(conductivity["source_metallic_resistance_ohm"])
    mapped_insulating_resistance = length / (
        area * float(conductivity["sigma_ins_ref_S_m"])
    )
    insulating_error = abs(mapped_insulating_resistance - insulating_resistance) / insulating_resistance
    metallic_resistance = float(conductivity["source_metallic_resistance_ohm"])
    mapped_metallic_resistance = length / (
        area * float(conductivity["sigma_met_ref_S_m"])
    )
    metallic_error = abs(mapped_metallic_resistance - metallic_resistance) / metallic_resistance

    active_capacity = (
        float(thermal["vo2_volumetric_heat_capacity_J_m3K"])
        * float(geometry["vo2_thickness_m"])
        * float(geometry["vo2_length_m"])
        * float(geometry["vo2_width_m"])
    )
    total_capacity = active_capacity + float(
        normalization["nominal_memory_capacity_target_J_K"]
    )
    target_total_capacity = float(normalization["nominal_total_thermal_capacity_J_K"])
    capacity_error = abs(total_capacity - target_total_capacity) / target_total_capacity

    references = normalized_references or build_normalized_vertical_references(config)
    target_conductance = float(
        normalization["nominal_total_thermal_conductance_W_K"]
    )
    conductance_error = abs(
        references.integrated_dc_conductance_W_K - target_conductance
    ) / target_conductance
    checks: dict[str, float | bool] = {
        "uniform_insulating_resistance_relative_error": float(insulating_error),
        "uniform_metallic_resistance_relative_error": float(metallic_error),
        "active_plus_memory_capacity_relative_error": float(capacity_error),
        "area_integrated_dc_thermal_conductance_relative_error": float(conductance_error),
        "conductance_scale_positive": bool(references.conductance_scale > 0.0),
        "capacity_scale_positive": bool(references.capacity_scale > 0.0),
        "electrical_endmembers_positive": bool(
            float(conductivity["sigma_ins_ref_S_m"]) > 0.0
            and float(conductivity["sigma_met_ref_S_m"]) > 0.0
        ),
    }
    passed = (
        insulating_error <= float(gates["uniform_insulating_resistance_relative_error_max"])
        and metallic_error <= float(gates["uniform_metallic_resistance_relative_error_max"])
        and capacity_error <= float(gates["active_plus_memory_capacity_relative_error_max"])
        and conductance_error
        <= float(gates["area_integrated_dc_thermal_conductance_relative_error_max"])
        and bool(checks["conductance_scale_positive"])
        and bool(checks["capacity_scale_positive"])
        and bool(checks["electrical_endmembers_positive"])
    )
    checks["passed"] = passed
    if not passed:
        raise ValueError("one or more locked source-scale preflights failed")
    return checks


def substrate_depth_truncation_metrics(config: dict) -> dict[str, object]:
    """Compare the two locked high-order vertical-depth references.

    Checkpoint A may exercise this evaluator, but only the formal cases may
    cast a scientific vote.  The returned values therefore contain no claim
    status.
    """

    depths = [float(value) for value in config["vertical_reference"]["substrate_depth_audit_m"]]
    if len(depths) != 2 or not depths[1] > depths[0] > 0.0:
        raise ValueError("substrate-depth audit requires two increasing positive depths")
    shallow = build_normalized_vertical_references(config, substrate_depth_m=depths[0])
    deep = build_normalized_vertical_references(config, substrate_depth_m=depths[1])
    fit = config["vertical_reference"]["reduction_fit_contract"]
    time_grid = fit["time_fit_grid"]
    frequency_grid = fit["frequency_fit_grid_Hz"]
    fit_times = np.geomspace(
        float(time_grid["start_s"]),
        float(time_grid["stop_s"]),
        int(time_grid["points"]),
    )
    times = np.sqrt(fit_times[:-1] * fit_times[1:])
    fit_frequency = np.geomspace(
        float(frequency_grid["start"]),
        float(frequency_grid["stop"]),
        int(frequency_grid["points"]),
    )
    omega = 2.0 * np.pi * np.sqrt(fit_frequency[:-1] * fit_frequency[1:])
    region_metrics: dict[str, dict[str, float]] = {}
    for region in sorted(shallow.references):
        shallow_model = shallow.references[region]
        deep_model = deep.references[region]
        shallow_step = shallow_model.step_heat_flux_W_m2(times)
        deep_step = deep_model.step_heat_flux_W_m2(times)
        deep_zero = float(deep_model.step_heat_flux_W_m2(np.asarray([0.0]))[0])
        step_scale = max(
            float(np.sqrt(np.mean((deep_step - deep_zero) ** 2))), 1.0e-30
        )
        step_nrmse = float(
            np.sqrt(np.mean((shallow_step - deep_step) ** 2)) / step_scale
        )
        shallow_frequency = shallow_model.driving_admittance_W_m2K(omega)
        deep_frequency = deep_model.driving_admittance_W_m2K(omega)
        frequency_rmse = float(
            np.sqrt(
                np.mean(
                    (
                        np.log(np.maximum(np.abs(shallow_frequency), 1.0e-300))
                        - np.log(np.maximum(np.abs(deep_frequency), 1.0e-300))
                    )
                    ** 2
                )
            )
        )
        region_metrics[region] = {
            "step_response_nrmse": step_nrmse,
            "frequency_log_magnitude_rmse": frequency_rmse,
        }
    values = [value for region in region_metrics.values() for value in region.values()]
    if not np.isfinite(np.asarray(values, dtype=float)).all():
        raise ValueError("substrate-depth audit produced a nonfinite metric")
    gates = config["gates"]
    passed = all(
        region["step_response_nrmse"]
        <= float(gates["substrate_depth_step_response_nrmse_max"])
        and region["frequency_log_magnitude_rmse"]
        <= float(gates["substrate_depth_frequency_log_magnitude_rmse_max"])
        for region in region_metrics.values()
    )
    return {
        "depths_m": depths,
        "regions": region_metrics,
        "would_pass_locked_gate": bool(passed),
    }


def contact_overlap_qoi_audit(
    config: dict,
    qoi_by_overlap: Mapping[float, Mapping[str, float]],
    spatial_fine_pair_relative_error: Mapping[str, float],
) -> dict[str, object]:
    """Audit overlap sensitivity against like-for-like discretization error."""

    geometry = config["geometry"]["primary_single_device"]
    overlaps = [float(value) for value in geometry["contact_overlap_audit_m"]]
    nominal = float(geometry["contact_overlap_nominal_m"])
    provided = {float(key): value for key, value in qoi_by_overlap.items()}
    if set(provided) != set(overlaps) or nominal not in provided:
        raise ValueError("contact-overlap audit does not cover the locked axis")
    names = set(provided[nominal])
    if not names or any(set(values) != names for values in provided.values()):
        raise ValueError("contact-overlap QoI names are inconsistent")
    if set(spatial_fine_pair_relative_error) != names:
        raise ValueError("spatial-error QoIs do not match overlap QoIs")
    effects: dict[str, float] = {}
    eligible = True
    for name in sorted(names):
        nominal_value = float(provided[nominal][name])
        scale = max(abs(nominal_value), 1.0e-30)
        effect = max(
            abs(float(values[name]) - nominal_value) / scale
            for values in provided.values()
        )
        spatial_error = float(spatial_fine_pair_relative_error[name])
        if not np.isfinite([effect, spatial_error]).all() or spatial_error < 0.0:
            raise ValueError("contact-overlap audit received invalid metrics")
        effects[name] = float(effect)
        eligible = eligible and effect <= spatial_error
    return {
        "relative_effect_by_qoi": effects,
        "geometry_robust_wording_eligible": bool(eligible),
        "reporting_required": bool(
            config["gates"]["contact_overlap_qoi_sensitivity_reporting_required"]
        ),
    }


def source_envelope_noise_audit(
    config: dict, source_values: np.ndarray, numerical_noise: float
) -> dict[str, float | bool]:
    """Check whether a source-envelope variation rises above numerical noise."""

    values = np.asarray(source_values, dtype=float)
    noise = float(numerical_noise)
    if values.ndim != 1 or values.size < 2 or not np.isfinite(values).all():
        raise ValueError("source-envelope audit requires finite one-dimensional values")
    if not np.isfinite(noise) or noise < 0.0:
        raise ValueError("numerical noise must be finite and nonnegative")
    variation = float(np.max(values) - np.min(values))
    ratio = variation / max(noise, np.finfo(float).tiny)
    minimum = float(config["gates"]["source_envelope_to_numerical_noise_ratio_min"])
    return {
        "source_envelope_variation": variation,
        "numerical_noise": noise,
        "variation_to_noise_ratio": float(ratio),
        "eligible_to_vote": bool(ratio >= minimum),
    }

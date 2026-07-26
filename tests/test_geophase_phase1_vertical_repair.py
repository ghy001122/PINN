from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_phase1_gates import (
    substrate_depth_truncation_metrics,
    vertical_passivity_and_identity_metrics,
    vertical_response_comparison,
)
from pinnpcm.solvers.vertical_multilayer_reference import (
    VerticalRawBuildRegistry,
    VerticalReferenceModalEvaluator,
    analytic_homogeneous_substrate_admittance_W_m2K,
    apply_repair_normalization,
    bisect_cell_widths,
    build_normalized_vertical_references,
    build_repair_overlay_branch,
    build_repair_raw_components,
    build_repair_substrate_branch,
    geometric_surface_refined_cell_widths,
    repair_normalization_scales,
    repair_surface_cell_bound_m,
)


ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _configs() -> tuple[dict, dict]:
    return (
        _yaml("configs/geophase_phase1_2p5d_reference.yaml"),
        _yaml("configs/geophase_phase1_vertical_repair_v7.yaml"),
    )


def test_locked_geometric_grid_has_exact_first_cell_and_nested_fine_grid() -> None:
    formal, repair = _configs()
    depth = 4.0e-7
    first = repair_surface_cell_bound_m(formal, repair)
    ratio = float(repair["nonuniform_grid"]["adjacent_cell_growth_ratio_max"])
    coarse = geometric_surface_refined_cell_widths(
        depth, top_cell_m=first, growth_ratio=ratio
    )
    fine = bisect_cell_widths(coarse)
    assert coarse[0] == first
    assert np.isclose(np.sum(coarse), depth, rtol=2.0e-14, atol=0.0)
    assert np.max(coarse[1:] / coarse[:-1]) <= ratio
    assert np.array_equal(fine.reshape(-1, 2).sum(axis=1), coarse)
    assert np.all(fine.reshape(-1, 2)[:, 0] == fine.reshape(-1, 2)[:, 1])


def test_overlay_grid_is_interface_aligned_and_depth_invariant() -> None:
    formal, repair = _configs()
    geometry = formal["geometry"]["primary_single_device"]
    coarse, coarse_widths = build_repair_overlay_branch(
        formal, repair, grid_level="coarse"
    )
    fine, fine_widths = build_repair_overlay_branch(
        formal, repair, grid_level="fine"
    )
    assert coarse.order == 16
    assert fine.order == 32
    assert np.isclose(np.sum(coarse_widths[:8]), geometry["ti_thickness_m"])
    assert np.isclose(np.sum(coarse_widths[8:]), geometry["au_thickness_m"])
    assert np.array_equal(fine_widths.reshape(-1, 2).sum(axis=1), coarse_widths)


def test_pair_normalization_uses_only_D_fine_and_is_not_reanchored() -> None:
    formal, repair = _configs()
    overlay, overlay_widths = build_repair_overlay_branch(
        formal, repair, grid_level="fine"
    )
    anchor = build_repair_raw_components(
        formal,
        repair,
        substrate_depth_m=4.0e-7,
        grid_level="fine",
        overlay_branch=overlay,
        overlay_cell_widths_m=overlay_widths,
    )
    comparator = build_repair_raw_components(
        formal,
        repair,
        substrate_depth_m=8.0e-7,
        grid_level="fine",
        overlay_branch=overlay,
        overlay_cell_widths_m=overlay_widths,
    )
    scales = repair_normalization_scales(anchor, formal)
    normalized_anchor = apply_repair_normalization(anchor, scales)
    normalized_comparator = apply_repair_normalization(comparator, scales)
    normalization = formal["vertical_reference"]["device_effective_normalization"]
    assert np.isclose(
        normalized_anchor.integrated_dc_conductance_W_K,
        normalization["nominal_total_thermal_conductance_W_K"],
        rtol=1.0e-12,
        atol=0.0,
    )
    assert np.isclose(
        normalized_anchor.integrated_memory_capacity_J_K,
        normalization["nominal_memory_capacity_target_J_K"],
        rtol=1.0e-12,
        atol=0.0,
    )
    assert normalized_comparator.conductance_scale == normalized_anchor.conductance_scale
    assert normalized_comparator.capacity_scale == normalized_anchor.capacity_scale
    assert not np.isclose(
        normalized_comparator.integrated_memory_capacity_J_K,
        normalization["nominal_memory_capacity_target_J_K"],
        rtol=1.0e-12,
        atol=0.0,
    )


def test_modal_evaluator_matches_existing_state_space_semantics() -> None:
    formal, _ = _configs()
    reference = build_normalized_vertical_references(
        formal, substrate_depth_m=4.0e-7, cells_per_layer=3
    ).references["electrode_covered_vo2"]
    modal = VerticalReferenceModalEvaluator(reference)
    times = np.asarray([0.0, 1.0e-10, 2.0e-7, 2.0e-5])
    omega = 2.0 * np.pi * np.asarray([1.0e3, 1.0e6, 1.0e10])
    assert np.allclose(
        modal.step_heat_flux_W_m2(times),
        reference.step_heat_flux_W_m2(times),
        rtol=1.0e-10,
        atol=1.0e-12,
    )
    assert np.allclose(
        modal.impulse_tail_W_m2K_s(times),
        reference.impulse_tail_W_m2K_s(times),
        rtol=1.0e-10,
        atol=1.0e-12,
    )
    assert np.allclose(
        modal.driving_admittance_W_m2K(omega),
        reference.driving_admittance_W_m2K(omega),
        rtol=1.0e-10,
        atol=1.0e-12,
    )


def test_locked_response_metrics_and_identity_audit_are_finite() -> None:
    formal, _ = _configs()
    reference = build_normalized_vertical_references(
        formal, substrate_depth_m=4.0e-7, cells_per_layer=3
    ).references["bare_vo2"]
    fit = formal["vertical_reference"]["reduction_fit_contract"]
    comparison = vertical_response_comparison(reference, reference, fit)
    assert comparison["metrics"] == {
        "step_response_nrmse": 0.0,
        "impulse_response_nrmse": 0.0,
        "frequency_log_magnitude_rmse": 0.0,
    }
    audit = vertical_passivity_and_identity_metrics(reference, fit)
    assert audit["minimum_capacity_J_m2K"] > 0.0
    assert audit["minimum_physical_conductance_W_m2K"] > 0.0
    assert audit["maximum_pole_real_per_s"] < 0.0
    assert audit["minimum_conductance_matrix_eigenvalue_W_m2K"] > 0.0
    for name in (
        "step_initial_relative_error",
        "step_DC_relative_error",
        "impulse_integral_relative_error",
        "impulse_step_derivative_relative_error",
        "frequency_state_space_relative_error",
    ):
        assert audit[name] <= 1.0e-10


def test_raw_uniform_slab_tracks_locked_analytic_admittance_direction() -> None:
    formal, repair = _configs()
    reference, _ = build_repair_substrate_branch(
        formal,
        repair,
        substrate_depth_m=4.0e-7,
        grid_level="fine",
    )
    omega = 2.0 * np.pi * np.asarray([1.0e3, 1.0e7, 1.0e10])
    finite = analytic_homogeneous_substrate_admittance_W_m2K(
        formal, omega, substrate_depth_m=4.0e-7
    )
    semi = analytic_homogeneous_substrate_admittance_W_m2K(
        formal, omega, substrate_depth_m=None
    )
    numerical = VerticalReferenceModalEvaluator(reference).driving_admittance_W_m2K(
        omega
    )
    assert np.all(np.real(finite) >= 0.0)
    assert np.all(np.real(semi) >= 0.0)
    assert abs(numerical[-1] - finite[-1]) / abs(finite[-1]) <= 2.0e-2
    assert abs(finite[-1] - semi[-1]) / abs(semi[-1]) <= 2.0e-2


def test_raw_build_registry_reuses_identity_and_fails_on_spec_drift() -> None:
    registry = VerticalRawBuildRegistry()
    calls = 0

    def builder() -> object:
        nonlocal calls
        calls += 1
        return object()

    first = registry.get_or_build("substrate_D4e-7_coarse", {"depth_m": 4.0e-7}, builder)
    second = registry.get_or_build("substrate_D4e-7_coarse", {"depth_m": 4.0e-7}, builder)
    assert second is first
    assert calls == 1
    record = registry.records()[0]
    assert record.builder_invocation_count == 1
    assert record.request_count == 2
    registry.assert_exactly_once(["substrate_D4e-7_coarse"])

    with np.testing.assert_raises(ValueError):
        registry.get_or_build(
            "substrate_D4e-7_coarse", {"depth_m": 8.0e-7}, builder
        )
    with np.testing.assert_raises(ValueError):
        registry.assert_exactly_once(
            ["substrate_D4e-7_coarse", "substrate_D8e-7_coarse"]
        )


def test_v6_warning_and_frequency_pointwise_rows_reaggregate_exactly() -> None:
    formal, _ = _configs()
    expected = 0.12312709438789984
    audit = substrate_depth_truncation_metrics(formal)
    actual = audit["regions"]["electrode_covered_vo2"][
        "frequency_log_magnitude_rmse"
    ]
    assert abs(actual - expected) / expected <= 1.0e-10

    shallow = build_normalized_vertical_references(
        formal, substrate_depth_m=4.0e-7, cells_per_layer=8
    ).references["electrode_covered_vo2"]
    deep = build_normalized_vertical_references(
        formal, substrate_depth_m=8.0e-7, cells_per_layer=8
    ).references["electrode_covered_vo2"]
    comparison = vertical_response_comparison(
        shallow,
        deep,
        formal["vertical_reference"]["reduction_fit_contract"],
    )
    pointwise = comparison["frequency_squared_rmse_contribution"]
    cumulative = comparison["frequency_cumulative_rmse"]
    reaggregated = float(np.sqrt(np.sum(pointwise)))
    assert np.isclose(reaggregated, comparison["metrics"]["frequency_log_magnitude_rmse"])
    assert np.isclose(cumulative[-1], reaggregated)
    assert abs(reaggregated - expected) / expected <= 1.0e-10

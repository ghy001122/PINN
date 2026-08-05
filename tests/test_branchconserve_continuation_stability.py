from __future__ import annotations

from pathlib import Path

import numpy as np

from pinnpcm.branchconserve.continuation import (
    first_contiguous_load_line_bracket,
    fixed_source_bracket_points,
    is_inside_physical_atlas_domain,
    should_start_pseudo_arclength,
    solve_fixed_source_equilibrium,
)
from pinnpcm.branchconserve.contract import load_branchconserve_contract
from pinnpcm.branchconserve.stability import (
    certify_branch_conditioned_stability,
    certify_dense_test_operator,
)
from pinnpcm.branchconserve.steady_model import build_branchconserve_model


ROOT = Path(__file__).resolve().parents[1]


def _model():
    contract = load_branchconserve_contract(
        ROOT / "configs/q2_branchconserve_2d_steady_mve_v1.yaml",
        repository_root=ROOT,
    )
    return build_branchconserve_model(contract, spatial_level=1)


def test_zero_source_load_line_reuses_full_equilibrium_certification() -> None:
    outcome = solve_fixed_source_equilibrium(
        _model(), source_voltage_V=0.0, branch_memory=1.0, include_stability=False
    )
    assert outcome.success
    assert outcome.device_voltage_V == 0.0
    assert outcome.certified_evaluation is not None
    assert outcome.certified_evaluation.load_line_residual <= 1.0e-10


def test_load_line_scan_starts_from_the_branch_endpoint() -> None:
    heating = fixed_source_bracket_points(
        source_voltage_V=15.8, branch_memory=1.0, count=33
    )
    cooling = fixed_source_bracket_points(
        source_voltage_V=15.8, branch_memory=-1.0, count=33
    )
    assert heating[0] == 0.0 and heating[-1] == 15.8
    assert cooling[0] == 15.8 and cooling[-1] == 0.0


def test_pseudo_arclength_points_cannot_leave_the_positive_source_domain() -> None:
    assert is_inside_physical_atlas_domain(
        device_voltage_V=3.0, source_voltage_V=6.2, source_voltage_max_V=15.8
    )
    assert not is_inside_physical_atlas_domain(
        device_voltage_V=-0.1, source_voltage_V=1.0, source_voltage_max_V=15.8
    )
    assert not is_inside_physical_atlas_domain(
        device_voltage_V=2.0, source_voltage_V=1.0, source_voltage_max_V=15.8
    )
    assert not is_inside_physical_atlas_domain(
        device_voltage_V=10.0, source_voltage_V=16.0, source_voltage_max_V=15.8
    )


def test_load_line_bracket_skips_leading_invalid_points_but_not_internal_gaps() -> None:
    points = np.asarray([3.0, 2.0, 1.0, 0.0])
    leading_invalid = {3.0: None, 2.0: -1.0, 1.0: 1.0, 0.0: 2.0}
    assert first_contiguous_load_line_bracket(
        points, lambda point: leading_invalid[point]
    ) == (2.0, 1.0)
    internal_gap = {3.0: -1.0, 2.0: None, 1.0: 1.0, 0.0: 2.0}
    assert first_contiguous_load_line_bracket(
        points, lambda point: internal_gap[point]
    ) is None


def test_zero_source_sparse_stability_is_certified_from_real_payload() -> None:
    model = _model()
    outcome = certify_branch_conditioned_stability(
        model,
        temperature_K=np.full(model.grid.shape, model.ambient_temperature_K),
        device_voltage_V=0.0,
        source_voltage_V=0.0,
        branch_memory=1.0,
    )
    assert outcome.success
    assert outcome.stable
    assert np.max(outcome.relative_residuals) <= 1.0e-6


def test_arclength_trigger_ignores_source_slope_and_requires_minimum_step() -> None:
    assert not should_start_pseudo_arclength(
        fixed_device_voltage_failed_at_minimum_step=False,
        current_tangent_device_voltage=0.01,
        previous_tangent_device_voltage=-0.01,
    )
    assert should_start_pseudo_arclength(
        fixed_device_voltage_failed_at_minimum_step=True,
        current_tangent_device_voltage=0.05,
        previous_tangent_device_voltage=0.06,
    )
    assert should_start_pseudo_arclength(
        fixed_device_voltage_failed_at_minimum_step=True,
        current_tangent_device_voltage=0.5,
        previous_tangent_device_voltage=-0.5,
    )
    assert not should_start_pseudo_arclength(
        fixed_device_voltage_failed_at_minimum_step=True,
        current_tangent_device_voltage=0.5,
        previous_tangent_device_voltage=0.4,
    )


def test_sparse_rightmost_helper_does_not_need_full_dense_spectrum() -> None:
    matrix = np.diag([-4.0, -3.0, -2.0, -1.0])
    values, _ = certify_dense_test_operator(matrix, eigenpairs=2)
    assert np.allclose(np.sort(values.real), [-2.0, -1.0], atol=1.0e-8)

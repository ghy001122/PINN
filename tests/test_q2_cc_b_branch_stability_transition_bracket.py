from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.current_clamp.cc_b_branch_stability_transition_bracket import (
    COVERAGE_DISPOSITION,
    NO_GO_DISPOSITION,
    PASS_DISPOSITION,
    PATTERN_DISPOSITION,
    SEMANTICS_DISPOSITION,
    build_registered_nominal_model,
    classify_mode,
    continuation_connected,
    load_bracket_contract,
    mode_metrics,
    refine_bracket_side,
    select_terminal_disposition,
)
from pinnpcm.current_clamp.cc_b_model import build_cc_b_model


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_cc_b_branch_stability_transition_bracket_v1.yaml"


@pytest.fixture(scope="module")
def contract():
    return load_bracket_contract(CONFIG, repository_root=ROOT)


def test_contract_authenticates_pr34_and_freezes_lattice(contract) -> None:
    assert contract.raw["authority"]["pr_34_merge_sha"] == (
        "22ed32018d5463e171be960beb00710a055a1f13"
    )
    currents = tuple(contract.raw["scope"]["fixed_currents_A"])
    assert currents == pytest.approx(tuple(index * 5.0e-5 for index in range(2, 15)))
    assert len(currents) == len(set(currents)) == 13
    assert contract.raw["scope"]["heating_order"] == "increasing"
    assert contract.raw["scope"]["cooling_order"] == "decreasing"
    assert contract.raw["scientific_vote"] is False
    assert contract.raw["formal_execution_count"] == 0
    assert contract.raw["cc_b_matrix_launch_count"] == 0


def test_registered_half_step_changes_only_external_current(contract) -> None:
    parent = build_cc_b_model(
        contract.parent,
        spatial_level=1,
        current_set_A=2.0e-4,
        branch="heating",
        defect="NOM",
    )
    half = build_registered_nominal_model(
        contract,
        spatial_level=1,
        current_set_A=1.5e-4,
        branch="heating",
    )
    assert half.current_set_A == 1.5e-4
    assert half.contract is parent.contract
    assert np.array_equal(half.thermal_matrix.toarray(), parent.thermal_matrix.toarray())
    assert np.array_equal(
        half.vertical_conductance_W_m2K, parent.vertical_conductance_W_m2K
    )
    assert np.array_equal(half.areal_capacity_J_m2K, parent.areal_capacity_J_m2K)
    with pytest.raises(ValueError):
        build_registered_nominal_model(
            contract,
            spatial_level=1,
            current_set_A=7.5e-4,
            branch="heating",
        )


def test_continuation_chain_never_recovers_after_break() -> None:
    active = True
    active = continuation_connected(
        chain_active=active,
        equilibrium_valid=True,
        spectrum_valid=True,
        stable=True,
    )
    assert active
    active = continuation_connected(
        chain_active=active,
        equilibrium_valid=True,
        spectrum_valid=True,
        stable=False,
    )
    assert not active
    assert not continuation_connected(
        chain_active=active,
        equilibrium_valid=True,
        spectrum_valid=True,
        stable=True,
    )


def test_deterministic_boundary_refinement_has_three_unique_midpoints() -> None:
    lower, upper = 2.0e-4, 2.5e-4
    lower_stable = True
    observed: list[float] = []
    for midpoint_stable in (True, False, True):
        observed.append(0.5 * (lower + upper))
        lower, upper = refine_bracket_side(
            lower,
            upper,
            lower_stable=lower_stable,
            midpoint_stable=midpoint_stable,
        )
        if midpoint_stable == lower_stable:
            lower_stable = midpoint_stable
    assert len(observed) == len(set(observed)) == 3
    assert all(2.0e-4 < value < 2.5e-4 for value in observed)


def test_mode_metrics_are_phase_sign_and_scale_invariant(contract) -> None:
    model = build_registered_nominal_model(
        contract,
        spatial_level=1,
        current_set_A=2.0e-4,
        branch="heating",
    )
    ny, nx = model.grid.shape
    y = np.arange(ny, dtype=float)
    field = np.cos(np.pi * (y + 0.5) / ny)[:, None] * np.ones((1, nx))
    base = mode_metrics(model, -1.0 + 2.0j, field.reshape(-1).astype(complex))
    for factor in (-3.0, 2.5j, -0.5j):
        transformed = mode_metrics(
            model,
            -1.0 + 2.0j,
            factor * field.reshape(-1).astype(complex),
        )
        for key in (
            "uniform_mass_overlap",
            "x_gradient_energy_fraction",
            "y_gradient_energy_fraction",
            "participation_ratio",
        ):
            assert transformed[key] == pytest.approx(base[key], abs=1.0e-12)
        assert transformed["dominant_transverse_mode_index"] == 1
    assert classify_mode(contract, base) == "transverse-dominated"


def test_grid_coordinate_orientation_and_synthetic_modes(contract) -> None:
    model = build_registered_nominal_model(
        contract,
        spatial_level=1,
        current_set_A=2.0e-4,
        branch="heating",
    )
    ny, nx = model.grid.shape
    assert model.grid.x_edges_m[-1] - model.grid.x_edges_m[0] == pytest.approx(1.0e-7)
    assert model.grid.y_edges_m[-1] - model.grid.y_edges_m[0] == pytest.approx(5.0e-7)
    uniform = mode_metrics(model, -1.0, np.ones(ny * nx, dtype=complex))
    assert uniform["uniform_mass_overlap"] == pytest.approx(1.0)
    x_field = np.tile(np.arange(nx) - (nx - 1) / 2.0, (ny, 1))
    x_mode = mode_metrics(model, -1.0, x_field.reshape(-1).astype(complex))
    assert x_mode["x_gradient_energy_fraction"] == pytest.approx(1.0)
    y_field = np.tile(
        (np.arange(ny) - (ny - 1) / 2.0)[:, None], (1, nx)
    )
    y_mode = mode_metrics(model, -1.0, y_field.reshape(-1).astype(complex))
    assert y_mode["y_gradient_energy_fraction"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("heating", "cooling", "patterned", "invalid", "expected"),
    [
        (True, True, False, False, PASS_DISPOSITION),
        (True, False, False, False, COVERAGE_DISPOSITION),
        (False, True, True, False, COVERAGE_DISPOSITION),
        (False, False, True, False, PATTERN_DISPOSITION),
        (False, False, False, False, NO_GO_DISPOSITION),
        (True, True, False, True, SEMANTICS_DISPOSITION),
    ],
)
def test_terminal_disposition_is_mutually_exclusive(
    heating: bool,
    cooling: bool,
    patterned: bool,
    invalid: bool,
    expected: str,
) -> None:
    assert (
        select_terminal_disposition(
            branch_pass={"heating": heating, "cooling": cooling},
            patterned=patterned,
            numeric_invalid=invalid,
        )
        == expected
    )


def test_new_module_does_not_import_retired_or_downstream_paths() -> None:
    import pinnpcm.current_clamp.cc_b_branch_stability_transition_bracket as module

    syntax = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = (
        "controller",
        "geophase_nls",
        "exact_condensed",
        "pinnpcm.pinn",
        "inverse",
    )
    assert not any(any(token in name for token in forbidden) for name in imports)

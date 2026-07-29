from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.solvers import geophase_2p5d_fvm as electrical_fvm
from pinnpcm.solvers.geophase_2p5d_fvm import (
    SheetElectricalTimings,
    build_sheet_electrical_topology,
    factor_sheet_electrical,
    solve_sheet_electrical,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
ORACLE_PATH = ROOT / "tests" / "oracles" / "pr8_geophase_2p5d_fvm.py"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _load_oracle_module():
    module_name = "_pr8_geophase_2p5d_fvm_oracle"
    spec = importlib.util.spec_from_file_location(module_name, ORACLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the frozen PR #8 electrical oracle")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ORACLE = _load_oracle_module()


def _conductivity_field(grid, context_name: str) -> np.ndarray:
    x = np.linspace(0.0, 1.0, grid.nx, dtype=float)[None, :]
    y = np.linspace(0.0, 1.0, grid.ny, dtype=float)[:, None]
    if context_name == "equilibrium_like":
        return np.full(grid.shape, 2.5e4, dtype=float)
    if context_name == "legal_critical_like":
        return 2.5e4 * np.exp(1.7 * x + 0.3 * y)
    if context_name == "high_conductive_like":
        return 8.0e5 * (1.0 + 0.2 * x + 0.1 * y)
    raise ValueError(f"unknown electrical parity context: {context_name}")


@pytest.fixture(scope="module")
def electrical_context():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    conductivity_fields = {
        context_name: _conductivity_field(grid, context_name)
        for context_name in (
            "equilibrium_like",
            "legal_critical_like",
            "high_conductive_like",
        )
    }
    return config, grid, conductivity_fields


def _assert_normalized_array_equal(
    candidate: np.ndarray,
    oracle: np.ndarray,
    *,
    denominator_floor: float,
) -> None:
    numerator = float(np.max(np.abs(candidate - oracle)))
    denominator = max(
        float(np.max(np.abs(candidate))),
        float(np.max(np.abs(oracle))),
        denominator_floor,
    )
    assert numerator / denominator <= 1.0e-12


def _assert_normalized_scalar_equal(
    candidate: float, oracle: float, *, denominator_floor: float
) -> None:
    denominator = max(abs(candidate), abs(oracle), denominator_floor)
    assert abs(candidate - oracle) / denominator <= 1.0e-12


@pytest.mark.parametrize("context_name", ["equilibrium_like", "legal_critical_like", "high_conductive_like"])
@pytest.mark.parametrize("source_voltage_V", [1.0, 12.5, 15.8])
def test_vectorized_superlu_path_matches_frozen_pr8_scalar_oracle(
    electrical_context, context_name: str, source_voltage_V: float
) -> None:
    _config, grid, conductivity_fields = electrical_context
    conductivity = conductivity_fields[context_name]

    oracle = ORACLE.solve_sheet_electrical(grid, conductivity, source_voltage_V)
    candidate = solve_sheet_electrical(grid, conductivity, source_voltage_V)

    _assert_normalized_array_equal(
        candidate.potential_V,
        oracle.potential_V,
        denominator_floor=max(1.0, source_voltage_V),
    )
    _assert_normalized_array_equal(
        candidate.cell_joule_power_W,
        oracle.cell_joule_power_W,
        denominator_floor=1.0e-30,
    )
    for name in ("source_current_A", "ground_current_A"):
        _assert_normalized_scalar_equal(
            getattr(candidate, name),
            getattr(oracle, name),
            denominator_floor=1.0e-12,
        )
    for name in ("joule_power_W", "terminal_device_power_W"):
        _assert_normalized_scalar_equal(
            getattr(candidate, name),
            getattr(oracle, name),
            denominator_floor=1.0e-30,
        )
    for name in ("relative_current_imbalance", "relative_power_imbalance"):
        _assert_normalized_scalar_equal(
            getattr(candidate, name),
            getattr(oracle, name),
            denominator_floor=1.0,
        )


@pytest.mark.parametrize("spatial_level", [1, 2, 4])
@pytest.mark.parametrize(
    ("context_name", "source_voltage_V"),
    [
        ("equilibrium_like", 1.0),
        ("legal_critical_like", 12.5),
        ("high_conductive_like", 15.8),
    ],
)
def test_vectorized_oracle_parity_covers_L1_L2_L4_and_all_frozen_contexts(
    electrical_context,
    spatial_level: int,
    context_name: str,
    source_voltage_V: float,
) -> None:
    config, _small_grid, _small_fields = electrical_context
    grid = build_geophase_grid(config, spatial_level=spatial_level)
    conductivity = _conductivity_field(grid, context_name)

    oracle = ORACLE.solve_sheet_electrical(grid, conductivity, source_voltage_V)
    candidate = solve_sheet_electrical(grid, conductivity, source_voltage_V)

    _assert_normalized_array_equal(
        candidate.potential_V,
        oracle.potential_V,
        denominator_floor=max(1.0, source_voltage_V),
    )
    _assert_normalized_array_equal(
        candidate.cell_joule_power_W,
        oracle.cell_joule_power_W,
        denominator_floor=1.0e-30,
    )
    for name in ("source_current_A", "ground_current_A"):
        _assert_normalized_scalar_equal(
            getattr(candidate, name),
            getattr(oracle, name),
            denominator_floor=1.0e-12,
        )
    for name in ("joule_power_W", "terminal_device_power_W"):
        _assert_normalized_scalar_equal(
            getattr(candidate, name),
            getattr(oracle, name),
            denominator_floor=1.0e-30,
        )


def test_frozen_conductivity_factorization_uses_one_factor_and_two_direct_rhs_solves(
    electrical_context, monkeypatch: pytest.MonkeyPatch
) -> None:
    _config, grid, conductivity_fields = electrical_context
    real_splu = electrical_fvm.splu
    factorization_calls = 0
    direct_right_hand_sides: list[np.ndarray] = []

    class RecordingFactorization:
        def __init__(self, delegate) -> None:
            self.delegate = delegate

        def solve(self, rhs: np.ndarray) -> np.ndarray:
            direct_right_hand_sides.append(np.asarray(rhs, dtype=float).copy())
            return self.delegate.solve(rhs)

    def recording_splu(*args, **kwargs):
        nonlocal factorization_calls
        factorization_calls += 1
        return RecordingFactorization(real_splu(*args, **kwargs))

    monkeypatch.setattr(electrical_fvm, "splu", recording_splu)
    factorization = factor_sheet_electrical(
        grid,
        conductivity_fields["legal_critical_like"],
        topology=build_sheet_electrical_topology(grid),
    )
    unit = factorization.solve(1.0)
    actual = factorization.solve(15.8)

    assert factorization_calls == 1
    assert len(direct_right_hand_sides) == 2
    np.testing.assert_allclose(
        direct_right_hand_sides[1],
        15.8 * direct_right_hand_sides[0],
        rtol=0.0,
        atol=1.0e-30,
    )
    assert factorization.timings.factorization_calls == 1
    assert factorization.timings.linear_solve_calls == 2
    assert not np.shares_memory(unit.potential_V, actual.potential_V)


def test_fixed_topology_rejects_a_different_grid_context(electrical_context) -> None:
    config, grid, conductivity_fields = electrical_context
    topology = build_sheet_electrical_topology(grid)
    other_grid = build_geophase_grid(config, nx_override=20, ny_override=4)

    with pytest.raises(ValueError, match="cannot cross grid context"):
        factor_sheet_electrical(
            other_grid,
            np.full(other_grid.shape, conductivity_fields["equilibrium_like"][0, 0]),
            topology=topology,
        )


def test_stage_timings_and_callback_names_are_locked_and_nonnegative(
    electrical_context,
) -> None:
    _config, grid, conductivity_fields = electrical_context
    timings = SheetElectricalTimings()
    callback_rows: list[tuple[str, float]] = []
    factorization = factor_sheet_electrical(
        grid,
        conductivity_fields["high_conductive_like"],
        topology=build_sheet_electrical_topology(grid),
        timings=timings,
        timing_callback=lambda name, elapsed_s: callback_rows.append(
            (name, elapsed_s)
        ),
    )
    factorization.solve(1.0)
    factorization.solve(15.8)

    assert [name for name, _elapsed in callback_rows] == [
        "electrical_assembly_wall_s",
        "factorization_wall_s",
        "linear_solves_wall_s",
        "Joule_port_postprocess_wall_s",
        "linear_solves_wall_s",
        "Joule_port_postprocess_wall_s",
    ]
    assert all(np.isfinite(elapsed) and elapsed >= 0.0 for _, elapsed in callback_rows)
    assert timings.electrical_assembly_calls == 1
    assert timings.factorization_calls == 1
    assert timings.linear_solve_calls == 2
    assert timings.postprocess_calls == 2
    for name in (
        "electrical_assembly_wall_s",
        "factorization_wall_s",
        "linear_solves_wall_s",
        "Joule_port_postprocess_wall_s",
    ):
        value = getattr(timings, name)
        assert np.isfinite(value) and value >= 0.0


def test_public_convenience_api_is_unchanged_and_has_no_legacy_mode() -> None:
    signature = inspect.signature(solve_sheet_electrical)
    assert list(signature.parameters) == [
        "grid",
        "conductivity_S_m",
        "source_voltage_V",
        "ground_voltage_V",
    ]
    factor_signature = inspect.signature(factor_sheet_electrical)
    assert "legacy" not in factor_signature.parameters
    assert "backend" not in factor_signature.parameters

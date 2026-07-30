from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as implicit
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    PERFORMANCE_TIMING_SEMANTICS,
    S2PerformanceTimings,
    advance_s2_backward_euler,
    build_s2_solver_cache,
    initial_s2_state,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _small_source_corrected_context():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    return config, grid, fields, closure


def test_coupled_map_and_residual_use_one_factor_for_two_direct_RHS(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, grid, fields, closure = _small_source_corrected_context()
    real_factor = implicit.factor_sheet_electrical
    solve_counts: list[int] = []

    class RecordingFactor:
        def __init__(self, delegate) -> None:
            self._delegate = delegate
            self._index = len(solve_counts)
            solve_counts.append(0)

        def solve(self, *args, **kwargs):
            solve_counts[self._index] += 1
            return self._delegate.solve(*args, **kwargs)

    def recording_factor(*args, **kwargs):
        return RecordingFactor(real_factor(*args, **kwargs))

    monkeypatch.setattr(implicit, "factor_sheet_electrical", recording_factor)
    timings = S2PerformanceTimings()
    initial = initial_s2_state(grid, closure, fields, config)
    advance_s2_backward_euler(
        initial,
        input_voltage_V=12.5,
        dt_s=float(config["reference_solver"]["time_grid"]["base_max_step_s"]),
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
        performance_timings=timings,
    )

    assert solve_counts
    assert solve_counts.count(1) == 1  # final actual-voltage post-solve only
    assert solve_counts.count(2) >= 1
    assert set(solve_counts) == {1, 2}


def test_performance_timings_are_hierarchical_and_never_a_wall_time_sum() -> None:
    assert PERFORMANCE_TIMING_SEMANTICS == (
        "hierarchical_nonadditive_use_observed_sample_wall_time_for_forecast"
    )
    timings = S2PerformanceTimings()
    assert set(timings.as_dict()) == {
        "electrical_assembly_wall_s",
        "factorization_wall_s",
        "linear_solves_wall_s",
        "Joule_port_postprocess_wall_s",
        "Picard_predictor_wall_s",
        "Newton_Krylov_wall_s",
        "fallback_wall_s",
    }
    assert all(value == 0.0 for value in timings.as_dict().values())

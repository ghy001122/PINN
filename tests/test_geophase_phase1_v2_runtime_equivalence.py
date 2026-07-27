from __future__ import annotations

import inspect
from pathlib import Path
import json

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    assemble_sheet_thermal_matrix,
    build_s2_thermal_backward_euler_solver,
    scale_unit_sheet_electrical_solution,
    solve_s2_thermal_backward_euler,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    advance_s2_backward_euler,
    build_s2_solver_cache,
    initial_s2_state,
)
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    build_campaign_cost_forecast,
    deterministic_lpt_schedule,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
    / "execution_dag.json"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def runtime_context():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    return config, grid, fields, closure


def test_unit_voltage_scaling_is_not_enabled_by_default() -> None:
    signature = inspect.signature(advance_s2_backward_euler)
    assert signature.parameters["use_unit_voltage_scaling"].default is False


def _assert_balance_equal(left, right) -> None:
    assert left.name == right.name
    assert left.input_power_W == pytest.approx(right.input_power_W, rel=1.0e-12, abs=1.0e-24)
    assert left.accounted_power_W == pytest.approx(
        right.accounted_power_W, rel=1.0e-12, abs=1.0e-24
    )
    ledger_scale = max(
        abs(left.input_power_W),
        abs(right.input_power_W),
        abs(left.accounted_power_W),
        abs(right.accounted_power_W),
        1.0e-30,
    )
    assert abs(left.signed_residual_W - right.signed_residual_W) / ledger_scale <= 1.0e-12
    assert abs(left.relative_residual - right.relative_residual) <= 1.0e-12
    assert left.terms_W.keys() == right.terms_W.keys()
    for key in left.terms_W:
        assert left.terms_W[key] == pytest.approx(
            right.terms_W[key], rel=1.0e-12, abs=1.0e-24
        )


def test_frozen_context_unit_voltage_scaling_matches_direct_solve(
    runtime_context,
) -> None:
    _config, grid, _fields, closure = runtime_context
    temperature = np.full(grid.shape, 337.0, dtype=float)
    branch = np.full(grid.shape, 0.3, dtype=float)
    conductive = closure.equilibrium_state(temperature, branch)
    conductivity = closure.conductivity_S_m(temperature, conductive)
    voltage = 12.5

    unit = solve_sheet_electrical(grid, conductivity, 1.0)
    scaled = scale_unit_sheet_electrical_solution(unit, voltage)
    direct = solve_sheet_electrical(grid, conductivity, voltage)

    np.testing.assert_allclose(scaled.potential_V, direct.potential_V, rtol=1.0e-12, atol=1.0e-14)
    np.testing.assert_allclose(
        scaled.cell_joule_power_W,
        direct.cell_joule_power_W,
        rtol=1.0e-12,
        atol=1.0e-24,
    )
    for name in (
        "source_current_A",
        "ground_current_A",
        "joule_power_W",
        "terminal_device_power_W",
    ):
        assert getattr(scaled, name) == pytest.approx(
            getattr(direct, name), rel=1.0e-12, abs=1.0e-24
        )
    for solution in (scaled, direct):
        assert solution.relative_current_imbalance <= 1.0e-12
        assert solution.relative_power_imbalance <= 1.0e-12


def test_cached_thermal_factorization_matches_uncached_solve(runtime_context) -> None:
    config, grid, fields, _closure = runtime_context
    dt_s = float(config["reference_solver"]["time_grid"]["base_max_step_s"])
    x = np.broadcast_to(grid.x_centers_m[None, :], grid.shape)
    y = np.broadcast_to(grid.y_centers_m[:, None], grid.shape)
    old_temperature = fields.ambient_temperature_K + 2.0e6 * x + 1.0e6 * y
    joule = np.full(grid.shape, 2.0e-8 / (grid.nx * grid.ny), dtype=float)
    matrix = assemble_sheet_thermal_matrix(
        grid, fields.sheet_thermal_conductance_W_K
    )
    cached_solver = build_s2_thermal_backward_euler_solver(
        grid, fields, dt_s, lateral_matrix=matrix
    )

    uncached = solve_s2_thermal_backward_euler(
        grid,
        fields,
        old_temperature,
        joule,
        dt_s,
        lateral_matrix=matrix,
    )
    cached = solve_s2_thermal_backward_euler(
        grid,
        fields,
        old_temperature,
        joule,
        dt_s,
        lateral_matrix=matrix,
        linear_solver=cached_solver,
    )

    np.testing.assert_allclose(cached, uncached, rtol=1.0e-12, atol=1.0e-12)


def test_cached_optimized_coupled_step_matches_uncached_direct_step(
    runtime_context,
) -> None:
    config, grid, fields, closure = runtime_context
    initial = initial_s2_state(grid, closure, fields, config)
    dt_s = float(config["reference_solver"]["time_grid"]["base_max_step_s"])

    direct = advance_s2_backward_euler(
        initial,
        input_voltage_V=12.5,
        dt_s=dt_s,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        use_equivalent_optimizations=False,
    )
    cached = advance_s2_backward_euler(
        initial,
        input_voltage_V=12.5,
        dt_s=dt_s,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=build_s2_solver_cache(grid, fields),
        use_equivalent_optimizations=True,
    )

    np.testing.assert_allclose(
        cached.state.temperature_K,
        direct.state.temperature_K,
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        cached.state.conductive_state,
        direct.state.conductive_state,
        rtol=1.0e-12,
        atol=1.0e-14,
    )
    np.testing.assert_allclose(
        cached.state.branch_memory,
        direct.state.branch_memory,
        rtol=1.0e-12,
        atol=1.0e-14,
    )
    assert cached.state.device_voltage_V == pytest.approx(
        direct.state.device_voltage_V, rel=1.0e-12, abs=1.0e-14
    )
    np.testing.assert_allclose(
        cached.electrical.potential_V,
        direct.electrical.potential_V,
        rtol=1.0e-12,
        atol=1.0e-14,
    )
    np.testing.assert_allclose(
        cached.electrical.cell_joule_power_W,
        direct.electrical.cell_joule_power_W,
        rtol=1.0e-12,
        atol=1.0e-24,
    )
    for name in (
        "source_current_A",
        "ground_current_A",
        "joule_power_W",
        "terminal_device_power_W",
    ):
        assert getattr(cached.electrical, name) == pytest.approx(
            getattr(direct.electrical, name), rel=1.0e-12, abs=1.0e-24
        )
    for name in ("thermal", "circuit", "combined", "device_power"):
        _assert_balance_equal(
            getattr(cached.ledgers, name), getattr(direct.ledgers, name)
        )


def test_case_cache_rejects_cross_context_reuse(runtime_context) -> None:
    config, grid, fields, _closure = runtime_context
    cache = build_s2_solver_cache(grid, fields)
    other_grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    other_fields = build_s2_thermal_fields(other_grid, config)
    with pytest.raises(ValueError, match="cannot cross"):
        cache.validate_context(other_grid, other_fields)


def test_campaign_forecast_maps_all_sixty_units_and_uses_deterministic_lpt() -> None:
    dag = json.loads(DAG_PATH.read_text(encoding="utf-8"))
    samples: list[dict] = []
    for level in (1, 2, 4):
        for state_index, state_id in enumerate(
            ("equilibrium", "legal_critical", "high_conductive")
        ):
            samples.append(
                {
                    "sample_id": f"PRE-SYNTH-L{level}-{state_id}",
                    "sample_kind": "short_trajectory",
                    "spatial_level": level,
                    "state_id": state_id,
                    "status": "pass",
                    "accepted_steps": 128 + state_index,
                    "achieved_simulated_time_s": 6.4e-7,
                    "step_wall_time_p90_s": 1.0e-4 * level * (1 + state_index),
                    "step_wall_time_max_s": 2.0e-4 * level * (1 + state_index),
                    "predicted_full_streaming_bytes": 1_000_000 * level,
                    "predicted_full_streaming_io_s": 0.1 * level,
                    "peak_rss_bytes": 100_000_000 * level,
                }
            )
    environment = {
        "physical_core_count": 8,
        "available_ram_bytes_at_launch": 16_000_000_000,
        "disk_total_bytes": 1_000_000_000_000,
        "disk_free_bytes_at_launch": 500_000_000_000,
    }

    rows, summary = build_campaign_cost_forecast(
        execution_dag=dag,
        sample_rows=samples,
        environment=environment,
        floor_dt_s=2.5e-10,
        disk_free_fraction_min=0.20,
    )

    assert len(rows) == summary["unit_count"] == 60
    assert summary["selected_worker_count"] == 8
    assert summary["aggregate_worker_rss_fraction_of_launch_available_ram"] <= 0.70
    fine = next(
        row
        for row in rows
        if row["execution_unit_id"] == "TRJ-P1V2-REF-nominal_12V-S4T4"
    )
    assert fine["absolute_floor_accepted_steps"] == 320_000
    dual = next(row for row in rows if row["execution_group"] == "DUAL0")
    assert dual["safety_wall_clock_s"] > dual["unreserved_wall_clock_s"]

    first, first_makespan = deterministic_lpt_schedule(
        rows, 8, "safety_wall_clock_s"
    )
    second, second_makespan = deterministic_lpt_schedule(
        list(reversed(rows)), 8, "safety_wall_clock_s"
    )
    assert first == second
    assert first_makespan == second_makespan

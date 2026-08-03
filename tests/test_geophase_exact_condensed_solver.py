from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation.geophase_exact_block_condensation_stage_a import (
    evaluate_exact_condensation,
)
from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_exact_condensed import (
    DEFAULT_EXACT_CONDENSED_SETTINGS,
    ExactCondensedRootFailure,
    ExactCondensedSettings,
    reconstruct_exact_auxiliary_state,
    solve_exact_condensed_step,
)
from pinnpcm.solvers.geophase_exact_condensed_controller_v2 import (
    attempt_exact_condensed_embedded_interval,
    simulate_exact_condensed_protocol_v2,
)


CONFIG = ROOT / "configs/geophase_exact_condensed_s0_c01_c06_r1.yaml"
REPLAYS = (
    ROOT
    / "outputs/tables/geophase_controller_v3/qualification/"
    "CTRLV3-QUAL-20260801-V2/failures/CTRLV3-QUAL-QUIESCENT-9V-T1.json",
    ROOT
    / "outputs/tables/geophase_controller_v3/qualification/"
    "CTRLV3-QUAL-20260801-V4/failures/CTRLV3-QUAL-QUIESCENT-9V-T1.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _context(level: int = 1):
    scientific = resolved_s2_config()
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    return scientific, grid, fields, closure, cache


def test_exact_settings_and_frozen_inputs_match_versioned_contract() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    solver = config["solver"]
    gates = config["gates"]
    settings = DEFAULT_EXACT_CONDENSED_SETTINGS
    assert settings.maximum_newton_iterations == solver["maximum_newton_iterations"]
    assert settings.maximum_krylov_matvecs == solver["budgets_per_root"][
        "maximum_krylov_matvecs"
    ]
    assert settings.maximum_reduced_residual_evaluations == solver[
        "budgets_per_root"
    ]["maximum_reduced_residual_evaluations"]
    assert settings.maximum_line_search_backtracks == solver["budgets_per_root"][
        "maximum_line_search_backtracks"
    ]
    assert settings.lgmres_inner_m == solver["lgmres"]["inner_m"]
    assert settings.lgmres_outer_k == solver["lgmres"]["outer_k"]
    assert settings.lgmres_rtol == solver["lgmres"]["rtol"]
    assert settings.lgmres_atol == solver["lgmres"]["atol"]
    assert settings.auxiliary_residual_tolerance == gates[
        "auxiliary_scaled_residual_inf_max"
    ]
    for item in config["frozen_inputs"]:
        assert _sha256(ROOT / item["path"]) == item["sha256"]


def test_reconstruction_matches_frozen_stage_a_for_two_states_and_seven_steps() -> None:
    scientific, grid, fields, closure, cache = _context()
    eps_factor = 64.0 * np.finfo(float).eps
    for replay_path in REPLAYS:
        replay = json.loads(replay_path.read_text(encoding="utf-8"))["replay"]
        old_state = _state_from_replay(replay["previous_state"])
        voltage = float(replay["full_input_voltage_V"])
        for dt_ns in (10.0, 5.0, 2.5, 1.25, 0.625, 0.3125, 0.15625):
            dt_s = dt_ns * 1.0e-9
            frozen = evaluate_exact_condensation(
                candidate_temperature_K=old_state.temperature_K,
                old_state=old_state,
                input_voltage_V=voltage,
                dt_s=dt_s,
                grid=grid,
                closure=closure,
                fields=fields,
                scientific_config=scientific,
                cache=cache,
            )
            exact = reconstruct_exact_auxiliary_state(
                old_state.temperature_K,
                old_state,
                dt_s,
                voltage,
                grid=grid,
                closure=closure,
                fields=fields,
                config=scientific,
                cache=cache,
            )
            temperature_norm = float(
                np.max(np.abs(exact.temperature_scaled_residual))
            )
            tolerance = eps_factor * max(1.0, abs(frozen["temperature"]))
            assert abs(temperature_norm - frozen["temperature"]) <= tolerance
            assert exact.auxiliary_scaled_residual_inf <= 1.0e-12
            assert np.isfinite(exact.raw_thermal_residual_W_per_cell).all()


@pytest.mark.parametrize("level", (1, 2, 4))
def test_full_state_pack_unpack_contract_holds_on_nested_grids(level: int) -> None:
    scientific, grid, fields, closure, _ = _context(level)
    state = production.initial_s2_state(grid, closure, fields, scientific)
    packed = production._pack(
        state.temperature_K,
        state.conductive_state,
        state.branch_memory,
        state.device_voltage_V,
    )
    temperature, conductive, branch, voltage = production._unpack(packed, grid)
    assert np.array_equal(temperature, state.temperature_K)
    assert np.array_equal(conductive, state.conductive_state)
    assert np.array_equal(branch, state.branch_memory)
    assert voltage == state.device_voltage_V


def test_zero_drive_uses_exact_path_and_preserves_full_integrity() -> None:
    scientific, grid, fields, closure, cache = _context()
    initial = production.initial_s2_state(grid, closure, fields, scientific)
    outcome = solve_exact_condensed_step(
        initial,
        input_voltage_V=0.0,
        dt_s=10.0e-9,
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        cache=cache,
    )
    assert outcome.step.nonlinear.method == (
        "exact_condensed_analytic_zero_drive_equilibrium"
    )
    assert outcome.step.nonlinear.scaled_residual_inf == 0.0
    assert outcome.step.nonlinear.scaled_update_inf == 0.0
    assert outcome.telemetry.last_newton_update_inf == 0.0
    assert np.array_equal(outcome.step.state.temperature_K, initial.temperature_K)
    assert outcome.step.ledgers.thermal.relative_residual == 0.0
    assert outcome.step.ledgers.combined.relative_residual == 0.0


def test_exact_controller_preserves_full_half_commit_landing_and_growth() -> None:
    scientific, grid, fields, closure, cache = _context()
    initial = production.initial_s2_state(grid, closure, fields, scientific)
    protocol = scientific["formal_protocols"]["protocols"]["zero_drive"]
    attempt = attempt_exact_condensed_embedded_interval(
        initial,
        protocol=protocol,
        protocol_id="zero_drive",
        outer_interval_s=10.0e-9,
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        cache=cache,
    )
    assert attempt.step is not None
    assert attempt.diagnostics.accepted
    assert attempt.diagnostics.coupled_solve_count == 3
    assert len(attempt.root_telemetry) == 3
    assert attempt.step.state.time_s == 10.0e-9
    assert attempt.step.state.time_s == attempt.second_half_candidate.state.time_s
    assert attempt.step.accepted_first_half.state.time_s == 5.0e-9
    assert not attempt.diagnostics.any_fallback

    result = simulate_exact_condensed_protocol_v2(
        initial,
        protocol=protocol,
        protocol_id="zero_drive",
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        final_time_s=20.0e-9,
        forced_times_s=(5.0e-9, 15.0e-9, 20.0e-9),
        cache=cache,
    )
    assert result.completed
    assert result.achieved_final_time_s == pytest.approx(20.0e-9, abs=1.0e-21)
    assert tuple(step.state.time_s for step in result.steps) == pytest.approx(
        (5.0e-9, 10.0e-9, 15.0e-9, 20.0e-9), abs=1.0e-21
    )
    assert result.diagnostics.growth_events >= 1
    assert result.diagnostics.fallback_steps == 0
    assert len(result.root_telemetry) == 3 * result.diagnostics.accepted_steps


def test_krylov_and_residual_budgets_fail_closed_before_overrun() -> None:
    scientific, grid, fields, closure, cache = _context()
    replay = json.loads(REPLAYS[0].read_text(encoding="utf-8"))["replay"]
    old_state = _state_from_replay(replay["previous_state"])
    settings = ExactCondensedSettings(
        maximum_krylov_matvecs=1,
        maximum_reduced_residual_evaluations=2,
    )
    with pytest.raises(ExactCondensedRootFailure) as caught:
        solve_exact_condensed_step(
            old_state,
            input_voltage_V=float(replay["full_input_voltage_V"]),
            dt_s=10.0e-9,
            grid=grid,
            closure=closure,
            fields=fields,
            config=scientific,
            cache=cache,
            settings=settings,
        )
    assert caught.value.code in {
        "KRYLOV_MATVEC_BUDGET_EXHAUSTED",
        "REDUCED_RESIDUAL_BUDGET_EXHAUSTED",
    }
    assert caught.value.telemetry.krylov_matvecs <= 1
    assert caught.value.telemetry.reduced_residual_evaluations <= 2

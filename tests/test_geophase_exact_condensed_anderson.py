from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_exact_condensed as exact_v1
from pinnpcm.solvers import geophase_exact_condensed_anderson as anderson
from pinnpcm.solvers import geophase_exact_condensed_controller_v2 as exact_controller
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_exact_condensed_anderson_controller_v2 import (
    attempt_exact_condensed_anderson_embedded_interval,
)


CONFIG = ROOT / "configs/geophase_controller_relevance_final_rescue.yaml"
R0_SUMMARY = (
    ROOT
    / "outputs/tables/geophase_controller_relevance_final_rescue/"
    "R0-CONTROLLER-RELEVANCE-20260804-V2/r0_summary.json"
)


def _context():
    scientific = resolved_s2_config()
    grid = build_geophase_grid(scientific, spatial_level=1)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    return scientific, grid, fields, closure, cache


def _fake_evaluation(
    temperature: np.ndarray,
    phi: np.ndarray,
    *,
    certified: bool = False,
):
    defect = np.asarray(temperature - phi, dtype=float)
    gate_value = 0.0 if certified else 1.0
    return SimpleNamespace(
        temperature_K=np.asarray(temperature, dtype=float),
        phi_temperature_K=np.asarray(phi, dtype=float),
        unscaled_defect_K=defect,
        unscaled_defect_inf_K=float(np.max(np.abs(defect))),
        reduced_residual_inf=gate_value,
        full_scaled_residual_inf=gate_value,
        full_fixed_point_defect_inf=gate_value,
        auxiliary_scaled_residual_inf=gate_value,
    )


def _validate_nonnegative_finite(values: np.ndarray) -> None:
    if not np.isfinite(values).all() or np.any(values < 0.0):
        raise ValueError("range/nonfinite")


def test_anderson_settings_match_frozen_r2_contract() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    frozen = config["r2"]["map"]
    settings = anderson.DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    assert settings.depth == frozen["anderson_depth"]
    assert settings.relaxation == frozen["relaxation"]
    assert settings.maximum_map_evaluations == frozen[
        "maximum_map_evaluations_per_root"
    ]
    assert settings.coefficient_regularization == frozen[
        "coefficient_regularization"
    ]
    assert settings.svd_rcond == frozen["svd_rcond"]
    assert settings.residual_scale_floor_K == frozen["residual_scale_floor_K"]
    assert settings.sufficient_decrease_c1 == frozen["sufficient_decrease_c1"]


def test_linear_contractive_map_accepts_anderson_candidate() -> None:
    settings = anderson.DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    counters = anderson._Counters()

    def evaluate(temperature: np.ndarray):
        phi = 0.2 * temperature
        certified = bool(np.max(np.abs(temperature - phi)) <= 1.0e-9)
        return _fake_evaluation(temperature, phi, certified=certified)

    result = anderson._run_safeguarded_iterations(
        np.asarray([1.0]),
        evaluate=evaluate,
        validate_temperature=lambda _: None,
        settings=settings,
        counters=counters,
    )
    assert result.reduced_residual_inf == 0.0
    assert counters.anderson_attempts >= 1
    assert counters.anderson_accepted >= 1
    assert counters.anderson_rejected == 0


def test_rejected_anderson_uses_picard_and_restarts_history() -> None:
    settings = anderson.DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    counters = anderson._Counters()

    def evaluate(temperature: np.ndarray):
        value = float(np.asarray(temperature).reshape(-1)[0])
        phi_value = 10.0 if value <= 0.1 else 0.0
        certified = bool(np.isclose(value, 0.25, atol=1.0e-12))
        return _fake_evaluation(
            np.asarray([value]),
            np.asarray([phi_value]),
            certified=certified,
        )

    result = anderson._run_safeguarded_iterations(
        np.asarray([1.0]),
        evaluate=evaluate,
        validate_temperature=lambda _: None,
        settings=settings,
        counters=counters,
    )
    assert result.reduced_residual_inf == 0.0
    assert counters.anderson_rejected == 1
    assert counters.safeguarded_picard_steps == 2
    assert counters.history_restarts == 1


def test_nonfinite_or_range_illegal_candidate_fails_closed() -> None:
    settings = anderson.DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    counters = anderson._Counters()

    def evaluate(temperature: np.ndarray):
        return _fake_evaluation(temperature, np.full_like(temperature, np.nan))

    with pytest.raises((ValueError, FloatingPointError)):
        anderson._run_safeguarded_iterations(
            np.asarray([1.0]),
            evaluate=evaluate,
            validate_temperature=_validate_nonnegative_finite,
            settings=settings,
            counters=counters,
        )


def test_real_floor_context_passes_full_and_auxiliary_certification() -> None:
    scientific, grid, fields, closure, cache = _context()
    summary = json.loads(R0_SUMMARY.read_text(encoding="utf-8"))
    context = next(
        case["r1_terminal_context"]
        for case in summary["cases"]
        if case["r1_eligible"]
    )
    outcome = anderson.solve_exact_condensed_safeguarded_anderson_step(
        _state_from_replay(context["old_state"]),
        input_voltage_V=float(context["input_voltage_V"]),
        dt_s=float(context["dt_s"]),
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        cache=cache,
    )
    telemetry = outcome.telemetry
    assert telemetry.status == "PASS"
    assert telemetry.solver_id == anderson.SOLVER_ID
    assert telemetry.map_evaluations <= 80
    assert telemetry.reduced_residual_inf <= 1.0e-8
    assert telemetry.full_scaled_residual_inf <= 1.0e-8
    assert telemetry.full_fixed_point_defect_inf <= 1.0e-8
    assert telemetry.auxiliary_scaled_residual_inf <= 1.0e-12


def test_controller_binding_preserves_full_half_order_commit_and_restores() -> None:
    scientific, grid, fields, closure, cache = _context()
    initial = production.initial_s2_state(grid, closure, fields, scientific)
    protocol = scientific["formal_protocols"]["protocols"]["zero_drive"]
    historical = exact_controller.solve_exact_condensed_step
    attempt = attempt_exact_condensed_anderson_embedded_interval(
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
    assert exact_controller.solve_exact_condensed_step is historical
    assert historical is exact_v1.solve_exact_condensed_step
    assert attempt.step is not None
    assert len(attempt.root_telemetry) == 3
    assert all(item.solver_id == anderson.SOLVER_ID for item in attempt.root_telemetry)
    assert attempt.first_half_candidate.state.time_s == pytest.approx(5.0e-9)
    assert attempt.second_half_candidate.state.time_s == pytest.approx(10.0e-9)
    assert attempt.step.accepted_first_half.state.time_s == pytest.approx(5.0e-9)
    assert attempt.step.state.time_s == attempt.second_half_candidate.state.time_s

    with pytest.raises(ValueError):
        attempt_exact_condensed_anderson_embedded_interval(
            initial,
            protocol=protocol,
            protocol_id="zero_drive",
            outer_interval_s=-1.0,
            grid=grid,
            closure=closure,
            fields=fields,
            config=scientific,
            cache=cache,
        )
    assert exact_controller.solve_exact_condensed_step is historical

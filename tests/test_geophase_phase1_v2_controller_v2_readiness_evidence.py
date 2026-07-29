from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from pinnpcm.solvers import geophase_phase1_v2_streaming as streaming
from pinnpcm.solvers.geophase_phase1_v2_implicit import S2State
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    build_campaign_cost_forecast,
)
from scripts import run_geophase_phase1_v2_embedded_controller_readiness as readiness


ROOT = Path(__file__).resolve().parents[1]
DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
    / "execution_dag.json"
)
ACTUAL_READINESS_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "controller_v2_readiness"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _dag() -> dict:
    return json.loads(DAG_PATH.read_text(encoding="utf-8"))


def _environment() -> dict:
    return {
        "physical_core_count": 8,
        "available_ram_bytes_at_launch": 16_000_000_000,
        "disk_total_bytes": 1_000_000_000_000,
        "disk_free_bytes_at_launch": 500_000_000_000,
    }


def _samples() -> list[dict]:
    rows: list[dict] = []
    for level in (1, 2, 4):
        for state_index, state_id in enumerate(
            ("equilibrium", "legal_critical", "high_conductive")
        ):
            accepted = 128 + state_index
            rows.append(
                {
                    "sample_id": f"PRE-CTRL-SYNTH-L{level}-{state_id}",
                    "sample_kind": "short_trajectory",
                    "spatial_level": level,
                    "state_id": state_id,
                    "status": "pass",
                    "accepted_steps": accepted,
                    "coupled_solve_count": 3 * accepted + 3 * state_index,
                    "achieved_simulated_time_s": 6.4e-7,
                    "step_wall_time_p90_s": 1.0e-4
                    * level
                    * (1 + state_index),
                    "step_wall_time_max_s": 2.0e-4
                    * level
                    * (1 + state_index),
                    "predicted_full_streaming_bytes": 1_000_000 * level,
                    "predicted_full_streaming_io_s": 0.1 * level,
                    "peak_rss_bytes": 100_000_000 * level,
                }
            )
    return rows


def _forecast(samples: list[dict], **kwargs):
    return build_campaign_cost_forecast(
        execution_dag=_dag(),
        sample_rows=samples,
        environment=_environment(),
        disk_free_fraction_min=0.20,
        **kwargs,
    )


@pytest.mark.parametrize("level", (1, 2, 4))
@pytest.mark.parametrize(
    "state_id", ("equilibrium", "legal_critical", "high_conductive")
)
def test_controller_v2_forecast_requires_each_state_on_each_grid(
    level: int, state_id: str
) -> None:
    incomplete = [
        row
        for row in _samples()
        if not (row["spatial_level"] == level and row["state_id"] == state_id)
    ]

    with pytest.raises(
        ValueError,
        match=rf"missing passing trajectory telemetry for L{level} states:.*{state_id}",
    ):
        _forecast(
            incomplete,
            outer_interval_floor_s=9.765625e-12,
            coupled_solves_per_clean_outer_interval=3,
        )


def test_controller_v2_outer_floor_and_coupled_solve_cost_are_explicit() -> None:
    rows, summary = _forecast(
        _samples(),
        outer_interval_floor_s=9.765625e-12,
        coupled_solves_per_clean_outer_interval=3,
    )

    assert len(rows) == summary["unit_count"] == 60
    assert summary["outer_interval_floor_s"] == pytest.approx(9.765625e-12)
    assert summary["required_state_ids_per_grid"] == [
        "equilibrium",
        "legal_critical",
        "high_conductive",
    ]
    semantics = summary["coupled_solve_cost_semantics"]
    assert semantics["clean_coupled_solves_per_outer_interval"] == 3
    assert semantics["measured_interval_wall_time_includes_all_coupled_solves"] is True
    assert semantics["wall_time_multiplier_for_embedded_solve_count"] == 1.0

    fine = next(
        row
        for row in rows
        if row["execution_unit_id"] == "TRJ-P1V2-REF-nominal_12V-S4T4"
    )
    assert fine["absolute_floor_accepted_steps"] == 8_192_000
    assert fine["clean_coupled_solves_per_outer_interval"] == 3
    assert fine["unreserved_coupled_solves"] >= 3 * fine["unreserved_accepted_steps"]
    assert fine["safety_coupled_solves"] >= 3 * fine["safety_accepted_steps"]


def test_embedded_solve_count_is_not_applied_again_to_measured_wall_time() -> None:
    samples = _samples()
    rows_one, summary_one = _forecast(
        samples,
        outer_interval_floor_s=9.765625e-12,
        coupled_solves_per_clean_outer_interval=1,
    )
    rows_three, summary_three = _forecast(
        samples,
        outer_interval_floor_s=9.765625e-12,
        coupled_solves_per_clean_outer_interval=3,
    )

    assert summary_one["unreserved_lpt_makespan_s"] == pytest.approx(
        summary_three["unreserved_lpt_makespan_s"]
    )
    assert summary_one["safety_lpt_makespan_s"] == pytest.approx(
        summary_three["safety_lpt_makespan_s"]
    )
    by_id_one = {row["execution_unit_id"]: row for row in rows_one}
    for row in rows_three:
        comparison = by_id_one[row["execution_unit_id"]]
        assert row["unreserved_wall_clock_s"] == pytest.approx(
            comparison["unreserved_wall_clock_s"]
        )
        assert math.isfinite(row["unreserved_wall_clock_s"])


def test_valid_error_rejection_contributes_to_observed_step_max() -> None:
    samples = _samples()
    samples.append(
        {
            "sample_id": "PRE-CTRL-STEP-L1-legal_critical-base",
            "sample_kind": "single_interval",
            "spatial_level": 1,
            "state_id": "legal_critical",
            "status": "valid_rejection",
            "step_wall_time_max_s": 9.0,
        }
    )
    rows, _summary = _forecast(
        samples,
        outer_interval_floor_s=9.765625e-12,
        coupled_solves_per_clean_outer_interval=3,
    )

    assert any(
        row["spatial_level"] == 1 and row["unreserved_wall_clock_s"] >= 9.0
        for row in rows
    )


def test_historical_floor_keyword_remains_supported() -> None:
    rows, summary = _forecast(_samples(), floor_dt_s=2.5e-10)

    assert len(rows) == 60
    assert summary["outer_interval_floor_s"] == pytest.approx(2.5e-10)


def test_conflicting_floor_keywords_fail_closed() -> None:
    with pytest.raises(ValueError, match="conflicting floor"):
        _forecast(
            _samples(),
            floor_dt_s=2.5e-10,
            outer_interval_floor_s=9.765625e-12,
        )


def _synthetic_streaming_config() -> dict:
    return {
        "formal_protocols": {
            "protocols": {
                "pulse_12p5V": {
                    "kind": "rectangular_voltage_pulse",
                    "baseline_voltage_V": 0.0,
                    "pulse_voltage_V": 12.5,
                    "pulse_start_s": 2.0e-9,
                    "pulse_stop_s": 4.0e-9,
                }
            }
        },
        "reference_solver": {
            "fixed_physical_comparison_time_grid": {
                "start_s": 0.0,
                "stop_s": 2.0e-5,
                "points": 4001,
                "interval_s": 5.0e-9,
            },
            "active_time_controller": {
                "controller_id": "embedded_time_consistency_v2_only",
                "voltage_scale": {
                    "protocol_V_scale_V": {"pulse_12p5V": 12.5}
                },
            },
        },
        "metric_contract": {
            "event_definition": {
                "threshold": 0.5,
                "minimum_separation_s": 1.0e-9,
            }
        },
    }


def _synthetic_embedded_step(time_s: float, conductive_state: float):
    balance = SimpleNamespace(
        name="synthetic",
        input_power_W=1.0,
        accounted_power_W=1.0,
        signed_residual_W=0.0,
        relative_residual=0.0,
        terms_W={"term_W": 1.0},
    )
    nonlinear = SimpleNamespace(
        method="embedded[synthetic]",
        iterations=3,
        scaled_residual_inf=1.0e-12,
        scaled_update_inf=2.0e-12,
        converged=True,
        krylov_matvecs=4,
        armijo_backtracks=1,
        predictor_picard_iterations=0,
        fallback_picard_iterations=0,
    )
    path = SimpleNamespace(
        finite=True,
        nonlinear_pass=True,
        ledger_pass=True,
        lateral_pass=True,
        overall_pass=True,
        ledger_relative_residuals={
            "thermal": 0.0,
            "circuit": 0.0,
            "combined": 0.0,
            "device_power": 0.0,
        },
        lateral_relative_mismatch=0.0,
        lateral_roundoff_ratio=0.0,
        error_class=None,
        error_message=None,
    )
    aggregate = SimpleNamespace(
        finite=True,
        ledger_pass=True,
        overall_pass=True,
        ledger_relative_residuals={
            "thermal": 0.0,
            "circuit": 0.0,
            "combined": 0.0,
            "device_power": 0.0,
        },
        error_class=None,
        error_message=None,
    )

    def candidate(candidate_time_s: float, candidate_s: float):
        return SimpleNamespace(
            state=S2State(
                time_s=candidate_time_s,
                temperature_K=np.full((1, 1), 336.4),
                conductive_state=np.full((1, 1), candidate_s),
                branch_memory=np.full((1, 1), 0.9),
                device_voltage_V=6.25,
            ),
            electrical=SimpleNamespace(
                potential_V=np.full((1, 1), 6.25),
                cell_joule_power_W=np.full((1, 1), 0.5),
                source_current_A=0.1,
                ground_current_A=-0.1,
                joule_power_W=0.5,
                terminal_device_power_W=0.625,
                relative_current_imbalance=0.0,
                relative_power_imbalance=0.0,
            ),
            ledgers=SimpleNamespace(
                storage=SimpleNamespace(
                    explicit_plane_storage_rate_W=0.0,
                    closure_storage_rate_W=0.0,
                    effective_storage_rate_W=0.0,
                    vertical_sink_power_W=0.0,
                    lateral_boundary_outflow_W=0.0,
                ),
                thermal=balance,
                circuit=balance,
                combined=balance,
                device_power=balance,
            ),
            lateral_flux=SimpleNamespace(
                net_cell_outflow_W=np.zeros((1, 1)),
                x_face_flux_W=np.zeros((1, 0)),
                y_face_flux_W=np.zeros((0, 1)),
                boundary_face_flux_W=np.zeros(4),
                boundary_outflow_W=0.0,
                internal_pair_cancellation_W=0.0,
                matrix_face_relative_mismatch=0.0,
                matrix_face_roundoff_ratio=0.0,
                face_to_cell_global_residual_W=0.0,
            ),
            nonlinear=nonlinear,
        )

    first_half = candidate(0.5 * time_s, 0.5 * conductive_state)
    accepted = candidate(time_s, conductive_state)
    accepted.controller = SimpleNamespace(
        embedded_error=SimpleNamespace(
            e_T=1.0e-4,
            e_s=2.0e-4,
            e_b=3.0e-4,
            e_V=4.0e-4,
            e_max=4.0e-4,
            voltage_scale_V=12.5,
        ),
        voltage_scale_V=12.5,
        outer_interval_s=time_s,
        half_interval_s=0.5 * time_s,
        full_input_voltage_V=12.5,
        first_half_input_voltage_V=12.5,
        second_half_input_voltage_V=12.5,
        legacy_conductive_increment=0.25,
        legacy_branch_increment=0.10,
        rejection_index=1,
        below_floor_remainder=False,
        at_outer_floor=False,
        accepted=True,
        coupled_solve_count=3,
        any_fallback=False,
        full_step=path,
        first_half_step=path,
        second_half_step=path,
        aggregate=aggregate,
        full_nonlinear=nonlinear,
        first_half_nonlinear=nonlinear,
        second_half_nonlinear=nonlinear,
    )
    accepted.accepted_first_half = first_half
    return accepted


def test_v2_streaming_retains_history_and_records_only_accepted_fine_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    def interval_step(
        start_s: float, stop_s: float, conductive_state: float, input_voltage_V: float
    ):
        step = _synthetic_embedded_step(stop_s, conductive_state)
        midpoint_s = 0.5 * (start_s + stop_s)
        for candidate, time_s in (
            (step.accepted_first_half, midpoint_s),
            (step, stop_s),
        ):
            state = candidate.state
            candidate.state = S2State(
                time_s=time_s,
                temperature_K=state.temperature_K,
                conductive_state=state.conductive_state,
                branch_memory=state.branch_memory,
                device_voltage_V=state.device_voltage_V,
            )
        step.controller.outer_interval_s = stop_s - start_s
        step.controller.half_interval_s = 0.5 * (stop_s - start_s)
        step.controller.full_input_voltage_V = input_voltage_V
        step.controller.first_half_input_voltage_V = input_voltage_V
        step.controller.second_half_input_voltage_V = input_voltage_V
        return step

    landing_start = interval_step(0.0, 2.0e-9, 0.0, 0.0)
    landing_stop = interval_step(2.0e-9, 4.0e-9, 0.0, 12.5)
    accepted_step = interval_step(4.0e-9, 5.0e-9, 0.25, 0.0)
    accepted_steps = (landing_start, landing_stop, accepted_step)

    def fake_simulate(initial_state, **kwargs):
        calls.append(kwargs)
        # A rejected estimator/fine bundle may contribute cost telemetry but
        # must never enter scalar/event output.
        previous = initial_state
        for index, (step, input_voltage_V) in enumerate(
            zip(accepted_steps, (0.0, 12.5, 0.0), strict=True)
        ):
            if index == 2:
                kwargs["attempted_candidate_callback"](
                    SimpleNamespace(
                        diagnostics=SimpleNamespace(coupled_solve_count=2),
                        step=None,
                        second_half_candidate=_synthetic_embedded_step(5.0e-9, 0.75),
                    )
                )
                kwargs["attempted_candidate_callback"](
                    SimpleNamespace(diagnostics=SimpleNamespace(coupled_solve_count=3))
                )
            kwargs["accepted_step_callback"](
                previous,
                step,
                float(step.controller.outer_interval_s),
                input_voltage_V,
                0.01,
            )
            previous = step.state
        return SimpleNamespace(
            steps=accepted_steps if kwargs["retain_full_history"] else (),
            diagnostics=SimpleNamespace(accepted_steps=3),
            requested_final_time_s=5.0e-9,
            achieved_final_time_s=5.0e-9,
            completed=True,
            stop_reason="requested_final_time_reached",
        )

    monkeypatch.setattr(streaming, "simulate_s2_protocol_v2", fake_simulate)
    initial = S2State(
        time_s=0.0,
        temperature_K=np.full((1, 1), 336.4),
        conductive_state=np.zeros((1, 1)),
        branch_memory=np.ones((1, 1)),
        device_voltage_V=0.0,
    )
    protocol = {
        "kind": "rectangular_voltage_pulse",
        "baseline_voltage_V": 0.0,
        "pulse_voltage_V": 12.5,
        "pulse_start_s": 2.0e-9,
        "pulse_stop_s": 4.0e-9,
    }
    grid = SimpleNamespace(
        shape=(1, 1),
        cell_area_m2=1.0,
        area_m2=1.0,
        x_centers_m=np.asarray([0.5]),
        y_centers_m=np.asarray([0.5]),
    )
    closure = SimpleNamespace(
        branch_activations=lambda new, old, _dt: (
            np.maximum(np.asarray(new) - np.asarray(old), 0.0),
            np.maximum(np.asarray(old) - np.asarray(new), 0.0),
        )
    )
    result = streaming.run_s2_streaming_protocol_v2(
        "PRE-CTRL-SYNTH-STREAM",
        initial,
        protocol=protocol,
        protocol_id="pulse_12p5V",
        grid=grid,
        closure=closure,
        fields=object(),
        config=_synthetic_streaming_config(),
        final_time_s=5.0e-9,
        retain_full_history=True,
        cache=object(),
    )

    assert len(calls) == 1
    assert calls[0]["retain_full_history"] is True
    np.testing.assert_allclose(
        calls[0]["forced_times_s"],
        np.asarray([0.0, 2.0e-9, 4.0e-9, 5.0e-9]),
        rtol=0.0,
        atol=1.0e-18,
    )
    assert result.protocol_result.steps == accepted_steps
    assert result.final_state is accepted_step.state
    assert len(result.scalar_records) == 2
    assert result.event_records == ()
    row = result.scalar_records[-1]
    assert row["mean_conductive_state"] == pytest.approx(0.25)
    assert row["time_controller"] == "embedded_time_consistency_v2_only"
    assert row["outer_interval_s"] == pytest.approx(1.0e-9)
    assert row["outer_rejections"] == 1
    assert row["coupled_solve_count"] == 5
    assert row["accepted_bundle_coupled_solve_count"] == 3
    assert [row[name] for name in ("e_T", "e_s", "e_b", "e_V", "e_max")] == [
        1.0e-4,
        2.0e-4,
        3.0e-4,
        4.0e-4,
        4.0e-4,
    ]
    assert row["legacy_max_absolute_delta_s"] == pytest.approx(0.25)
    assert row["legacy_max_absolute_delta_b"] == pytest.approx(0.10)
    assert result.reversal_records == ()

    parity = readiness._history_streaming_parity(
        initial, result, grid, _synthetic_streaming_config(), "pulse_12p5V"
    )
    assert parity["pass"] is True
    assert readiness._history_streaming_event_parity(
        initial, result, _synthetic_streaming_config(), grid
    )["pass"] is True
    assert readiness._history_streaming_reversal_parity(
        initial, result, closure, grid
    )["pass"] is True

    original = row["thermal_input_power_W"]
    row["thermal_input_power_W"] = original + 1.0
    assert readiness._history_streaming_parity(
        initial, result, grid, _synthetic_streaming_config(), "pulse_12p5V"
    )["pass"] is False
    row["thermal_input_power_W"] = original

    missing_scalar = SimpleNamespace(
        **{**result.__dict__, "scalar_records": result.scalar_records[:-1]}
    )
    assert readiness._history_streaming_parity(
        initial,
        missing_scalar,
        grid,
        _synthetic_streaming_config(),
        "pulse_12p5V",
    )["worst_component"] == "fixed_scalar_record_count"

    missing_snapshot = SimpleNamespace(
        **{**result.__dict__, "field_snapshots": result.field_snapshots[:-1]}
    )
    assert readiness._history_streaming_parity(
        initial,
        missing_snapshot,
        grid,
        _synthetic_streaming_config(),
        "pulse_12p5V",
    )["pass"] is False

    row["voltage_scale_V"] = 9.0
    assert readiness._history_streaming_parity(
        initial, result, grid, _synthetic_streaming_config(), "pulse_12p5V"
    )["pass"] is False
    row["voltage_scale_V"] = 12.5

    initial_row = result.scalar_records[0]
    initial_row["case_id"] = "PRE-CTRL-TAMPERED"
    assert readiness._history_streaming_parity(
        initial, result, grid, _synthetic_streaming_config(), "pulse_12p5V"
    )["pass"] is False
    initial_row["case_id"] = result.case_id

    first_snapshot = result.field_snapshots[0]
    object.__setattr__(first_snapshot, "snapshot_kind", "tampered")
    assert readiness._history_streaming_parity(
        initial, result, grid, _synthetic_streaming_config(), "pulse_12p5V"
    )["pass"] is False
    object.__setattr__(first_snapshot, "snapshot_kind", "fixed")


def test_history_integrity_uses_all_embedded_paths_and_existing_gates() -> None:
    step = _synthetic_embedded_step(5.0e-9, 0.25)
    config = {
        "gates": {
            "thermal_ledger_relative_residual_max": 1.0e-2,
            "circuit_ledger_relative_residual_max": 1.0e-2,
            "combined_ledger_relative_residual_max": 1.0e-2,
            "device_power_identity_relative_residual_max": 1.0e-8,
        }
    }

    assert readiness._embedded_step_integrity(step, config) is True
    step.controller.first_half_step.overall_pass = False
    assert readiness._embedded_step_integrity(step, config) is False


def test_fixed_grid_event_parity_checks_endpoints_and_nonlinear_fields() -> None:
    grid = SimpleNamespace(shape=(1, 1), cell_area_m2=1.0, area_m2=1.0)
    initial = S2State(
        time_s=0.0,
        temperature_K=np.full((1, 1), 336.4),
        conductive_state=np.full((1, 1), 0.25),
        branch_memory=np.ones((1, 1)),
        device_voltage_V=0.0,
    )
    step = _synthetic_embedded_step(5.0e-9, 0.75)
    nonlinear = step.nonlinear
    event = {
        "case_id": "PRE-CTRL-EVENT-PARITY",
        "event_index": 1,
        "direction": "upward",
        "crossing_time_s": 2.5e-9,
        "before_sample_time_s": 0.0,
        "after_sample_time_s": 5.0e-9,
        "before_signal": 0.25,
        "after_signal": 0.75,
        "nonlinear_method": nonlinear.method,
        "nonlinear_iterations": nonlinear.iterations,
        "krylov_matvecs": nonlinear.krylov_matvecs,
        "armijo_backtracks": nonlinear.armijo_backtracks,
        "predictor_picard_iterations": nonlinear.predictor_picard_iterations,
        "fallback_picard_iterations": nonlinear.fallback_picard_iterations,
        "scaled_residual_inf": nonlinear.scaled_residual_inf,
        "scaled_update_inf": nonlinear.scaled_update_inf,
        "nonlinear_converged": nonlinear.converged,
    }
    result = SimpleNamespace(
        case_id="PRE-CTRL-EVENT-PARITY",
        protocol_result=SimpleNamespace(steps=(step,)),
        scalar_records=({}, {"time_s": 5.0e-9}),
        event_records=(event,),
    )

    parity = readiness._history_streaming_event_parity(
        initial, result, _synthetic_streaming_config(), grid
    )
    assert parity["pass"] is True
    event["after_signal"] = 0.70
    assert readiness._history_streaming_event_parity(
        initial, result, _synthetic_streaming_config(), grid
    )["pass"] is False


def test_reversal_parity_checks_both_directional_mask_hashes() -> None:
    grid = SimpleNamespace(
        shape=(1, 1),
        cell_area_m2=1.0,
        area_m2=1.0,
        x_centers_m=np.asarray([0.5]),
        y_centers_m=np.asarray([0.5]),
    )
    closure = SimpleNamespace(
        branch_activations=lambda new, old, _dt: (
            np.maximum(np.asarray(new) - np.asarray(old), 0.0),
            np.maximum(np.asarray(old) - np.asarray(new), 0.0),
        )
    )
    initial = S2State(
        time_s=0.0,
        temperature_K=np.full((1, 1), 336.0),
        conductive_state=np.full((1, 1), 0.4),
        branch_memory=np.ones((1, 1)),
        device_voltage_V=0.0,
    )

    def set_state(candidate, time_s: float, temperature_K: float) -> None:
        candidate.state = S2State(
            time_s=time_s,
            temperature_K=np.full((1, 1), temperature_K),
            conductive_state=np.full((1, 1), 0.4),
            branch_memory=np.ones((1, 1)),
            device_voltage_V=6.25,
        )

    first = _synthetic_embedded_step(5.0e-9, 0.4)
    set_state(first.accepted_first_half, 2.5e-9, 337.0)
    set_state(first, 5.0e-9, 338.0)
    second = _synthetic_embedded_step(10.0e-9, 0.4)
    set_state(second.accepted_first_half, 7.5e-9, 337.0)
    set_state(second, 10.0e-9, 336.0)
    recorder = streaming._ControllerV2StreamingRecorder(
        case_id="PRE-CTRL-REVERSAL-PARITY",
        grid=grid,
        fields=object(),
        protocol={"kind": "constant_voltage_step_at_t0", "input_voltage_V": 12.5},
        config=_synthetic_streaming_config(),
        sample_times_s=np.asarray([0.0, 5.0e-9, 10.0e-9]),
        fixed_snapshot_times_s=(0.0, 5.0e-9, 10.0e-9),
        initial_state=initial,
        voltage_scale_V=12.5,
        closure=closure,
    )
    recorder.record_accepted_interval(
        initial, first, 5.0e-9, 12.5, 0.0, coupled_solve_count=3
    )
    recorder.record_accepted_interval(
        first.state, second, 5.0e-9, 12.5, 0.0, coupled_solve_count=3
    )
    result = SimpleNamespace(
        case_id="PRE-CTRL-REVERSAL-PARITY",
        protocol_result=SimpleNamespace(steps=(first, second)),
        reversal_records=tuple(recorder.reversal_records),
    )

    parity = readiness._history_streaming_reversal_parity(
        initial, result, closure, grid
    )
    assert parity["pass"] is True
    assert result.reversal_records[0]["direction"] == "heating_to_cooling"
    original = result.reversal_records[0]["heating_to_cooling_mask_sha256"]
    result.reversal_records[0]["heating_to_cooling_mask_sha256"] = "0" * 64
    assert readiness._history_streaming_reversal_parity(
        initial, result, closure, grid
    )["pass"] is False
    result.reversal_records[0]["heating_to_cooling_mask_sha256"] = original


def test_cached_uncached_attempt_parity_covers_fields_ports_and_ledger_terms() -> None:
    step = _synthetic_embedded_step(5.0e-9, 0.25)
    observation = SimpleNamespace(
        error_class=None,
        error_message=None,
        full_candidate=step,
        first_half_candidate=step.accepted_first_half,
        second_half_candidate=step,
        step=step,
        aggregate_ledgers=step.ledgers,
        aggregate_energy=None,
        diagnostics=step.controller,
    )
    reference = copy.deepcopy(observation)
    parity = readiness._compare_attempt_observations(
        observation, reference, voltage_scale=12.5
    )
    assert parity["pass"] is True

    reference.full_candidate.electrical.cell_joule_power_W[0, 0] += 1.0e-6
    tampered_field = readiness._compare_attempt_observations(
        observation, reference, voltage_scale=12.5
    )
    assert tampered_field["pass"] is False
    assert "cell_joule_power_W" in tampered_field["worst_component"]

    reference = copy.deepcopy(observation)
    reference.aggregate_ledgers.thermal.terms_W["term_W"] += 1.0e-6
    tampered_ledger = readiness._compare_attempt_observations(
        observation, reference, voltage_scale=12.5
    )
    assert tampered_ledger["pass"] is False
    assert "terms.term_W" in tampered_ledger["worst_component"]


def test_single_interval_row_exercises_cached_and_uncached_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    step = _synthetic_embedded_step(1.0e-8, 0.25)
    observation = SimpleNamespace(
        error_class=None,
        error_message=None,
        full_candidate=step,
        first_half_candidate=step.accepted_first_half,
        second_half_candidate=step,
        step=step,
        aggregate_ledgers=step.ledgers,
        aggregate_energy=None,
        diagnostics=step.controller,
    )
    calls: list[dict] = []

    def fake_attempt(*_args, **kwargs):
        calls.append(kwargs)
        return copy.deepcopy(observation)

    monkeypatch.setattr(readiness, "attempt_s2_embedded_interval", fake_attempt)
    monkeypatch.setattr(
        readiness,
        "_attempt_integrity_values",
        lambda *_args: {
            "overall_pass": True,
            "finite": True,
            "nonlinear_pass": True,
            "ledgers_pass": True,
            "lateral_pass": True,
            "thermal_relative_residual_max": 0.0,
            "circuit_relative_residual_max": 0.0,
            "combined_relative_residual_max": 0.0,
            "device_power_relative_residual_max": 0.0,
            "lateral_relative_mismatch_max": 0.0,
            "lateral_roundoff_ratio_max": 0.0,
        },
    )
    execution = object.__new__(readiness._RealReadinessExecution)
    execution.deadline_s = math.inf
    execution.config = {
        "formal_protocols": {
            "protocols": {
                "transition_probe_12p5V": {
                    "kind": "constant_voltage_step_at_t0",
                    "input_voltage_V": 12.5,
                }
            }
        },
        "reference_solver": {
            "formal_time_step_divisors": [1, 2, 4],
            "active_time_controller": {
                "controller_id": "embedded_time_consistency_v2_only",
                "outer_interval": {
                    "base_maximum_s": 1.0e-8,
                    "emergency_floor_base_s": 9.765625e-12,
                },
                "voltage_scale": {
                    "protocol_V_scale_V": {"transition_probe_12p5V": 12.5}
                },
            },
        },
    }
    grid = SimpleNamespace(nx=10, ny=25)
    execution.context = lambda _level: (grid, object(), object(), object())
    monkeypatch.setattr(
        readiness,
        "_deterministic_state",
        lambda *_args, **_kwargs: S2State(
            time_s=0.0,
            temperature_K=np.full((1, 1), 336.4),
            conductive_state=np.full((1, 1), 0.5),
            branch_memory=np.ones((1, 1)),
            device_voltage_V=0.0,
        ),
    )

    row = execution._single_interval_row(
        {
            "sample_id": "PRE-CTRL-STEP-L1-legal_critical-base",
            "spatial_level": 1,
            "state_id": "legal_critical",
            "interval_class": "base",
        }
    )

    assert row["status"] == "pass"
    assert row["cached_uncached_parity_pass"] is True
    assert len(calls) == 2
    assert calls[0]["cache"] is not None
    assert calls[0]["use_equivalent_optimizations"] is True
    assert calls[0]["use_unit_voltage_scaling"] is False
    assert calls[1]["cache"] is None
    assert calls[1]["use_equivalent_optimizations"] is False
    assert calls[1]["use_unit_voltage_scaling"] is False


def test_single_interval_stops_before_uncached_when_global_budget_is_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observation = SimpleNamespace()
    calls: list[dict[str, Any]] = []

    def fake_attempt(*_args, **kwargs):
        calls.append(kwargs)
        return observation

    execution = object.__new__(readiness._RealReadinessExecution)
    execution.config = {
        "formal_protocols": {
            "protocols": {
                "transition_probe_12p5V": {
                    "kind": "constant_voltage_step_at_t0",
                    "input_voltage_V": 12.5,
                }
            }
        },
        "reference_solver": {
            "formal_time_step_divisors": [1, 2, 4],
            "active_time_controller": {
                "controller_id": "embedded_time_consistency_v2_only",
                "outer_interval": {
                    "base_maximum_s": 1.0e-8,
                    "emergency_floor_base_s": 9.765625e-12,
                },
            },
        },
    }
    grid = SimpleNamespace(nx=10, ny=25)
    execution.context = lambda _level: (grid, object(), object(), object())
    remaining = iter((100.0, 100.0, 0.0))
    execution.remaining_budget_s = lambda: next(remaining)
    monkeypatch.setattr(readiness, "attempt_s2_embedded_interval", fake_attempt)
    monkeypatch.setattr(
        readiness,
        "_deterministic_state",
        lambda *_args, **_kwargs: S2State(
            time_s=0.0,
            temperature_K=np.full((1, 1), 336.4),
            conductive_state=np.full((1, 1), 0.5),
            branch_memory=np.ones((1, 1)),
            device_voltage_V=0.0,
        ),
    )

    row = execution._single_interval_row(
        {
            "sample_id": "PRE-CTRL-STEP-L1-legal_critical-base",
            "spatial_level": 1,
            "state_id": "legal_critical",
            "interval_class": "base",
        }
    )

    assert len(calls) == 1
    assert calls[0]["use_unit_voltage_scaling"] is False
    assert row["status"] == "budget_exhausted"
    assert row["failure_class"] == "performance_only"
    assert row["stop_reason"] == "runtime_budget_exhausted_after_cached_interval"


def test_streaming_publish_failure_is_not_reclassified_as_controller_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = object.__new__(readiness._RealReadinessExecution)
    execution.config = {
        "formal_protocols": {
            "protocols": {
                "transition_probe_12p5V": {
                    "kind": "constant_voltage_step_at_t0",
                    "input_voltage_V": 12.5,
                }
            }
        }
    }
    execution.authority = SimpleNamespace(identity_hashes={"identity": "abc"})
    execution.io_measurement_root = Path("unused")
    execution.remaining_budget_s = lambda: 100.0
    grid = SimpleNamespace(nx=10, ny=25)
    execution.context = lambda _level: (grid, object(), object(), object())
    monkeypatch.setattr(
        readiness,
        "_deterministic_state",
        lambda *_args, **_kwargs: S2State(
            time_s=0.0,
            temperature_K=np.full((1, 1), 336.4),
            conductive_state=np.full((1, 1), 0.5),
            branch_memory=np.ones((1, 1)),
            device_voltage_V=0.0,
        ),
    )
    monkeypatch.setattr(
        readiness,
        "run_s2_streaming_protocol_v2",
        lambda *_args, **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        readiness,
        "publish_pre_streaming_case",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )

    with pytest.raises(OSError, match="disk unavailable"):
        execution._short_trajectory_row(
            {
                "sample_id": "PRE-CTRL-TRAJ-L1-legal_critical",
                "spatial_level": 1,
                "state_id": "legal_critical",
            },
            100.0,
        )


def test_global_supervisor_timeout_is_performance_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = SimpleNamespace()
    monkeypatch.setattr(readiness, "_load_authority", lambda: authority)
    monkeypatch.setattr(
        readiness.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            readiness.subprocess.TimeoutExpired(
                "worker", readiness.GLOBAL_WORKER_TIMEOUT_S
            )
        ),
    )
    observed: dict[str, Any] = {}

    def fake_publish(passed_authority, supervisor_started_s):
        observed["authority"] = passed_authority
        observed["supervisor_started_s"] = supervisor_started_s
        return {"disposition": "NO_GO_RUNTIME_PERFORMANCE_ONLY"}

    monkeypatch.setattr(readiness, "_publish_global_timeout_evidence", fake_publish)
    monkeypatch.setattr(
        readiness,
        "_finalize_supervised_wall_clock",
        lambda summary, _started: summary,
    )

    result = readiness.run_readiness_with_global_supervisor()

    assert result["disposition"] == "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    assert observed["authority"] is authority
    assert observed["supervisor_started_s"] > 0.0


def test_only_explicit_solver_fail_closed_exceptions_are_scientific() -> None:
    assert readiness._is_observed_controller_failure(
        RuntimeError("controller-v2 failed at locked outer floor")
    )
    assert not readiness._is_observed_controller_failure(OSError("disk unavailable"))
    assert not readiness._is_observed_controller_failure(
        RuntimeError("controller-v2 fixed event lacks nonlinear context")
    )


def test_global_timeout_preserves_completed_controller_failure() -> None:
    disposition, cause = readiness._timeout_disposition_and_cause(
        {"status": "pass"},
        {
            "status": "fail",
            "failure_class": "controller_integrity",
            "error_class": "aggregate_ledger_failure",
        },
        {
            "status": "fail",
            "failure_class": "performance_only",
            "reason": "global_runtime_preflight_deadline_reached",
        },
    )
    assert disposition == "NO_GO_TIME_CONTROLLER_REVISION"
    assert cause == "aggregate_ledger_failure"

    performance, performance_cause = readiness._timeout_disposition_and_cause(
        {"status": "pass"},
        {"status": "pass"},
        {
            "status": "fail",
            "failure_class": "performance_only",
            "reason": "global_runtime_preflight_deadline_reached",
        },
    )
    assert performance == "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    assert performance_cause == "global_runtime_preflight_deadline_reached"


def test_parent_wall_gate_downgrades_only_go_when_total_exceeds_900_s(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(readiness, "PREFLIGHT_PATH", tmp_path / "preflight.json")
    monkeypatch.setattr(readiness, "READINESS_PATH", tmp_path / "readiness.json")
    monkeypatch.setattr(readiness, "REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(readiness, "RUNNER_PATH", tmp_path / "runner.json")
    monkeypatch.setattr(readiness, "perf_counter", lambda: 901.0)
    summary = {
        "disposition": "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
        "C1": {"status": "pass"},
        "C2": {"status": "pass"},
        "C3": {"status": "pass"},
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
    }

    finalized = readiness._finalize_supervised_wall_clock(summary, 0.0)

    assert finalized["disposition"] == "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    assert finalized["C3"]["failure_class"] == "performance_only"
    assert finalized["preflight_wall_clock_s"] == pytest.approx(901.0)
    assert json.loads((tmp_path / "readiness.json").read_text(encoding="utf-8"))[
        "formal_execution_count"
    ] == 0


def test_environment_identity_excludes_volatile_capacity_telemetry() -> None:
    environment = {
        "platform": "Windows-test",
        "machine": "AMD64",
        "processor": "CPU",
        "physical_core_count": 8,
        "logical_core_count": 12,
        "python_version": "3.11.9",
        "numpy_version": "1.26.4",
        "scipy_version": "1.13.1",
        "thread_environment": {"OMP_NUM_THREADS": "1"},
        "total_ram_bytes": 8_000_000_000,
        "available_ram_bytes_at_launch": 1_000_000_000,
        "disk_total_bytes": 100_000_000_000,
        "disk_free_bytes_at_launch": 20_000_000_000,
        "process_working_set_bytes_at_launch": 10_000_000,
        "process_peak_working_set_bytes_at_launch": 12_000_000,
    }
    changed = dict(environment)
    changed["available_ram_bytes_at_launch"] = 2_000_000_000
    changed["disk_free_bytes_at_launch"] = 10_000_000_000

    assert readiness._stable_environment(environment) == readiness._stable_environment(
        changed
    )
    assert readiness._canonical_hash(
        readiness._stable_environment(environment)
    ) == readiness._canonical_hash(readiness._stable_environment(changed))
    assert readiness._json_safe({"unavailable": math.inf}) == {
        "unavailable": None
    }


def test_one_shot_pipeline_is_strictly_sequential_and_reuses_c2() -> None:
    calls: list[tuple] = []

    def run_c1(remaining_s: float) -> dict:
        calls.append(("C1", remaining_s))
        return {"status": "pass", "failure_class": None}

    def run_c2(remaining_s: float, maximum_intervals: int, stop_s: float) -> dict:
        calls.append(("C2", remaining_s, maximum_intervals, stop_s))
        return {
            "status": "pass",
            "failure_class": None,
            "runtime_evidence_sufficient": True,
            "forecast_sample_row": {"sample_id": "PRE-CTRL-C2-L1-legal_critical"},
        }

    def run_c3(remaining_s: float, reused_c2_row: dict) -> dict:
        calls.append(("C3", remaining_s, reused_c2_row["sample_id"]))
        return {"status": "pass", "failure_class": None}

    result = readiness.execute_readiness_pipeline(
        readiness.ReadinessHooks(run_c1=run_c1, run_c2=run_c2, run_c3=run_c3),
        clock=lambda: 0.0,
    )

    assert [item[0] for item in calls] == ["C1", "C2", "C3"]
    assert calls[1][2:] == (128, 1.0e-6)
    assert calls[2][2] == "PRE-CTRL-C2-L1-legal_critical"
    assert result["disposition"] == "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION"
    assert result["formal_execution_count"] == 0
    assert result["formal_artifact_count"] == 0


def test_stage_marker_is_atomic_before_callback_and_blocks_replay(tmp_path: Path) -> None:
    path = tmp_path / "C1_summary.json"
    authority = SimpleNamespace(identity_hashes={"code_tree": "abc"})
    observed: list[str] = []

    def callback(value: int) -> dict:
        marker = json.loads(path.read_text(encoding="utf-8"))
        observed.append(marker["status"])
        assert marker["numerical_attempt_count"] == 1
        return {"status": "pass", "value": value}

    wrapped = readiness._single_attempt_stage(
        stage="C1",
        path=path,
        authority=authority,
        deadline_utc="2030-01-01T00:00:00+00:00",
        callback=callback,
    )
    result = wrapped(7)

    assert observed == ["RUNNING_SINGLE_ATTEMPT_DO_NOT_REPLAY"]
    assert result["value"] == 7
    assert result["numerical_attempt_count"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "pass"
    with pytest.raises(RuntimeError, match="already exists"):
        wrapped(7)


def test_c1_failure_stops_before_c2_and_c3() -> None:
    calls: list[str] = []

    def forbidden(*_args, **_kwargs):
        calls.append("forbidden")
        raise AssertionError("later readiness gate must not execute")

    result = readiness.execute_readiness_pipeline(
        readiness.ReadinessHooks(
            run_c1=lambda _remaining: {
                "status": "fail",
                "failure_class": "controller_integrity",
            },
            run_c2=forbidden,
            run_c3=forbidden,
        ),
        clock=lambda: 0.0,
    )

    assert calls == []
    assert result["disposition"] == "NO_GO_TIME_CONTROLLER_REVISION"
    assert result["C2"]["status"] == "not_reached"
    assert result["C3"]["status"] == "not_reached"


def test_c2_budget_truncation_with_insufficient_forecast_is_performance_only() -> None:
    result = readiness.execute_readiness_pipeline(
        readiness.ReadinessHooks(
            run_c1=lambda _remaining: {"status": "pass", "failure_class": None},
            run_c2=lambda _remaining, _maximum, _stop: {
                "status": "pass",
                "failure_class": None,
                "stop_reason": "C2_truncated_by_readiness_budget",
                "runtime_evidence_sufficient": False,
            },
            run_c3=lambda *_args: pytest.fail("C3 must not run without evidence"),
        ),
        clock=lambda: 0.0,
    )

    assert result["disposition"] == "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    assert result["C3"]["status"] == "runtime_evidence_insufficient"


def test_c3_integrity_and_performance_failures_classify_differently() -> None:
    base_hooks = dict(
        run_c1=lambda _remaining: {"status": "pass", "failure_class": None},
        run_c2=lambda _remaining, _maximum, _stop: {
            "status": "pass",
            "failure_class": None,
            "runtime_evidence_sufficient": True,
            "forecast_sample_row": {"sample_id": "PRE-CTRL-C2-L1-legal_critical"},
        },
    )
    integrity = readiness.execute_readiness_pipeline(
        readiness.ReadinessHooks(
            **base_hooks,
            run_c3=lambda *_args: {
                "status": "fail",
                "failure_class": "controller_integrity",
            },
        ),
        clock=lambda: 0.0,
    )
    performance = readiness.execute_readiness_pipeline(
        readiness.ReadinessHooks(
            **base_hooks,
            run_c3=lambda *_args: {
                "status": "fail",
                "failure_class": "performance_only",
            },
        ),
        clock=lambda: 0.0,
    )

    assert integrity["disposition"] == "NO_GO_TIME_CONTROLLER_REVISION"
    assert performance["disposition"] == "NO_GO_RUNTIME_PERFORMANCE_ONLY"


def test_c2_no_event_is_exact_nonvoting_na() -> None:
    assert readiness.c2_event_observation(()) == (
        "NA_not_observed_within_bounded_C2_window"
    )
    assert readiness.c2_event_observation(({"direction": "upward"},)) == "observed"
    assert readiness.c2_event_observation((), ({"direction": "heating_to_cooling"},)) == (
        "observed"
    )


def test_c3_plan_is_exact_18_plus_9_with_one_c2_reuse() -> None:
    plan = readiness.build_c3_plan()
    assert len(plan["single_intervals"]) == 18
    assert len(plan["short_trajectories"]) == 9
    assert {
        (item["spatial_level"], item["state_id"], item["interval_class"])
        for item in plan["single_intervals"]
    } == {
        (level, state, interval_class)
        for level in (1, 2, 4)
        for state in ("equilibrium", "legal_critical", "high_conductive")
        for interval_class in ("base", "floor")
    }
    reused = [item for item in plan["short_trajectories"] if item["reuse_C2"]]
    assert reused == [
        {
            "sample_id": "PRE-CTRL-C2-L1-legal_critical",
            "spatial_level": 1,
            "state_id": "legal_critical",
            "reuse_C2": True,
        }
    ]


def test_readiness_publication_orders_csv_before_json_and_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        readiness,
        "_atomic_csv",
        lambda *_args, **_kwargs: calls.append("CSV"),
    )
    monkeypatch.setattr(
        readiness,
        "_atomic_json",
        lambda *_args, **_kwargs: calls.append("JSON"),
    )
    monkeypatch.setattr(
        readiness,
        "_atomic_text",
        lambda *_args, **_kwargs: calls.append("REPORT"),
    )

    readiness.publish_readiness_evidence(
        tmp_path,
        samples=[],
        cost_rows=[],
        C1={"status": "pass"},
        C2={"status": "pass"},
        C3={"status": "pass"},
        summary={
            "disposition": "GO_FOR_PHASE1_V2_FORMAL_AUTHORIZATION",
            "formal_execution_count": 0,
            "formal_artifact_count": 0,
        },
        runner={"status": "pass"},
    )

    assert calls[:2] == ["CSV", "CSV"]
    assert all(item == "JSON" for item in calls[2:-1])
    assert calls[-1] == "REPORT"


def test_actual_controller_v2_readiness_evidence_is_performance_only_no_go() -> None:
    summary = json.loads(
        (ACTUAL_READINESS_DIR / "readiness_summary.json").read_text(
            encoding="utf-8"
        )
    )
    C1 = json.loads(
        (ACTUAL_READINESS_DIR / "C1_summary.json").read_text(encoding="utf-8")
    )
    C2 = json.loads(
        (ACTUAL_READINESS_DIR / "C2_summary.json").read_text(encoding="utf-8")
    )
    preflight = json.loads(
        (ACTUAL_READINESS_DIR / "preflight_summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["disposition"] == "NO_GO_RUNTIME_PERFORMANCE_ONLY"
    assert summary["unique_primary_cause"] == (
        "global_runtime_preflight_deadline_reached"
    )
    assert summary["formal_execution_count"] == 0
    assert summary["formal_artifact_count"] == 0
    assert summary["controller_revision_opportunity_remaining"] is False
    assert summary["performance_repair_consumed"] is False
    assert summary["performance_repair_opportunity_remaining"] is True
    assert summary["preflight_wall_clock_s"] <= 900.0

    assert C1["status"] == "pass"
    assert C1["numerical_attempt_count"] == 1
    assert C1["attempt_marker_created_before_numerics"] is True
    assert C1["accepted_interval_count"] == 23
    assert C1["finite_nonlinear_ledger_lateral_pass"] is True
    assert all(C1["path_integrity"].values())
    assert C1["full_history_streaming_parity"]["pass"] is True

    assert C2["status"] == "pass"
    assert C2["numerical_attempt_count"] == 1
    assert C2["attempt_marker_created_before_numerics"] is True
    assert C2["accepted_interval_count"] == 128
    assert C2["state_bounds_pass"] is True
    assert C2["runtime_evidence_sufficient"] is True
    assert C2["event_observation"] == (
        "NA_not_observed_within_bounded_C2_window"
    )
    assert C2["accepted_fine_event_parity"]["pass"] is True
    assert C2["accepted_fine_reversal_parity"]["pass"] is True

    assert preflight["C3"]["status"] == "fail"
    assert preflight["C3"]["failure_class"] == "performance_only"
    assert preflight["C3"]["numerical_attempt_count"] == 1
    assert preflight["required_single_interval_completed"] == 0
    assert preflight["required_single_interval_expected"] == 18
    assert preflight["required_short_trajectory_completed"] == 1
    assert preflight["required_short_trajectory_expected"] == 9


def test_actual_controller_v2_stop_boundary_is_atomically_preserved() -> None:
    runner = json.loads(
        (ACTUAL_READINESS_DIR / "runner_dry_run.json").read_text(
            encoding="utf-8"
        )
    )
    with (ACTUAL_READINESS_DIR / "preflight_samples.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        samples = list(csv.DictReader(handle))
    forecast_lines = (
        ACTUAL_READINESS_DIR / "campaign_cost_forecast.csv"
    ).read_text(encoding="utf-8").splitlines()

    assert len(samples) == 1
    assert samples[0]["sample_id"] == "PRE-CTRL-C2-L1-legal_critical"
    assert samples[0]["status"] == "pass"
    assert all(row["sample_id"].startswith("PRE-CTRL-") for row in samples)
    assert len(forecast_lines) == 1
    assert forecast_lines[0].startswith("execution_unit_id,")
    assert runner == {
        "formal_artifact_count": 0,
        "formal_execution_count": 0,
        "reason": "global_runtime_preflight_deadline_reached",
        "status": "not_reached",
    }
    assert not (
        ACTUAL_READINESS_DIR.parent / "formal_summary.json"
    ).exists()
    assert not (
        ACTUAL_READINESS_DIR.parent / "formal_convergence.csv"
    ).exists()

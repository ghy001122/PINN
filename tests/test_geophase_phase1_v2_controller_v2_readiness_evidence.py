from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pinnpcm.solvers import geophase_phase1_v2_streaming as streaming
from pinnpcm.solvers.geophase_phase1_v2_implicit import S2State
from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    build_campaign_cost_forecast,
)


ROOT = Path(__file__).resolve().parents[1]
DAG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "runtime_readiness"
    / "execution_dag.json"
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
        "reference_solver": {
            "fixed_physical_comparison_time_grid": {
                "start_s": 0.0,
                "stop_s": 2.0e-5,
                "points": 4001,
                "interval_s": 5.0e-9,
            }
        },
        "metric_contract": {
            "event_definition": {
                "threshold": 0.5,
                "minimum_separation_s": 1.0e-9,
            }
        },
    }


def _synthetic_embedded_step(time_s: float, conductive_state: float):
    state = S2State(
        time_s=time_s,
        temperature_K=np.full((1, 1), 336.4),
        conductive_state=np.full((1, 1), conductive_state),
        branch_memory=np.full((1, 1), 0.9),
        device_voltage_V=6.25,
    )
    balance = SimpleNamespace(
        input_power_W=1.0,
        accounted_power_W=1.0,
        signed_residual_W=0.0,
        relative_residual=0.0,
    )
    return SimpleNamespace(
        state=state,
        electrical=SimpleNamespace(
            potential_V=np.full((1, 1), 6.25),
            cell_joule_power_W=np.full((1, 1), 0.5),
            source_current_A=0.1,
            terminal_device_power_W=0.625,
        ),
        ledgers=SimpleNamespace(
            thermal=balance,
            circuit=balance,
            combined=balance,
            device_power=balance,
        ),
        lateral_flux=SimpleNamespace(
            matrix_face_relative_mismatch=0.0,
            matrix_face_roundoff_ratio=0.0,
            face_to_cell_global_residual_W=0.0,
        ),
        nonlinear=SimpleNamespace(
            method="embedded[synthetic]",
            iterations=3,
            krylov_matvecs=4,
            armijo_backtracks=1,
            fallback_picard_iterations=0,
        ),
        controller=SimpleNamespace(
            embedded_error=SimpleNamespace(
                e_T=1.0e-4,
                e_s=2.0e-4,
                e_b=3.0e-4,
                e_V=4.0e-4,
                e_max=4.0e-4,
            ),
            legacy_conductive_increment=0.25,
            legacy_branch_increment=0.10,
            rejection_index=1,
            coupled_solve_count=3,
        ),
    )


def test_v2_streaming_retains_history_and_records_only_accepted_fine_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    accepted_step = _synthetic_embedded_step(5.0e-9, 0.25)

    def fake_simulate(initial_state, **kwargs):
        calls.append(kwargs)
        # A rejected estimator/fine bundle may contribute cost telemetry but
        # must never enter scalar/event output.
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
            initial_state,
            accepted_step,
            5.0e-9,
            12.5,
            0.01,
        )
        return SimpleNamespace(
            steps=(accepted_step,) if kwargs["retain_full_history"] else (),
            diagnostics=SimpleNamespace(accepted_steps=1),
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
    result = streaming.run_s2_streaming_protocol_v2(
        "PRE-CTRL-SYNTH-STREAM",
        initial,
        protocol=protocol,
        protocol_id="pulse_12p5V",
        grid=SimpleNamespace(shape=(1, 1), cell_area_m2=1.0),
        closure=object(),
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
    assert result.protocol_result.steps == (accepted_step,)
    assert result.final_state is accepted_step.state
    assert len(result.scalar_records) == 2
    assert result.event_records == ()
    row = result.scalar_records[-1]
    assert row["mean_conductive_state"] == pytest.approx(0.25)
    assert row["time_controller"] == "embedded_time_consistency_v2_only"
    assert row["outer_interval_s"] == pytest.approx(5.0e-9)
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

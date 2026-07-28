from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_ledgers import LedgerBalance
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    S2State,
    build_s2_solver_cache,
    initial_s2_state,
    simulate_s2_protocol,
)
from pinnpcm.solvers import geophase_phase1_v2_streaming as streaming


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.fixture(scope="module")
def streaming_context():
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    grid = build_geophase_grid(config, nx_override=10, ny_override=2)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    return config, grid, fields, closure


def test_streaming_matches_identical_short_history_without_retaining_steps(
    streaming_context,
) -> None:
    config, grid, fields, closure = streaming_context
    initial = initial_s2_state(grid, closure, fields, config)
    protocol = config["formal_protocols"]["protocols"]["transition_probe_12p5V"]
    final_time_s = 2.0e-8
    sample_times = streaming.fixed_scalar_sample_times(config, final_time_s)

    history = simulate_s2_protocol(
        initial,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=final_time_s,
        forced_times_s=tuple(sample_times),
        cache=build_s2_solver_cache(grid, fields),
    )
    streamed = streaming.run_s2_streaming_protocol(
        "PRE-STREAM-PARITY",
        initial,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=final_time_s,
    )

    assert history.completed is streamed.protocol_result.completed is True
    assert len(streamed.protocol_result.steps) == 0
    assert len(streamed.scalar_records) == len(sample_times)
    assert len(history.steps) == len(sample_times) - 1
    np.testing.assert_allclose(
        streamed.final_state.temperature_K,
        history.steps[-1].state.temperature_K,
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        streamed.final_state.conductive_state,
        history.steps[-1].state.conductive_state,
        rtol=1.0e-12,
        atol=1.0e-14,
    )
    np.testing.assert_allclose(
        streamed.final_state.branch_memory,
        history.steps[-1].state.branch_memory,
        rtol=1.0e-12,
        atol=1.0e-14,
    )
    for row, step in zip(streamed.scalar_records[1:], history.steps, strict=True):
        assert row["time_s"] == pytest.approx(step.state.time_s, rel=0.0, abs=1.0e-18)
        assert row["device_voltage_V"] == pytest.approx(
            step.state.device_voltage_V, rel=1.0e-12, abs=1.0e-14
        )
        assert row["terminal_current_A"] == pytest.approx(
            step.electrical.source_current_A, rel=1.0e-12, abs=1.0e-24
        )
        assert row["mean_conductive_state"] == pytest.approx(
            float(np.mean(step.state.conductive_state)), rel=1.0e-12, abs=1.0e-14
        )
        for name in ("thermal", "circuit", "combined", "device_power"):
            assert row[f"{name}_relative_residual"] == pytest.approx(
                getattr(step.ledgers, name).relative_residual,
                rel=1.0e-12,
                abs=1.0e-15,
            )


def test_event_full_field_memory_keeps_earliest_four_and_latest_four(
    streaming_context,
) -> None:
    config, grid, fields, _closure = streaming_context
    interval = 5.0e-9
    sample_times = interval * np.arange(13, dtype=float)
    initial = S2State(
        time_s=0.0,
        temperature_K=np.full(grid.shape, fields.ambient_temperature_K),
        conductive_state=np.full(grid.shape, 0.4),
        branch_memory=np.ones(grid.shape),
        device_voltage_V=0.0,
    )
    protocol = config["formal_protocols"]["protocols"]["zero_drive"]
    recorder = streaming._StreamingRecorder(
        case_id="PRE-EVENT-CAP",
        grid=grid,
        fields=fields,
        protocol=protocol,
        config=config,
        sample_times_s=sample_times,
        fixed_snapshot_times_s=(0.0,),
        initial_state=initial,
    )
    zero_balance = LedgerBalance(
        name="zero",
        input_power_W=0.0,
        accounted_power_W=0.0,
        signed_residual_W=0.0,
        relative_residual=0.0,
        terms_W={},
    )
    previous = initial
    for index, time_s in enumerate(sample_times[1:], start=1):
        signal = 0.6 if index % 2 else 0.4
        state = S2State(
            time_s=float(time_s),
            temperature_K=initial.temperature_K.copy(),
            conductive_state=np.full(grid.shape, signal),
            branch_memory=initial.branch_memory.copy(),
            device_voltage_V=0.0,
        )
        step = SimpleNamespace(
            state=state,
            electrical=SimpleNamespace(
                potential_V=np.zeros(grid.shape),
                cell_joule_power_W=np.zeros(grid.shape),
                source_current_A=0.0,
                terminal_device_power_W=0.0,
            ),
            ledgers=SimpleNamespace(
                thermal=zero_balance,
                circuit=zero_balance,
                combined=zero_balance,
                device_power=zero_balance,
            ),
            nonlinear=SimpleNamespace(
                method="synthetic",
                iterations=0,
                krylov_matvecs=0,
                armijo_backtracks=0,
                fallback_picard_iterations=0,
            ),
            lateral_flux=SimpleNamespace(
                matrix_face_relative_mismatch=0.0,
                matrix_face_roundoff_ratio=0.0,
                face_to_cell_global_residual_W=0.0,
            ),
        )
        recorder(previous, step, interval, 0.0, 0.0)
        previous = state

    retained = recorder.selected_event_snapshots()
    retained_indices = sorted({item.event_index for item in retained})
    assert len(recorder.event_records) == 12
    assert len(retained) == 16
    assert retained_indices == [1, 2, 3, 4, 9, 10, 11, 12]
    assert recorder.maximum_in_memory_event_snapshots <= 16
    assert [row["event_index"] for row in recorder.event_records] == list(range(1, 13))


def test_pre_case_publish_is_validated_atomic_and_immutable(
    tmp_path: Path, streaming_context
) -> None:
    config, grid, fields, closure = streaming_context
    initial = initial_s2_state(grid, closure, fields, config)
    protocol = config["formal_protocols"]["protocols"]["zero_drive"]
    result = streaming.run_s2_streaming_protocol(
        "PRE-ATOMIC-CASE",
        initial,
        protocol=protocol,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        final_time_s=1.0e-8,
    )

    published = streaming.publish_pre_streaming_case(
        tmp_path, result, identity_hashes={"execution_addendum": "abc123"}
    )
    assert published == tmp_path / "PRE-ATOMIC-CASE"
    assert not list(tmp_path.glob(".*.tmp-*"))
    metadata = json.loads((published / "metadata.json").read_text(encoding="utf-8"))
    completion = json.loads(
        (published / "completion.json").read_text(encoding="utf-8")
    )
    rows = list(csv.DictReader((published / "scalars.csv").read_text(encoding="utf-8").splitlines()))
    assert metadata["retained_full_accepted_step_history"] == 0
    assert metadata["schema_version"].endswith("_v2")
    assert metadata["reversal_record_count"] == len(result.reversal_records)
    assert metadata["identity_hashes"] == {"execution_addendum": "abc123"}
    assert completion["status"] == "validated_complete"
    assert completion["schema_version"].endswith("_v2")
    assert "reversals.csv" in completion["payload_hashes_sha256"]
    assert (published / "reversals.csv").is_file()
    assert (published / "events.csv").read_text(encoding="utf-8").splitlines()[0] == ",".join(
        streaming._EVENT_FIELDS
    )
    assert (published / "reversals.csv").read_text(encoding="utf-8").splitlines()[0] == ",".join(
        streaming._REVERSAL_FIELDS
    )
    assert len(rows) == metadata["scalar_record_count"]
    assert streaming.published_case_bytes(published) > 0
    with pytest.raises(FileExistsError, match="immutable"):
        streaming.publish_pre_streaming_case(
            tmp_path, result, identity_hashes={"execution_addendum": "abc123"}
        )


def test_controller_v2_event_publication_rejects_missing_diagnostics(
    tmp_path: Path,
) -> None:
    result = SimpleNamespace(
        case_id="PRE-CTRL-EVENT-SCHEMA-TAMPER",
        scalar_records=(
            {
                "case_id": "PRE-CTRL-EVENT-SCHEMA-TAMPER",
                "time_controller": "embedded_time_consistency_v2_only",
            },
        ),
        event_records=(
            {
                "case_id": "PRE-CTRL-EVENT-SCHEMA-TAMPER",
                "event_index": 1,
                "direction": "upward",
                "crossing_time_s": 1.0e-9,
                "before_sample_time_s": 0.0,
                "after_sample_time_s": 2.0e-9,
                "before_signal": 0.4,
                "after_signal": 0.6,
            },
        ),
        reversal_records=(),
        field_snapshots=(),
        protocol_result=SimpleNamespace(
            completed=True,
            stop_reason="synthetic",
            diagnostics=SimpleNamespace(accepted_steps=1),
            steps=(),
        ),
    )

    with pytest.raises(ValueError, match="event record is incomplete"):
        streaming.publish_pre_streaming_case(
            tmp_path, result, identity_hashes={"controller_v2": "locked"}
        )

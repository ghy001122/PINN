"""Behavioral tests for the M37R post-transient event-window repair."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import yaml

from pinnpcm.external_data.vo2_cross_regime_observability_repair import (
    EVENT_WINDOW_CONTRACT_ID,
    build_m36_reference_window_audit,
    event_topology_diagnostics,
    forward_cache_key,
    post_transient_event_signature,
    run_mock_contract_pipeline,
)
from pinnpcm.external_data.vo2_multivoltage import preprocess_experiment
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


CONFIG_PATH = Path("configs/m37r_continuous_event_observability_repair.yaml")


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_config_preserves_original_scientific_contract_and_seal() -> None:
    config = _config()
    assert config["parameters"]["coordinate_names"] == ["log_C_th", "log_S_e"]
    assert config["parameters"]["relative_steps"] == [0.01, 0.005, 0.0025]
    assert config["observations"]["groups"] == {
        "static_only": [9.0, 17.0],
        "oscillatory_only": [11.0, 15.0],
        "joint": [9.0, 11.0, 15.0, 17.0],
    }
    assert config["solvers"]["primary_method"] == "DOP853"
    assert config["solvers"]["independent_method"] == "Radau"
    assert config["solvers"]["maximum_total_forward_evaluations"] == 72
    assert config["gates"] == {
        "every_state_finite": True,
        "every_activity_class_exact": True,
        "every_event_topology_compatible": True,
        "two_finest_white_jacobian_relative_change_max": 0.10,
        "two_finest_retained_left_subspace_angle_deg_max": 10.0,
        "dop853_radau_column_direction_cosine_min": 0.99,
        "dop853_radau_retained_singular_value_relative_difference_max": 0.10,
        "relative_singular_value_rank_threshold": 0.05,
        "joint_required_rank": 2,
        "joint_retained_condition_number_max": "1.0e4",
        "static_oscillatory_top_right_direction_angle_deg_min": 20.0,
        "all_gates_required_for_qualified_support": True,
    }
    assert config["data"]["withheld_13v"]["numeric_access"] == "forbidden"
    assert config["data"]["withheld_13v"]["extracted_path"] is None


def test_event_window_includes_both_boundaries_without_tolerance() -> None:
    records = [
        {"event_type": "reversal_before_trace", "time_s": -1.0e-12},
        {"event_type": "reversal_before_window", "time_s": 0.999999999999},
        {"event_type": "reversal_at_window", "time_s": 1.0},
        {"event_type": "thermal_extremum_high", "time_s": 2.0},
        {"event_type": "reversal_inside", "time_s": 5.0},
        {"event_type": "reversal_at_end", "time_s": 10.0},
        {"event_type": "reversal_after_trace", "time_s": 10.0 + 1.0e-12},
    ]
    audit = post_transient_event_signature(
        records, trace_start_s=0.0, trace_end_s=10.0, transient_fraction=0.1
    )
    assert audit["window_start_s"] == 1.0
    assert audit["lower_boundary"] == audit["upper_boundary"] == "inclusive"
    assert audit["floating_tolerance_s"] == 0.0
    assert audit["full_horizon_event_count"] == 4
    assert audit["post_transient_event_times_s"] == (1.0, 5.0, 10.0)
    assert audit["post_transient_event_count"] == 3


def test_registered_full_and_post_transient_counts_match_locked_m37_m36_facts() -> None:
    config = _config()
    m37 = json.loads(Path(config["historical_inputs"]["m37_result"]).read_text(encoding="utf-8"))
    m36 = json.loads(Path(config["historical_inputs"]["m36_summary"]).read_text(encoding="utf-8"))
    expected = config["event_window"]["expected_nominal_counts"]
    for voltage in (9.0, 11.0, 15.0, 17.0):
        key = f"{voltage:g}"
        assert m37["nominal_checks"]["DOP853"][key]["event_count"] == int(
            expected[key]["full_horizon"]
        )
        assert m37["nominal_checks"]["Radau"][key]["event_count"] == int(
            expected[key]["full_horizon"]
        )
        assert m36["voltage_results"][key]["reference_parity_metrics"][
            "reference_reversal_event_count"
        ] == int(expected[key]["post_transient"])


def test_m36_reference_rows_pass_the_same_post_transient_helper() -> None:
    config = _config()
    observations = {}
    for item in config["data"]["open_voltage_curves"]:
        voltage = float(item["voltage_V"])
        observations[voltage] = preprocess_experiment(
            Path(item["path"]),
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
    m36 = json.loads(Path(config["historical_inputs"]["m36_summary"]).read_text(encoding="utf-8"))
    expected_counts = {
        voltage: int(
            m36["voltage_results"][f"{voltage:g}"]["reference_parity_metrics"][
                "reference_reversal_event_count"
            ]
        )
        for voltage in (9.0, 11.0, 15.0, 17.0)
    }
    with Path(config["historical_inputs"]["m36_event_times"]).open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    audit = build_m36_reference_window_audit(
        rows, observations, expected_counts, transient_fraction=0.1
    )
    assert audit["all_counts_match"] is True
    assert {
        key: row["post_transient_event_count"]
        for key, row in audit["by_voltage"].items()
    } == {"9": 0, "11": 196, "15": 344, "17": 0}


def test_cache_key_includes_solver_voltage_parameter_step_context_and_window() -> None:
    source = yaml.safe_load(
        Path("configs/vo2_d0a_exact_source_v2.yaml").read_text(encoding="utf-8")
    )
    params = VO2ThermalNeuristorParameters.from_config(source)
    times = np.linspace(0.0, 1.0e-6, 11)
    base = forward_cache_key(
        params,
        voltage_V=11.0,
        evaluation_times_s=times,
        method="DOP853",
        event_window_contract_id=EVENT_WINDOW_CONTRACT_ID,
    )
    assert base != forward_cache_key(
        params,
        voltage_V=11.0,
        evaluation_times_s=times,
        method="Radau",
        event_window_contract_id=EVENT_WINDOW_CONTRACT_ID,
    )
    assert base != forward_cache_key(
        params,
        voltage_V=11.0,
        evaluation_times_s=times,
        method="DOP853",
        event_window_contract_id="different_window",
    )


def test_topology_uses_post_transient_sequence_and_retains_terminal_rule() -> None:
    reference = ("reversal_to_cooling", "reversal_to_heating", "reversal_to_cooling")
    compatible = event_topology_diagnostics(reference, reference[:-1])
    incompatible = event_topology_diagnostics(reference, reference[:-2])
    assert compatible["event_topology_compatible"] is True
    assert compatible["common_prefix_length"] == 2
    assert incompatible["event_topology_compatible"] is False


def test_mock_pipeline_reaches_event_feature_jacobian_svd_and_schema() -> None:
    result = run_mock_contract_pipeline()
    assert result["pipeline"] == "synthetic_mock_no_scientific_vote"
    assert result["all_pass"] is True
    assert all(result["checks"].values())
    assert result["group_threshold_ranks"]["joint"] == 2
    assert all(shape[1] == 2 for shape in result["group_shapes"].values())


def test_schema_forbids_fit_training_m38_and_13v_actions() -> None:
    schema = json.loads(
        Path("docs/schemas/m37r_continuous_event_observability_evidence_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["sealed_13v_access"]["const"] is False
    assert schema["properties"]["fit_executed"]["const"] is False
    assert schema["properties"]["fit_lock_created"]["const"] is False
    assert schema["properties"]["pinn_training_performed"]["const"] is False
    assert schema["properties"]["m38_executed"]["const"] is False

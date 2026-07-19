"""Behavioral tests for the preregistered M37 observability contract."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import yaml

from pinnpcm.external_data.vo2_cross_regime_observability import (
    acute_vector_angle_deg,
    analytic_quotient_jacobian,
    event_topology_compatible,
    m36_semantic_audit,
    svd_geometry,
    whitened_feature_vector,
)


CONFIG_PATH = Path("configs/m37_continuous_event_observability.yaml")


def _config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _fake_result(*, oscillatory: bool) -> SimpleNamespace:
    time_s = np.linspace(0.0, 5.0, 501)
    if oscillatory:
        current = 2.0 + np.sin(2.0 * np.pi * time_s)
        voltage = 3.0 + 0.4 * np.cos(2.0 * np.pi * time_s)
        records = [
            {"event_type": "reversal_to_cooling", "time_s": value}
            for value in (1.0, 2.0, 3.0, 4.0, 5.0)
        ]
    else:
        current = np.full_like(time_s, 2.0)
        voltage = np.full_like(time_s, 3.0)
        records = []
    trace = SimpleNamespace(
        time_s=time_s,
        current_A=current,
        voltage_V=voltage,
        temperature_K=np.full_like(time_s, 325.0),
        resistance_ohm=np.full_like(time_s, 1.5),
    )
    return SimpleNamespace(trace=trace, event_records=records)


def test_config_locks_exact_parameters_steps_groups_and_seal() -> None:
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
    assert config["data"]["withheld_13v"]["numeric_access"] == "forbidden"
    assert config["data"]["withheld_13v"]["extracted_path"] is None
    assert config["budget"]["fitting"] == "forbidden"


def test_event_topology_allows_only_one_terminal_horizon_difference() -> None:
    reference = ("reversal_to_cooling", "reversal_to_heating", "reversal_to_cooling")
    assert event_topology_compatible(reference, reference)
    assert event_topology_compatible(reference, reference[:-1])
    assert not event_topology_compatible(reference, reference[:-2])
    assert not event_topology_compatible(
        reference,
        ("reversal_to_heating", "reversal_to_cooling", "reversal_to_heating"),
    )


def test_whitened_feature_contract_has_expected_dimensions_and_is_finite() -> None:
    config = _config()
    static_scales = {
        "feature_scales": {
            "steady_current_A": 1.0,
            "steady_voltage_V": 1.0,
            "total_charge_C": 1.0,
            "total_energy_J": 1.0,
        }
    }
    static, static_labels, _ = whitened_feature_vector(
        _fake_result(oscillatory=False),
        regime="static",
        scale_record=static_scales,
        observation_config=config["observations"],
    )
    assert static.shape == (4,)
    assert len(static_labels) == 4
    assert np.isfinite(static).all()

    oscillatory_scales = {
        "feature_scales": {
            "log_frequency": 1.0,
            "peak_to_trough_current_A": 1.0,
            "duty_cycle": 1.0,
            "cycle_charge_C": 1.0,
            "cycle_energy_J": 1.0,
            "phase_current_A": 1.0,
            "phase_voltage_V": 1.0,
        }
    }
    oscillatory, labels, raw = whitened_feature_vector(
        _fake_result(oscillatory=True),
        regime="oscillatory",
        scale_record=oscillatory_scales,
        observation_config=config["observations"],
    )
    assert oscillatory.shape == (5 + 2 * config["observations"]["phase_grid_points"],)
    assert len(labels) == oscillatory.size
    assert raw["cycle_count"] >= 2
    assert np.isfinite(oscillatory).all()


def test_analytic_quotient_transform_preserves_algebraic_rank() -> None:
    raw = np.asarray([[2.0, 0.1], [0.5, 3.0], [1.0, -0.2]])
    quotient = analytic_quotient_jacobian(raw)
    assert np.linalg.matrix_rank(raw) == np.linalg.matrix_rank(quotient) == 2
    assert not np.allclose(raw, quotient)
    raw_geometry = svd_geometry(raw, relative_threshold=0.05)
    assert raw_geometry["threshold_rank"] == 2
    assert acute_vector_angle_deg(np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])) == 90.0


def test_m36_broad_classifier_is_detected_without_changing_failure_vote() -> None:
    summary = {
        "m36_primary_gates_pass": False,
        "voltage_results": {
            "9": {"classification": "normalization_artifact_resolved_by_absolute_noise_floor_metrics", "primary_gate_passed": True},
            "11": {"classification": "true_numerical_nonconvergence", "primary_gate_passed": False},
            "15": {"classification": "true_numerical_nonconvergence", "primary_gate_passed": False},
            "17": {"classification": "true_numerical_nonconvergence", "primary_gate_passed": False},
        },
    }
    rows = []
    for voltage in (9.0, 11.0, 15.0, 17.0):
        for dt, score in zip((0.01, 0.005, 0.0025), (4.0, 2.0, 1.0)):
            rows.append(
                {
                    "voltage_V": voltage,
                    "solver_family": "source_compatible_explicit_euler",
                    "dt_s": dt,
                    "normalized_primary_score": score,
                }
            )
    script = 'elif not primary_pass:\n    classification = "true_numerical_nonconvergence"'
    audit = m36_semantic_audit(
        summary,
        rows,
        execution_script_text=script,
        summary_sha256="A",
        metrics_sha256="B",
        execution_script_sha256="C",
    )
    assert audit["broad_primary_failure_classifier_detected"] is True
    assert audit["source_m36_failure_vote_unchanged"] is True
    assert audit["voltage_audit"]["11"]["superseding_semantic_wording"].startswith(
        "finite_step_accuracy_gate_failed"
    )


def test_schema_forbids_positive_flags_for_sealed_or_fit_actions() -> None:
    schema = json.loads(
        Path(
            "docs/schemas/m37_continuous_event_observability_evidence_v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema["properties"]["sealed_13v_access"]["const"] is False
    assert schema["properties"]["fit_executed"]["const"] is False
    assert schema["properties"]["fit_lock_created"]["const"] is False
    assert schema["properties"]["pinn_training_performed"]["const"] is False

"""Behavioral tests for the sealed-data M35 public multi-voltage workflow."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.external_data.vo2_multivoltage import (
    activity_metrics,
    parameters_from_coordinates,
    preprocess_experiment,
)
from pinnpcm.external_data.vo2_zhang import load_tektronix_trace
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


def _config() -> dict:
    return yaml.safe_load(
        Path("configs/m35_public_multivoltage_fit.yaml").read_text(encoding="utf-8")
    )


def _source_params() -> VO2ThermalNeuristorParameters:
    source = yaml.safe_load(
        Path("configs/vo2_d0a_exact_source_v2.yaml").read_text(encoding="utf-8")
    )
    return VO2ThermalNeuristorParameters.from_config(source)


def test_open_voltage_and_lovo_roles_are_exact_and_13v_stays_metadata_only() -> None:
    config = _config()
    curves = config["data"]["open_voltage_curves"]
    assert [float(item["voltage_V"]) for item in curves] == [9.0, 11.0, 15.0, 17.0]
    assert all("13v" not in Path(item["path"]).name.casefold().replace("_", "") for item in curves)
    withheld = config["data"]["withheld_13v"]
    assert withheld["numeric_access"] == "forbidden"
    assert withheld["extracted_path"] is None
    assert len(withheld["member_names_metadata_only"]) == 2
    for fold in config["fit"]["folds"]:
        roles = sorted(
            [float(value) for value in fold["fit_voltages_V"]]
            + [float(fold["holdout_voltage_V"])]
        )
        assert roles == [9.0, 11.0, 15.0, 17.0]


def test_13v_loader_guard_fails_before_file_access(tmp_path: Path) -> None:
    missing = tmp_path / "Experiment_13V.csv"
    with pytest.raises(PermissionError, match="sealed"):
        load_tektronix_trace(missing, current_sense_ohm=50.0)


def test_open_trace_preprocessing_uses_raw_time_zero_and_baseline_only() -> None:
    config = _config()
    item = config["data"]["open_voltage_curves"][0]
    trace = preprocess_experiment(
        Path(item["path"]),
        voltage_V=float(item["voltage_V"]),
        current_sense_ohm=float(config["data"]["current_sense_ohm"]),
    )
    assert trace["time_s"][0] >= 0.0
    assert np.all(np.diff(trace["time_s"]) > 0.0)
    assert trace["raw_sample_count"] > trace["evaluation_sample_count"]
    assert trace["source_kind"].startswith("public_external_raw")
    assert math.isfinite(trace["current_baseline_A"])
    assert math.isfinite(trace["device_voltage_baseline_V"])


def test_raw_and_quotient_coordinates_map_to_identical_physics() -> None:
    base = _source_params()
    raw = np.asarray([0.2, -0.1])
    quotient = np.asarray([raw[0] - raw[1], raw[1]])
    raw_params = parameters_from_coordinates(base, raw, "raw_Cth_Sth")
    quotient_params = parameters_from_coordinates(
        base, quotient, "quotient_tau_th_Sth"
    )
    assert raw_params.C_th_J_per_K == pytest.approx(quotient_params.C_th_J_per_K)
    assert raw_params.S_th_W_per_K == pytest.approx(quotient_params.S_th_W_per_K)
    assert raw_params.C_th_J_per_K / raw_params.S_th_W_per_K == pytest.approx(
        quotient_params.C_th_J_per_K / quotient_params.S_th_W_per_K
    )


def test_activity_classifier_is_fixed_and_executable_for_quiescent_trace() -> None:
    config = _config()["event_metrics"]
    time_s = np.linspace(0.0, 1.0e-5, 1000)
    current_A = np.zeros_like(time_s)
    voltage_V = np.zeros_like(time_s)
    result = activity_metrics(
        time_s, current_A, voltage_V, config, noise_scale_A=1.0e-9
    )
    assert result["activity_class"] == "quiescent"
    assert result["spike_count"] == 0
    assert result["frequency_Hz"] == 0.0


def test_cross_model_mapping_refuses_direct_gamma_sub_validation() -> None:
    mapping = _config()["cross_model_mapping"]
    assert mapping["gamma_sub_units"] != mapping["S_e_units"]
    assert mapping["geometry_equivalence_proved"] is False
    assert mapping["material_equivalence_proved"] is False
    assert mapping["direct_S_e_to_gamma_sub_validation_claim"] == "forbidden"
    assert mapping["allowed_cross_model_coordinate"] == "tau_th_equals_C_th_over_S_e"

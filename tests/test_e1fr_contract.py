"""Fail-closed tests for the one-run E1F-R corrective-audit contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pinnpcm.audit.evidence_identity import assert_evidence_lock
from pinnpcm.physics.qiu_author_compact_model import (
    default_parameters,
    proximity_temperature_from_reversal,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/e1fr_qiu_source_equation_correction.yaml"
PREREG = ROOT / "outputs/tables/e1fr_qiu_source_equation_correction_preregistration.json"


def test_e1fr_locks_literal_s3_and_forbids_holdout_vote() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    correction = config["correction_contract"]
    assert correction["source_equation_s3_literal"] == (
        "T_pr = delta*w/2 + T_c - (2*F(T_r)-1)/beta - T_r"
    )
    assert correction["original_formal_status"] == "implementation_contract_invalid"
    assert correction["original_scientific_vote"] is False
    assert correction["main_fig2b_status"] == "implementation_contract_invalid_unassessed"
    assert correction["main_fig2b_simulation_or_scoring_forbidden"] is True
    assert config["source"]["setting_curve"]["input_voltage_V"] == 12.0
    assert config["gates"]["setting_curve_nrmse_max"] == 0.10
    assert config["budget"]["formal_execution_limit"] == 1
    assert config["budget"]["holdout_refit"] == "forbidden"
    assert config["governance"]["m41_authorized"] is False
    assert config["governance"]["sealed_zhang_13v_access"] is False


def test_e1fr_proximity_temperature_uses_printed_linear_fraction_term() -> None:
    params = default_parameters()
    fraction = 0.73
    reversal_temperature = 337.2
    expected = (
        -params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - (2.0 * fraction - 1.0) / params.beta_per_K
        - reversal_temperature
    )
    actual = proximity_temperature_from_reversal(
        -1, fraction, reversal_temperature, params
    )
    assert actual == pytest.approx(expected, rel=0.0, abs=1.0e-14)


def test_e1fr_preregistration_is_hash_locked_when_present() -> None:
    if not PREREG.exists():
        pytest.skip("E1F-R preregistration has not yet been generated")
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    assert payload["all_preflight_checks_pass"] is True
    assert all(payload["preflight_checks"].values())
    assert payload["post_lock_corrective_audit"] is True
    assert payload["independent_holdout"] is False
    assert payload["main_fig2b_simulation_or_scoring_authorized"] is False
    assert payload["original_e1f_scientific_vote"] is False
    assert payload["formal_execution_limit"] == 1
    assert payload["m41_authorized"] is False
    assert payload["pinn_training_authorized"] is False
    assert payload["sealed_zhang_13v_access"] is False
    assert payload["implementation_records"]
    for record in payload["implementation_records"]:
        path = ROOT / record["path"]
        assert path.exists()
        assert_evidence_lock(
            path,
            record["sha256"],
            expected_size=int(record["size_bytes"]),
            root=ROOT,
            allow_historical_revision=True,
        )

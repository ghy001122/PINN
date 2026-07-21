from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.audit.qiu_llp_source_contract import (
    ContractParameters,
    build_source_contract_summary,
    de_almeida_sena_atanh_proximity_temperature,
    proximity_kernel,
)


ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict:
    return yaml.safe_load((ROOT / "configs/qiu_llp_source_contract.yaml").read_text(encoding="utf-8"))


def test_kernel_zero_has_analytic_normalization_deficit() -> None:
    value = proximity_kernel(0.0, 0.956)
    expected = 0.5 * (1.0 + math.tanh(math.pi**2))
    assert value == expected
    assert 0.0 < 1.0 - value < 1.0e-8


def test_atanh_input_is_not_silently_clipped() -> None:
    params = ContractParameters(**_config()["parameters"])
    for invalid in [0.0, 1.0, -0.1, 1.1, np.nan]:
        with pytest.raises(ValueError):
            de_almeida_sena_atanh_proximity_temperature(1, invalid, 330.0, params)


def test_blocking_source_contract_gates_pass_at_locked_thresholds() -> None:
    summary, rows = build_source_contract_summary(_config())
    assert len(rows) == 4002
    assert summary["formula_contract_evaluations"] == 4002
    assert summary["source_transcription_fidelity"]["gate_pass"] is True
    assert summary["anchor_inverse_identity"]["gate_pass"] is True
    assert summary["realized_reversal_continuity"]["gate_pass"] is True
    assert summary["blocking_gates_pass"] is True
    assert summary["hysteresis_property_diagnostics"]["blocking"] is False
    assert summary["new_formal_scientific_experiments"] == 0
    assert summary["new_claim_bearing_device_forward_runs"] == 0


def test_manufactured_protocols_keep_explicit_event_and_refinement_metadata() -> None:
    summary, _ = build_source_contract_summary(_config())
    protocols = summary["hysteresis_property_diagnostics"]["protocol_runs"]
    assert len(protocols) == 12
    assert all(item["diagnostic_only"] and item["all_finite"] for item in protocols)
    assert {item["step_refinement"] for item in protocols} == {1, 2}

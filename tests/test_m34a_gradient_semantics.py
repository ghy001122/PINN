"""Safety and classification tests for the diagnostic-only M34-A amendment."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from pinnpcm.pinn.m34a_gradient_semantics import _longest_true_run


def _config() -> dict:
    return yaml.safe_load(
        Path("configs/m35_public_multivoltage_fit.yaml").read_text(encoding="utf-8")
    )


def test_m34a_contract_is_diagnostic_only_and_cannot_authorize_training() -> None:
    config = _config()["m34a"]
    assert config["diagnostic_only"] is True
    assert config["training_authorization"] is False
    assert len(config["direction_seeds"]) == 8
    assert len(config["modules"]) == 4
    assert len(config["relative_steps"]) >= 8
    assert config["dtype"] == "float64"

    script = Path("scripts/run_m34a_gradient_semantics.py").read_text(
        encoding="utf-8"
    )
    assert '"training_authorized": False' in script
    assert '"sealed_13v_access": False' in script
    assert "train_m34" not in script


def test_m34a_original_failed_gate_is_hash_locked() -> None:
    config = _config()["m34a"]
    original = json.loads(Path(config["original_summary"]).read_text(encoding="utf-8"))
    assert original["corrected_training_authorized"] is False
    assert original["status"] == "failed_but_informative"
    assert config["original_summary_sha256"]


def test_longest_true_run_handles_fragmented_intervals() -> None:
    assert _longest_true_run([]) == 0
    assert _longest_true_run([False, True, True, False, True]) == 2
    assert _longest_true_run([True, True, True]) == 3

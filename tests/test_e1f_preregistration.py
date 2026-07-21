"""Fail-closed checks for the E1F pre-result evidence lock."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/e1f_qiu_author_external_anchor.yaml"
PREREG = ROOT / "outputs/tables/e1f_qiu_author_anchor_preregistration.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_e1f_preregistration_is_leakage_safe_and_fail_closed() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    payload = json.loads(PREREG.read_text(encoding="utf-8"))
    assert payload["all_preflight_checks_pass"] is True
    assert all(payload["preflight_checks"].values())
    holdout = payload["locked_source_contract"]["holdout_curve"]
    assert holdout["curve_id"] == "qiu_2024_main_fig2b_12p5v"
    assert holdout["numeric_ordinate_access_before_preregistration"] is False
    assert holdout["independent_external_validation"] is False
    assert holdout["source_author_parameter_development_independence_known"] is False
    assert holdout["same_paper_development_contamination_risk"] is True
    assert payload["locked_hysteresis_contract"][
        "qiu_source_reports_complete_executable_update"
    ] is False
    assert payload["locked_hysteresis_contract"][
        "exact_author_code_reproduction_authorized"
    ] is False
    assert payload["preregistration_implementation_records"]
    assert payload["digitization_authorized_after_preregistration_commit"] is True
    assert payload["formal_execution_limit"] == 1
    assert payload["m41_authorized"] is False
    assert payload["pinn_training_authorized"] is False
    assert payload["sealed_zhang_13v_access"] is False
    for group in ("m40_protected_records", "m40r_protected_records", "frozen_gt_records"):
        assert payload[group]
        for record in payload[group]:
            path = ROOT / record["path"]
            assert path.exists()
            assert _sha256(path) == record["sha256"]
    assert config["governance"]["further_m40r_execution_forbidden"] is True

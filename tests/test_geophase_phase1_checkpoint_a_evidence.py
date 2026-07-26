from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml"
OUTPUT_ROOT = ROOT / "outputs" / "tables" / "geophase_phase1"
PREREGISTRATION_SHA = "212a4277bf9cf8afe365d922adefe67bdd7595e1"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _json(name: str) -> dict:
    return json.loads((OUTPUT_ROOT / name).read_text(encoding="utf-8"))


def test_checkpoint_a_identity_is_locked_and_formal_count_is_zero() -> None:
    preregistration = _json("preregistration.json")
    summary = _json("checkpoint_a_summary.json")
    environment = _json("environment_manifest.json")
    config_hash = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    assert preregistration["preregistration_sha"] == PREREGISTRATION_SHA
    assert preregistration["checkpoint_a_smoke_start_head"] == PREREGISTRATION_SHA
    assert preregistration["implementation_commit"] == "SELF"
    assert preregistration["config_sha256"] == config_hash
    assert environment["config_sha256"] == config_hash
    assert summary["formal_execution_count"] == 0
    assert preregistration["formal_execution_count"] == 0
    assert environment["formal_execution_count"] == 0
    assert summary["formal_campaign_executed"] is False
    assert summary["formal_case_results_generated"] == 0
    assert summary["claim_status"] == "forbidden_pending_formal_campaign"
    assert summary["next_action"] == (
        "stop_and_wait_for_explicit_checkpoint_b_authorization"
    )


def test_formal_inventory_is_manifest_only_and_exactly_96() -> None:
    with (OUTPUT_ROOT / "formal_case_inventory.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 96
    assert len({row["case_id"] for row in rows}) == 96
    assert {row["formal_status"] for row in rows} == {"planned_not_executed"}
    assert {row["evidence_type"] for row in rows} == {
        "preregistered_case_manifest_only"
    }
    assert not (OUTPUT_ROOT / "summary.json").exists()
    assert not (OUTPUT_ROOT / "convergence.csv").exists()
    assert not (OUTPUT_ROOT / "k_state_reduction.csv").exists()


def test_checkpoint_a_smoke_ledgers_do_not_vote_as_formal_results() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    thresholds = {
        "thermal": float(config["gates"]["thermal_ledger_relative_residual_max"]),
        "circuit": float(config["gates"]["circuit_ledger_relative_residual_max"]),
        "combined_electrothermal": float(
            config["gates"]["combined_ledger_relative_residual_max"]
        ),
        "device_power_identity": float(
            config["gates"]["device_power_identity_relative_residual_max"]
        ),
    }
    with (OUTPUT_ROOT / "checkpoint_a_ledgers.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 8
    assert {row["evidence_type"] for row in rows} == {
        "checkpoint_a_smoke_nonclaim_evidence"
    }
    zero = [row for row in rows if row["case_id"] == "smoke_zero_drive"]
    low = [row for row in rows if row["case_id"] == "smoke_low_drive"]
    assert len(zero) == 4 and {row["voting"] for row in zero} == {"False"}
    assert len(low) == 4 and {row["voting"] for row in low} == {"True"}
    for row in low:
        assert float(row["relative_residual"]) <= thresholds[row["ledger"]]


def test_checkpoint_a_preserves_user_locked_scope() -> None:
    summary = _json("checkpoint_a_summary.json")
    assert summary["nominal_metallic_endmember_resistance_ohm"] == pytest.approx(
        262.5
    )
    assert summary["qiu_s7_dynamic_channel_correction_in_formal_matrix"] is False
    assert summary["nonzero_dual_device_coupling"] == "forbidden"
    assert summary["reported_500nm_placement_semantics"] == (
        "unresolved_and_nonvoting_in_phase1"
    )

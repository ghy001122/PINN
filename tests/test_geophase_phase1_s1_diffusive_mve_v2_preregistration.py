from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve.yaml"
AMENDMENT_PATH = (
    ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve_v2.yaml"
)
S2_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
PREREG_PATH = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "s1_diffusive_mve_v2_preregistration.json"
)

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_s1_v2_amendment_preserves_and_hashes_the_original_contract() -> None:
    cfg = _yaml(AMENDMENT_PATH)

    assert cfg["task_id"] == "Q2_PHASE1_V2_S1_DIFFUSIVE_SENSITIVITY_MVE_V2"
    assert cfg["schema_version"].endswith("_v2")
    assert cfg["status"] == (
        "preregistered_amendment_pending_push_no_numerical_fit_executed"
    )
    assert cfg["supersedes"]["path"] == str(BASE_PATH.relative_to(ROOT)).replace(
        "\\", "/"
    )
    assert cfg["supersedes"]["sha256"] == _sha256(BASE_PATH)
    assert cfg["supersedes"]["unchanged_fields_remain_authoritative"] is True


def test_s1_v2_amendment_keeps_s2_nominal_and_formal_count_zero() -> None:
    cfg = _yaml(AMENDMENT_PATH)
    boundary = cfg["execution_boundary"]
    identity = cfg["source_scale_identity"]

    assert boundary["formal_execution_count"] == 0
    assert boundary["formal_artifacts"] == "forbidden"
    assert boundary["production_selection"].startswith("forbidden_")
    assert boundary["may_delay_or_block_S2"] is False
    assert identity["S2_config_path"] == str(S2_PATH.relative_to(ROOT)).replace(
        "\\", "/"
    )
    assert identity["S2_config_sha256"] == _sha256(S2_PATH)
    assert cfg["runner_contract"]["result_may_change_nominal_S2"] is False


def test_s1_v2_amendment_locks_reference_optimizer_and_cauer_gates() -> None:
    cfg = _yaml(AMENDMENT_PATH)

    reference = cfg["analytic_reference_control"]
    assert reference["production_modal_terms"] == 16384
    assert reference["comparator_modal_terms"] == 32768
    assert reference["reference_discrepancy_max"] == pytest.approx(5.0e-4)

    safety = cfg["optimizer_safety"]
    assert safety["overflow_or_construction_exception"].startswith("isolate_")
    assert safety["boundary_hit"] == "ineligible"
    assert cfg["candidate_eligibility"]["single_authoritative_aggregator"] == (
        "candidate_eligible"
    )

    cauer = cfg["cauer_embedding_and_validation"]
    assert cauer["port_node"] == "resolved_active_plane_temperature_T"
    assert cauer["independent_vertical_state_count"] == "K_minus_1"
    assert cauer["duplicate_port_temperature_state"] == "forbidden"
    assert cauer["backward_euler_ledger"]["negative_controls"] == [
        "tamper_storage",
        "tamper_terminal_sink",
    ]


def test_s1_v2_output_namespace_cannot_be_formal_or_production() -> None:
    cfg = _yaml(AMENDMENT_PATH)
    outputs = cfg["outputs"]

    assert all("geophase_phase1_v2" in value for value in outputs.values())
    assert cfg["runner_contract"]["formal_ID_prefix"] == "forbidden"
    assert cfg["claim_boundary"]["forbidden_without_holdout"] == [
        "S1_is_more_physically_accurate_than_S2",
        "Qiu_diffusive_spectrum_identified",
        "S1_is_a_production_reference",
        "S1_is_a_manuscript_headline_contribution",
    ]


def test_s1_v2_machine_preregistration_points_to_the_pushed_protocol() -> None:
    cfg = _yaml(AMENDMENT_PATH)
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))

    assert prereg["schema_version"].endswith("_v2")
    assert prereg["preregistration_commit"] == (
        "15b15131fe8ee9299085d1724971c08c1ae977cf"
    )
    assert prereg["amendment_config_sha256"] == _sha256(AMENDMENT_PATH)
    assert prereg["superseded_s1_config_sha256"] == _sha256(BASE_PATH)
    assert prereg["s2_config_sha256"] == _sha256(S2_PATH)
    assert prereg["new_s1_numerical_work_before_preregistration_push"] is False
    assert prereg["formal_execution_count"] == 0
    assert prereg["formal_execution_consumed"] is False
    assert prereg["production_selection_authorized"] is False
    assert prereg["nominal_phase1v2_model"] == (
        cfg["runner_contract"]["no_holdout_requires"]["S2_remains_nominal"]
        and "S2_source_scale_preserving_local_single_rc"
    )

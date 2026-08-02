from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "geophase_phase1_e0_single_implementation_physics_validation.yaml"
MANIFEST = ROOT / "configs" / "geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml"
S2_CONFIG = ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
SOURCE_CONTRACT = ROOT / "configs" / "qiu_vo2_phase1_source_contract_v3.yaml"
EXECUTION_ADDENDUM = (
    ROOT / "configs" / "geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml"
)
CANDIDATE_IDENTITY = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "performance_repair"
    / "optimized_candidate_identity.json"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _commit_tree_if_available(commit: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{tree}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode == 0:
        return result.stdout.strip()

    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if os.environ.get("PINN_PUBLIC_CHECKOUT") == "1" and shallow == "true":
        return None
    raise AssertionError(result.stderr.strip())


def test_e0_activation_is_zero_computation_and_waits_for_fresh_authorization() -> None:
    cfg = _yaml(CONFIG)
    authority = cfg["activation_authority"]
    preflight = cfg["future_e0_preflight"]
    formal = cfg["future_formal_campaign"]

    assert cfg["task_id"] == "Q2_PHASE1_E0_SINGLE_IMPLEMENTATION_PHYSICS_VALIDATION"
    assert cfg["status"] == "activated_contract_only_waiting_fresh_e0_preflight_authorization"
    assert authority["numerical_execution_authorized"] is False
    assert authority["e0_preflight_requires_fresh_user_authorization"] is True
    assert authority["formal_campaign_requires_fresh_user_authorization"] is True
    assert authority["formal_execution_count"] == 0
    assert authority["formal_artifact_count"] == 0
    assert preflight["current_authorization"].startswith("forbidden_")
    assert preflight["maximum_wall_clock_s"] == 7200
    assert formal["current_authorization"].startswith("forbidden_")
    assert formal["formal_execution_count"] == 0
    assert cfg["activation_outputs"]["formal_or_preflight_outputs_created"] is False


def test_consumed_equivalence_routes_are_immutable_and_have_no_e0_vote() -> None:
    history = _yaml(CONFIG)["historical_route_lock"]

    assert history["strict_equivalence_v1"]["retry"] == "forbidden"
    assert history["equivalence_v2"]["retry"] == "forbidden"
    assert history["equivalence_v3"]["retry"] == "forbidden"
    assert history["equivalence_v3"]["A_B_C_vote_formed"] is False
    assert history["equivalence_v4_or_v5"] == "forbidden"


def test_single_selected_implementation_is_frozen_without_equivalence_claim() -> None:
    selection = _yaml(CONFIG)["single_implementation_selection"]
    candidate_identity = _json(CANDIDATE_IDENTITY)

    assert selection["origin_commit"] == "1ae2704f6d84a3733d9de58aa23d992aa0c471a5"
    assert selection["origin_tree"] == "d3833a4a5dd067dab72c84f15fe2f8e726bd9512"
    assert selection["origin_commit"] == candidate_identity["candidate_commit"]
    assert selection["origin_tree"] == candidate_identity["candidate_tree"]
    resolved_tree = _commit_tree_if_available(selection["origin_commit"])
    if resolved_tree is not None:
        assert selection["origin_tree"] == resolved_tree
    assert selection["frozen_candidate_identity_sha256"] == _sha256(CANDIDATE_IDENTITY)
    assert selection["implementation_equivalence_to_PR8"] == "forbidden_unassessed"
    assert selection["switching_after_any_e0_numerical_result"] == "forbidden"
    assert selection["future_PINN_residual_code_reuse"] == "forbidden"

    for item in selection["frozen_core_paths"]:
        assert _sha256(ROOT / item["path"]) == item["sha256"]


def test_existing_63_item_scientific_inventory_is_reused_without_change() -> None:
    cfg = _yaml(CONFIG)
    mapping = cfg["scientific_inventory_mapping"]
    manifest = _yaml(MANIFEST)
    authority = cfg["physics_authority"]

    assert mapping["reuse_existing_manifest_without_modification"] is True
    assert mapping["evaluation_item_count"] == manifest["total_evaluation_items"] == 63
    assert mapping["unique_execution_unit_count"] == manifest["unique_execution_units"] == 60
    assert mapping["legal_reuse_count"] == manifest["reused_evaluation_items"] == 3
    assert mapping["inventory_execution_during_activation"] == "forbidden"
    assert mapping["inventory_status"] == "planned_not_executed"
    assert authority["formal_manifest"]["sha256"] == _sha256(MANIFEST)
    assert authority["S2_config"]["sha256"] == _sha256(S2_CONFIG)
    assert authority["source_contract"]["sha256"] == _sha256(SOURCE_CONTRACT)
    assert authority["execution_addendum"]["sha256"] == _sha256(EXECUTION_ADDENDUM)
    assert _yaml(S2_CONFIG)["execution_contract"]["formal_execution_count"] == 0


def test_failure_taxonomy_separates_invalid_infrastructure_from_science() -> None:
    taxonomy = _yaml(CONFIG)["failure_taxonomy"]

    infra = taxonomy["record_schema_runner_or_environment_failure"]
    performance = taxonomy["performance_or_resource_only_failure"]
    formal = taxonomy["valid_formal_scientific_gate_failure"]
    assert infra["validity"] == "invalid"
    assert infra["claim_status"] == "forbidden"
    assert infra["scientific_vote"] is False
    assert performance["scientific_vote"] is False
    assert formal["claim_status"] == "failed_but_informative"


def test_current_authority_records_nls_terminal_without_unlocking_downstream_work() -> None:
    active = (ROOT / "docs" / "research_strategy" / "active_phase.md").read_text(encoding="utf-8")
    context = (ROOT / "CODEX_CONTEXT.md").read_text(encoding="utf-8")
    next_actions = (ROOT / "NEXT_ACTIONS.md").read_text(encoding="utf-8")

    checkpoint = "Q2_NLS_V1_QUALIFICATION_REJECTED_NO_S0"
    assert checkpoint in active
    assert checkpoint in context
    assert checkpoint in next_actions
    assert "formal_execution_count=0" in active
    assert "equivalence-v4/v5" in active
    assert "No experiment is authorized" in next_actions

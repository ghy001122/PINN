from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_project_governance",
    ROOT / "scripts" / "audit_project_governance.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_governance_audit_has_no_failed_checks() -> None:
    summary = MODULE.run_audit(write_output=False)
    assert summary["overall_status"] in {"pass", "pass_with_manual_review"}
    assert summary["failed_checks"] == []


def test_frozen_gt_hashes_and_claim_vocabulary() -> None:
    summary = MODULE.run_audit(write_output=False)
    assert summary["checks"]["frozen_gt_integrity"]["status"] == "pass"
    assert summary["checks"]["claim_vocabulary"]["status"] == "pass"
    assert summary["checks"]["claim_matrix_vocabulary"]["status"] == "pass"


def test_single_current_route_and_context_hygiene() -> None:
    summary = MODULE.run_audit(write_output=False)
    assert summary["checks"]["current_handoff"]["status"] == "pass"
    assert summary["checks"]["single_current_snapshot"]["status"] == "pass"
    assert summary["checks"]["phase_consistency"]["status"] == "pass"
    assert summary["checks"]["phase_consistency"]["active_phase_id"] == (
        "Q2_PHASE1_2P5D_REFERENCE_SOLVER"
    )
    assert summary["checks"]["delivery_contract"]["status"] == "pass"
    assert summary["checks"]["no_obsolete_current_route"]["status"] == "pass"
    assert summary["checks"]["critical_markdown_links"]["status"] == "pass"


def test_documentation_hygiene_has_no_arbitrary_size_gate() -> None:
    audit_source = (ROOT / "scripts" / "audit_project_governance.py").read_text(
        encoding="utf-8"
    )
    pipeline = (
        ROOT / "docs" / "research_strategy" / "sci_delivery_pipeline.md"
    ).read_text(encoding="utf-8")
    root_rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for obsolete in [
        "low_token_context_budget",
        "agents_chain_size",
        "context_total <= 24576",
        'len(handoff.encode("utf-8")) <= 2048',
    ]:
        assert obsolete not in audit_source
    assert "below 24 KiB" not in pipeline
    assert "do not use arbitrary byte, token, line, or file-count" in pipeline
    assert "must not use arbitrary byte, token, line, or file-count" in root_rules


def test_revision_rules_and_current_routers_are_semantically_guarded() -> None:
    summary = MODULE.run_audit(write_output=False)
    rules = summary["checks"]["revision_rules_integration"]
    assert rules["status"] == "pass"
    assert rules["expected_rule_count"] == 75
    assert rules["mapped_rule_count"] == 75
    assert rules["missing_ids"] == []
    assert rules["duplicate_ids"] == []
    assert summary["checks"]["current_router_semantics"]["status"] == "pass"


def test_archive_outputs_and_repository_safety_are_governed() -> None:
    summary = MODULE.run_audit(write_output=False)
    assert summary["checks"]["realignment_outputs"]["status"] == "pass"
    assert summary["checks"]["realignment_outputs"]["rows"] >= 1000
    assert summary["checks"]["phase0_report"]["status"] == "pass"
    assert summary["checks"]["retired_generator_guard"]["status"] == "pass"
    assert summary["checks"]["no_duplicate_active_markdown"]["status"] == "pass"
    assert summary["checks"]["final_report_template"]["status"] == "pass"
    assert summary["checks"]["workspace_routing_and_hygiene"]["status"] == "pass"
    assert summary["checks"]["local_external_asset_registry"]["status"] == "pass"
    assert summary["checks"]["phase1_contract_hardening"]["status"] == "pass"

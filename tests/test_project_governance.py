from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_project_governance", ROOT / "scripts" / "audit_project_governance.py")
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


def test_handoff_snapshot_context_budget_and_agents_hierarchy() -> None:
    summary = MODULE.run_audit(write_output=False)
    assert summary["checks"]["current_handoff"]["status"] == "pass"
    assert summary["checks"]["single_current_snapshot"]["status"] == "pass"
    assert summary["checks"]["agents_chain_size"]["status"] == "pass"
    assert summary["checks"]["no_authoritative_memorys_directory"]["status"] == "pass"
    assert summary["checks"]["low_token_context_budget"]["status"] == "pass"
    assert summary["checks"]["retired_generator_guard"]["status"] == "pass"
    assert summary["checks"]["no_duplicate_active_markdown"]["status"] == "pass"


def test_delivery_contract_and_claim_matrices_are_consistent() -> None:
    summary = MODULE.run_audit(write_output=False)
    assert summary["checks"]["delivery_contract"]["status"] == "pass"
    assert summary["checks"]["claim_matrix_vocabulary"]["status"] == "pass"
    assert summary["checks"]["final_report_template"]["status"] == "pass"

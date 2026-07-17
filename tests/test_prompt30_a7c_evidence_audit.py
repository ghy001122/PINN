from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_a7c_prompt30_evidence import build_audit


def test_a7c_machine_audit_preserves_failure_scope(tmp_path: Path) -> None:
    output = tmp_path / "audit.json"
    summary = build_audit(output)
    assert summary["audited_commit"] == "a7c108e3980953ced24d2de86ce7afc340e65a88"
    assert summary["historical_expensive_results_recomputed"] is False
    assert summary["row_counts"] == {"sid_cases": 36, "sid_bootstrap": 600}
    assert all(summary["report_json_consistency"].values())
    scientific_matches = {
        path: matched
        for path, matched in summary["working_tree_matches_a7c"].items()
        if not path.startswith(".github/workflows/")
    }
    assert all(scientific_matches.values())
    assert summary["audited_base_blob_hashes"][".github/workflows/read_only_validation.yml"] != summary["working_tree_hashes"][".github/workflows/read_only_validation.yml"]
    correction = summary["sid_scope_correction"]
    assert correction["current_preregistered_implementation_rejected"] is True
    assert correction["broad_scientific_hypothesis_permanently_falsified"] is False
    assert correction["active_now"] is False
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["claim_scope"] == "machine audit of existing a7c artifacts only"


def test_a7c_audit_has_all_required_evidence_classes(tmp_path: Path) -> None:
    summary = build_audit(tmp_path / "audit.json")
    assert summary["actually_executed"]
    assert summary["gates_passed"]
    assert summary["failed_but_informative"]
    assert summary["current_implementation_rejected"]
    assert summary["still_unvalidated"]

from __future__ import annotations

import json
from pathlib import Path

import scripts.audit_oasis_algorithms_v10 as algorithms


def test_p4_blocks_when_strict_p1_gate_fails(tmp_path: Path, monkeypatch) -> None:
    p1 = tmp_path / "p1.json"
    p1.write_text(json.dumps({"P1_gate_passed": False}), encoding="utf-8")
    monkeypatch.setattr(algorithms, "P1_JSON", p1)
    monkeypatch.setattr(algorithms, "SUMMARY_JSON", tmp_path / "algorithm.json")
    summary = algorithms.run_oasis_algorithms_v10()
    assert summary["P1_gate_passed"] is False
    assert summary["canonical_seiler_STL_status"] == "not_run_blocked"
    assert summary["positive_algorithm_claim_allowed"] is False


def test_v10_outputs_keep_claim_boundaries() -> None:
    generalization = json.loads(Path("outputs/tables/oasis_generalization_v10_summary.json").read_text(encoding="utf-8"))
    multiterminal = json.loads(Path("outputs/tables/multiterminal_yz_forward_summary.json").read_text(encoding="utf-8"))
    physical = json.loads(Path("outputs/tables/physical_semantics_v10_summary.json").read_text(encoding="utf-8"))
    assert generalization["status"] == "preflight_only"
    assert "not OASIS neural-operator" in generalization["claim_boundary"]
    assert "no positive hidden-field recovery" in multiterminal["claim_boundary"]
    assert physical["literature_shape_plausibility"]["quantitative_experimental_validation"] is False

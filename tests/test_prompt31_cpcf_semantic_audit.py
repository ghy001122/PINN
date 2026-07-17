from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_prompt31_cpcf_semantics import build_semantic_audit


def test_cpcf_semantic_audit_supersedes_scientific_vote(tmp_path: Path) -> None:
    output = tmp_path / "audit.json"
    claim = tmp_path / "claim.json"
    audit = build_semantic_audit(output, claim)
    assert audit["status"] == "implementation_contract_invalid"
    assert audit["claim_status"] == "failed_but_informative"
    assert audit["scientific_vote"] is False
    assert audit["valid_scope"] == "software/proxy mismatch diagnosis only"
    assert audit["case_accounting"] == {
        "total_case_rows": 48,
        "proxy_prediction_rows": 48,
        "proxy_only_rows": 40,
        "proxy_plus_fresh_solver_diagnostic_rows": 8,
        "fresh_solver_diagnostic_rows": 8,
        "fresh_solver_trajectory_evaluations": 48,
        "fully_direct_solver_voting_rows": 0,
        "operating_point_vote_source": "predicted_relative_error",
    }
    assert json.loads(claim.read_text(encoding="utf-8"))["scientific_vote"] is False


def test_cpcf_protocol_solver_objective_and_pareto_contracts_fail(tmp_path: Path) -> None:
    audit = build_semantic_audit(tmp_path / "audit.json", tmp_path / "claim.json")
    comparisons = {row["cpcf_protocol"]: row for row in audit["protocol_contract"]["comparisons"]}
    assert comparisons["ltp_ltd"]["contract_status"] == "equivalent"
    assert comparisons["short_pulse_to_ltp_ltd"]["contract_status"] == "protocol_contract_mismatch"
    assert comparisons["multi_pulse_to_ltp_ltd"]["contract_status"] == "protocol_contract_mismatch"
    assert audit["solver_contract"]["equivalent"] is False
    assert audit["candidate_grid_contract"]["historical_count"] == 15
    assert audit["candidate_grid_contract"]["cpcf_fresh_anchor_count"] == 5
    assert audit["objective_contract"]["equivalent"] is False
    assert audit["T_sw_prior_width_contract"]["unit_contract_mismatch"] is True
    assert audit["noise_seed_contract"]["same_distribution_seed_replication"] is False
    assert audit["bootstrap_contract"]["iid_seed_bootstrap"] is False
    assert audit["pareto_contract"]["stable_but_locked_risk_unqualified_ids"] == ["cal_010_ltp_n16", "proto_100_ltp_n16"]

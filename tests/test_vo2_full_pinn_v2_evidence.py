"""Claim-gate tests for the executed D0a/N0 v2 evidence round."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_d0a_failure_stops_fit_and_preserves_13v_seal() -> None:
    d0a = _json("outputs/tables/vo2_d0a_source_reproduction.json")
    cumulative = _json("outputs/tables/vo2_protocol_quotient_full_pinn_v2_summary.json")
    manifest = _json("data/external/vo2_zhang_2024/manifest.json")
    assert d0a["claim_status"] == "failed_but_informative"
    assert d0a["gate_passed"] is False
    assert d0a["gate_results"]["finest_time_step_convergence"] is False
    assert d0a["source_si_metrics"]["medium_vs_fine_dt_current_nrmse95"] > 0.01
    assert d0a["gate_results"]["sealed_13v_untouched"] is True
    assert manifest["sealed_member_content_read_prelock"] is False
    assert all(item["sha256"] is None for item in manifest["archive_members"]["nature_source_data"] if "13V" in item["member_name"])
    assert cumulative["d0b_d0c_d0d"] == {
        "13v_unsealed": False,
        "fit_lock_created": False,
        "status": "not_run_upstream_gate",
    }


def test_n0_contract_and_training_claims_remain_separate() -> None:
    contract = _json("outputs/tables/full_pinn_contract_v1.json")
    mve = _json("outputs/tables/full_pinn_single_seed_mve_v1.json")
    cumulative = _json("outputs/tables/vo2_protocol_quotient_full_pinn_v2_summary.json")
    assert contract["status"] == "preflight_passed"
    assert contract["contract"]["independent_log_sigma_output"] is False
    assert contract["frozen_gt_role"] == "score_only"
    assert mve["status"] == "mve_fail"
    assert mve["claim_status"] == "forbidden"
    metrics = mve["results"][0]["metrics"]
    assert metrics["port_full_trace_nrmse95"] > 0.10
    assert all(value > 0.01 for value in metrics["residual_rms"].values())
    assert cumulative["n0"]["claim_status"] == "failed_but_informative"
    assert cumulative["n0"]["full_pinn_training_claim"] == "forbidden"
    assert cumulative["n1_n2_n3"]["status"] == "not_run_upstream_gate"


def test_data_semantics_are_not_collapsed() -> None:
    d0a = _json("outputs/tables/vo2_d0a_source_reproduction.json")
    roles = d0a["evidence_semantics"]
    assert roles["source_paper_model_reproduction"] is True
    assert roles["repository_side_refit"] is False
    assert roles["repository_withheld_preregistered_cross_voltage_evaluation"] is False
    assert roles["independent_external_validation"] is False

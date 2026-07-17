import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_v3_failure_is_fail_closed_without_checkpoint_or_follow_on_runs():
    result = _json("outputs/tables/n0_cv_e_v3_seed_20260715.json")
    assert result["status"] == "failed_but_informative"
    assert result["failure_stage"] == "lbfgs_strong_wolfe_closure"
    assert result["checkpoint"] is None
    assert result["metrics"] is None
    assert result["gates"]["all_pass"] is False
    assert set(result["gates"]["checks"].values()) == {"unassessed_fail_closed"}
    assert result["balancing_arm_run"] is False
    assert result["seed_expansion_run"] is False
    assert result["sparse_anchor_run"] is False
    assert result["hyperparameter_search_run"] is False
    assert result["scientific_lock_match_after_failure"] is True


def test_v3_summary_closes_n0_and_preserves_claim_boundary():
    summary = _json("outputs/tables/n0_cv_e_v3_summary.json")
    assert summary["preflight"]["all_pass"] is True
    assert summary["claim_status"] == "failed_but_informative"
    assert summary["positive_forward_claim_allowed"] is False
    assert summary["disposition"] == "N0_final_stop_training_runtime_failure"
    assert "gamma_sub" in summary["next_single_recommendation"]


def test_v3_checkpoint_manifest_explicitly_records_absence():
    manifest = _json("outputs/tables/n0_cv_e_v3_checkpoint_manifest.json")
    assert manifest["checkpoints"] == []
    assert manifest["status"] == "no_checkpoint_runtime_failure_before_serialization"

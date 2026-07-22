from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fast_validation_does_not_fetch_full_history() -> None:
    workflow = (ROOT / ".github" / "workflows" / "read_only_validation.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" not in workflow
    assert "validate_historical_evidence_manifest.py" in workflow
    assert "test_prompt30_a7c_evidence_audit.py" not in workflow
    assert "test_validation_workflow_contract.py" in workflow
    assert "cache: pip" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout-minutes:" in workflow
    assert 'PINN_PUBLIC_CHECKOUT: "1"' in workflow


def test_full_validation_alone_verifies_historic_blobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "full_validation.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in workflow
    assert "validate_historical_evidence_manifest.py --verify-history" in workflow
    assert "cache: pip" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout-minutes:" in workflow
    assert "runs-on: [self-hosted, windows, pinn-trusted-replay]" in workflow
    assert "verify_local_replay_assets.py" in workflow
    assert "PINN_LOCAL_REPLAY_ASSET_ROOT" in workflow
    assert "RUNNER_TEMP" in workflow
    assert "audit_hermetic_replay.py" in workflow
    assert "git status --porcelain=v1 --untracked-files=all" in workflow
    assert "git diff --exit-code" in workflow
    assert "run_gt_v1_acceptance.py" not in workflow

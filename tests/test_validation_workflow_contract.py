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
    assert "git diff --exit-code" in workflow
    assert "scripts/run_geophase_phase1_reference.py" not in workflow


def test_fast_validation_covers_phase1_checkpoint_a_and_authority_paths() -> None:
    workflow = (ROOT / ".github" / "workflows" / "read_only_validation.yml").read_text(encoding="utf-8")
    required_tests = (
        "tests/test_geophase_phase1_solver.py",
        "tests/test_geophase_phase1_checkpoint_a_evidence.py",
        "tests/test_geophase_phase1_vertical_repair_preregistration.py",
        "tests/test_geophase_phase1_vertical_repair.py",
        "tests/test_geophase_phase1_vertical_repair_evidence.py",
    )
    for test_path in required_tests:
        assert test_path in workflow

    required_trigger_paths = (
        "README.md",
        "docs/method_equations.md",
        "docs/codex_reports/**",
        "LIVE_WORKSPACE.md",
        "EXPERIMENT_REGISTRY.md",
        "DATASET_REGISTRY.md",
        "FIGURE_REGISTRY.md",
    )
    for trigger_path in required_trigger_paths:
        assert workflow.count(f'- "{trigger_path}"') == 2


def test_full_validation_alone_verifies_historic_blobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "full_validation.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in workflow
    assert "validate_historical_evidence_manifest.py --verify-history" in workflow
    assert "cache: pip" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "timeout-minutes:" in workflow
    assert "runs-on: [self-hosted, windows, pinn-trusted-replay]" in workflow
    assert "verify_local_replay_assets.py" in workflow
    assert "run_gt_v1_acceptance.py" not in workflow

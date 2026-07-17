from __future__ import annotations

from scripts.validate_historical_evidence_manifest import DEFAULT_MANIFEST, load_manifest, validate_manifest


def test_historical_evidence_manifest_current_artifacts_are_locked() -> None:
    result = validate_manifest(DEFAULT_MANIFEST, verify_history=False)
    assert result["all_passed"] is True
    assert result["entry_count"] >= 20
    assert result["current_check_count"] < result["entry_count"]
    assert result["history_check_count"] == 0


def test_historical_evidence_manifest_has_claim_scope_and_full_ids() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    for entry in manifest["entries"]:
        assert len(entry["historic_commit"]) == 40
        assert len(entry["git_blob_oid"]) == 40
        assert len(entry["sha256"]) == 64
        assert entry["claim_scope"].strip()

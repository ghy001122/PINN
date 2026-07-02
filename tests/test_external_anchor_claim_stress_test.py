from __future__ import annotations

from pathlib import Path

from scripts.build_external_anchor_claim_stress_test import build_external_anchor_claim_stress_test


def test_external_anchor_claim_stress_matrix(tmp_path: Path) -> None:
    md = tmp_path / "matrix.md"
    summary_path = tmp_path / "summary.json"
    summary = build_external_anchor_claim_stress_test(md, summary_path)
    text = md.read_text(encoding="utf-8")
    assert summary["num_claims"] >= 6
    assert summary["all_claims_have_limitations"] is True
    assert summary["all_claims_have_forbidden_overclaims"] is True
    assert "synthetic numerical digital-twin" in text
    assert "experimental" in text
    assert summary_path.exists()

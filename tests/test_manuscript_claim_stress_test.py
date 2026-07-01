from __future__ import annotations

import json
from pathlib import Path

from scripts.build_manuscript_claim_stress_test import build_claim_stress_test


def test_manuscript_claim_stress_test_smoke(tmp_path: Path) -> None:
    md = tmp_path / "claim_matrix.md"
    summary_path = tmp_path / "claim_summary.json"
    summary = build_claim_stress_test(md, summary_path)
    assert summary["num_claims"] >= 7
    assert summary["all_claims_have_limitations"] is True
    assert summary["all_claims_have_forbidden_overclaims"] is True
    text = md.read_text(encoding="utf-8")
    assert "synthetic numerical digital-twin benchmark" in text
    assert "Sparse port data uniquely recover" in text
    saved = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved["num_claims"] == summary["num_claims"]

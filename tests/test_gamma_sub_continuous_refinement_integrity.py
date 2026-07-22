from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_gamma_sub_continuous_refinement_integrity import audit


ROOT = Path(__file__).resolve().parents[1]


def test_committed_summary_matches_committed_case_rows() -> None:
    result = audit(root=ROOT)
    assert result["all_passed"] is True
    assert result["row_count"] == 36
    assert result["scientific_forward_runs"] == 0
    assert result["figure_regenerated"] is False


def test_integrity_audit_rejects_tampered_summary(tmp_path: Path) -> None:
    source = ROOT / "outputs/tables/gamma_sub_continuous_refinement_summary.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["rows"][0]["continuous_refined_relative_error"] += 0.1
    tampered = tmp_path / "summary.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    result = audit(
        root=ROOT,
        summary_path=tampered,
        cases_path=ROOT / "outputs/tables/gamma_sub_continuous_refinement_cases.csv",
    )
    assert result["all_passed"] is False
    assert "row_numeric:0:continuous_refined_relative_error" in result["failures"]

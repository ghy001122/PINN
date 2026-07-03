from __future__ import annotations

from scripts.build_reviewer_defense_matrix import QUESTIONS, build_reviewer_defense_matrix


def test_reviewer_defense_matrix_covers_required_questions() -> None:
    out = build_reviewer_defense_matrix()
    text = out.read_text(encoding="utf-8")
    assert len(QUESTIONS) == 13
    required = ["black-box", "full hidden fields", "T_sw", "0.1 K", "F-SPS", "external-curve", "quasi-2D", "phase-transition stiffness", "phase-field inverse"]
    for item in required:
        assert item in text
    assert "synthetic numerical digital-twin benchmark" in text

from __future__ import annotations

from pathlib import Path

from scripts.build_reviewer_defense_matrix import ALLOWED_STATUSES, OUT, QUESTIONS, build_reviewer_defense_matrix


def test_reviewer_defense_matrix_covers_locked_questions_without_tracked_side_effect(tmp_path: Path) -> None:
    before = OUT.read_bytes()
    out = build_reviewer_defense_matrix(tmp_path / "reviewer_defense.md")
    text = out.read_text(encoding="utf-8")
    assert OUT.read_bytes() == before
    assert len(QUESTIONS) == 17
    required = [
        "black-box",
        "full hidden fields",
        "gamma_sub",
        "0.1 K",
        "observation count",
        "Figure 5",
        "external-curve",
        "P1",
        "P2",
        "rank 1 to 3",
        "STL",
        "across materials",
    ]
    for item in required:
        assert item in text
    assert "synthetic numerical digital-twin" in text
    assert "field-anchored" not in text or "sparse-port-only" not in text
    assert {row[2] for row in QUESTIONS} <= ALLOWED_STATUSES
    for status in ALLOWED_STATUSES:
        assert f"`{status}`" in text
from __future__ import annotations

from pathlib import Path

import pytest

from pinnpcm.audit.hermetic_replay import evaluate_facts, normalize_required_paths


def test_hermetic_contract_fails_closed_on_any_missing_fact() -> None:
    facts = {
        "actual_head_matches_expected": True,
        "head_is_detached": False,
        "status_before_equals_status_after": True,
    }
    result = evaluate_facts(facts)
    assert result["all_passed"] is False
    assert result["status"] == "fail"
    assert result["failures"] == ["head_is_detached"]


def test_required_checkout_paths_reject_escape_and_absolute_paths() -> None:
    assert normalize_required_paths(["configs/a.yaml", "outputs/tables/a.json"]) == (
        "configs/a.yaml",
        "outputs/tables/a.json",
    )
    with pytest.raises(ValueError):
        normalize_required_paths([])
    with pytest.raises(ValueError):
        normalize_required_paths(["../outside.json"])
    with pytest.raises(ValueError):
        normalize_required_paths([str(Path.cwd().anchor + "outside.json")])

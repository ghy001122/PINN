"""Fail-closed semantic lock for the invalid first E1F formal execution."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_first_e1f_vote_is_invalid_and_cannot_authorize_downstream_work() -> None:
    payload = json.loads(
        (ROOT / "outputs/tables/e1f_semantic_amendment.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["original_formal_status_superseded_by"] == (
        "implementation_contract_invalid"
    )
    assert payload["scientific_vote_from_original_run"] is False
    assert payload["effective_coordinate_preflight_authorized_from_original_run"] is False
    assert payload["source_equation_defect"]["implemented_term"].startswith("atanh")
    assert payload["holdout_digitization_defect"][
        "formal_holdout_nrmse_scientific_vote"
    ] is False
    correction = payload["required_correction_contract"]
    assert correction["parameters_unchanged"] is True
    assert correction["gates_unchanged"] is True
    assert correction["curve_ids_unchanged"] is True
    assert correction["deterministic_legend_geometry_exclusion_only"] is True

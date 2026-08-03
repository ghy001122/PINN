from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_exact_condensed_v2_d0 import (
    SCHEMA_VERSION,
    explicit_central_jacobian,
    finite_difference_base_step,
    select_jv_candidate,
    verify_frozen_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "geophase_exact_condensed_v2_d0.yaml"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_d0_contract_is_one_replay_nonvoting_and_content_addressed() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["schema_version"] == SCHEMA_VERSION
    identity = config["identity"]
    assert identity["diagnostic_replay_count"] == 1
    assert identity["scientific_vote"] is False
    assert identity["formal_execution_count"] == 0
    assert identity["proposed_solver_identity_created_only_after_d0_pass"] is True
    assert config["scope"]["old_b2_rerun_or_resume"] == "forbidden"
    assert config["scope"]["v1_solver_modification"] == "forbidden"
    verified = verify_frozen_inputs(config)
    assert len(verified) == len(config["frozen_inputs"])
    for item in config["frozen_inputs"]:
        assert _sha256(ROOT / item["path"]) == item["sha256"]


def test_d0_fixed_sets_are_exact_and_not_result_selected() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    diagnostic = config["diagnostic"]
    assert diagnostic["source_case_id"] == "B2-ORIGINAL-S1-DT10p0NS"
    assert diagnostic["jv_multipliers"] == [
        0.125,
        0.25,
        0.5,
        1.0,
        2.0,
        4.0,
        8.0,
    ]
    assert diagnostic["line_profile_exponents"] == list(range(21))
    assert diagnostic["dyadic_root_dt_ns"] == [
        10.0,
        5.0,
        2.5,
        1.25,
        0.625,
        0.3125,
        0.15625,
        0.0390625,
        0.009765625,
        0.0048828125,
    ]


def test_explicit_central_jacobian_recovers_a_linear_operator() -> None:
    matrix = np.asarray(
        [[3.0, -1.0, 0.5], [2.0, 4.0, -2.0], [-1.0, 0.25, 5.0]]
    )
    offset = np.asarray([0.2, -0.3, 0.4])
    point = np.asarray([2.0, -1.0, 0.5])
    residual = matrix @ point + offset
    step = finite_difference_base_step(point, residual)
    observed = explicit_central_jacobian(
        lambda values: matrix @ values + offset, point, step
    )
    assert np.allclose(observed, matrix, rtol=2.0e-7, atol=2.0e-7)


def test_jv_selection_prefers_passing_forward_then_smallest_median() -> None:
    candidates = [
        {
            "scheme": "central",
            "multiplier": 1.0,
            "median_relative_error": 1.0e-8,
            "maximum_relative_error": 2.0e-8,
            "passed": True,
        },
        {
            "scheme": "forward",
            "multiplier": 0.5,
            "median_relative_error": 4.0e-4,
            "maximum_relative_error": 8.0e-4,
            "passed": True,
        },
        {
            "scheme": "forward",
            "multiplier": 1.0,
            "median_relative_error": 2.0e-4,
            "maximum_relative_error": 9.0e-4,
            "passed": True,
        },
    ]
    selected = select_jv_candidate(candidates)
    assert selected is not None
    assert selected["scheme"] == "forward"
    assert selected["multiplier"] == 1.0


def test_jv_selection_fails_closed_when_no_candidate_passes() -> None:
    assert (
        select_jv_candidate(
            [
                {
                    "scheme": "forward",
                    "multiplier": 1.0,
                    "median_relative_error": 2.0e-3,
                    "maximum_relative_error": 2.0e-2,
                    "passed": False,
                }
            ]
        )
        is None
    )

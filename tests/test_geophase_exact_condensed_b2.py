from __future__ import annotations

import json

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_exact_condensed_b2 import (
    build_b2_root_cases,
    load_b2_case_state,
    verify_frozen_inputs,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT


CONFIG = ROOT / "configs/geophase_exact_condensed_s0_c01_c06_r1.yaml"
TERMINAL_SUMMARY = (
    ROOT
    / "outputs/tables/geophase_exact_condensed/b2/"
    "B2-EXACT-CONDENSED-20260803-V1/b2_summary.json"
)


def _config():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_b2_matrix_is_mechanically_frozen_at_24_unique_roots() -> None:
    cases = build_b2_root_cases(_config())
    assert len(cases) == 24
    assert len({case.case_id for case in cases}) == 24
    assert sum("ORIGINAL" in case.case_id for case in cases) == 14
    assert sum("SMALL" in case.case_id for case in cases) == 6
    assert sum("HARDEST-L1" in case.case_id for case in cases) == 2
    assert sum(case.spatial_level == 2 for case in cases) == 1
    assert sum(case.spatial_level == 4 for case in cases) == 1
    assert {case.wall_time_s for case in cases if case.spatial_level == 1} == {
        60.0
    }
    assert next(case for case in cases if case.spatial_level == 2).wall_time_s == 180
    assert next(case for case in cases if case.spatial_level == 4).wall_time_s == 300


def test_nested_states_use_conservative_piecewise_constant_prolongation() -> None:
    cases = build_b2_root_cases(_config())
    level1 = load_b2_case_state(
        next(case for case in cases if case.case_id.startswith("B2-HARDEST-L1"))
    )
    for level in (2, 4):
        case = next(case for case in cases if case.spatial_level == level)
        state = load_b2_case_state(case)
        assert state.temperature_K.shape == (
            level1.temperature_K.shape[0] * level,
            level1.temperature_K.shape[1] * level,
        )
        assert np.array_equal(
            state.temperature_K,
            np.repeat(np.repeat(level1.temperature_K, level, axis=0), level, axis=1),
        )
        assert np.array_equal(
            state.conductive_state,
            np.repeat(
                np.repeat(level1.conductive_state, level, axis=0), level, axis=1
            ),
        )
        assert np.array_equal(
            state.branch_memory,
            np.repeat(np.repeat(level1.branch_memory, level, axis=0), level, axis=1),
        )
        assert state.time_s == level1.time_s
        assert state.device_voltage_V == level1.device_voltage_V


def test_b2_config_keeps_frozen_hashes_and_nonvoting_comparator() -> None:
    config = _config()
    verified = verify_frozen_inputs(config)
    assert len(verified) == len(config["frozen_inputs"])
    assert config["b2"]["required_passes"] == 24
    assert config["b2"]["nls_comparator"]["scope"] == "original_14_only"
    assert config["b2"]["nls_comparator"]["voting"] is False
    assert config["identity"]["fresh_s0_formal_execution_count"] == 0
    assert config["identity"]["scientific_vote"] is False


def test_first_b2_case_uses_frozen_replay_without_running_a_root() -> None:
    case = build_b2_root_cases(_config())[0]
    replay = json.loads((ROOT / case.source_path).read_text(encoding="utf-8"))["replay"]
    state = load_b2_case_state(case)
    assert case.dt_s == 10.0e-9
    assert case.input_voltage_V == float(replay["full_input_voltage_V"])
    assert state.time_s == float(replay["previous_state"]["time_s"])
    assert np.array_equal(
        state.temperature_K,
        np.asarray(replay["previous_state"]["temperature_K"], dtype=float),
    )


def test_b2_terminal_result_is_valid_fail_fast_without_downstream_unlock() -> None:
    summary = json.loads(TERMINAL_SUMMARY.read_text(encoding="utf-8"))
    assert summary["disposition"] == "B2_REDUCED_ROOT_VALID_FAIL"
    assert summary["lifecycle_state"] == "executed"
    assert summary["claim_status"] == "failed_but_informative"
    assert summary["scientific_vote"] is False
    assert summary["planned_roots"] == 24
    assert summary["executed_roots"] == 1
    assert summary["passed_roots"] == 0
    assert summary["unassessed_roots"] == 23

    failure = summary["first_failure"]
    telemetry = failure["telemetry"]
    assert failure["validity"] == "valid"
    assert failure["status"] == "VALID_FAIL"
    assert failure["failure_code"] == "ARMIJO_LINE_SEARCH_FAILURE"
    assert telemetry["reduced_residual_inf"] > 1.0e-8
    assert telemetry["full_scaled_residual_inf"] > 1.0e-8
    assert telemetry["auxiliary_scaled_residual_inf"] <= 1.0e-12
    assert telemetry["full_fixed_point_defect_inf"] is None
    assert _config()["identity"]["fresh_s0_formal_execution_count"] == 0

    workflow = (ROOT / ".github/workflows/read_only_validation.yml").read_text(
        encoding="utf-8"
    )
    assert "tests/test_geophase_exact_condensed_solver.py" in workflow
    assert "tests/test_geophase_exact_condensed_b2.py" in workflow

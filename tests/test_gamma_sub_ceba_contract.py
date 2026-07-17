from __future__ import annotations

import numpy as np

from scripts.audit_gamma_sub_multi_protocol_recoverability import _loss_from_series
from scripts.run_gamma_sub_ceba import (
    DEFAULT_CONFIG,
    _candidate_cache_key,
    _find_bracket,
    _load_config,
    _target_cache_key,
    ceba_objective,
    waveform_contract,
)


def test_ceba_preregistered_scope_and_budget_are_bounded() -> None:
    config = _load_config(DEFAULT_CONFIG)
    assert list(config["protocols"]) == ["triangle", "ltp_ltd"]
    assert len(config["parity"]["anchors"]) == 6
    assert len(config["inverse"]["gamma_candidates"]) == 15
    assert config["inverse"]["objective"] == {"w_g": 1.0, "w_i": 0.5}
    assert float(config["inverse"]["heat_residual_weight"]) == 0.0
    assert int(config["budget"]["maximum_unique_solver_trajectories"]) == 60
    assert int(config["budget"]["maximum_workers"]) == 2
    assert float(config["budget"]["maximum_wall_time_minutes"]) == 30.0
    assert int(config["pilot"]["maximum_additional_base_target_trajectories"]) == 12
    assert int(config["pilot"]["refinement"]["maximum_additional_trajectories"]) == 10


def test_ceba_cache_keys_exclude_observation_noise_and_seed() -> None:
    candidate = _candidate_cache_key("wave", 4.5e8, "solver")
    target = _target_cache_key("wave", 0.2, "solver")
    assert candidate == "wave|gamma_sub=450000000|solver"
    assert target == "wave|delta_T_sw_K=0.20000000000000001|solver"
    for forbidden in ("observation", "noise", "seed"):
        assert forbidden not in candidate
        assert forbidden not in target


def test_ceba_objective_is_independent_but_numerically_equal_to_source() -> None:
    pred_g = np.asarray([1.0, 2.1, 2.9])
    pred_i = np.asarray([0.5, 0.7, 0.9])
    target_g = np.asarray([1.1, 2.0, 3.0])
    target_i = np.asarray([0.4, 0.8, 1.0])
    weights = {"w_g": 1.0, "w_i": 0.5}
    local = ceba_objective(pred_g, pred_i, target_g, target_i, weights)
    source = _loss_from_series(pred_g, pred_i, target_g, target_i, weights)
    assert local == source


def test_ceba_waveforms_are_exact_and_distinct() -> None:
    config = _load_config(DEFAULT_CONFIG)
    triangle = waveform_contract(config, "triangle")
    ltp_ltd = waveform_contract(config, "ltp_ltd")
    assert triangle["t_max_s"] == 3.0e-3
    assert ltp_ltd["t_max_s"] == 15.0e-3
    assert triangle["waveform_sha256"] != ltp_ltd["waveform_sha256"]
    assert ltp_ltd["pulse_count"] == 12


def test_ceba_bracket_requires_direct_pass_below_and_failure_above() -> None:
    bracket = _find_bracket(
        {
            0.0: {"passes_locked_gate": True},
            0.5: {"passes_locked_gate": True},
            1.0: {"passes_locked_gate": False},
            2.0: {"passes_locked_gate": False},
        }
    )
    assert bracket == (0.5, 1.0)
    assert _find_bracket({0.0: {"passes_locked_gate": True}, 2.0: {"passes_locked_gate": True}}) is None

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from scripts.run_gamma_sub_scis import (
    CEBA_IMMUTABLE_PATHS,
    DEFAULT_CONFIG,
    CacheMissStop,
    CacheOnlyTrajectoryStore,
    _load_yaml,
    _resolve,
    _sha256_file,
    cache_preflight,
    expand_seed_block,
    finite_sample_quantile,
    infer_scis,
)

ROOT = Path(__file__).resolve().parents[1]


def test_scis_scope_seeds_and_gates_are_preregistered() -> None:
    config = _load_yaml(DEFAULT_CONFIG)
    assert config["stage_id"] == "M32_SCIS"
    assert config["protocols"] == ["triangle", "ltp_ltd"]
    assert config["observation_counts"] == [8, 32]
    assert config["noise_levels"] == [0.02, 0.0]
    assert len(config["candidate_grid"]["gamma_sub"]) == 15
    assert float(config["calibration"]["alpha"]) == 0.10
    assert float(config["inference"]["relative_radius"]) == 0.15
    assert int(config["gates"]["new_ode_evaluations_maximum"]) == 0
    assert int(config["gates"]["pinn_training_runs_maximum"]) == 0
    seeds = {name: set(expand_seed_block(block)) for name, block in config["seeds"].items()}
    assert len(seeds["calibration"]) >= 50
    assert len(seeds["heldout"]) >= 50
    assert seeds["discovery"].isdisjoint(seeds["calibration"])
    assert seeds["discovery"].isdisjoint(seeds["heldout"])
    assert seeds["calibration"].isdisjoint(seeds["heldout"])


def test_finite_sample_quantile_uses_locked_one_based_rank() -> None:
    value, rank = finite_sample_quantile(list(range(50)), alpha=0.10)
    assert rank == 46
    assert value == 45.0
    value_small, rank_small = finite_sample_quantile([3.0, 1.0], alpha=0.10)
    assert rank_small == 2
    assert value_small == 3.0


def test_scis_inference_signature_and_decision_do_not_accept_truth() -> None:
    assert "true_gamma" not in inspect.signature(infer_scis).parameters
    thresholds = {1.0: 0.11, 2.0: 0.11, 4.0: 0.11}
    result = infer_scis(
        objectives=[0.1, 0.0, 0.3],
        candidate_grid=[1.0, 2.0, 4.0],
        candidate_thresholds=thresholds,
        relative_radius=0.15,
    )
    assert result["gamma_hat"] == 2.0
    assert result["set_members"] == [1.0, 2.0]
    assert result["certificate_acceptance"] is False
    assert result["abstention_refusal"] is True


def test_scis_candidate_grid_deletion_is_an_explicit_decision_sensitivity() -> None:
    full = infer_scis(
        objectives=[0.0, 0.01, 0.015],
        candidate_grid=[1.0, 1.1, 9.0],
        candidate_thresholds={1.0: 0.1, 1.1: 0.1, 9.0: 0.1},
        relative_radius=0.15,
    )
    reduced = infer_scis(
        objectives=[0.0, 0.01],
        candidate_grid=[1.0, 1.1],
        candidate_thresholds={1.0: 0.1, 1.1: 0.1},
        relative_radius=0.15,
    )
    assert full["certificate_acceptance"] is False
    assert reduced["certificate_acceptance"] is True


def test_scis_cache_preflight_is_complete_and_zero_solver() -> None:
    payload = cache_preflight(DEFAULT_CONFIG, write_output=False)
    assert payload["status"] == "pass"
    assert payload["all_required_entries_valid"] is True
    assert payload["unique_trajectory_count"] == payload["expected_unique_trajectory_count"] == 36
    assert payload["new_ode_evaluations"] == 0
    assert payload["pinn_training_runs"] == 0
    assert payload["external_13v_accessed"] is False
    source = (ROOT / "scripts/run_gamma_sub_scis.py").read_text(encoding="utf-8")
    assert "simulate_with_overrides" not in source


def test_scis_cache_miss_is_a_hard_stop_without_fallback(tmp_path: Path) -> None:
    config = _load_yaml(DEFAULT_CONFIG)
    config["source_contract"]["trajectory_cache"] = str(tmp_path)
    store = CacheOnlyTrajectoryStore(config)
    with pytest.raises(CacheMissStop, match="solver fallback forbidden"):
        store.load("candidate", "triangle", 4.5e8)


def test_scis_preregistration_locks_unmodified_ceba_hashes() -> None:
    prereg = json.loads((ROOT / "outputs/tables/gamma_sub_scis_preregistration.json").read_text(encoding="utf-8"))
    assert prereg["no_scis_scoring_results"] is True
    assert prereg["no_solver_run"] is True
    assert prereg["new_ode_evaluations"] == 0
    assert prereg["pinn_training_runs"] == 0
    assert prereg["seeds_pairwise_disjoint"] is True
    assert set(prereg["ceba_immutable_hashes"]) == set(CEBA_IMMUTABLE_PATHS)
    for path, expected in prereg["ceba_immutable_hashes"].items():
        assert _sha256_file(_resolve(path)) == expected

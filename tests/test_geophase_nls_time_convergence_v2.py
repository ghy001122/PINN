from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.evaluation.geophase_nls_time_convergence_v2 import (
    CONFIG_PATH,
    _heldout_specs,
    _profile_specs,
    _without_allowed_overlay_fields,
    compare_time_levels,
    derived_coordinates,
    load_contract,
    qualification_scientific_config,
    richardson_metric,
    verify_frozen_inputs,
    write_heldout_unlock,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import resolved_s2_config
from pinnpcm.physics.geophase_s2_thermal import effective_vo2_closure_from_v2_config


def test_frozen_pr27_atoms_and_t8_overlay_parity() -> None:
    contract = load_contract(CONFIG_PATH)
    verified = verify_frozen_inputs(contract)
    paths = {item["path"] for item in verified}
    assert "outputs/tables/geophase_b3v2_solution_level/development/workers/transition_12p5V_nls_v1_T1.json" in paths
    assert "outputs/tables/geophase_b3v2_solution_level/development/workers/transition_12p5V_nls_v1_T2.fields.npz" in paths
    base = qualification_scientific_config(contract, 4)
    t8 = qualification_scientific_config(contract, 8)
    assert base["reference_solver"]["formal_time_step_divisors"] == [1, 2, 4]
    assert t8["reference_solver"]["formal_time_step_divisors"] == [1, 2, 4, 8]
    assert t8["qualification_overlay_identity"] == "nls_reference_time_convergence_t8_qualification_overlay_v1"
    assert _without_allowed_overlay_fields(base) == _without_allowed_overlay_fields(t8)


def test_transition_temperature_and_production_log_conductivity() -> None:
    scientific = resolved_s2_config()
    closure = effective_vo2_closure_from_v2_config(scientific)
    temperature = np.asarray([[[330.0, 340.0]]])
    state = np.asarray([[[0.2, 0.8]]])
    branch = np.asarray([[[-1.0, 1.0]]])
    result = derived_coordinates(
        {
            "temperature_K": temperature,
            "conductive_state": state,
            "branch_memory": branch,
        },
        scientific,
    )
    expected_tc = 0.5 * (1.0 + branch) * closure.T_c_up_K + 0.5 * (
        1.0 - branch
    ) * closure.T_c_down_K
    expected_log_sigma = np.log(closure.conductivity_S_m(temperature, state))
    assert np.array_equal(result["transition_temperature_K"], expected_tc)
    assert np.array_equal(result["log_conductivity"], expected_log_sigma)


def test_area_mask_and_derived_metrics_use_active_vo2_only() -> None:
    contract = load_contract(CONFIG_PATH)
    prior = Path("outputs/tables/geophase_b3v2_solution_level/development/workers")
    t1 = __import__("json").loads((prior / "transition_12p5V_nls_v1_T1.json").read_text(encoding="utf-8"))
    t2 = __import__("json").loads((prior / "transition_12p5V_nls_v1_T2.json").read_text(encoding="utf-8"))
    comparison = compare_time_levels(t1, t2, contract)
    assert comparison["time_grid_equal"]
    assert comparison["voting_metrics"]["transition_temperature_rmse_K"] >= 0.0
    assert comparison["voting_metrics"]["log_conductivity_rmse"] >= 0.0
    assert comparison["report_only"]["raw_fields"]["conductive_state"]["rmse"] > 0.0
    assert comparison["raw_reversal_voting"] is False


def test_richardson_zero_monotonic_nonmonotonic_and_p07_boundary() -> None:
    contract = load_contract(CONFIG_PATH)
    zero = richardson_metric(0.0, 0.0, 0.05, contract)
    assert zero["floor_resolved"] and zero["passed"]
    monotonic = richardson_metric(0.04, 0.02, 0.05, contract)
    assert monotonic["observed_order"] == pytest.approx(1.0)
    assert monotonic["order_pass"]
    nonmonotonic = richardson_metric(0.02, 0.03, 0.05, contract)
    assert not nonmonotonic["order_pass"]
    e12 = 0.04
    e24 = e12 / (2.0**0.7)
    boundary = richardson_metric(e12, e24, 0.05, contract)
    assert boundary["observed_order"] == pytest.approx(0.7)
    assert boundary["order_pass"]


def test_heldout_is_nls_only_and_unlocks_once(tmp_path: Path) -> None:
    contract = load_contract(CONFIG_PATH)
    selected = {
        "final_state": {
            "time_s": 2.0e-6,
            "temperature_K": [[330.0]],
            "conductive_state": [[0.4]],
            "branch_memory": [[-1.0]],
            "device_voltage_V": 0.0,
        }
    }
    specs = _heldout_specs(contract, selected, 4)
    assert len(specs) == 6
    assert {spec["solver"] for _, spec in specs} == {"nls_v1"}
    assert {spec["time_divisor"] for _, spec in specs} == {1, 2, 4}
    marker = tmp_path / "heldout_unlock.json"
    write_heldout_unlock(
        marker,
        contract_hash="a" * 64,
        anchor_commit="b" * 40,
        selected_divisor=4,
        unlocked_at_utc="2026-08-04T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="already"):
        write_heldout_unlock(
            marker,
            contract_hash="a" * 64,
            anchor_commit="b" * 40,
            selected_divisor=4,
            unlocked_at_utc="2026-08-04T00:00:01+00:00",
        )


def test_transition_centered_profiles_use_frozen_state_and_matrix() -> None:
    contract = load_contract(CONFIG_PATH)
    specs = _profile_specs(contract, 4)
    assert len(specs) == 18
    transition = [spec for label, spec in specs if label.startswith("transition_centered_12p5V")]
    assert len(transition) == 9
    assert all("initial_state" in spec and "initial_state_mode" not in spec for spec in transition)
    assert all(float(spec["initial_state"]["time_s"]) == pytest.approx(1.0510421196050138e-6) for spec in transition)
    assert all(float(spec["final_time_s"]) > float(spec["initial_state"]["time_s"]) for spec in transition)


def test_nan_inf_and_missing_artifact_fail_closed(tmp_path: Path) -> None:
    scientific = resolved_s2_config()
    fields = {
        "temperature_K": np.asarray([[[np.nan]]]),
        "conductive_state": np.asarray([[[0.5]]]),
        "branch_memory": np.asarray([[[0.0]]]),
    }
    with pytest.raises(ValueError, match="NaN or Inf"):
        derived_coordinates(fields, scientific)
    contract = load_contract(CONFIG_PATH)
    missing = {
        "validity": "valid",
        "local_pass": True,
        "field_artifact": {
            "path": str(tmp_path / "missing.npz"),
            "sha256": "0" * 64,
        },
    }
    with pytest.raises((FileNotFoundError, ValueError)):
        compare_time_levels(missing, deepcopy(missing), contract)

"""Fixed diagnostic-set and gate-path tests for N0-R."""

from __future__ import annotations

import numpy as np
import yaml

from pinnpcm.pinn.n0_diagnostics import (
    evaluate_repair_gates,
    fixed_points_content_sha256,
    generate_fixed_points,
)


def _config() -> dict[str, object]:
    with open("configs/full_pinn_n0_repair_v2.yaml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_fixed_points_are_reproducible_and_train_eval_are_disjoint() -> None:
    first = generate_fixed_points(_config())
    second = generate_fixed_points(_config())
    assert fixed_points_content_sha256(first) == fixed_points_content_sha256(second)
    for domain in ("left", "right"):
        train = {tuple(row) for row in first[f"train_{domain}_stage_100"]}
        evaluation = {tuple(row) for row in first[f"eval_{domain}"]}
        assert train.isdisjoint(evaluation)
        assert np.all(first[f"train_{domain}_stage_100"][:, 0] > 0.0)
        assert np.all(first[f"train_{domain}_stage_100"][:, 0] < 1.0)
    assert np.all(first["near_transition_left"][:, 1] >= 0.35)
    assert np.all(first["near_transition_left"][:, 1] <= 0.65)


def test_gate_evaluation_cannot_hide_one_failed_residual_or_seed_metric() -> None:
    config = _config()
    metrics = {
        "port_full_trace_nrmse95": 0.05,
        "heldout_residual_rms": {"r_phi": 0.001, "r_c": 0.011, "r_T": 0.001, "r_m": 0.001},
        "field_score_only_nrmse95": {key: 0.10 for key in ("phi", "c_v", "T", "m", "sigma")},
        "interface_state_rms": {key: 0.01 for key in ("phi", "c_v", "T", "m")},
        "interface_flux_rms": {key: 0.01 for key in ("current", "heat", "defect")},
        "boundary_rms": {
            "phi_left": 0.0,
            "phi_right": 0.0,
            "defect_left": 0.01,
            "defect_right": 0.01,
            "heat_left": 0.01,
            "heat_right": 0.01,
        },
        "terminal_current_conservation_normalized_error": 0.001,
        "global_energy_account_normalized_imbalance": 0.01,
        "finite_outputs": True,
        "physical_state_bounds": True,
    }
    gate = evaluate_repair_gates(metrics, config)
    assert gate["checks"]["heldout_residuals"] is False
    assert gate["all_pass"] is False

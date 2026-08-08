from __future__ import annotations

from dataclasses import replace
import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.current_clamp.cc_b_patterned_branch_mve import (
    NUMERIC_STOP,
    PatternedContract,
    _analytic_fi_scaled_per_A,
    _budget_check,
    _write_rows,
    _write_terminal,
    augmented_operator_jv_from_state,
    build_model,
    field_gradient_fractions,
    load_patterned_contract,
    mass_rms,
    mirror_pair_error_K,
    orient_transverse_mode,
    patterned_amplitude_K,
    patterned_seed_temperature,
    reflect_y,
    EquilibriumTrace,
    solve_equilibrium_with_trace,
    solve_fold_toy_arclength,
    solve_pitchfork_toy_amplitude,
)
from pinnpcm.current_clamp.cc_b_solver import solve_cc_b_equilibrium


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_cc_b_patterned_branch_decision_mve_v1.yaml"


def _contract():
    return load_patterned_contract(CONFIG, repository_root=ROOT)


def test_contract_freezes_scope_and_zero_legacy_counters():
    contract = _contract()
    assert contract.raw["scope"]["critical_brackets_A"] == {
        "heating": [2.0e-4, 2.5e-4],
        "cooling": [1.5e-4, 2.0e-4],
    }
    assert contract.raw["branch_switch"]["amplitude_fractions"] == [
        0.05,
        0.10,
        0.20,
        0.40,
    ]
    assert contract.raw["formal_execution_count"] == 0
    assert contract.raw["cc_b_matrix_launch_count"] == 0


def test_solver_recorder_disabled_enabled_numerical_parity():
    contract = _contract()
    model = build_model(contract, branch="heating", current_A=2.0e-4, spatial_level=1)
    initial = np.full(model.grid.shape, 331.6091013039466)
    baseline = solve_cc_b_equilibrium(model, initial_temperature_K=initial)
    events: list[dict] = []
    trace = EquilibriumTrace(rows=[])
    recorded = solve_equilibrium_with_trace(model, initial, trace)
    events = trace.rows
    assert baseline.success and recorded.success
    assert np.array_equal(baseline.temperature_K, recorded.temperature_K)
    assert baseline.last_scaled_update_inf == recorded.last_scaled_update_inf
    assert baseline.telemetry.full_residual_evaluations == recorded.telemetry.full_residual_evaluations
    assert events[0]["event"] == "start"
    assert events[-1]["event"] == "finish"


def test_analytic_current_column_matches_centered_difference():
    contract = _contract()
    model = build_model(contract, branch="heating", current_A=2.0e-4, spatial_level=1)
    temperature = np.full(model.grid.shape, 331.6091013039466)
    solve = solve_cc_b_equilibrium(model, initial_temperature_K=temperature)
    assert solve.success and solve.temperature_K is not None
    evaluation = model.evaluate_temperature(solve.temperature_K)
    analytic = _analytic_fi_scaled_per_A(model, evaluation)
    h = np.finfo(float).eps ** (1.0 / 3.0) * model.current_set_A
    plus = replace(model, current_set_A=model.current_set_A + h)
    minus = replace(model, current_set_A=model.current_set_A - h)
    finite_difference = (
        plus.evaluate_temperature(solve.temperature_K).scaled_thermal_residual
        - minus.evaluate_temperature(solve.temperature_K).scaled_thermal_residual
    ) / (2.0 * h)
    relative = np.linalg.norm(analytic - finite_difference) / max(
        np.linalg.norm(analytic), np.linalg.norm(finite_difference)
    )
    assert relative <= 1.0e-6


def test_augmented_operator_jv_matches_centered_augmented_residual():
    contract = _contract()
    model = build_model(contract, branch="heating", current_A=2.0e-4, spatial_level=1)
    initial = np.full(model.grid.shape, 331.6091013039466)
    solve = solve_cc_b_equilibrium(model, initial_temperature_K=initial)
    assert solve.success and solve.temperature_K is not None
    z = model.scaled_from_temperature(solve.temperature_K).reshape(-1)
    y = np.repeat(model.grid.y_centers_m, model.grid.nx)
    mode, _metrics = orient_transverse_mode(model, y - np.mean(y))
    direction = np.concatenate(
        [np.linspace(-0.4, 0.6, z.size), np.asarray([0.3])]
    )
    current_scale = 5.0e-5
    width = 1.0 / (2.0 * 0.253)
    operator_action = augmented_operator_jv_from_state(
        model,
        z,
        direction,
        current_scale_A=current_scale,
        oriented_mode=mode,
        transition_scale_K=width,
    )

    def augmented_residual(values: np.ndarray) -> np.ndarray:
        z_trial = values[:-1]
        current = model.current_set_A + current_scale * float(values[-1])
        trial = replace(model, current_set_A=current)
        top = trial.evaluate_scaled_temperature(z_trial).scaled_thermal_residual
        bottom = (
            np.real(
                np.sum(
                    trial.cell_capacity_J_K.reshape(-1)
                    * np.conjugate(mode)
                    * trial.temperature_reference_K
                    * (z_trial - z)
                )
            )
            / np.sum(trial.cell_capacity_J_K)
            / width
        )
        return np.concatenate([top, [bottom]])

    base = np.concatenate([z, [0.0]])
    epsilon = 2.0e-6 / max(1.0, float(np.max(np.abs(direction))))
    centered = (
        augmented_residual(base + epsilon * direction)
        - augmented_residual(base - epsilon * direction)
    ) / (2.0 * epsilon)
    relative = np.linalg.norm(operator_action - centered) / max(
        np.linalg.norm(operator_action), np.linalg.norm(centered)
    )
    assert relative <= 2.0e-5


def test_bordered_pitchfork_toy_and_fold_arclength():
    x, mu = solve_pitchfork_toy_amplitude(0.2)
    assert x == pytest.approx(0.2, abs=1.0e-12)
    assert mu == pytest.approx(0.04, abs=1.0e-12)
    previous = (0.2, 0.96)
    current = (0.1, 0.99)
    x2, mu2 = solve_fold_toy_arclength(previous, current, 0.2)
    assert x2 * x2 + mu2 == pytest.approx(1.0, abs=1.0e-12)
    assert x2 < current[0]


def test_reflection_orientation_and_pattern_metrics_are_phase_invariant():
    contract = _contract()
    model = build_model(contract, branch="heating", current_A=2.5e-4, spatial_level=1)
    y = np.repeat(model.grid.y_centers_m, model.grid.nx)
    raw = y - np.mean(y)
    mode_a, metrics_a = orient_transverse_mode(model, raw)
    mode_b, metrics_b = orient_transverse_mode(model, raw * np.exp(1j * 1.234))
    assert np.allclose(mode_a, mode_b, atol=1.0e-12)
    assert metrics_a["reflection_odd_residual"] <= 1.0e-12
    assert metrics_b["reflection_odd_residual"] <= 1.0e-12
    assert np.allclose(reflect_y(reflect_y(raw, model.grid.shape), model.grid.shape), raw)
    temperature = 330.0 + 0.5 * mode_a.reshape(model.grid.shape)
    assert patterned_amplitude_K(model, temperature) == pytest.approx(0.5, rel=1.0e-12)
    x_fraction, y_fraction = field_gradient_fractions(
        model, temperature - reflect_y(temperature, model.grid.shape)
    )
    assert y_fraction > 0.999
    assert x_fraction < 1.0e-12


def test_patterned_seed_canonicalizes_flat_equilibrium_to_grid_shape():
    shape = (25, 10)
    base = np.full(shape[0] * shape[1], 330.0)
    mode = np.linspace(-1.0, 1.0, base.size)
    seeded = patterned_seed_temperature(
        base,
        mode,
        grid_shape=shape,
        signed_amplitude_K=0.25,
    )
    assert seeded.shape == shape
    assert np.array_equal(seeded, base.reshape(shape) + 0.25 * mode.reshape(shape))


def test_mirror_pair_metric_accepts_mixed_flat_and_grid_layouts():
    contract = _contract()
    model = build_model(contract, branch="heating", current_A=2.5e-4, spatial_level=1)
    plus = np.arange(model.grid.nx * model.grid.ny, dtype=float).reshape(
        model.grid.shape
    )
    minus = reflect_y(plus, model.grid.shape).reshape(-1)
    assert mirror_pair_error_K(model, plus, minus) == pytest.approx(0.0)


def test_nested_grid_prolongation_is_only_an_initial_field():
    contract = _contract()
    l1 = build_model(contract, branch="heating", current_A=2.0e-4, spatial_level=1)
    l2 = build_model(contract, branch="heating", current_A=2.0e-4, spatial_level=2)
    coarse = np.arange(l1.grid.nx * l1.grid.ny, dtype=float).reshape(l1.grid.shape)
    from pinnpcm.current_clamp.cc_b_solver import prolong_temperature, restrict_area_average

    prolonged = prolong_temperature(coarse, l2.grid.shape)
    assert prolonged.shape == l2.grid.shape
    assert np.array_equal(restrict_area_average(prolonged, l1.grid.shape), coarse)
    assert "then_resolve" in "L1_patterned_prolongation_then_resolve"


def test_task_csv_bytes_are_lf_only_and_hash_stable(tmp_path: Path):
    path = tmp_path / "evidence.csv"
    rows = [{"branch": "heating", "alpha_tau": np.float64(-0.25)}]
    first = _write_rows(path, rows)
    first_bytes = path.read_bytes()
    second = _write_rows(path, rows)
    assert first == second
    assert path.read_bytes() == first_bytes
    assert b"\r\n" not in first_bytes
    assert first_bytes.endswith(b"\n")


def test_stage_budget_failure_cannot_pass():
    contract = _contract()
    with pytest.raises(Exception, match="wall budget"):
        _budget_check(
            contract,
            "T",
            {"wall_time_s": contract.raw["budget"]["stage_T_wall_cap_s"] + 1.0},
        )


def test_invalid_terminal_is_fail_closed_and_keeps_counters_zero(tmp_path: Path):
    base = _contract()
    raw = dict(base.raw)
    raw["outputs"] = {
        "compact_root": "compact",
        "processed_root": "processed",
        "report": "report.md",
    }
    contract = PatternedContract(
        CONFIG,
        tmp_path,
        raw,
        base.parent,
        base.requalification,
        base.parent_bracket_raw,
    )
    contract.compact_root.mkdir(parents=True)
    contract.processed_root.mkdir(parents=True)
    terminal = _write_terminal(
        contract,
        disposition=NUMERIC_STOP,
        detail="synthetic invalidity",
        summary={},
        total_wall_s=1.0,
        total_cpu_s=1.0,
    )
    assert terminal["validity"] == "invalid"
    assert terminal["claim_status"] == "forbidden"
    assert terminal["formal_execution_count"] == 0
    assert terminal["cc_b_matrix_launch_count"] == 0
    assert terminal["patterned_mve_execution_count"] == 0
    manifest = (contract.compact_root / "artifact_manifest.json").read_text(encoding="utf-8")
    assert str(tmp_path).replace("\\", "/") not in manifest


def test_cli_returns_nonzero_for_invalid(monkeypatch):
    script_path = ROOT / "scripts/run_q2_cc_b_patterned_branch_decision_mve.py"
    spec = importlib.util.spec_from_file_location("patterned_cli", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "run_all",
        lambda *_args, **_kwargs: {"disposition": NUMERIC_STOP},
    )
    monkeypatch.setattr("sys.argv", [str(script_path)])
    assert module.main() == 2


def test_new_module_does_not_import_retired_or_downstream_paths():
    text = (
        ROOT / "src/pinnpcm/current_clamp/cc_b_patterned_branch_mve.py"
    ).read_text(encoding="utf-8")
    imports = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = (
        "pinnpcm.pinn",
        "controller_v3",
        "exact_condensed",
        "inverse",
        "ground_truth",
    )
    assert all(not any(token in name for name in imports) for token in forbidden)

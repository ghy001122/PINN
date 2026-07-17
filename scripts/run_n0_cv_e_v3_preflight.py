"""No-training operator and evidence preflight for N0-CV-E v3."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from pinnpcm.physics.conductivity import mixed_conductivity
from pinnpcm.physics.electrostatics import solve_series_electrostatics
from pinnpcm.physics.gt_solver import _rhs_factory
from pinnpcm.physics.params import spatial_param_profiles
from pinnpcm.physics.voltage_protocols import get_voltage_protocol
from pinnpcm.pinn.full_pinn_n0_cv_e import (
    ControlVolumeFullPINN,
    hard_constraint_metrics,
    torch_cv_rhs,
)
from pinnpcm.pinn.n0_cv_evidence import (
    common_cv_score,
    deterministic_npz_bytes,
    gate_coverage_table,
    load_frozen_gt,
    nested_get,
    raw_sha256,
    stable_file_hash,
    trajectory_ledgers,
)
from pinnpcm.pinn.n0_diagnostics import fixed_points_content_sha256


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _build_model(config: Mapping[str, Any], params: Mapping[str, Any], duration_s: float, seed: int) -> ControlVolumeFullPINN:
    architecture = config["architecture"]
    model = ControlVolumeFullPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=duration_s,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=config["dimensionless_registry"],
        seed=int(seed),
    )
    return model


def diagnostic_arrays(config: Mapping[str, Any], gt: Mapping[str, np.ndarray], params: Mapping[str, Any]) -> dict[str, np.ndarray]:
    diagnostics = config["diagnostics"]
    rng = np.random.default_rng(int(diagnostics["seed"]))
    nx = int(config["architecture"]["nx"])
    count = int(diagnostics["operator_random_states"])
    random_t = rng.uniform(0.03, 0.97, size=(count, 1))
    random_c = rng.uniform(0.03, 0.16, size=(count, nx))
    random_temperature = rng.uniform(300.5, 330.0, size=(count, nx))
    random_m = rng.uniform(0.03, 0.85, size=(count, nx))
    stages: dict[str, np.ndarray] = {}
    for fraction in (0.25, 0.50, 0.75, 1.00):
        label = f"{int(fraction * 100):03d}"
        stages[f"train_t_stage_{label}"] = np.sort(
            rng.uniform(1.0e-4, fraction, size=int(diagnostics["train_times_per_stage"]))
        ).reshape(-1, 1)

    t = np.asarray(gt["t"], dtype=float)
    t_norm = t / float(t[-1])
    x = np.asarray(gt["x"], dtype=float)
    material = spatial_param_profiles(x, dict(params))["k_th"]
    changes = np.flatnonzero(material[:-1] != material[1:])
    interface_left = int(changes[0])
    half_width = int(diagnostics["near_interface_half_width_cells"])
    near_interface_cells = np.arange(
        max(0, interface_left - half_width + 1), min(nx, interface_left + 1 + half_width)
    )
    transition = np.flatnonzero(
        (t_norm >= float(diagnostics["near_transition_t_norm"][0]))
        & (t_norm <= float(diagnostics["near_transition_t_norm"][1]))
    )
    ordinary_mask = np.zeros_like(t_norm, dtype=bool)
    for lower, upper in diagnostics["ordinary_t_norm_windows"]:
        ordinary_mask |= (t_norm >= float(lower)) & (t_norm <= float(upper))
    ordinary = np.flatnonzero(ordinary_mask)
    frozen_indices = np.asarray(diagnostics["operator_frozen_indices"], dtype=np.int64)
    return {
        **stages,
        "eval_t": np.sort(rng.uniform(1.0e-4, 0.9999, size=int(diagnostics["eval_times"]))).reshape(-1, 1),
        "ledger_t": np.linspace(0.0, 1.0, int(diagnostics["ledger_times"]), dtype=float).reshape(-1, 1),
        "operator_random_t": random_t,
        "operator_random_c_v": random_c,
        "operator_random_T": random_temperature,
        "operator_random_m": random_m,
        "operator_frozen_indices": frozen_indices,
        "x_m": x,
        "t_s": t,
        "t_norm": t_norm,
        "V": np.asarray(gt["V"], dtype=float),
        "I": np.asarray(gt["I"], dtype=float),
        "frozen_c_v": np.asarray(gt["c_v"], dtype=float),
        "frozen_T": np.asarray(gt["T"], dtype=float),
        "frozen_m": np.asarray(gt["m"], dtype=float),
        "frozen_phi": np.asarray(gt["phi"], dtype=float),
        "frozen_sigma": np.asarray(gt["sigma"], dtype=float),
        "material_left_mask": (x <= float(params["L_int"])).astype(np.int8),
        "near_interface_cell_indices": near_interface_cells.astype(np.int64),
        "near_transition_time_indices": transition.astype(np.int64),
        "ordinary_time_indices": ordinary.astype(np.int64),
    }


def ensure_diagnostic_dataset(path: Path, arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    expected = deterministic_npz_bytes(arrays)
    expected_hash = __import__("hashlib").sha256(expected).hexdigest()
    if path.exists():
        actual = path.read_bytes()
        if actual != expected:
            raise RuntimeError("Existing v3 diagnostic dataset differs from deterministic preregistered bytes.")
        created = False
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        created = True
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "raw_sha256": expected_hash,
        "size_bytes": len(expected),
        "created": created,
        "array_keys": sorted(arrays),
    }


def _locked_paths(config_path: Path, config: Mapping[str, Any], diagnostic_path: Path) -> list[Path]:
    frozen = config["frozen_inputs"]
    paths = [
        config_path,
        ROOT / config["outputs"]["phase_a_json"],
        diagnostic_path,
        ROOT / frozen["gt_path"],
        ROOT / frozen["gt_config"],
        ROOT / frozen["gt_manifest"],
        ROOT / frozen["old_fixed_points"],
        ROOT / "src/pinnpcm/physics/conductivity.py",
        ROOT / "src/pinnpcm/physics/electrostatics.py",
        ROOT / "src/pinnpcm/physics/gt_solver.py",
        ROOT / "src/pinnpcm/physics/params.py",
        ROOT / "src/pinnpcm/pinn/full_pinn_n0_cv_e.py",
        ROOT / "src/pinnpcm/pinn/n0_cv_evidence.py",
        ROOT / "scripts/audit_n0_r_v2_evidence_integrity.py",
        ROOT / "scripts/run_n0_cv_e_v3_preflight.py",
        ROOT / "scripts/train_n0_cv_e_v3.py",
        ROOT / "scripts/build_n0_cv_e_v3_evidence.py",
    ]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Cannot preregister missing scientific files: {missing}")
    return paths


def create_or_validate_lock(
    config_path: Path,
    config: Mapping[str, Any],
    diagnostic_record: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    lock_path = ROOT / config["outputs"]["preregistration"]
    diagnostic_path = ROOT / diagnostic_record["path"]
    paths = _locked_paths(config_path, config, diagnostic_path)
    manifest = {
        str(path.relative_to(ROOT)).replace("\\", "/"): stable_file_hash(path) for path in paths
    }
    if lock_path.exists():
        lock = _load_json(lock_path)
        if lock["locked_files"] != manifest:
            raise RuntimeError("N0-CV-E v3 preregistration hash mismatch; training remains blocked.")
        return lock, False
    lock = {
        "schema_version": "n0_cv_e_v3_preregistration_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": config["base_commit"],
        "git_commit_before_training": _git("rev-parse", "HEAD"),
        "git_dirty_before_training": bool(_git("status", "--short")),
        "locked_files": manifest,
        "diagnostic_dataset": dict(diagnostic_record),
        "old_fixed_points": {
            "content_sha256": config["frozen_inputs"]["old_fixed_points_content_sha256"],
            "raw_sha256": config["frozen_inputs"]["old_fixed_points_raw_sha256"],
        },
        "locked_preflight_gates": config["preflight_gates"],
        "locked_result_gates": config["result_gates"],
        "locked_gate_coverage": config["gate_coverage"],
        "locked_dimensionless_registry": config["dimensionless_registry"],
        "locked_training": config["training"],
        "locked_stop_rules": config["stop_rules"],
        "status": "locked_before_preflight_and_training",
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(lock, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return lock, True


def _relative_rms(prediction: np.ndarray, reference: np.ndarray) -> float:
    numerator = float(np.sqrt(np.mean((np.asarray(prediction) - np.asarray(reference)) ** 2)))
    denominator = max(float(np.sqrt(np.mean(np.asarray(reference) ** 2))), 1.0e-30)
    return numerator / denominator


def electrostatic_parity(
    model: ControlVolumeFullPINN,
    arrays: Mapping[str, np.ndarray],
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    frozen_indices = arrays["operator_frozen_indices"].astype(int)
    c_v = np.vstack([arrays["operator_random_c_v"], np.asarray(gt["c_v"])[frozen_indices]])
    temperature = np.vstack([arrays["operator_random_T"], np.asarray(gt["T"])[frozen_indices]])
    m = np.vstack([arrays["operator_random_m"], np.asarray(gt["m"])[frozen_indices]])
    t_norm = np.vstack([arrays["operator_random_t"], np.asarray(gt["t"])[frozen_indices, None] / float(gt["t"][-1])])
    c_t = torch.as_tensor(c_v, dtype=torch.float64)
    T_t = torch.as_tensor(temperature, dtype=torch.float64)
    m_t = torch.as_tensor(m, dtype=torch.float64)
    time_t = torch.as_tensor(t_norm, dtype=torch.float64)
    with torch.no_grad():
        voltage = model.voltage(time_t)
        actual = model.analytic_electrostatics(c_t, T_t, m_t, voltage)
    x = np.asarray(gt["x"], dtype=float)
    dx = float(params["L_eff"]) / x.size
    profiles = {**dict(params), **spatial_param_profiles(x, dict(params))}
    expected = {key: [] for key in ("sigma", "R_area", "J", "E", "I", "G", "phi")}
    for index in range(c_v.shape[0]):
        sigma = mixed_conductivity(c_v[index], temperature[index], m[index], profiles)
        result = solve_series_electrostatics(float(voltage[index]), sigma, dict(params), dx)
        expected["sigma"].append(sigma)
        for key in ("R_area", "J", "E", "I", "G", "phi"):
            expected[key].append(result[key])
    errors = {
        key: _relative_rms(actual[key].detach().cpu().numpy(), np.asarray(expected[key])) for key in expected
    }
    current_matrix = actual["sigma"] * actual["E"]
    scale = torch.clamp(torch.abs(actual["J"]), min=1.0e-30)
    spread = torch.max(
        (torch.max(current_matrix, dim=1).values - torch.min(current_matrix, dim=1).values) / scale
    )
    return {
        "relative_rms": errors,
        "maximum_relative_rms": max(errors.values()),
        "current_spatial_spread": float(spread.cpu()),
        "sample_count": int(c_v.shape[0]),
        "dtype": "float64",
    }


def rhs_parity(
    model: ControlVolumeFullPINN,
    arrays: Mapping[str, np.ndarray],
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    frozen_indices = arrays["operator_frozen_indices"].astype(int)
    blocks = {
        "random": (
            arrays["operator_random_t"],
            arrays["operator_random_c_v"],
            arrays["operator_random_T"],
            arrays["operator_random_m"],
        ),
        "frozen": (
            np.asarray(gt["t"])[frozen_indices, None] / float(gt["t"][-1]),
            np.asarray(gt["c_v"])[frozen_indices],
            np.asarray(gt["T"])[frozen_indices],
            np.asarray(gt["m"])[frozen_indices],
        ),
    }
    x = np.asarray(gt["x"], dtype=float)
    dx = float(params["L_eff"]) / x.size
    profiles = {**dict(params), **spatial_param_profiles(x, dict(params))}
    voltage_fn = get_voltage_protocol("triangle", float(gt["t"][-1]), dict(params))
    numpy_rhs = _rhs_factory(voltage_fn, profiles, x.size, dx)
    output: dict[str, Any] = {}
    for label, (time, c_v, temperature, m) in blocks.items():
        time_tensor = torch.as_tensor(time, dtype=torch.float64)
        c_tensor = torch.as_tensor(c_v, dtype=torch.float64)
        T_tensor = torch.as_tensor(temperature, dtype=torch.float64)
        m_tensor = torch.as_tensor(m, dtype=torch.float64)
        actual = torch_cv_rhs(model, time_tensor, c_tensor, T_tensor, m_tensor)
        expected = []
        for index in range(len(time)):
            state = np.concatenate([c_v[index], temperature[index], m[index]])
            expected.append(numpy_rhs(float(time[index, 0] * gt["t"][-1]), state))
        expected_array = np.asarray(expected)
        errors = {
            "dc_dt": _relative_rms(actual["dc_dt"].detach().numpy(), expected_array[:, : x.size]),
            "dT_dt": _relative_rms(actual["dT_dt"].detach().numpy(), expected_array[:, x.size : 2 * x.size]),
            "dm_dt": _relative_rms(actual["dm_dt"].detach().numpy(), expected_array[:, 2 * x.size :]),
        }
        output[label] = {"relative_rms": errors, "maximum_relative_rms": max(errors.values())}
    output["maximum_relative_rms"] = max(entry["maximum_relative_rms"] for entry in output.values())
    output["dtype"] = "float64"
    return output


def gradient_parity(
    model: ControlVolumeFullPINN,
    arrays: Mapping[str, np.ndarray],
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    index = int(arrays["operator_frozen_indices"][3])
    c_np = np.asarray(gt["c_v"])[index].copy()
    T_np = np.asarray(gt["T"])[index].copy()
    m_np = np.asarray(gt["m"])[index].copy()
    c = torch.tensor(c_np[None, :], dtype=torch.float64, requires_grad=True)
    temperature = torch.tensor(T_np[None, :], dtype=torch.float64, requires_grad=True)
    m = torch.tensor(m_np[None, :], dtype=torch.float64, requires_grad=True)
    voltage = torch.tensor([[float(gt["V"][index])]], dtype=torch.float64)
    result = model.analytic_electrostatics(c, temperature, m, voltage)
    objective = torch.log(result["R_area"]).sum()
    gradients = torch.autograd.grad(objective, (c, temperature, m), create_graph=False)

    x = np.asarray(gt["x"], dtype=float)
    dx = float(params["L_eff"]) / x.size
    profiles = {**dict(params), **spatial_param_profiles(x, dict(params))}

    def objective_numpy(c_value: np.ndarray, T_value: np.ndarray, m_value: np.ndarray) -> float:
        sigma = mixed_conductivity(c_value, T_value, m_value, profiles)
        electrical = solve_series_electrostatics(float(gt["V"][index]), sigma, dict(params), dx)
        return float(np.log(electrical["R_area"]))

    selected = [0, 6, 7, 15, 30]
    steps = {"c_v": 1.0e-6, "T": 1.0e-3, "m": 1.0e-6}
    records: dict[str, Any] = {}
    for name, source, gradient, step in (
        ("c_v", c_np, gradients[0].detach().numpy()[0], steps["c_v"]),
        ("T", T_np, gradients[1].detach().numpy()[0], steps["T"]),
        ("m", m_np, gradients[2].detach().numpy()[0], steps["m"]),
    ):
        comparisons = []
        for cell in selected:
            plus = source.copy()
            minus = source.copy()
            plus[cell] += step
            minus[cell] -= step
            if name == "c_v":
                finite_difference = (objective_numpy(plus, T_np, m_np) - objective_numpy(minus, T_np, m_np)) / (2 * step)
            elif name == "T":
                finite_difference = (objective_numpy(c_np, plus, m_np) - objective_numpy(c_np, minus, m_np)) / (2 * step)
            else:
                finite_difference = (objective_numpy(c_np, T_np, plus) - objective_numpy(c_np, T_np, minus)) / (2 * step)
            automatic = float(gradient[cell])
            relative = abs(automatic - finite_difference) / max(abs(automatic), abs(finite_difference), 1.0e-12)
            comparisons.append(
                {
                    "cell": cell,
                    "automatic": automatic,
                    "central_difference": finite_difference,
                    "relative_error": relative,
                }
            )
        records[name] = {
            "gradient_norm": float(np.linalg.norm(gradient)),
            "finite": bool(np.isfinite(gradient).all()),
            "comparisons": comparisons,
            "maximum_relative_error": max(row["relative_error"] for row in comparisons),
        }
    return {
        "objective": "log_series_resistance_area",
        "state_index": index,
        "variables": records,
        "all_finite": all(record["finite"] for record in records.values()),
        "minimum_gradient_norm": min(record["gradient_norm"] for record in records.values()),
        "maximum_relative_error": max(record["maximum_relative_error"] for record in records.values()),
    }


def dimensionless_roundtrip(model: ControlVolumeFullPINN) -> dict[str, Any]:
    time = torch.tensor([[0.17], [0.63], [0.91]], dtype=torch.float64)
    with torch.no_grad():
        original = model(time)
        dimensionless = model.si_to_dimensionless(original)
        recovered = model.dimensionless_to_si(dimensionless)
    errors = {}
    for key in recovered:
        errors[key] = _relative_rms(recovered[key].numpy(), original[key].numpy())
    return {"relative_rms": errors, "maximum_relative_rms": max(errors.values())}


def negative_candidate_separation(
    gt: Mapping[str, np.ndarray], params: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    base = {key: np.asarray(gt[key], dtype=float).copy() for key in ("x", "t", "V")}
    candidates = {
        "frozen_state": {
            **base,
            "c_v": np.repeat(gt["c_v"][:1], len(gt["t"]), axis=0),
            "T": np.repeat(gt["T"][:1], len(gt["t"]), axis=0),
            "m": np.repeat(gt["m"][:1], len(gt["t"]), axis=0),
        },
        "isothermal": {
            **base,
            "c_v": np.asarray(gt["c_v"]).copy(),
            "T": np.full_like(gt["T"], float(params["T0"])),
            "m": np.asarray(gt["m"]).copy(),
        },
        "near_zero_conductivity": {
            **base,
            "c_v": np.full_like(gt["c_v"], 1.0e-8),
            "T": np.full_like(gt["T"], float(params["T0"])),
            "m": np.zeros_like(gt["m"]),
        },
        "frozen_phase": {
            **base,
            "c_v": np.asarray(gt["c_v"]).copy(),
            "T": np.asarray(gt["T"]).copy(),
            "m": np.repeat(gt["m"][:1], len(gt["t"]), axis=0),
        },
    }
    result: dict[str, Any] = {}
    result_gates = config["result_gates"]
    for name, trajectory in candidates.items():
        score = common_cv_score(trajectory, gt, dict(params), config["dimensionless_registry"])
        clearly_wrong = score["port_full_trace_nrmse95"] > float(result_gates["port_full_trace_nrmse95_max"]) or max(
            score["field_score_only_nrmse95"].values()
        ) > float(result_gates["field_score_only_nrmse95_max"])
        violations = {
            "cv_residual": max(score["cv_residual_rms"].values()) > float(result_gates["residual_rms_max"]),
            "defect_ledger": score["defect_mass_ledger"]["gate_value"] > float(result_gates["defect_mass_ledger_max"]),
            "energy_ledger": score["global_energy_ledger"]["gate_value"] > float(result_gates["global_energy_imbalance_max"]),
        }
        result[name] = {
            "clearly_wrong_port_or_field": clearly_wrong,
            "physics_violations": violations,
            "separated": bool((not clearly_wrong) or any(violations.values())),
            "port_full_trace_nrmse95": score["port_full_trace_nrmse95"],
            "max_field_nrmse95": max(score["field_score_only_nrmse95"].values()),
            "cv_residual_rms": score["cv_residual_rms"],
            "defect_ledger": score["defect_mass_ledger"]["gate_value"],
            "energy_ledger": score["global_energy_ledger"]["gate_value"],
        }
    return {"candidates": result, "all_separated": all(row["separated"] for row in result.values())}


def _preflight_result_keys_complete(config: Mapping[str, Any], checks: Mapping[str, Any]) -> tuple[bool, list[str]]:
    wrapper = {"preflight": {"checks": checks}}
    missing = []
    for gate in config["preflight_gates"]:
        if gate == "result_keys_complete_required":
            continue
        path = config["gate_coverage"].get(gate)
        present, value = nested_get(wrapper, path) if path else (False, None)
        if not present or not isinstance(value, bool):
            missing.append(gate)
    return not missing, missing


def run(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    gt, params = load_frozen_gt(ROOT / config["frozen_inputs"]["gt_path"])
    phase_a = _load_json(ROOT / config["outputs"]["phase_a_json"])
    arrays = diagnostic_arrays(config, gt, params)
    diagnostic_path = ROOT / config["diagnostics"]["dataset_path"]
    diagnostic_record = ensure_diagnostic_dataset(diagnostic_path, arrays)
    lock, lock_created = create_or_validate_lock(config_path, config, diagnostic_record)
    model = _build_model(config, params, float(gt["t"][-1]), int(config["training"]["seed"])).double()

    electrostatic = electrostatic_parity(model, arrays, gt, params)
    rhs = rhs_parity(model, arrays, gt, params)
    gradients = gradient_parity(model, arrays, gt, params)
    roundtrip = dimensionless_roundtrip(model)
    constraints = hard_constraint_metrics(
        model, torch.as_tensor(arrays["eval_t"][:32], dtype=torch.float64)
    )
    ledger = trajectory_ledgers(gt, params)
    negative = negative_candidate_separation(gt, params, config)
    mapping = gate_coverage_table(config)

    with np.load(ROOT / config["frozen_inputs"]["old_fixed_points"], allow_pickle=False) as archive:
        old_points = {key: np.asarray(archive[key]) for key in archive.files}
    old_content_hash = fixed_points_content_sha256(old_points)
    expected_hashes = lock["locked_files"]
    current_hashes = {
        relative: stable_file_hash(ROOT / relative) for relative in expected_hashes
    }
    hash_match = current_hashes == expected_hashes
    all_operator_arrays = [
        electrostatic["maximum_relative_rms"],
        rhs["maximum_relative_rms"],
        gradients["maximum_relative_error"],
        roundtrip["maximum_relative_rms"],
        *constraints.values(),
    ]
    finite_operator = all(math.isfinite(float(value)) for value in all_operator_arrays)
    gates = config["preflight_gates"]
    checks: dict[str, bool] = {
        "phase_a_completed": bool(phase_a.get("phase_a_completed")),
        "gate_coverage_complete": bool(mapping["mapping_complete"]),
        "electrostatics_parity": electrostatic["maximum_relative_rms"]
        <= float(gates["electrostatics_float64_relative_error_max"]),
        "cv_rhs_parity": rhs["maximum_relative_rms"] <= float(gates["cv_rhs_relative_rms_max"]),
        "current_spread": electrostatic["current_spatial_spread"]
        <= float(gates["current_spatial_spread_max"]),
        "gradient_finite": bool(gradients["all_finite"]),
        "gradient_nonzero": gradients["minimum_gradient_norm"]
        >= float(gates["gradient_nonzero_norm_min"]),
        "gradient_parity": gradients["maximum_relative_error"]
        <= float(gates["gradient_central_difference_relative_error_max"]),
        "dimensionless_roundtrip": roundtrip["maximum_relative_rms"]
        <= float(gates["roundtrip_relative_error_max"]),
        "frozen_defect_ledger": ledger["defect"]["gate_value"]
        <= float(gates["frozen_trajectory_defect_ledger_max"]),
        "frozen_energy_ledger": ledger["energy"]["gate_value"]
        <= float(gates["frozen_trajectory_energy_ledger_max"]),
        "radau_replay": phase_a["radau_replay"]["maximum_relative_rms"]
        <= float(gates["radau_replay_relative_rms_max"]),
        "negative_candidate_separation": bool(negative["all_separated"]),
        "ic_bc": max(constraints.values()) <= float(gates["ic_bc_max_normalized_error"]),
        "finite_operator_outputs": finite_operator,
        "frozen_gt_hash": hash_match
        and raw_sha256(ROOT / config["frozen_inputs"]["gt_path"])
        == phase_a["frozen_hashes"][config["frozen_inputs"]["gt_path"]],
        "old_fixed_points_hash": raw_sha256(ROOT / config["frozen_inputs"]["old_fixed_points"])
        == config["frozen_inputs"]["old_fixed_points_raw_sha256"]
        and old_content_hash == config["frozen_inputs"]["old_fixed_points_content_sha256"],
    }
    keys_complete, missing_keys = _preflight_result_keys_complete(config, checks)
    checks["result_keys_complete"] = keys_complete
    all_pass = all(checks.values())
    payload = {
        "schema_version": "n0_cv_e_v3_preflight_v1",
        "stage_id": "N0-CV-E-v3-preflight",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": config["base_commit"],
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--short")),
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "preregistration_path": config["outputs"]["preregistration"],
        "preregistration_raw_sha256": raw_sha256(ROOT / config["outputs"]["preregistration"]),
        "preregistration_created_this_run": lock_created,
        "diagnostic_dataset": diagnostic_record,
        "parameter_count": model.parameter_count(),
        "contract": model.contract(),
        "checks": checks,
        "missing_result_keys": missing_keys,
        "all_pass": all_pass,
        "training_authorized": all_pass,
        "status": "pass" if all_pass else "fail_closed",
        "metrics": {
            "electrostatics": electrostatic,
            "cv_rhs": rhs,
            "gradients": gradients,
            "dimensionless_roundtrip": roundtrip,
            "hard_constraints": constraints,
            "frozen_trajectory_ledger": ledger,
            "negative_candidates": negative,
        },
        "gate_mapping": mapping,
        "hash_validation": {
            "all_locked_files_match": hash_match,
            "old_fixed_points_content_sha256": old_content_hash,
            "old_fixed_points_raw_sha256": raw_sha256(ROOT / config["frozen_inputs"]["old_fixed_points"]),
            "frozen_gt_raw_sha256": raw_sha256(ROOT / config["frozen_inputs"]["gt_path"]),
        },
        "stop_reason": None if all_pass else "At least one operator, ledger, negative-control, IC/BC, result-key, or hash gate failed.",
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/full_pinn_n0_cv_e_v3.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    payload = run(config_path)
    config = _load_yaml(config_path)
    output = ROOT / config["outputs"]["preflight"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": payload["status"], "all_pass": payload["all_pass"], "training_authorized": payload["training_authorized"]}))
    if not payload["all_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

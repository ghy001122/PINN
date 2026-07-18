"""Fail-closed no-training preflight for the M33 mixed-flux contract."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from pinnpcm.physics.gt_solver import equilibrium_m
from pinnpcm.pinn.mixed_flux_pinn import (
    MixedStateFluxPINN,
    grouped_constraint_tensors,
    mixed_operator_residuals,
    rms,
)
from pinnpcm.pinn.full_pinn_n0_cv_e import torch_cv_rhs
from pinnpcm.pinn.n0_cv_evidence import (
    load_frozen_gt,
    raw_sha256,
    stable_file_hash,
    tamper_detection,
    trajectory_ledgers,
)


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def _relative_rms(actual: np.ndarray, expected: np.ndarray) -> float:
    numerator = float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(expected)) ** 2)))
    denominator = max(float(np.sqrt(np.mean(np.asarray(expected) ** 2))), 1.0e-30)
    return numerator / denominator


def _build(config: Mapping[str, Any], params: Mapping[str, Any], duration: float, *, seed: int | None = None) -> MixedStateFluxPINN:
    architecture = config["architecture"]
    return MixedStateFluxPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=duration,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=config["dimensionless_registry"],
        seed=int(config["training"]["seed"] if seed is None else seed),
    )


def _rms_map(result: Mapping[str, torch.Tensor]) -> dict[str, float]:
    names = ("q_c_constitutive", "q_T_constitutive", "r_c", "r_T", "r_m", "discrete_electrical")
    return {name: float(rms(result[name]).detach().cpu()) for name in names}


def _constant_equilibrium(config: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    local = dict(params)
    local.update({"layer_profile": "uniform", "initial_defect_mode": "uniform", "triangle_v_peak": 0.0})
    model = _build(config, local, 3.0e-3, seed=91).double()
    count = 4
    time = torch.linspace(0.1, 0.9, count, dtype=torch.float64).reshape(-1, 1)
    c = torch.full((count, model.nx), float(local["c_v0"]), dtype=torch.float64)
    temperature = torch.full_like(c, float(local["T0"]))
    equilibrium = equilibrium_m(c.numpy(), temperature.numpy(), local)
    m = torch.as_tensor(equilibrium, dtype=torch.float64)
    zero_state = torch.zeros_like(c)
    zero_flux = torch.zeros((count, model.nx + 1), dtype=torch.float64)
    residuals = mixed_operator_residuals(
        model, time, c, temperature, m, zero_state, zero_state, zero_state, zero_flux, zero_flux
    )
    values = _rms_map(residuals)
    return {"residual_rms": values, "maximum_residual_rms": max(values.values())}


def _exact_fvm_parity(
    model: MixedStateFluxPINN,
    arrays: Mapping[str, np.ndarray],
    gt: Mapping[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, torch.Tensor]]:
    indices = np.asarray(arrays["operator_frozen_indices"], dtype=int)
    time = torch.as_tensor(np.asarray(gt["t"])[indices, None] / float(gt["t"][-1]), dtype=torch.float64)
    c = torch.as_tensor(np.asarray(gt["c_v"])[indices], dtype=torch.float64)
    temperature = torch.as_tensor(np.asarray(gt["T"])[indices], dtype=torch.float64)
    m = torch.as_tensor(np.asarray(gt["m"])[indices], dtype=torch.float64)
    frozen = torch_cv_rhs(model, time, c, temperature, m)
    residuals = mixed_operator_residuals(
        model, time, c, temperature, m,
        frozen["dc_dt"], frozen["dT_dt"], frozen["dm_dt"],
        frozen["defect_flux"], frozen["heat_flux"],
    )
    values = _rms_map(residuals)
    record = {"sample_indices": indices.tolist(), "residual_rms": values, "maximum_relative_rms": max(values.values())}
    return record, {"time": time, "c": c, "T": temperature, "m": m, **frozen}


def _initial_flux_head_parity(model: MixedStateFluxPINN) -> dict[str, Any]:
    time = torch.zeros((1, 1), dtype=torch.float64)
    output = model(time)
    frozen = torch_cv_rhs(model, time, output["c_v"], output["T"], output["m"])
    errors = {
        "q_c_relative_rms": _relative_rms(output["q_c"].detach().numpy(), frozen["defect_flux"].detach().numpy()),
        "q_T_absolute_rms_W_m2": float(rms(output["q_T"] - frozen["heat_flux"]).detach()),
    }
    return {
        **errors,
        "maximum_error": max(errors.values()),
        "q_c_scale_m_s": float(model.defect_flux_scale),
        "q_T_scale_W_m2": float(model.heat_flux_scale),
        "q_c_units": "m s^-1",
        "q_T_units": "W m^-2",
    }


def _interface_audit(
    model: MixedStateFluxPINN,
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    i = model.interface_left
    j = i + 1
    scales = {"c_v": 1.0, "T": float(model.registry["temperature_scale_K"]), "m": 1.0, "phi": float(model.registry["voltage_scale_V"])}
    state_rms: dict[str, float] = {}
    for name, scale in scales.items():
        value = np.asarray(gt[name], dtype=float)
        left = 1.5 * value[:, i] - 0.5 * value[:, i - 1]
        right = 1.5 * value[:, j] - 0.5 * value[:, j + 1]
        state_rms[name] = float(np.sqrt(np.mean(((right - left) / scale) ** 2)))
    indices = np.asarray([0, 57, 171, 285, 399], dtype=int)
    time = torch.as_tensor(np.asarray(gt["t"])[indices, None] / float(gt["t"][-1]), dtype=torch.float64)
    c = torch.as_tensor(np.asarray(gt["c_v"])[indices], dtype=torch.float64)
    temperature = torch.as_tensor(np.asarray(gt["T"])[indices], dtype=torch.float64)
    m = torch.as_tensor(np.asarray(gt["m"])[indices], dtype=torch.float64)
    frozen = torch_cv_rhs(model, time, c, temperature, m)
    q_c = frozen["defect_flux"][:, model.interface_face]
    q_T = frozen["heat_flux"][:, model.interface_face]
    # One shared global face value corresponds to opposite outward normals.
    jumps = {
        "defect_oriented_jump": float(torch.max(torch.abs(q_c + (-q_c))) / model.defect_flux_scale),
        "heat_oriented_jump": float(torch.max(torch.abs(q_T + (-q_T))) / model.heat_flux_scale),
        "current_oriented_jump": 0.0,
    }
    return {
        "interface_left_cell": i,
        "interface_right_cell": j,
        "interface_face": model.interface_face,
        "one_sided_state_trace_rms": state_rms,
        "maximum_state_trace_rms": max(state_rms.values()),
        "oriented_flux_jump": jumps,
        "maximum_oriented_flux_jump": max(jumps.values()),
        "semantics": "frozen one-sided state traces plus one explicit shared face flux with opposite outward normals",
    }


def _independent_ledger_reconstruction(gt: Mapping[str, np.ndarray], params: Mapping[str, Any]) -> dict[str, Any]:
    reference = trajectory_ledgers(gt, dict(params))
    # A second direct adjacent-state reconstruction, deliberately not calling
    # internal trajectory_ledgers helpers.
    t = np.asarray(gt["t"], dtype=float)
    x = np.asarray(gt["x"], dtype=float)
    c = np.asarray(gt["c_v"], dtype=float)
    temperature = np.asarray(gt["T"], dtype=float)
    from pinnpcm.physics.conductivity import arrhenius_reference, mixed_conductivity
    from pinnpcm.physics.electrostatics import solve_series_electrostatics
    from pinnpcm.physics.params import spatial_param_profiles

    dx = float(params["L_eff"]) / x.size
    profiles = {**dict(params), **spatial_param_profiles(x, dict(params))}
    reaction_rate = arrhenius_reference(float(params["k_r0"]), float(params["E_r_eV"]), temperature, float(params["T0"]))
    reaction = np.sum(reaction_rate * (c - float(params["c_v0"])), axis=1) * dx
    joule = np.zeros(t.size)
    sink = np.sum(float(params["gamma_sub"]) * (temperature - float(params["T0"])), axis=1) * dx
    for index, voltage in enumerate(np.asarray(gt["V"], dtype=float)):
        sigma = mixed_conductivity(c[index], temperature[index], np.asarray(gt["m"])[index], profiles)
        electrical = solve_series_electrostatics(float(voltage), sigma, dict(params), dx)
        joule[index] = np.sum(float(electrical["J"]) * np.asarray(electrical["E"])) * dx
    dt = np.diff(t)
    mass = np.sum(c, axis=1) * dx
    energy = np.sum(float(params["rho"]) * float(params["Cp"]) * temperature, axis=1) * dx
    mass_storage = np.diff(mass)
    mass_reaction = 0.5 * (reaction[:-1] + reaction[1:]) * dt
    mass_balance = mass_storage + mass_reaction
    mass_relative = np.abs(mass_balance) / np.maximum(np.abs(mass_storage) + np.abs(mass_reaction), 1.0e-30)
    energy_storage = np.diff(energy)
    energy_joule = 0.5 * (joule[:-1] + joule[1:]) * dt
    energy_sink = 0.5 * (sink[:-1] + sink[1:]) * dt
    energy_balance = energy_storage - energy_joule + energy_sink
    energy_relative = np.abs(energy_balance) / np.maximum(np.abs(energy_storage) + np.abs(energy_joule) + np.abs(energy_sink), 1.0e-30)
    direct = {
        "defect_gate_value": float(max(np.max(mass_relative), abs(np.sum(mass_balance)) / max(abs(np.sum(mass_storage)) + abs(np.sum(mass_reaction)), 1.0e-30))),
        "energy_gate_value": float(max(np.max(energy_relative), abs(np.sum(energy_balance)) / max(abs(np.sum(energy_storage)) + abs(np.sum(energy_joule)) + abs(np.sum(energy_sink)), 1.0e-30))),
    }
    differences = {
        "defect": abs(direct["defect_gate_value"] - float(reference["defect"]["gate_value"])),
        "energy": abs(direct["energy_gate_value"] - float(reference["energy"]["gate_value"])),
    }
    return {"reference": reference, "direct": direct, "absolute_differences": differences, "maximum_relative_error": max(differences.values())}


def _gradient_audit(model: MixedStateFluxPINN, arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    train_t = torch.as_tensor(np.asarray(arrays["train_t_stage_025"])[:8], dtype=torch.float64)
    ledger_t = torch.as_tensor(np.asarray(arrays["ledger_t"])[:8], dtype=torch.float64)
    groups = grouped_constraint_tensors(model, train_t, ledger_t)
    objective = sum(rms(value).square() for value in groups.values())
    parameter = model.heat_flux_head.weight
    automatic = torch.autograd.grad(objective, parameter, retain_graph=True)[0][0, 0]
    step = 1.0e-6
    original = float(parameter.data[0, 0])
    with torch.no_grad():
        parameter.data[0, 0] = original + step
        plus = float(sum(rms(value).square() for value in grouped_constraint_tensors(model, train_t, ledger_t).values()))
        parameter.data[0, 0] = original - step
        minus = float(sum(rms(value).square() for value in grouped_constraint_tensors(model, train_t, ledger_t).values()))
        parameter.data[0, 0] = original
    finite_difference = (plus - minus) / (2.0 * step)
    relative = abs(float(automatic) - finite_difference) / max(abs(float(automatic)), abs(finite_difference), 1.0e-12)
    model.zero_grad(set_to_none=True)
    objective = sum(rms(value).square() for value in grouped_constraint_tensors(model, train_t, ledger_t).values())
    objective.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
    norms = [float(torch.linalg.vector_norm(value)) for value in gradients]
    return {
        "parameter": "heat_flux_head.weight[0,0]",
        "automatic": float(automatic),
        "central_difference": finite_difference,
        "relative_error": relative,
        "all_gradients_finite": bool(gradients and all(torch.isfinite(value).all() for value in gradients)),
        "gradient_norm": float(sum(norms)),
        "all_outputs_finite": bool(all(torch.isfinite(value).all() for value in groups.values())),
    }


def _tamper_audit(
    model: MixedStateFluxPINN,
    exact_payload: Mapping[str, torch.Tensor],
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = mixed_operator_residuals(
        model, exact_payload["time"], exact_payload["c"], exact_payload["T"], exact_payload["m"],
        exact_payload["dc_dt"], exact_payload["dT_dt"], exact_payload["dm_dt"],
        exact_payload["defect_flux"], exact_payload["heat_flux"],
    )
    flipped = mixed_operator_residuals(
        model, exact_payload["time"], exact_payload["c"], exact_payload["T"], exact_payload["m"],
        exact_payload["dc_dt"], exact_payload["dT_dt"], exact_payload["dm_dt"],
        -exact_payload["defect_flux"], -exact_payload["heat_flux"],
    )
    shifted_q_c = exact_payload["defect_flux"].clone()
    shifted_q_T = exact_payload["heat_flux"].clone()
    shifted_q_c[:, model.interface_face] += model.defect_flux_scale.to(shifted_q_c)
    shifted_q_T[:, model.interface_face] += model.heat_flux_scale.to(shifted_q_T)
    interface_tamper = mixed_operator_residuals(
        model, exact_payload["time"], exact_payload["c"], exact_payload["T"], exact_payload["m"],
        exact_payload["dc_dt"], exact_payload["dT_dt"], exact_payload["dm_dt"], shifted_q_c, shifted_q_T,
    )
    base = max(_rms_map(baseline).values())
    flip = max(_rms_map(flipped).values())
    interface = max(_rms_map(interface_tamper).values())
    ledger = tamper_detection(gt, dict(params))
    return {
        "baseline_max": base,
        "sign_flip_max": flip,
        "interface_shift_max": interface,
        "minimum_amplification": min(flip, interface) / max(base, 1.0e-12),
        "ledger_tamper": ledger,
        "all_detected": bool(
            flip > max(base * 10.0, 1.0e-6)
            and interface > max(base * 10.0, 1.0e-6)
            and ledger["defect_tamper_detected"]
            and ledger["energy_tamper_detected"]
        ),
    }


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prereg_path = ROOT / config["outputs"]["preregistration"]
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    current_hashes = {relative: stable_file_hash(ROOT / relative) for relative in prereg["locked_files"]}
    hash_match = current_hashes == prereg["locked_files"]
    gt, params = load_frozen_gt(ROOT / config["frozen_inputs"]["gt_path"])
    with np.load(ROOT / config["frozen_inputs"]["diagnostic_dataset"], allow_pickle=False) as archive:
        arrays = {key: np.asarray(archive[key]) for key in archive.files}
    model = _build(config, params, float(gt["t"][-1])).double()
    constant = _constant_equilibrium(config, params)
    exact, exact_payload = _exact_fvm_parity(model, arrays, gt)
    initial_flux = _initial_flux_head_parity(model)
    interface = _interface_audit(model, gt, params)
    ledgers = _independent_ledger_reconstruction(gt, params)
    gradients = _gradient_audit(model, arrays)
    tamper = _tamper_audit(model, exact_payload, gt, params)
    groups = list(config["training"]["augmented_lagrangian"]["groups"])
    multipliers = {name: float(config["training"]["augmented_lagrangian"]["initial_multiplier"]) for name in groups}
    penalties = {name: float(config["training"]["augmented_lagrangian"]["initial_penalty"]) for name in groups}
    finite_multipliers = all(math.isfinite(value) for value in [*multipliers.values(), *penalties.values()])
    gates = config["preflight_gates"]
    contract = model.contract()
    parameter_difference = abs(float(contract["relative_parameter_difference"]))
    checks = {
        "parameter_budget": parameter_difference <= float(gates["parameter_count_relative_difference_max"]),
        "constant_equilibrium": constant["maximum_residual_rms"] <= float(gates["constant_equilibrium_residual_rms_max"]),
        "exact_fvm_parity": exact["maximum_relative_rms"] <= float(gates["exact_fvm_residual_relative_rms_max"]),
        "initial_flux_head_parity": initial_flux["maximum_error"] <= float(gates["initial_flux_head_relative_rms_max"]),
        "interface_state_trace": interface["maximum_state_trace_rms"] <= float(gates["interface_state_rms_max"]),
        "interface_flux_jump": interface["maximum_oriented_flux_jump"] <= float(gates["interface_oriented_flux_jump_max"]),
        "ledger_reconstruction": ledgers["maximum_relative_error"] <= float(gates["ledger_reconstruction_relative_error_max"]),
        "frozen_defect_ledger": ledgers["reference"]["defect"]["gate_value"] <= float(gates["frozen_defect_ledger_max"]),
        "frozen_energy_ledger": ledgers["reference"]["energy"]["gate_value"] <= float(gates["frozen_energy_ledger_max"]),
        "gradient_parity": gradients["relative_error"] <= float(gates["gradient_central_difference_relative_error_max"]),
        "gradient_nonzero": gradients["gradient_norm"] >= float(gates["gradient_nonzero_norm_min"]),
        "tamper_controls": bool(tamper["all_detected"] and tamper["minimum_amplification"] >= float(gates["tamper_detection_min_factor"])),
        "finite_outputs_gradients_multipliers": bool(gradients["all_outputs_finite"] and gradients["all_gradients_finite"] and finite_multipliers),
        "frozen_gt_hash": bool(hash_match and raw_sha256(ROOT / config["frozen_inputs"]["gt_path"]) == prereg["frozen_gt_raw_sha256"]),
        "diagnostic_dataset_hash": raw_sha256(ROOT / config["frozen_inputs"]["diagnostic_dataset"]) == config["frozen_inputs"]["diagnostic_dataset_sha256"],
        "preregistration_precedes_preflight": _git("rev-parse", "HEAD") != config["base_snapshot"] and not bool(_git("status", "--short")),
    }
    all_pass = all(checks.values())
    return {
        "schema_version": "m33_mixed_flux_preflight_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "preregistration_commit": _git("rev-parse", "HEAD"),
        "preregistration_raw_sha256": raw_sha256(prereg_path),
        "locked_files_match": hash_match,
        "contract": contract,
        "checks": checks,
        "all_pass": all_pass,
        "training_authorized": all_pass,
        "status": "supported" if all_pass else "failed_but_informative",
        "metrics": {
            "constant_equilibrium": constant,
            "exact_fvm_parity": exact,
            "initial_flux_head": initial_flux,
            "interface": interface,
            "ledgers": ledgers,
            "gradients": gradients,
            "tamper": tamper,
            "initial_augmented_lagrangian_state": {"multipliers": multipliers, "penalties": penalties},
        },
        "stop_reason": None if all_pass else "At least one preregistered no-training preflight check failed; M33 training is blocked.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m33_feasibility_first_mixed_flux.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    payload = run(config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output = ROOT / config["outputs"]["preflight"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": payload["status"], "all_pass": payload["all_pass"], "checks": payload["checks"]}))
    if not payload["all_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

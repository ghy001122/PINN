"""Single-seed feasibility-first training for preregistered M33."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from pinnpcm.pinn.full_pinn_n0_cv_e import hard_constraint_metrics, torch_cv_rhs
from pinnpcm.pinn.mixed_flux_pinn import (
    MixedStateFluxPINN,
    grouped_constraint_tensors,
    mixed_ledger_residuals,
    mixed_state_flux_residuals,
    rms,
)
from pinnpcm.pinn.n0_cv_evidence import (
    common_cv_score,
    load_frozen_gt,
    nrmse95,
    raw_sha256,
    stable_file_hash,
)


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested(payload: Mapping[str, Any], dotted: str) -> float:
    current: Any = payload
    for part in dotted.split("."):
        current = current[part]
    return float(current)


def _build(config: Mapping[str, Any], params: Mapping[str, Any], duration: float) -> MixedStateFluxPINN:
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
        seed=int(config["training"]["seed"]),
    )


def _authorize(config: Mapping[str, Any]) -> dict[str, Any]:
    prereg_path = ROOT / config["outputs"]["preregistration"]
    preflight_path = ROOT / config["outputs"]["preflight"]
    prereg = _load_json(prereg_path)
    preflight = _load_json(preflight_path)
    mismatches = {}
    for relative, expected in prereg["locked_files"].items():
        actual = stable_file_hash(ROOT / relative)
        if actual != expected:
            mismatches[relative] = {"expected": expected, "actual": actual}
    head = _git("rev-parse", "HEAD")
    status_lines = [line for line in _git("status", "--short").splitlines() if line]
    expected_preflight_status = f"?? {config['outputs']['preflight']}"
    worktree_allowed = status_lines == [expected_preflight_status]
    authorized = bool(
        preflight.get("all_pass")
        and preflight.get("training_authorized")
        and preflight.get("preregistration_commit") == head
        and not mismatches
        and worktree_allowed
    )
    record = {
        "authorized": authorized,
        "preregistration_commit": preflight.get("preregistration_commit"),
        "current_commit": head,
        "hash_mismatches": mismatches,
        "worktree_status": status_lines,
        "expected_preflight_only_status": expected_preflight_status,
        "worktree_allowed": worktree_allowed,
        "preflight_all_pass": bool(preflight.get("all_pass")),
        "preregistration_raw_sha256": raw_sha256(prereg_path),
        "preflight_raw_sha256": raw_sha256(preflight_path),
    }
    if not authorized:
        raise RuntimeError(f"M33 training authorization failed closed: {record}")
    return record


def _group_norms(groups: Mapping[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {name: rms(value) for name, value in groups.items()}


def _augmented_loss(
    norms: Mapping[str, torch.Tensor],
    multipliers: Mapping[str, float],
    penalties: Mapping[str, float],
    *,
    coupled: bool,
) -> torch.Tensor:
    terms = []
    for name, value in norms.items():
        term = float(multipliers[name]) * value + 0.5 * float(penalties[name]) * value.square()
        if coupled:
            term = term + value.square()
        terms.append(term)
    return torch.stack(terms).sum()


def _snapshot(
    model: MixedStateFluxPINN,
    train_t: torch.Tensor,
    ledger_t: torch.Tensor,
    multipliers: Mapping[str, float],
    penalties: Mapping[str, float],
    *,
    step: int,
    stage: str,
    fraction: float,
    gradient_norm: float | None,
    elapsed_s: float,
) -> dict[str, Any]:
    groups = grouped_constraint_tensors(model, train_t, ledger_t)
    norms = _group_norms(groups)
    with torch.no_grad():
        output = model(train_t)
    return {
        "step": int(step),
        "stage": stage,
        "t_norm_max": float(fraction),
        "group_rms": {name: float(value.detach().cpu()) for name, value in norms.items()},
        "multipliers": {name: float(value) for name, value in multipliers.items()},
        "penalties": {name: float(value) for name, value in penalties.items()},
        "augmented_loss": float(_augmented_loss(norms, multipliers, penalties, coupled=stage == "coupled").detach().cpu()),
        "gradient_norm_before_clip": None if gradient_norm is None else float(gradient_norm),
        "state_ranges": {
            name: [float(torch.min(output[name]).cpu()), float(torch.max(output[name]).cpu())]
            for name in ("c_v", "T", "m", "phi", "q_c", "q_T")
        },
        "finite": bool(
            all(torch.isfinite(value).all() for value in output.values())
            and all(math.isfinite(value) for value in multipliers.values())
            and all(math.isfinite(value) for value in penalties.values())
        ),
        "elapsed_s": float(elapsed_s),
    }


def _model_trajectory(model: MixedStateFluxPINN, gt: Mapping[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    t = np.asarray(gt["t"], dtype=float)
    t_norm = torch.as_tensor((t / t[-1])[:, None], dtype=torch.float32)
    model.eval()
    with torch.no_grad():
        output = model(t_norm)
    trajectory = {
        "x": np.asarray(gt["x"], dtype=float).copy(),
        "t": t.copy(),
        "V": np.asarray(gt["V"], dtype=float).copy(),
        "c_v": output["c_v"].cpu().numpy(),
        "T": output["T"].cpu().numpy(),
        "m": output["m"].cpu().numpy(),
    }
    fluxes = {"q_c": output["q_c"].cpu().numpy(), "q_T": output["q_T"].cpu().numpy()}
    return trajectory, fluxes


def _evaluate(
    model: MixedStateFluxPINN,
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    eval_t = torch.as_tensor(np.asarray(arrays["eval_t"]), dtype=torch.float32)
    ledger_t = torch.as_tensor(np.asarray(arrays["ledger_t"]), dtype=torch.float32)
    residuals = mixed_state_flux_residuals(model, eval_t)
    head_ledgers = mixed_ledger_residuals(model, ledger_t)
    trajectory, predicted_fluxes = _model_trajectory(model, gt)
    common = common_cv_score(trajectory, gt, dict(params), config["dimensionless_registry"])

    gt_t = torch.as_tensor((np.asarray(gt["t"]) / float(gt["t"][-1]))[:, None], dtype=torch.float64)
    gt_c = torch.as_tensor(np.asarray(gt["c_v"]), dtype=torch.float64)
    gt_T = torch.as_tensor(np.asarray(gt["T"]), dtype=torch.float64)
    gt_m = torch.as_tensor(np.asarray(gt["m"]), dtype=torch.float64)
    target_flux = torch_cv_rhs(model.double(), gt_t, gt_c, gt_T, gt_m)
    model.float()
    face = model.interface_face
    explicit_interface_flux = {
        "current": float(common["interface_flux_rms"]["current"]),
        "heat": nrmse95(predicted_fluxes["q_T"][:, face], target_flux["heat_flux"].detach().numpy()[:, face]),
        "defect": nrmse95(predicted_fluxes["q_c"][:, face], target_flux["defect_flux"].detach().numpy()[:, face]),
        "semantics": "explicit_m33_face_head_vs_frozen_gt_face_flux",
    }
    cv_rms = {name: float(rms(residuals[name]).detach().cpu()) for name in ("r_c", "r_T", "r_m")}
    constitutive_rms = {
        "q_c": float(rms(residuals["q_c_constitutive"]).detach().cpu()),
        "q_T": float(rms(residuals["q_T_constitutive"]).detach().cpu()),
    }
    electrical_rms = float(rms(residuals["discrete_electrical"]).detach().cpu())
    ledger_rms = {name: float(rms(value).detach().cpu()) for name, value in head_ledgers.items()}
    constraints = hard_constraint_metrics(model, eval_t[:32])
    with torch.no_grad():
        boundary = model(eval_t[:32])
    constraints.update(
        {
            "bc_q_c": float(torch.max(torch.abs(boundary["q_c"][:, [0, -1]]) / model.defect_flux_scale).cpu()),
            "bc_q_T": float(torch.max(torch.abs(boundary["q_T"][:, [0, -1]]) / model.heat_flux_scale).cpu()),
        }
    )
    metrics = {
        "port_full_trace_nrmse95": float(common["port_full_trace_nrmse95"]),
        "cv_residual_rms": cv_rms,
        "constitutive_rms": constitutive_rms,
        "discrete_electrical_rms": electrical_rms,
        "field_score_only_nrmse95": common["field_score_only_nrmse95"],
        "interface_state_rms": common["interface_state_rms"],
        "interface_flux_rms": explicit_interface_flux,
        "terminal_current_conservation_normalized_error": float(common["terminal_current_conservation_normalized_error"]),
        "global_energy_ledger": common["global_energy_ledger"],
        "defect_mass_ledger": common["defect_mass_ledger"],
        "explicit_head_ledger_rms": ledger_rms,
        "ic_bc_normalized_errors": constraints,
        "finite_outputs": bool(common["finite_outputs"] and np.isfinite(predicted_fluxes["q_c"]).all() and np.isfinite(predicted_fluxes["q_T"]).all()),
        "bounded_states": bool(common["bounded_states"]),
        "region_diagnostics": common["region_diagnostics"],
        "normalization": common["normalization"],
        "final_physics": "frozen_H0_exact_width_and_original_operator",
    }
    gates = config["result_gates"]
    numeric_interface_state = [value for value in metrics["interface_state_rms"].values() if isinstance(value, (int, float))]
    numeric_interface_flux = [value for value in metrics["interface_flux_rms"].values() if isinstance(value, (int, float))]
    checks = {
        "port": metrics["port_full_trace_nrmse95"] <= float(gates["port_full_trace_nrmse95_max"]),
        "cv_residuals": all(value <= float(gates["residual_rms_max"]) for value in cv_rms.values()),
        "constitutive": all(value <= float(gates["constitutive_rms_max"]) for value in constitutive_rms.values()),
        "discrete_electrical": electrical_rms <= float(gates["discrete_electrical_rms_max"]),
        "fields": all(float(value) <= float(gates["field_score_only_nrmse95_max"]) for value in metrics["field_score_only_nrmse95"].values()),
        "interface_state": all(value <= float(gates["interface_state_rms_max"]) for value in numeric_interface_state),
        "interface_flux": all(value <= float(gates["interface_flux_rms_max"]) for value in numeric_interface_flux),
        "current_conservation": metrics["terminal_current_conservation_normalized_error"] <= float(gates["terminal_current_conservation_max"]),
        "energy_ledger": metrics["global_energy_ledger"]["gate_value"] <= float(gates["global_energy_imbalance_max"]),
        "defect_ledger": metrics["defect_mass_ledger"]["gate_value"] <= float(gates["defect_mass_ledger_max"]),
        "explicit_head_energy_ledger": ledger_rms["energy_ledger"] <= float(gates["global_energy_imbalance_max"]),
        "explicit_head_defect_ledger": ledger_rms["defect_mass_ledger"] <= float(gates["defect_mass_ledger_max"]),
        "explicit_head_current_ledger": ledger_rms["current_ledger"] <= float(gates["terminal_current_conservation_max"]),
        "ic_bc": max(constraints.values()) <= float(gates["result_ic_bc_max_normalized_error"]),
        "finite_outputs": bool(metrics["finite_outputs"]),
        "bounded_states": bool(metrics["bounded_states"]),
    }

    baseline_payload = _load_json(ROOT / config["frozen_inputs"]["v3r_post_adam_score"])
    baseline_raw = baseline_payload["score"]["metrics"]
    baseline = {
        "port_full_trace_nrmse95": baseline_raw["port_full_trace_nrmse95"],
        "cv_residual_rms": baseline_raw["cv_residual_rms"],
        "discrete_electrical_rms": baseline_raw["discrete_electrical_rms"],
        "field_score_only_nrmse95": baseline_raw["field_score_only_nrmse95"],
        "interface_state_rms": baseline_raw["interface_state_score_only_rms"],
        "interface_flux_rms": baseline_raw["interface_flux_score_only_nrmse95"],
        "terminal_current_conservation_normalized_error": baseline_raw["analytic_current_conservation_nonvote"],
        "global_energy_ledger": baseline_raw["global_energy_ledger"],
        "defect_mass_ledger": baseline_raw["defect_mass_ledger"],
    }
    relative_tolerance = float(config["comparison_to_v3r"]["no_worse_relative_tolerance"])
    absolute_tolerance = float(config["comparison_to_v3r"]["no_worse_absolute_tolerance"])
    comparison_rows = []
    for name in config["comparison_to_v3r"]["required_metrics"]:
        current = _nested(metrics, name)
        previous = _nested(baseline, name)
        no_worse = current <= previous * (1.0 + relative_tolerance) + absolute_tolerance
        comparison_rows.append(
            {"metric": name, "v3r_post_adam": previous, "m33": current, "delta": current - previous, "no_worse": no_worse}
        )
    comparison = {
        "required_metrics": len(comparison_rows),
        "no_worse_count": sum(bool(row["no_worse"]) for row in comparison_rows),
        "all_no_worse": all(bool(row["no_worse"]) for row in comparison_rows),
        "rows": comparison_rows,
    }
    checks["v3r_no_regression"] = bool(comparison["all_no_worse"])
    return metrics, {"checks": checks, "all_pass": all(checks.values())}, comparison, comparison_rows


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    final_path = ROOT / config["outputs"]["final_summary"]
    if final_path.exists():
        raise RuntimeError("M33 final result already exists; the single training run cannot be repeated.")
    authorization = _authorize(config)
    gt, params = load_frozen_gt(ROOT / config["frozen_inputs"]["gt_path"])
    with np.load(ROOT / config["frozen_inputs"]["diagnostic_dataset"], allow_pickle=False) as archive:
        arrays = {key: np.asarray(archive[key]) for key in archive.files}
    torch.manual_seed(int(config["training"]["seed"]))
    model = _build(config, params, float(gt["t"][-1])).float()
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["training"]["learning_rate"]))
    al = config["training"]["augmented_lagrangian"]
    groups = list(al["groups"])
    multipliers = {name: float(al["initial_multiplier"]) for name in groups}
    penalties = {name: float(al["initial_penalty"]) for name in groups}
    update_frequency = int(al["update_frequency_steps"])
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    step = 0
    last_gradient_norm: float | None = None

    first_key = config["training"]["feasibility_stage"]["causal_schedule"][0]["dataset_key"]
    initial_t = torch.as_tensor(arrays[first_key], dtype=torch.float32)
    initial_ledger = torch.as_tensor(arrays["ledger_t"][arrays["ledger_t"][:, 0] <= 0.25], dtype=torch.float32)
    history.append(_snapshot(model, initial_t, initial_ledger, multipliers, penalties, step=0, stage="feasibility", fraction=0.25, gradient_norm=None, elapsed_s=0.0))

    def train_block(train_t: torch.Tensor, ledger_t: torch.Tensor, count: int, stage: str, fraction: float) -> None:
        nonlocal step, last_gradient_norm
        for _ in range(count):
            optimizer.zero_grad(set_to_none=True)
            constraint_groups = grouped_constraint_tensors(model, train_t, ledger_t)
            norms = _group_norms(constraint_groups)
            loss = _augmented_loss(norms, multipliers, penalties, coupled=stage == "coupled")
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite M33 loss at step {step}.")
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), float(config["training"]["gradient_clip_norm"]))
            if not torch.isfinite(gradient_norm):
                raise RuntimeError(f"Non-finite M33 gradient at step {step}.")
            optimizer.step()
            step += 1
            last_gradient_norm = float(gradient_norm)
            if step % update_frequency == 0:
                detached = {name: float(value.detach().cpu()) for name, value in norms.items()}
                for name in groups:
                    multipliers[name] = min(float(al["multiplier_cap"]), multipliers[name] + penalties[name] * detached[name])
                    penalties[name] = min(float(al["penalty_cap"]), penalties[name] * float(al["penalty_growth"]))
                history.append(_snapshot(model, train_t, ledger_t, multipliers, penalties, step=step, stage=stage, fraction=fraction, gradient_norm=last_gradient_norm, elapsed_s=time.perf_counter() - started))

    for stage in config["training"]["feasibility_stage"]["causal_schedule"]:
        fraction = float(stage["t_norm_max"])
        train_t = torch.as_tensor(arrays[stage["dataset_key"]], dtype=torch.float32)
        ledger_t = torch.as_tensor(arrays["ledger_t"][arrays["ledger_t"][:, 0] <= fraction], dtype=torch.float32)
        train_block(train_t, ledger_t, int(stage["steps"]), "feasibility", fraction)
    coupled = config["training"]["coupled_stage"]
    train_t = torch.as_tensor(arrays[coupled["dataset_key"]], dtype=torch.float32)
    ledger_t = torch.as_tensor(arrays["ledger_t"], dtype=torch.float32)
    train_block(train_t, ledger_t, int(coupled["total_steps"]), "coupled", 1.0)
    if step != int(config["training"]["total_steps"]):
        raise RuntimeError(f"M33 step count mismatch: {step}")

    history_path = ROOT / config["outputs"]["history"]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_payload = {
        "schema_version": "m33_mixed_flux_training_history_v1",
        "stage_id": config["stage_id"],
        "seed": int(config["training"]["seed"]),
        "optimizer": "Adam",
        "total_steps": step,
        "records": history,
        "final_multipliers": multipliers,
        "final_penalties": penalties,
        "post_result_changes": [],
    }
    history_path.write_text(json.dumps(history_payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")

    metrics, gates, comparison, comparison_rows = _evaluate(model, gt, params, arrays, config)
    checkpoint_path = ROOT / config["outputs"]["checkpoint"]
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": "m33_mixed_flux_checkpoint_v1",
            "model_state_dict": model.state_dict(),
            "seed": int(config["training"]["seed"]),
            "steps": step,
            "multipliers": multipliers,
            "penalties": penalties,
            "preregistration_commit": authorization["preregistration_commit"],
        },
        checkpoint_path,
    )
    comparison_path = ROOT / config["outputs"]["comparison"]
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "v3r_post_adam", "m33", "delta", "no_worse"])
        writer.writeheader()
        writer.writerows(comparison_rows)
    all_pass = bool(gates["all_pass"])
    result = {
        "schema_version": "m33_mixed_flux_final_summary_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": config["base_snapshot"],
        "preregistration_commit": authorization["preregistration_commit"],
        "authorization": authorization,
        "preflight_all_pass": True,
        "training_executed": True,
        "training_seed": int(config["training"]["seed"]),
        "training_steps": step,
        "training_budget_ratio_to_v3r": step / float(config["baseline_contract"]["adam_steps"]),
        "optimizer": "Adam",
        "continuation_used": False,
        "port_labels_used": [],
        "hidden_field_labels_used": [],
        "N1_N2_N3_SID_EC_OQ_or_SCIS_run": False,
        "external_13v_access": False,
        "contract": model.contract(),
        "metrics": metrics,
        "gates": gates,
        "comparison_to_v3r": comparison,
        "history_path": config["outputs"]["history"],
        "history_raw_sha256": raw_sha256(history_path),
        "checkpoint": config["outputs"]["checkpoint"],
        "checkpoint_sha256": raw_sha256(checkpoint_path),
        "checkpoint_size_bytes": checkpoint_path.stat().st_size,
        "wall_clock_s": time.perf_counter() - started,
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "status": "qualified_supported" if all_pass else "failed_but_informative",
        "positive_forward_claim_allowed": all_pass,
        "failure_interpretation": None if all_pass else "At least one unchanged v3r, explicit mixed-flux, ledger, or no-regression gate failed; one seed only and no post-result repair is allowed.",
    }
    final_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m33_feasibility_first_mixed_flux.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(config_path)
    print(json.dumps({"status": result["status"], "all_pass": result["gates"]["all_pass"], "steps": result["training_steps"], "wall_clock_s": result["wall_clock_s"]}))


if __name__ == "__main__":
    main()

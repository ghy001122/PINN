"""Conditional, data-free training for the preregistered N0-CV-E v3 model."""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from pinnpcm.pinn.full_pinn_n0_cv_e import (
    ControlVolumeFullPINN,
    control_volume_residuals,
    differentiable_ledger_residuals,
    hard_constraint_metrics,
)
from pinnpcm.pinn.n0_cv_evidence import (
    common_cv_score,
    load_frozen_gt,
    raw_sha256,
    stable_file_hash,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_model(
    config: Mapping[str, Any], params: Mapping[str, Any], duration_s: float, seed: int
) -> ControlVolumeFullPINN:
    architecture = config["architecture"]
    return ControlVolumeFullPINN(
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


def validate_authorization(config: Mapping[str, Any]) -> dict[str, Any]:
    lock_path = ROOT / config["outputs"]["preregistration"]
    preflight_path = ROOT / config["outputs"]["preflight"]
    if not lock_path.exists() or not preflight_path.exists():
        raise RuntimeError("Preregistration and preflight are required before training.")
    lock = _load_json(lock_path)
    preflight = _load_json(preflight_path)
    mismatches = {}
    for relative, expected in lock["locked_files"].items():
        actual = stable_file_hash(ROOT / relative)
        if actual != expected:
            mismatches[relative] = {"expected": expected, "actual": actual}
    authorized = bool(preflight.get("all_pass") and preflight.get("training_authorized") and not mismatches)
    result = {
        "authorized": authorized,
        "preflight_status": preflight.get("status"),
        "preflight_raw_sha256": raw_sha256(preflight_path),
        "preregistration_raw_sha256": raw_sha256(lock_path),
        "hash_mismatches": mismatches,
    }
    if not authorized:
        raise RuntimeError(f"Training authorization failed closed: {result}")
    return result


def _loss_blocks(
    model: ControlVolumeFullPINN,
    train_t: torch.Tensor,
    ledger_t: torch.Tensor,
) -> dict[str, torch.Tensor]:
    residuals = control_volume_residuals(model, train_t)
    ledgers = differentiable_ledger_residuals(model, ledger_t)
    return {
        "r_c": torch.mean(residuals["r_c"].square()),
        "r_T": torch.mean(residuals["r_T"].square()),
        "r_m": torch.mean(residuals["r_m"].square()),
        "discrete_electrical": torch.mean(residuals["discrete_electrical"].square()),
        "defect_mass_ledger": torch.mean(ledgers["defect_mass_ledger"].square()),
        "energy_ledger": torch.mean(ledgers["energy_ledger"].square()),
    }


def _weighted_total(blocks: Mapping[str, torch.Tensor], weights: Mapping[str, float]) -> torch.Tensor:
    return torch.stack([float(weights[key]) * value for key, value in blocks.items()]).sum()


def _gradient_statistics(
    model: ControlVolumeFullPINN, blocks: Mapping[str, torch.Tensor]
) -> dict[str, Any]:
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    vectors: dict[str, torch.Tensor] = {}
    norms: dict[str, float] = {}
    for name, loss in blocks.items():
        gradients = torch.autograd.grad(
            loss, parameters, retain_graph=True, create_graph=False, allow_unused=True
        )
        flat = torch.cat(
            [
                torch.zeros_like(parameter).reshape(-1) if gradient is None else gradient.detach().reshape(-1)
                for parameter, gradient in zip(parameters, gradients, strict=True)
            ]
        )
        vectors[name] = flat
        norms[name] = float(torch.linalg.vector_norm(flat).cpu())
    cosine: dict[str, dict[str, float]] = {}
    negative = []
    for first, first_vector in vectors.items():
        cosine[first] = {}
        for second, second_vector in vectors.items():
            denominator = torch.linalg.vector_norm(first_vector) * torch.linalg.vector_norm(second_vector)
            value = float(
                (torch.dot(first_vector, second_vector) / denominator).cpu()
            ) if float(denominator) > 0.0 else 0.0
            cosine[first][second] = value
            if first < second and value < 0.0:
                negative.append({"first": first, "second": second, "cosine": value})
    return {"gradient_norms": norms, "cosine_matrix": cosine, "negative_pairs": negative}


def _balancing_weights(
    base_weights: Mapping[str, float], statistics: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, float]:
    norms = statistics["gradient_norms"]
    positive = [value for value in norms.values() if value > 1.0e-30 and math.isfinite(value)]
    reference = float(np.median(positive)) if positive else 1.0
    lower, upper = [float(value) for value in config["training"]["gradient_statistics_balancing_arm"]["weight_clip"]]
    return {
        key: float(np.clip(reference / max(norms[key], 1.0e-30), lower, upper)) * float(base_weights[key])
        for key in base_weights
    }


def _snapshot(
    model: ControlVolumeFullPINN,
    train_t: torch.Tensor,
    eval_t: torch.Tensor,
    ledger_t: torch.Tensor,
    weights: Mapping[str, float],
    epoch: int,
    stage: str,
) -> dict[str, Any]:
    train_blocks = _loss_blocks(model, train_t, ledger_t)
    eval_residuals = control_volume_residuals(model, eval_t)
    statistics = _gradient_statistics(model, train_blocks)
    with torch.no_grad():
        states = model.dynamic_states(eval_t)
    return {
        "epoch": epoch,
        "stage": stage,
        "block_losses": {key: float(value.detach().cpu()) for key, value in train_blocks.items()},
        "weighted_total_loss": float(_weighted_total(train_blocks, weights).detach().cpu()),
        "eval_residual_rms": {
            key: float(torch.sqrt(torch.mean(eval_residuals[key].detach().square())).cpu())
            for key in ("r_c", "r_T", "r_m", "discrete_electrical")
        },
        "variable_ranges": {
            key: [float(torch.min(value).cpu()), float(torch.max(value).cpu())]
            for key, value in states.items()
        },
        **statistics,
    }


def _model_trajectory(model: ControlVolumeFullPINN, gt: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    t = np.asarray(gt["t"], dtype=float)
    t_norm = torch.as_tensor((t / t[-1])[:, None], dtype=torch.float32)
    model.eval()
    with torch.no_grad():
        output = model(t_norm)
    return {
        "x": np.asarray(gt["x"], dtype=float).copy(),
        "t": t.copy(),
        "V": np.asarray(gt["V"], dtype=float).copy(),
        "c_v": output["c_v"].cpu().numpy(),
        "T": output["T"].cpu().numpy(),
        "m": output["m"].cpu().numpy(),
    }


def _evaluate(
    model: ControlVolumeFullPINN,
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    config: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    eval_t = torch.as_tensor(arrays["eval_t"], dtype=torch.float32)
    residuals = control_volume_residuals(model, eval_t)
    cv_rms = {
        key: float(torch.sqrt(torch.mean(residuals[key].detach().square())).cpu())
        for key in ("r_c", "r_T", "r_m")
    }
    electrical_rms = float(
        torch.sqrt(torch.mean(residuals["discrete_electrical"].detach().square())).cpu()
    )
    trajectory = _model_trajectory(model, gt)
    common = common_cv_score(trajectory, gt, dict(params), config["dimensionless_registry"])
    constraints = hard_constraint_metrics(model, eval_t[:32])
    metrics = {
        "cv_residual_rms": cv_rms,
        "discrete_electrical_rms": electrical_rms,
        "port_full_trace_nrmse95": common["port_full_trace_nrmse95"],
        "field_score_only_nrmse95": common["field_score_only_nrmse95"],
        "interface_state_rms": common["interface_state_rms"],
        "interface_flux_rms": common["interface_flux_rms"],
        "terminal_current_conservation_normalized_error": common[
            "terminal_current_conservation_normalized_error"
        ],
        "global_energy_ledger": common["global_energy_ledger"],
        "defect_mass_ledger": common["defect_mass_ledger"],
        "ic_bc_normalized_errors": constraints,
        "finite_outputs": common["finite_outputs"],
        "bounded_states": common["bounded_states"],
        "region_diagnostics": common["region_diagnostics"],
        "common_scale_normalization": common["normalization"],
    }
    gates = config["result_gates"]
    numeric_interface_flux = [
        value for value in metrics["interface_flux_rms"].values() if isinstance(value, (int, float))
    ]
    checks = {
        "port": metrics["port_full_trace_nrmse95"] <= float(gates["port_full_trace_nrmse95_max"]),
        "cv_residuals": all(value <= float(gates["residual_rms_max"]) for value in cv_rms.values()),
        "discrete_electrical": electrical_rms <= float(gates["discrete_electrical_rms_max"]),
        "fields": all(
            value <= float(gates["field_score_only_nrmse95_max"])
            for value in metrics["field_score_only_nrmse95"].values()
        ),
        "interface_state": all(
            value <= float(gates["interface_state_rms_max"])
            for value in metrics["interface_state_rms"].values()
        ),
        "interface_flux": all(
            value <= float(gates["interface_flux_rms_max"]) for value in numeric_interface_flux
        ),
        "current_conservation": metrics["terminal_current_conservation_normalized_error"]
        <= float(gates["terminal_current_conservation_max"]),
        "energy_ledger": metrics["global_energy_ledger"]["gate_value"]
        <= float(gates["global_energy_imbalance_max"]),
        "defect_ledger": metrics["defect_mass_ledger"]["gate_value"]
        <= float(gates["defect_mass_ledger_max"]),
        "ic_bc": max(constraints.values()) <= float(gates["result_ic_bc_max_normalized_error"]),
        "finite_outputs": bool(metrics["finite_outputs"]),
        "bounded_states": bool(metrics["bounded_states"]),
        "hash_and_operator": bool(authorization["authorized"]),
    }
    return metrics, {"checks": checks, "all_pass": all(checks.values())}


def _run_arm(
    *,
    config: Mapping[str, Any],
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    seed: int,
    arm: str,
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    torch.manual_seed(int(seed))
    model = _build_model(config, params, float(gt["t"][-1]), seed).float()
    training = config["training"]
    base_weights = {key: float(value) for key, value in training["loss_weights"].items()}
    initial_train = torch.as_tensor(arrays["train_t_stage_025"], dtype=torch.float32)
    initial_ledger = torch.as_tensor(
        arrays["ledger_t"][arrays["ledger_t"][:, 0] <= 0.25], dtype=torch.float32
    )
    initial_blocks = _loss_blocks(model, initial_train, initial_ledger)
    initial_statistics = _gradient_statistics(model, initial_blocks)
    weights = (
        base_weights
        if arm == "primary_equal_weight"
        else _balancing_weights(base_weights, initial_statistics, config)
    )
    history = [
        _snapshot(
            model,
            initial_train,
            torch.as_tensor(arrays["eval_t"], dtype=torch.float32),
            initial_ledger,
            weights,
            0,
            "025",
        )
    ]
    optimizer = torch.optim.Adam(model.parameters(), lr=float(training["learning_rate"]))
    started = time.perf_counter()
    epoch_total = 0
    eval_t = torch.as_tensor(arrays["eval_t"], dtype=torch.float32)
    for stage in training["causal_stages"]:
        fraction = float(stage["t_norm_max"])
        label = f"{int(fraction * 100):03d}"
        train_t = torch.as_tensor(arrays[f"train_t_stage_{label}"], dtype=torch.float32)
        ledger_subset = arrays["ledger_t"][arrays["ledger_t"][:, 0] <= fraction]
        ledger_t = torch.as_tensor(ledger_subset, dtype=torch.float32)
        for _ in range(int(stage["epochs"])):
            optimizer.zero_grad(set_to_none=True)
            blocks = _loss_blocks(model, train_t, ledger_t)
            loss = _weighted_total(blocks, weights)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite N0-CV-E loss at epoch {epoch_total}.")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), max_norm=float(training["gradient_clip_norm"])
            )
            optimizer.step()
            epoch_total += 1
        history.append(_snapshot(model, train_t, eval_t, ledger_t, weights, epoch_total, label))

    lbfgs_calls = 0
    if bool(training["lbfgs"]["enabled"]):
        final_train = torch.as_tensor(arrays["train_t_stage_100"], dtype=torch.float32)
        final_ledger = torch.as_tensor(arrays["ledger_t"], dtype=torch.float32)
        lbfgs = torch.optim.LBFGS(
            model.parameters(),
            max_iter=int(training["lbfgs"]["max_iter"]),
            history_size=int(training["lbfgs"]["history_size"]),
            tolerance_grad=float(training["lbfgs"]["tolerance_grad"]),
            tolerance_change=float(training["lbfgs"]["tolerance_change"]),
            line_search_fn="strong_wolfe",
        )

        def closure() -> torch.Tensor:
            nonlocal lbfgs_calls
            lbfgs.zero_grad(set_to_none=True)
            blocks = _loss_blocks(model, final_train, final_ledger)
            loss = _weighted_total(blocks, weights)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite N0-CV-E L-BFGS loss.")
            loss.backward()
            lbfgs_calls += 1
            return loss

        lbfgs.step(closure)
        history.append(_snapshot(model, final_train, eval_t, final_ledger, weights, epoch_total, "lbfgs"))

    metrics, gates = _evaluate(model, gt, params, arrays, config, authorization)
    checkpoint_dir = ROOT / config["outputs"]["checkpoint_dir"]
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"{arm}_seed_{seed}.pt"
    torch.save(
        {
            "schema_version": "n0_cv_e_v3_checkpoint_v1",
            "model_state_dict": model.state_dict(),
            "seed": int(seed),
            "arm": arm,
            "epochs": epoch_total,
            "weights": weights,
            "preregistration_raw_sha256": authorization["preregistration_raw_sha256"],
            "preflight_raw_sha256": authorization["preflight_raw_sha256"],
        },
        checkpoint_path,
    )
    initial_loss = history[0]["weighted_total_loss"]
    final_loss = history[-1]["weighted_total_loss"]
    optimization_pathology = bool(
        not gates["all_pass"]
        and metrics["finite_outputs"]
        and math.isfinite(final_loss)
        and final_loss < initial_loss
        and history[-1]["negative_pairs"]
    )
    return {
        "seed": int(seed),
        "arm": arm,
        "status": "pilot_pass" if gates["all_pass"] else "gate_fail",
        "training_semantics": "data_free_solver_exact_CV_and_ledger_only",
        "port_labels_used": [],
        "hidden_field_labels_used": [],
        "score_only_fields_used_after_training": ["phi", "c_v", "T", "m", "sigma"],
        "parameter_count": model.parameter_count(),
        "epochs": epoch_total,
        "lbfgs_optimizer_instances": 1 if bool(training["lbfgs"]["enabled"]) else 0,
        "lbfgs_closure_calls": lbfgs_calls,
        "loss_weights": weights,
        "initial_gradient_statistics": initial_statistics,
        "history": history,
        "metrics": metrics,
        "gates": gates,
        "optimization_pathology_eligible_for_balancing_arm": optimization_pathology,
        "wall_clock_s": time.perf_counter() - started,
        "checkpoint": str(checkpoint_path.relative_to(ROOT)).replace("\\", "/"),
        "checkpoint_sha256": raw_sha256(checkpoint_path),
        "checkpoint_size_bytes": checkpoint_path.stat().st_size,
    }


def _checkpoint_manifest(results: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    rows = []
    for result in results:
        path = ROOT / result["checkpoint"]
        rows.append(
            {
                "path": result["checkpoint"],
                "sha256": raw_sha256(path),
                "size_bytes": path.stat().st_size,
                "retrieval": "tracked_repository_file" if path.stat().st_size <= 1_000_000 else "local_artifact_only",
                "include_in_version_control": path.stat().st_size <= 1_000_000,
            }
        )
    payload = {"schema_version": "n0_cv_e_v3_checkpoint_manifest_v1", "checkpoints": rows}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return payload


def run(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    authorization = validate_authorization(config)
    gt, params = load_frozen_gt(ROOT / config["frozen_inputs"]["gt_path"])
    with np.load(ROOT / config["diagnostics"]["dataset_path"], allow_pickle=False) as archive:
        arrays = {key: np.asarray(archive[key]) for key in archive.files}
    pilot_seed = int(config["training"]["seed"])
    primary = _run_arm(
        config=config,
        gt=gt,
        params=params,
        arrays=arrays,
        seed=pilot_seed,
        arm="primary_equal_weight",
        authorization=authorization,
    )
    arms = [primary]
    selected = primary
    balancing_run = False
    if (
        not primary["gates"]["all_pass"]
        and primary["optimization_pathology_eligible_for_balancing_arm"]
        and bool(config["training"]["gradient_statistics_balancing_arm"]["preregistered"])
    ):
        balancing_run = True
        balanced = _run_arm(
            config=config,
            gt=gt,
            params=params,
            arrays=arrays,
            seed=pilot_seed,
            arm="gradient_statistics_balanced",
            authorization=authorization,
        )
        arms.append(balanced)
        if balanced["gates"]["all_pass"]:
            selected = balanced

    expanded: list[dict[str, Any]] = []
    if selected["gates"]["all_pass"]:
        for seed in config["training"]["expansion_seeds"]:
            expanded.append(
                _run_arm(
                    config=config,
                    gt=gt,
                    params=params,
                    arrays=arrays,
                    seed=int(seed),
                    arm=selected["arm"],
                    authorization=authorization,
                )
            )
    all_selected_seed_results = [selected, *expanded]
    passing = sum(result["gates"]["all_pass"] for result in all_selected_seed_results)
    total_required = int(config["result_gates"]["total_seeds"])
    minimum = int(config["result_gates"]["minimum_passing_seeds"])
    seed_vote = {
        "pilot_complete_pass_required_before_expansion": True,
        "pilot_passed": selected["gates"]["all_pass"],
        "expansion_run": bool(expanded),
        "passing_seeds": int(passing),
        "evaluated_seeds": len(all_selected_seed_results),
        "minimum_passing_seeds": minimum,
        "total_seeds": total_required,
        "all_metrics_must_pass_within_seed": True,
        "overall_pass": bool(
            len(all_selected_seed_results) == total_required and passing >= minimum
        ),
    }
    all_results = [*arms, *expanded]
    manifest = _checkpoint_manifest(
        all_results, ROOT / config["outputs"]["checkpoint_manifest"]
    )
    return {
        "schema_version": "n0_cv_e_v3_training_v1",
        "stage_id": "N0-CV-E-v3-training",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": config["base_commit"],
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "authorization": authorization,
        "primary": primary,
        "balancing_arm_run": balancing_run,
        "arms": arms,
        "selected_pilot_arm": selected["arm"],
        "selected_pilot": selected,
        "expanded_seed_results": expanded,
        "seed_vote": seed_vote,
        "checkpoint_manifest": manifest,
        "sparse_anchor_run": False,
        "N1_N3_or_SC_LOS_run": False,
        "status": "qualified_supported" if seed_vote["overall_pass"] else "failed_but_informative",
        "positive_forward_claim_allowed": seed_vote["overall_pass"],
        "stop_reason": None
        if seed_vote["overall_pass"]
        else "Pilot failed at least one complete preregistered gate; seed expansion and sparse anchor remain blocked.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/full_pinn_n0_cv_e_v3.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    payload = run(config_path)
    config = _load_yaml(config_path)
    output = ROOT / config["outputs"]["pilot_result"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if payload["expanded_seed_results"]:
        expanded_output = ROOT / config["outputs"]["expanded_result"]
        expanded_output.write_text(
            json.dumps(
                {
                    "schema_version": "n0_cv_e_v3_all_seeds_v1",
                    "selected_pilot": payload["selected_pilot"],
                    "expanded_seed_results": payload["expanded_seed_results"],
                    "seed_vote": payload["seed_vote"],
                },
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "pilot_pass": payload["selected_pilot"]["gates"]["all_pass"],
                "balancing_arm_run": payload["balancing_arm_run"],
                "seed_expansion_run": payload["seed_vote"]["expansion_run"],
            }
        )
    )


if __name__ == "__main__":
    main()

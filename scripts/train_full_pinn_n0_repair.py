"""Preregister, train, diagnose, and route the bounded N0-R repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.full_pinn_1d_split import DualDomainFullPINN1D
from pinnpcm.pinn.full_residuals_1d_split import (
    compute_boundary_terms,
    compute_domain_residuals,
    compute_exact_interface_terms,
    layer_residual_scales,
)
from pinnpcm.pinn.n0_diagnostics import (
    diagnose_split_model,
    evaluate_repair_gates,
    fixed_points_content_sha256,
    generate_fixed_points,
    gradient_diagnostics,
    save_fixed_points,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _locked_paths(config_path: Path, config: dict[str, Any], points_path: Path) -> list[Path]:
    return [
        config_path,
        ROOT / config["frozen_gt_path"],
        ROOT / config["frozen_gt_config"],
        ROOT / config["baseline_config"],
        ROOT / "src/pinnpcm/physics/gt_solver.py",
        ROOT / "src/pinnpcm/physics/params.py",
        ROOT / "src/pinnpcm/physics/conductivity.py",
        ROOT / "src/pinnpcm/physics/electrostatics.py",
        ROOT / "src/pinnpcm/pinn/full_pinn_1d_split.py",
        ROOT / "src/pinnpcm/pinn/full_residuals_1d_split.py",
        ROOT / "src/pinnpcm/pinn/n0_compatibility.py",
        ROOT / "src/pinnpcm/pinn/n0_diagnostics.py",
        ROOT / "scripts/audit_n0_teacher_equation_compatibility.py",
        ROOT / "scripts/diagnose_full_pinn_n0.py",
        ROOT / "scripts/train_full_pinn_n0_repair.py",
        ROOT / "outputs/tables/n0_teacher_equation_compatibility_v1.json",
        ROOT / "outputs/tables/n0_global_conservation_audit_v1.json",
        points_path,
    ]


def _hash_manifest(paths: list[Path]) -> dict[str, str]:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Cannot lock missing files: {missing}")
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in paths
    }


def create_preregistration_lock(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    compatibility_path = ROOT / "outputs/tables/n0_teacher_equation_compatibility_v1.json"
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    if compatibility.get("status") != "repair_authorized":
        raise RuntimeError("Compatibility audit did not authorize repair training.")
    points = generate_fixed_points(config)
    points_path = ROOT / config["diagnostics"]["saved_points_path"]
    point_record = save_fixed_points(points, points_path)
    manifest = _hash_manifest(_locked_paths(config_path, config, points_path))
    baseline_checkpoint = ROOT / config["baseline_checkpoint"]
    if not baseline_checkpoint.exists():
        raise FileNotFoundError("Reproduced baseline checkpoint is required before preregistration.")
    payload = {
        "schema_version": "full_pinn_n0_repair_v2_preregistration",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": bool(_git(["status", "--short"])),
        "git_diff_sha256": _hash_text(_git(["diff", "--binary", "--", "."])),
        "config_path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256_file(config_path),
        "fixed_points": point_record,
        "baseline_checkpoint_sha256": sha256_file(baseline_checkpoint),
        "locked_file_sha256": manifest,
        "locked_gates": config["gates"],
        "locked_training": config["training"],
        "locked_normalization": config["normalization"],
        "locked_sparse_anchor": config["sparse_port_anchor_ablation"],
        "compatibility_audit_sha256": sha256_file(compatibility_path),
        "status": "locked_before_repair_training",
    }
    output = ROOT / config["outputs"]["preregistration_lock"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def validate_preregistration_lock(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    lock_path = ROOT / config["outputs"]["preregistration_lock"]
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if sha256_file(config_path) != lock["config_sha256"]:
        raise RuntimeError("Preregistered config hash changed after lock creation.")
    points = generate_fixed_points(config)
    if fixed_points_content_sha256(points) != lock["fixed_points"]["content_sha256"]:
        raise RuntimeError("Fixed diagnostic point content changed after lock creation.")
    points_path = ROOT / config["diagnostics"]["saved_points_path"]
    current = _hash_manifest(_locked_paths(config_path, config, points_path))
    if current != lock["locked_file_sha256"]:
        changed = sorted(key for key in set(current) | set(lock["locked_file_sha256"]) if current.get(key) != lock["locked_file_sha256"].get(key))
        raise RuntimeError(f"Locked scientific files changed before training: {changed}")
    return lock


def _build_model(config: dict[str, Any], params: dict[str, Any], duration: float, seed: int) -> DualDomainFullPINN1D:
    architecture = config["architecture"]
    return DualDomainFullPINN1D(
        params=params,
        t_max_s=duration,
        hidden_dim_per_domain=int(architecture["hidden_dim_per_domain"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        voltage_scale_v=float(architecture["voltage_scale_V"]),
        temperature_scale_k=float(architecture["temperature_scale_K"]),
        seed=seed,
    ).cpu()


def _tensor_points(points: dict[str, np.ndarray]) -> dict[str, torch.Tensor]:
    return {key: torch.as_tensor(value, dtype=torch.float32) for key, value in points.items()}


def _loss_blocks(
    model: DualDomainFullPINN1D,
    tensor_points: dict[str, torch.Tensor],
    stage_label: str,
    weights: dict[str, float],
) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, Any]]:
    residuals = {
        domain: compute_domain_residuals(model, tensor_points[f"train_{domain}_stage_{stage_label}"], domain)
        for domain in ("left", "right")
    }
    blocks = {
        key: torch.mean(torch.cat([residuals["left"][key], residuals["right"][key]], dim=0).square())
        for key in ("r_phi", "r_c", "r_T", "r_m")
    }
    boundary = compute_boundary_terms(model, tensor_points["boundary_t"])
    interface = compute_exact_interface_terms(model, tensor_points["interface_t"])
    blocks["endpoint_flux"] = torch.stack([torch.mean(value.square()) for value in boundary.values()]).mean()
    blocks["interface_state"] = torch.stack(
        [torch.mean(value.square()) for value in interface["state"].values()]
    ).mean()
    blocks["interface_flux"] = torch.stack(
        [torch.mean(value.square()) for value in interface["flux"].values()]
    ).mean()
    total = sum(float(weights[name]) * value for name, value in blocks.items())
    return total, blocks, {"residuals": residuals, "boundary": boundary, "interface": interface}


def _residual_rms_from_pair(pair: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(
            torch.sqrt(torch.mean(torch.cat([pair["left"][key], pair["right"][key]], dim=0).detach().square())).cpu()
        )
        for key in ("r_phi", "r_c", "r_T", "r_m")
    }


def _diagnostic_snapshot(
    model: DualDomainFullPINN1D,
    tensor_points: dict[str, torch.Tensor],
    weights: dict[str, float],
    epoch: int,
    stage_label: str,
) -> dict[str, Any]:
    total, blocks, details = _loss_blocks(model, tensor_points, stage_label, weights)
    evaluation = {
        domain: compute_domain_residuals(model, tensor_points[f"eval_{domain}"], domain)
        for domain in ("left", "right")
    }
    gradient = gradient_diagnostics(model, blocks)
    return {
        "epoch": epoch,
        "stage_label": stage_label,
        "total_loss": float(total.detach()),
        "block_losses": {key: float(value.detach()) for key, value in blocks.items()},
        "train_residual_rms": _residual_rms_from_pair(details["residuals"]),
        "heldout_residual_rms": _residual_rms_from_pair(evaluation),
        "gradient_norms": gradient["gradient_norms"],
        "gradient_cosine_matrix": gradient["cosine_matrix"],
        "negative_gradient_pairs": gradient["negative_cosine_pairs"],
    }


def _train_data_free_seed(
    config: dict[str, Any],
    params: dict[str, Any],
    gt: dict[str, np.ndarray],
    points: dict[str, np.ndarray],
    seed: int,
    lock: dict[str, Any],
) -> tuple[DualDomainFullPINN1D, dict[str, Any]]:
    torch.manual_seed(seed)
    model = _build_model(config, params, float(np.max(gt["t"])), seed)
    counts = model.parameter_counts()
    expected = int(config["architecture"]["baseline_parameter_count"])
    tolerance = float(config["architecture"]["parameter_count_relative_tolerance"])
    if abs(counts["total"] - expected) / expected > tolerance:
        raise RuntimeError("Split model violates the preregistered matched-parameter budget.")
    tensor_points = _tensor_points(points)
    weights = {key: float(value) for key, value in config["training"]["loss_weights"].items()}
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["training"]["learning_rate"]))
    history = [_diagnostic_snapshot(model, tensor_points, weights, 0, "025")]
    started = time.perf_counter()
    epoch_total = 0
    stage_labels = {0.25: "025", 0.50: "050", 0.75: "075", 1.00: "100"}

    for stage in config["training"]["causal_continuation"]["stages"]:
        fraction = float(stage["t_norm_max"])
        label = stage_labels[fraction]
        for _ in range(int(stage["epochs"])):
            optimizer.zero_grad(set_to_none=True)
            loss, _, _ = _loss_blocks(model, tensor_points, label, weights)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite data-free loss at epoch {epoch_total}.")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(config["training"]["gradient_clip_norm"]))
            optimizer.step()
            epoch_total += 1
        history.append(_diagnostic_snapshot(model, tensor_points, weights, epoch_total, label))

    lbfgs_config = config["training"]["lbfgs_tail"]
    lbfgs_calls = 0
    if bool(lbfgs_config["enabled"]):
        optimizer_lbfgs = torch.optim.LBFGS(
            model.parameters(),
            max_iter=int(lbfgs_config["max_iter"]),
            history_size=int(lbfgs_config["history_size"]),
            tolerance_grad=float(lbfgs_config["tolerance_grad"]),
            tolerance_change=float(lbfgs_config["tolerance_change"]),
            line_search_fn="strong_wolfe",
        )

        def closure() -> torch.Tensor:
            nonlocal lbfgs_calls
            optimizer_lbfgs.zero_grad(set_to_none=True)
            loss, _, _ = _loss_blocks(model, tensor_points, "100", weights)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite L-BFGS loss.")
            loss.backward()
            lbfgs_calls += 1
            return loss

        optimizer_lbfgs.step(closure)
        history.append(_diagnostic_snapshot(model, tensor_points, weights, epoch_total, "100"))

    metrics = diagnose_split_model(model, gt, points)
    gates = evaluate_repair_gates(metrics, config)
    checkpoint_dir = ROOT / config["outputs"]["checkpoint_dir"]
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"data_free_seed_{seed}.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "seed": seed,
            "epochs": epoch_total,
            "preregistration_config_sha256": lock["config_sha256"],
            "fixed_points_content_sha256": lock["fixed_points"]["content_sha256"],
        },
        checkpoint_path,
    )
    result = {
        "seed": seed,
        "status": "pilot_pass" if gates["all_pass"] else "gate_fail",
        "training_semantics": "data_free_PDE_IC_BC_exact_interface_only",
        "frozen_full_fields_semantics": "post_training_score_only",
        "parameter_counts": counts,
        "epochs": epoch_total,
        "lbfgs_optimizer_instances": 1 if bool(lbfgs_config["enabled"]) else 0,
        "lbfgs_closure_calls": lbfgs_calls,
        "wall_clock_s": time.perf_counter() - started,
        "metrics": metrics,
        "gates": gates,
        "diagnostic_history": history,
        "normalization_scales": {
            domain: layer_residual_scales(model, domain) for domain in ("left", "right")
        },
        "checkpoint": str(checkpoint_path.relative_to(ROOT)).replace("\\", "/"),
        "checkpoint_sha256": sha256_file(checkpoint_path),
    }
    return model, result


def _anchor_allowed(gates: dict[str, Any]) -> bool:
    checks = gates["checks"]
    physics_pass = all(
        checks[name]
        for name in ("heldout_residuals", "interface_flux", "current_conservation", "energy_conservation")
    )
    prediction_failure = not checks["port"] or not checks["fields"]
    return physics_pass and prediction_failure


def _sparse_anchor_loss(
    model: DualDomainFullPINN1D,
    gt: dict[str, np.ndarray],
    indices: list[int],
) -> torch.Tensor:
    x = torch.as_tensor(gt["x"] / float(model.params["L_eff"]), dtype=torch.float32)
    t = torch.as_tensor(gt["t"][indices] / float(np.max(gt["t"])), dtype=torch.float32)
    xx = x.repeat(t.numel())
    tt = t.repeat_interleave(x.numel())
    fields = model(torch.stack([xx, tt], dim=-1))
    sigma = fields["sigma"].reshape(t.numel(), x.numel())
    voltage = fields["V"].reshape(t.numel(), x.numel())[:, 0]
    port = model.port_observation(sigma, voltage)
    target_current = torch.as_tensor(gt["I"][indices], dtype=torch.float32)
    target_conductance = torch.as_tensor(gt["G"][indices], dtype=torch.float32)
    current_scale = max(float(np.sqrt(np.mean(np.square(gt["I"][indices])))), 1.0e-30)
    conductance_scale = max(float(np.sqrt(np.mean(np.square(gt["G"][indices])))), 1.0e-30)
    return 0.5 * (
        torch.mean(((port["I"] - target_current) / current_scale) ** 2)
        + torch.mean(((port["G"] - target_conductance) / conductance_scale) ** 2)
    )


def _train_sparse_anchor_once(
    model: DualDomainFullPINN1D,
    config: dict[str, Any],
    gt: dict[str, np.ndarray],
    points: dict[str, np.ndarray],
    seed: int,
) -> dict[str, Any]:
    anchor_config = config["sparse_port_anchor_ablation"]
    tensor_points = _tensor_points(points)
    weights = {key: float(value) for key, value in config["training"]["loss_weights"].items()}
    optimizer = torch.optim.Adam(model.parameters(), lr=float(anchor_config["learning_rate"]))
    indices = [int(value) for value in anchor_config["time_indices"]]
    started = time.perf_counter()
    for _ in range(int(anchor_config["additional_adam_epochs"])):
        optimizer.zero_grad(set_to_none=True)
        physics, _, _ = _loss_blocks(model, tensor_points, "100", weights)
        anchor = _sparse_anchor_loss(model, gt, indices)
        loss = physics + float(anchor_config["loss_weight"]) * anchor
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(config["training"]["gradient_clip_norm"]))
        optimizer.step()
    metrics = diagnose_split_model(model, gt, points)
    gates = evaluate_repair_gates(metrics, config)
    checkpoint_dir = ROOT / config["outputs"]["checkpoint_dir"]
    checkpoint_path = checkpoint_dir / f"sparse_anchor_seed_{seed}.pt"
    torch.save({"model_state_dict": model.state_dict(), "seed": seed, "anchor_indices": indices}, checkpoint_path)
    return {
        "seed": seed,
        "status": "pilot_pass" if gates["all_pass"] else "gate_fail",
        "training_semantics": "hybrid_sparse_port_anchored_full_pinn",
        "allowed_labels_used": ["I", "G"],
        "hidden_field_labels_used": [],
        "additional_epochs": int(anchor_config["additional_adam_epochs"]),
        "wall_clock_s": time.perf_counter() - started,
        "metrics": metrics,
        "gates": gates,
        "checkpoint": str(checkpoint_path.relative_to(ROOT)).replace("\\", "/"),
        "checkpoint_sha256": sha256_file(checkpoint_path),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _plot_training(result: dict[str, Any], path: Path) -> None:
    history = result["diagnostic_history"]
    epochs = [item["epoch"] for item in history]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for key in ("r_phi", "r_c", "r_T", "r_m"):
        axes[0].plot(epochs, [item["train_residual_rms"][key] for item in history], marker="o", label=f"train {key}")
        axes[0].plot(epochs, [item["heldout_residual_rms"][key] for item in history], marker="x", linestyle="--", label=f"eval {key}")
    axes[0].axhline(0.01, color="black", linewidth=1, linestyle=":", label="gate")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Adam epoch")
    axes[0].set_ylabel("normalized RMS")
    axes[0].set_title("Fixed train/evaluation residuals")
    axes[0].legend(fontsize=7, ncol=2)
    names = list(history[-1]["gradient_norms"])
    for name in names:
        axes[1].plot(epochs, [max(item["gradient_norms"][name], 1.0e-30) for item in history], marker="o", label=name)
    axes[1].set_yscale("log")
    axes[1].set_xlabel("Adam epoch")
    axes[1].set_ylabel("gradient norm")
    axes[1].set_title("Per-block gradient diagnostics")
    axes[1].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_gate_comparison(baseline: dict[str, Any], repair: dict[str, Any], config: dict[str, Any], path: Path) -> None:
    base = baseline["metrics"]
    repaired = repair["metrics"]
    gates = config["gates"]
    labels = ["port", "max residual", "max field", "max interface flux", "current", "energy"]
    limits = [
        float(gates["port_full_trace_nrmse95_max"]),
        float(gates["residual_rms_max"]),
        0.25,
        0.05,
        float(gates["terminal_current_conservation_max"]),
        float(gates["global_energy_account_imbalance_max"]),
    ]

    def values(metrics: dict[str, Any]) -> list[float]:
        return [
            metrics["port_full_trace_nrmse95"],
            max(metrics["heldout_residual_rms"].values()),
            max(metrics["field_score_only_nrmse95"].values()),
            max(metrics["interface_flux_rms"].values()),
            metrics["terminal_current_conservation_normalized_error"],
            metrics["global_energy_account_normalized_imbalance"],
        ]

    base_values = np.asarray(values(base)) / np.asarray(limits)
    repair_values = np.asarray(values(repaired)) / np.asarray(limits)
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.bar(x - 0.18, base_values, width=0.36, label="single-global baseline")
    ax.bar(x + 0.18, repair_values, width=0.36, label="dual-domain repair")
    ax.axhline(1.0, color="black", linestyle=":", label="operational gate")
    ax.set_yscale("log")
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("metric / gate (<=1 passes)")
    ax.set_title("N0-R controlled baseline and repair")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_bounded(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    lock = validate_preregistration_lock(config_path)
    gt_config = _load_yaml(ROOT / config["frozen_gt_config"])
    params = merge_params(gt_config.get("params"))
    with np.load(ROOT / config["frozen_gt_path"]) as archive:
        gt = {key: np.asarray(archive[key]) for key in archive.files if key != "params_json"}
    points = generate_fixed_points(config)
    seed = int(config["training"]["pilot_seed"])
    started_at = datetime.now(timezone.utc)
    model, pilot = _train_data_free_seed(config, params, gt, points, seed, lock)
    common = {
        "schema_version": "full_pinn_n0_repair_v2",
        "stage_id": "N0-R",
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": bool(_git(["status", "--short"])),
        "config_path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": lock["config_sha256"],
        "preregistration_lock_sha256": sha256_file(ROOT / config["outputs"]["preregistration_lock"]),
        "fixed_points_content_sha256": lock["fixed_points"]["content_sha256"],
        "machine_summary": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
    }
    pilot_payload = {**common, "run_role": "data_free_single_seed_MVE", "result": pilot}
    pilot_output = ROOT / config["outputs"]["data_free_pilot"]
    _write_json(pilot_output, pilot_payload)
    _plot_training(pilot, ROOT / config["outputs"]["diagnostic_figure"])

    baseline = json.loads((ROOT / config["outputs"]["baseline_diagnostics"]).read_text(encoding="utf-8"))
    _plot_gate_comparison(baseline, pilot, config, ROOT / config["outputs"]["gate_comparison_figure"])

    route: dict[str, Any] = {"data_free_pilot": pilot["status"], "anchor_run": False, "seed_expansion_run": False}
    if pilot["gates"]["all_pass"]:
        results = [pilot]
        for other_seed in [int(value) for value in config["training"]["seeds"] if int(value) != seed]:
            _, result = _train_data_free_seed(config, params, gt, points, other_seed, lock)
            results.append(result)
        passing = sum(result["gates"]["all_pass"] for result in results)
        aggregate = {
            **common,
            "run_role": "data_free_fixed_three_seeds",
            "results": results,
            "passing_seeds": passing,
            "minimum_passing_seeds": int(config["gates"]["minimum_passing_seeds"]),
            "status": "gate_pass" if passing >= int(config["gates"]["minimum_passing_seeds"]) else "gate_fail",
            "claim_status": "qualified_supported" if passing >= int(config["gates"]["minimum_passing_seeds"]) else "failed_but_informative",
        }
        _write_json(ROOT / config["outputs"]["full_seed_result"], aggregate)
        route["seed_expansion_run"] = True
        route["three_seed_status"] = aggregate["status"]
    elif _anchor_allowed(pilot["gates"]):
        anchor = _train_sparse_anchor_once(model, config, gt, points, seed)
        anchor_payload = {**common, "run_role": "conditional_sparse_port_anchor_ablation", "result": anchor}
        _write_json(ROOT / config["outputs"]["sparse_anchor_pilot"], anchor_payload)
        route["anchor_run"] = True
        route["anchor_status"] = anchor["status"]
    else:
        route["stop_reason"] = "data-free residual/interface/current/energy conditions do not authorize anchor or seed expansion"

    summary = {
        **common,
        "status": "completed_with_scientific_gate_result",
        "data_free_pilot_status": pilot["status"],
        "route": route,
        "n0_claim_status": (
            "pilot_pass_only" if pilot["gates"]["all_pass"] else "failed_but_informative"
        ),
        "n1_n3_run": False,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--create-lock", action="store_true")
    action.add_argument("--run-bounded", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    if args.create_lock:
        result = create_preregistration_lock(config_path)
        print(json.dumps({"status": result["status"], "config_sha256": result["config_sha256"], "fixed_points": result["fixed_points"]}, indent=2))
        return
    result = run_bounded(config_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

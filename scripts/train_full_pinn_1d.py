"""Train the N0 data-free full-PINN and score only after optimization."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.full_pinn_1d import FullPINN1D
from pinnpcm.pinn.full_residuals_1d import (
    compute_boundary_terms,
    compute_full_residuals,
    compute_interface_terms,
    residual_rms,
    squared_mean,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git(command: list[str]) -> str:
    result = subprocess.run(["git", *command], check=False, capture_output=True, text=True)
    return result.stdout.strip()


def _nrmse95(prediction: np.ndarray, target: np.ndarray) -> float:
    scale = max(float(np.quantile(target, 0.95) - np.quantile(target, 0.05)), 1.0e-30)
    return float(np.sqrt(np.mean((prediction - target) ** 2)) / scale)


def _sample_interior(count: int, interface: float, exclusion: float, generator: torch.Generator) -> torch.Tensor:
    points: list[torch.Tensor] = []
    remaining = int(count)
    while remaining > 0:
        candidate = torch.rand((remaining * 2, 2), generator=generator)
        keep = torch.abs(candidate[:, 0] - interface) >= exclusion
        accepted = candidate[keep][:remaining]
        points.append(accepted)
        remaining -= accepted.shape[0]
    return torch.cat(points, dim=0)


def _build_model(config: dict[str, Any], params: dict[str, Any], duration: float, seed: int) -> FullPINN1D:
    architecture = config["architecture"]
    return FullPINN1D(
        params=params,
        t_max_s=duration,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        voltage_scale_v=float(architecture["voltage_scale_V"]),
        temperature_scale_k=float(architecture["temperature_scale_K"]),
        seed=seed,
    )


def _score(model: FullPINN1D, gt: dict[str, np.ndarray], generator: torch.Generator) -> dict[str, Any]:
    x = torch.as_tensor(gt["x"] / float(model.params["L_eff"]), dtype=torch.float32)
    t = torch.as_tensor(gt["t"] / float(np.max(gt["t"])), dtype=torch.float32)
    xx = x.repeat(t.numel())
    tt = t.repeat_interleave(x.numel())
    coords = torch.stack([xx, tt], dim=-1)
    with torch.no_grad():
        fields = model(coords)
        nt, nx = t.numel(), x.numel()
        sigma = fields["sigma"].reshape(nt, nx)
        voltage = fields["V"].reshape(nt, nx)[:, 0]
        port = model.port_observation(sigma, voltage)
        prediction = {key: fields[key].reshape(nt, nx).cpu().numpy() for key in ("c_v", "T", "m", "phi", "sigma")}
        current = port["I"].cpu().numpy()

    interface = float(model.params["L_int"]) / float(model.params["L_eff"])
    residual_coords = _sample_interior(512, interface, 0.01, generator)
    residuals = compute_full_residuals(model, residual_coords)
    rms = residual_rms(residuals)
    finite = bool(np.all(np.isfinite(current))) and all(np.all(np.isfinite(value)) for value in prediction.values())
    physical = bool(
        np.min(prediction["T"]) > 0.0
        and np.min(prediction["c_v"]) >= 0.0
        and np.max(prediction["c_v"]) <= 1.0
        and np.min(prediction["m"]) >= 0.0
        and np.max(prediction["m"]) <= 1.0
    )
    return {
        "port_full_trace_nrmse95": _nrmse95(current, np.asarray(gt["I"])),
        "field_score_only_nrmse95": {
            key: _nrmse95(prediction[key], np.asarray(gt[key])) for key in ("c_v", "T", "m", "phi", "sigma")
        },
        "residual_rms": rms,
        "finite_outputs": finite,
        "physical_state_bounds": physical,
        "prediction_summary": {
            "current_A_min": float(np.min(current)),
            "current_A_max": float(np.max(current)),
            "temperature_K_min": float(np.min(prediction["T"])),
            "temperature_K_max": float(np.max(prediction["T"])),
            "c_v_min": float(np.min(prediction["c_v"])),
            "c_v_max": float(np.max(prediction["c_v"])),
            "m_min": float(np.min(prediction["m"])),
            "m_max": float(np.max(prediction["m"])),
        },
    }


def train_seed(config: dict[str, Any], params: dict[str, Any], gt: dict[str, np.ndarray], seed: int, epochs: int) -> dict[str, Any]:
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    duration = float(np.max(gt["t"]))
    model = _build_model(config, params, duration, seed).cpu()
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["training"]["learning_rate"]))
    interface = float(params["L_int"]) / float(params["L_eff"])
    exclusion = float(config["training"]["interface_exclusion_fraction"])
    probe = float(config["training"]["interface_probe_fraction"])
    weights = config["training"]["loss_weights"]
    history: list[dict[str, float]] = []
    started = time.perf_counter()

    for epoch in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        coords = _sample_interior(int(config["training"]["collocation_points"]), interface, exclusion, generator)
        residuals = compute_full_residuals(model, coords)
        pde_loss = sum(float(weights[key]) * torch.mean(residuals[key].square()) for key in ("r_phi", "r_c", "r_T", "r_m"))
        t_boundary = torch.rand((int(config["training"]["boundary_points"]), 1), generator=generator)
        boundary_loss = squared_mean(compute_boundary_terms(model, t_boundary))
        t_interface = torch.rand((int(config["training"]["interface_points"]), 1), generator=generator)
        interface_loss = squared_mean(compute_interface_terms(model, t_interface, probe))
        loss = pde_loss + float(weights["boundary"]) * boundary_loss + float(weights["interface"]) * interface_loss
        if not torch.isfinite(loss):
            return {"seed": seed, "status": "numerical_failure", "epoch": epoch, "failure_reason": "nonfinite_loss"}
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=100.0)
        optimizer.step()
        if epoch == 0 or (epoch + 1) % max(1, epochs // 8) == 0 or epoch + 1 == epochs:
            history.append({
                "epoch": int(epoch + 1),
                "loss": float(loss.detach()),
                "pde_loss": float(pde_loss.detach()),
                "boundary_loss": float(boundary_loss.detach()),
                "interface_loss": float(interface_loss.detach()),
            })

    metrics = _score(model, gt, generator)
    gates = config["gates"]
    passed = (
        metrics["port_full_trace_nrmse95"] <= float(gates["port_full_trace_nrmse95_max"])
        and all(value <= float(gates["residual_rms_max"]) for value in metrics["residual_rms"].values())
        and metrics["finite_outputs"]
        and metrics["physical_state_bounds"]
    )
    checkpoint_dir = Path(config["outputs"]["checkpoint_dir"])
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_dir / f"seed_{seed}_epochs_{epochs}.pt"
    torch.save({"model_state_dict": model.state_dict(), "seed": seed, "epochs": epochs}, checkpoint)
    return {
        "seed": seed,
        "status": "gate_pass" if passed else "gate_fail",
        "epochs": epochs,
        "wall_clock_s": time.perf_counter() - started,
        "metrics": metrics,
        "training_history": history,
        "checkpoint": checkpoint.as_posix(),
        "training_data_semantics": "PDE_IC_BC_only",
        "frozen_full_fields_semantics": "post_training_score_only",
    }


def run(config_path: Path, mode: str) -> dict[str, Any]:
    config = _load_yaml(config_path)
    gt_config = _load_yaml(Path(config["frozen_gt_config"]))
    params = merge_params(gt_config.get("params"))
    with np.load(config["frozen_gt_path"]) as archive:
        gt = {key: np.asarray(archive[key]) for key in archive.files if key != "params_json"}
    seeds = [int(value) for value in config["training"]["seeds"]]
    if mode in {"pilot", "single_seed_mve"}:
        seeds = seeds[: int(config["training"]["pilot_seed_count"])]
    epochs = int(config["training"]["pilot_epochs"] if mode == "pilot" else config["training"]["full_epochs"])
    started = datetime.now(timezone.utc)
    results = [train_seed(config, params, gt, seed, epochs) for seed in seeds]
    passing = sum(item.get("status") == "gate_pass" for item in results)
    minimum = 1 if mode in {"pilot", "single_seed_mve"} else int(config["gates"]["minimum_passing_seeds"])
    if mode == "pilot":
        aggregate_status = "pilot_pass" if passing >= minimum else "pilot_fail"
    elif mode == "single_seed_mve":
        aggregate_status = "mve_pass" if passing >= minimum else "mve_fail"
    else:
        aggregate_status = "gate_pass" if passing >= minimum else "gate_fail"
    payload = {
        "schema_version": "full_pinn_training_v1",
        "stage_id": "N0",
        "run_mode": mode,
        "status": aggregate_status,
        "claim_status": "forbidden" if aggregate_status != "gate_pass" else "qualified_supported",
        "started_at_utc": started.isoformat(),
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": bool(_git(["status", "--short"])),
        "config_path": config_path.as_posix(),
        "machine_summary": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "seeds_requested": seeds,
        "passing_seeds": passing,
        "minimum_passing_seeds": minimum,
        "results": results,
        "stop_rule": "Do not expand seeds or enter N1 if the single-seed pilot fails.",
    }
    if mode == "pilot":
        output = Path(config["outputs"]["pilot_json"])
    elif mode == "single_seed_mve":
        output = Path(config["outputs"]["single_seed_mve_json"])
    else:
        output = Path(config["outputs"]["full_training_json"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--single-seed-mve", action="store_true")
    args = parser.parse_args()
    if args.pilot and args.single_seed_mve:
        parser.error("--pilot and --single-seed-mve are mutually exclusive")
    mode = "pilot" if args.pilot else "single_seed_mve" if args.single_seed_mve else "full_preregistered_seeds"
    result = run(args.config, mode)
    print(json.dumps({"status": result["status"], "passing_seeds": result["passing_seeds"], "results": result["results"]}, indent=2))
    if result["status"] in {"pilot_fail", "mve_fail", "gate_fail"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

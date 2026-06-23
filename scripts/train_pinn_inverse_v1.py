"""Train PINN inverse v1 with lightweight physics residual regularization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.pinn.data import InverseV0Data, load_inverse_v0_data
from pinnpcm.pinn.losses import normalized_mse, reconstruct_port_from_sigma, smoothness_loss
from pinnpcm.pinn.models import InverseV0Net, predict_on_grid
from pinnpcm.pinn.physics_residuals import compute_boundary_residuals, compute_physics_residuals
from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import ensure_dir, write_json
from pinnpcm.utils.seed import seed_everything

from train_pinn_inverse_v0 import DEFAULT_NRMSE_SCALES, _build_coords, _display_path, _nrmse, _relative_l2, _rmse, _tensor


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description="Train PINN inverse v1 with lightweight physics residuals.")
    parser.add_argument("--config", type=Path, default=Path("configs/pinn_inverse_v1_triangle_physics.yaml"))
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs for smoke tests.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override output directory.")
    return parser


def _select_indices(total_points: int, n_points: int, rng: np.random.Generator, device: torch.device) -> torch.Tensor:
    """Select deterministic random indices for anchors or collocation."""

    n_pick = min(max(int(n_points), 0), int(total_points))
    if n_pick == 0:
        return torch.empty(0, dtype=torch.long, device=device)
    return torch.as_tensor(rng.choice(total_points, size=n_pick, replace=False), dtype=torch.long, device=device)


def _scheduled_weights(weights: dict[str, float], epoch: int, schedule: dict[str, Any]) -> dict[str, float]:
    """Apply optional warmup scheduling to selected loss weights."""

    if not schedule.get("enabled", False):
        return dict(weights)
    warmup_epochs = max(int(schedule.get("warmup_epochs", 1)), 1)
    start_factor = float(schedule.get("start_factor", 0.1))
    factor = start_factor + (1.0 - start_factor) * min(float(epoch) / float(warmup_epochs), 1.0)
    keys = tuple(
        schedule.get(
            "warmup_keys",
            (
                "w_heat_residual",
                "w_state_residual",
                "w_defect_residual",
                "w_sigma_consistency",
                "w_boundary",
                "w_sigma_initial",
            ),
        )
    )
    scheduled = dict(weights)
    for key in keys:
        if key in scheduled:
            scheduled[key] = scheduled[key] * factor
    return scheduled


def _balanced_loss(
    name: str,
    value: torch.Tensor,
    running_scales: dict[str, float],
    balance_cfg: dict[str, Any],
) -> torch.Tensor:
    """Optionally normalize a raw loss by a running scale."""

    if not balance_cfg.get("enabled", False):
        return value
    keys = set(
        balance_cfg.get(
            "keys",
            (
                "heat_residual_loss",
                "state_residual_loss",
                "defect_residual_loss",
                "sigma_consistency_loss",
                "boundary_loss",
                "sigma_initial_loss",
            ),
        )
    )
    if name not in keys:
        return value

    detached = float(torch.clamp(value.detach(), min=0.0).cpu())
    momentum = float(balance_cfg.get("momentum", 0.95))
    previous = running_scales.get(name, detached)
    running_scales[name] = momentum * previous + (1.0 - momentum) * detached
    min_scale = float(balance_cfg.get("min_scale", 1.0e-4))
    max_scale = float(balance_cfg.get("max_scale", 1.0e6))
    scale = min(max(running_scales[name], min_scale), max_scale)
    scale_tensor = torch.as_tensor(scale, dtype=value.dtype, device=value.device)
    return value / scale_tensor


def _plot_map(path: Path, values: np.ndarray, x: np.ndarray, t: np.ndarray, title: str, colorbar: str, dpi: int) -> None:
    """Save a field map."""

    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    image = ax.imshow(
        values,
        aspect="auto",
        origin="lower",
        extent=[float(x[0] * 1.0e9), float(x[-1] * 1.0e9), float(t[0] * 1.0e6), float(t[-1] * 1.0e6)],
    )
    ax.set_xlabel("x (nm)")
    ax.set_ylabel("t (us)")
    ax.set_title(title)
    fig.colorbar(image, ax=ax, label=colorbar)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def _save_figures(
    output_dir: Path,
    history: list[dict[str, float]],
    data: InverseV0Data,
    predictions: dict[str, np.ndarray],
    port_pred: dict[str, np.ndarray],
    dpi: int,
) -> list[str]:
    """Save v1 diagnostic figures."""

    figure_paths: list[str] = []
    x = data.x
    t = data.t
    epochs = [row["epoch"] for row in history]

    loss_path = output_dir / "loss_curve.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    for key in ("total_loss", "port_loss", "ic_loss", "field_anchor_loss", "physics_loss"):
        ax.semilogy(epochs, [row[key] for row in history], label=key)
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.legend(fontsize=8)
    fig.savefig(loss_path, dpi=dpi)
    plt.close(fig)
    figure_paths.append(_display_path(loss_path))

    components_path = output_dir / "loss_components.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    for key in ("port_loss", "ic_loss", "field_anchor_loss", "smooth_loss", "boundary_loss", "sigma_initial_loss"):
        ax.semilogy(epochs, [max(row[key], 1.0e-30) for row in history], label=key)
    ax.set_xlabel("epoch")
    ax.set_ylabel("component loss")
    ax.legend(fontsize=8)
    fig.savefig(components_path, dpi=dpi)
    plt.close(fig)
    figure_paths.append(_display_path(components_path))

    residual_path = output_dir / "residual_components.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    for key in ("heat_residual_loss", "state_residual_loss", "defect_residual_loss", "sigma_consistency_loss"):
        ax.semilogy(epochs, [max(row[key], 1.0e-30) for row in history], label=key)
    ax.set_xlabel("epoch")
    ax.set_ylabel("residual loss")
    ax.legend(fontsize=8)
    fig.savefig(residual_path, dpi=dpi)
    plt.close(fig)
    figure_paths.append(_display_path(residual_path))

    for filename, values, title, colorbar in (
        ("pred_delta_T_map.png", predictions["delta_T"], "Predicted delta T", "K"),
        ("pred_delta_c_v_map.png", predictions["delta_c_v"], "Predicted delta c_v", "fraction"),
        ("pred_delta_m_map.png", predictions["delta_m"], "Predicted delta m", "fraction"),
        ("pred_sigma_map.png", predictions["sigma"], "Predicted sigma", "S/m"),
    ):
        path = output_dir / filename
        _plot_map(path, values, x, t, title, colorbar, dpi)
        figure_paths.append(_display_path(path))

    compare_path = output_dir / "compare_g_time.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    ax.plot(t * 1.0e6, np.asarray(data.gt["G"], dtype=float), label="Ground Truth G")
    ax.plot(t * 1.0e6, port_pred["G"], label="PINN v1 G")
    ax.scatter(np.asarray(data.obs["t"], dtype=float) * 1.0e6, np.asarray(data.obs["G"], dtype=float), s=24, label="Sparse G")
    ax.set_xlabel("t (us)")
    ax.set_ylabel("G (S)")
    ax.legend(fontsize=8)
    fig.savefig(compare_path, dpi=dpi)
    plt.close(fig)
    figure_paths.append(_display_path(compare_path))

    return figure_paths


def _evaluate(
    model: InverseV0Net,
    data: InverseV0Data,
    device: torch.device,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Evaluate trained v1 model on the full frozen triangle grid."""

    model.eval()
    x_norm = _tensor(data.x_norm, device)
    t_norm = _tensor(data.t_norm, device)
    pred_tensors = predict_on_grid(model, x_norm, t_norm)
    voltage = _tensor(data.gt["V"], device)
    port_tensors = reconstruct_port_from_sigma(pred_tensors["sigma"], voltage, data.dx, data.params)
    predictions = {key: value.detach().cpu().numpy() for key, value in pred_tensors.items()}
    c0 = np.asarray(data.gt["c_v"], dtype=float)[0:1, :]
    m0 = np.asarray(data.gt["m"], dtype=float)[0:1, :]
    predictions["delta_c_v"] = predictions["c_v"] - c0
    predictions["delta_m"] = predictions["m"] - m0
    port_pred = {key: value.detach().cpu().numpy() for key, value in port_tensors.items()}
    return predictions, port_pred


def train(config_path: Path, *, epochs_override: int | None = None, output_dir_override: Path | None = None) -> dict[str, Any]:
    """Train one v1 experiment and write all requested artifacts."""

    cfg = load_yaml(config_path)
    if epochs_override is not None:
        cfg["epochs"] = int(epochs_override)
    if output_dir_override is not None:
        cfg["output_dir"] = str(output_dir_override)

    seed = int(cfg.get("seed", 2026))
    seed_everything(seed)
    rng = np.random.default_rng(seed)
    data = load_inverse_v0_data(cfg, root=ROOT, verbose=True)
    output_dir = ensure_dir(data.output_dir)
    device = torch.device(str(cfg.get("device", "cpu")))

    gt_c = np.asarray(data.gt["c_v"], dtype=float)
    gt_t = np.asarray(data.gt["T"], dtype=float)
    gt_m = np.asarray(data.gt["m"], dtype=float)
    gt_sigma = np.asarray(data.gt["sigma"], dtype=float)
    gt_delta_t = gt_t - float(data.params["T0"])
    gt_delta_c = gt_c - gt_c[0:1, :]
    gt_delta_m = gt_m - gt_m[0:1, :]

    bounds = dict(cfg.get("model_bounds", {}))
    model = InverseV0Net(
        hidden_dim=int(cfg.get("hidden_dim", 64)),
        num_layers=int(cfg.get("num_layers", 3)),
        fourier_features=int(cfg.get("fourier_features", 32)),
        fourier_scale=float(cfg.get("fourier_scale", 3.0)),
        initial_c_v=float(np.mean(gt_c[0])),
        initial_m=float(np.mean(gt_m[0])),
        initial_sigma=float(np.mean(gt_sigma[0])),
        **{key: float(value) for key, value in bounds.items()},
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=float(cfg.get("lr", 1.0e-3)))
    coords = _build_coords(data, device)
    nt, nx = data.nt, data.nx
    x_scale = float(data.params["L_eff"])
    t_scale = float(data.t[-1] - data.t[0])

    voltage = _tensor(data.gt["V"], device)
    obs_t_idx = torch.as_tensor(np.asarray(data.obs["t_idx"], dtype=np.int64), dtype=torch.long, device=device)
    obs_i = _tensor(data.obs["I"], device)
    obs_g = _tensor(data.obs["G"], device)
    target_c = _tensor(gt_c, device)
    target_delta_t = _tensor(gt_delta_t, device)
    target_m = _tensor(gt_m, device)
    target_sigma_log = torch.log(torch.clamp(_tensor(gt_sigma, device), min=1.0e-30))
    target_delta_m = _tensor(gt_delta_m, device)

    weights = {key: float(value) for key, value in dict(cfg.get("loss_weights", {})).items()}
    scales = {key: float(value) for key, value in dict(cfg.get("loss_scales", {})).items()}
    physics_scales = {key: float(value) for key, value in dict(cfg.get("physics_scales", {})).items()}
    balance_cfg = dict(cfg.get("residual_balancing", {}))
    schedule_cfg = dict(cfg.get("loss_schedule", {}))
    field_anchor_weights = {key: float(value) for key, value in dict(cfg.get("field_anchor_weights", {})).items()}
    c_scale = scales.get("c_v", 1.0e-2)
    temp_scale = scales.get("delta_T", 10.0)
    m_scale = scales.get("m", 0.1)
    sigma_log_scale = scales.get("sigma_log", 1.0)
    i_scale = max(float(np.max(np.abs(np.asarray(data.obs["I"], dtype=float)))), 1.0e-30)
    g_scale = max(float(np.max(np.abs(np.asarray(data.obs["G"], dtype=float)))), 1.0e-30)

    anchor_idx = _select_indices(nt * nx, int(cfg.get("field_anchor_points", 0)), rng, device)
    n_collocation = int(cfg.get("physics_collocation_points", 512))
    n_boundary = int(cfg.get("boundary_points", 128))
    history: list[dict[str, float]] = []
    running_scales: dict[str, float] = {}
    n_epochs = int(cfg.get("epochs", 120))
    print(f"Training PINN inverse v1 for {n_epochs} epochs on {device}.")

    for epoch in range(1, n_epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)

        pred = model(coords)
        fields = {key: value.reshape(nt, nx) for key, value in pred.items()}
        port = reconstruct_port_from_sigma(fields["sigma"], voltage, data.dx, data.params)
        port_loss = normalized_mse(port["G"][obs_t_idx], obs_g, g_scale) + normalized_mse(
            port["I"][obs_t_idx], obs_i, i_scale
        )
        ic_loss = (
            normalized_mse(fields["c_v"][0], target_c[0], c_scale)
            + normalized_mse(fields["delta_T"][0], target_delta_t[0], temp_scale)
            + normalized_mse(fields["m"][0], target_m[0], m_scale)
        )

        if anchor_idx.numel() > 0 and weights.get("w_field_anchor", 0.0) != 0.0:
            flat_c = fields["c_v"].reshape(-1)
            flat_delta_t = fields["delta_T"].reshape(-1)
            flat_delta_m = (fields["m"] - target_m[0:1, :]).reshape(-1)
            flat_log_sigma = fields["log_sigma"].reshape(-1)
            field_anchor_loss = (
                field_anchor_weights.get("c_v", 1.0)
                * normalized_mse(flat_c[anchor_idx], target_c.reshape(-1)[anchor_idx], c_scale)
                + field_anchor_weights.get("delta_T", 1.0)
                * normalized_mse(flat_delta_t[anchor_idx], target_delta_t.reshape(-1)[anchor_idx], temp_scale)
                + field_anchor_weights.get("m", 1.0)
                * normalized_mse(flat_delta_m[anchor_idx], target_delta_m.reshape(-1)[anchor_idx], m_scale)
                + field_anchor_weights.get("log_sigma", 1.0)
                * normalized_mse(flat_log_sigma[anchor_idx], target_sigma_log.reshape(-1)[anchor_idx], sigma_log_scale)
            )
        else:
            field_anchor_loss = torch.zeros((), dtype=coords.dtype, device=device)

        sigma_initial_loss = normalized_mse(fields["log_sigma"][0], target_sigma_log[0], sigma_log_scale)

        smooth_loss = (
            smoothness_loss(fields["c_v"] / c_scale)
            + smoothness_loss(fields["delta_T"] / temp_scale)
            + smoothness_loss(fields["m"] / m_scale)
            + smoothness_loss(fields["log_sigma"] / sigma_log_scale)
        )

        collocation_idx = _select_indices(nt * nx, n_collocation, rng, device)
        residuals = compute_physics_residuals(
            model,
            coords[collocation_idx],
            data.params,
            x_scale=x_scale,
            t_scale=t_scale,
            physics_scales=physics_scales,
        )
        heat_loss = torch.mean(torch.square(residuals["heat_residual"]))
        state_loss = torch.mean(torch.square(residuals["state_residual"]))
        defect_loss = torch.mean(torch.square(residuals["defect_residual"]))
        sigma_consistency_loss = torch.mean(torch.square(residuals["sigma_consistency"]))

        boundary_t = torch.linspace(0.0, 1.0, max(n_boundary, 2), dtype=coords.dtype, device=device)
        boundary = compute_boundary_residuals(model, boundary_t, data.params, x_scale=x_scale, t_scale=t_scale)
        boundary_loss = torch.mean(torch.square(boundary["temperature_boundary"])) + torch.mean(
            torch.square(boundary["defect_boundary"])
        )

        scheduled = _scheduled_weights(weights, epoch, schedule_cfg)
        heat_term = _balanced_loss("heat_residual_loss", heat_loss, running_scales, balance_cfg)
        state_term = _balanced_loss("state_residual_loss", state_loss, running_scales, balance_cfg)
        defect_term = _balanced_loss("defect_residual_loss", defect_loss, running_scales, balance_cfg)
        sigma_consistency_term = _balanced_loss(
            "sigma_consistency_loss", sigma_consistency_loss, running_scales, balance_cfg
        )
        boundary_term = _balanced_loss("boundary_loss", boundary_loss, running_scales, balance_cfg)
        sigma_initial_term = _balanced_loss("sigma_initial_loss", sigma_initial_loss, running_scales, balance_cfg)

        physics_loss = (
            scheduled.get("w_heat_residual", 0.0) * heat_term
            + scheduled.get("w_state_residual", 0.0) * state_term
            + scheduled.get("w_defect_residual", 0.0) * defect_term
            + scheduled.get("w_sigma_consistency", 0.0) * sigma_consistency_term
            + scheduled.get("w_boundary", 0.0) * boundary_term
            + scheduled.get("w_sigma_initial", 0.0) * sigma_initial_term
        )
        total = (
            scheduled.get("w_port_data", 1.0) * port_loss
            + scheduled.get("w_ic", 1.0) * ic_loss
            + scheduled.get("w_field_anchor", 0.0) * field_anchor_loss
            + scheduled.get("w_smooth", 0.0) * smooth_loss
            + physics_loss
        )
        if not torch.isfinite(total):
            raise FloatingPointError("PINN inverse v1 loss became non-finite.")

        total.backward()
        optimizer.step()

        row = {
            "epoch": float(epoch),
            "total_loss": float(total.detach().cpu()),
            "port_loss": float(port_loss.detach().cpu()),
            "ic_loss": float(ic_loss.detach().cpu()),
            "field_anchor_loss": float(field_anchor_loss.detach().cpu()),
            "smooth_loss": float(smooth_loss.detach().cpu()),
            "physics_loss": float(physics_loss.detach().cpu()),
            "heat_residual_loss": float(heat_loss.detach().cpu()),
            "state_residual_loss": float(state_loss.detach().cpu()),
            "defect_residual_loss": float(defect_loss.detach().cpu()),
            "sigma_consistency_loss": float(sigma_consistency_loss.detach().cpu()),
            "boundary_loss": float(boundary_loss.detach().cpu()),
            "sigma_initial_loss": float(sigma_initial_loss.detach().cpu()),
            "w_heat_residual_effective": float(scheduled.get("w_heat_residual", 0.0)),
            "w_sigma_consistency_effective": float(scheduled.get("w_sigma_consistency", 0.0)),
        }
        history.append(row)
        if epoch == 1 or epoch == n_epochs or epoch % max(n_epochs // 10, 1) == 0:
            print(
                f"epoch {epoch:04d} total={row['total_loss']:.4e} port={row['port_loss']:.4e} "
                f"heat={row['heat_residual_loss']:.4e} sigma={row['sigma_consistency_loss']:.4e}"
            )

    predictions, port_pred = _evaluate(model, data, device)
    nrmse_cfg = {key: float(value) for key, value in dict(cfg.get("nrmse_scales", {})).items()}
    nrmse_scales = dict(DEFAULT_NRMSE_SCALES)
    nrmse_scales.update(nrmse_cfg)
    sigma_scale = nrmse_scales.get("sigma_range", nrmse_scales["sigma_max"] - nrmse_scales["sigma_min"])
    rmse_delta_t = _rmse(predictions["delta_T"], gt_delta_t)
    rmse_delta_c = _rmse(predictions["delta_c_v"], gt_delta_c)
    rmse_delta_m = _rmse(predictions["delta_m"], gt_delta_m)
    rmse_sigma = _rmse(predictions["sigma"], gt_sigma)
    metrics = {
        "final_total_loss": history[-1]["total_loss"],
        "final_port_loss": history[-1]["port_loss"],
        "relative_G_error": _relative_l2(port_pred["G"], np.asarray(data.gt["G"], dtype=float)),
        "relative_I_error": _relative_l2(port_pred["I"], np.asarray(data.gt["I"], dtype=float)),
        "rmse_delta_T": rmse_delta_t,
        "nrmse_delta_T": _nrmse(rmse_delta_t, nrmse_scales["delta_T"]),
        "rmse_delta_c_v": rmse_delta_c,
        "nrmse_delta_c_v": _nrmse(rmse_delta_c, nrmse_scales["delta_c_v"]),
        "rmse_delta_m": rmse_delta_m,
        "nrmse_delta_m": _nrmse(rmse_delta_m, nrmse_scales["delta_m"]),
        "rmse_sigma": rmse_sigma,
        "nrmse_sigma": _nrmse(rmse_sigma, sigma_scale),
        "max_abs_error_delta_T": float(np.max(np.abs(predictions["delta_T"] - gt_delta_t))),
        "max_abs_error_delta_c_v": float(np.max(np.abs(predictions["delta_c_v"] - gt_delta_c))),
        "max_abs_error_delta_m": float(np.max(np.abs(predictions["delta_m"] - gt_delta_m))),
        "final_heat_residual": history[-1]["heat_residual_loss"],
        "final_state_residual": history[-1]["state_residual_loss"],
        "final_defect_residual": history[-1]["defect_residual_loss"],
        "final_sigma_consistency": history[-1]["sigma_consistency_loss"],
        "final_sigma_initial_loss": history[-1]["sigma_initial_loss"],
        "residual_balancing": balance_cfg,
        "loss_schedule": schedule_cfg,
        "sigma_closure": "PINN inverse v1 uses a positive network sigma with approximate torch sigma-consistency regularization.",
    }
    figure_paths = _save_figures(output_dir, history, data, predictions, port_pred, int(cfg.get("plot_dpi", 160)))
    metrics["figure_paths"] = figure_paths

    write_json(
        output_dir / "train_history.json",
        {
            "config_path": str(config_path),
            "train_data": str(data.train_data_path.relative_to(ROOT)),
            "sparse_obs": str(data.sparse_obs_path.relative_to(ROOT)),
            "manifest": str(data.manifest_path.relative_to(ROOT)),
            "history": history,
        },
    )
    write_json(output_dir / "metrics.json", metrics)
    print(f"Saved train history: {_display_path(output_dir / 'train_history.json')}")
    print(f"Saved metrics: {_display_path(output_dir / 'metrics.json')}")
    return metrics


def main() -> None:
    """CLI entry point."""

    args = build_parser().parse_args()
    train(args.config, epochs_override=args.epochs, output_dir_override=args.output_dir)


if __name__ == "__main__":
    main()

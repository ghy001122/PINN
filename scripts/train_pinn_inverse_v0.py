"""Train PINN inverse v0 on frozen Ground Truth v1.1 triangle data."""

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
from pinnpcm.pinn.losses import (
    normalized_mse,
    physics_light_loss,
    reconstruct_port_from_sigma,
    smoothness_loss,
)
from pinnpcm.pinn.models import InverseV0Net, predict_on_grid
from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import ensure_dir, write_json
from pinnpcm.utils.seed import seed_everything


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description="Train PINN inverse v0 on frozen Ground Truth v1.1 data.")
    parser.add_argument("--config", type=Path, default=Path("configs/pinn_inverse_v0_triangle.yaml"))
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs for smoke tests.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override output directory.")
    return parser


def _tensor(array: Any, device: torch.device) -> torch.Tensor:
    """Convert an array-like object to a float32 tensor."""

    return torch.as_tensor(array, dtype=torch.float32, device=device)


def _relative_l2(pred: np.ndarray, target: np.ndarray) -> float:
    """Return relative L2 error with a safe denominator."""

    denom = max(float(np.linalg.norm(target)), 1.0e-30)
    return float(np.linalg.norm(pred - target) / denom)


def _rmse(pred: np.ndarray, target: np.ndarray) -> float:
    """Return root mean square error."""

    return float(np.sqrt(np.mean(np.square(pred - target))))


def _display_path(path: Path) -> str:
    """Return a workspace-relative path when possible."""

    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _build_coords(data: InverseV0Data, device: torch.device) -> torch.Tensor:
    """Build flattened normalized `(x,t)` coordinates for the full grid."""

    x_norm = _tensor(data.x_norm, device)
    t_norm = _tensor(data.t_norm, device)
    mesh_t, mesh_x = torch.meshgrid(t_norm, x_norm, indexing="ij")
    return torch.stack([mesh_x.reshape(-1), mesh_t.reshape(-1)], dim=-1)


def _select_anchor_indices(total_points: int, n_anchor: int, seed: int, device: torch.device) -> torch.Tensor:
    """Select deterministic field-anchor indices."""

    if n_anchor <= 0:
        return torch.empty(0, dtype=torch.long, device=device)
    rng = np.random.default_rng(seed)
    n_pick = min(int(n_anchor), int(total_points))
    indices = rng.choice(total_points, size=n_pick, replace=False)
    return torch.as_tensor(indices, dtype=torch.long, device=device)


def _plot_map(path: Path, values: np.ndarray, x: np.ndarray, t: np.ndarray, title: str, colorbar: str, dpi: int) -> None:
    """Save a predicted field map."""

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
    """Save inverse v0 diagnostic figures and return their relative paths."""

    figure_paths: list[str] = []
    x = data.x
    t = data.t
    gt_c = np.asarray(data.gt["c_v"], dtype=float)
    gt_m = np.asarray(data.gt["m"], dtype=float)
    _ = gt_c, gt_m

    loss_path = output_dir / "loss_curve.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    epochs = [item["epoch"] for item in history]
    for key in ("total_loss", "port_loss", "ic_loss", "field_anchor_loss", "smooth_loss", "physics_light_loss"):
        ax.semilogy(epochs, [item[key] for item in history], label=key)
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.legend(fontsize=8)
    fig.savefig(loss_path, dpi=dpi)
    plt.close(fig)
    figure_paths.append(_display_path(loss_path))

    maps = [
        ("pred_delta_T_map.png", predictions["delta_T"], "Predicted delta T", "K"),
        ("pred_delta_c_v_map.png", predictions["delta_c_v"], "Predicted delta c_v", "fraction"),
        ("pred_delta_m_map.png", predictions["delta_m"], "Predicted delta m", "fraction"),
        ("pred_sigma_map.png", predictions["sigma"], "Predicted sigma", "S/m"),
    ]
    for filename, values, title, colorbar in maps:
        path = output_dir / filename
        _plot_map(path, values, x, t, title, colorbar, dpi)
        figure_paths.append(_display_path(path))

    compare_path = output_dir / "compare_g_time.png"
    fig, ax = plt.subplots(figsize=(6.4, 4.0), constrained_layout=True)
    ax.plot(t * 1.0e6, np.asarray(data.gt["G"], dtype=float), label="Ground Truth G")
    ax.plot(t * 1.0e6, port_pred["G"], label="PINN v0 G")
    obs_t = np.asarray(data.obs["t"], dtype=float)
    obs_g = np.asarray(data.obs["G"], dtype=float)
    ax.scatter(obs_t * 1.0e6, obs_g, s=24, label="Sparse observed G", zorder=3)
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
    """Evaluate trained model and port reconstruction on the full grid."""

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
    """Run PINN inverse v0 training and save artifacts."""

    cfg = load_yaml(config_path)
    if epochs_override is not None:
        cfg["epochs"] = int(epochs_override)
    if output_dir_override is not None:
        cfg["output_dir"] = str(output_dir_override)

    seed = int(cfg.get("seed", 2026))
    seed_everything(seed)
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

    voltage = _tensor(data.gt["V"], device)
    obs_t_idx = torch.as_tensor(np.asarray(data.obs["t_idx"], dtype=np.int64), dtype=torch.long, device=device)
    obs_i = _tensor(data.obs["I"], device)
    obs_g = _tensor(data.obs["G"], device)

    target_c = _tensor(gt_c, device)
    target_delta_t = _tensor(gt_delta_t, device)
    target_m = _tensor(gt_m, device)
    target_sigma_log = torch.log(torch.clamp(_tensor(gt_sigma, device), min=1.0e-30))
    target_delta_c = _tensor(gt_delta_c, device)
    target_delta_m = _tensor(gt_delta_m, device)

    anchor_idx = _select_anchor_indices(nt * nx, int(cfg.get("field_anchor_points", 0)), seed, device)
    weights = {key: float(value) for key, value in dict(cfg.get("loss_weights", {})).items()}
    scales = {key: float(value) for key, value in dict(cfg.get("loss_scales", {})).items()}
    c_scale = scales.get("c_v", 1.0e-2)
    temp_scale = scales.get("delta_T", 10.0)
    m_scale = scales.get("m", 0.1)
    sigma_log_scale = scales.get("sigma_log", 1.0)
    i_scale = max(float(np.max(np.abs(np.asarray(data.obs["I"], dtype=float)))), 1.0e-30)
    g_scale = max(float(np.max(np.abs(np.asarray(data.obs["G"], dtype=float)))), 1.0e-30)

    history: list[dict[str, float]] = []
    n_epochs = int(cfg.get("epochs", 200))
    print(f"Training PINN inverse v0 for {n_epochs} epochs on {device}.")

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
                normalized_mse(flat_c[anchor_idx], target_c.reshape(-1)[anchor_idx], c_scale)
                + normalized_mse(flat_delta_t[anchor_idx], target_delta_t.reshape(-1)[anchor_idx], temp_scale)
                + normalized_mse(flat_delta_m[anchor_idx], target_delta_m.reshape(-1)[anchor_idx], m_scale)
                + normalized_mse(flat_log_sigma[anchor_idx], target_sigma_log.reshape(-1)[anchor_idx], sigma_log_scale)
            )
        else:
            field_anchor_loss = torch.zeros((), dtype=coords.dtype, device=device)

        smooth_loss = (
            smoothness_loss(fields["c_v"] / c_scale)
            + smoothness_loss(fields["delta_T"] / temp_scale)
            + smoothness_loss(fields["m"] / m_scale)
            + smoothness_loss(fields["log_sigma"] / sigma_log_scale)
        )
        feasibility_loss = physics_light_loss(fields)
        total = (
            weights.get("w_port_data", 1.0) * port_loss
            + weights.get("w_ic", 1.0) * ic_loss
            + weights.get("w_field_anchor", 1.0) * field_anchor_loss
            + weights.get("w_smooth", 0.0) * smooth_loss
            + weights.get("w_physics_light", 0.0) * feasibility_loss
        )

        total.backward()
        optimizer.step()

        row = {
            "epoch": float(epoch),
            "total_loss": float(total.detach().cpu()),
            "port_loss": float(port_loss.detach().cpu()),
            "ic_loss": float(ic_loss.detach().cpu()),
            "field_anchor_loss": float(field_anchor_loss.detach().cpu()),
            "smooth_loss": float(smooth_loss.detach().cpu()),
            "physics_light_loss": float(feasibility_loss.detach().cpu()),
        }
        history.append(row)
        if epoch == 1 or epoch == n_epochs or epoch % max(n_epochs // 10, 1) == 0:
            print(
                f"epoch {epoch:04d} total={row['total_loss']:.4e} "
                f"port={row['port_loss']:.4e} anchor={row['field_anchor_loss']:.4e}"
            )

    predictions, port_pred = _evaluate(model, data, device)
    metrics = {
        "final_total_loss": history[-1]["total_loss"],
        "final_port_loss": history[-1]["port_loss"],
        "relative_G_error": _relative_l2(port_pred["G"], np.asarray(data.gt["G"], dtype=float)),
        "relative_I_error": _relative_l2(port_pred["I"], np.asarray(data.gt["I"], dtype=float)),
        "rmse_delta_T": _rmse(predictions["delta_T"], gt_delta_t),
        "rmse_delta_c_v": _rmse(predictions["delta_c_v"], gt_delta_c),
        "rmse_delta_m": _rmse(predictions["delta_m"], gt_delta_m),
        "rmse_sigma": _rmse(predictions["sigma"], gt_sigma),
        "max_abs_error_delta_T": float(np.max(np.abs(predictions["delta_T"] - gt_delta_t))),
        "max_abs_error_delta_c_v": float(np.max(np.abs(predictions["delta_c_v"] - gt_delta_c))),
        "max_abs_error_delta_m": float(np.max(np.abs(predictions["delta_m"] - gt_delta_m))),
        "gt_keys": data.gt_keys,
        "obs_keys": data.obs_keys,
        "sigma_closure": "PINN inverse v0 predicts positive sigma as a surrogate closure.",
    }
    figure_paths = _save_figures(
        output_dir,
        history,
        data,
        predictions,
        port_pred,
        int(cfg.get("plot_dpi", 160)),
    )
    metrics["figure_paths"] = figure_paths

    write_json(
        output_dir / "train_history.json",
        {
            "config_path": str(config_path),
            "train_data": str(data.train_data_path.relative_to(ROOT)),
            "sparse_obs": str(data.sparse_obs_path.relative_to(ROOT)),
            "manifest": str(data.manifest_path.relative_to(ROOT)),
            "gt_keys": data.gt_keys,
            "obs_keys": data.obs_keys,
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

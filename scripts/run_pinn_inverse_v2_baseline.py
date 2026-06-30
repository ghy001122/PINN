"""Run a small F-SPS-PINN v2 baseline.

The baseline compares a legacy-style free `log_sigma` conductivity shortcut
against a white-box `vo2_sigma(T, c_v, m)` closure under the same seed, data,
training budget, field-anchor count, and sparse terminal observations. This is
a synthetic numerical digital-twin small-run benchmark, not a formal
performance experiment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.vo2_constitutive import vo2_sigma
from pinnpcm.pinn.data import InverseV0Data, load_inverse_v0_data
from pinnpcm.pinn.losses import reconstruct_port_from_sigma, smoothness_loss
from pinnpcm.pinn.network import StiffAwareMLP
from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import ensure_dir, write_json
from pinnpcm.utils.seed import seed_everything

DEFAULT_CONFIG = Path("configs/pinn_inverse_v2_f_sps_baseline.yaml")
CSV_FIELDS = [
    "run_name",
    "conductivity_mode",
    "seed",
    "epochs",
    "initial_loss",
    "final_loss",
    "finite_loss",
    "loss_decreased",
    "relative_G_error",
    "relative_I_error",
    "nrmse_delta_T",
    "nrmse_c_v",
    "nrmse_m",
    "nrmse_sigma",
    "sigma_min",
    "sigma_max",
    "used_vo2_sigma",
    "used_free_log_sigma",
]


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tensor(array: Any, device: torch.device) -> torch.Tensor:
    return torch.as_tensor(array, dtype=torch.float32, device=device)


def _build_coords(data: InverseV0Data, device: torch.device) -> torch.Tensor:
    x_norm = _tensor(data.x_norm, device)
    t_norm = _tensor(data.t_norm, device)
    mesh_t, mesh_x = torch.meshgrid(t_norm, x_norm, indexing="ij")
    return torch.stack([mesh_x.reshape(-1), mesh_t.reshape(-1)], dim=-1)


def _select_anchor_indices(total_points: int, n_anchor: int, seed: int, device: torch.device) -> torch.Tensor:
    if n_anchor <= 0:
        return torch.empty(0, dtype=torch.long, device=device)
    rng = np.random.default_rng(seed)
    n_pick = min(int(n_anchor), int(total_points))
    return torch.as_tensor(rng.choice(total_points, size=n_pick, replace=False), dtype=torch.long, device=device)


def _relative_mse(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    floor = torch.as_tensor(1.0e-30, dtype=pred.dtype, device=pred.device)
    scale = torch.clamp(torch.max(torch.abs(target)), min=floor)
    return torch.mean(((pred - target) / scale).square())


def _relative_rmse(pred: np.ndarray, target: np.ndarray) -> float:
    denom = max(float(np.sqrt(np.mean(np.square(target)))), 1.0e-30)
    return float(np.sqrt(np.mean(np.square(pred - target))) / denom)


def _nrmse(pred: np.ndarray, target: np.ndarray) -> float:
    span = max(float(np.max(target) - np.min(target)), 1.0e-12)
    return float(np.sqrt(np.mean(np.square(pred - target))) / span)


class V2BaselineNet(nn.Module):
    """Minimal neural field for v2 conductivity-mode comparison."""

    def __init__(
        self,
        *,
        conductivity_mode: str,
        hidden_dim: int,
        hidden_layers: int,
        fourier_scales: list[float],
        fourier_enabled: bool,
        c_v_min: float,
        c_v_max: float,
        delta_T_max: float,
        T0: float,
        initial_c_v: float,
        initial_m: float,
        initial_sigma: float,
        sigma_min: float,
        sigma_max: float,
    ) -> None:
        super().__init__()
        if conductivity_mode not in {"free_log_sigma", "white_box_vo2_sigma"}:
            raise ValueError(f"Unsupported conductivity_mode: {conductivity_mode}")
        if c_v_max <= c_v_min:
            raise ValueError("c_v_max must be greater than c_v_min.")
        if delta_T_max <= 0.0:
            raise ValueError("delta_T_max must be positive.")
        if sigma_max <= sigma_min:
            raise ValueError("sigma_max must be greater than sigma_min.")
        self.conductivity_mode = conductivity_mode
        self.c_v_min = float(c_v_min)
        self.c_v_max = float(c_v_max)
        self.delta_T_max = float(delta_T_max)
        self.T0 = float(T0)
        self.sigma_min = float(sigma_min)
        self.sigma_max = float(sigma_max)
        out_dim = 4 if conductivity_mode == "free_log_sigma" else 3
        self.core = StiffAwareMLP(
            in_dim=2,
            out_dim=out_dim,
            hidden_dim=int(hidden_dim),
            hidden_layers=int(hidden_layers),
            scales=[float(value) for value in fourier_scales],
            use_fourier=bool(fourier_enabled),
        )
        self._initialize_bias(initial_c_v=initial_c_v, initial_m=initial_m, initial_sigma=initial_sigma)

    @staticmethod
    def _logit(value: float) -> float:
        clipped = min(max(float(value), 1.0e-6), 1.0 - 1.0e-6)
        return float(np.log(clipped / (1.0 - clipped)))

    def _initialize_bias(self, *, initial_c_v: float, initial_m: float, initial_sigma: float) -> None:
        last = self.core.net[-1]
        if not isinstance(last, nn.Linear):
            return
        with torch.no_grad():
            c_ratio = (float(initial_c_v) - self.c_v_min) / (self.c_v_max - self.c_v_min)
            dt_ratio = 1.0e-2 / self.delta_T_max
            values = [self._logit(c_ratio), self._logit(dt_ratio), self._logit(float(initial_m))]
            if self.conductivity_mode == "free_log_sigma":
                sigma_ratio = (float(initial_sigma) - self.sigma_min) / (self.sigma_max - self.sigma_min)
                values.append(self._logit(sigma_ratio))
            last.bias.copy_(torch.tensor(values, dtype=last.bias.dtype, device=last.bias.device))

    def forward(self, coords: torch.Tensor, vo2_params: dict[str, Any]) -> dict[str, torch.Tensor]:
        raw = self.core(coords)
        c_v = self.c_v_min + (self.c_v_max - self.c_v_min) * torch.sigmoid(raw[..., 0:1])
        delta_T = self.delta_T_max * torch.sigmoid(raw[..., 1:2])
        T = self.T0 + delta_T
        m = torch.sigmoid(raw[..., 2:3])
        fields = {"T": T, "delta_T": delta_T, "c_v": c_v, "m": m}
        if self.conductivity_mode == "free_log_sigma":
            sigma = self.sigma_min + (self.sigma_max - self.sigma_min) * torch.sigmoid(raw[..., 3:4])
        else:
            phase_arg = None if bool(vo2_params.get("use_temperature_phase_fraction", False)) else m
            sigma = vo2_sigma(T, c_v, phase_arg, params=vo2_params)
        fields["sigma"] = sigma
        return fields


def _prepare_tensors(data: InverseV0Data, cfg: dict[str, Any], seed: int, device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "coords": _build_coords(data, device),
        "voltage": _tensor(data.gt["V"], device),
        "obs_t_idx": torch.as_tensor(np.asarray(data.obs["t_idx"], dtype=np.int64), dtype=torch.long, device=device),
        "obs_g": _tensor(data.obs["G"], device),
        "obs_i": _tensor(data.obs["I"], device),
        "target_delta_T": _tensor(np.asarray(data.gt["T"], dtype=float) - float(data.params["T0"]), device),
        "target_c_v": _tensor(data.gt["c_v"], device),
        "target_m": _tensor(data.gt["m"], device),
        "target_sigma": _tensor(data.gt["sigma"], device),
        "target_G": _tensor(data.gt["G"], device),
        "target_I": _tensor(data.gt["I"], device),
        "anchor_idx": _select_anchor_indices(data.nt * data.nx, int(cfg.get("field_anchor_points", 0)), seed, device),
    }


def _loss_and_diagnostics(
    model: V2BaselineNet,
    data: InverseV0Data,
    cfg: dict[str, Any],
    tensors: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    nt, nx = data.nt, data.nx
    pred_flat = model(tensors["coords"], dict(cfg.get("vo2_params", {})))
    fields = {key: value.reshape(nt, nx) for key, value in pred_flat.items()}
    port = reconstruct_port_from_sigma(fields["sigma"], tensors["voltage"], data.dx, data.params)
    obs_g_pred = port["G"][tensors["obs_t_idx"]]
    obs_i_pred = port["I"][tensors["obs_t_idx"]]

    weights = dict(cfg.get("loss_weights", {}))
    port_g_loss = _relative_mse(obs_g_pred, tensors["obs_g"])
    port_i_loss = _relative_mse(obs_i_pred, tensors["obs_i"])
    field_anchor_loss = torch.zeros((), dtype=tensors["coords"].dtype, device=tensors["coords"].device)
    if tensors["anchor_idx"].numel() > 0:
        idx = tensors["anchor_idx"]
        field_anchor_loss = (
            _relative_mse(fields["delta_T"].reshape(-1)[idx], tensors["target_delta_T"].reshape(-1)[idx])
            + _relative_mse(fields["c_v"].reshape(-1)[idx], tensors["target_c_v"].reshape(-1)[idx])
            + _relative_mse(fields["m"].reshape(-1)[idx], tensors["target_m"].reshape(-1)[idx])
        ) / 3.0
    smooth_loss = (
        smoothness_loss(fields["delta_T"])
        + smoothness_loss(fields["c_v"])
        + smoothness_loss(fields["m"])
        + smoothness_loss(fields["sigma"])
    )
    total = (
        float(weights.get("w_port_g", 1.0)) * port_g_loss
        + float(weights.get("w_port_i", 0.5)) * port_i_loss
        + float(weights.get("w_field_anchor", 0.0)) * field_anchor_loss
        + float(weights.get("w_smooth", 0.0)) * smooth_loss
    )
    diagnostics = {
        "total_loss": total.detach(),
        "port_g_loss": port_g_loss.detach(),
        "port_i_loss": port_i_loss.detach(),
        "field_anchor_loss": field_anchor_loss.detach(),
        "smooth_loss": smooth_loss.detach(),
        "sigma_min": torch.min(fields["sigma"]).detach(),
        "sigma_max": torch.max(fields["sigma"]).detach(),
    }
    return total, diagnostics, {"fields": fields, "port": port}


def _final_metrics(
    *,
    run_name: str,
    conductivity_mode: str,
    seed: int,
    epochs: int,
    initial_loss: float,
    final_loss: float,
    finite_loss: bool,
    diagnostics: dict[str, torch.Tensor],
    state: dict[str, dict[str, torch.Tensor]],
    tensors: dict[str, torch.Tensor],
) -> dict[str, Any]:
    fields = state["fields"]
    port = state["port"]
    pred_delta_T = fields["delta_T"].detach().cpu().numpy()
    pred_c_v = fields["c_v"].detach().cpu().numpy()
    pred_m = fields["m"].detach().cpu().numpy()
    pred_sigma = fields["sigma"].detach().cpu().numpy()
    target_delta_T = tensors["target_delta_T"].detach().cpu().numpy()
    target_c_v = tensors["target_c_v"].detach().cpu().numpy()
    target_m = tensors["target_m"].detach().cpu().numpy()
    target_sigma = tensors["target_sigma"].detach().cpu().numpy()
    pred_G = port["G"].detach().cpu().numpy()
    pred_I = port["I"].detach().cpu().numpy()
    target_G = tensors["target_G"].detach().cpu().numpy()
    target_I = tensors["target_I"].detach().cpu().numpy()
    return {
        "run_name": run_name,
        "conductivity_mode": conductivity_mode,
        "seed": int(seed),
        "epochs": int(epochs),
        "initial_loss": float(initial_loss),
        "final_loss": float(final_loss),
        "finite_loss": bool(finite_loss),
        "loss_decreased": bool(final_loss <= initial_loss),
        "relative_G_error": _relative_rmse(pred_G, target_G),
        "relative_I_error": _relative_rmse(pred_I, target_I),
        "nrmse_delta_T": _nrmse(pred_delta_T, target_delta_T),
        "nrmse_c_v": _nrmse(pred_c_v, target_c_v),
        "nrmse_m": _nrmse(pred_m, target_m),
        "nrmse_sigma": _nrmse(pred_sigma, target_sigma),
        "sigma_min": float(diagnostics["sigma_min"].cpu()),
        "sigma_max": float(diagnostics["sigma_max"].cpu()),
        "used_vo2_sigma": bool(conductivity_mode == "white_box_vo2_sigma"),
        "used_free_log_sigma": bool(conductivity_mode == "free_log_sigma"),
    }


def _run_one(
    *,
    run_cfg: dict[str, Any],
    base_cfg: dict[str, Any],
    data: InverseV0Data,
    tensors: dict[str, torch.Tensor],
    device: torch.device,
    epochs: int,
    seed: int,
) -> dict[str, Any]:
    conductivity_mode = str(run_cfg["conductivity_mode"])
    model_bounds = dict(base_cfg.get("model_bounds", {}))
    gt_c = np.asarray(data.gt["c_v"], dtype=float)
    gt_m = np.asarray(data.gt["m"], dtype=float)
    gt_sigma = np.asarray(data.gt["sigma"], dtype=float)
    model = V2BaselineNet(
        conductivity_mode=conductivity_mode,
        hidden_dim=int(base_cfg.get("hidden_dim", 32)),
        hidden_layers=int(base_cfg.get("hidden_layers", 2)),
        fourier_scales=[float(value) for value in base_cfg.get("fourier_scales", [1.0, 2.0, 4.0])],
        fourier_enabled=bool(base_cfg.get("fourier_enabled", True)),
        c_v_min=float(model_bounds.get("c_v_min", 0.0)),
        c_v_max=float(model_bounds.get("c_v_max", 0.2)),
        delta_T_max=float(model_bounds.get("delta_T_max", 20.0)),
        T0=float(data.params["T0"]),
        initial_c_v=float(np.mean(gt_c[0])),
        initial_m=float(np.mean(gt_m[0])),
        initial_sigma=float(np.mean(gt_sigma[0])),
        sigma_min=float(model_bounds.get("sigma_min", 1.0e-8)),
        sigma_max=float(model_bounds.get("sigma_max", 1.0)),
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(base_cfg.get("lr", 1.0e-3)))
    initial_loss: float | None = None
    final_diag: dict[str, torch.Tensor] | None = None
    final_state: dict[str, dict[str, torch.Tensor]] | None = None
    for _ in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        loss, diagnostics, state = _loss_and_diagnostics(model, data, base_cfg, tensors)
        if initial_loss is None:
            initial_loss = float(loss.detach().cpu())
        loss.backward()
        optimizer.step()
        final_diag = diagnostics
        final_state = state
    if initial_loss is None or final_diag is None or final_state is None:
        raise RuntimeError("No baseline training epochs were executed.")
    final_loss = float(final_diag["total_loss"].cpu())
    finite_loss = bool(np.isfinite(initial_loss) and np.isfinite(final_loss))
    return _final_metrics(
        run_name=str(run_cfg["run_name"]),
        conductivity_mode=conductivity_mode,
        seed=seed,
        epochs=epochs,
        initial_loss=initial_loss,
        final_loss=final_loss,
        finite_loss=finite_loss,
        diagnostics=final_diag,
        state=final_state,
        tensors=tensors,
    )


def run_baseline(
    config_path: Path,
    *,
    epochs_override: int | None = None,
    output_root_override: Path | None = None,
    summary_override: Path | None = None,
    runs_csv_override: Path | None = None,
) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    if epochs_override is not None:
        cfg["epochs"] = int(epochs_override)
    if output_root_override is not None:
        cfg["output_root"] = str(output_root_override)
    if summary_override is not None:
        cfg["summary_json"] = str(summary_override)
    if runs_csv_override is not None:
        cfg["runs_csv"] = str(runs_csv_override)

    seed = int(cfg.get("seed", 2026))
    seed_everything(seed)
    data_cfg = dict(cfg)
    data_cfg["output_dir"] = cfg.get("output_root", "outputs/pinn_inverse_v2/f_sps_baseline")
    data = load_inverse_v0_data(data_cfg, root=ROOT, verbose=True)
    output_root = ensure_dir(_resolve(cfg.get("output_root", "outputs/pinn_inverse_v2/f_sps_baseline")))
    summary_path = _resolve(cfg.get("summary_json", "outputs/tables/pinn_inverse_v2_f_sps_baseline_summary.json"))
    runs_csv_path = _resolve(cfg.get("runs_csv", "outputs/tables/pinn_inverse_v2_f_sps_baseline_runs.csv"))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    runs_csv_path.parent.mkdir(parents=True, exist_ok=True)

    before_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    before_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    device = torch.device(str(cfg.get("device", "cpu")))
    tensors = _prepare_tensors(data, cfg, seed, device)
    epochs = int(cfg.get("epochs", 8))

    results: list[dict[str, Any]] = []
    for run_cfg in cfg.get("runs", []):
        seed_everything(seed)
        results.append(
            _run_one(
                run_cfg=dict(run_cfg),
                base_cfg=cfg,
                data=data,
                tensors=tensors,
                device=device,
                epochs=epochs,
                seed=seed,
            )
        )

    after_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    after_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    frozen_unchanged = before_hashes == after_hashes and before_mtimes == after_mtimes
    summary = {
        "benchmark": "synthetic numerical digital-twin small-run baseline",
        "config": _display_path(_resolve(config_path)),
        "train_data": _display_path(data.train_data_path),
        "sparse_obs": _display_path(data.sparse_obs_path),
        "output_root": _display_path(output_root),
        "summary_json": _display_path(summary_path),
        "runs_csv": _display_path(runs_csv_path),
        "epochs": epochs,
        "seed": seed,
        "num_runs": len(results),
        "runs": results,
        "frozen_hashes_before": before_hashes,
        "frozen_hashes_after": after_hashes,
        "frozen_mtimes_before": before_mtimes,
        "frozen_mtimes_after": after_mtimes,
        "frozen_inputs_unchanged": frozen_unchanged,
        "claim_boundary": "small-run synthetic numerical benchmark only; no F-SPS-PINN performance superiority claim",
    }
    with runs_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in results:
            writer.writerow({field: row[field] for field in CSV_FIELDS})
    write_json(summary_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--runs-csv", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_baseline(
        args.config,
        epochs_override=args.epochs,
        output_root_override=args.output_root,
        summary_override=args.summary,
        runs_csv_override=args.runs_csv,
    )
    print(json.dumps({key: summary[key] for key in ["summary_json", "runs_csv", "num_runs", "frozen_inputs_unchanged"]}, indent=2))
    for row in summary["runs"]:
        print(json.dumps({key: row[key] for key in CSV_FIELDS}, indent=2))


if __name__ == "__main__":
    main()

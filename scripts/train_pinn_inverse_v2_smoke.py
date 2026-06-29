"""F-SPS-PINN v2 smoke training with white-box VO2-like sigma closure.

This script is intentionally small. It verifies that the new Fourier-pyramid
network and `vo2_sigma(T, c_v, m)` closure can enter a differentiable training
loop on the frozen Ground Truth v1.1 triangle benchmark. It is a synthetic
numerical digital-twin smoke test, not a performance experiment.
"""

from __future__ import annotations

import argparse
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

DEFAULT_CONFIG = Path("configs/pinn_inverse_v2_f_sps_smoke.yaml")


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


class FSpsSmokeNet(nn.Module):
    """Minimal v2 neural field using Fourier pyramid features.

    Outputs physical state variables only. Conductivity is computed outside the
    network via `vo2_sigma`; there is no free `log_sigma` head in this v2 smoke
    path.
    """

    def __init__(
        self,
        *,
        hidden_dim: int,
        hidden_layers: int,
        fourier_scales: list[float],
        c_v_min: float,
        c_v_max: float,
        delta_T_max: float,
        T0: float,
        initial_c_v: float,
        initial_m: float,
    ) -> None:
        super().__init__()
        if c_v_max <= c_v_min:
            raise ValueError("c_v_max must be greater than c_v_min.")
        if delta_T_max <= 0.0:
            raise ValueError("delta_T_max must be positive.")
        self.core = StiffAwareMLP(
            in_dim=2,
            out_dim=3,
            hidden_dim=int(hidden_dim),
            hidden_layers=int(hidden_layers),
            scales=[float(value) for value in fourier_scales],
        )
        self.c_v_min = float(c_v_min)
        self.c_v_max = float(c_v_max)
        self.delta_T_max = float(delta_T_max)
        self.T0 = float(T0)
        self._initialize_bias(initial_c_v=float(initial_c_v), initial_m=float(initial_m))

    @staticmethod
    def _logit(value: float) -> float:
        clipped = min(max(float(value), 1.0e-6), 1.0 - 1.0e-6)
        return float(np.log(clipped / (1.0 - clipped)))

    def _initialize_bias(self, *, initial_c_v: float, initial_m: float) -> None:
        last = self.core.net[-1]
        if not isinstance(last, nn.Linear):
            return
        with torch.no_grad():
            c_ratio = (initial_c_v - self.c_v_min) / (self.c_v_max - self.c_v_min)
            dt_ratio = 1.0e-2 / self.delta_T_max
            last.bias.copy_(
                torch.tensor(
                    [self._logit(c_ratio), self._logit(dt_ratio), self._logit(initial_m)],
                    dtype=last.bias.dtype,
                    device=last.bias.device,
                )
            )

    def forward(self, coords: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = self.core(coords)
        c_v = self.c_v_min + (self.c_v_max - self.c_v_min) * torch.sigmoid(raw[..., 0:1])
        delta_T = self.delta_T_max * torch.sigmoid(raw[..., 1:2])
        T = self.T0 + delta_T
        m = torch.sigmoid(raw[..., 2:3])
        return {"T": T, "delta_T": delta_T, "c_v": c_v, "m": m}


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _sample_obs_from_full(full: torch.Tensor, obs_t_idx: torch.Tensor) -> torch.Tensor:
    return full[obs_t_idx]


def _relative_mse(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    scale = torch.clamp(torch.max(torch.abs(target)), min=torch.as_tensor(1.0e-30, dtype=pred.dtype, device=pred.device))
    return torch.mean(((pred - target) / scale).square())


def _train_step(
    model: FSpsSmokeNet,
    data: InverseV0Data,
    cfg: dict[str, Any],
    tensors: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    nt, nx = data.nt, data.nx
    pred_flat = model(tensors["coords"])
    fields = {key: value.reshape(nt, nx) for key, value in pred_flat.items()}
    sigma = vo2_sigma(fields["T"], fields["c_v"], fields["m"], params=dict(cfg.get("vo2_params", {})))
    port = reconstruct_port_from_sigma(sigma, tensors["voltage"], data.dx, data.params)
    obs_g_pred = _sample_obs_from_full(port["G"], tensors["obs_t_idx"])
    obs_i_pred = _sample_obs_from_full(port["I"], tensors["obs_t_idx"])

    weights = dict(cfg.get("loss_weights", {}))
    port_g_loss = _relative_mse(obs_g_pred, tensors["obs_g"])
    port_i_loss = _relative_mse(obs_i_pred, tensors["obs_i"])
    field_anchor_loss = torch.zeros((), dtype=tensors["coords"].dtype, device=tensors["coords"].device)
    if tensors["anchor_idx"].numel() > 0:
        flat_t = fields["T"].reshape(-1)
        flat_c = fields["c_v"].reshape(-1)
        flat_m = fields["m"].reshape(-1)
        idx = tensors["anchor_idx"]
        field_anchor_loss = (
            _relative_mse(flat_t[idx], tensors["target_T"].reshape(-1)[idx])
            + _relative_mse(flat_c[idx], tensors["target_c_v"].reshape(-1)[idx])
            + _relative_mse(flat_m[idx], tensors["target_m"].reshape(-1)[idx])
        ) / 3.0
    smooth_loss = smoothness_loss(fields["T"]) + smoothness_loss(fields["c_v"]) + smoothness_loss(fields["m"])
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
        "sigma_min": torch.min(sigma).detach(),
        "sigma_max": torch.max(sigma).detach(),
    }
    return total, diagnostics


def train(config_path: Path, *, epochs_override: int | None = None, output_dir_override: Path | None = None, summary_override: Path | None = None) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    if epochs_override is not None:
        cfg["epochs"] = int(epochs_override)
    if output_dir_override is not None:
        cfg["output_dir"] = str(output_dir_override)
    if summary_override is not None:
        cfg["summary_json"] = str(summary_override)

    seed = int(cfg.get("seed", 2026))
    seed_everything(seed)
    data = load_inverse_v0_data(cfg, root=ROOT, verbose=True)
    output_dir = ensure_dir(_resolve(cfg["output_dir"]))
    summary_path = _resolve(cfg.get("summary_json", output_dir / "summary.json"))
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    before_hashes = {
        "train_data": _sha256(data.train_data_path),
        "sparse_obs": _sha256(data.sparse_obs_path),
    }
    before_mtimes = {
        "train_data": data.train_data_path.stat().st_mtime_ns,
        "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns,
    }

    device = torch.device(str(cfg.get("device", "cpu")))
    gt_c = np.asarray(data.gt["c_v"], dtype=float)
    gt_T = np.asarray(data.gt["T"], dtype=float)
    gt_m = np.asarray(data.gt["m"], dtype=float)
    model_bounds = dict(cfg.get("model_bounds", {}))
    model = FSpsSmokeNet(
        hidden_dim=int(cfg.get("hidden_dim", 32)),
        hidden_layers=int(cfg.get("hidden_layers", 2)),
        fourier_scales=[float(value) for value in cfg.get("fourier_scales", [1.0, 2.0, 4.0])],
        c_v_min=float(model_bounds.get("c_v_min", 0.0)),
        c_v_max=float(model_bounds.get("c_v_max", 0.2)),
        delta_T_max=float(model_bounds.get("delta_T_max", 20.0)),
        T0=float(data.params["T0"]),
        initial_c_v=float(np.mean(gt_c[0])),
        initial_m=float(np.mean(gt_m[0])),
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(cfg.get("lr", 1.0e-3)))
    coords = _build_coords(data, device)
    tensors = {
        "coords": coords,
        "voltage": _tensor(data.gt["V"], device),
        "obs_t_idx": torch.as_tensor(np.asarray(data.obs["t_idx"], dtype=np.int64), dtype=torch.long, device=device),
        "obs_g": _tensor(data.obs["G"], device),
        "obs_i": _tensor(data.obs["I"], device),
        "target_T": _tensor(gt_T, device),
        "target_c_v": _tensor(gt_c, device),
        "target_m": _tensor(gt_m, device),
        "anchor_idx": _select_anchor_indices(data.nt * data.nx, int(cfg.get("field_anchor_points", 0)), seed, device),
    }

    history: list[dict[str, float]] = []
    epochs = int(cfg.get("epochs", 3))
    initial_loss = None
    final_diag: dict[str, torch.Tensor] | None = None
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad(set_to_none=True)
        loss, diagnostics = _train_step(model, data, cfg, tensors)
        if initial_loss is None:
            initial_loss = float(loss.detach().cpu())
        loss.backward()
        optimizer.step()
        final_diag = diagnostics
        row = {"epoch": float(epoch), **{key: float(value.cpu()) for key, value in diagnostics.items()}}
        history.append(row)

    if final_diag is None or initial_loss is None:
        raise RuntimeError("No training epochs were executed.")
    final_loss = float(final_diag["total_loss"].cpu())
    finite_loss = bool(np.isfinite(final_loss) and np.isfinite(initial_loss))
    after_hashes = {
        "train_data": _sha256(data.train_data_path),
        "sparse_obs": _sha256(data.sparse_obs_path),
    }
    after_mtimes = {
        "train_data": data.train_data_path.stat().st_mtime_ns,
        "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns,
    }
    summary = {
        "benchmark": "synthetic numerical digital-twin smoke test",
        "config": _display_path(_resolve(config_path)),
        "train_data": _display_path(data.train_data_path),
        "sparse_obs": _display_path(data.sparse_obs_path),
        "output_dir": _display_path(output_dir),
        "summary_json": _display_path(summary_path),
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "loss_decreased": bool(final_loss <= initial_loss),
        "finite_loss": finite_loss,
        "sigma_min": float(final_diag["sigma_min"].cpu()),
        "sigma_max": float(final_diag["sigma_max"].cpu()),
        "used_vo2_sigma": True,
        "used_free_log_sigma": False,
        "dynamic_gate_enabled": bool(float(dict(cfg.get("loss_weights", {})).get("w_dynamic_gate", 0.0)) > 0.0),
        "frequency_loss_enabled": bool(float(dict(cfg.get("loss_weights", {})).get("w_frequency", 0.0)) > 0.0),
        "epochs": epochs,
        "seed": seed,
        "history": history,
        "frozen_hashes_before": before_hashes,
        "frozen_hashes_after": after_hashes,
        "frozen_mtimes_before": before_mtimes,
        "frozen_mtimes_after": after_mtimes,
        "frozen_inputs_unchanged": before_hashes == after_hashes and before_mtimes == after_mtimes,
    }
    write_json(summary_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = train(args.config, epochs_override=args.epochs, output_dir_override=args.output_dir, summary_override=args.summary)
    print(json.dumps({key: summary[key] for key in ["summary_json", "initial_loss", "final_loss", "loss_decreased", "finite_loss", "used_vo2_sigma", "used_free_log_sigma", "frozen_inputs_unchanged"]}, indent=2))


if __name__ == "__main__":
    main()
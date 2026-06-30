"""Run F-SPS-PINN v2 Fourier on/off ablation under stress.

The ablation reuses the v2 baseline training utilities and the frozen Ground
Truth v1.1 triangle benchmark. It compares only the Fourier-pyramid feature
switch under the same sharp-transition white-box `vo2_sigma` stress condition.
This is a synthetic numerical digital-twin small-run ablation, not a formal
performance experiment and not a Ground Truth revision.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.pinn.data import load_inverse_v0_data
from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import ensure_dir, write_json
from pinnpcm.utils.seed import seed_everything
from scripts.run_pinn_inverse_v2_baseline import (
    _display_path,
    _prepare_tensors,
    _resolve,
    _run_one,
    _sha256,
)

DEFAULT_CONFIG = Path("configs/pinn_inverse_v2_fourier_ablation.yaml")
CSV_FIELDS = [
    "run_name",
    "conductivity_mode",
    "fourier_enabled",
    "fourier_scales",
    "stress_case",
    "T_c",
    "transition_width",
    "sigma_ins0",
    "sigma_met0",
    "sigma_contrast",
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
    "sigma_dynamic_range",
    "used_vo2_sigma",
    "used_free_log_sigma",
    "frozen_inputs_unchanged",
]


def _row_from_metrics(
    *,
    metrics: dict[str, Any],
    run_cfg: dict[str, Any],
    base_cfg: dict[str, Any],
    vo2_params: dict[str, Any],
    frozen_inputs_unchanged: bool,
) -> dict[str, Any]:
    sigma_ins0 = float(vo2_params["sigma_ins0"])
    sigma_met0 = float(vo2_params["sigma_met0"])
    sigma_min = float(metrics["sigma_min"])
    sigma_max = float(metrics["sigma_max"])
    return {
        "run_name": str(metrics["run_name"]),
        "conductivity_mode": str(metrics["conductivity_mode"]),
        "fourier_enabled": bool(run_cfg.get("fourier_enabled", True)),
        "fourier_scales": [float(value) for value in base_cfg.get("fourier_scales", [])],
        "stress_case": str(base_cfg.get("stress_case", "sharp_transition")),
        "T_c": float(vo2_params["T_c"]),
        "transition_width": float(vo2_params["transition_width"]),
        "sigma_ins0": sigma_ins0,
        "sigma_met0": sigma_met0,
        "sigma_contrast": sigma_met0 / max(sigma_ins0, 1.0e-30),
        "initial_loss": float(metrics["initial_loss"]),
        "final_loss": float(metrics["final_loss"]),
        "finite_loss": bool(metrics["finite_loss"]),
        "loss_decreased": bool(metrics["loss_decreased"]),
        "relative_G_error": float(metrics["relative_G_error"]),
        "relative_I_error": float(metrics["relative_I_error"]),
        "nrmse_delta_T": float(metrics["nrmse_delta_T"]),
        "nrmse_c_v": float(metrics["nrmse_c_v"]),
        "nrmse_m": float(metrics["nrmse_m"]),
        "nrmse_sigma": float(metrics["nrmse_sigma"]),
        "sigma_min": sigma_min,
        "sigma_max": sigma_max,
        "sigma_dynamic_range": sigma_max / max(sigma_min, 1.0e-30),
        "used_vo2_sigma": bool(metrics["used_vo2_sigma"]),
        "used_free_log_sigma": bool(metrics["used_free_log_sigma"]),
        "frozen_inputs_unchanged": bool(frozen_inputs_unchanged),
    }


def _csv_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = dict(row)
    copied["fourier_scales"] = json.dumps(copied["fourier_scales"])
    return copied


def run_fourier_ablation(
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
    if int(cfg.get("epochs", 10)) > 50:
        raise ValueError("Fourier ablation must use epochs <= 50.")
    if output_root_override is not None:
        cfg["output_root"] = str(output_root_override)
    if summary_override is not None:
        cfg["summary_json"] = str(summary_override)
    if runs_csv_override is not None:
        cfg["runs_csv"] = str(runs_csv_override)

    seed = int(cfg.get("seed", 2026))
    seed_everything(seed)
    data_cfg = dict(cfg)
    data_cfg["output_dir"] = cfg.get("output_root", "outputs/pinn_inverse_v2/fourier_ablation")
    data = load_inverse_v0_data(data_cfg, root=ROOT, verbose=True)
    output_root = ensure_dir(_resolve(cfg.get("output_root", "outputs/pinn_inverse_v2/fourier_ablation")))
    summary_path = _resolve(cfg.get("summary_json", "outputs/tables/pinn_inverse_v2_fourier_ablation_summary.json"))
    runs_csv_path = _resolve(cfg.get("runs_csv", "outputs/tables/pinn_inverse_v2_fourier_ablation_runs.csv"))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    runs_csv_path.parent.mkdir(parents=True, exist_ok=True)

    before_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    before_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    device = torch.device(str(cfg.get("device", "cpu")))
    tensors = _prepare_tensors(data, cfg, seed, device)
    epochs = int(cfg.get("epochs", 10))
    vo2_params = dict(cfg.get("vo2_params", {}))

    rows: list[dict[str, Any]] = []
    for raw_run_cfg in cfg.get("runs", []):
        run_cfg = dict(raw_run_cfg)
        if str(run_cfg.get("conductivity_mode", "")) != "white_box_vo2_sigma":
            raise ValueError("This ablation keeps conductivity_mode fixed to white_box_vo2_sigma.")
        run_base_cfg = deepcopy(cfg)
        run_base_cfg["fourier_enabled"] = bool(run_cfg.get("fourier_enabled", True))
        run_base_cfg["vo2_params"] = vo2_params
        seed_everything(seed)
        metrics = _run_one(
            run_cfg={"run_name": str(run_cfg["run_name"]), "conductivity_mode": str(run_cfg["conductivity_mode"])},
            base_cfg=run_base_cfg,
            data=data,
            tensors=tensors,
            device=device,
            epochs=epochs,
            seed=seed,
        )
        current_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
        current_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
        rows.append(
            _row_from_metrics(
                metrics=metrics,
                run_cfg=run_cfg,
                base_cfg=cfg,
                vo2_params=vo2_params,
                frozen_inputs_unchanged=before_hashes == current_hashes and before_mtimes == current_mtimes,
            )
        )

    after_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    after_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    frozen_unchanged = before_hashes == after_hashes and before_mtimes == after_mtimes
    for row in rows:
        row["frozen_inputs_unchanged"] = bool(row["frozen_inputs_unchanged"] and frozen_unchanged)

    with runs_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_row(row)[field] for field in CSV_FIELDS})

    summary = {
        "benchmark": "synthetic numerical digital-twin Fourier on/off ablation under sharp-transition stress",
        "claim_boundary": "small-run Fourier ablation only; no F-SPS-PINN superiority claim unless supported by results",
        "recommended_interpretation": "If Fourier on clearly outperforms off, treat it only as supplemental method evidence. If it does not, interpret this as evidence that multiscale features alone do not resolve terminal-observation underdetermination; it is not a project failure.",
        "config": _display_path(_resolve(config_path)),
        "train_data": _display_path(data.train_data_path),
        "sparse_obs": _display_path(data.sparse_obs_path),
        "output_root": _display_path(output_root),
        "summary_json": _display_path(summary_path),
        "runs_csv": _display_path(runs_csv_path),
        "epochs": epochs,
        "seed": seed,
        "num_runs": len(rows),
        "stress_case": str(cfg.get("stress_case", "sharp_transition")),
        "runs": rows,
        "all_finite_loss": bool(all(row["finite_loss"] for row in rows)),
        "all_used_vo2_sigma": bool(all(row["used_vo2_sigma"] and not row["used_free_log_sigma"] for row in rows)),
        "all_frozen_inputs_unchanged": bool(all(row["frozen_inputs_unchanged"] for row in rows) and frozen_unchanged),
        "frozen_hashes_before": before_hashes,
        "frozen_hashes_after": after_hashes,
        "frozen_mtimes_before": before_mtimes,
        "frozen_mtimes_after": after_mtimes,
        "frozen_inputs_unchanged": frozen_unchanged,
    }
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
    summary = run_fourier_ablation(
        args.config,
        epochs_override=args.epochs,
        output_root_override=args.output_root,
        summary_override=args.summary,
        runs_csv_override=args.runs_csv,
    )
    print(json.dumps({key: summary[key] for key in ["summary_json", "runs_csv", "num_runs", "all_finite_loss", "all_used_vo2_sigma", "all_frozen_inputs_unchanged"]}, indent=2))
    for row in summary["runs"]:
        print(json.dumps({key: row[key] for key in CSV_FIELDS}, indent=2))


if __name__ == "__main__":
    main()

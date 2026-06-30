"""Run F-SPS-PINN v2 phase-transition stress preflight.

This script reuses the v2 baseline training utilities to test whether the
white-box `vo2_sigma(T, c_v, m)` closure remains finite and trainable under
sharper or higher-contrast synthetic phase-transition parameters. It is a
synthetic numerical digital-twin preflight only, not a formal performance
experiment and not a Ground Truth revision.
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

DEFAULT_CONFIG = Path("configs/pinn_inverse_v2_phase_transition_stress.yaml")
CSV_FIELDS = [
    "case_name",
    "conductivity_mode",
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


def _merge_vo2_params(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged.update(dict(override))
    return merged


def _case_row(metrics: dict[str, Any], case_name: str, vo2_params: dict[str, Any], frozen_inputs_unchanged: bool) -> dict[str, Any]:
    sigma_ins0 = float(vo2_params["sigma_ins0"])
    sigma_met0 = float(vo2_params["sigma_met0"])
    sigma_min = float(metrics["sigma_min"])
    sigma_max = float(metrics["sigma_max"])
    row = {
        "case_name": case_name,
        "conductivity_mode": metrics["conductivity_mode"],
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
    return row


def run_stress_preflight(
    config_path: Path,
    *,
    epochs_override: int | None = None,
    output_root_override: Path | None = None,
    summary_override: Path | None = None,
    cases_csv_override: Path | None = None,
) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    if epochs_override is not None:
        cfg["epochs"] = int(epochs_override)
    if int(cfg.get("epochs", 6)) > 20:
        raise ValueError("Phase-transition stress preflight must use epochs <= 20.")
    if output_root_override is not None:
        cfg["output_root"] = str(output_root_override)
    if summary_override is not None:
        cfg["summary_json"] = str(summary_override)
    if cases_csv_override is not None:
        cfg["cases_csv"] = str(cases_csv_override)

    seed = int(cfg.get("seed", 2026))
    seed_everything(seed)
    data_cfg = dict(cfg)
    data_cfg["output_dir"] = cfg.get("output_root", "outputs/pinn_inverse_v2/phase_transition_stress")
    data = load_inverse_v0_data(data_cfg, root=ROOT, verbose=True)
    output_root = ensure_dir(_resolve(cfg.get("output_root", "outputs/pinn_inverse_v2/phase_transition_stress")))
    summary_path = _resolve(cfg.get("summary_json", "outputs/tables/pinn_inverse_v2_phase_transition_stress_summary.json"))
    cases_csv_path = _resolve(cfg.get("cases_csv", "outputs/tables/pinn_inverse_v2_phase_transition_stress_cases.csv"))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    cases_csv_path.parent.mkdir(parents=True, exist_ok=True)

    before_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    before_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    device = torch.device(str(cfg.get("device", "cpu")))
    tensors = _prepare_tensors(data, cfg, seed, device)
    epochs = int(cfg.get("epochs", 6))
    conductivity_mode = str(cfg.get("conductivity_mode", "white_box_vo2_sigma"))
    if conductivity_mode != "white_box_vo2_sigma":
        raise ValueError("Stress preflight currently allows only white_box_vo2_sigma.")

    rows: list[dict[str, Any]] = []
    for case in cfg.get("stress_cases", []):
        case_cfg = deepcopy(cfg)
        case_name = str(case["case_name"])
        vo2_params = _merge_vo2_params(dict(cfg.get("vo2_params", {})), dict(case.get("vo2_params", {})))
        case_cfg["vo2_params"] = vo2_params
        seed_everything(seed)
        metrics = _run_one(
            run_cfg={"run_name": case_name, "conductivity_mode": conductivity_mode},
            base_cfg=case_cfg,
            data=data,
            tensors=tensors,
            device=device,
            epochs=epochs,
            seed=seed,
        )
        current_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
        current_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
        rows.append(_case_row(metrics, case_name, vo2_params, before_hashes == current_hashes and before_mtimes == current_mtimes))

    after_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    after_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    frozen_unchanged = before_hashes == after_hashes and before_mtimes == after_mtimes
    for row in rows:
        row["frozen_inputs_unchanged"] = bool(row["frozen_inputs_unchanged"] and frozen_unchanged)

    with cases_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})

    summary = {
        "benchmark": "synthetic numerical digital-twin phase-transition stress preflight",
        "claim_boundary": "stress preflight only; no F-SPS-PINN performance superiority claim",
        "config": _display_path(_resolve(config_path)),
        "train_data": _display_path(data.train_data_path),
        "sparse_obs": _display_path(data.sparse_obs_path),
        "output_root": _display_path(output_root),
        "summary_json": _display_path(summary_path),
        "cases_csv": _display_path(cases_csv_path),
        "epochs": epochs,
        "seed": seed,
        "num_cases": len(rows),
        "stress_cases": [row["case_name"] for row in rows],
        "all_finite_loss": bool(all(row["finite_loss"] for row in rows)),
        "all_used_vo2_sigma": bool(all(row["used_vo2_sigma"] and not row["used_free_log_sigma"] for row in rows)),
        "all_frozen_inputs_unchanged": bool(all(row["frozen_inputs_unchanged"] for row in rows) and frozen_unchanged),
        "max_sigma_dynamic_range": float(max((row["sigma_dynamic_range"] for row in rows), default=np.nan)),
        "rows": rows,
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
    parser.add_argument("--cases-csv", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_stress_preflight(
        args.config,
        epochs_override=args.epochs,
        output_root_override=args.output_root,
        summary_override=args.summary,
        cases_csv_override=args.cases_csv,
    )
    print(json.dumps({key: summary[key] for key in ["summary_json", "cases_csv", "num_cases", "all_finite_loss", "all_used_vo2_sigma", "all_frozen_inputs_unchanged"]}, indent=2))
    for row in summary["rows"]:
        print(json.dumps({key: row[key] for key in CSV_FIELDS}, indent=2))


if __name__ == "__main__":
    main()

"""Run a balanced F-SPS-PINN medium-budget benchmark subset.

The script plans the full model x epoch x seed matrix and executes at least one
seed for every model and epoch budget by default. Results are synthetic
numerical digital-twin evidence only and do not establish F-SPS-PINN
superiority.
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
from scripts.run_pinn_inverse_v2_baseline import _display_path, _prepare_tensors, _resolve, _sha256
from scripts.train_f_sps_medium_budget_benchmark import CSV_FIELDS, _blank_case, _run_case

DEFAULT_CONFIG = Path("configs/f_sps_balanced_medium_budget_benchmark.yaml")


def _coverage(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        if row.get("executed"):
            out[str(row[key])] = out.get(str(row[key]), 0) + 1
    return out


def _best_by(rows: list[dict[str, Any]], key: str) -> str | None:
    finite = [row for row in rows if row.get("executed") and row.get("finite_loss") and row.get(key) is not None]
    if not finite:
        return None
    return str(min(finite, key=lambda row: float(row[key]))["model_name"])


def _model_metric(rows: list[dict[str, Any]], model_name: str, key: str) -> float | None:
    vals = [float(row[key]) for row in rows if row.get("executed") and str(row["model_name"]) == model_name and row.get(key) is not None]
    if not vals:
        return None
    return float(np.mean(vals))


def _should_execute(seed: int, seeds: list[int], seed_count: int) -> bool:
    allowed = set(seeds[: max(int(seed_count), 1)])
    return int(seed) in allowed


def run_balanced_medium_budget(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    seeds = [int(value) for value in cfg["seeds"]]
    seed_count = int(cfg.get("execute_seed_count_per_model_epoch", 1))
    seed_everything(seeds[0])
    data_cfg = deepcopy(cfg)
    data_cfg["output_dir"] = cfg.get("output_root", "outputs/pinn_inverse_v2/f_sps_balanced_medium_budget")
    data = load_inverse_v0_data(data_cfg, root=ROOT, verbose=True)
    ensure_dir(_resolve(cfg.get("output_root", "outputs/pinn_inverse_v2/f_sps_balanced_medium_budget")))
    summary_path = _resolve(cfg["summary_json"])
    cases_path = _resolve(cfg["cases_csv"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.parent.mkdir(parents=True, exist_ok=True)

    before_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    before_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    device = torch.device(str(cfg.get("device", "cpu")))

    rows: list[dict[str, Any]] = []
    for epochs in cfg["epochs"]:
        for model_cfg in cfg["models"]:
            if not bool(model_cfg.get("enabled", True)):
                for seed in seeds:
                    rows.append(_blank_case(model_cfg, int(epochs), int(seed), str(model_cfg.get("disabled_reason", "disabled"))))
                continue
            for seed in seeds:
                if not _should_execute(int(seed), seeds, seed_count):
                    rows.append(_blank_case(model_cfg, int(epochs), int(seed), "not_executed_by_balanced_seed_budget"))
                    continue
                tensors = _prepare_tensors(data, cfg, int(seed), device)
                rows.append(
                    _run_case(
                        model_cfg=dict(model_cfg),
                        base_cfg=cfg,
                        data=data,
                        tensors=tensors,
                        device=device,
                        epochs=int(epochs),
                        seed=int(seed),
                    )
                )

    after_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    after_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    frozen_unchanged = bool(before_hashes == after_hashes and before_mtimes == after_mtimes)
    for row in rows:
        if row.get("executed"):
            row["frozen_inputs_unchanged"] = frozen_unchanged

    with cases_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})

    executed_rows = [row for row in rows if row.get("executed")]
    planned_cases = len([row for epoch in cfg["epochs"] for model in cfg["models"] if model.get("enabled", True) for row in seeds])
    f_sps_g = _model_metric(executed_rows, "f_sps_pinn", "relative_G_error")
    free_g = _model_metric(executed_rows, "free_log_sigma_pinn", "relative_G_error")
    fourier_g = _model_metric(executed_rows, "white_box_vo2_sigma_fourier", "relative_G_error")
    summary = {
        "benchmark": "synthetic numerical digital-twin balanced F-SPS medium-budget benchmark",
        "config": _display_path(_resolve(config_path)),
        "summary_json": _display_path(summary_path),
        "cases_csv": _display_path(cases_path),
        "planned_cases": int(planned_cases),
        "executed_cases": len(executed_rows),
        "all_executed_finite": bool(executed_rows and all(row.get("finite_loss") for row in executed_rows)),
        "coverage_by_model": _coverage(rows, "model_name"),
        "coverage_by_epoch": _coverage(rows, "epochs"),
        "best_model_by_G_error": _best_by(executed_rows, "relative_G_error"),
        "best_model_by_sigma_nrmse": _best_by(executed_rows, "nrmse_sigma"),
        "best_model_by_delta_T_nrmse": _best_by(executed_rows, "nrmse_delta_T"),
        "whether_f_sps_improves_over_free_log_sigma": bool(f_sps_g is not None and free_g is not None and f_sps_g < free_g),
        "whether_f_sps_improves_over_white_box_fourier": bool(f_sps_g is not None and fourier_g is not None and f_sps_g < fourier_g),
        "runs": rows,
        "frozen_hashes_before": before_hashes,
        "frozen_hashes_after": after_hashes,
        "frozen_mtimes_before": before_mtimes,
        "frozen_mtimes_after": after_mtimes,
        "frozen_inputs_unchanged": frozen_unchanged,
        "claim_boundary": cfg.get(
            "claim_boundary",
            "Balanced medium-budget evidence only; no F-SPS-PINN superiority claim is supported without stronger repeated runs.",
        ),
    }
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_balanced_medium_budget(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["summary_json"],
                "cases_csv": summary["cases_csv"],
                "planned_cases": summary["planned_cases"],
                "executed_cases": summary["executed_cases"],
                "all_executed_finite": summary["all_executed_finite"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

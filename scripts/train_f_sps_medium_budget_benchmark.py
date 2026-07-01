"""Run a bounded F-SPS-PINN medium-budget benchmark matrix.

The script plans the requested model/epoch/seed matrix and executes a bounded
subset by default. This keeps the evidence lightweight and reproducible on CPU
while making unexecuted cases explicit in the output tables.
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
    _final_metrics,
    _loss_and_diagnostics,
    _prepare_tensors,
    _resolve,
    _sha256,
    V2BaselineNet,
)

DEFAULT_CONFIG = Path("configs/f_sps_medium_budget_benchmark.yaml")
CSV_FIELDS = [
    "model_name",
    "conductivity_mode",
    "epochs",
    "seed",
    "executed",
    "disabled_reason",
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
    "fourier_enabled",
    "dynamic_gate_enabled",
    "gradient_norm_mean",
    "gradient_norm_max",
    "frozen_inputs_unchanged",
]


def _blank_case(model: dict[str, Any], epochs: int, seed: int, reason: str) -> dict[str, Any]:
    return {
        "model_name": str(model["model_name"]),
        "conductivity_mode": str(model["conductivity_mode"]),
        "epochs": int(epochs),
        "seed": int(seed),
        "executed": False,
        "disabled_reason": reason,
        "initial_loss": None,
        "final_loss": None,
        "finite_loss": False,
        "loss_decreased": False,
        "relative_G_error": None,
        "relative_I_error": None,
        "nrmse_delta_T": None,
        "nrmse_c_v": None,
        "nrmse_m": None,
        "nrmse_sigma": None,
        "sigma_min": None,
        "sigma_max": None,
        "used_vo2_sigma": bool(str(model["conductivity_mode"]) == "white_box_vo2_sigma"),
        "used_free_log_sigma": bool(str(model["conductivity_mode"]) == "free_log_sigma"),
        "fourier_enabled": bool(model.get("fourier_enabled", False)),
        "dynamic_gate_enabled": bool(model.get("dynamic_gate_enabled", False)),
        "gradient_norm_mean": None,
        "gradient_norm_max": None,
        "frozen_inputs_unchanged": None,
    }


def _grad_norm(model: torch.nn.Module) -> float:
    total = 0.0
    for param in model.parameters():
        if param.grad is not None:
            total += float(torch.sum(param.grad.detach() ** 2).cpu())
    return float(np.sqrt(total))


def _run_case(
    *,
    model_cfg: dict[str, Any],
    base_cfg: dict[str, Any],
    data: Any,
    tensors: dict[str, torch.Tensor],
    device: torch.device,
    epochs: int,
    seed: int,
) -> dict[str, Any]:
    seed_everything(seed)
    run_cfg = {"run_name": str(model_cfg["model_name"]), "conductivity_mode": str(model_cfg["conductivity_mode"])}
    run_base = deepcopy(base_cfg)
    run_base["fourier_enabled"] = bool(model_cfg.get("fourier_enabled", False))
    gt_c = np.asarray(data.gt["c_v"], dtype=float)
    gt_m = np.asarray(data.gt["m"], dtype=float)
    gt_sigma = np.asarray(data.gt["sigma"], dtype=float)
    bounds = dict(base_cfg.get("model_bounds", {}))
    model = V2BaselineNet(
        conductivity_mode=str(model_cfg["conductivity_mode"]),
        hidden_dim=int(base_cfg.get("hidden_dim", 32)),
        hidden_layers=int(base_cfg.get("hidden_layers", 2)),
        fourier_scales=[float(value) for value in base_cfg.get("fourier_scales", [1.0, 2.0, 4.0])],
        fourier_enabled=bool(model_cfg.get("fourier_enabled", False)),
        c_v_min=float(bounds.get("c_v_min", 0.0)),
        c_v_max=float(bounds.get("c_v_max", 0.2)),
        delta_T_max=float(bounds.get("delta_T_max", 20.0)),
        T0=float(data.params["T0"]),
        initial_c_v=float(np.mean(gt_c[0])),
        initial_m=float(np.mean(gt_m[0])),
        initial_sigma=float(np.mean(gt_sigma[0])),
        sigma_min=float(bounds.get("sigma_min", 1.0e-8)),
        sigma_max=float(bounds.get("sigma_max", 1.0)),
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(base_cfg.get("lr", 1.0e-3)))
    initial_loss: float | None = None
    final_diag: dict[str, torch.Tensor] | None = None
    final_state: dict[str, dict[str, torch.Tensor]] | None = None
    grad_norms: list[float] = []
    for _ in range(int(epochs)):
        optimizer.zero_grad(set_to_none=True)
        loss, diagnostics, state = _loss_and_diagnostics(model, data, run_base, tensors)
        if initial_loss is None:
            initial_loss = float(loss.detach().cpu())
        loss.backward()
        grad_norms.append(_grad_norm(model))
        optimizer.step()
        final_diag = diagnostics
        final_state = state
    if initial_loss is None or final_diag is None or final_state is None:
        raise RuntimeError("No medium-budget training epochs were executed.")
    metrics = _final_metrics(
        run_name=str(model_cfg["model_name"]),
        conductivity_mode=str(model_cfg["conductivity_mode"]),
        seed=seed,
        epochs=epochs,
        initial_loss=initial_loss,
        final_loss=float(final_diag["total_loss"].cpu()),
        finite_loss=bool(np.isfinite(initial_loss) and np.isfinite(float(final_diag["total_loss"].cpu()))),
        diagnostics=final_diag,
        state=final_state,
        tensors=tensors,
    )
    metrics.update(
        {
            "model_name": str(model_cfg["model_name"]),
            "executed": True,
            "disabled_reason": "",
            "fourier_enabled": bool(model_cfg.get("fourier_enabled", False)),
            "dynamic_gate_enabled": bool(model_cfg.get("dynamic_gate_enabled", False)),
            "gradient_norm_mean": float(np.mean(grad_norms)),
            "gradient_norm_max": float(np.max(grad_norms)),
            "frozen_inputs_unchanged": True,
        }
    )
    return metrics


def run_medium_budget(config_path: Path = DEFAULT_CONFIG, *, max_cases_override: int | None = None) -> dict[str, Any]:
    cfg = load_yaml(config_path)
    if max_cases_override is not None:
        cfg["max_executed_cases"] = int(max_cases_override)
    seed_everything(int(cfg.get("seeds", [2026])[0]))
    data_cfg = dict(cfg)
    data_cfg["output_dir"] = cfg.get("output_root", "outputs/pinn_inverse_v2/f_sps_medium_budget")
    data = load_inverse_v0_data(data_cfg, root=ROOT, verbose=True)
    ensure_dir(_resolve(cfg.get("output_root", "outputs/pinn_inverse_v2/f_sps_medium_budget")))
    summary_path = _resolve(cfg["summary_json"])
    cases_path = _resolve(cfg["cases_csv"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.parent.mkdir(parents=True, exist_ok=True)

    before_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    before_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    device = torch.device(str(cfg.get("device", "cpu")))
    rows: list[dict[str, Any]] = []
    executed = 0
    max_cases = int(cfg.get("max_executed_cases", 8))
    for epochs in cfg["epochs"]:
        for seed in cfg["seeds"]:
            for model_cfg in cfg["models"]:
                if not bool(model_cfg.get("enabled", True)):
                    rows.append(_blank_case(model_cfg, int(epochs), int(seed), str(model_cfg.get("disabled_reason", "disabled"))))
                    continue
                if executed >= max_cases:
                    rows.append(_blank_case(model_cfg, int(epochs), int(seed), "not_executed_due_to_cpu_budget_limit"))
                    continue
                tensors = _prepare_tensors(data, cfg, int(seed), device)
                rows.append(_run_case(model_cfg=model_cfg, base_cfg=cfg, data=data, tensors=tensors, device=device, epochs=int(epochs), seed=int(seed)))
                executed += 1

    after_hashes = {"train_data": _sha256(data.train_data_path), "sparse_obs": _sha256(data.sparse_obs_path)}
    after_mtimes = {"train_data": data.train_data_path.stat().st_mtime_ns, "sparse_obs": data.sparse_obs_path.stat().st_mtime_ns}
    frozen_unchanged = before_hashes == after_hashes and before_mtimes == after_mtimes
    for row in rows:
        if row["executed"]:
            row["frozen_inputs_unchanged"] = frozen_unchanged
    executed_rows = [row for row in rows if row["executed"]]
    finite_rows = [row for row in executed_rows if row["finite_loss"]]
    best = min(finite_rows, key=lambda row: float(row["relative_G_error"])) if finite_rows else None

    with cases_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in CSV_FIELDS})

    summary = {
        "benchmark": "synthetic numerical digital-twin F-SPS medium-budget benchmark planning matrix",
        "config": _display_path(_resolve(config_path)),
        "summary_json": _display_path(summary_path),
        "cases_csv": _display_path(cases_path),
        "planned_cases": len(rows),
        "executed_cases": len(executed_rows),
        "skipped_cases": len(rows) - len(executed_rows),
        "all_executed_finite": bool(executed_rows and all(row["finite_loss"] for row in executed_rows)),
        "best_executed_model_by_relative_G_error": best,
        "execution_budget_note": "Config contains 3 epoch budgets and 3 seeds; default execution is capped to keep CPU smoke/medium-budget evidence lightweight.",
        "dynamic_gate_status": "f_sps_pinn_with_dynamic_gate is registered but disabled because dynamic gate is a deferred extension.",
        "runs": rows,
        "frozen_hashes_before": before_hashes,
        "frozen_hashes_after": after_hashes,
        "frozen_mtimes_before": before_mtimes,
        "frozen_mtimes_after": after_mtimes,
        "frozen_inputs_unchanged": frozen_unchanged,
        "claim_boundary": "Medium-budget benchmark evidence only; no F-SPS-PINN superiority claim is supported unless repeated full-budget runs confirm it.",
    }
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()
    summary = run_medium_budget(args.config, max_cases_override=args.max_cases)
    print(json.dumps({"summary_json": summary["summary_json"], "cases_csv": summary["cases_csv"], "executed_cases": summary["executed_cases"], "all_executed_finite": summary["all_executed_finite"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


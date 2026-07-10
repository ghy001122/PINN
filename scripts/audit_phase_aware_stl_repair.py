"""Phase-aware STL repair audit with actual torch smoke training.

This is a reduced synthetic transfer-diagnostic audit, not a full STL-PINN
reproduction and not experimental validation.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_integrated_stiffness_stl import _run_algorithm
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/phase_aware_stl_repair_summary.json")
CASES_CSV = Path("outputs/tables/phase_aware_stl_repair_cases.csv")
FIG_GAIN = Path("outputs/figures/phase_aware_stl_gain.png")
ALGORITHMS = ["continuation_asinh", "progressive_width_stl", "adapter_stl"]
INTEGRATED_MAP = {"continuation_asinh": "continuation_plus_asinh", "progressive_width_stl": "STL_repair_unfrozen_tail", "adapter_stl": "STL_repair_head_only"}
CSV_FIELDS = ["algorithm", "seed", "noise", "target_transition_width", "relative_error", "success", "success_rate_proxy", "gradient_spike", "front_position_error", "residual_imbalance", "transfer_gain", "representation_drift", "finite_result", "claim_status", "is_actual_stl_training", "factor_model_only"]


def _actual_case(algorithm: str, seed: int, noise: float, cfg: dict[str, Any]) -> dict[str, Any]:
    raw = _run_algorithm(INTEGRATED_MAP[algorithm], seed, noise, 0.05, cfg)
    rel = float(raw["relative_error"])
    front = float(abs(rel - 0.75) / max(rel + 0.75, 1.0e-9))
    return {"algorithm": algorithm, "seed": int(seed), "noise": float(noise), "target_transition_width": 0.05, "relative_error": rel, "success": bool(raw["success"]), "success_rate_proxy": float(raw["success"]), "gradient_spike": float(raw["gradient_spike"]), "front_position_error": front, "residual_imbalance": float(raw["residual_imbalance"]), "transfer_gain": 0.0, "representation_drift": float(raw["representation_drift_metric"]), "finite_result": bool(raw["finite_result"]), "claim_status": "pending", "is_actual_stl_training": True, "factor_model_only": False}


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS); w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in CSV_FIELDS})


def _plot(summary: dict[str, Any]) -> None:
    FIG_GAIN.parent.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(ALGORITHMS)); vals = [summary["transfer_gain_by_algorithm"][a] for a in ALGORITHMS]
    fig, ax = plt.subplots(figsize=(7.2, 4.0)); ax.bar(x, vals); ax.axhline(0.20, color="black", linestyle="--")
    ax.set_xticks(x); ax.set_xticklabels(ALGORITHMS, rotation=25, ha="right")
    ax.set_ylabel("gain over continuation_asinh"); ax.set_title("Actual torch phase-aware STL smoke")
    fig.tight_layout(); fig.savefig(ROOT / FIG_GAIN, dpi=150); plt.close(fig)


def run_phase_aware_stl_repair() -> dict[str, Any]:
    cfg = {"collocation_points": 32, "eval_points": 40, "hidden_dim": 14, "lr": 0.025, "stl_low_epochs": 1, "stl_transfer_epochs": 2, "stl_unfreeze_epochs": 1, "repair_low_epochs": 1, "repair_head_epochs": 2, "repair_tail_epochs": 1, "low_width_heads": [0.3, 0.2, 0.1, 0.075]}
    rows = [_actual_case(a, s, n, cfg) for a in ALGORITHMS for n in [0.0, 0.02] for s in [2026, 2027]]
    cont = { (r["seed"], r["noise"]): r["relative_error"] for r in rows if r["algorithm"] == "continuation_asinh" }
    for r in rows:
        base = cont[(r["seed"], r["noise"])]
        r["transfer_gain"] = float((base - r["relative_error"]) / max(base, 1.0e-12)) if r["algorithm"] != "continuation_asinh" else 0.0
    gain = {a: float(np.median([r["transfer_gain"] for r in rows if r["algorithm"] == a])) for a in ALGORITHMS}
    success = {a: float(np.mean([r["success"] for r in rows if r["algorithm"] == a])) for a in ALGORITHMS}
    best = max(ALGORITHMS, key=lambda a: gain[a])
    status = "qualified_supported" if gain[best] >= 0.20 and success[best] > success["continuation_asinh"] else ("failed_but_informative" if gain[best] > 0 else "failed_but_informative")
    for r in rows:
        r["claim_status"] = status if r["algorithm"] == best else "failed_but_informative"
    summary = {"benchmark": "phase_aware_stl_repair", "note": "Synthetic numerical actual torch reduced transfer diagnostic; not full STL-PINN reproduction.", "num_cases": len(rows), "actual_torch_stl_smoke": True, "is_actual_stl_training": True, "factor_model_only": False, "best_algorithm": best, "transfer_gain_by_algorithm": gain, "success_rate_by_algorithm": success, "phase_aware_stl_status": status, "full_stl_claim": "forbidden", "full_stl_pinn_reproduction_status": "forbidden", "forbidden_claims": ["full STL-PINN reproduction", "experimental validation"], "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/"), "gain_figure": str(FIG_GAIN).replace("\\", "/")}}
    _write_cases(ROOT / CASES_CSV, rows); _plot(summary); write_json(ROOT / SUMMARY_JSON, summary); return summary


def main() -> None:
    argparse.ArgumentParser().parse_args(); print(run_phase_aware_stl_repair())


if __name__ == "__main__": main()

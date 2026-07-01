"""Build lightweight SCI planning figures from high-throughput audit tables."""

from __future__ import annotations

import csv
import json
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


FIG_DIR = ROOT / "outputs" / "figures" / "high_throughput_sci"


def _read_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(fig: plt.Figure, name: str) -> str:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path.relative_to(ROOT))


def _dense_profile_landscape() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_tsw_dense_profile_likelihood_grid.csv")
    gammas = sorted({float(row["gamma_sub"]) for row in rows})
    offsets = sorted({float(row["T_sw_offset_K"]) for row in rows})
    z = np.full((len(offsets), len(gammas)), np.nan)
    gi = {value: idx for idx, value in enumerate(gammas)}
    oi = {value: idx for idx, value in enumerate(offsets)}
    for row in rows:
        z[oi[float(row["T_sw_offset_K"])], gi[float(row["gamma_sub"])]] = float(row["objective"])
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    im = ax.imshow(z, origin="lower", aspect="auto", extent=[min(gammas), max(gammas), min(offsets), max(offsets)])
    ax.set_xscale("log")
    ax.set_xlabel("gamma_sub")
    ax.set_ylabel("T_sw offset (K)")
    ax.set_title("Dense response-surface profile likelihood")
    fig.colorbar(im, ax=ax, label="objective")
    return _save(fig, "dense_profile_landscape.png")


def _profile_uncertainty_intervals() -> str:
    summary = _read_json("outputs/tables/gamma_sub_tsw_dense_profile_likelihood_summary.json")
    rows = []
    for key, value in summary["ridge_widths"].items():
        rows.append((key, value.get("gamma_sub_uncertainty_interval", [np.nan, np.nan]), value.get("T_sw_uncertainty_interval", [np.nan, np.nan])))
    labels = [row[0].replace("threshold_", "") for row in rows]
    gamma_width = [float(row[1][1]) - float(row[1][0]) if row[1] else 0.0 for row in rows]
    tsw_width = [float(row[2][1]) - float(row[2][0]) if row[2] else 0.0 for row in rows]
    x = np.arange(len(labels))
    fig, ax1 = plt.subplots(figsize=(6.4, 4.0))
    ax1.bar(x - 0.18, gamma_width, width=0.36, label="gamma_sub interval width")
    ax2 = ax1.twinx()
    ax2.bar(x + 0.18, tsw_width, width=0.36, color="tab:orange", label="T_sw interval width")
    ax1.set_xticks(x, labels)
    ax1.set_xlabel("objective threshold")
    ax1.set_ylabel("gamma_sub width")
    ax2.set_ylabel("T_sw width (K)")
    ax1.set_title("Profile uncertainty intervals")
    return _save(fig, "profile_uncertainty_intervals.png")


def _recoverability_phase_diagram() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_recoverability_phase_diagram_cases.csv")
    protocols = sorted({row["protocol"] for row in rows})
    widths = sorted({float(row["T_sw_prior_width"]) for row in rows})
    z = np.zeros((len(protocols), len(widths)))
    for i, protocol in enumerate(protocols):
        for j, width in enumerate(widths):
            sub = [row for row in rows if row["protocol"] == protocol and float(row["T_sw_prior_width"]) == width]
            z[i, j] = np.mean([row["recoverable_le_0p2"] == "True" for row in sub]) if sub else 0.0
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    im = ax.imshow(z, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(np.arange(len(widths)), [str(v) for v in widths])
    ax.set_yticks(np.arange(len(protocols)), protocols)
    ax.set_xlabel("T_sw prior width")
    ax.set_title("Recoverability rate <= 20% error")
    fig.colorbar(im, ax=ax, label="rate")
    return _save(fig, "recoverability_phase_diagram.png")


def _protocol_actual_validation() -> str:
    summary = _read_json("outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json")
    names = list(summary["by_protocol"].keys())
    means = [summary["by_protocol"][name]["mean_relative_error"] for name in names]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.bar(np.arange(len(names)), means)
    ax.set_xticks(np.arange(len(names)), names, rotation=35, ha="right")
    ax.set_ylabel("mean relative error")
    ax.set_title("Protocol actual response-surface validation")
    return _save(fig, "protocol_actual_validation.png")


def _weighted_protocol_objective() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_weighted_protocol_objective_cases.csv")
    names = [row["combination_name"] for row in rows]
    errors = [float(row["relative_error"]) for row in rows]
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ax.bar(np.arange(len(names)), errors)
    ax.set_xticks(np.arange(len(names)), names, rotation=45, ha="right")
    ax.set_ylabel("relative error")
    ax.set_title("Weighted protocol objective")
    return _save(fig, "weighted_protocol_objective.png")


def _statistical_robustness_boxplot() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_statistical_robustness_cases.csv")
    protocols = sorted({row["protocol"] for row in rows})
    values = [[float(row["relative_error"]) for row in rows if row["protocol"] == protocol] for protocol in protocols]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.boxplot(values, labels=protocols, showfliers=False)
    ax.set_ylabel("relative error")
    ax.set_title("Bootstrap/noise/seed robustness")
    return _save(fig, "statistical_robustness_boxplot.png")


def _f_sps_medium_budget_benchmark() -> str:
    rows = [row for row in _read_csv("outputs/tables/f_sps_medium_budget_benchmark_cases.csv") if row["executed"] == "True"]
    labels = [f"{row['model_name']}\n{row['epochs']}e/{row['seed']}" for row in rows]
    errors = [float(row["relative_G_error"]) for row in rows]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.bar(np.arange(len(labels)), errors)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=45, ha="right")
    ax.set_ylabel("relative G error")
    ax.set_title("Executed F-SPS medium-budget cases")
    return _save(fig, "f_sps_medium_budget_benchmark.png")


def build_all() -> dict[str, Any]:
    outputs = [
        _dense_profile_landscape(),
        _profile_uncertainty_intervals(),
        _recoverability_phase_diagram(),
        _protocol_actual_validation(),
        _weighted_protocol_objective(),
        _statistical_robustness_boxplot(),
        _f_sps_medium_budget_benchmark(),
    ]
    return {"figure_dir": str(FIG_DIR.relative_to(ROOT)), "figures": outputs}


def main() -> None:
    print(json.dumps(build_all(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

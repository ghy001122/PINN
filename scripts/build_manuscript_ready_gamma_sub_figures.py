"""Build manuscript-ready planning figures for the gamma_sub evidence chain."""

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

FIG_DIR = ROOT / "outputs" / "figures" / "manuscript_ready_gamma_sub"


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


def _figure_confounding_profile() -> str:
    profile_rows = _read_csv("outputs/tables/gamma_sub_tsw_dense_profile_likelihood_grid.csv")
    gammas = sorted({float(row["gamma_sub"]) for row in profile_rows})
    offsets = sorted({float(row["T_sw_offset_K"]) for row in profile_rows})
    z = np.full((len(offsets), len(gammas)), np.nan)
    gi = {value: idx for idx, value in enumerate(gammas)}
    oi = {value: idx for idx, value in enumerate(offsets)}
    for row in profile_rows:
        z[oi[float(row["T_sw_offset_K"])], gi[float(row["gamma_sub"])]] = float(row["objective"])

    recovery_rows = _read_csv("outputs/tables/gamma_sub_continuous_refinement_cases.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))

    im = axes[0].imshow(
        z,
        origin="lower",
        aspect="auto",
        extent=[min(gammas), max(gammas), min(offsets), max(offsets)],
    )
    axes[0].set_xscale("log")
    axes[0].set_xlabel("gamma_sub (W m$^{-3}$ K$^{-1}$)")
    axes[0].set_ylabel("T_sw offset (K)")
    axes[0].set_title("(a) gamma_sub/T_sw objective ridge")
    fig.colorbar(im, ax=axes[0], label="objective")

    noise_levels = sorted({float(row["noise_level"]) for row in recovery_rows})
    colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(noise_levels)))
    for noise, color in zip(noise_levels, colors):
        subset = [row for row in recovery_rows if float(row["noise_level"]) == noise]
        truth = np.asarray([float(row["true_gamma_sub"]) for row in subset]) / 1.0e8
        estimate = np.asarray([float(row["continuous_refined_gamma_sub"]) for row in subset]) / 1.0e8
        sizes = np.asarray([float(row["n_obs"]) for row in subset]) * 2.2
        axes[1].scatter(truth, estimate, s=sizes, color=color, alpha=0.72, label=f"noise={noise:g}")
    all_truth = np.asarray([float(row["true_gamma_sub"]) for row in recovery_rows]) / 1.0e8
    all_estimate = np.asarray([float(row["continuous_refined_gamma_sub"]) for row in recovery_rows]) / 1.0e8
    low = min(float(np.min(all_truth)), float(np.min(all_estimate))) * 0.98
    high = max(float(np.max(all_truth)), float(np.max(all_estimate))) * 1.02
    axes[1].plot([low, high], [low, high], color="black", linestyle="--", linewidth=1.0)
    axes[1].set_xlim(low, high)
    axes[1].set_ylim(low, high)
    axes[1].set_xlabel("true off-grid gamma_sub ($10^8$ W m$^{-3}$ K$^{-1}$)")
    axes[1].set_ylabel("continuous estimate ($10^8$ W m$^{-3}$ K$^{-1}$)")
    axes[1].set_title("(b) constrained off-grid recovery (36 cases)")
    axes[1].legend(fontsize=7, loc="best")
    axes[1].text(0.98, 0.03, "marker size proportional to n_obs", transform=axes[1].transAxes, ha="right", fontsize=7)

    return _save(fig, "main_figure_2_confounding_profile.png")


def _figure_recoverability() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_recoverability_phase_diagram_cases.csv")
    protocols = sorted({row["protocol"] for row in rows})
    widths = sorted({float(row["T_sw_prior_width"]) for row in rows})
    z = np.zeros((len(protocols), len(widths)))
    for i, protocol in enumerate(protocols):
        for j, width in enumerate(widths):
            sub = [row for row in rows if row["protocol"] == protocol and float(row["T_sw_prior_width"]) == width]
            z[i, j] = np.mean([row["recoverable_le_0p1"] == "True" for row in sub]) if sub else 0.0
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    im = ax.imshow(z, vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(np.arange(len(widths)), [str(value) for value in widths])
    ax.set_yticks(np.arange(len(protocols)), protocols)
    ax.set_xlabel("T_sw prior width")
    ax.set_title("Recoverability rate <= 10% error")
    fig.colorbar(im, ax=ax, label="rate")
    return _save(fig, "main_figure_3_recoverability_phase_diagram.png")


def _figure_anchor_verification() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv")
    sim = np.asarray([float(row["simulator_backed_error"]) for row in rows], dtype=float)
    pred = np.asarray([float(row["response_surface_predicted_error"]) for row in rows], dtype=float)
    regions = sorted({row["anchor_region"] for row in rows})
    fig, ax = plt.subplots(figsize=(5.2, 4.8))
    for region in regions:
        idx = [i for i, row in enumerate(rows) if row["anchor_region"] == region]
        ax.scatter(sim[idx], pred[idx], s=24, label=region, alpha=0.8)
    lim = [0.0, max(float(np.max(sim)), float(np.max(pred)), 0.1)]
    ax.plot(lim, lim, color="black", linewidth=1.0, linestyle="--")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("simulator-backed anchor error")
    ax.set_ylabel("response-surface predicted error")
    ax.set_title("Response-surface anchor verification")
    ax.legend(fontsize=7, loc="best")
    return _save(fig, "main_figure_4_anchor_verification.png")


def _figure_protocol_design() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_sequential_protocol_design_cases.csv")
    names = [row["candidate_name"] for row in rows]
    errors = [float(row["stage2_gamma_error"]) for row in rows]
    voi = [float(row["cost_normalized_score"]) for row in rows]
    x = np.arange(len(names))
    fig, ax1 = plt.subplots(figsize=(8.8, 4.2))
    ax1.bar(x - 0.18, errors, width=0.36, label="gamma error")
    ax2 = ax1.twinx()
    ax2.bar(x + 0.18, voi, width=0.36, color="tab:orange", label="cost-normalized VOI")
    ax1.set_xticks(x, names, rotation=45, ha="right")
    ax1.set_ylabel("relative gamma error")
    ax2.set_ylabel("VOI / cost")
    ax1.set_title("Sequential protocol design preflight")
    return _save(fig, "main_figure_5_protocol_design.png")


def _figure_statistical_robustness() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_statistical_robustness_cases.csv")
    scenarios = sorted({row["scenario"] for row in rows})
    values = [[float(row["relative_error"]) for row in rows if row["scenario"] == scenario] for scenario in scenarios]
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.boxplot(values, labels=scenarios, showfliers=False)
    ax.set_ylabel("relative gamma error")
    ax.set_title("Noise/seed robustness by scenario")
    return _save(fig, "main_figure_6_statistical_robustness.png")


def _figure_f_sps_balanced() -> str:
    rows = [row for row in _read_csv("outputs/tables/f_sps_balanced_medium_budget_benchmark_cases.csv") if row["executed"] == "True"]
    labels = [f"{row['model_name']}\n{row['epochs']}e" for row in rows]
    errors = [float(row["relative_G_error"]) for row in rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    ax.bar(np.arange(len(labels)), errors)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=55, ha="right")
    ax.set_ylabel("relative G error")
    ax.set_title("Balanced F-SPS medium-budget appendix check")
    return _save(fig, "appendix_f_sps_balanced_benchmark.png")


def build_all() -> dict[str, Any]:
    figures = [
        _figure_confounding_profile(),
        _figure_recoverability(),
        _figure_anchor_verification(),
        _figure_protocol_design(),
        _figure_statistical_robustness(),
        _figure_f_sps_balanced(),
    ]
    return {
        "benchmark": "synthetic numerical digital-twin manuscript-ready gamma_sub figures",
        "figure_dir": str(FIG_DIR.relative_to(ROOT)),
        "figures": figures,
        "note": "Figures are generated from lightweight JSON/CSV evidence and are ignored by Git by default.",
    }


def main() -> None:
    print(json.dumps(build_all(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

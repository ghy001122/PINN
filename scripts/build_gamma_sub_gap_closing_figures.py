"""Build figure-ready gamma_sub gap-closing plots.

The figures are generated from lightweight JSON/CSV evidence tables and are
reproducible. They are synthetic numerical digital-twin benchmark visuals, not
experimental data.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTDIR = Path("outputs/figures/gamma_sub_gap_closing")


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _phase_map(summary_path: Path, out_path: Path) -> None:
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    matrix = data["relative_error_matrix"]
    deltas = [float(value) for value in matrix["T_sw_delta_K"]]
    widths = [float(value) for value in matrix["T_sw_prior_widths"]]
    values = np.asarray(matrix["values"], dtype=float)
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    im = ax.imshow(values, origin="lower", aspect="auto", cmap="viridis", vmin=0.0)
    ax.set_xticks(range(len(deltas)), [f"{value:g}" for value in deltas])
    ax.set_yticks(range(len(widths)), [f"{value:g}" for value in widths])
    ax.set_xlabel("T_sw calibration-error stress amplitude (K)")
    ax.set_ylabel("Residual T_sw prior width")
    ax.set_title("gamma_sub relative error phase map")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            text_color = "white" if values[i, j] > 0.35 else "black"
            ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", color=text_color, fontsize=8)
    fig.colorbar(im, ax=ax, label="relative error")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _prior_width_curve(csv_path: Path, out_path: Path) -> None:
    rows = _read_csv(csv_path)
    rows = sorted(rows, key=lambda row: float(row["T_sw_prior_width"]))
    x = [float(row["T_sw_prior_width"]) for row in rows]
    y = [float(row["relative_error"]) for row in rows]
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.plot(x, y, marker="o", linewidth=2)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("T_sw prior width")
    ax.set_ylabel("gamma_sub relative error")
    ax.set_title("Prior-width narrowing reduces gamma_sub bias")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _anchor_bar(csv_path: Path, out_path: Path) -> None:
    rows = _read_csv(csv_path)
    labels = [row["case_name"].replace("_anchors", "").replace("random_", "rand_") for row in rows]
    y = [float(row["gamma_relative_error"]) for row in rows]
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.bar(range(len(rows)), y, color="#4c78a8")
    ax.set_xticks(range(len(rows)), labels, rotation=35, ha="right")
    ax.set_ylabel("gamma_sub relative error")
    ax.set_title("Temperature-anchor placement did not reduce wide T_sw bias")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _scalar_baseline(csv_path: Path, out_path: Path) -> None:
    rows = _read_csv(csv_path)
    labels = [f"{row['target_case']}\n{row['method'].replace('_', ' ')}" for row in rows]
    y = [max(float(row["relative_error"]), 1.0e-8) for row in rows]
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    ax.bar(range(len(rows)), y, color="#59a14f")
    ax.set_yscale("log")
    ax.set_xticks(range(len(rows)), labels, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("gamma_sub relative error (log scale)")
    ax.set_title("Scalar baselines are strong for the reduced gamma_sub target")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)



def _auxiliary_heatmap(csv_path: Path, out_path: Path) -> None:
    rows = [row for row in _read_csv(csv_path) if float(row["noise"]) == 0.0]
    modes = [
        "port_plus_sparse_T",
        "port_plus_T_temporal_derivative_proxy",
        "port_plus_m_proxy",
        "port_plus_sigma_aggregate_proxy",
    ]
    anchors = sorted({int(row["anchor_count"]) for row in rows if row["observation_mode"] in modes})
    values = np.full((len(modes), len(anchors)), np.nan, dtype=float)
    for i, mode in enumerate(modes):
        for j, anchor in enumerate(anchors):
            selected = [row for row in rows if row["observation_mode"] == mode and int(row["anchor_count"]) == anchor]
            if selected:
                values[i, j] = min(float(row["relative_error"]) for row in selected)
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    im = ax.imshow(values, origin="lower", aspect="auto", cmap="magma_r", vmin=0.0, vmax=max(1.25, float(np.nanmax(values))))
    ax.set_xticks(range(len(anchors)), [str(anchor) for anchor in anchors])
    ax.set_yticks(range(len(modes)), [mode.replace("port_plus_", "").replace("_proxy", "") for mode in modes])
    ax.set_xlabel("auxiliary anchor count")
    ax.set_title("Best gamma_sub relative error by auxiliary proxy")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            if np.isfinite(values[i, j]):
                ax.text(j, i, f"{values[i, j]:.2f}", ha="center", va="center", color="black", fontsize=8)
    fig.colorbar(im, ax=ax, label="relative error")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _auxiliary_mode_comparison(csv_path: Path, out_path: Path) -> None:
    rows = _read_csv(csv_path)
    modes = sorted({row["observation_mode"] for row in rows})
    best = []
    for mode in modes:
        selected = [row for row in rows if row["observation_mode"] == mode]
        best.append(min(float(row["relative_error"]) for row in selected))
    labels = [mode.replace("port_plus_", "+ ").replace("port_only", "port only").replace("_", " ") for mode in modes]
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    ax.bar(range(len(modes)), best, color="#e15759")
    ax.set_xticks(range(len(modes)), labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("best gamma_sub relative error")
    ax.set_title("Auxiliary observability mode comparison")
    ax.axhline(0.1, color="black", linestyle="--", linewidth=1, label="0.1 threshold")
    ax.axhline(0.2, color="gray", linestyle=":", linewidth=1, label="0.2 threshold")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)

def build_gap_closing_figures(outdir: Path = DEFAULT_OUTDIR) -> dict[str, Any]:
    outdir = _resolve(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "tsw_confounding_phase_map": outdir / "tsw_confounding_phase_map.png",
        "tsw_prior_width_error_curve": outdir / "tsw_prior_width_error_curve.png",
        "anchor_placement_bar": outdir / "anchor_placement_bar.png",
        "scalar_baseline_comparison": outdir / "scalar_baseline_comparison.png",
        "auxiliary_observability_heatmap": outdir / "auxiliary_observability_heatmap.png",
        "auxiliary_mode_comparison": outdir / "auxiliary_mode_comparison.png",
    }
    _phase_map(_resolve("outputs/tables/gamma_sub_tsw_confounding_phase_map_summary.json"), outputs["tsw_confounding_phase_map"])
    _prior_width_curve(_resolve("outputs/tables/gamma_sub_tsw_prior_width_sweep_cases.csv"), outputs["tsw_prior_width_error_curve"])
    _anchor_bar(_resolve("outputs/tables/gamma_sub_temperature_anchor_placement_cases.csv"), outputs["anchor_placement_bar"])
    _scalar_baseline(_resolve("outputs/tables/gamma_sub_scalar_baseline_comparison.csv"), outputs["scalar_baseline_comparison"])
    _auxiliary_heatmap(_resolve("outputs/tables/gamma_sub_auxiliary_observability_sweep_cases.csv"), outputs["auxiliary_observability_heatmap"])
    _auxiliary_mode_comparison(_resolve("outputs/tables/gamma_sub_auxiliary_observability_sweep_cases.csv"), outputs["auxiliary_mode_comparison"])
    return {"outputs": {key: _display(path) for key, path in outputs.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    args = parser.parse_args()
    print(json.dumps(build_gap_closing_figures(args.outdir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build manuscript-style gamma_sub figures from lightweight evidence tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "outputs" / "figures" / "manuscript_style_gamma_sub"


def _read_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _read_csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(fig: plt.Figure, name: str) -> str:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return str(path.relative_to(ROOT))


def _apply_style(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=10)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, linewidth=0.4, alpha=0.35)


def _plot_tsw_necessity() -> str:
    rows = _read_csv("outputs/tables/gamma_sub_tsw_calibration_necessity_cases.csv")
    names = [row["case_name"].replace("_", "\n") for row in rows]
    errors = [float(row["relative_error"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.bar(np.arange(len(rows)), errors, color="#5277a3")
    ax.axhline(0.15, color="black", linestyle="--", linewidth=1.0, label="15% threshold")
    ax.set_xticks(np.arange(len(rows)), names, rotation=35, ha="right")
    _apply_style(ax, "T_sw calibration controls gamma_sub recovery", "case", "relative gamma_sub error")
    ax.legend(fontsize=8)
    return _save(fig, "figure_tsw_calibration_necessity.png")


def _plot_sequential_validation() -> str:
    summary = _read_json("outputs/tables/gamma_sub_simulator_backed_sequential_protocol_validation_summary.json")
    items = sorted(summary["by_candidate"].items())
    names = [name.replace("_", "\n") for name, _ in items]
    means = [float(stats["mean_relative_error"]) for _, stats in items]
    maxes = [float(stats["max_relative_error"]) for _, stats in items]
    x = np.arange(len(items))
    fig, ax = plt.subplots(figsize=(8.0, 3.9))
    ax.bar(x - 0.18, means, width=0.36, label="mean")
    ax.bar(x + 0.18, maxes, width=0.36, label="max", color="#c27a43")
    ax.set_xticks(x, names, rotation=35, ha="right")
    _apply_style(ax, "Simulator-backed sequential protocol check", "candidate", "relative gamma_sub error")
    ax.legend(fontsize=8)
    return _save(fig, "figure_simulator_backed_protocol_validation.png")


def _plot_literature_sanity() -> str:
    rows = _read_csv("data/literature/literature_parameter_sanity_table.csv")
    labels = [row["parameter_name"].replace("_", "\n") for row in rows]
    flags = [1.0 if row["within_literature_range"] == "True" else 0.0 for row in rows]
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    ax.bar(np.arange(len(rows)), flags, color=["#4f8f5f" if v > 0 else "#b85b5b" for v in flags])
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([0, 1], ["boundary", "plausible"])
    ax.set_xticks(np.arange(len(rows)), labels, rotation=40, ha="right")
    _apply_style(ax, "Literature/engineering-prior sanity checks", "parameter", "status")
    return _save(fig, "figure_literature_parameter_sanity.png")


def build_all() -> dict[str, Any]:
    figures = []
    for builder in (_plot_tsw_necessity, _plot_sequential_validation, _plot_literature_sanity):
        try:
            figures.append(builder())
        except FileNotFoundError:
            continue
    return {"benchmark": "synthetic numerical digital-twin manuscript-style gamma_sub figures", "figure_dir": str(FIG_DIR.relative_to(ROOT)), "figures": figures, "note": "Figures are generated from lightweight JSON/CSV evidence and are ignored by Git by default."}


def main() -> None:
    print(json.dumps(build_all(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

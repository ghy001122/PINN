"""Build submission-ready gamma_sub figure drafts from lightweight tables."""

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
FIG_DIR = ROOT / "outputs/figures/submission_ready_gamma_sub"
SUMMARY = ROOT / "outputs/tables/submission_ready_gamma_sub_figures_summary.json"


def _json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _csv(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(fig: plt.Figure, name: str) -> str:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(out, dpi=220)
    plt.close(fig)
    return str(out.relative_to(ROOT))


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=10)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.3, linewidth=0.4)
    ax.tick_params(labelsize=8)


def fig_calibration_workflow() -> str:
    rows = _csv("outputs/tables/gamma_sub_tsw_calibration_workflow_cases.csv")
    labels = [r["workflow"].replace("_", "\n") for r in rows]
    err = [float(r["relative_error"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    ax.bar(np.arange(len(rows)), err, color="#4f78a8")
    ax.axhline(0.15, color="black", linestyle="--", linewidth=1, label="15% threshold")
    ax.set_xticks(np.arange(len(rows)), labels, rotation=35, ha="right")
    _style(ax, "Figure 2 draft: T_sw calibration before gamma_sub inversion", "workflow", "relative gamma_sub error")
    ax.legend(fontsize=8)
    return _save(fig, "figure_2_calibration_workflow.png")


def fig_calibrated_protocol() -> str:
    summary = _json("outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json")
    items = sorted(summary["median_error_by_protocol"].items())
    labels = [k.replace("_", "\n") for k, _ in items]
    med = [float(v) for _, v in items]
    fig, ax = plt.subplots(figsize=(8.8, 4.0))
    ax.bar(np.arange(len(items)), med, color="#5d8f62")
    ax.axhline(0.15, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(np.arange(len(items)), labels, rotation=35, ha="right")
    _style(ax, "Figure 5 draft: calibrated sequential protocol validation", "protocol", "median relative gamma_sub error")
    return _save(fig, "figure_5_calibrated_protocol_validation.png")


def fig_external_anchor() -> str:
    sanity = _csv("data/literature/literature_parameter_sanity_table.csv")
    fit = _json("outputs/tables/literature_curve_fit_external_anchor_v2_summary.json")
    labels = ["parameter\nsanity", "curve\nfit"]
    values = [sum(1 for r in sanity if r["within_literature_range"] == "True") / max(len(sanity), 1), 1.0 if fit["num_curves_fit"] else 0.0]
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    ax.bar(labels, values, color=["#4f78a8", "#b85b5b" if values[1] == 0 else "#5d8f62"])
    ax.set_ylim(0, 1.05)
    _style(ax, "Figure 4 draft: literature anchor status", "external anchor", "readiness score")
    return _save(fig, "figure_4_external_anchor_status.png")


def build_submission_figures() -> dict[str, Any]:
    figures = []
    for fn in (fig_calibration_workflow, fig_calibrated_protocol, fig_external_anchor):
        figures.append(fn())
    payload = {"benchmark": "submission_ready_gamma_sub_figures", "note": "Figure drafts are synthetic numerical digital-twin evidence and are ignored by Git.", "figure_dir": str(FIG_DIR.relative_to(ROOT)), "figures": figures}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    print(json.dumps(build_submission_figures(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

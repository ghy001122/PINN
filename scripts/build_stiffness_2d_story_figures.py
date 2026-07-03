"""Build supplementary stiffness, phase-field, and quasi-2D story figures.

The figures are generated from existing lightweight JSON/CSV evidence. They are
synthetic numerical digital-twin supplementary figures, not experimental data,
not a new Ground Truth revision, and not a full 2D training run.
"""
from __future__ import annotations

import argparse
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

DEFAULT_STIFFNESS_SUMMARY = Path("outputs/tables/phase_transition_stiffness_continuation_audit_summary.json")
DEFAULT_STIFFNESS_CASES = Path("outputs/tables/phase_transition_stiffness_continuation_audit_cases.csv")
DEFAULT_PHASE_SUMMARY = Path("outputs/tables/phase_field_inverse_alignment_smoke_summary.json")
DEFAULT_PHASE_CASES = Path("outputs/tables/phase_field_inverse_alignment_smoke_cases.csv")
DEFAULT_QUASI2D_SUMMARY = Path("outputs/tables/gt_quasi_2d_phase_transition_preflight_summary.json")
DEFAULT_RESIDUAL_SUMMARY = Path("outputs/tables/pinn_quasi_2d_residual_preflight_summary.json")
DEFAULT_FIGURE_DIR = Path("outputs/figures")
DEFAULT_MANIFEST = Path("outputs/tables/stiffness_2d_story_figure_manifest.json")
LABEL = "synthetic / supplementary / not experimental"


def _resolve(path: Path | str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _load_json(path: Path | str) -> dict[str, Any]:
    with _resolve(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(path: Path | str) -> list[dict[str, str]]:
    with _resolve(path).open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _add_label(ax: plt.Axes, note: str) -> None:
    ax.text(0.01, -0.22, f"{LABEL}; {note}", transform=ax.transAxes, fontsize=8, va="top")


def _sorted_numeric_items(mapping: dict[str, Any]) -> tuple[list[float], list[float]]:
    items = sorted(((float(k), float(v)) for k, v in mapping.items()), key=lambda item: item[0])
    return [item[0] for item in items], [item[1] for item in items]


def build_figures(
    *,
    stiffness_summary: Path = DEFAULT_STIFFNESS_SUMMARY,
    stiffness_cases: Path = DEFAULT_STIFFNESS_CASES,
    phase_summary: Path = DEFAULT_PHASE_SUMMARY,
    phase_cases: Path = DEFAULT_PHASE_CASES,
    quasi2d_summary: Path = DEFAULT_QUASI2D_SUMMARY,
    residual_summary: Path = DEFAULT_RESIDUAL_SUMMARY,
    figure_dir: Path = DEFAULT_FIGURE_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    stiff = _load_json(stiffness_summary)
    phase = _load_json(phase_summary)
    quasi = _load_json(quasi2d_summary)
    residual = _load_json(residual_summary)
    phase_rows = _load_csv(phase_cases)
    _ = _load_csv(stiffness_cases)  # load to ensure source exists and is parseable

    fig_dir = _resolve(figure_dir)
    manifest_file = _resolve(manifest_path)
    fig_paths = {
        "stiffness_residual_vs_transition_width": fig_dir / "stiffness_residual_vs_transition_width.png",
        "stiffness_continuation_gain_vs_width": fig_dir / "stiffness_continuation_gain_vs_width.png",
        "stiffness_fourier_gain_caution": fig_dir / "stiffness_fourier_gain_caution.png",
        "phase_field_m_true_vs_estimated": fig_dir / "phase_field_m_true_vs_estimated.png",
        "phase_field_noise_sensitivity": fig_dir / "phase_field_noise_sensitivity.png",
    }

    widths, residuals = _sorted_numeric_items(stiff["residual_median_by_width"])
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(widths, residuals, marker="o", color="#1f77b4")
    ax.set_yscale("log")
    ax.set_xlabel("transition width (K proxy)")
    ax.set_ylabel("median residual proxy (log scale)")
    ax.set_title("Phase-transition residual stiffness cliff")
    ax.grid(True, alpha=0.25)
    _add_label(ax, "narrow width increases residual stress; not full STL")
    _save(fig, fig_paths["stiffness_residual_vs_transition_width"])

    widths_gain, cont_gain = _sorted_numeric_items(stiff["continuation_gain_by_width"])
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(widths_gain, cont_gain, marker="s", color="#2ca02c")
    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--")
    ax.set_xlabel("transition width (K proxy)")
    ax.set_ylabel("direct / continuation residual proxy")
    ax.set_title("Continuation is a stability aid")
    ax.grid(True, alpha=0.25)
    _add_label(ax, "gain > 1 means continuation lower residual; not a full STL reproduction")
    _save(fig, fig_paths["stiffness_continuation_gain_vs_width"])

    widths_fourier, fourier_gain = _sorted_numeric_items(stiff["fourier_feature_gain_by_width"])
    colors = ["#d62728" if value < 1.0 else "#9467bd" for value in fourier_gain]
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.bar([str(w) for w in widths_fourier], fourier_gain, color=colors)
    ax.axhline(1.0, color="black", linewidth=1.0, linestyle="--")
    ax.set_xlabel("transition width (K proxy)")
    ax.set_ylabel("vanilla / Fourier residual proxy")
    ax.set_title("Fourier feature gain is not uniform")
    ax.grid(True, axis="y", alpha=0.25)
    _add_label(ax, "not a Fourier or F-SPS superiority claim")
    _save(fig, fig_paths["stiffness_fourier_gain_caution"])

    m_true = np.asarray([float(row["M_true"]) for row in phase_rows], dtype=float)
    m_est = np.asarray([float(row["M_estimated"]) for row in phase_rows], dtype=float)
    noise = np.asarray([float(row["noise_level"]) for row in phase_rows], dtype=float)
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    sc = ax.scatter(m_true, m_est, c=noise, cmap="viridis", edgecolor="black", linewidth=0.3)
    lo = float(min(np.min(m_true), np.min(m_est)))
    hi = float(max(np.max(m_true), np.max(m_est)))
    ax.plot([lo, hi], [lo, hi], color="black", linestyle="--", linewidth=1.0)
    ax.set_xlabel("true mobility M")
    ax.set_ylabel("estimated mobility M")
    ax.set_title("Phase-field mobility inversion smoke")
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("noise level")
    ax.grid(True, alpha=0.25)
    _add_label(ax, "full-field-anchor smoke; not sparse-port inversion")
    _save(fig, fig_paths["phase_field_m_true_vs_estimated"])

    noise_x, noise_y = _sorted_numeric_items(phase["noise_sensitivity"])
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(noise_x, noise_y, marker="o", color="#ff7f0e")
    ax.axhline(0.1, color="black", linewidth=1.0, linestyle="--", label="0.1 threshold")
    ax.set_xlabel("noise level")
    ax.set_ylabel("median relative error of M")
    ax.set_title("Phase-field smoke noise sensitivity")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.25)
    _add_label(ax, "supplementary related-work alignment only")
    _save(fig, fig_paths["phase_field_noise_sensitivity"])

    figure_entries = [
        {
            "name": name,
            "path": _display(path),
            "source_tables": [_display(_resolve(stiffness_summary)), _display(_resolve(stiffness_cases))] if name.startswith("stiffness") else [_display(_resolve(phase_summary)), _display(_resolve(phase_cases))],
            "label": LABEL,
        }
        for name, path in fig_paths.items()
    ]
    manifest = {
        "benchmark": "stiffness and 2D supplementary story figures",
        "note": "All figures are synthetic numerical digital-twin supplementary evidence, not experimental data.",
        "figures": figure_entries,
        "quasi_2d_existing_figure_references": [str(item).replace("\\", "/") for item in quasi.get("outputs", {}).get("figures", [])],
        "quasi_2d_summary": _display(_resolve(quasi2d_summary)),
        "quasi_2d_residual_summary": _display(_resolve(residual_summary)),
        "stiffness_key_results": {
            "num_cases": stiff["num_cases"],
            "all_finite_results": stiff["all_finite_results"],
            "stiffness_cliff_ratio_sharpest_to_widest": stiff["stiffness_cliff_ratio_sharpest_to_widest"],
            "whether_stiffness_cliff_claim_supported": stiff["whether_stiffness_cliff_claim_supported"],
            "fourier_gain_not_uniform": any(float(v) < 1.0 for v in stiff["fourier_feature_gain_by_width"].values()),
        },
        "phase_field_key_results": {
            "num_cases": phase["num_cases"],
            "all_finite_results": phase["all_finite_results"],
            "median_relative_error_M": phase["median_relative_error_M"],
            "success_rate_le_0p1": phase["success_rate_le_0p1"],
            "full_field_anchor_not_sparse_port": True,
        },
        "quasi_2d_key_results": {
            "num_cases": quasi.get("num_cases"),
            "all_fields_finite": quasi.get("all_fields_finite"),
            "all_observables_finite": quasi.get("all_observables_finite"),
            "all_residuals_finite": residual.get("all_residuals_finite"),
            "whether_2d_inverse_claim_allowed": residual.get("whether_2d_inverse_claim_allowed"),
        },
        "forbidden_claims": [
            "experimental validation",
            "F-SPS or Fourier superiority",
            "continuation fully solves stiffness cliff",
            "2D inverse diagnosis is solved",
            "phase-field smoke is sparse-port inversion",
        ],
        "outputs": {"manifest_json": _display(manifest_file)},
    }
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = build_figures(figure_dir=args.figure_dir, manifest_path=args.manifest)
    print(json.dumps({"manifest": manifest["outputs"]["manifest_json"], "num_figures": len(manifest["figures"]), "note": manifest["note"]}, indent=2))


if __name__ == "__main__":
    main()

"""Fit normalized external literature curves with lightweight closures."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG = Path("configs/literature_curve_fit_external_anchor_v2.yaml")
CASE_FIELDS = ["source_id", "curve_type", "num_points", "fit_model", "normalized_rmse", "fitted_parameters", "finite_result", "limitation"]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _fit_logistic(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    best = None
    increasing = y[-1] >= y[0]
    for tc in np.linspace(0.05, 0.95, 37):
        for width in np.linspace(0.02, 0.35, 34):
            z = 1.0 / (1.0 + np.exp(-(x - tc) / width))
            pred = z if increasing else 1.0 - z
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            if best is None or rmse < best[0]:
                best = (rmse, tc, width, 1.0)
    assert best is not None
    return {"fit_model": "logistic_transition_closure", "normalized_rmse": best[0], "fitted_parameters": {"T_c_norm": best[1], "width_norm": best[2], "contrast_norm": best[3]}}


def _fit_iv(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    dy = np.gradient(y, x + 1.0e-12)
    pos = float(x[int(np.argmax(dy))])
    neg = float(x[int(np.argmin(dy))])
    area = float(abs(np.trapz(y, x)))
    pred = np.interp(x, [float(np.min(x)), neg, pos, float(np.max(x))], [float(y[0]), float(np.min(y)), float(np.max(y)), float(y[-1])])
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    return {"fit_model": "threshold_hysteresis_proxy", "normalized_rmse": rmse, "fitted_parameters": {"threshold_pos": pos, "threshold_neg": neg, "loop_area_norm": area}}


def _fit_pulse(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    best = None
    for rate in np.linspace(0.2, 8.0, 80):
        sat = float(np.max(y))
        base = float(y[0])
        pred = base + (sat - base) * (1.0 - np.exp(-rate * (x - float(np.min(x))) / max(float(np.ptp(x)), 1.0e-30)))
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        if best is None or rmse < best[0]:
            best = (rmse, rate, sat)
    assert best is not None
    return {"fit_model": "saturating_exponential_update", "normalized_rmse": best[0], "fitted_parameters": {"update_rate": best[1], "saturation_level": best[2], "asymmetry": 0.0}}


def _fit_curve(curve_type: str, x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    if curve_type in {"R_T", "sigma_T"}:
        return _fit_logistic(x, y)
    if curve_type == "I_V":
        return _fit_iv(x, y)
    if curve_type in {"pulse_conductance", "retention"}:
        return _fit_pulse(x, y)
    raise ValueError(f"Unsupported curve_type: {curve_type}")


def run_curve_fit_v2(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = _load_yaml(_resolve(config_path))
    ingestion = json.loads(_resolve(cfg["ingestion_summary_json"]).read_text(encoding="utf-8"))
    rows = ingestion.get("normalized_rows", [])
    cases: list[dict[str, Any]] = []
    overlays: list[tuple[str, str, np.ndarray, np.ndarray]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((str(row["source_id"]), str(row["curve_type"])), []).append(row)
    for (source_id, curve_type), group in grouped.items():
        x = np.asarray([float(row["x_normalized"]) for row in group], dtype=float)
        y = np.asarray([float(row["y_normalized"]) for row in group], dtype=float)
        order = np.argsort(x)
        x, y = x[order], y[order]
        fit = _fit_curve(curve_type, x, y)
        finite = bool(np.isfinite([fit["normalized_rmse"], *[float(v) for v in fit["fitted_parameters"].values()]]).all())
        cases.append({"source_id": source_id, "curve_type": curve_type, "num_points": int(x.size), **fit, "fitted_parameters": json.dumps(fit["fitted_parameters"], sort_keys=True), "finite_result": finite, "limitation": "normalized external anchor only; not direct gamma_sub validation"})
        overlays.append((source_id, curve_type, x, y))
    best_by_type: dict[str, Any] = {}
    for curve_type in sorted({row["curve_type"] for row in cases}):
        subset = [row for row in cases if row["curve_type"] == curve_type]
        best_by_type[curve_type] = min(subset, key=lambda row: float(row["normalized_rmse"]))
    ranges: dict[str, list[float]] = {}
    for row in cases:
        for key, value in json.loads(row["fitted_parameters"]).items():
            ranges.setdefault(key, []).append(float(value))
    ranges_out = {key: {"min": float(min(vals)), "max": float(max(vals))} for key, vals in ranges.items()}
    rmses = [float(row["normalized_rmse"]) for row in cases]
    summary = {"benchmark": cfg.get("benchmark"), "note": "Literature curves are normalized external anchors for a synthetic numerical digital-twin benchmark; no experimental validation is claimed.", "num_curves_fit": len(cases), "best_fit_by_curve_type": best_by_type, "median_normalized_rmse": None if not rmses else float(np.median(rmses)), "fitted_parameter_ranges": ranges_out, "whether_literature_curves_support_model_plausibility": bool(cases), "limitation": "literature curves are normalized external anchors, not direct validation of gamma_sub inversion" if cases else "blocked: no provenance-backed digitized curves available", "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"], "overlay_png": cfg["overlay_png"]}}
    _write_csv(_resolve(cfg["cases_csv"]), cases, CASE_FIELDS)
    out = _resolve(cfg["summary_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    fig_path = _resolve(cfg["overlay_png"])
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    if overlays:
        for source_id, curve_type, x, y in overlays:
            ax.plot(x, y, marker="o", linewidth=1.0, label=f"{source_id}:{curve_type}")
        ax.legend(fontsize=7)
    else:
        ax.text(0.5, 0.5, "No provenance-backed\ndigitized curves", ha="center", va="center")
    ax.set_xlabel("normalized x")
    ax.set_ylabel("normalized y")
    ax.set_title("External literature curve fit status")
    fig.tight_layout()
    fig.savefig(fig_path, dpi=180)
    plt.close(fig)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_curve_fit_v2(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

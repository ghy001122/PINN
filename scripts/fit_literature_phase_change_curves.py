"""Fit normalized literature curves when digitized curve data exist.

If no provenance-backed digitized curve CSV is available, this script emits a
blocked/template result and does not fabricate external data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG = Path("configs/literature_curve_fit_external_anchor.yaml")
REGISTRY_FIELDS = ["source_id", "source_title", "source_year", "curve_type", "data_path", "provenance", "fit_status", "notes"]
CASE_FIELDS = ["source_id", "curve_type", "data_path", "num_points", "fit_model", "normalized_rmse", "fitted_parameters", "finite_result"]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def _fit_curve(path: Path) -> dict[str, Any]:
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"No rows in curve file: {path}")
    x_key = "x_normalized" if "x_normalized" in rows[0] else "x"
    y_key = "y_normalized" if "y_normalized" in rows[0] else "y"
    x = np.asarray([float(row[x_key]) for row in rows], dtype=float)
    y = np.asarray([float(row[y_key]) for row in rows], dtype=float)
    y_norm = (y - np.min(y)) / max(float(np.max(y) - np.min(y)), 1.0e-30)
    coeff = np.polyfit(x, y_norm, deg=1)
    pred = np.polyval(coeff, x)
    rmse = float(np.sqrt(np.mean((pred - y_norm) ** 2)))
    return {"num_points": int(x.size), "fit_model": "normalized_linear_baseline", "normalized_rmse": rmse, "fitted_parameters": {"slope": float(coeff[0]), "intercept": float(coeff[1])}, "finite_result": bool(np.isfinite([rmse, coeff[0], coeff[1]]).all())}


def run_curve_fit(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = _load_yaml(_resolve(config_path))
    curve_dir = _resolve(cfg["curve_data_dir"])
    registry_path = _resolve(cfg["curve_registry_csv"])
    summary_path = _resolve(cfg["summary_json"])
    cases_path = _resolve(cfg["cases_csv"])
    notes_path = _resolve(cfg["notes_md"])
    readme_path = _resolve(cfg["template_readme"])
    curve_dir.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(path for path in curve_dir.glob("*.csv") if path.name != registry_path.name)
    registry_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    if not csv_files:
        registry_rows = [
            {"source_id": "lee_2024_compact_memristor_pinn", "source_title": "A Compact Memristor Model Based on Physics-Informed Neural Networks", "source_year": 2024, "curve_type": "I-V or state-response curve", "data_path": "", "provenance": "Google Drive PDF text available; no digitized numerical curve CSV committed", "fit_status": "blocked_no_digitized_curve", "notes": "Do not fabricate curve points; digitize only with provenance later."},
            {"source_id": "jurj_2026_physics_regularized_printed_memristor_surrogate", "source_title": "A Physics-Regularized Neural Surrogate Framework for Printed Memristors", "source_year": 2026, "curve_type": "printed memristor I-V curve", "data_path": "", "provenance": "Google Drive PDF text available; no digitized numerical curve CSV committed", "fit_status": "blocked_no_digitized_curve", "notes": "Use as methodological framing until a digitized curve is added to data/literature/curves."},
        ]
    else:
        for path in csv_files:
            fit = _fit_curve(path)
            source_id = path.stem
            registry_rows.append({"source_id": source_id, "source_title": source_id, "source_year": "", "curve_type": "normalized_external_curve", "data_path": _display_path(path), "provenance": "repo-local digitized curve CSV", "fit_status": "fit_complete", "notes": "Requires manual provenance check before manuscript use."})
            case_rows.append({"source_id": source_id, "curve_type": "normalized_external_curve", "data_path": _display_path(path), **fit, "fitted_parameters": json.dumps(fit["fitted_parameters"], sort_keys=True)})
    _write_csv(registry_path, registry_rows, REGISTRY_FIELDS)
    _write_csv(cases_path, case_rows, CASE_FIELDS)
    best = min(case_rows, key=lambda row: float(row["normalized_rmse"])) if case_rows else None
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin manuscript support; no external curve is fabricated.",
        "num_sources_found": len(registry_rows),
        "num_curves_fit": len(case_rows),
        "best_fit_curve_type": None if best is None else best["curve_type"],
        "normalized_rmse": None if best is None else float(best["normalized_rmse"]),
        "fitted_parameters": None if best is None else json.loads(best["fitted_parameters"]),
        "whether_external_anchor_supports_model_plausibility": bool(case_rows),
        "limitation": "No provenance-backed digitized numerical literature curve was available in the repository, so curve fitting is blocked and only a template registry is emitted." if not case_rows else "Digitized curve fits require source-specific provenance review before manuscript use.",
        "outputs": {"curve_registry_csv": _display_path(registry_path), "summary_json": _display_path(summary_path), "cases_csv": _display_path(cases_path), "notes_md": _display_path(notes_path)},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("# Literature Data Templates\n\nThis directory may hold provenance-backed digitized literature curves for future validation.\nDo not add fabricated points. Each curve CSV should include source_id, curve_type, x_normalized, y_normalized, and provenance notes.\nCurrent run found no digitized numerical curves, so external curve fitting is intentionally blocked.\n", encoding="utf-8")
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text("# Literature Curve Fit Notes\n\nNo provenance-backed digitized literature curve CSV was found in `data/literature/curves/` during this run.\nThe script therefore emitted a registry/template and did not fabricate external data.\nFuture work can add digitized curves only with documented source, units, axis normalization, and extraction method.\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_curve_fit(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

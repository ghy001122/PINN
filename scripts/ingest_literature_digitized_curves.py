"""Ingest provenance-backed digitized literature curves.

No points are fabricated. If no valid CSV curves exist, the output is an
explicit blocked report for the synthetic numerical digital-twin manuscript.
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

DEFAULT_CONFIG = Path("configs/literature_curve_ingestion.yaml")
CASE_FIELDS = ["file_path", "source_id", "source_title", "source_year", "material_family", "curve_type", "num_points", "has_provenance", "normalized_generated", "valid_curve", "blocked_reason"]
REGISTRY_FIELDS = ["source_id", "source_title", "source_year", "material_family", "curve_type", "data_path", "num_points", "provenance", "extraction_method", "figure_or_table_id", "notes"]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _display(path: Path) -> str:
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


def _norm(values: list[float]) -> list[float]:
    arr = np.asarray(values, dtype=float)
    lo = float(np.min(arr))
    span = max(float(np.max(arr) - lo), 1.0e-30)
    return ((arr - lo) / span).astype(float).tolist()


def _read_curve(path: Path, cfg: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    missing = [col for col in cfg["required_columns"] if not rows or col not in rows[0]]
    if missing:
        return {"file_path": _display(path), "valid_curve": False, "blocked_reason": "missing_columns:" + ",".join(missing), "num_points": 0, "has_provenance": False, "normalized_generated": False}, []
    allowed = set(cfg.get("allowed_curve_types", []))
    curve_type = str(rows[0]["curve_type"])
    has_prov = bool(str(rows[0].get("provenance", "")).strip())
    valid_type = curve_type in allowed
    try:
        x = [float(row["x_raw"]) for row in rows]
        y = [float(row["y_raw"]) for row in rows]
    except ValueError:
        return {"file_path": _display(path), "valid_curve": False, "blocked_reason": "non_numeric_raw_values", "num_points": len(rows), "has_provenance": has_prov, "normalized_generated": False}, []
    generated = False
    if "x_normalized" not in rows[0] or "y_normalized" not in rows[0] or any(str(row.get("x_normalized", "")).strip() == "" or str(row.get("y_normalized", "")).strip() == "" for row in rows):
        xn = _norm(x)
        yn = _norm(y)
        for row, xv, yv in zip(rows, xn, yn):
            row["x_normalized"] = xv
            row["y_normalized"] = yv
        generated = True
    valid = bool(has_prov and valid_type and len(rows) >= 3)
    reason = "" if valid else "missing_provenance_or_invalid_type_or_too_few_points"
    meta = rows[0]
    case = {"file_path": _display(path), "source_id": meta["source_id"], "source_title": meta["source_title"], "source_year": meta["source_year"], "material_family": meta["material_family"], "curve_type": curve_type, "num_points": len(rows), "has_provenance": has_prov, "normalized_generated": generated, "valid_curve": valid, "blocked_reason": reason}
    return case, rows if valid else []


def run_ingestion(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = _load_yaml(_resolve(config_path))
    curve_dir = _resolve(cfg["curve_data_dir"])
    curve_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(curve_dir.glob("*.csv"))
    cases: list[dict[str, Any]] = []
    registry: list[dict[str, Any]] = []
    valid_points = 0
    curve_types: set[str] = set()
    sources: set[str] = set()
    normalized_rows: list[dict[str, Any]] = []
    for path in files:
        case, rows = _read_curve(path, cfg)
        cases.append(case)
        if rows:
            valid_points += len(rows)
            curve_types.add(str(case["curve_type"]))
            sources.add(str(case["source_id"]))
            first = rows[0]
            registry.append({"source_id": first["source_id"], "source_title": first["source_title"], "source_year": first["source_year"], "material_family": first["material_family"], "curve_type": first["curve_type"], "data_path": _display(path), "num_points": len(rows), "provenance": first["provenance"], "extraction_method": first["extraction_method"], "figure_or_table_id": first["figure_or_table_id"], "notes": first.get("notes", "")})
            normalized_rows.extend({**row, "data_path": _display(path)} for row in rows)
    blocked = "no_provenance_backed_digitized_curve_csv_found" if not registry else ""
    summary = {"benchmark": cfg.get("benchmark"), "note": "Synthetic numerical digital-twin manuscript support; no literature curve data are fabricated.", "num_curve_files_found": len(files), "num_valid_curve_files": len(registry), "num_total_points": valid_points, "curve_types_available": sorted(curve_types), "sources_available": sorted(sources), "blocked_reason_if_any": blocked, "whether_ready_for_external_curve_fit": bool(registry), "normalized_rows": normalized_rows, "outputs": {"registry_csv": cfg["registry_csv"], "summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"], "notes_md": cfg["notes_md"]}}
    _write_csv(_resolve(cfg["cases_csv"]), cases, CASE_FIELDS)
    _write_csv(_resolve(cfg["registry_csv"]), registry, REGISTRY_FIELDS)
    out = _resolve(cfg["summary_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    notes = _resolve(cfg["notes_md"])
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("# Literature Curve Provenance Notes\n\n" + ("No valid provenance-backed digitized curve CSV was found. External curve fitting remains blocked.\n" if blocked else "Valid curves were ingested from provenance-backed CSV files.\n"), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    payload = run_ingestion(args.config)
    payload.pop("normalized_rows", None)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

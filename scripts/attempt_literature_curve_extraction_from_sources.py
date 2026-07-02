"""Attempt targeted discovery of provenance-backed digitized literature curves.

This script never fabricates points. PDF-only candidates are queued for manual
future digitization instead of being used as numerical data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("configs/literature_targeted_curve_extraction_attempt.yaml")
CASE_FIELDS = ["source", "path_or_url", "file_type", "matched_keywords", "status", "reason", "accepted_points", "curve_type"]
QUEUE_FIELDS = ["source", "path_or_url", "reason", "candidate_curve_types", "recommended_action"]
REQUIRED = {"source_id", "source_title", "source_year", "material_family", "curve_type", "x_raw", "y_raw", "x_unit", "y_unit", "provenance", "extraction_method", "figure_or_table_id", "notes"}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _load_yaml(path: Path) -> dict[str, Any]:
    with _resolve(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    out = _resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _matches(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [kw for kw in keywords if kw.lower() in low]


def _inspect_csv(path: Path, keywords: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except UnicodeDecodeError:
        with path.open("r", newline="", encoding="gbk", errors="ignore") as f:
            rows = list(csv.DictReader(f))
    cols = set(rows[0].keys()) if rows else set()
    matched = _matches(path.name + " " + " ".join(cols), keywords)
    if REQUIRED.issubset(cols) and rows:
        return {"source": "local", "path_or_url": _display(path), "file_type": "csv", "matched_keywords": ";".join(matched), "status": "valid_digitized_curve_table", "reason": "required provenance and raw curve columns present", "accepted_points": len(rows), "curve_type": rows[0].get("curve_type", "")}, []
    queue = []
    status = "csv_missing_required_curve_columns" if matched else "not_curve_relevant"
    reason = "CSV lacks required provenance-backed curve schema" if matched else "No curve keyword match"
    if matched:
        queue.append({"source": "local", "path_or_url": _display(path), "reason": reason, "candidate_curve_types": ";".join(matched), "recommended_action": "manually inspect and convert to required curve schema only if numeric provenance exists"})
    return {"source": "local", "path_or_url": _display(path), "file_type": "csv", "matched_keywords": ";".join(matched), "status": status, "reason": reason, "accepted_points": 0, "curve_type": ""}, queue


def _inspect_json(path: Path, keywords: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    matched = _matches(path.name + " " + text[:2000], keywords)
    status = "json_candidate_not_digitized" if matched else "not_curve_relevant"
    queue = []
    if matched:
        queue.append({"source": "local", "path_or_url": _display(path), "reason": "JSON matched curve keywords but was not accepted as required curve table", "candidate_curve_types": ";".join(matched), "recommended_action": "inspect for numerical arrays and convert with provenance if valid"})
    return {"source": "local", "path_or_url": _display(path), "file_type": "json", "matched_keywords": ";".join(matched), "status": status, "reason": "No accepted required curve schema", "accepted_points": 0, "curve_type": ""}, queue


def _inspect_text(path: Path, keywords: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    matched = _matches(path.name + " " + text[:4000], keywords)
    status = "text_candidate_not_digitized" if matched else "not_curve_relevant"
    queue = []
    if matched:
        queue.append({"source": "local", "path_or_url": _display(path), "reason": "Text mentions curve keywords but provides no accepted numeric table", "candidate_curve_types": ";".join(matched), "recommended_action": "manually digitize only from cited figure/table with provenance"})
    return {"source": "local", "path_or_url": _display(path), "file_type": path.suffix.lower().lstrip("."), "matched_keywords": ";".join(matched), "status": status, "reason": "No accepted numeric curve table", "accepted_points": 0, "curve_type": ""}, queue


def run_extraction_attempt(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = _load_yaml(config_path)
    keywords = [str(k) for k in cfg["keywords"]]
    cases: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    accepted = 0
    for root in cfg["search_roots"]:
        base = _resolve(root)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".csv", ".json", ".md", ".txt", ".pdf"}:
                continue
            if path.suffix.lower() == ".csv":
                case, q = _inspect_csv(path, keywords)
            elif path.suffix.lower() == ".json":
                case, q = _inspect_json(path, keywords)
            elif path.suffix.lower() == ".pdf":
                matched = _matches(path.name, keywords)
                case = {"source": "local", "path_or_url": _display(path), "file_type": "pdf", "matched_keywords": ";".join(matched), "status": "candidate_not_digitized" if matched else "not_curve_relevant", "reason": "PDF is not accepted as numerical curve data without digitized table", "accepted_points": 0, "curve_type": ""}
                q = [{"source": "local", "path_or_url": _display(path), "reason": case["reason"], "candidate_curve_types": ";".join(matched), "recommended_action": "manual digitization with documented figure/table provenance"}] if matched else []
            else:
                case, q = _inspect_text(path, keywords)
            cases.append(case)
            queue.extend(q)
            accepted += int(case.get("accepted_points") or 0)
    for item in cfg.get("drive_candidates", []):
        title = str(item.get("title", ""))
        matched = _matches(title, keywords)
        cases.append({"source": "google_drive", "path_or_url": item.get("url", ""), "file_type": item.get("mime_type", ""), "matched_keywords": ";".join(matched), "status": "candidate_not_digitized", "reason": "Drive source is PDF metadata only; no numerical table fetched or accepted", "accepted_points": 0, "curve_type": ""})
        queue.append({"source": "google_drive", "path_or_url": item.get("url", ""), "reason": "PDF candidate requires manual digitization; no numerical table available", "candidate_curve_types": ";".join(matched), "recommended_action": "manual digitization queue; do not fit until CSV exists"})
    _write_csv(cfg["cases_csv"], cases, CASE_FIELDS)
    _write_csv(cfg["manual_queue_csv"], queue, QUEUE_FIELDS)
    protocol = _resolve(cfg["protocol_md"])
    protocol.parent.mkdir(parents=True, exist_ok=True)
    protocol.write_text("""# Manual Digitization Protocol\n\nAll external curve data must be provenance-backed. Do not fabricate points.\n\n1. Record source title, year, DOI or URL, figure/table id, axes units, and extraction method.\n2. Digitize only if the axis scale and curve identity are unambiguous.\n3. Save CSV files under `data/literature/curves/` using the schema required by `configs/literature_curve_ingestion.yaml`.\n4. Re-run `scripts/ingest_literature_digitized_curves.py` and `scripts/fit_literature_phase_change_curves_v2.py`.\n5. If no numeric provenance exists, keep the item in `data/literature/manual_digitization_queue.csv` and write only a blocked/no-fabrication limitation.\n""", encoding="utf-8")
    status_counts: dict[str, int] = {}
    for c in cases:
        status_counts[str(c["status"])] = status_counts.get(str(c["status"]), 0) + 1
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Targeted external curve extraction attempt; no points are fabricated and PDF-only candidates are queued.",
        "num_sources_scanned": len(cases),
        "num_valid_digitized_curve_tables": sum(1 for c in cases if c["status"] == "valid_digitized_curve_table"),
        "num_accepted_points": accepted,
        "num_manual_digitization_queue_items": len(queue),
        "status_counts": status_counts,
        "whether_ready_for_literature_curve_ingestion_rerun": bool(accepted > 0),
        "blocked_reason_if_any": "no_provenance_backed_digitized_curve_tables_found" if accepted == 0 else "",
        "outputs": {"summary_json": cfg["summary_json"], "cases_csv": cfg["cases_csv"], "manual_queue_csv": cfg["manual_queue_csv"], "protocol_md": cfg["protocol_md"]},
    }
    out = _resolve(cfg["summary_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_extraction_attempt(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

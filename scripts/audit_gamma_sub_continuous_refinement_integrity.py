"""Audit committed gamma_sub summary/case consistency without new simulation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from pinnpcm.audit.evidence_identity import canonical_lf_bytes, sha256_bytes


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = Path("outputs/tables/gamma_sub_continuous_refinement_summary.json")
CASES = Path("outputs/tables/gamma_sub_continuous_refinement_cases.csv")
NUMERIC_FIELDS = {
    "true_gamma_sub",
    "n_obs",
    "noise_level",
    "nearest_grid_gamma_sub",
    "nearest_grid_relative_error",
    "nearest_grid_objective_value",
    "continuous_refined_gamma_sub",
    "continuous_refined_relative_error",
    "continuous_refined_objective_value",
    "continuous_refined_G_loss",
    "continuous_refined_I_loss",
    "continuous_eval_count",
    "continuous_bracket_low",
    "continuous_bracket_high",
    "error_reduction",
}
BOOLEAN_FIELDS = {
    "refinement_resimulated_non_grid",
    "success_flag",
    "optimizer_success",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _close(left: Any, right: Any) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1.0e-12, abs_tol=1.0e-15)


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if str(value) == "True":
        return True
    if str(value) == "False":
        return False
    raise ValueError(value)


def _display_path(path: Path, root: Path) -> str:
    try:
        value = path.relative_to(root)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


def _group_check(
    rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    key: str,
) -> list[str]:
    failures: list[str] = []
    indexed = {float(record[key]): record for record in records}
    for coordinate in sorted({float(row[key]) for row in rows}):
        subset = [row for row in rows if _close(row[key], coordinate)]
        record = indexed.get(coordinate)
        if record is None:
            failures.append(f"missing_group:{key}:{coordinate}")
            continue
        expected = {
            "all_success": all(_boolean(row["success_flag"]) for row in subset),
            "max_continuous_refined_relative_error": max(
                float(row["continuous_refined_relative_error"]) for row in subset
            ),
            "max_nearest_grid_relative_error": max(
                float(row["nearest_grid_relative_error"]) for row in subset
            ),
            "mean_error_reduction": mean(float(row["error_reduction"]) for row in subset),
        }
        if bool(record["all_success"]) != expected["all_success"]:
            failures.append(f"group_all_success:{key}:{coordinate}")
        for field in (
            "max_continuous_refined_relative_error",
            "max_nearest_grid_relative_error",
            "mean_error_reduction",
        ):
            if not _close(record[field], expected[field]):
                failures.append(f"group_metric:{key}:{coordinate}:{field}")
    return failures


def audit(
    *,
    root: Path = ROOT,
    summary_path: Path = SUMMARY,
    cases_path: Path = CASES,
) -> dict[str, Any]:
    root = root.resolve()
    summary_path = summary_path if summary_path.is_absolute() else root / summary_path
    cases_path = cases_path if cases_path.is_absolute() else root / cases_path
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    with cases_path.open("r", encoding="utf-8-sig", newline="") as handle:
        cases = list(csv.DictReader(handle))
    summary_rows = summary.get("rows", [])
    failures: list[str] = []
    if len(cases) != len(summary_rows) or len(cases) != int(summary.get("num_cases", -1)):
        failures.append("row_count")
    for index, (case, row) in enumerate(zip(cases, summary_rows)):
        for field in NUMERIC_FIELDS:
            if field not in case or field not in row or not _close(case[field], row[field]):
                failures.append(f"row_numeric:{index}:{field}")
        for field in BOOLEAN_FIELDS:
            try:
                equal = _boolean(case[field]) == _boolean(row[field])
            except (KeyError, ValueError):
                equal = False
            if not equal:
                failures.append(f"row_boolean:{index}:{field}")

    if cases:
        aggregate = {
            "max_continuous_refined_relative_error": max(
                float(row["continuous_refined_relative_error"]) for row in cases
            ),
            "max_nearest_grid_relative_error": max(
                float(row["nearest_grid_relative_error"]) for row in cases
            ),
            "mean_error_reduction": mean(float(row["error_reduction"]) for row in cases),
        }
        for field, expected in aggregate.items():
            if not _close(summary.get(field), expected):
                failures.append(f"aggregate:{field}")
        if bool(summary.get("all_success")) != all(
            _boolean(row["success_flag"]) for row in cases
        ):
            failures.append("aggregate:all_success")

    failures.extend(_group_check(cases, summary.get("by_noise_level", []), "noise_level"))
    failures.extend(
        _group_check(cases, summary.get("by_observation_count", []), "n_obs")
    )
    if summary.get("frozen_gt_hashes_before") != summary.get("frozen_gt_hashes_after"):
        failures.append("frozen_gt_hash_pair")
    if summary.get("frozen_gt_unchanged") is not True:
        failures.append("frozen_gt_flag")
    return {
        "schema_version": "gamma_sub_continuous_refinement_integrity_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary_path": _display_path(summary_path, root),
        "summary_sha256": _sha256(summary_path),
        "summary_canonical_lf_sha256": sha256_bytes(
            canonical_lf_bytes(summary_path.read_bytes())
        ),
        "cases_path": _display_path(cases_path, root),
        "cases_sha256": _sha256(cases_path),
        "row_count": len(cases),
        "scientific_forward_runs": 0,
        "figure_regenerated": False,
        "all_passed": not failures,
        "failures": sorted(set(failures)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/tables/gamma_sub_continuous_refinement_integrity_audit.json"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    result = audit(root=root, summary_path=args.summary, cases_path=args.cases)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"all_passed": result["all_passed"], "row_count": result["row_count"]}))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

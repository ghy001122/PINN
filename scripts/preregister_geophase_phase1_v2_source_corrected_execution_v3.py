from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from io import StringIO
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ADDENDUM_PATH = (
    ROOT
    / "configs"
    / "geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml"
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain one mapping")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _relative(path_text: str) -> Path:
    path = ROOT / path_text
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _validate_authority_hashes(addendum: dict[str, Any]) -> dict[str, str]:
    authority = addendum["authority_lock"]
    keys = (
        "S2_config",
        "formal_manifest_contract",
        "expanded_manifest_csv",
        "expanded_manifest_json",
        "source_corrected_contract",
    )
    hashes: dict[str, str] = {}
    for key in keys:
        record = authority[key]
        path = _relative(record["path"])
        observed = _sha256(path)
        if observed != record["sha256"]:
            raise RuntimeError(f"authority hash mismatch for {record['path']}")
        hashes[record["path"]] = observed
    return hashes


def _manifest_rows(addendum: dict[str, Any]) -> list[dict[str, str]]:
    manifest_path = _relative(
        addendum["authority_lock"]["expanded_manifest_csv"]["path"]
    )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 63:
        raise RuntimeError("the execution addendum requires exactly 63 manifest rows")
    identifiers = [row["evaluation_id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError("formal evaluation identifiers are not unique")
    if any(row["status"] != "planned_not_executed" for row in rows):
        raise RuntimeError("a formal evaluation row is no longer planned_not_executed")
    return rows


def build_execution_dag(addendum: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if addendum["authority_lock"]["formal_execution_count"] != 0:
        raise RuntimeError("readiness preregistration requires formal count zero")
    if addendum["authority_lock"]["formal_campaign_authorized"] is not False:
        raise RuntimeError("readiness preregistration cannot authorize formal execution")

    authority_hashes = _validate_authority_hashes(addendum)
    rows = _manifest_rows(addendum)
    stage_by_group = {
        "FAIL": (2, "FAIL_fail_closed_controls"),
        "MMS": (3, "MMS_manufactured_foundations"),
        "LIM": (4, "LIM_analytic_and_zero_input_foundations"),
        "REF": (5, "REF_independent_refinement_trajectories"),
        "DUAL0": (6, "DUAL0_zero_coupling_limits"),
        "TOP": (7, "TOP_unique_overlap_trajectories_then_reused_evaluations"),
    }
    by_evaluation = {row["evaluation_id"]: row for row in rows}
    configured_reuses = {
        item["evaluation_id"]: item["dependency_id"]
        for item in addendum["execution_dependency_graph"]["reuse_rows"]
    }
    actual_reuses = {
        row["evaluation_id"]: row["dependency_ids"]
        for row in rows
        if row["dependency_ids"]
    }
    if actual_reuses != configured_reuses:
        raise RuntimeError("the three configured trajectory reuses do not match the manifest")

    csv_rows: list[dict[str, Any]] = []
    unit_consumers: dict[str, list[str]] = {}
    unit_primary: dict[str, str] = {}
    unit_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        evaluation_id = row["evaluation_id"]
        group = row["evaluation_group"]
        evaluation_stage, evaluation_stage_id = stage_by_group[group]
        dependency_id = row["dependency_ids"]
        reused = bool(dependency_id)
        if reused:
            dependency = by_evaluation.get(dependency_id)
            if dependency is None:
                raise RuntimeError(f"missing dependency {dependency_id}")
            if row["trajectory_id"] != dependency["trajectory_id"]:
                raise RuntimeError("a reused evaluation changed trajectory identity")
            execution_unit_id = dependency["trajectory_id"]
            unit_source = dependency
        else:
            execution_unit_id = row["trajectory_id"]
            unit_source = row
            if execution_unit_id in unit_primary:
                raise RuntimeError(f"undeclared execution-unit reuse: {execution_unit_id}")
            unit_primary[execution_unit_id] = evaluation_id
            unit_rows[execution_unit_id] = row
        unit_consumers.setdefault(execution_unit_id, []).append(evaluation_id)
        unit_stage, unit_stage_id = stage_by_group[unit_source["evaluation_group"]]
        csv_rows.append(
            {
                "evaluation_id": evaluation_id,
                "evaluation_group": group,
                "evaluation_status": row["status"],
                "execution_unit_id": execution_unit_id,
                "primary_evaluation_id": unit_source["evaluation_id"],
                "is_reused_evaluation": str(reused).lower(),
                "reuse_dependency_id": dependency_id,
                "evaluation_stage": evaluation_stage,
                "evaluation_stage_id": evaluation_stage_id,
                "execution_unit_stage": unit_stage,
                "execution_unit_stage_id": unit_stage_id,
                "protocol_id": row["protocol_id"],
                "fixture_id": row["fixture_id"],
                "spatial_level": row["spatial_level"],
                "time_divisor": row["time_divisor"],
                "contact_overlap_m": row["contact_overlap_m"],
            }
        )

    expected_units = addendum["execution_dependency_graph"][
        "unique_execution_unit_count"
    ]
    if len(unit_primary) != expected_units:
        raise RuntimeError(f"expected {expected_units} unique execution units")
    reused_rows = [row for row in csv_rows if row["is_reused_evaluation"] == "true"]
    if len(reused_rows) != 3:
        raise RuntimeError("expected exactly three reused evaluations")

    execution_units = []
    for unit_id, primary_id in unit_primary.items():
        row = unit_rows[unit_id]
        stage, stage_id = stage_by_group[row["evaluation_group"]]
        execution_units.append(
            {
                "execution_unit_id": unit_id,
                "primary_evaluation_id": primary_id,
                "consumer_evaluation_ids": unit_consumers[unit_id],
                "execution_group": row["evaluation_group"],
                "execution_stage": stage,
                "execution_stage_id": stage_id,
                "protocol_id": row["protocol_id"] or None,
                "fixture_id": row["fixture_id"] or None,
                "spatial_level": int(row["spatial_level"])
                if row["spatial_level"]
                else None,
                "time_divisor": int(row["time_divisor"])
                if row["time_divisor"]
                else None,
            }
        )
    execution_units.sort(
        key=lambda item: (
            item["execution_stage"],
            rows.index(by_evaluation[item["primary_evaluation_id"]]),
        )
    )

    summary = {
        "task_id": addendum["task_id"],
        "schema_version": "geophase_phase1_v2_execution_dag_source_corrected_v3",
        "status": "config_only_preregistered_not_executed",
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_artifacts_created": False,
        "evaluation_item_count": len(rows),
        "unique_execution_unit_count": len(execution_units),
        "reused_evaluation_count": len(reused_rows),
        "authority_hashes_sha256": authority_hashes,
        "addendum_sha256": _sha256(ADDENDUM_PATH),
        "execution_units": execution_units,
        "reuse_map": configured_reuses,
    }
    return summary, csv_rows


def _csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("execution DAG table cannot be empty")
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the config-only source-corrected Phase 1-v2 v3 60-to-63 execution DAG."
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    addendum = _load_yaml(ADDENDUM_PATH)
    summary, rows = build_execution_dag(addendum)
    csv_text = _csv_text(rows)
    json_text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    csv_path = ROOT / addendum["outputs"]["execution_dag_csv"]
    json_path = ROOT / addendum["outputs"]["execution_dag_json"]
    if args.check:
        if csv_path.read_text(encoding="utf-8") != csv_text:
            raise SystemExit("execution DAG CSV is stale")
        if json_path.read_text(encoding="utf-8") != json_text:
            raise SystemExit("execution DAG JSON is stale")
        return
    _atomic_text(csv_path, csv_text)
    _atomic_text(json_path, json_text)


if __name__ == "__main__":
    main()

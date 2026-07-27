from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from itertools import product
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
MANIFEST_CONTRACT_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_formal_manifest.yaml"
)
S1_PATH = ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve.yaml"
AUDIT_PATH = ROOT / "configs" / "qiu_same_device_thermal_holdout_audit.yaml"
SOURCE_PATH = ROOT / "configs" / "qiu_vo2_phase1_source_contract.yaml"
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
CSV_PATH = OUTPUT_DIR / "formal_evaluation_manifest.csv"
MANIFEST_JSON_PATH = OUTPUT_DIR / "formal_evaluation_manifest.json"
PREREGISTRATION_PATH = OUTPUT_DIR / "preregistration.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{path} must contain a mapping")
    return loaded


def _blank_row(columns: list[str]) -> dict[str, str]:
    return {column: "" for column in columns}


def _append_row(
    rows: list[dict[str, str]],
    columns: list[str],
    *,
    evaluation_id: str,
    group: str,
    group_index: int,
    execution_class: str,
    trajectory_id: str,
    dependency_ids: str = "",
    problem_id: str = "",
    protocol_id: str = "",
    audit_id: str = "",
    fixture_id: str = "",
    spatial_level: str = "",
    time_divisor: str = "",
    contact_overlap_m: str = "",
    gate_ids: str = "",
) -> None:
    row = _blank_row(columns)
    row.update(
        {
            "evaluation_id": evaluation_id,
            "evaluation_group": group,
            "group_index": str(group_index),
            "status": "planned_not_executed",
            "evidence_type": "literature_guided_synthetic_numerical_digital_twin",
            "execution_class": execution_class,
            "trajectory_id": trajectory_id,
            "dependency_ids": dependency_ids,
            "problem_id": problem_id,
            "protocol_id": protocol_id,
            "audit_id": audit_id,
            "fixture_id": fixture_id,
            "spatial_level": spatial_level,
            "time_divisor": time_divisor,
            "contact_overlap_m": contact_overlap_m,
            "gate_ids": gate_ids,
        }
    )
    rows.append(row)


def _expand_manifest(contract: dict[str, Any]) -> list[dict[str, str]]:
    columns = list(contract["manifest_columns"])
    groups = {group["group_id"]: group for group in contract["groups"]}
    rows: list[dict[str, str]] = []

    mms = groups["MMS"]
    for index, (problem, level) in enumerate(
        product(mms["axes"]["problem"], mms["axes"]["level"]), start=1
    ):
        evaluation_id = f"P1V2-MMS-{problem}-L{level}"
        _append_row(
            rows,
            columns,
            evaluation_id=evaluation_id,
            group="MMS",
            group_index=index,
            execution_class="formal_manufactured_solve",
            trajectory_id=f"TRJ-{evaluation_id}",
            problem_id=problem,
            spatial_level=str(level),
            gate_ids=f"manufactured_{problem}",
        )

    refinement = groups["REF"]
    ref_index = 0
    for protocol in refinement["axes"]["protocol"]:
        for pair in refinement["axes"]["grid_time_combinations"]:
            ref_index += 1
            grid_time_id = pair["grid_time_id"]
            evaluation_id = f"P1V2-REF-{protocol}-{grid_time_id}"
            _append_row(
                rows,
                columns,
                evaluation_id=evaluation_id,
                group="REF",
                group_index=ref_index,
                execution_class="formal_dynamic_trajectory",
                trajectory_id=f"TRJ-{evaluation_id}",
                protocol_id=protocol,
                spatial_level=str(pair["spatial_level"]),
                time_divisor=str(pair["time_divisor"]),
                gate_ids="space_time_event_convergence;ledgers;source_trend",
            )

    topology = groups["TOP"]
    top_index = 0
    for overlap in topology["axes"]["overlap_combinations"]:
        for protocol in topology["axes"]["protocol"]:
            top_index += 1
            overlap_nm = overlap["overlap_nm"]
            evaluation_id = f"P1V2-TOP-O{overlap_nm}-{protocol}"
            dependency = ""
            trajectory_id = f"TRJ-{evaluation_id}"
            execution_class = "formal_dynamic_trajectory"
            if overlap_nm == 20:
                dependency = f"P1V2-REF-{protocol}-S4T4"
                trajectory_id = f"TRJ-{dependency}"
                execution_class = "formal_reused_trajectory_evaluation"
            _append_row(
                rows,
                columns,
                evaluation_id=evaluation_id,
                group="TOP",
                group_index=top_index,
                execution_class=execution_class,
                trajectory_id=trajectory_id,
                dependency_ids=dependency,
                protocol_id=protocol,
                audit_id=f"contact_overlap_{overlap_nm}nm",
                spatial_level="4",
                time_divisor="4",
                contact_overlap_m=f"{float(overlap['contact_overlap_m']):.17g}",
                gate_ids="contact_overlap_qoi_sensitivity;geometry_wording",
            )

    for group_id in ("DUAL0", "FAIL", "LIM"):
        group = groups[group_id]
        for index, case in enumerate(group["axes"]["case"], start=1):
            evaluation_id = f"P1V2-{group_id}-{case}"
            _append_row(
                rows,
                columns,
                evaluation_id=evaluation_id,
                group=group_id,
                group_index=index,
                execution_class="formal_fixture",
                trajectory_id=f"TRJ-{evaluation_id}",
                fixture_id=case,
                gate_ids=f"{group_id.lower()}_{case}",
            )

    expected = int(contract["total_evaluation_items"])
    if len(rows) != expected:
        raise ValueError(f"expanded {len(rows)} rows, expected {expected}")
    identifiers = [row["evaluation_id"] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate Phase 1-v2 evaluation IDs")
    if any(not identifier.startswith("P1V2-") for identifier in identifiers):
        raise ValueError("all Phase 1-v2 IDs must use the P1V2 prefix")
    return rows


def _csv_text(rows: list[dict[str, str]], columns: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def build_payloads(base_sha: str) -> tuple[str, str, str]:
    if len(base_sha) != 40 or any(character not in "0123456789abcdef" for character in base_sha):
        raise ValueError("--base-sha must be a lowercase 40-character Git SHA")

    config = _load_yaml(CONFIG_PATH)
    contract = _load_yaml(MANIFEST_CONTRACT_PATH)
    rows = _expand_manifest(contract)
    columns = list(contract["manifest_columns"])
    csv_text = _csv_text(rows, columns)
    csv_sha = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()

    reused = [row for row in rows if row["dependency_ids"]]
    unique_trajectories = {row["trajectory_id"] for row in rows}
    manifest_metadata = {
        "config_sha256": _sha256(CONFIG_PATH),
        "evaluation_item_count": len(rows),
        "formal_execution_count": 0,
        "manifest_contract_sha256": _sha256(MANIFEST_CONTRACT_PATH),
        "manifest_csv_sha256": csv_sha,
        "old_v6_96_item_manifest_reused": False,
        "reused_evaluation_item_count": len(reused),
        "reuse_map": {
            row["evaluation_id"]: row["dependency_ids"] for row in reused
        },
        "schema_version": "geophase_phase1_v2_formal_manifest_metadata_v1",
        "status": "preregistered_not_executed",
        "task_id": config["task_id"],
        "unique_execution_unit_count": len(unique_trajectories),
    }
    manifest_json_text = _json_text(manifest_metadata)

    preregistration = {
        "base_commit": base_sha,
        "bounded_holdout_audit_sha256": _sha256(AUDIT_PATH),
        "config_sha256": _sha256(CONFIG_PATH),
        "evaluation_item_count": len(rows),
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "manifest_contract_sha256": _sha256(MANIFEST_CONTRACT_PATH),
        "manifest_csv_sha256": csv_sha,
        "manifest_metadata_sha256": hashlib.sha256(
            manifest_json_text.encode("utf-8")
        ).hexdigest(),
        "new_numerical_work_before_preregistration_push": False,
        "old_96_item_campaign_status": "permanently_planned_not_executed",
        "schema_version": "geophase_phase1_v2_preregistration_v1",
        "source_contract_sha256": _sha256(SOURCE_PATH),
        "s1_mve_contract_sha256": _sha256(S1_PATH),
        "status": "preregistered_not_executed",
        "task_id": config["task_id"],
    }
    return csv_text, manifest_json_text, _json_text(preregistration)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build deterministic config-only Phase 1-v2 preregistration artifacts."
    )
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    csv_text, manifest_json_text, preregistration_text = build_payloads(args.base_sha)
    expected = {
        CSV_PATH: csv_text,
        MANIFEST_JSON_PATH: manifest_json_text,
        PREREGISTRATION_PATH: preregistration_text,
    }
    if args.check:
        mismatches = [
            str(path.relative_to(ROOT))
            for path, content in expected.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if mismatches:
            raise SystemExit("preregistration artifacts differ: " + ", ".join(mismatches))
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

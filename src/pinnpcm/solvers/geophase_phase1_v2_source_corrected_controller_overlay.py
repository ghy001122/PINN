"""Closed source-corrected v3 transform of the immutable controller-v2 overlay.

This module performs no numerical solve.  It proves that the active v3 overlay
differs from the historical controller-v2 contract only in versioned authority,
the corrected 15.8 V protocol scale, and the isolated output namespace.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from pinnpcm.solvers.geophase_phase1_v2_controller_overlay import (
    ResolvedControllerV2,
    sha256_path,
    validate_controller_overlay_document,
)


RESOLUTION_SCHEMA_VERSION = (
    "geophase_phase1_v2_source_corrected_controller_overlay_resolution_v3"
)
OLD_BASE_SHA256 = "0600498590a8c100ec8dee95621719ea655354ec118015868cb07fedf89f85d5"
OLD_OVERLAY_SHA256 = "eaca81d59b9a52c21fe60fab213a8f7fd65d83a674fd2ef27746d164e163c528"
SOURCE_CORRECTION_BASE_COMMIT = "5dcd23f8ad1c47a01105d62c526d12dc886c8568"
SOURCE_CORRECTION_BASE_TREE = "7a06d2b38d5203c580dffa0b13174729db591ae7"

IDENTITY_FIELD_RECORDS = (
    ("base_S2_config_sha256", ("base_S2_config", "sha256")),
    ("source_contract_sha256", ("source_contract", "sha256")),
    ("formal_manifest_sha256", ("formal_manifest", "sha256")),
    (
        "expanded_manifest_CSV_sha256",
        ("formal_manifest", "expanded_CSV", "sha256"),
    ),
    (
        "expanded_manifest_JSON_sha256",
        ("formal_manifest", "expanded_JSON", "sha256"),
    ),
    ("execution_addendum_sha256", ("execution_addendum", "sha256")),
    ("execution_DAG_CSV_sha256", ("execution_DAG", "CSV_sha256")),
    ("execution_DAG_JSON_sha256", ("execution_DAG", "sha256")),
)


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a mapping")
    return value


def _nested(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"missing authority identity field {'.'.join(keys)}")
        value = value[key]
    return value


def _expected_v3_overlay(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Return the only permitted deterministic old-to-v3 overlay transform."""

    expected = copy.deepcopy(old)
    expected["task_id"] = "Q2_PHASE1_V2_SOURCE_CORRECTED_EMBEDDED_TIME_CONTROLLER_V2"
    expected["schema_version"] = (
        "geophase_phase1_v2_embedded_time_controller_overlay_source_corrected_v3"
    )
    expected["status"] = (
        "preregistered_source_corrected_pending_push_no_runtime_preflight_executed"
    )
    expected["evidence_type"] = (
        "versioned_source_corrected_numerical_time_controller_contract"
    )

    authority = expected["authority_lock"]
    authority.pop("merged_pr7_main_commit")
    authority.pop("merged_pr7_main_tree")
    authority["source_correction_base_main_commit"] = SOURCE_CORRECTION_BASE_COMMIT
    authority["source_correction_base_main_tree"] = SOURCE_CORRECTION_BASE_TREE
    for key in ("base_S2_config", "source_contract", "formal_manifest", "execution_DAG"):
        authority[key] = copy.deepcopy(new["authority_lock"][key])
    authority["execution_addendum"] = copy.deepcopy(
        new["authority_lock"]["execution_addendum"]
    )

    boundary = expected["execution_boundary"]
    boundary.pop("preregistration_commit_must_be_pushed_before_controller_implementation")
    boundary["preregistration_commit_must_be_pushed_before_source_corrected_runtime_routing"] = True
    boundary["source_correction_diff_contract"] = copy.deepcopy(
        new["execution_boundary"]["source_correction_diff_contract"]
    )
    boundary.pop("implementation_diff_contract")

    resolution = expected["deterministic_resolution"]
    resolution["schema_version"] = RESOLUTION_SCHEMA_VERSION
    resolution["resolved_runtime_identity_fields"] = [
        name for name, _ in IDENTITY_FIELD_RECORDS
    ] + ["controller_v2_overlay_sha256", "resolution_schema_version"]
    resolution["resolved_runtime_identity_formula"] = (
        "sha256_of_canonical_JSON_of_the_ten_identity_fields"
    )

    scale = expected["controller_overlay"]["reference_solver"][
        "active_time_controller"
    ]["voltage_scale"]["protocol_V_scale_V"]
    if scale.pop("high_bias_15V") != 15.0:
        raise ValueError("historical controller no longer contains the 15.0 V scale")
    scale["high_bias_lock_15p8V"] = 15.8
    expected["outputs"] = copy.deepcopy(new["outputs"])
    return expected


def _validate_authority_files(root: Path, overlay: dict[str, Any]) -> None:
    authority = overlay["authority_lock"]
    records = [
        authority["base_S2_config"],
        authority["source_contract"],
        authority["execution_addendum"],
        authority["formal_manifest"],
        authority["formal_manifest"]["expanded_CSV"],
        authority["formal_manifest"]["expanded_JSON"],
        authority["execution_DAG"],
        {
            "path": authority["execution_DAG"]["CSV_path"],
            "sha256": authority["execution_DAG"]["CSV_sha256"],
        },
    ]
    for record in records:
        path = root / str(record["path"])
        if sha256_path(path) != str(record["sha256"]):
            raise ValueError(f"source-corrected authority hash mismatch: {record['path']}")


def validate_source_corrected_overlay_document(
    overlay: dict[str, Any],
    base_config: dict[str, Any],
    *,
    root: Path,
) -> None:
    old_base_path = root / "configs" / "geophase_phase1_v2_s2_reference.yaml"
    old_overlay_path = (
        root / "configs" / "geophase_phase1_v2_embedded_time_controller_v2.yaml"
    )
    if sha256_path(old_base_path) != OLD_BASE_SHA256:
        raise ValueError("historical S2 base bytes changed")
    if sha256_path(old_overlay_path) != OLD_OVERLAY_SHA256:
        raise ValueError("historical controller-v2 overlay bytes changed")
    old_base = _load_yaml(old_base_path)
    old_overlay = _load_yaml(old_overlay_path)
    validate_controller_overlay_document(old_overlay, old_base)

    if overlay != _expected_v3_overlay(old_overlay, overlay):
        raise ValueError("source-corrected overlay contains an undeclared semantic change")
    authority = overlay["authority_lock"]
    if authority["source_correction_base_main_commit"] != SOURCE_CORRECTION_BASE_COMMIT:
        raise ValueError("source-correction base commit changed")
    if authority["source_correction_base_main_tree"] != SOURCE_CORRECTION_BASE_TREE:
        raise ValueError("source-correction base tree changed")
    if authority["formal_manifest"]["evaluation_item_count"] != 63:
        raise ValueError("formal evaluation count changed")
    if authority["formal_manifest"]["unique_execution_unit_count"] != 60:
        raise ValueError("formal execution-unit count changed")
    if authority["formal_manifest"]["legal_reuse_count"] != 3:
        raise ValueError("formal reuse count changed")
    if base_config.get("schema_version") != (
        "geophase_phase1_v2_s2_reference_source_corrected_v3"
    ):
        raise ValueError("unexpected source-corrected S2 schema")
    _validate_authority_files(root, overlay)


def resolve_controller_v2(base_path: Path, overlay_path: Path) -> ResolvedControllerV2:
    root = base_path.resolve().parent.parent
    base = _load_yaml(base_path)
    overlay = _load_yaml(overlay_path)
    validate_source_corrected_overlay_document(overlay, base, root=root)

    locked_base = overlay["authority_lock"]["base_S2_config"]
    base_hash = sha256_path(base_path)
    if base_hash != str(locked_base["sha256"]):
        raise ValueError("source-corrected S2 YAML hash differs from overlay")
    if locked_base["base_file_bytes_mutable"] is not False:
        raise ValueError("source-corrected S2 YAML bytes must remain immutable")

    resolved = copy.deepcopy(base)
    reference = overlay["controller_overlay"]["reference_solver"]
    resolved["reference_solver"]["time_discretization"] = copy.deepcopy(
        reference["time_discretization"]
    )
    if "active_time_controller" in resolved["reference_solver"]:
        raise ValueError("controller overlay ADD target already exists")
    resolved["reference_solver"]["active_time_controller"] = copy.deepcopy(
        reference["active_time_controller"]
    )

    authority = overlay["authority_lock"]
    overlay_hash = sha256_path(overlay_path)
    identity_payload = {
        name: str(_nested(authority, path)) for name, path in IDENTITY_FIELD_RECORDS
    }
    identity_payload["controller_v2_overlay_sha256"] = overlay_hash
    identity_payload["resolution_schema_version"] = RESOLUTION_SCHEMA_VERSION
    canonical = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    identity_hash = hashlib.sha256(canonical).hexdigest()
    return ResolvedControllerV2(
        base_config=base,
        overlay_document=overlay,
        resolved_config=resolved,
        base_sha256=base_hash,
        overlay_sha256=overlay_hash,
        identity_payload=identity_payload,
        identity_sha256=identity_hash,
    )


def resolved_runtime_identity_document(resolved: ResolvedControllerV2) -> dict[str, Any]:
    return {
        "task_id": "Q2_PHASE1_V2_SOURCE_CORRECTED_RUNTIME_IDENTITY_V3",
        "schema_version": "geophase_phase1_v2_source_corrected_runtime_identity_v3",
        "status": "preregistered_not_executed",
        "identity_fields_sha256": resolved.identity_payload,
        "resolved_runtime_identity_sha256": resolved.identity_sha256,
        "formal_execution_count": 0,
        "formal_artifact_count": 0,
        "numerical_execution_performed": False,
    }


__all__ = [
    "IDENTITY_FIELD_RECORDS",
    "RESOLUTION_SCHEMA_VERSION",
    "SOURCE_CORRECTION_BASE_COMMIT",
    "SOURCE_CORRECTION_BASE_TREE",
    "resolve_controller_v2",
    "resolved_runtime_identity_document",
    "validate_source_corrected_overlay_document",
]

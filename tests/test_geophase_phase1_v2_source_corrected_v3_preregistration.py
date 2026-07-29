from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    IDENTITY_FIELD_RECORDS,
    RESOLUTION_SCHEMA_VERSION,
    resolve_controller_v2,
    resolved_runtime_identity_document,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
OUTPUT_DIR = ROOT / "outputs" / "tables"
V3_OUTPUT_DIR = OUTPUT_DIR / "geophase_phase1_v2_source_corrected_v3"

SOURCE_PATH = CONFIG_DIR / "qiu_vo2_phase1_source_contract_v3.yaml"
S2_PATH = CONFIG_DIR / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
MANIFEST_PATH = (
    CONFIG_DIR / "geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml"
)
ADDENDUM_PATH = (
    CONFIG_DIR / "geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml"
)
OVERLAY_PATH = (
    CONFIG_DIR
    / "geophase_phase1_v2_embedded_time_controller_v2_source_corrected_v3.yaml"
)
EXPANDED_CSV_PATH = V3_OUTPUT_DIR / "formal_evaluation_manifest.csv"
EXPANDED_JSON_PATH = V3_OUTPUT_DIR / "formal_evaluation_manifest.json"
DAG_CSV_PATH = V3_OUTPUT_DIR / "runtime_readiness" / "execution_dag.csv"
DAG_JSON_PATH = V3_OUTPUT_DIR / "runtime_readiness" / "execution_dag.json"
IDENTITY_PATH = V3_OUTPUT_DIR / "resolved_runtime_identity.json"
PREREGISTRATION_PATH = V3_OUTPUT_DIR / "source_correction_preregistration.json"
SOURCE_MANIFEST_PATH = (
    ROOT / "data" / "external" / "qiu_2024_thermal_neuristor" / "manifest.json"
)

OLD_OVERLAY_PATH = CONFIG_DIR / "geophase_phase1_v2_embedded_time_controller_v2.yaml"
OLD_ADDENDUM_PATH = CONFIG_DIR / "geophase_phase1_v2_execution_addendum.yaml"

EXPECTED_OLD_BUNDLE_HASHES = {
    "configs/geophase_phase1_v2_embedded_time_controller_v2.yaml": (
        "eaca81d59b9a52c21fe60fab213a8f7fd65d83a674fd2ef27746d164e163c528"
    ),
    "configs/geophase_phase1_v2_execution_addendum.yaml": (
        "9d477b79a6a598b5032f104bea5b92290026b798e6599c2e9813c9ba11083640"
    ),
    "configs/geophase_phase1_v2_formal_manifest.yaml": (
        "54823e83d813ec4acd8df25354b62c38d58be158548414e637282383d1dc14a5"
    ),
    "configs/geophase_phase1_v2_s2_reference.yaml": (
        "0600498590a8c100ec8dee95621719ea655354ec118015868cb07fedf89f85d5"
    ),
    "configs/qiu_vo2_phase1_source_contract.yaml": (
        "857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252"
    ),
    "outputs/tables/geophase_phase1_v2/formal_evaluation_manifest.csv": (
        "c2b04c31c21e27a21b9ac90d1c9c9edfc05e6ea75dee7bf3b0dad180f8804a89"
    ),
    "outputs/tables/geophase_phase1_v2/formal_evaluation_manifest.json": (
        "c5b903997cb0c4d1a9df7c11c2d881bc391d326dfdcccd60d4d0a2d52a25176b"
    ),
    "outputs/tables/geophase_phase1_v2/runtime_readiness/execution_dag.csv": (
        "b506021bd2c3b64be917e728da463349b774ada6dd1c402eaf4c602a7b750fd2"
    ),
    "outputs/tables/geophase_phase1_v2/runtime_readiness/execution_dag.json": (
        "1f8a5ef122898974224c2208a0b41af0f776b5ef07bca444f5f0a727b5c9c87a"
    ),
}

EXPECTED_HIGH_BIAS_EVALUATIONS = {
    "P1V2-REF-high_bias_lock_15p8V-S1T4",
    "P1V2-REF-high_bias_lock_15p8V-S2T4",
    "P1V2-REF-high_bias_lock_15p8V-S4T1",
    "P1V2-REF-high_bias_lock_15p8V-S4T2",
    "P1V2-REF-high_bias_lock_15p8V-S4T4",
    "P1V2-TOP-O10-high_bias_lock_15p8V",
    "P1V2-TOP-O20-high_bias_lock_15p8V",
    "P1V2-TOP-O30-high_bias_lock_15p8V",
}

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _manifest_rows() -> list[dict[str, str]]:
    with EXPANDED_CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_historical_nine_file_bundle_is_byte_locked_and_preregistered() -> None:
    preregistration = _json(PREREGISTRATION_PATH)

    assert preregistration["old_bundle_hashes_sha256"] == EXPECTED_OLD_BUNDLE_HASHES
    assert len(EXPECTED_OLD_BUNDLE_HASHES) == 9
    for relative, expected in EXPECTED_OLD_BUNDLE_HASHES.items():
        assert _sha256(ROOT / relative) == expected
    assert preregistration["old_bundle_disposition"] == (
        "immutable_historical_planned_not_executed"
    )


def test_source_v3_locks_locators_hashes_and_qualitative_only_use() -> None:
    source = _yaml(SOURCE_PATH)
    source_manifest = _json(SOURCE_MANIFEST_PATH)
    preregistration = _json(PREREGISTRATION_PATH)
    correction = source["source_trend_correction_v3"]

    assert correction["source_manifest"]["sha256"] == _sha256(SOURCE_MANIFEST_PATH)
    assert correction["main_article"]["locator"] == (
        "Figure_2A_to_2C_printed_page_2306818_3_of_8"
    )
    assert correction["supporting_information"]["locator"] == (
        "Figure_S2_supporting_information_page_7"
    )
    assert correction["active_high_bias_protocol"] == {
        "protocol_id": "high_bias_lock_15p8V",
        "input_voltage_V": 15.8,
        "allowed_role": "qualitative_source_trend_probe",
    }
    assert correction["active_15V_compatibility_alias"] == "forbidden"
    assert {
        "quantitative_real_device_calibration",
        "waveform_fit_or_curve_reproduction",
        "independent_external_validation",
        "experimental_validation",
    } <= set(correction["forbidden_use"])
    assert preregistration["claim_status"] == "forbidden"
    assert preregistration["source_evidence"] == {
        "manifest_sha256": _sha256(SOURCE_MANIFEST_PATH),
        "main_article_sha256": correction["main_article"]["sha256"],
        "main_locator": correction["main_article"]["locator"],
        "supporting_information_sha256": correction["supporting_information"][
            "sha256"
        ],
        "supporting_information_locator": correction["supporting_information"][
            "locator"
        ],
    }

    manifest_sources = {
        record["artifact_id"]: record for record in source_manifest["sources"]
    }
    for section in ("main_article", "supporting_information"):
        locked = correction[section]
        manifest_record = manifest_sources[locked["artifact_id"]]
        assert manifest_record["sha256"].lower() == locked["sha256"]
        local_path = manifest_record.get("local_raw_path")
        if local_path and (ROOT / local_path).is_file():
            assert _sha256(ROOT / local_path) == locked["sha256"]


def test_v3_manifest_is_exactly_63_60_3_with_only_eight_renamed_evaluations() -> None:
    rows = _manifest_rows()
    metadata = _json(EXPANDED_JSON_PATH)
    preregistration = _json(PREREGISTRATION_PATH)

    assert len(rows) == metadata["evaluation_item_count"] == 63
    trajectories = {row["trajectory_id"] for row in rows}
    assert len(trajectories) == metadata["unique_execution_unit_count"] == 60
    reused = [row for row in rows if row["dependency_ids"]]
    assert len(reused) == metadata["reused_evaluation_item_count"] == 3
    assert preregistration["evaluation_item_count"] == 63
    assert preregistration["unique_execution_unit_count"] == 60
    assert preregistration["reused_evaluation_item_count"] == 3

    high_bias_rows = [row for row in rows if "high_bias_lock_15p8V" in row["evaluation_id"]]
    assert {row["evaluation_id"] for row in high_bias_rows} == (
        EXPECTED_HIGH_BIAS_EVALUATIONS
    )
    assert sum(row["evaluation_group"] == "REF" for row in high_bias_rows) == 5
    assert sum(row["evaluation_group"] == "TOP" for row in high_bias_rows) == 3
    assert len({row["trajectory_id"] for row in high_bias_rows}) == 7

    o20 = next(
        row
        for row in high_bias_rows
        if row["evaluation_id"] == "P1V2-TOP-O20-high_bias_lock_15p8V"
    )
    assert o20["dependency_ids"] == "P1V2-REF-high_bias_lock_15p8V-S4T4"
    assert o20["trajectory_id"] == "TRJ-P1V2-REF-high_bias_lock_15p8V-S4T4"
    assert metadata["reuse_map"][o20["evaluation_id"]] == o20["dependency_ids"]


def test_active_v3_bundle_has_no_executable_15V_alias() -> None:
    source = _yaml(SOURCE_PATH)
    config = _yaml(S2_PATH)
    manifest = _yaml(MANIFEST_PATH)
    addendum = _yaml(ADDENDUM_PATH)
    overlay = _yaml(OVERLAY_PATH)
    rows = _manifest_rows()

    assert source["source_trend_correction_v3"]["active_15V_compatibility_alias"] == (
        "forbidden"
    )
    protocols = config["formal_protocols"]["protocols"]
    assert "high_bias_15V" not in protocols
    assert protocols["high_bias_lock_15p8V"]["input_voltage_V"] == pytest.approx(15.8)
    assert "high_bias_15V" not in config["verification_matrix"]["literature_trends"]
    ref_group = next(group for group in manifest["groups"] if group["group_id"] == "REF")
    assert "high_bias_15V" not in ref_group["axes"]["protocol"]
    assert "high_bias_15V" not in addendum["runtime_preflight"][
        "deterministic_states"
    ]["high_conductive"].values()
    scales = overlay["controller_overlay"]["reference_solver"][
        "active_time_controller"
    ]["voltage_scale"]["protocol_V_scale_V"]
    assert "high_bias_15V" not in scales
    assert scales["high_bias_lock_15p8V"] == pytest.approx(15.8)
    assert all(row["protocol_id"] != "high_bias_15V" for row in rows)
    assert all("high_bias_15V" not in row["evaluation_id"] for row in rows)


def test_C1_C2_and_12p5V_are_unchanged_and_high_state_changes_only_protocol() -> None:
    old_overlay = _yaml(OLD_OVERLAY_PATH)
    new_overlay = _yaml(OVERLAY_PATH)
    old_addendum = _yaml(OLD_ADDENDUM_PATH)
    new_addendum = _yaml(ADDENDUM_PATH)

    old_readiness = old_overlay["readiness_validation"]
    new_readiness = new_overlay["readiness_validation"]
    assert new_readiness["C1"] == old_readiness["C1"]
    assert new_readiness["C2"] == old_readiness["C2"]
    assert new_readiness["C1"]["fixture"]["protocol"] == (
        "transition_probe_12p5V"
    )
    assert new_readiness["C1"]["fixture"]["initial_state"] == {
        "temperature_K": 336.4,
        "branch_memory_b": 1.0,
        "conductive_state_s": 0.5,
        "device_voltage_V": 0.0,
    }
    scale = new_overlay["controller_overlay"]["reference_solver"][
        "active_time_controller"
    ]["voltage_scale"]["protocol_V_scale_V"]
    assert scale["transition_probe_12p5V"] == pytest.approx(12.5)

    old_states = old_addendum["runtime_preflight"]["deterministic_states"]
    new_states = new_addendum["runtime_preflight"]["deterministic_states"]
    assert new_states["equilibrium"] == old_states["equilibrium"]
    assert new_states["legal_critical"] == old_states["legal_critical"]
    expected_high = copy.deepcopy(old_states["high_conductive"])
    assert expected_high.pop("short_protocol") == "high_bias_15V"
    actual_high = copy.deepcopy(new_states["high_conductive"])
    assert actual_high.pop("short_protocol") == "high_bias_lock_15p8V"
    assert actual_high == expected_high == {
        "temperature_K": "upper_validity_temperature_380K",
        "branch_memory": 1.0,
        "conductive_state": "equilibrium_at_temperature_and_branch",
    }


def test_resolver_and_machine_identity_bind_exactly_ten_fields() -> None:
    resolved = resolve_controller_v2(S2_PATH, OVERLAY_PATH)
    machine = _json(IDENTITY_PATH)
    expected_names = [name for name, _ in IDENTITY_FIELD_RECORDS] + [
        "controller_v2_overlay_sha256",
        "resolution_schema_version",
    ]

    assert len(expected_names) == len(set(expected_names)) == 10
    assert list(resolved.identity_payload) == expected_names
    assert resolved.identity_payload["resolution_schema_version"] == (
        RESOLUTION_SCHEMA_VERSION
    )
    assert machine == resolved_runtime_identity_document(resolved)
    assert machine["identity_fields_sha256"] == resolved.identity_payload
    assert machine["resolved_runtime_identity_sha256"] == resolved.identity_sha256
    assert machine["formal_execution_count"] == 0
    assert machine["formal_artifact_count"] == 0
    assert machine["numerical_execution_performed"] is False


def test_config_only_builders_are_current_and_no_formal_artifact_exists() -> None:
    preregistration = _json(PREREGISTRATION_PATH)
    commands = [
        [
            sys.executable,
            "scripts/preregister_geophase_phase1_v2_source_corrected_execution_v3.py",
            "--check",
        ],
        [
            sys.executable,
            "scripts/preregister_geophase_phase1_v2_source_corrected_v3.py",
            "--base-sha",
            preregistration["base_main_commit"],
            "--base-tree",
            preregistration["base_main_tree"],
            "--check",
        ],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    assert preregistration["formal_execution_count"] == 0
    assert preregistration["formal_artifact_count"] == 0
    assert preregistration["formal_execution_consumed"] is False
    assert preregistration["new_numerical_work_before_preregistration_push"] is False
    assert _json(EXPANDED_JSON_PATH)["formal_execution_count"] == 0
    assert _json(DAG_JSON_PATH)["formal_execution_count"] == 0
    assert not (V3_OUTPUT_DIR / "formal_summary.json").exists()
    assert not (V3_OUTPUT_DIR / "formal_convergence.csv").exists()

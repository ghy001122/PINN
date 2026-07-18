"""Freeze the M35 public multi-voltage protocol before any fitting."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from pinnpcm.external_data.vo2_zhang import compute_sha256, load_manifest


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _curve_record(
    *,
    path: Path,
    curve_id: str,
    voltage_V: float | None,
    raw_units: dict[str, str],
    si_units: dict[str, str],
    conversion_formula: str,
) -> dict[str, Any]:
    return {
        "artifact_id": curve_id,
        "source_role": "nature_source_data",
        "source_url": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-51254-4/MediaObjects/41467_2024_51254_MOESM8_ESM.zip",
        "source_version_or_tag": "publisher_file",
        "source_commit_or_blob_sha": "",
        "sha256": compute_sha256(path),
        "license_id": "CC-BY-4.0",
        "data_kind": "public_external_raw",
        "use_role": "repository_calibration_and_lovo",
        "derived_from_artifact_ids": ["zhang_2024_nature_source_data"],
        "curve_id": curve_id,
        "protocol_id": None if voltage_V is None else f"dc_{voltage_V:g}v",
        "voltage_V": voltage_V,
        "branch_id": "heating_and_cooling" if voltage_V is None else None,
        "raw_units": raw_units,
        "si_units": si_units,
        "conversion_formula": conversion_formula,
        "sealed_until_fit_lock": False,
        "path": _relative(path),
    }


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    if head != str(config["base_snapshot"]):
        raise RuntimeError(
            f"M35 preregistration requires {config['base_snapshot']}; found {head}."
        )
    output = _resolve(config["outputs"]["preregistration"])
    provenance_path = _resolve(config["data"]["prereg_manifest"])
    if output.exists() or provenance_path.exists():
        raise RuntimeError("M35 preregistration already exists; do not overwrite it.")

    original_manifest_path = _resolve(config["data"]["original_manifest"])
    original_manifest = load_manifest(original_manifest_path)
    archive_path = _resolve(config["sources"]["nature_source_data"]["parent_archive"])
    archive_hash = compute_sha256(archive_path)

    rt_spec = config["data"]["rt"]
    rt_path = _resolve(rt_spec["path"])
    open_specs = list(config["data"]["open_voltage_curves"])
    open_paths = [_resolve(item["path"]) for item in open_specs]
    sealed_names = set(config["data"]["withheld_13v"]["member_names_metadata_only"])
    manifest_sealed = [
        item
        for item in original_manifest["archive_members"]["nature_source_data"]
        if item.get("member_name") in sealed_names
    ]

    provenance_artifacts: list[dict[str, Any]] = [
        {
            "artifact_id": "zhang_2024_nature_article",
            "source_role": "paper",
            "source_url": config["sources"]["paper"]["url"],
            "source_version_or_tag": "published_2024-08-14",
            "source_commit_or_blob_sha": "",
            "sha256": None,
            "license_id": config["sources"]["paper"]["license_id"],
            "data_kind": "bibliographic_source",
            "use_role": "source_model_semantics",
        },
        {
            "artifact_id": "zhang_2024_nature_source_data",
            "source_role": "nature_source_data",
            "source_url": config["sources"]["nature_source_data"]["url"],
            "source_version_or_tag": "publisher_file",
            "source_commit_or_blob_sha": "",
            "sha256": archive_hash,
            "license_id": config["sources"]["nature_source_data"]["license_id"],
            "data_kind": "public_external_raw_archive",
            "use_role": "source_reproduction_and_repository_calibration",
            "path": _relative(archive_path),
        },
        {
            "artifact_id": "zhang_2024_zenodo_record_13119587",
            "source_role": "zenodo_archive",
            "source_url": config["sources"]["zenodo"]["url"],
            "source_version_or_tag": "record_13119587",
            "source_commit_or_blob_sha": "",
            "sha256": None,
            "license_id": config["sources"]["zenodo"]["license_id"],
            "data_kind": "public_external_archive_record",
            "use_role": "source_provenance",
        },
        {
            "artifact_id": "zhang_2024_github_v1_0_0",
            "source_role": "github_tag",
            "source_url": config["sources"]["github"]["url"],
            "source_version_or_tag": config["sources"]["github"]["tag"],
            "source_commit_or_blob_sha": "v1.0.0_tag",
            "sha256": None,
            "license_id": config["sources"]["github"]["license_id"],
            "data_kind": "third_party_source_code",
            "use_role": "source_model_semantics",
        },
        _curve_record(
            path=rt_path,
            curve_id=str(rt_spec["curve_id"]),
            voltage_V=None,
            raw_units={"temperature": "K", "resistance": "kOhm"},
            si_units={"temperature": "K", "resistance": "ohm"},
            conversion_formula="temperature_K=x; resistance_ohm=1000*y",
        ),
    ]
    for item, path in zip(open_specs, open_paths):
        provenance_artifacts.append(
            _curve_record(
                path=path,
                curve_id=str(item["curve_id"]),
                voltage_V=float(item["voltage_V"]),
                raw_units={"time": "s", "CH3": "V", "CH4": "V"},
                si_units={"time": "s", "current": "A", "device_voltage": "V"},
                conversion_formula=f"current_A=CH3/{float(config['data']['current_sense_ohm']):g}; device_voltage_V=CH4",
            )
        )

    provenance = {
        "schema_version": "m35_public_multivoltage_provenance_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_semantics": config["evidence_semantics"],
        "artifacts": provenance_artifacts,
        "lovo_roles": {
            fold["fold_id"]: {
                "fit_voltages_V": fold["fit_voltages_V"],
                "holdout_voltage_V": fold["holdout_voltage_V"],
                "role": "repository_side_lovo_evaluation",
            }
            for fold in config["fit"]["folds"]
        },
        "sealed_members_metadata_only": [
            {
                "member_name": item["member_name"],
                "crc32": item["crc32"],
                "compressed_size": item["compressed_size"],
                "uncompressed_size": item["uncompressed_size"],
                "content_read_prelock": item["content_read_prelock"],
                "extracted_path": item["extracted_path"],
                "sha256": item["sha256"],
                "use_role": "future_repository_withheld_preregistered_cross_voltage_evaluation",
            }
            for item in manifest_sealed
        ],
        "sealed_13v_access": False,
        "independent_external_validation": False,
    }
    _write_json(provenance_path, provenance)

    d0a_path = ROOT / "outputs/tables/vo2_d0a_source_reproduction.json"
    d0a = json.loads(d0a_path.read_text(encoding="utf-8"))
    expected_member_names = set(
        config["data"]["withheld_13v"]["member_names_metadata_only"]
    )
    open_voltages = [float(item["voltage_V"]) for item in open_specs]
    folds = config["fit"]["folds"]
    preflight = {
        "base_snapshot_exact": head == str(config["base_snapshot"]),
        "parent_archive_sha256_exact": archive_hash
        == str(config["sources"]["nature_source_data"]["parent_sha256"]).upper(),
        "all_open_curves_exist": bool(rt_path.exists() and all(path.exists() for path in open_paths)),
        "open_voltage_set_exact": open_voltages == [9.0, 11.0, 15.0, 17.0],
        "no_open_path_mentions_13v": all("13v" not in path.name.casefold().replace("_", "") for path in open_paths),
        "sealed_member_names_exact": {item.get("member_name") for item in manifest_sealed}
        == expected_member_names,
        "sealed_member_content_unread": len(manifest_sealed) == 2
        and all(item.get("content_read_prelock") is False for item in manifest_sealed),
        "sealed_member_unextracted": len(manifest_sealed) == 2
        and all(item.get("extracted_path") is None and item.get("sha256") is None for item in manifest_sealed),
        "original_manifest_sealed_flag_false": original_manifest.get("sealed_member_content_read_prelock") is False,
        "license_surfaces_separated": (
            config["sources"]["paper"]["license_id"] == "CC-BY-4.0"
            and config["sources"]["zenodo"]["license_id"] == "CC-BY-4.0"
            and config["sources"]["github"]["license_id"] == "MIT"
        ),
        "four_evidence_semantics_distinct": len(set(config["evidence_semantics"].values())) == 4,
        "source_equations_complete": set(config["source_model"]["equations"])
        == {"electrical", "thermal", "resistance"},
        "source_event_order_locked": bool(config["source_model"]["event_rules"]["ordering"]),
        "source_si_units_complete": set(config["source_model"]["units"])
        >= {"time", "voltage", "current", "resistance", "thermal_capacitance", "thermal_conductance"},
        "gamma_sub_direct_validation_forbidden": config["cross_model_mapping"]["direct_S_e_to_gamma_sub_validation_claim"]
        == "forbidden",
        "geometry_equivalence_not_assumed": config["cross_model_mapping"]["geometry_equivalence_proved"] is False,
        "historical_d0a_failure_preserved": (
            d0a.get("gate_passed") is False
            and d0a.get("claim_status") == "failed_but_informative"
            and abs(
                float(d0a["source_si_metrics"]["medium_vs_fine_dt_current_nrmse95"])
                - float(config["solver_convergence"]["d0a_medium_vs_fine_current_nrmse95"])
            )
            <= 1.0e-15
        ),
        "four_lovo_folds_complete": len(folds) == 4
        and all(
            sorted([float(value) for value in fold["fit_voltages_V"]] + [float(fold["holdout_voltage_V"])])
            == open_voltages
            for fold in folds
        ),
        "eight_deterministic_starts_locked": len(config["fit"]["deterministic_start_offsets"]) == 8,
        "fit_output_absent": not _resolve(config["outputs"]["fit_summary"]).exists(),
        "fit_lock_absent": not _resolve(config["outputs"]["fit_lock"]).exists(),
    }
    all_pass = bool(preflight and all(preflight.values()))

    locked_paths = [
        "configs/m35_public_multivoltage_fit.yaml",
        "docs/schemas/m35_public_multivoltage_preregistration_v1.schema.json",
        "scripts/preregister_m35_public_multivoltage.py",
        "scripts/run_m34a_gradient_semantics.py",
        "scripts/run_m35_public_multivoltage_fit.py",
        "src/pinnpcm/external_data/vo2_multivoltage.py",
        "src/pinnpcm/pinn/m34a_gradient_semantics.py",
        "tests/test_m34a_gradient_semantics.py",
        "tests/test_m35_public_multivoltage.py",
        "tests/test_m35_result_evidence.py",
        ".gitignore",
        "configs/vo2_d0a_exact_source_v2.yaml",
        "src/pinnpcm/external_data/vo2_zhang.py",
        "src/pinnpcm/physics/vo2_thermal_neuristor.py",
        "outputs/tables/vo2_d0a_source_reproduction.json",
        "outputs/tables/m34_contract_audit_summary.json",
        "data/external/vo2_zhang_2024/manifest.json",
        _relative(archive_path),
        _relative(rt_path),
        *[_relative(path) for path in open_paths],
    ]
    missing = [path for path in locked_paths if not (ROOT / path).exists()]
    if missing:
        raise FileNotFoundError(f"Missing M35 locked files: {missing}")
    payload = {
        "schema_version": "m35_public_multivoltage_preregistration_v1",
        "stage_id": config["stage_id"],
        "base_snapshot": head,
        "status": "locked_before_fit" if all_pass else "failed_but_informative",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_question": "Can the open public 9/11/15/17 V traces support a step-converged thermal-timescale calibration and leave-one-voltage-out bridge while 13 V remains sealed?",
        "config_sha256": {
            "path": _relative(config_path),
            "sha256": compute_sha256(config_path),
        },
        "provenance_manifest": _relative(provenance_path),
        "provenance_manifest_sha256": compute_sha256(provenance_path),
        "locked_files": {path: compute_sha256(ROOT / path) for path in locked_paths},
        "preflight_checks": preflight,
        "all_preflight_checks_pass": all_pass,
        "fit_authorized_after_preregistration_commit": all_pass,
        "fit_must_wait_for_new_commit": True,
        "solver_convergence_and_jacobian_are_fail_closed": True,
        "m34a_is_post_hoc_diagnostic_and_never_authorizes_training": True,
        "sealed_13v_access": False,
        "forbidden_claims": config["claim_boundary"]["forbidden"],
    }
    _write_json(output, payload)
    if not all_pass:
        raise RuntimeError("M35 preregistration failed one or more preflight checks.")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("configs/m35_public_multivoltage_fit.yaml")
    )
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(path)
    print(
        json.dumps(
            {
                "status": result["status"],
                "all_preflight_checks_pass": result["all_preflight_checks_pass"],
                "sealed_13v_access": False,
            },
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()

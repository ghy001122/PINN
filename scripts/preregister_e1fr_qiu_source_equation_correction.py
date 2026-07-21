"""Lock the single post-hoc E1F-R source-equation correction vote."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/e1fr_qiu_source_equation_correction.yaml"
ORIGINAL_PREREG = ROOT / "outputs/tables/e1f_qiu_author_anchor_preregistration.json"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
        "size_bytes": int(stat.st_size),
    }


def _verify_record(record: Mapping[str, Any]) -> bool:
    path = ROOT / str(record["path"])
    return (
        path.exists()
        and path.stat().st_size == int(record["size_bytes"])
        and _sha256(path) == str(record["sha256"])
    )


def preregister(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    base = str(config["base_snapshot"])
    original = json.loads(ORIGINAL_PREREG.read_text(encoding="utf-8"))
    amendment_path = _resolve(config["source"]["semantic_amendment"])
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    original_result_path = _resolve(config["source"]["original_formal_result"])
    original_result = json.loads(original_result_path.read_text(encoding="utf-8"))

    output_paths = [
        _resolve(config["outputs"][key])
        for key in (
            "validation_json",
            "validation_csv",
            "coordinate_preflight_json",
            "figure_setting",
            "report",
        )
    ]
    implementation_paths = [
        config_path,
        ROOT / "src/pinnpcm/physics/qiu_author_compact_model.py",
        ROOT / "src/pinnpcm/solvers/qiu_author_ode.py",
        ROOT / "scripts/run_e1f_qiu_author_anchor.py",
        ROOT / "scripts/preregister_e1fr_qiu_source_equation_correction.py",
        ROOT / "scripts/run_e1fr_qiu_source_equation_correction.py",
        ROOT / "tests/test_e1f_qiu_author_equations.py",
        ROOT / "tests/test_e1fr_contract.py",
        _resolve(config["source"]["digitized_manifest"]),
        ROOT
        / "data/external/qiu_2024_thermal_neuristor/derived/qiu_2024_si_fig_s1_12v_current.csv",
        ROOT
        / "data/external/qiu_2024_thermal_neuristor/derived/qiu_2024_si_fig_s1_12v_device_voltage.csv",
        amendment_path,
        original_result_path,
    ]
    original_groups = (
        "raw_source_records",
        "m40_protected_records",
        "m40r_protected_records",
        "frozen_gt_records",
    )
    protected_records = [
        record for group in original_groups for record in original[group]
    ]
    all_implementation_exist = all(path.exists() for path in implementation_paths)
    correction = config["correction_contract"]
    gates = config["gates"]
    checks = {
        "base_snapshot_exact": head == base,
        "original_e1f_prereg_passed": original["all_preflight_checks_pass"] is True,
        "original_protected_records_unchanged": all(
            _verify_record(record) for record in protected_records
        ),
        "original_formal_preserved": original_result.get("formal_execution_attempt") == 1,
        "amendment_requires_corrected_vote": amendment["corrected_formal_vote_required"]
        is True,
        "original_vote_invalid": amendment["scientific_vote_from_original_run"]
        is False,
        "literal_s3_locked": correction["source_equation_s3_literal"]
        == "T_pr = delta*w/2 + T_c - (2*F(T_r)-1)/beta - T_r",
        "holdout_invalid_and_forbidden": correction["main_fig2b_status"]
        == "implementation_contract_invalid_unassessed"
        and correction["main_fig2b_simulation_or_scoring_forbidden"] is True,
        "setting_identity_unchanged": config["source"]["setting_curve"]["curve_id"]
        == "qiu_2024_si_fig_s1_12v"
        and float(config["source"]["setting_curve"]["input_voltage_V"]) == 12.0,
        "setting_gate_unchanged": float(gates["setting_curve_nrmse_max"]) == 0.10,
        "solver_gate_unchanged": float(
            gates["dop853_radau_current_waveform_nrmse_max"]
        )
        == 1.0e-3,
        "implementation_inputs_exist": all_implementation_exist,
        "result_paths_absent": not any(path.exists() for path in output_paths),
        "one_run_budget": int(config["budget"]["formal_execution_limit"]) == 1,
        "no_fit_training_or_holdout": all(
            config["budget"][key] == "forbidden"
            for key in ("fitting", "holdout_refit", "pinn_training")
        ),
        "m41_and_13v_closed": config["governance"]["m41_authorized"] is False
        and config["governance"]["sealed_zhang_13v_access"] is False,
    }
    payload: dict[str, Any] = {
        "schema_version": "e1fr_qiu_source_equation_correction_preregistration_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": base,
        "git_commit_before_preregistration": head,
        "git_dirty_before_preregistration": bool(_git("status", "--short")),
        "post_lock_corrective_audit": True,
        "independent_holdout": False,
        "original_e1f_scientific_vote": False,
        "main_fig2b_status": "implementation_contract_invalid_unassessed",
        "main_fig2b_simulation_or_scoring_authorized": False,
        "preflight_checks": checks,
        "all_preflight_checks_pass": bool(all(checks.values())),
        "locked_config": config,
        "implementation_records": (
            [_record(path) for path in implementation_paths]
            if all_implementation_exist
            else []
        ),
        "protected_record_count": len(protected_records),
        "protected_groups_from_original_preregistration": list(original_groups),
        "formal_result_paths_absent_at_lock": [
            path.relative_to(ROOT).as_posix() for path in output_paths
        ],
        "formal_execution_limit": 1,
        "m41_authorized": False,
        "pinn_training_authorized": False,
        "sealed_zhang_13v_access": False,
    }
    output = _resolve(config["outputs"]["preregistration"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not payload["all_preflight_checks_pass"]:
        raise RuntimeError(f"E1F-R preregistration failed: {checks}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    payload = preregister(_resolve(args.config))
    print(
        json.dumps(
            {
                "all_preflight_checks_pass": payload["all_preflight_checks_pass"],
                "check_count": len(payload["preflight_checks"]),
                "post_lock_corrective_audit": True,
                "holdout_simulation_or_scoring_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

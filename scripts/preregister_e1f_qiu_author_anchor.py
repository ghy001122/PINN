"""Create the E1F source/holdout/protection lock before digitization."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/e1f_qiu_author_external_anchor.yaml"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_blob_oid(path: Path) -> str | None:
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _record(path: Path, source_commit: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
        "size_bytes": stat.st_size,
        "git_blob_oid": _git_blob_oid(path),
        "source_commit": source_commit,
        "mtime_utc_informational": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def _protected_paths() -> tuple[list[Path], list[Path], list[Path]]:
    m40r_prereg_path = ROOT / "outputs/tables/m40r_qiu_e0_preregistration.json"
    m40r_prereg = json.loads(m40r_prereg_path.read_text(encoding="utf-8"))
    m40 = [ROOT / path for path in m40r_prereg["old_m40_protected_hashes"]]
    m40.append(ROOT / "src/pinnpcm/solvers/__init__.py")
    m40r = [ROOT / path for path in m40r_prereg["locked_files"]]
    m40r.extend(
        ROOT / path
        for path in (
            "outputs/tables/m40r_qiu_e0_preregistration.json",
            "outputs/tables/m40r_qiu_e0_summary.json",
            "outputs/tables/m40r_qiu_active_transient.json",
            "outputs/tables/m40r_qiu_mesh_convergence.csv",
            "outputs/figures/m40r/mesh_and_field_convergence.png",
            "outputs/figures/m40r/active_transient_and_ledgers.png",
            "docs/codex_reports/m40r_qiu_e0_repair_results.md",
            "tests/test_m40r_qiu_result_evidence.py",
        )
    )
    frozen = [ROOT / path for path in m40r_prereg["frozen_gt_hashes"]]
    return sorted(set(m40)), sorted(set(m40r)), sorted(set(frozen))


def preregister(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    source_commit = str(config["base_snapshot"])
    if head != source_commit:
        raise RuntimeError(f"E1F requires base {source_commit}; found {head}.")

    output_paths = [
        _resolve(config["outputs"][key])
        for key in (
            "validation_json",
            "validation_csv",
            "bridge_mismatch_csv",
            "coordinate_preflight_json",
            "figure_validation",
            "figure_bridge",
            "report",
        )
    ]
    if any(path.exists() for path in output_paths):
        present = [path.relative_to(ROOT).as_posix() for path in output_paths if path.exists()]
        raise RuntimeError(f"E1F result artifacts exist before preregistration: {present}")

    manifest_path = _resolve(config["source"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    main_path = _resolve(config["source"]["main_pdf"])
    si_path = _resolve(config["source"]["supporting_information_pdf"])
    expected_hashes = {
        item["local_raw_path"]: item["sha256"]
        for item in manifest["sources"]
        if item.get("local_raw_path")
    }
    raw_sources = [_record(main_path, source_commit), _record(si_path, source_commit)]
    preregistration_implementation_paths = [
        config_path,
        ROOT / "scripts/preregister_e1f_qiu_author_anchor.py",
        ROOT / "tests/test_e1f_preregistration.py",
        ROOT / "scripts/train_pinn_inverse_v1.py",
        ROOT / "tests/test_pinn_inverse_v1.py",
    ]

    m40_paths, m40r_paths, frozen_paths = _protected_paths()
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in [*m40_paths, *m40r_paths, *frozen_paths, main_path, si_path]
        if not path.exists()
    ]
    m40r_summary = json.loads(
        (ROOT / "outputs/tables/m40r_qiu_e0_summary.json").read_text(encoding="utf-8")
    )
    gates = config["gates"]
    governance = config["governance"]
    holdout = config["source"]["holdout_curve"]
    checks = {
        "base_snapshot_exact": head == source_commit,
        "all_protected_inputs_exist": not missing,
        "raw_main_hash_matches_manifest": _sha256(main_path)
        == expected_hashes[config["source"]["main_pdf"]].upper(),
        "raw_si_hash_matches_manifest": _sha256(si_path)
        == expected_hashes[config["source"]["supporting_information_pdf"]].upper(),
        "holdout_curve_locked_before_ordinate_access": holdout["curve_id"]
        == "qiu_2024_main_fig2b_12p5v"
        and holdout["numeric_ordinate_access_before_preregistration"] is False,
        "holdout_not_mislabeled_independent": holdout["independent_external_validation"]
        is False,
        "holdout_development_independence_not_assumed": holdout[
            "source_author_parameter_development_independence_known"
        ]
        is False
        and holdout["same_paper_development_contamination_risk"] is True,
        "source_contract_limitations_declared": config["hysteresis_contract"][
            "qiu_source_reports_complete_executable_update"
        ]
        is False
        and config["hysteresis_contract"][
            "exact_author_code_reproduction_authorized"
        ]
        is False
        and config["governance"]["exact_author_code_reproduction_authorized"]
        is False,
        "setting_curve_locked": config["source"]["setting_curve"]["curve_id"]
        == "qiu_2024_si_fig_s1_12v",
        "source_parameter_values_match_si": config["author_parameters"]
        == {
            "resistance_prefactor_ohm": 5.359e-3,
            "metallic_resistance_ohm": 262.5,
            "activation_temperature_K": 5220.0,
            "beta_per_K": 0.253,
            "hysteresis_width_K": 7.193,
            "critical_temperature_K": 332.8,
            "proximity_gamma_dimensionless": 0.956,
            "dynamic_metallic_factor": 4.90,
            "parallel_capacitance_F": 145.0e-12,
            "thermal_conductance_W_per_K": 0.206e-3,
            "thermal_capacitance_J_per_K": 49.6e-12,
            "provenance_role": "source_author_fitted_lumped_equivalent",
        },
        "solver_pair_locked": config["solvers"]["primary_method"] == "DOP853"
        and config["solvers"]["independent_method"] == "Radau",
        "scientific_gates_locked": float(
            gates["dop853_radau_current_waveform_nrmse_max"]
        )
        == 1.0e-3
        and float(gates["setting_curve_nrmse_max"]) == 0.10
        and float(gates["holdout_curve_nrmse_max"]) == 0.15,
        "formal_budget_locked": int(config["budget"]["formal_execution_limit"]) == 1
        and int(config["budget"]["maximum_total_forward_integrations"]) <= 72
        and float(config["budget"]["maximum_cpu_wall_hours"]) <= 1.0,
        "no_fit_or_training": all(
            config["budget"][key] == "forbidden"
            for key in ("fitting", "holdout_refit", "pinn_training")
        ),
        "m40r_history_preserved": m40r_summary["status"]
        == "failed_but_informative"
        and m40r_summary["m41_conservative_reduction_authorized"] is False,
        "e1f_governance_exact": governance["m40r_formal_budget_consumed"] is True
        and governance["further_m40r_execution_forbidden"] is True
        and governance["original_numeric_e0_passed"] is True
        and governance["qiu_dynamic_source_bridge_passed"] is False,
        "no_result_artifacts_before_lock": not any(path.exists() for path in output_paths),
    }
    payload = {
        "schema_version": "e1f_qiu_author_anchor_preregistration_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": source_commit,
        "git_commit_before_preregistration": head,
        "git_dirty_before_preregistration": bool(_git("status", "--short")),
        "preflight_checks": checks,
        "all_preflight_checks_pass": bool(all(checks.values())),
        "missing_protected_inputs": missing,
        "raw_source_records": raw_sources,
        "preregistration_implementation_records": [
            _record(path, source_commit) for path in preregistration_implementation_paths
        ],
        "m40_protected_records": [_record(path, source_commit) for path in m40_paths],
        "m40r_protected_records": [_record(path, source_commit) for path in m40r_paths],
        "frozen_gt_records": [_record(path, source_commit) for path in frozen_paths],
        "locked_source_contract": config["source"],
        "locked_author_parameters": config["author_parameters"],
        "locked_initial_conditions": config["initial_conditions"],
        "locked_hysteresis_contract": config["hysteresis_contract"],
        "locked_solver_contract": config["solvers"],
        "locked_digitization_contract": config["digitization"],
        "locked_baselines": config["baselines"],
        "locked_gates": gates,
        "locked_effective_coordinate_preflight": config[
            "effective_coordinate_preflight"
        ],
        "locked_budget": config["budget"],
        "governance": governance,
        "formal_result_paths_absent_at_lock": [
            path.relative_to(ROOT).as_posix() for path in output_paths
        ],
        "digitization_authorized_after_preregistration_commit": bool(all(checks.values())),
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
        raise RuntimeError(f"E1F preregistration failed: {checks}; missing={missing}")
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
                "m40_protected_count": len(payload["m40_protected_records"]),
                "m40r_protected_count": len(payload["m40r_protected_records"]),
                "frozen_gt_count": len(payload["frozen_gt_records"]),
                "holdout_ordinate_accessed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

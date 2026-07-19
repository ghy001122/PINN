"""Create the fail-closed M37 semantic audit and preregistration lock."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from pinnpcm.external_data.vo2_cross_regime_observability import (
    build_whitening_record,
    m36_semantic_audit,
)
from pinnpcm.external_data.vo2_multivoltage import preprocess_experiment
from pinnpcm.external_data.vo2_zhang import compute_sha256


ROOT = Path(__file__).resolve().parents[1]


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_observations(config: Mapping[str, Any]) -> dict[float, dict[str, Any]]:
    observations: dict[float, dict[str, Any]] = {}
    for item in config["data"]["open_voltage_curves"]:
        path = _resolve(item["path"])
        normalized = path.name.casefold().replace("_", "").replace(" ", "")
        if "13v" in normalized:
            raise PermissionError("M37 preregistration attempted 13 V numeric access.")
        voltage = float(item["voltage_V"])
        observations[voltage] = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
    if sorted(observations) != [9.0, 11.0, 15.0, 17.0]:
        raise RuntimeError("M37 open observation set must be exactly 9/11/15/17 V.")
    return observations


def _locked_paths(config: Mapping[str, Any]) -> list[str]:
    paths = [
        "configs/m37_continuous_event_observability.yaml",
        "docs/schemas/m37_continuous_event_observability_evidence_v1.schema.json",
        "src/pinnpcm/external_data/vo2_cross_regime_observability.py",
        "scripts/preregister_m37_continuous_event_observability.py",
        "scripts/run_m37_continuous_event_observability.py",
        "tests/test_m37_continuous_event_observability.py",
        "tests/test_m37_result_evidence.py",
        str(config["historical_inputs"]["m36_config"]),
        str(config["historical_inputs"]["m36_summary"]),
        str(config["historical_inputs"]["m36_metrics"]),
        str(config["historical_inputs"]["m36_execution_script"]),
        str(config["historical_inputs"]["source_parameter_config"]),
        "src/pinnpcm/physics/vo2_event_resolved.py",
        "src/pinnpcm/physics/vo2_thermal_neuristor.py",
        "src/pinnpcm/external_data/vo2_orbit_convergence.py",
        "src/pinnpcm/external_data/vo2_orbit_fit.py",
        str(config["outputs"]["semantic_audit"]),
    ]
    paths.extend(str(item["path"]) for item in config["data"]["open_voltage_curves"])
    if len(paths) != len(set(paths)):
        raise RuntimeError("M37 lock path list contains duplicates.")
    return paths


def preregister(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    m36_config_path = _resolve(config["historical_inputs"]["m36_config"])
    m36_summary_path = _resolve(config["historical_inputs"]["m36_summary"])
    m36_metrics_path = _resolve(config["historical_inputs"]["m36_metrics"])
    m36_script_path = _resolve(config["historical_inputs"]["m36_execution_script"])
    m36_config = yaml.safe_load(m36_config_path.read_text(encoding="utf-8"))
    m36_summary = json.loads(m36_summary_path.read_text(encoding="utf-8"))
    with m36_metrics_path.open(encoding="utf-8", newline="") as handle:
        metric_rows = list(csv.DictReader(handle))
    audit = m36_semantic_audit(
        m36_summary,
        metric_rows,
        execution_script_text=m36_script_path.read_text(encoding="utf-8"),
        summary_sha256=compute_sha256(m36_summary_path),
        metrics_sha256=compute_sha256(m36_metrics_path),
        execution_script_sha256=compute_sha256(m36_script_path),
    )
    _write_json(_resolve(config["outputs"]["semantic_audit"]), audit)

    observations = _load_observations(config)
    whitening = build_whitening_record(observations, m36_summary, config)
    open_records = [
        {
            "voltage_V": float(item["voltage_V"]),
            "regime": str(item["regime"]),
            "expected_activity_class": str(item["expected_activity_class"]),
            "path": str(item["path"]),
            "sha256": compute_sha256(_resolve(item["path"])),
        }
        for item in config["data"]["open_voltage_curves"]
    ]

    result_paths = [
        _resolve(config["outputs"]["jacobian_summary"]),
        _resolve(config["outputs"]["jacobian_spectra"]),
        _resolve(config["outputs"]["figure"]),
        _resolve(config["outputs"]["report"]),
    ]
    checks = {
        "base_snapshot_is_current_head": _git("rev-parse", "HEAD")
        == str(config["base_snapshot"]),
        "m36_failure_preserved": m36_summary["m36_primary_gates_pass"] is False,
        "m36_outputs_are_read_only_inputs": bool(
            config["historical_inputs"]["preserve_m36_outputs"]
        ),
        "m36_classifier_breadth_detected": bool(
            audit["broad_primary_failure_classifier_detected"]
        ),
        "semantic_audit_does_not_change_vote": bool(
            audit["source_m36_failure_vote_unchanged"]
        ),
        "semantic_audit_has_observed_trends": all(
            audit["voltage_audit"][key]["observed_convergence_trend"]
            for key in ("11", "15", "17")
        ),
        "open_voltages_exact": [row["voltage_V"] for row in open_records]
        == [9.0, 11.0, 15.0, 17.0],
        "withheld_13v_numeric_access_forbidden": config["data"]["withheld_13v"]
        ["numeric_access"]
        == "forbidden",
        "withheld_13v_path_absent": config["data"]["withheld_13v"]
        ["extracted_path"]
        is None,
        "sealed_13v_access_false": config["data"]["withheld_13v"]
        ["sealed_13v_access"]
        is False,
        "parameter_coordinates_exact": config["parameters"]["coordinate_names"]
        == ["log_C_th", "log_S_e"],
        "difference_steps_exact": config["parameters"]["relative_steps"]
        == [0.01, 0.005, 0.0025],
        "primary_solver_exact": config["solvers"]["primary_method"] == "DOP853",
        "independent_solver_exact": config["solvers"]["independent_method"]
        == "Radau",
        "radau_scope_limited": config["solvers"]["radau_scope"]
        == "nominal_and_finest_difference_scale_only",
        "observation_groups_exact": config["observations"]["groups"]
        == {
            "static_only": [9.0, 17.0],
            "oscillatory_only": [11.0, 15.0],
            "joint": [9.0, 11.0, 15.0, 17.0],
        },
        "relative_rank_threshold_exact": float(
            config["gates"]["relative_singular_value_rank_threshold"]
        )
        == 0.05,
        "joint_rank_exact": int(config["gates"]["joint_required_rank"]) == 2,
        "complementarity_angle_exact": float(
            config["gates"][
                "static_oscillatory_top_right_direction_angle_deg_min"
            ]
        )
        == 20.0,
        "no_fit_in_m37": config["budget"]["fitting"] == "forbidden",
        "cpu_budget_at_most_two_hours": float(
            config["budget"]["maximum_incremental_cpu_wall_hours"]
        )
        <= 2.0,
        "no_existing_result_outputs": not any(path.exists() for path in result_paths),
    }
    locked_paths = _locked_paths(config)
    missing = [path for path in locked_paths if not _resolve(path).exists()]
    checks["all_locked_files_exist"] = not missing
    locked_files = {
        path: compute_sha256(_resolve(path)) for path in locked_paths if _resolve(path).exists()
    }
    payload = {
        "schema_version": "m37_continuous_event_observability_preregistration_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": str(config["base_snapshot"]),
        "git_commit_before_preregistration": _git("rev-parse", "HEAD"),
        "git_dirty_before_preregistration": bool(_git("status", "--short")),
        "preflight_checks": checks,
        "all_preflight_checks_pass": bool(all(checks.values())),
        "missing_locked_files": missing,
        "locked_files": locked_files,
        "open_public_curve_records": open_records,
        "locked_whitening": whitening,
        "registered_parameter_coordinates": config["parameters"],
        "registered_observation_contract": config["observations"],
        "registered_gates": config["gates"],
        "registered_budget": config["budget"],
        "solver_authorized_after_preregistration_commit": bool(all(checks.values())),
        "solver_must_run_on_later_commit": True,
        "fit_authorized": False,
        "fit_lock_authorized": False,
        "pinn_training_authorized": False,
        "sealed_13v_access": False,
    }
    _write_json(_resolve(config["outputs"]["preregistration"]), payload)
    if not payload["all_preflight_checks_pass"]:
        raise RuntimeError(f"M37 preregistration failed: {checks}; missing={missing}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/m37_continuous_event_observability.yaml"),
    )
    args = parser.parse_args()
    payload = preregister(_resolve(args.config))
    print(
        json.dumps(
            {
                "all_preflight_checks_pass": payload["all_preflight_checks_pass"],
                "check_count": len(payload["preflight_checks"]),
                "locked_file_count": len(payload["locked_files"]),
                "sealed_13v_access": payload["sealed_13v_access"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

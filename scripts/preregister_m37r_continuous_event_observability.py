"""Create the M37R event-window repair preregistration and input hash lock."""

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
)
from pinnpcm.external_data.vo2_cross_regime_observability_repair import (
    EVENT_WINDOW_CONTRACT_ID,
    build_m36_reference_window_audit,
    run_mock_contract_pipeline,
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
            raise PermissionError("M37R preregistration attempted 13 V numeric access.")
        voltage = float(item["voltage_V"])
        observations[voltage] = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
    if sorted(observations) != [9.0, 11.0, 15.0, 17.0]:
        raise RuntimeError("M37R open observations must be exactly 9/11/15/17 V.")
    return observations


def _historical_read_only_paths() -> list[str]:
    tracked = _git("ls-files").splitlines()
    selected = [
        path
        for path in tracked
        if "m37r" not in path.casefold()
        and any(token in path.casefold() for token in ("m35", "m36", "m37"))
    ]
    selected.extend(
        [
            "src/pinnpcm/external_data/vo2_cross_regime_observability.py",
            "src/pinnpcm/external_data/vo2_orbit_convergence.py",
            "src/pinnpcm/external_data/vo2_orbit_fit.py",
            "src/pinnpcm/physics/vo2_event_resolved.py",
            "src/pinnpcm/physics/vo2_thermal_neuristor.py",
        ]
    )
    return sorted(set(selected))


def _locked_paths(config: Mapping[str, Any]) -> list[str]:
    paths = [
        "configs/m37r_continuous_event_observability_repair.yaml",
        "docs/schemas/m37r_continuous_event_observability_evidence_v1.schema.json",
        "src/pinnpcm/external_data/vo2_cross_regime_observability_repair.py",
        "scripts/preregister_m37r_continuous_event_observability.py",
        "scripts/run_m37r_continuous_event_observability.py",
        "tests/test_m37r_continuous_event_observability_repair.py",
        "tests/test_m37r_result_evidence.py",
        str(config["historical_inputs"]["m36_config"]),
        str(config["historical_inputs"]["m36_summary"]),
        str(config["historical_inputs"]["m36_metrics"]),
        str(config["historical_inputs"]["m36_event_times"]),
        str(config["historical_inputs"]["source_parameter_config"]),
    ]
    paths.extend(str(item["path"]) for item in config["data"]["open_voltage_curves"])
    paths.extend(_historical_read_only_paths())
    if len(paths) != len(set(paths)):
        paths = list(dict.fromkeys(paths))
    return paths


def preregister(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    m36_config = yaml.safe_load(
        _resolve(config["historical_inputs"]["m36_config"]).read_text(
            encoding="utf-8"
        )
    )
    m36_summary = json.loads(
        _resolve(config["historical_inputs"]["m36_summary"]).read_text(
            encoding="utf-8"
        )
    )
    m37_result = json.loads(
        _resolve(config["historical_inputs"]["m37_result"]).read_text(
            encoding="utf-8"
        )
    )
    observations = _load_observations(config)
    whitening = build_whitening_record(observations, m36_summary, config)
    expected_counts = {
        voltage: int(
            m36_summary["voltage_results"][f"{voltage:g}"][
                "reference_parity_metrics"
            ]["reference_reversal_event_count"]
        )
        for voltage in (9.0, 11.0, 15.0, 17.0)
    }
    with _resolve(config["historical_inputs"]["m36_event_times"]).open(
        encoding="utf-8", newline=""
    ) as handle:
        m36_event_rows = list(csv.DictReader(handle))
    m36_window_audit = build_m36_reference_window_audit(
        m36_event_rows,
        observations,
        expected_counts,
        transient_fraction=float(config["event_window"]["transient_fraction"]),
    )
    mock_pipeline = run_mock_contract_pipeline()
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
        _resolve(config["outputs"][key])
        for key in (
            "jacobian_summary",
            "jacobian_spectra",
            "event_window_audit",
            "figure",
            "report",
        )
    ]
    expected_regression = config["event_window"]["expected_nominal_counts"]
    checks = {
        "base_snapshot_is_current_head": _git("rev-parse", "HEAD")
        == str(config["base_snapshot"]),
        "worktree_has_only_preregistration_changes": bool(_git("status", "--short")),
        "m36_failure_preserved": m36_summary["m36_primary_gates_pass"] is False,
        "m37_failure_status_preserved": m37_result["status"]
        == "stopped_at_nominal_solver_event_gate",
        "m37_geometry_remains_unassessed": not bool(m37_result["groups"]),
        "historical_files_declared_read_only": bool(
            config["historical_inputs"]["preserve_m35_m36_m37_artifacts"]
        ),
        "m36_post_transient_reference_reproduced": bool(
            m36_window_audit["all_counts_match"]
        ),
        "expected_count_regression_exact": expected_regression
        == {
            "9": {"full_horizon": 0, "post_transient": 0},
            "11": {"full_horizon": 216, "post_transient": 196},
            "15": {"full_horizon": 381, "post_transient": 344},
            "17": {"full_horizon": 4, "post_transient": 0},
        },
        "event_window_contract_exact": config["event_window"]["contract_id"]
        == EVENT_WINDOW_CONTRACT_ID
        and float(config["event_window"]["transient_fraction"]) == 0.1
        and config["event_window"]["lower_boundary"] == "inclusive"
        and config["event_window"]["upper_boundary"] == "inclusive"
        and float(config["event_window"]["floating_tolerance_s"]) == 0.0,
        "parameters_exact": config["parameters"]["coordinate_names"]
        == ["log_C_th", "log_S_e"],
        "steps_exact": config["parameters"]["relative_steps"]
        == [0.01, 0.005, 0.0025],
        "groups_exact": config["observations"]["groups"]
        == {
            "static_only": [9.0, 17.0],
            "oscillatory_only": [11.0, 15.0],
            "joint": [9.0, 11.0, 15.0, 17.0],
        },
        "solvers_exact": config["solvers"]["primary_method"] == "DOP853"
        and config["solvers"]["independent_method"] == "Radau",
        "scientific_thresholds_unchanged": (
            float(config["gates"]["two_finest_white_jacobian_relative_change_max"])
            == 0.10
            and float(
                config["gates"][
                    "two_finest_retained_left_subspace_angle_deg_max"
                ]
            )
            == 10.0
            and float(config["gates"]["dop853_radau_column_direction_cosine_min"])
            == 0.99
            and float(
                config["gates"][
                    "dop853_radau_retained_singular_value_relative_difference_max"
                ]
            )
            == 0.10
            and float(config["gates"]["relative_singular_value_rank_threshold"])
            == 0.05
            and int(config["gates"]["joint_required_rank"]) == 2
            and float(config["gates"]["joint_retained_condition_number_max"])
            == 1.0e4
            and float(
                config["gates"][
                    "static_oscillatory_top_right_direction_angle_deg_min"
                ]
            )
            == 20.0
        ),
        "forward_budget_exact": int(
            config["solvers"]["maximum_total_forward_evaluations"]
        )
        == 72,
        "wall_budget_at_most_two_hours": float(
            config["budget"]["maximum_incremental_cpu_wall_hours"]
        )
        <= 2.0,
        "gpu_budget_zero": float(config["budget"]["gpu_hours"]) == 0.0,
        "no_fit_optimization_bootstrap_or_training": all(
            config["budget"][key] == "forbidden"
            for key in ("fitting", "optimization", "bootstrap", "pinn_training")
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
        "mock_end_to_end_contract_passes": bool(mock_pipeline["all_pass"]),
        "no_existing_m37r_result_outputs": not any(
            path.exists() for path in result_paths
        ),
    }
    locked_paths = _locked_paths(config)
    missing = [path for path in locked_paths if not _resolve(path).exists()]
    checks["all_locked_files_exist"] = not missing
    locked_files = {
        path: compute_sha256(_resolve(path))
        for path in locked_paths
        if _resolve(path).exists()
    }
    historical_paths = _historical_read_only_paths()
    historical_hashes = {
        path: compute_sha256(_resolve(path))
        for path in historical_paths
        if _resolve(path).exists()
    }
    payload = {
        "schema_version": "m37r_continuous_event_observability_preregistration_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": str(config["base_snapshot"]),
        "git_commit_before_preregistration": _git("rev-parse", "HEAD"),
        "git_dirty_before_preregistration": bool(_git("status", "--short")),
        "preflight_checks": checks,
        "all_preflight_checks_pass": bool(all(checks.values())),
        "missing_locked_files": missing,
        "locked_files": locked_files,
        "historical_read_only_files": historical_hashes,
        "original_m37_result_status": m37_result["status"],
        "open_public_curve_records": open_records,
        "locked_whitening": whitening,
        "m36_reference_window_audit": m36_window_audit,
        "mock_end_to_end_contract": mock_pipeline,
        "registered_parameter_coordinates": config["parameters"],
        "registered_event_window_contract": config["event_window"],
        "registered_observation_contract": config["observations"],
        "registered_gates": config["gates"],
        "registered_budget": config["budget"],
        "formal_result_paths_absent_at_lock": [
            str(path.relative_to(ROOT)).replace("\\", "/") for path in result_paths
        ],
        "solver_authorized_after_preregistration_commit": bool(all(checks.values())),
        "solver_must_run_on_later_clean_commit": True,
        "formal_execution_limit": 1,
        "fit_authorized": False,
        "fit_lock_authorized": False,
        "pinn_training_authorized": False,
        "m38_execution_authorized": False,
        "sealed_13v_access": False,
    }
    _write_json(_resolve(config["outputs"]["preregistration"]), payload)
    if not payload["all_preflight_checks_pass"]:
        raise RuntimeError(f"M37R preregistration failed: {checks}; missing={missing}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/m37r_continuous_event_observability_repair.yaml"),
    )
    args = parser.parse_args()
    payload = preregister(_resolve(args.config))
    print(
        json.dumps(
            {
                "all_preflight_checks_pass": payload["all_preflight_checks_pass"],
                "check_count": len(payload["preflight_checks"]),
                "locked_file_count": len(payload["locked_files"]),
                "historical_read_only_file_count": len(
                    payload["historical_read_only_files"]
                ),
                "mock_end_to_end_contract_pass": payload[
                    "mock_end_to_end_contract"
                ]["all_pass"],
                "sealed_13v_access": payload["sealed_13v_access"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

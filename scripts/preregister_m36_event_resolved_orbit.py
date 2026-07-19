"""Freeze M36 numerical and conditional-fit rules before any new simulation."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.external_data.vo2_multivoltage import preprocess_experiment
from pinnpcm.external_data.vo2_zhang import compute_sha256


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _locked_paths(config: Mapping[str, Any]) -> list[str]:
    paths = [
        "configs/m36_event_resolved_orbit_convergence.yaml",
        "docs/schemas/m36_event_resolved_orbit_evidence_v1.schema.json",
        "scripts/preregister_m36_event_resolved_orbit.py",
        "scripts/run_m36_event_resolved_orbit.py",
        "src/pinnpcm/physics/vo2_event_resolved.py",
        "src/pinnpcm/external_data/vo2_orbit_convergence.py",
        "src/pinnpcm/external_data/vo2_orbit_fit.py",
        "tests/test_m36_event_resolved_orbit.py",
        "tests/test_m36_result_evidence.py",
        "docs/codex_reports/m36_event_resolved_orbit_and_conditional_fit.md",
        ".gitignore",
        "configs/vo2_d0a_exact_source_v2.yaml",
        "src/pinnpcm/physics/vo2_thermal_neuristor.py",
        "src/pinnpcm/external_data/vo2_multivoltage.py",
    ]
    paths.extend(
        str(item["path"]) for item in config["historical_evidence_lock"].values() if isinstance(item, dict) and "path" in item
    )
    paths.extend(str(item["path"]) for item in config["data"]["open_voltage_curves"])
    return list(dict.fromkeys(path.replace("\\", "/") for path in paths))


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    if head != str(config["base_snapshot"]):
        raise RuntimeError(
            f"M36 preregistration requires base {config['base_snapshot']}; found {head}."
        )
    output = _resolve(config["outputs"]["preregistration"])
    if output.exists():
        raise RuntimeError("M36 preregistration already exists; it must never be overwritten.")

    historical_hash_checks: dict[str, bool] = {}
    for name, item in config["historical_evidence_lock"].items():
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = _resolve(item["path"])
        historical_hash_checks[name] = bool(
            path.exists() and compute_sha256(path) == str(item["sha256"]).upper()
        )

    open_records: list[dict[str, Any]] = []
    measured_sampling: list[float] = []
    measured_noise: dict[str, dict[str, float]] = {}
    for item in config["data"]["open_voltage_curves"]:
        path = _resolve(item["path"])
        normalized_name = path.name.casefold().replace("_", "").replace(" ", "")
        if "13v" in normalized_name:
            raise PermissionError("M36 open path attempted to access sealed 13 V data.")
        voltage = float(item["voltage_V"])
        trace = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
        dt = float(np.median(np.diff(trace["time_s"])))
        measured_sampling.append(dt)
        measured_noise[f"{voltage:g}"] = {
            "current_A": float(trace["current_noise_scale_A"]),
            "device_voltage_V": float(trace["device_voltage_noise_scale_V"]),
        }
        open_records.append(
            {
                "voltage_V": voltage,
                "regime": str(item["regime"]),
                "curve_id": str(item["curve_id"]),
                "path": _relative(path),
                "sha256": compute_sha256(path),
                "sample_interval_s": dt,
                "current_noise_floor_A": float(trace["current_noise_scale_A"]),
                "device_voltage_noise_floor_V": float(
                    trace["device_voltage_noise_scale_V"]
                ),
                "data_kind": "public_external_raw_with_preregistered_instrument_zeroing",
            }
        )

    locked_noise = config["data"]["locked_pretrigger_instrument_floors"]
    noise_exact = all(
        abs(measured_noise[key][quantity] - float(locked_noise[key][quantity])) <= 1.0e-15
        for key in measured_noise
        for quantity in ("current_A", "device_voltage_V")
    )
    sampling_exact = all(
        abs(value - float(config["data"]["locked_sampling_interval_s"])) <= 2.0e-13
        for value in measured_sampling
    )
    m35 = json.loads(
        _resolve(config["historical_evidence_lock"]["m35_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    d0a = json.loads(
        _resolve(
            config["historical_evidence_lock"]["d0a_source_reproduction"]["path"]
        ).read_text(encoding="utf-8")
    )
    fixed_steps = [float(value) for value in config["fixed_step_family"]["dt_values_s"]]
    reference = config["independent_reference"]
    folds = config["conditional_fit"]["folds"]
    open_voltages = [float(item["voltage_V"]) for item in config["data"]["open_voltage_curves"]]
    preflight = {
        "base_snapshot_exact": head == str(config["base_snapshot"]),
        "historical_artifact_hashes_exact": bool(
            historical_hash_checks and all(historical_hash_checks.values())
        ),
        "m35_solver_failure_preserved": m35.get("status")
        == "stopped_at_solver_convergence_gate"
        and m35.get("fit_executed") is False
        and m35.get("fit_lock_created") is False,
        "d0a_failure_preserved": d0a.get("gate_passed") is False
        and abs(
            float(d0a["source_si_metrics"]["medium_vs_fine_dt_current_nrmse95"])
            - float(config["historical_evidence_lock"]["preserve_d0a_current_nrmse95"])
        )
        <= 1.0e-15,
        "open_voltage_set_exact": open_voltages == [9.0, 11.0, 15.0, 17.0],
        "static_and_oscillatory_roles_exact": [
            str(item["regime"]) for item in config["data"]["open_voltage_curves"]
        ]
        == ["static", "oscillatory", "oscillatory", "static"],
        "no_open_path_mentions_13v": all(
            "13v" not in Path(item["path"]).name.casefold().replace("_", "").replace(" ", "")
            for item in config["data"]["open_voltage_curves"]
        ),
        "sealed_13v_metadata_only": config["data"]["withheld_13v"]["numeric_access"]
        == "forbidden"
        and config["data"]["withheld_13v"]["extracted_path"] is None
        and config["data"]["withheld_13v"]["sealed_13v_access"] is False,
        "sampling_interval_prelocked": sampling_exact,
        "instrument_noise_floors_prelocked": noise_exact,
        "fixed_step_family_exact": fixed_steps
        == [2.5e-9, 1.25e-9, 6.25e-10, 3.125e-10],
        "two_independent_methods_locked": reference["methods"] == ["DOP853", "Radau"],
        "solver_tolerances_locked": float(reference["rtol"]) > 0.0
        and float(reference["atol_voltage_V"]) > 0.0
        and float(reference["atol_temperature_K"]) > 0.0,
        "different_event_semantics_declared": config["source_model"]["semantics_are_identical"]
        is False
        and config["source_model"]["discrete_semantics_name"]
        != config["source_model"]["continuous_semantics_name"],
        "raw_full_horizon_is_diagnostic_only": config["diagnostic_only_gates"][
            "full_horizon_raw_time_failure_alone_is_not_primary_failure"
        ]
        is True,
        "dtw_and_primary_global_shift_forbidden": config["event_metrics"]["dtw"]
        == "forbidden"
        and config["event_metrics"]["global_phase_shift"]
        == "forbidden_for_primary_gate",
        "four_lovo_folds_and_eight_starts_locked": len(folds) == 4
        and all(
            sorted(
                [float(value) for value in fold["fit_voltages_V"]]
                + [float(fold["holdout_voltage_V"])]
            )
            == open_voltages
            for fold in folds
        )
        and len(config["conditional_fit"]["deterministic_start_offsets"]) == 8,
        "equal_objective_budget_locked": config["conditional_fit"][
            "equal_forward_budget_required"
        ]
        is True,
        "pinn_and_gpu_work_absent": int(config["budget"]["gpu_hours"]) == 0,
        "conditional_outputs_absent": all(
            not _resolve(config["outputs"][name]).exists()
            for name in (
                "summary",
                "jacobian_summary",
                "fit_starts",
                "fit_metrics",
                "fit_lock",
            )
        ),
    }
    locked_paths = _locked_paths(config)
    missing = [path for path in locked_paths if not (ROOT / path).exists()]
    if missing:
        raise FileNotFoundError(f"Missing M36 locked files: {missing}")
    all_pass = bool(preflight and all(preflight.values()))
    payload = {
        "schema_version": "m36_event_resolved_orbit_preregistration_v1",
        "stage_id": config["stage_id"],
        "base_snapshot": head,
        "status": "locked_before_m36_solver_execution"
        if all_pass
        else "failed_but_informative",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_question": (
            "Do sampled Euler solutions converge to a separately labelled, root-located "
            "hybrid reference in static observables and limit-cycle orbit coordinates?"
        ),
        "config_sha256": compute_sha256(config_path),
        "open_public_curve_records": open_records,
        "historical_hash_checks": historical_hash_checks,
        "locked_files": {path: compute_sha256(ROOT / path) for path in locked_paths},
        "thresholds": {
            "reference_parity": config["reference_parity_gates"],
            "static_primary": config["static_primary_gates"],
            "oscillatory_primary": config["oscillatory_primary_gates"],
            "sequence_convergence": config["sequence_convergence_gates"],
            "diagnostic_only": config["diagnostic_only_gates"],
            "conditional_jacobian": config["conditional_jacobian"],
            "conditional_fit": config["conditional_fit"],
        },
        "preflight_checks": preflight,
        "all_preflight_checks_pass": all_pass,
        "solver_authorized_after_preregistration_commit": all_pass,
        "conditional_continuation_authorized_without_second_user_confirmation": all_pass,
        "solver_must_run_on_later_commit": True,
        "sealed_13v_access": False,
        "pinn_training_performed": False,
        "forbidden_claims": config["claim_boundary"]["forbidden"],
    }
    _write_json(output, payload)
    if not all_pass:
        raise RuntimeError("M36 preregistration failed one or more preflight checks.")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/m36_event_resolved_orbit_convergence.yaml"),
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

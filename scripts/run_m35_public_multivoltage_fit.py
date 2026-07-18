"""Run the fail-closed M35 convergence, Jacobian, and open-voltage LOVO fit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import scipy
import yaml

from pinnpcm.external_data.vo2_multivoltage import (
    ForwardCache,
    coordinate_dispersion,
    jacobian_stability_audit,
    preprocess_experiment,
    rt_sanity_metric,
    run_multistart_job,
    solver_convergence_audit,
)
from pinnpcm.external_data.vo2_zhang import compute_sha256
from pinnpcm.physics.vo2_thermal_neuristor import VO2ThermalNeuristorParameters


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


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.floating, float)):
        result = float(value)
        return result if np.isfinite(result) else None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _jsonable(row.get(key)) for key in fields})


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _jsonable(dict(payload)), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _verify_preregistration(config: Mapping[str, Any]) -> dict[str, Any]:
    path = _resolve(config["outputs"]["preregistration"])
    if not path.exists():
        raise RuntimeError("M35 fitting is forbidden before the preregistration exists.")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    if prereg.get("fit_authorized_after_preregistration_commit") is not True:
        raise RuntimeError("M35 preregistration did not authorize the bounded fit.")
    if prereg.get("sealed_13v_access") is not False:
        raise RuntimeError("M35 preregistration violated the sealed 13 V boundary.")
    head = _git("rev-parse", "HEAD")
    if head == str(config["base_snapshot"]):
        raise RuntimeError("D-FIT must run only after the preregistration commit.")
    mismatches = {
        name: {"expected": expected, "actual": compute_sha256(ROOT / name)}
        for name, expected in prereg["locked_files"].items()
        if not (ROOT / name).exists() or compute_sha256(ROOT / name) != expected
    }
    if mismatches:
        raise RuntimeError(f"M35 locked-file mismatch: {mismatches}")
    provenance = _resolve(prereg["provenance_manifest"])
    if compute_sha256(provenance) != prereg["provenance_manifest_sha256"]:
        raise RuntimeError("M35 provenance manifest changed after preregistration.")
    return prereg


def _assert_expected_dirty_state(config: Mapping[str, Any]) -> None:
    allowed = {
        config["outputs"]["m34a_summary"].replace("\\", "/"),
        config["outputs"]["m34a_directions"].replace("\\", "/"),
    }
    unexpected: list[str] = []
    for line in _git("status", "--porcelain").splitlines():
        path = line[3:].strip().replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path not in allowed:
            unexpected.append(line)
    if unexpected:
        raise RuntimeError(
            "D-FIT found uncommitted changes outside the expected M34-A outputs: "
            + repr(unexpected)
        )


def _load_open_observations(config: Mapping[str, Any]) -> dict[float, dict[str, Any]]:
    observations: dict[float, dict[str, Any]] = {}
    for spec in config["data"]["open_voltage_curves"]:
        path = _resolve(spec["path"])
        normalized = path.name.casefold().replace("_", "").replace(" ", "")
        if "13v" in normalized:
            raise PermissionError("13 V numeric access is forbidden in M35.")
        voltage = float(spec["voltage_V"])
        observations[voltage] = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
    if sorted(observations) != [9.0, 11.0, 15.0, 17.0]:
        raise RuntimeError("M35 open observation set is not exactly 9/11/15/17 V.")
    return observations


def _machine_summary() -> dict[str, Any]:
    return {
        "device": "cpu",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def _initial_summary(
    *, config: Mapping[str, Any], prereg: Mapping[str, Any], started_at: str
) -> dict[str, Any]:
    return {
        "schema_version": "m35_public_multivoltage_fit_evidence_v1",
        "stage_id": config["stage_id"],
        "started_at_utc": started_at,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty_expected_m34a_only": True,
        "preregistration_path": config["outputs"]["preregistration"],
        "preregistration_sha256": compute_sha256(
            _resolve(config["outputs"]["preregistration"])
        ),
        "provenance_manifest_sha256": prereg["provenance_manifest_sha256"],
        "machine_summary": _machine_summary(),
        "evidence_semantics": config["evidence_semantics"],
        "fit_data_voltages_V": [9.0, 11.0, 15.0, 17.0],
        "sealed_13v_access": False,
        "pinn_training_performed": False,
        "m34_corrected_training_authorized": False,
        "claim_status": "failed_but_informative",
    }


def _aggregate_fit(
    config: Mapping[str, Any],
    starts: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gates = config["fit_gates"]
    systems: dict[str, Any] = {}
    for system in config["fit"]["coordinate_systems"]:
        system_starts = [row for row in starts if row["coordinate_system"] == system]
        fold_checks: dict[str, Any] = {}
        holdout_rows: list[Mapping[str, Any]] = []
        for fold in config["fit"]["folds"]:
            fold_id = str(fold["fold_id"])
            finite = [
                row
                for row in system_starts
                if row["job_id"] == fold_id and bool(row["finite"])
            ]
            fold_metrics = [
                row
                for row in metrics
                if row["coordinate_system"] == system
                and row["job_id"] == fold_id
                and row["role"] == "holdout"
            ]
            holdout_rows.extend(fold_metrics)
            fold_checks[fold_id] = {
                "finite_start_count": len(finite),
                "required_finite_start_count": int(
                    gates["minimum_finite_optimizer_starts_per_fold"]
                ),
                "finite_start_gate": len(finite)
                >= int(gates["minimum_finite_optimizer_starts_per_fold"]),
                "all_start_holdout_rows_reported": len(fold_metrics)
                == len(config["fit"]["deterministic_start_offsets"]),
            }
        nrmse = [float(row["combined_nrmse95"]) for row in holdout_rows]
        activity = [bool(row["activity_class_match"]) for row in holdout_rows]
        median_nrmse = float(np.median(nrmse)) if nrmse else float("inf")
        activity_accuracy = float(np.mean(activity)) if activity else 0.0
        dispersion = coordinate_dispersion(system_starts, coordinate_system=system)
        systems[system] = {
            "folds": fold_checks,
            "all_finite_start_gates_pass": bool(
                fold_checks
                and all(value["finite_start_gate"] for value in fold_checks.values())
            ),
            "all_holdout_rows_reported": bool(
                fold_checks
                and all(
                    value["all_start_holdout_rows_reported"]
                    for value in fold_checks.values()
                )
            ),
            "holdout_row_count": len(holdout_rows),
            "median_full_trace_combined_nrmse95": median_nrmse,
            "maximum_full_trace_combined_nrmse95": max(nrmse) if nrmse else float("inf"),
            "activity_class_accuracy": activity_accuracy,
            "operational_nrmse_gate": median_nrmse
            <= float(gates["repository_operational_holdout_combined_nrmse95_max"]),
            "activity_gate": activity_accuracy
            >= float(gates["activity_class_accuracy_min"]),
            "coordinate_dispersion": dispersion,
        }

    raw = systems["raw_Cth_Sth"]
    quotient = systems["quotient_tau_th_Sth"]
    raw_dispersion = float(
        raw["coordinate_dispersion"]["median_max_log_coordinate_std"]
    )
    quotient_dispersion = float(
        quotient["coordinate_dispersion"]["median_max_log_coordinate_std"]
    )
    improvement = (
        (raw_dispersion - quotient_dispersion) / raw_dispersion
        if raw_dispersion > 0.0 and np.isfinite(raw_dispersion)
        else float("-inf")
    )
    comparison = {
        "quotient_noninferior_nrmse": float(
            quotient["median_full_trace_combined_nrmse95"]
        )
        <= float(raw["median_full_trace_combined_nrmse95"])
        + float(gates["quotient_noninferiority_nrmse_margin"]),
        "quotient_log_dispersion_improvement_fraction": improvement,
        "quotient_dispersion_improvement_gate": improvement
        >= float(gates["quotient_log_dispersion_improvement_fraction_min"]),
    }
    all_complete = bool(
        all(
            value["all_finite_start_gates_pass"]
            and value["all_holdout_rows_reported"]
            for value in systems.values()
        )
    )
    mainline = bool(
        all_complete
        and quotient["operational_nrmse_gate"]
        and quotient["activity_gate"]
        and comparison["quotient_noninferior_nrmse"]
        and comparison["quotient_dispersion_improvement_gate"]
    )
    return {
        "coordinate_systems": systems,
        "comparison": comparison,
        "all_multistart_and_lovo_outputs_complete": all_complete,
        "quotient_mainline_gate_passed": mainline,
        "claim_status": "qualified_supported" if mainline else "failed_but_informative",
        "operational_nrmse_gate_is_repository_defined_not_domain_standard": True,
    }


def _write_fit_lock(
    *,
    config: Mapping[str, Any],
    prereg: Mapping[str, Any],
    summary: Mapping[str, Any],
    start_rows: Sequence[Mapping[str, Any]],
    metrics_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    starts_path = _resolve(config["outputs"]["all_multistarts"])
    metrics_path = _resolve(config["outputs"]["lovo_metrics"])
    fit_data_hashes = {
        str(item["curve_id"]): compute_sha256(_resolve(item["path"]))
        for item in config["data"]["open_voltage_curves"]
    }
    fit_data_hashes[str(config["data"]["rt"]["curve_id"])] = compute_sha256(
        _resolve(config["data"]["rt"]["path"])
    )
    payload: dict[str, Any] = {
        "schema_version": "m35_public_multivoltage_fit_lock_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "config_path": "configs/m35_public_multivoltage_fit.yaml",
        "config_sha256": compute_sha256(ROOT / "configs/m35_public_multivoltage_fit.yaml"),
        "preregistration_sha256": compute_sha256(
            _resolve(config["outputs"]["preregistration"])
        ),
        "provenance_manifest_sha256": prereg["provenance_manifest_sha256"],
        "fit_data_sha256": fit_data_hashes,
        "fit_data_voltages_V": [9.0, 11.0, 15.0, 17.0],
        "preprocessing": config["preprocessing"],
        "metrics": {
            "full_trace": [
                "current_nrmse95",
                "device_voltage_nrmse95",
                "combined_nrmse95",
            ],
            "events_and_qoi": [
                "activity_class",
                "spike_count",
                "frequency",
                "peak_amplitude",
                "onset",
                "duty_cycle",
                "charge",
                "energy",
            ],
        },
        "thresholds": {
            "solver_convergence": config["solver_convergence"],
            "jacobian_audit": config["jacobian_audit"],
            "fit_gates": config["fit_gates"],
        },
        "optimizer": config["fit"],
        "all_start_results": {
            "path": _relative(starts_path),
            "sha256": compute_sha256(starts_path),
            "row_count": len(start_rows),
            "best_start_only_reporting": False,
        },
        "all_trace_metrics": {
            "path": _relative(metrics_path),
            "sha256": compute_sha256(metrics_path),
            "row_count": len(metrics_rows),
        },
        "scientific_gate": summary["fit_result"],
        "sealed_13v_access": False,
        "future_13v_requires_new_explicit_user_authorization": True,
        "independent_external_validation": False,
        "unique_raw_parameter_recovery_claim": False,
    }
    payload["fit_lock_sha256"] = _canonical_hash(payload)
    _write_json(_resolve(config["outputs"]["fit_lock"]), payload)
    return payload


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    _assert_expected_dirty_state(config)
    prereg = _verify_preregistration(config)
    m34a_path = _resolve(config["outputs"]["m34a_summary"])
    if not m34a_path.exists():
        raise RuntimeError("Run the diagnostic-only M34-A amendment before D-FIT.")
    m34a = json.loads(m34a_path.read_text(encoding="utf-8"))
    if m34a.get("training_authorized") is not False or m34a.get("sealed_13v_access") is not False:
        raise RuntimeError("M34-A violated its training or sealed-data boundary.")

    started_clock = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    summary = _initial_summary(config=config, prereg=prereg, started_at=started_at)
    observations = _load_open_observations(config)
    source_config = yaml.safe_load(
        _resolve(config["source_model"]["source_config"]).read_text(encoding="utf-8")
    )
    base = VO2ThermalNeuristorParameters.from_config(source_config)
    cache = ForwardCache(
        maximum_evaluations=int(config["fit"]["maximum_forward_evaluations"])
    )
    summary["rt_constitutive_sanity"] = rt_sanity_metric(
        base, _resolve(config["data"]["rt"]["path"])
    )

    convergence_rows, convergence = solver_convergence_audit(
        base,
        observations,
        config["solver_convergence"],
        config["event_metrics"],
        cache,
    )
    _write_csv(_resolve(config["outputs"]["solver_convergence"]), convergence_rows)
    summary["solver_convergence"] = convergence
    if not convergence["all_operational_gates_pass"]:
        summary.update(
            {
                "status": "stopped_at_solver_convergence_gate",
                "failure_reason": "The preregistered open-voltage time-step convergence gate failed.",
                "fit_executed": False,
                "fit_lock_created": False,
                "forward_evaluations": cache.forward_evaluations,
                "elapsed_seconds": time.perf_counter() - started_clock,
                "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        _write_json(_resolve(config["outputs"]["fit_summary"]), summary)
        return summary

    spectra_rows, jacobian = jacobian_stability_audit(
        base,
        observations,
        config["jacobian_audit"],
        dt_s=float(config["solver_convergence"]["fit_dt_s"]),
        cache=cache,
    )
    _write_csv(_resolve(config["outputs"]["jacobian_spectra"]), spectra_rows)
    _write_json(_resolve(config["outputs"]["jacobian_summary"]), jacobian)
    summary["jacobian_audit"] = jacobian
    if not jacobian["all_coordinate_systems_stable"]:
        summary.update(
            {
                "status": "stopped_at_prefit_jacobian_gate",
                "failure_reason": "At least one preregistered coordinate system failed the numerical Jacobian stability/rank gate.",
                "fit_executed": False,
                "fit_lock_created": False,
                "forward_evaluations": cache.forward_evaluations,
                "elapsed_seconds": time.perf_counter() - started_clock,
                "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        _write_json(_resolve(config["outputs"]["fit_summary"]), summary)
        return summary

    jobs = [
        (str(fold["fold_id"]), [float(value) for value in fold["fit_voltages_V"]])
        for fold in config["fit"]["folds"]
    ]
    if config["fit"]["include_all_open_voltage_final_fit"]:
        jobs.append(("all_open_final", sorted(observations)))
    start_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    for job_id, fit_voltages in jobs:
        for system in config["fit"]["coordinate_systems"]:
            for start_id, offset in enumerate(config["fit"]["deterministic_start_offsets"]):
                start_row, trace_rows = run_multistart_job(
                    job_id=job_id,
                    coordinate_system=str(system),
                    fit_voltages=fit_voltages,
                    observations=observations,
                    base=base,
                    fit_config=config["fit"],
                    preprocessing=config["preprocessing"],
                    event_config=config["event_metrics"],
                    start_id=start_id,
                    start_offset=offset,
                    dt_s=float(config["solver_convergence"]["fit_dt_s"]),
                    cache=cache,
                    task_started=started_clock,
                )
                start_rows.append(start_row)
                metrics_rows.extend(trace_rows)

    _write_csv(_resolve(config["outputs"]["all_multistarts"]), start_rows)
    _write_csv(_resolve(config["outputs"]["lovo_metrics"]), metrics_rows)
    fit_result = _aggregate_fit(config, start_rows, metrics_rows)
    expected_starts = len(jobs) * len(config["fit"]["coordinate_systems"]) * len(
        config["fit"]["deterministic_start_offsets"]
    )
    expected_metrics = expected_starts * len(observations)
    complete = len(start_rows) == expected_starts and len(metrics_rows) == expected_metrics
    summary.update(
        {
            "status": "completed_open_voltage_fit",
            "fit_executed": True,
            "fit_result": fit_result,
            "all_start_result_count": len(start_rows),
            "expected_all_start_result_count": expected_starts,
            "all_trace_metric_count": len(metrics_rows),
            "expected_all_trace_metric_count": expected_metrics,
            "all_outputs_complete": complete,
            "forward_evaluations": cache.forward_evaluations,
            "forward_evaluation_budget": int(config["fit"]["maximum_forward_evaluations"]),
            "elapsed_seconds": time.perf_counter() - started_clock,
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            "claim_status": fit_result["claim_status"],
            "failure_reason": None
            if fit_result["quotient_mainline_gate_passed"]
            else "The quotient mainline gate failed; retain the result as a bounded calibration/identifiability boundary.",
            "fit_lock_created": complete,
        }
    )
    _write_json(_resolve(config["outputs"]["fit_summary"]), summary)
    if complete:
        lock = _write_fit_lock(
            config=config,
            prereg=prereg,
            summary=summary,
            start_rows=start_rows,
            metrics_rows=metrics_rows,
        )
        summary["fit_lock_sha256"] = lock["fit_lock_sha256"]
        _write_json(_resolve(config["outputs"]["fit_summary"]), summary)
    return summary


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
                "claim_status": result["claim_status"],
                "fit_executed": result["fit_executed"],
                "fit_lock_created": result["fit_lock_created"],
                "sealed_13v_access": False,
            },
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()

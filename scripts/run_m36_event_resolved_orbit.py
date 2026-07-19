"""Run M36 and conditionally continue to event-aware Jacobian and LOVO fit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml

from pinnpcm.external_data.vo2_multivoltage import preprocess_experiment
from pinnpcm.external_data.vo2_orbit_convergence import (
    compare_solver_results,
    convergence_loglog_slope,
    cycle_energy_ledger,
    normalized_primary_score,
)
from pinnpcm.external_data.vo2_orbit_fit import (
    EventForwardCache,
    aggregate_conditional_fit,
    event_aware_jacobian_audit,
    run_fit_start,
)
from pinnpcm.external_data.vo2_zhang import compute_sha256
from pinnpcm.physics.vo2_event_resolved import (
    EventResolvedResult,
    event_sequence_signature,
    simulate_event_resolved_si,
    simulate_source_compatible_family_member,
)
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
        return _jsonable(value.tolist())
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
        raise ValueError(f"Refusing to write empty M36 CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
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
        raise RuntimeError("M36 cannot run before its immutable preregistration exists.")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    if prereg.get("solver_authorized_after_preregistration_commit") is not True:
        raise RuntimeError("M36 preregistration did not authorize solver execution.")
    if prereg.get("sealed_13v_access") is not False:
        raise RuntimeError("M36 preregistration violated the 13 V seal.")
    head = _git("rev-parse", "HEAD")
    if head == str(config["base_snapshot"]):
        raise RuntimeError("M36 solver execution must occur after the preregistration commit.")
    mismatches = {
        name: {"expected": expected, "actual": compute_sha256(ROOT / name)}
        for name, expected in prereg["locked_files"].items()
        if not (ROOT / name).exists() or compute_sha256(ROOT / name) != expected
    }
    if mismatches:
        raise RuntimeError(f"M36 locked-file mismatch: {mismatches}")
    return prereg


def _load_open_observations(
    config: Mapping[str, Any], prereg: Mapping[str, Any]
) -> tuple[dict[float, dict[str, Any]], dict[float, str]]:
    observations: dict[float, dict[str, Any]] = {}
    regimes: dict[float, str] = {}
    prereg_hashes = {
        float(row["voltage_V"]): str(row["sha256"]).upper()
        for row in prereg["open_public_curve_records"]
    }
    for item in config["data"]["open_voltage_curves"]:
        path = _resolve(item["path"])
        normalized = path.name.casefold().replace("_", "").replace(" ", "")
        if "13v" in normalized:
            raise PermissionError("M36 attempted sealed 13 V numeric access.")
        voltage = float(item["voltage_V"])
        if compute_sha256(path) != prereg_hashes[voltage]:
            raise RuntimeError(f"Open {voltage:g} V curve changed after preregistration.")
        observations[voltage] = preprocess_experiment(
            path,
            voltage_V=voltage,
            current_sense_ohm=float(config["data"]["current_sense_ohm"]),
        )
        regimes[voltage] = str(item["regime"])
    if sorted(observations) != [9.0, 11.0, 15.0, 17.0]:
        raise RuntimeError("M36 open observation set is not exactly 9/11/15/17 V.")
    return observations, regimes


def _finite_le(value: Any, threshold: float) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return bool(math.isfinite(number) and abs(number) <= float(threshold))


def _reference_gate(
    metrics: Mapping[str, Any],
    *,
    regime: str,
    gates: Mapping[str, Any],
    sequence_exact: bool,
    dop_ledger: Mapping[str, Any] | None,
) -> tuple[bool, dict[str, bool]]:
    checks = {
        "event_sequence": bool(sequence_exact),
        "current_absolute_rmse": _finite_le(
            metrics["current_absolute_rmse_noise_fraction"],
            float(gates["current_absolute_rmse_noise_fraction_max"]),
        ),
        "voltage_absolute_rmse": _finite_le(
            metrics["voltage_absolute_rmse_noise_fraction"],
            float(gates["voltage_absolute_rmse_noise_fraction_max"]),
        ),
    }
    if regime == "oscillatory":
        checks.update(
            {
                "reversal_count": bool(metrics["reversal_event_count_exact"]),
                "reversal_time": _finite_le(
                    metrics["maximum_event_time_error_s"],
                    float(gates["maximum_reversal_event_time_error_s"]),
                ),
                "cycle_shape": _finite_le(
                    metrics["cycle_shape_combined_nrmse95"],
                    float(gates["cycle_shape_nrmse_max"]),
                ),
                "period": _finite_le(
                    metrics["period_relative_error"],
                    float(gates["period_relative_error_max"]),
                ),
                "charge": _finite_le(
                    metrics["cycle_charge_relative_error"],
                    float(gates["charge_relative_error_max"]),
                ),
                "energy": _finite_le(
                    metrics["cycle_energy_relative_error"],
                    float(gates["energy_relative_error_max"]),
                ),
                "radau_ledger": _finite_le(
                    metrics["cycle_ledger_relative_residual"],
                    float(gates["reference_cycle_ledger_relative_residual_max"]),
                ),
                "dop853_ledger": bool(
                    dop_ledger
                    and _finite_le(
                        dop_ledger["cycle_ledger_relative_residual"],
                        float(gates["reference_cycle_ledger_relative_residual_max"]),
                    )
                ),
            }
        )
    else:
        checks.update(
            {
                "charge": _finite_le(
                    metrics["charge_relative_error"],
                    float(gates["charge_relative_error_max"]),
                ),
                "energy": _finite_le(
                    metrics["energy_relative_error"],
                    float(gates["energy_relative_error_max"]),
                ),
            }
        )
    return bool(all(checks.values())), checks


def _primary_checks(
    metrics: Mapping[str, Any], *, regime: str, gates: Mapping[str, Any]
) -> dict[str, bool]:
    if regime == "static":
        return {
            "current_rmse": _finite_le(
                metrics["current_absolute_rmse_noise_fraction"],
                float(gates["current_absolute_rmse_noise_fraction_max"]),
            ),
            "current_max": _finite_le(
                metrics["current_max_error_noise_fraction"],
                float(gates["current_max_error_noise_fraction_max"]),
            ),
            "voltage_rmse": _finite_le(
                metrics["voltage_absolute_rmse_noise_fraction"],
                float(gates["voltage_absolute_rmse_noise_fraction_max"]),
            ),
            "voltage_max": _finite_le(
                metrics["voltage_max_error_noise_fraction"],
                float(gates["voltage_max_error_noise_fraction_max"]),
            ),
            "steady_current": _finite_le(
                metrics["steady_current_error_noise_fraction"],
                float(gates["steady_current_error_noise_fraction_max"]),
            ),
            "steady_voltage": _finite_le(
                metrics["steady_voltage_error_noise_fraction"],
                float(gates["steady_voltage_error_noise_fraction_max"]),
            ),
            "activity": bool(metrics["activity_class_match"]),
            "charge": _finite_le(
                metrics["charge_relative_error"], float(gates["charge_relative_error_max"])
            ),
            "energy": _finite_le(
                metrics["energy_relative_error"], float(gates["energy_relative_error_max"])
            ),
        }
    return {
        "activity": bool(metrics["activity_class_match"]),
        "reversal_count": bool(metrics["reversal_event_count_exact"]),
        "reversal_type_sequence": bool(metrics["reversal_event_type_sequence_exact"]),
        "period": _finite_le(
            metrics["period_relative_error"], float(gates["period_relative_error_max"])
        ),
        "frequency": _finite_le(
            metrics["frequency_relative_error"],
            float(gates["frequency_relative_error_max"]),
        ),
        "event_time": _finite_le(
            metrics["maximum_event_time_error_s"],
            float(gates["maximum_event_time_error_s"]),
        ),
        "phase_drift": _finite_le(
            metrics["phase_drift_s_per_event"],
            float(gates["phase_drift_s_per_event_max"]),
        ),
        "cycle_shape": _finite_le(
            metrics["cycle_shape_combined_nrmse95"],
            float(gates["cycle_shape_nrmse_max"]),
        ),
        "peak": _finite_le(
            metrics["cycle_peak_relative_error"],
            float(gates["peak_relative_error_max"]),
        ),
        "duty": _finite_le(
            metrics["cycle_duty_cycle_absolute_error"],
            float(gates["duty_cycle_absolute_error_max"]),
        ),
        "cycle_charge": _finite_le(
            metrics["cycle_charge_relative_error"],
            float(gates["cycle_charge_relative_error_max"]),
        ),
        "cycle_energy": _finite_le(
            metrics["cycle_energy_relative_error"],
            float(gates["cycle_energy_relative_error_max"]),
        ),
        "cycle_ledger": _finite_le(
            metrics["cycle_ledger_relative_residual"],
            float(gates["cycle_ledger_relative_residual_max"]),
        ),
        "short_current": _finite_le(
            metrics["short_raw_current_nrmse95"],
            float(gates["short_raw_current_nrmse95_max"]),
        ),
        "short_voltage": _finite_le(
            metrics["short_raw_voltage_nrmse95"],
            float(gates["short_raw_voltage_nrmse95_max"]),
        ),
    }


def _make_figures(
    config: Mapping[str, Any],
    metric_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    references: Mapping[float, EventResolvedResult],
    finest: Mapping[float, EventResolvedResult],
) -> None:
    plt.figure(figsize=(7.2, 4.6))
    for voltage in (9.0, 11.0, 15.0, 17.0):
        rows = [
            row
            for row in metric_rows
            if float(row["voltage_V"]) == voltage
            and str(row["candidate"]).startswith("Euler_dt_")
        ]
        rows.sort(key=lambda row: float(row["dt_s"]), reverse=True)
        plt.loglog(
            [float(row["dt_s"]) for row in rows],
            [float(row["normalized_primary_score"]) for row in rows],
            marker="o",
            label=f"{voltage:g} V",
        )
    plt.axhline(1.0, color="black", linestyle="--", linewidth=1.0, label="primary gate")
    plt.xlabel("Euler time step (s)")
    plt.ylabel("maximum normalized primary error")
    plt.title("M36 fixed-step convergence toward DOP853 reference")
    plt.legend(ncol=2)
    plt.tight_layout()
    path = _resolve(config["outputs"]["figure_convergence"])
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=180)
    plt.close()

    plt.figure(figsize=(7.2, 4.6))
    for voltage in (11.0, 15.0):
        rows = [
            row
            for row in event_rows
            if float(row["voltage_V"]) == voltage
            and str(row["candidate"]).endswith("3.125e-10s")
        ]
        plt.plot(
            [int(row["event_index"]) for row in rows],
            [1.0e9 * float(row["event_time_error_s"]) for row in rows],
            label=f"{voltage:g} V finest Euler",
        )
    plt.xlabel("fixed reversal-event index")
    plt.ylabel("event-time error (ns)")
    plt.title("M36 event-time drift without DTW")
    plt.legend()
    plt.tight_layout()
    plt.savefig(_resolve(config["outputs"]["figure_event_drift"]), dpi=180)
    plt.close()

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.8), sharey=False)
    phase = np.linspace(0.0, 1.0, 128)
    for axis, voltage in zip(axes, (11.0, 15.0)):
        reference = references[voltage]
        candidate = finest[voltage]
        r_anchors = np.asarray(
            [
                float(row["time_s"])
                for row in reference.event_records
                if row["event_type"] == "reversal_to_cooling"
                and float(row["time_s"]) >= 0.1 * reference.trace.time_s[-1]
            ]
        )
        c_anchors = np.asarray(
            [
                float(row["time_s"])
                for row in candidate.event_records
                if row["event_type"] == "reversal_to_cooling"
                and float(row["time_s"]) >= 0.1 * candidate.trace.time_s[-1]
            ]
        )
        if r_anchors.size >= 2 and c_anchors.size >= 2:
            r_time = r_anchors[-2] + phase * (r_anchors[-1] - r_anchors[-2])
            c_time = c_anchors[-2] + phase * (c_anchors[-1] - c_anchors[-2])
            axis.plot(
                phase,
                np.interp(r_time, reference.trace.time_s, reference.trace.current_A),
                label="DOP853",
            )
            axis.plot(
                phase,
                np.interp(c_time, candidate.trace.time_s, candidate.trace.current_A),
                linestyle="--",
                label="finest Euler",
            )
        axis.set_title(f"{voltage:g} V")
        axis.set_xlabel("linear cycle phase")
    axes[0].set_ylabel("device current (A)")
    axes[1].legend()
    fig.suptitle("Phase-normalized cycle overlay (diagnostic, no DTW)")
    fig.tight_layout()
    fig.savefig(_resolve(config["outputs"]["figure_cycle_overlay"]), dpi=180)
    plt.close(fig)

    static_rows = [
        row
        for row in metric_rows
        if float(row["voltage_V"]) in (9.0, 17.0)
        and str(row["candidate"]).endswith("3.125e-10s")
    ]
    labels = [f"{float(row['voltage_V']):g} V" for row in static_rows]
    x = np.arange(len(labels))
    width = 0.35
    plt.figure(figsize=(6.2, 4.2))
    plt.bar(
        x - width / 2,
        [float(row["current_absolute_rmse_noise_fraction"]) for row in static_rows],
        width,
        label="current RMSE / noise",
    )
    plt.bar(
        x + width / 2,
        [float(row["voltage_absolute_rmse_noise_fraction"]) for row in static_rows],
        width,
        label="voltage RMSE / noise",
    )
    plt.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    plt.xticks(x, labels)
    plt.ylabel("absolute error normalized by locked noise floor")
    plt.title("Static-branch absolute convergence metric")
    plt.legend()
    plt.tight_layout()
    plt.savefig(_resolve(config["outputs"]["figure_static_absolute"]), dpi=180)
    plt.close()


def _write_fit_lock(
    config: Mapping[str, Any],
    prereg: Mapping[str, Any],
    fit_result: Mapping[str, Any],
    starts_path: Path,
    metrics_path: Path,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "m36_public_multivoltage_fit_lock_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "config_path": "configs/m36_event_resolved_orbit_convergence.yaml",
        "config_sha256": compute_sha256(
            ROOT / "configs/m36_event_resolved_orbit_convergence.yaml"
        ),
        "preregistration_sha256": compute_sha256(
            _resolve(config["outputs"]["preregistration"])
        ),
        "fit_data_voltages_V": [9.0, 11.0, 15.0, 17.0],
        "fit_data_hashes": {
            str(row["curve_id"]): str(row["sha256"])
            for row in prereg["open_public_curve_records"]
        },
        "solver_semantics": config["source_model"],
        "numerical_thresholds": {
            "reference_parity": config["reference_parity_gates"],
            "static": config["static_primary_gates"],
            "oscillatory": config["oscillatory_primary_gates"],
            "jacobian": config["conditional_jacobian"],
        },
        "optimizer_and_starts": config["conditional_fit"],
        "all_start_results": {
            "path": _relative(starts_path),
            "sha256": compute_sha256(starts_path),
        },
        "all_lovo_metrics": {
            "path": _relative(metrics_path),
            "sha256": compute_sha256(metrics_path),
        },
        "fit_result": fit_result,
        "sealed_13v_access": False,
        "future_13v_requires_new_explicit_user_authorization": True,
        "repository_withheld_preregistered_cross_voltage_evaluation_completed": False,
        "independent_external_validation": False,
        "unique_raw_parameter_recovery_claim": False,
        "trained_pinn_claim": False,
    }
    payload["fit_lock_sha256"] = _canonical_hash(payload)
    _write_json(_resolve(config["outputs"]["fit_lock"]), payload)
    return payload


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prereg = _verify_preregistration(config)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    observations, regimes = _load_open_observations(config, prereg)
    source_config = yaml.safe_load(
        _resolve(config["source_model"]["source_config"]).read_text(encoding="utf-8")
    )
    params = VO2ThermalNeuristorParameters.from_config(source_config)
    dt_values = [float(value) for value in config["fixed_step_family"]["dt_values_s"]]
    metric_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    voltage_results: dict[str, Any] = {}
    dop_references: dict[float, EventResolvedResult] = {}
    finest_results: dict[float, EventResolvedResult] = {}

    for voltage in (9.0, 11.0, 15.0, 17.0):
        observation = observations[voltage]
        regime = regimes[voltage]
        evaluation_times = np.asarray(observation["time_s"], dtype=np.float64)
        dop = simulate_event_resolved_si(
            params,
            input_voltage_V=voltage,
            evaluation_times_s=evaluation_times,
            method="DOP853",
            reference_config=config["independent_reference"],
        )
        radau = simulate_event_resolved_si(
            params,
            input_voltage_V=voltage,
            evaluation_times_s=evaluation_times,
            method="Radau",
            reference_config=config["independent_reference"],
        )
        dop_references[voltage] = dop
        reference_metrics, reference_events = compare_solver_results(
            dop,
            radau,
            voltage_V=voltage,
            regime=regime,
            current_noise_A=float(observation["current_noise_scale_A"]),
            voltage_noise_V=float(observation["device_voltage_noise_scale_V"]),
            event_config=config["event_metrics"],
            params=params,
            candidate_label="Radau",
        )
        reference_metrics.update(
            {
                "dt_s": None,
                "solver_family": "independent_reference_parity",
                "normalized_primary_score": None,
            }
        )
        metric_rows.append(reference_metrics)
        event_rows.extend(reference_events)
        reference_sequence_exact = event_sequence_signature(
            dop.event_records
        ) == event_sequence_signature(radau.event_records)
        transient_start = 0.1 * float(evaluation_times[-1] - evaluation_times[0])
        dop_ledger = (
            cycle_energy_ledger(
                dop, params, input_voltage_V=voltage, start_s=transient_start
            )
            if regime == "oscillatory"
            else None
        )
        reference_pass, reference_checks = _reference_gate(
            reference_metrics,
            regime=regime,
            gates=config["reference_parity_gates"],
            sequence_exact=reference_sequence_exact,
            dop_ledger=dop_ledger,
        )

        fixed_results: list[EventResolvedResult] = []
        fixed_metrics: list[dict[str, Any]] = []
        for dt_s in dt_values:
            candidate = simulate_source_compatible_family_member(
                params,
                input_voltage_V=voltage,
                t_max_s=float(evaluation_times[-1] + dt_s),
                dt_s=dt_s,
            )
            fixed_results.append(candidate)
            label = f"Euler_dt_{dt_s:g}s"
            metrics, rows = compare_solver_results(
                dop,
                candidate,
                voltage_V=voltage,
                regime=regime,
                current_noise_A=float(observation["current_noise_scale_A"]),
                voltage_noise_V=float(observation["device_voltage_noise_scale_V"]),
                event_config=config["event_metrics"],
                params=params,
                candidate_label=label,
            )
            gates = (
                config["static_primary_gates"]
                if regime == "static"
                else config["oscillatory_primary_gates"]
            )
            score = normalized_primary_score(metrics, regime=regime, gates=gates)
            metrics.update(
                {
                    "dt_s": dt_s,
                    "solver_family": "source_compatible_explicit_euler",
                    "normalized_primary_score": score,
                }
            )
            fixed_metrics.append(metrics)
            metric_rows.append(metrics)
            event_rows.extend(rows)
        finest_results[voltage] = fixed_results[-1]
        primary_gates = (
            config["static_primary_gates"]
            if regime == "static"
            else config["oscillatory_primary_gates"]
        )
        finest_checks = _primary_checks(
            fixed_metrics[-1], regime=regime, gates=primary_gates
        )
        scores = [float(row["normalized_primary_score"]) for row in fixed_metrics]
        slope = convergence_loglog_slope(dt_values, scores)
        two_finest_sequence_exact = event_sequence_signature(
            fixed_results[-2].event_records
        ) == event_sequence_signature(fixed_results[-1].event_records)
        two_finest_activity_exact = (
            fixed_metrics[-2]["candidate_activity_class"]
            == fixed_metrics[-1]["candidate_activity_class"]
        )
        trend_checks = {
            "finest_not_greater_than_coarsest": bool(
                math.isfinite(scores[-1]) and scores[-1] <= scores[0]
            ),
            "loglog_slope": bool(
                math.isfinite(slope)
                and slope
                >= float(config["sequence_convergence_gates"]["normalized_loglog_slope_min"])
            ),
            "two_finest_event_sequence_exact": two_finest_sequence_exact,
            "two_finest_activity_class_exact": two_finest_activity_exact,
        }
        primary_pass = bool(
            reference_pass and all(finest_checks.values()) and all(trend_checks.values())
        )
        raw_diagnostic_pass = bool(
            _finite_le(
                fixed_metrics[-1]["full_horizon_current_nrmse95"],
                float(config["diagnostic_only_gates"]["full_horizon_current_nrmse95_max"]),
            )
            and _finite_le(
                fixed_metrics[-1]["full_horizon_voltage_nrmse95"],
                float(config["diagnostic_only_gates"]["full_horizon_voltage_nrmse95_max"]),
            )
        )
        if not reference_pass or not two_finest_sequence_exact:
            classification = "event_semantic_nonconvergence"
        elif not primary_pass:
            classification = "true_numerical_nonconvergence"
        elif regime == "static":
            classification = "normalization_artifact_resolved_by_absolute_noise_floor_metrics"
        elif not raw_diagnostic_pass:
            classification = "phase_shadowing_failure_not_orbit_failure"
        else:
            classification = "normalization_and_orbit_metrics_converged"
        voltage_results[f"{voltage:g}"] = {
            "regime": regime,
            "classification": classification,
            "reference_parity_passed": reference_pass,
            "reference_checks": reference_checks,
            "reference_event_sequence_exact": reference_sequence_exact,
            "dop853_statistics": dict(dop.solver_statistics),
            "radau_statistics": dict(radau.solver_statistics),
            "finest_dt_s": dt_values[-1],
            "finest_primary_checks": finest_checks,
            "convergence_scores": scores,
            "convergence_loglog_slope": slope,
            "trend_checks": trend_checks,
            "full_horizon_raw_time_diagnostic_passed": raw_diagnostic_pass,
            "primary_gate_passed": primary_pass,
            "finest_metrics": fixed_metrics[-1],
            "reference_parity_metrics": reference_metrics,
        }

    _write_csv(_resolve(config["outputs"]["convergence_metrics"]), metric_rows)
    _write_csv(_resolve(config["outputs"]["event_table"]), event_rows)
    _make_figures(config, metric_rows, event_rows, dop_references, finest_results)
    all_primary = bool(
        all(row["primary_gate_passed"] for row in voltage_results.values())
    )
    summary: dict[str, Any] = {
        "schema_version": "m36_event_resolved_orbit_evidence_v1",
        "stage_id": config["stage_id"],
        "started_at_utc": started_at,
        "git_commit": _git("rev-parse", "HEAD"),
        "machine_summary": {
            "device": "cpu",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "open_public_voltages_V": [9.0, 11.0, 15.0, 17.0],
        "event_semantics_identical": False,
        "event_semantics_comparison_required": True,
        "m35_artifacts_rerun_or_overwritten": False,
        "historical_d0a_failure_preserved": True,
        "m36_primary_gates_pass": all_primary,
        "voltage_results": voltage_results,
        "jacobian_executed": False,
        "fit_executed": False,
        "fit_lock_created": False,
        "sealed_13v_access": False,
        "pinn_training_performed": False,
        "claim_status": "qualified_supported" if all_primary else "failed_but_informative",
    }

    if not all_primary:
        summary.update(
            {
                "status": "stopped_at_m36_primary_solver_gate",
                "failure_reason": (
                    "At least one preregistered reference-parity, event-sequence, "
                    "fixed-step trend, or regime-specific orbit gate failed."
                ),
                "conditional_public_refit_route": "closed",
                "next_single_action": "close_public_refit_route_and_compress_manuscript",
            }
        )
    else:
        jacobian_cache = EventForwardCache(
            reference_config=config["independent_reference"],
            maximum_evaluations=int(config["conditional_fit"]["maximum_forward_evaluations"]),
            method=str(config["conditional_fit"]["solver_method"]),
        )
        spectra, jacobian = event_aware_jacobian_audit(
            params,
            observations,
            regimes,
            config["conditional_jacobian"],
            config["event_metrics"],
            jacobian_cache,
        )
        _write_csv(_resolve(config["outputs"]["jacobian_spectra"]), spectra)
        _write_json(_resolve(config["outputs"]["jacobian_summary"]), jacobian)
        summary["jacobian_executed"] = True
        summary["jacobian_audit"] = jacobian
        if not jacobian["conditional_fit_authorized"]:
            summary.update(
                {
                    "status": "stopped_at_event_aware_jacobian_gate",
                    "failure_reason": (
                        "The event-aware static/oscillatory/joint Jacobian did not pass "
                        "all numerical, joint-rank, and complementarity gates."
                    ),
                    "conditional_public_refit_route": "closed",
                    "next_single_action": "preserve_cross_regime_nonidentifiability_without_parameter_search",
                }
            )
        else:
            fit_config = config["conditional_fit"]
            objectives = [str(value) for value in fit_config["objectives"]]
            per_objective_budget = int(fit_config["maximum_forward_evaluations"]) // len(objectives)
            fit_caches = {
                objective: EventForwardCache(
                    reference_config=config["independent_reference"],
                    maximum_evaluations=per_objective_budget,
                    method=str(fit_config["solver_method"]),
                )
                for objective in objectives
            }
            start_rows: list[dict[str, Any]] = []
            fit_metric_rows: list[dict[str, Any]] = []
            for fold in fit_config["folds"]:
                fit_voltages = [float(value) for value in fold["fit_voltages_V"]]
                for objective in objectives:
                    for coordinate_system in fit_config["coordinate_systems"]:
                        for start_id, offset in enumerate(
                            fit_config["deterministic_start_offsets"]
                        ):
                            start_row, rows = run_fit_start(
                                job_id=str(fold["fold_id"]),
                                objective=objective,
                                coordinate_system=str(coordinate_system),
                                fit_voltages=fit_voltages,
                                observations=observations,
                                regimes=regimes,
                                base=params,
                                fit_config=fit_config,
                                event_config=config["event_metrics"],
                                start_id=start_id,
                                start_offset=offset,
                                cache=fit_caches[objective],
                                task_started=started,
                            )
                            start_rows.append(start_row)
                            fit_metric_rows.extend(rows)
            starts_path = _resolve(config["outputs"]["fit_starts"])
            fit_metrics_path = _resolve(config["outputs"]["fit_metrics"])
            _write_csv(starts_path, start_rows)
            _write_csv(fit_metrics_path, fit_metric_rows)
            fit_result = aggregate_conditional_fit(start_rows, fit_metric_rows, fit_config)
            expected_starts = 4 * 2 * 2 * 8
            expected_metrics = expected_starts * 4
            complete = len(start_rows) == expected_starts and len(fit_metric_rows) == expected_metrics
            summary.update(
                {
                    "fit_executed": True,
                    "fit_result": fit_result,
                    "all_start_result_count": len(start_rows),
                    "expected_all_start_result_count": expected_starts,
                    "all_lovo_metric_count": len(fit_metric_rows),
                    "expected_all_lovo_metric_count": expected_metrics,
                    "all_fit_outputs_complete": complete,
                    "objective_forward_evaluations": {
                        objective: cache.forward_evaluations
                        for objective, cache in fit_caches.items()
                    },
                }
            )
            if complete and fit_result["fit_lock_gate_passed"]:
                lock = _write_fit_lock(
                    config, prereg, fit_result, starts_path, fit_metrics_path
                )
                summary.update(
                    {
                        "status": "completed_with_valid_open_voltage_fit_lock",
                        "fit_lock_created": True,
                        "fit_lock_sha256": lock["fit_lock_sha256"],
                        "conditional_public_refit_route": "open_for_one_authorized_13v_evaluation",
                        "next_single_action": "request_one_repository_withheld_13v_evaluation",
                        "claim_status": "qualified_supported",
                        "failure_reason": None,
                    }
                )
            else:
                summary.update(
                    {
                        "status": "completed_solver_but_conditional_fit_gate_failed",
                        "fit_lock_created": False,
                        "conditional_public_refit_route": "closed",
                        "next_single_action": "preserve_cross_regime_nonidentifiability_without_parameter_search",
                        "claim_status": "failed_but_informative",
                        "failure_reason": (
                            "All numerical gates passed, but the preregistered LOVO, "
                            "activity, stability, or regime-aware noninferiority gate failed."
                        ),
                    }
                )

    summary["elapsed_seconds"] = time.perf_counter() - started
    summary["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["cpu_wall_clock_budget_hours"] = float(config["budget"]["total_incremental_cpu_hours_max"])
    summary["budget_exceeded"] = bool(
        float(summary["elapsed_seconds"])
        > 3600.0 * float(config["budget"]["total_incremental_cpu_hours_max"])
    )
    _write_json(_resolve(config["outputs"]["summary"]), summary)
    validation = {
        "schema_version": "prompt36_final_validation_v1",
        "stage_id": config["stage_id"],
        "summary_sha256": compute_sha256(_resolve(config["outputs"]["summary"])),
        "convergence_metrics_sha256": compute_sha256(
            _resolve(config["outputs"]["convergence_metrics"])
        ),
        "event_table_sha256": compute_sha256(_resolve(config["outputs"]["event_table"])),
        "frozen_gt_modified": False,
        "m34a_or_m35_rerun": False,
        "sealed_13v_access": False,
        "pinn_training_performed": False,
        "full_pytest_status": "pending_single_final_run",
        "claim_status": summary["claim_status"],
    }
    _write_json(_resolve(config["outputs"]["validation"]), validation)
    return summary


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
                "m36_primary_gates_pass": result["m36_primary_gates_pass"],
                "jacobian_executed": result["jacobian_executed"],
                "fit_executed": result["fit_executed"],
                "fit_lock_created": result["fit_lock_created"],
                "sealed_13v_access": False,
            },
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()

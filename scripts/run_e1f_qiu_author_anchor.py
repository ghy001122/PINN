"""Run the single preregistered E1F Qiu compact-model evidence vote."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml

from pinnpcm.physics.qiu_author_compact_model import (
    QiuAuthorCompactParameters,
    load_parameters,
)
from pinnpcm.solvers.qiu_author_ode import QiuAuthorSimulation, simulate

try:
    from audit_e1f_source_to_pde_bridge import write_bridge_csv
except ModuleNotFoundError:  # pragma: no cover - module import path under pytest
    from scripts.audit_e1f_source_to_pde_bridge import write_bridge_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/e1f_qiu_author_external_anchor.yaml"
DIGITIZED_MANIFEST = (
    ROOT / "data/external/qiu_2024_thermal_neuristor/digitized_manifest.json"
)


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


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("Refusing to write an empty E1F table")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: _jsonable(row.get(key)) for key in fields} for row in rows)


def _verify_record(record: Mapping[str, Any]) -> None:
    path = ROOT / str(record["path"])
    if not path.exists():
        raise RuntimeError(f"Protected E1F input is missing: {record['path']}")
    if path.stat().st_size != int(record["size_bytes"]):
        raise RuntimeError(f"Protected E1F input size changed: {record['path']}")
    if _sha256(path) != str(record["sha256"]):
        raise RuntimeError(f"Protected E1F input hash changed: {record['path']}")


def _verify_preregistration(config: Mapping[str, Any]) -> dict[str, Any]:
    prereg_path = _resolve(config["outputs"]["preregistration"])
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("digitization_authorized_after_preregistration_commit") is not True:
        raise RuntimeError("E1F preregistration did not authorize digitization")
    if prereg.get("all_preflight_checks_pass") is not True:
        raise RuntimeError("E1F preregistration did not pass")
    head = _git("rev-parse", "HEAD")
    if head == str(prereg["base_snapshot"]):
        raise RuntimeError("E1F formal execution requires the preregistration commit")
    if not _git("merge-base", "--is-ancestor", str(prereg["base_snapshot"]), head) == "":
        # `git merge-base --is-ancestor` has no stdout on success. The command
        # already raises on failure; this branch is documentary.
        raise RuntimeError("Unexpected output from ancestry check")
    for group in (
        "raw_source_records",
        "m40_protected_records",
        "m40r_protected_records",
        "frozen_gt_records",
        "preregistration_implementation_records",
    ):
        for record in prereg[group]:
            _verify_record(record)
    if prereg["sealed_zhang_13v_access"] is not False:
        raise RuntimeError("The Zhang 13 V seal is not intact")
    return prereg


def _load_curve(curve_id: str) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    manifest = json.loads(DIGITIZED_MANIFEST.read_text(encoding="utf-8"))
    matches = [item for item in manifest["curves"] if item["curve_id"] == curve_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one digitized curve {curve_id}, found {len(matches)}")
    meta = matches[0]
    path = ROOT / meta["csv_path"]
    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    if not rows:
        raise RuntimeError(f"Digitized curve is empty: {curve_id}")
    columns = {name: np.asarray([float(row[name]) for row in rows]) for name in rows[0] if name not in {"curve_id", "trace_observed"} and rows[0][name] not in {"", None}}
    columns["trace_observed"] = np.asarray(
        [row["trace_observed"].casefold() == "true" for row in rows], dtype=bool
    )
    return columns, meta


def range_normalized_rmse(prediction: np.ndarray, reference: np.ndarray) -> float:
    prediction = np.asarray(prediction, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    if prediction.shape != reference.shape or prediction.size == 0:
        raise ValueError("NRMSE arrays must be nonempty and shape matched")
    scale = max(
        float(np.percentile(reference, 95.0) - np.percentile(reference, 5.0)),
        float(np.max(np.abs(reference))) * 1.0e-12,
        np.finfo(np.float64).tiny,
    )
    return float(np.sqrt(np.mean((prediction - reference) ** 2)) / scale)


def _curve_score(
    simulation: QiuAuthorSimulation,
    curve: Mapping[str, np.ndarray],
    *,
    observed_name: str,
    observed_scale: float,
    simulated_name: str,
) -> dict[str, Any]:
    time_s = np.asarray(curve["time_us"], dtype=np.float64) * 1.0e-6
    observed = np.asarray(curve[observed_name], dtype=np.float64) * observed_scale
    simulated = np.interp(time_s, simulation.time_s, getattr(simulation, simulated_name))
    score = range_normalized_rmse(simulated, observed)
    low_name = observed_name + "_p025"
    high_name = observed_name + "_p975"
    # The digitizer already propagated 500 calibration/line-width draws per
    # point. These envelope scores are sensitivity bounds, not independent-data
    # confidence intervals because the source pixels are correlated.
    envelope_scores: list[float] = []
    for candidate in (low_name, high_name):
        if candidate in curve:
            envelope_scores.append(
                range_normalized_rmse(
                    simulated,
                    np.asarray(curve[candidate], dtype=np.float64) * observed_scale,
                )
            )
    std_name = observed_name + "_std"
    return {
        "range_normalized_rmse": score,
        "digitization_envelope_score_min": min([score, *envelope_scores]),
        "digitization_envelope_score_max": max([score, *envelope_scores]),
        "median_digitized_point_std": (
            float(np.median(curve[std_name])) * observed_scale if std_name in curve else None
        ),
        "point_count": int(time_s.size),
        "directly_observed_fraction": float(np.mean(curve["trace_observed"])),
        "no_phase_or_time_alignment": True,
    }


def _parity(primary: QiuAuthorSimulation, independent: QiuAuthorSimulation) -> dict[str, Any]:
    return {
        "current_nrmse": range_normalized_rmse(primary.current_A, independent.current_A),
        "voltage_nrmse": range_normalized_rmse(primary.voltage_V, independent.voltage_V),
        "temperature_nrmse": range_normalized_rmse(
            primary.temperature_K, independent.temperature_K
        ),
        "activity_class_match": primary.metrics["activity_class"]
        == independent.metrics["activity_class"],
        "event_count_match": primary.metrics["event_count"]
        == independent.metrics["event_count"],
        "event_type_sequence_match": tuple(
            row["event_type"] for row in primary.event_records
        )
        == tuple(row["event_type"] for row in independent.event_records),
        "primary_event_count": int(primary.metrics["event_count"]),
        "independent_event_count": int(independent.metrics["event_count"]),
        "primary_activity_class": primary.metrics["activity_class"],
        "independent_activity_class": independent.metrics["activity_class"],
    }


def _topology(simulation: QiuAuthorSimulation) -> tuple[str, ...]:
    return tuple(str(row["event_type"]) for row in simulation.event_records)


def _feature_vector(
    simulation: QiuAuthorSimulation,
    indices: np.ndarray,
    *,
    waveform_scale: float | None = None,
) -> tuple[np.ndarray, list[str], float]:
    waveform = simulation.current_A[indices]
    if waveform_scale is None:
        waveform_scale = max(
            float(np.percentile(waveform, 95.0) - np.percentile(waveform, 5.0)),
            float(np.max(np.abs(waveform))) * 1.0e-12,
        )
    values = list(waveform / waveform_scale)
    names = [f"current_{index:03d}" for index in range(indices.size)]
    metrics = simulation.metrics
    scalars = {
        "period_s": metrics["median_period_s"],
        "peak_current_A": metrics["peak_current_A"],
        "charge_per_cycle_C": metrics["charge_per_last_cycle_C"],
        "energy_per_cycle_J": metrics["energy_per_last_cycle_J"],
    }
    for name, value in scalars.items():
        if value is None or not math.isfinite(float(value)) or float(value) <= 0.0:
            raise RuntimeError(f"Effective-coordinate feature unavailable: {name}")
        values.append(math.log(float(value)))
        names.append("log_" + name)
    return np.asarray(values, dtype=np.float64), names, float(waveform_scale)


def _perturbed_parameters(
    params: QiuAuthorCompactParameters, coordinate: str, delta: float
) -> QiuAuthorCompactParameters:
    s_th = params.thermal_conductance_W_per_K
    tau = params.thermal_time_constant_s
    if coordinate == "log_S_th":
        s_th *= math.exp(delta)
    elif coordinate == "log_tau_th":
        tau *= math.exp(delta)
    else:
        raise ValueError(coordinate)
    return replace(
        params,
        thermal_conductance_W_per_K=s_th,
        thermal_capacitance_J_per_K=tau * s_th,
    )


def _effective_coordinate_preflight(
    config: Mapping[str, Any],
    params: QiuAuthorCompactParameters,
    baseline: QiuAuthorSimulation,
    times: np.ndarray,
) -> tuple[dict[str, Any], int]:
    preflight = config["effective_coordinate_preflight"]
    indices = np.linspace(0, times.size - 1, int(preflight["waveform_points"]), dtype=int)
    baseline_vector, names, waveform_scale = _feature_vector(baseline, indices)
    baseline_topology = _topology(baseline)
    rows: list[dict[str, Any]] = []
    matrices: dict[float, np.ndarray] = {}
    calls = 0
    for step in (float(value) for value in preflight["relative_steps"]):
        columns: list[np.ndarray] = []
        for coordinate in preflight["coordinates"]:
            plus = simulate(
                _perturbed_parameters(params, coordinate, step),
                float(config["source"]["setting_curve"]["input_voltage_V"]),
                times,
                "DOP853",
                config,
            )
            minus = simulate(
                _perturbed_parameters(params, coordinate, -step),
                float(config["source"]["setting_curve"]["input_voltage_V"]),
                times,
                "DOP853",
                config,
            )
            calls += 2
            plus_vector, _, _ = _feature_vector(
                plus, indices, waveform_scale=waveform_scale
            )
            minus_vector, _, _ = _feature_vector(
                minus, indices, waveform_scale=waveform_scale
            )
            plus_match = _topology(plus) == baseline_topology
            minus_match = _topology(minus) == baseline_topology
            if plus_match and minus_match:
                derivative = (plus_vector - minus_vector) / (2.0 * step)
                derivative_kind = "central"
            elif plus_match:
                derivative = (plus_vector - baseline_vector) / step
                derivative_kind = "one_sided_plus_topology_boundary"
            elif minus_match:
                derivative = (baseline_vector - minus_vector) / step
                derivative_kind = "one_sided_minus_topology_boundary"
            else:
                derivative = np.full_like(baseline_vector, np.nan)
                derivative_kind = "invalid_topology_boundary"
            rows.append(
                {
                    "relative_step": step,
                    "coordinate": coordinate,
                    "plus_topology_match": plus_match,
                    "minus_topology_match": minus_match,
                    "derivative_kind": derivative_kind,
                    "plus_event_count": plus.metrics["event_count"],
                    "minus_event_count": minus.metrics["event_count"],
                }
            )
            columns.append(derivative)
        matrix = np.column_stack(columns)
        matrices[step] = matrix

    fine_step = min(matrices)
    fine = matrices[fine_step]
    all_columns_finite = bool(np.isfinite(fine).all())
    singular_values: list[float] = []
    rank = 0
    retained_condition = None
    if all_columns_finite:
        singular_values = np.linalg.svd(fine, full_matrices=False, compute_uv=False).tolist()
        threshold = float(preflight["relative_singular_value_rank_threshold"])
        rank = int(sum(value >= singular_values[0] * threshold for value in singular_values))
        if rank:
            retained_condition = singular_values[0] / singular_values[rank - 1]
    status = (
        "qualified_supported_local_preflight"
        if all_columns_finite
        and rank >= 1
        and retained_condition is not None
        and retained_condition <= float(preflight["retained_condition_number_max"])
        else "failed_but_informative"
    )
    return (
        {
            "schema_version": "e1f_effective_coordinate_preflight_v1",
            "status": status,
            "protocol_voltage_V": float(config["source"]["setting_curve"]["input_voltage_V"]),
            "feature_normalization": "current_by_baseline_p95_minus_p5_plus_log_positive_cycle_features",
            "feature_names": names,
            "baseline_event_topology": list(baseline_topology),
            "finite_difference_rows": rows,
            "fine_step": fine_step,
            "fine_matrix": fine,
            "singular_values": singular_values,
            "relative_rank_threshold": float(preflight["relative_singular_value_rank_threshold"]),
            "effective_rank": rank,
            "retained_condition_number": retained_condition,
            "topology_boundary_present": any(
                row["derivative_kind"] != "central" for row in rows
            ),
            "local_rank_is_not_global_identifiability": True,
            "inverse_network_run": False,
            "scientific_claim_authorized": False,
        },
        calls,
    )


def _plot_validation(
    path: Path,
    setting: QiuAuthorSimulation,
    holdout: QiuAuthorSimulation,
    curves: Mapping[str, tuple[Mapping[str, np.ndarray], Mapping[str, Any]]],
    baselines: Mapping[str, QiuAuthorSimulation],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.8))
    current_curve = curves["setting_current"][0]
    voltage_curve = curves["setting_voltage"][0]
    holdout_curve = curves["holdout_experiment"][0]
    author_curve = curves["holdout_author_simulation"][0]
    axes[0].plot(current_curve["time_us"], current_curve["current_mA"], color="tab:red", lw=1.0, label="digitized Fig. S1")
    axes[0].plot(setting.time_s * 1e6, setting.current_A * 1e3, color="black", lw=1.0, label="repository")
    axes[0].set(xlabel="Time (µs)", ylabel="Current (mA)", title="12 V source-figure check")
    axes[1].plot(voltage_curve["time_us"], voltage_curve["device_voltage_V"], color="tab:red", lw=1.0, label="digitized Fig. S1")
    axes[1].plot(setting.time_s * 1e6, setting.voltage_V, color="black", lw=1.0, label="repository")
    axes[1].set(xlabel="Time (µs)", ylabel="Device voltage (V)", title="12 V voltage")
    axes[2].plot(holdout_curve["time_us"], holdout_curve["current_mA"], color="tab:blue", lw=1.0, label="digitized experiment")
    axes[2].plot(author_curve["time_us"], author_curve["current_mA"], color="0.45", ls="--", lw=0.9, label="digitized author simulation")
    axes[2].plot(holdout.time_s * 1e6, holdout.current_A * 1e3, color="black", lw=1.0, label="repository")
    axes[2].plot(baselines["no_hysteresis"].time_s * 1e6, baselines["no_hysteresis"].current_A * 1e3, color="tab:orange", lw=0.8, alpha=0.8, label="no hysteresis")
    axes[2].set(xlabel="Time (µs)", ylabel="Current (mA)", title="12.5 V same-paper evaluation")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_bridge(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(row["quantity"]).replace("_", "\n") for row in rows]
    ratios = [float(row["ratio_source_over_local"]) for row in rows]
    fig, axis = plt.subplots(figsize=(7.2, 4.0))
    bars = axis.bar(labels, ratios, color=["#4C78A8", "#F58518", "#E45756", "#72B7B2"])
    axis.set_yscale("log")
    axis.axhline(1.0, color="black", lw=0.8)
    axis.set_ylabel("Qiu source lumped / M40 local projection")
    axis.set_title("Read-only source-to-local-PDE mismatch audit")
    axis.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, ratios):
        axis.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.3g}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _report(payload: Mapping[str, Any]) -> str:
    gates = payload["gates"]
    return "\n".join(
        [
            "# E1F Qiu source-equation external-anchor results",
            "",
            f"- Status: `{payload['status']}`.",
            f"- Formal execution: `{payload['formal_execution_attempt']}/1`; forward integrations: `{payload['forward_integrations']}`; wall time: `{payload['wall_time_s']:.3f} s`.",
            "- Source boundary: S1--S7 are reported, but the executable reversal update, numerical initial conditions, integrator/tolerances, author code, and raw arrays are not public. Exact author-code reproduction remains `forbidden`.",
            "- The 12.5 V curve is repository-withheld but comes from the same paper and may have informed source-author parameter development; it is not independent external validation.",
            "",
            "## Numerical and curve gates",
            "",
            f"- DOP853/Radau parity: `{gates['solver_parity_all_pass']}`; worst waveform NRMSE `{payload['solver_parity_worst_nrmse']:.9g}`.",
            f"- Source-figure setting check: `{gates['setting_curve_pass']}`; max current/voltage NRMSE `{payload['setting_curve_max_nrmse']:.9g}` versus `0.10`.",
            f"- Same-paper 12.5 V curve: `{gates['holdout_curve_pass']}`; current NRMSE `{payload['holdout_curve_nrmse']:.9g}` versus `0.15`.",
            f"- Effective-coordinate preflight: `{payload['effective_coordinate_preflight']['status']}`; it is local diagnostic evidence only.",
            "",
            "## Read-only source-to-PDE bridge audit",
            "",
            "Locked M40/M40R artifacts give local/source ratios that disagree by 2.330233 in resistance; source/local ratios are 635.5145 for thermal capacitance, 206 for thermal conductance, and 3.085022 for thermal time constant. These values forbid direct transfer of lumped author fits into local PDE material or boundary parameters; they do not authorize another M40 repair.",
            "",
            "## Claim disposition",
            "",
            payload["claim_disposition"],
            "",
            "The constrained synthetic rank-1 `gamma_sub` result remains the only positive inverse mainline. M40/M40R, full-PINN training, M41, public inverse identification, and experimental-validation claims are unchanged.",
            "",
        ]
    )


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validation_path = _resolve(config["outputs"]["validation_json"])
    if validation_path.exists():
        raise RuntimeError("E1F formal result already exists; the one-run budget is consumed")
    prereg = _verify_preregistration(config)
    if not DIGITIZED_MANIFEST.exists():
        raise RuntimeError("Locked-panel digitization is missing")
    digitized_manifest = json.loads(DIGITIZED_MANIFEST.read_text(encoding="utf-8"))
    if digitized_manifest["independent_external_holdout"] is not False:
        raise RuntimeError("Digitized curve was mislabeled as independent")

    started = time.perf_counter()
    params = load_parameters(config)
    times = np.linspace(0.0, 20.0e-6, int(config["solvers"]["comparison_points"]))
    setting_voltage = float(config["source"]["setting_curve"]["input_voltage_V"])
    holdout_voltage = float(config["source"]["holdout_curve"]["input_voltage_V"])
    setting_dop = simulate(params, setting_voltage, times, "DOP853", config)
    setting_rad = simulate(params, setting_voltage, times, "Radau", config)
    holdout_dop = simulate(params, holdout_voltage, times, "DOP853", config)
    holdout_rad = simulate(params, holdout_voltage, times, "Radau", config)
    forward_integrations = 4

    baselines = {
        variant: simulate(params, holdout_voltage, times, "DOP853", config, variant=variant)
        for variant in ("no_hysteresis", "fixed_heating")
    }
    forward_integrations += len(baselines)
    curves = {
        "setting_current": _load_curve("qiu_2024_si_fig_s1_12v_current"),
        "setting_voltage": _load_curve("qiu_2024_si_fig_s1_12v_device_voltage"),
        "holdout_experiment": _load_curve("qiu_2024_main_fig2b_12p5v_experimental_current"),
        "holdout_author_simulation": _load_curve("qiu_2024_main_fig2b_12p5v_author_simulation_current"),
    }
    setting_current = _curve_score(setting_dop, curves["setting_current"][0], observed_name="current_mA", observed_scale=1.0e-3, simulated_name="current_A")
    setting_voltage_score = _curve_score(setting_dop, curves["setting_voltage"][0], observed_name="device_voltage_V", observed_scale=1.0, simulated_name="voltage_V")
    holdout_score = _curve_score(holdout_dop, curves["holdout_experiment"][0], observed_name="current_mA", observed_scale=1.0e-3, simulated_name="current_A")
    author_sim_score = _curve_score(holdout_dop, curves["holdout_author_simulation"][0], observed_name="current_mA", observed_scale=1.0e-3, simulated_name="current_A")
    baseline_scores = {
        name: _curve_score(simulation, curves["holdout_experiment"][0], observed_name="current_mA", observed_scale=1.0e-3, simulated_name="current_A")
        for name, simulation in baselines.items()
    }

    parity = {
        "12V": _parity(setting_dop, setting_rad),
        "12p5V": _parity(holdout_dop, holdout_rad),
    }
    parity_threshold = float(config["gates"]["dop853_radau_current_waveform_nrmse_max"])
    parity_checks = {
        label: {
            "current": row["current_nrmse"] <= parity_threshold,
            "voltage": row["voltage_nrmse"] <= float(config["gates"]["dop853_radau_voltage_waveform_nrmse_max"]),
            "temperature": row["temperature_nrmse"] <= float(config["gates"]["dop853_radau_temperature_waveform_nrmse_max"]),
            "activity_class": bool(row["activity_class_match"]),
            "event_count": bool(row["event_count_match"]),
            "event_types": bool(row["event_type_sequence_match"]),
        }
        for label, row in parity.items()
    }
    solver_parity_pass = all(all(row.values()) for row in parity_checks.values())
    setting_max = max(
        setting_current["range_normalized_rmse"],
        setting_voltage_score["range_normalized_rmse"],
    )
    setting_pass = setting_max <= float(config["gates"]["setting_curve_nrmse_max"])
    holdout_pass = holdout_score["range_normalized_rmse"] <= float(config["gates"]["holdout_curve_nrmse_max"])

    if solver_parity_pass and setting_pass:
        coordinate_preflight, extra_calls = _effective_coordinate_preflight(
            config, params, setting_dop, times
        )
        forward_integrations += extra_calls
    else:
        coordinate_preflight = {
            "schema_version": "e1f_effective_coordinate_preflight_v1",
            "status": "not_run_upstream_gate_failed",
            "solver_parity_pass": solver_parity_pass,
            "setting_curve_pass": setting_pass,
            "scientific_claim_authorized": False,
            "inverse_network_run": False,
        }
    _write_json(_resolve(config["outputs"]["coordinate_preflight_json"]), coordinate_preflight)

    bridge_rows = write_bridge_csv(_resolve(config["outputs"]["bridge_mismatch_csv"]))
    _plot_validation(
        _resolve(config["outputs"]["figure_validation"]),
        setting_dop,
        holdout_dop,
        curves,
        baselines,
    )
    _plot_bridge(_resolve(config["outputs"]["figure_bridge"]), bridge_rows)
    worst_parity = max(
        value
        for row in parity.values()
        for key, value in row.items()
        if key.endswith("_nrmse")
    )
    all_positive = solver_parity_pass and setting_pass and holdout_pass
    status = "qualified_supported" if all_positive else "failed_but_informative"
    if all_positive:
        claim_disposition = (
            "The source-equation-constrained reimplementation passes the locked "
            "numerical and same-paper literature-curve gates under explicit "
            "implementation assumptions. This is qualified literature-curve evidence only."
        )
    else:
        failed = [
            name
            for name, value in (
                ("solver_parity", solver_parity_pass),
                ("setting_curve", setting_pass),
                ("same_paper_holdout", holdout_pass),
            )
            if not value
        ]
        claim_disposition = (
            "The formal external-anchor vote failed at " + ", ".join(failed) +
            ". Passed numerical/provenance sub-results and the bridge-refusal audit "
            "remain usable; no refit or replacement curve is authorized."
        )

    rows: list[dict[str, Any]] = []
    for voltage, row in parity.items():
        for metric in ("current_nrmse", "voltage_nrmse", "temperature_nrmse"):
            rows.append({"block": "solver_parity", "case": voltage, "metric": metric, "value": row[metric], "threshold": parity_threshold, "pass": parity_checks[voltage][metric.replace("_nrmse", "")]})
    for name, score, threshold in (
        ("setting_current", setting_current, float(config["gates"]["setting_curve_nrmse_max"])),
        ("setting_voltage", setting_voltage_score, float(config["gates"]["setting_curve_nrmse_max"])),
        ("holdout_experiment", holdout_score, float(config["gates"]["holdout_curve_nrmse_max"])),
        ("holdout_author_simulation_diagnostic", author_sim_score, None),
        ("baseline_no_hysteresis", baseline_scores["no_hysteresis"], None),
        ("baseline_fixed_heating", baseline_scores["fixed_heating"], None),
    ):
        rows.append({"block": "curve_evaluation", "case": name, "metric": "range_normalized_rmse", "value": score["range_normalized_rmse"], "threshold": threshold, "pass": None if threshold is None else score["range_normalized_rmse"] <= threshold, "digitization_envelope_min": score["digitization_envelope_score_min"], "digitization_envelope_max": score["digitization_envelope_score_max"]})

    payload: dict[str, Any] = {
        "schema_version": "e1f_qiu_author_validation_v1",
        "stage_id": config["stage_id"],
        "status": status,
        "formal_execution_attempt": 1,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": config["base_snapshot"],
        "preregistration_commit": _git("rev-parse", "HEAD"),
        "git_dirty_at_execution": bool(_git("status", "--short")),
        "execution_file_hashes": {
            str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path)
            for path in (
                config_path,
                ROOT / "src/pinnpcm/physics/qiu_author_compact_model.py",
                ROOT / "src/pinnpcm/solvers/qiu_author_ode.py",
                ROOT / "scripts/run_e1f_qiu_author_anchor.py",
                ROOT / "scripts/digitize_qiu_author_curves.py",
                DIGITIZED_MANIFEST,
            )
        },
        "source_contract_complete_for_exact_author_code_reproduction": False,
        "exact_author_code_reproduction_status": "forbidden",
        "initial_conditions_and_event_update_are_declared_implementation_assumptions": True,
        "digitized_manifest_sha256": _sha256(DIGITIZED_MANIFEST),
        "digitized_evidence_kind": digitized_manifest["evidence_kind"],
        "independent_external_holdout": False,
        "same_paper_development_contamination_risk": True,
        "solver_parity": parity,
        "solver_parity_checks": parity_checks,
        "solver_parity_worst_nrmse": worst_parity,
        "setting_curve": {"current": setting_current, "voltage": setting_voltage_score},
        "setting_curve_max_nrmse": setting_max,
        "holdout_curve": holdout_score,
        "holdout_curve_nrmse": holdout_score["range_normalized_rmse"],
        "digitized_author_simulation_diagnostic": author_sim_score,
        "matched_baselines": baseline_scores,
        "primary_12V_metrics": setting_dop.metrics,
        "primary_12p5V_metrics": holdout_dop.metrics,
        "gates": {
            "solver_parity_all_pass": solver_parity_pass,
            "setting_curve_pass": setting_pass,
            "holdout_curve_pass": holdout_pass,
            "all_positive_anchor_gates_pass": all_positive,
        },
        "effective_coordinate_preflight": coordinate_preflight,
        "bridge_audit": bridge_rows,
        "governance": config["governance"],
        "m40_m40r_and_frozen_gt_hashes_reverified": True,
        "m40_or_m40r_solver_rerun": False,
        "holdout_refit": False,
        "inverse_network_run": False,
        "pinn_training_run": False,
        "sealed_zhang_13v_access": False,
        "forward_integrations": forward_integrations,
        "wall_time_s": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "claim_disposition": claim_disposition,
        "m41_authorized": False,
        "next_route": "reduced_effective_coordinate_identifiability_review" if all_positive else "q2_manuscript_evidence_compression",
        "preregistration_sha256": _sha256(_resolve(config["outputs"]["preregistration"])),
        "protected_record_counts": {
            group: len(prereg[group])
            for group in ("m40_protected_records", "m40r_protected_records", "frozen_gt_records")
        },
    }
    _write_csv(_resolve(config["outputs"]["validation_csv"]), rows)
    _write_json(validation_path, payload)
    report_path = _resolve(config["outputs"]["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(payload), encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    payload = run(_resolve(args.config))
    print(json.dumps({
        "status": payload["status"],
        "forward_integrations": payload["forward_integrations"],
        "solver_parity_worst_nrmse": payload["solver_parity_worst_nrmse"],
        "setting_curve_max_nrmse": payload["setting_curve_max_nrmse"],
        "holdout_curve_nrmse": payload["holdout_curve_nrmse"],
        "coordinate_preflight": payload["effective_coordinate_preflight"]["status"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

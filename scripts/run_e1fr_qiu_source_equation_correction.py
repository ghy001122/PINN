"""Run the single E1F-R literal-S3 setting-curve corrective audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np
import scipy
import yaml

from pinnpcm.physics.qiu_author_compact_model import load_parameters
from pinnpcm.solvers.qiu_author_ode import QiuAuthorSimulation, simulate

try:
    from run_e1f_qiu_author_anchor import (
        _curve_score,
        _effective_coordinate_preflight,
        _load_curve,
        _parity,
        _write_csv,
        _write_json,
    )
except ModuleNotFoundError:  # pragma: no cover - import path under pytest
    from scripts.run_e1f_qiu_author_anchor import (
        _curve_score,
        _effective_coordinate_preflight,
        _load_curve,
        _parity,
        _write_csv,
        _write_json,
    )


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


def _verify_record(record: Mapping[str, Any]) -> None:
    path = ROOT / str(record["path"])
    if not path.exists():
        raise RuntimeError(f"locked E1F-R input missing: {record['path']}")
    if path.stat().st_size != int(record["size_bytes"]):
        raise RuntimeError(f"locked E1F-R input size changed: {record['path']}")
    if _sha256(path) != str(record["sha256"]):
        raise RuntimeError(f"locked E1F-R input hash changed: {record['path']}")


def _verify_preregistration(config: Mapping[str, Any]) -> dict[str, Any]:
    prereg_path = _resolve(config["outputs"]["preregistration"])
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg["all_preflight_checks_pass"] is not True:
        raise RuntimeError("E1F-R preregistration did not pass")
    if prereg["main_fig2b_simulation_or_scoring_authorized"] is not False:
        raise RuntimeError("E1F-R holdout boundary is not closed")
    if _git("rev-parse", "HEAD") == str(config["base_snapshot"]):
        raise RuntimeError("E1F-R requires the committed preregistration snapshot")
    for record in prereg["implementation_records"]:
        _verify_record(record)
    original = json.loads(ORIGINAL_PREREG.read_text(encoding="utf-8"))
    for group in (
        "raw_source_records",
        "m40_protected_records",
        "m40r_protected_records",
        "frozen_gt_records",
    ):
        for record in original[group]:
            _verify_record(record)
    return prereg


def _plot_setting(
    path: Path,
    simulation: QiuAuthorSimulation,
    current_curve: Mapping[str, np.ndarray],
    voltage_curve: Mapping[str, np.ndarray],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.7))
    axes[0].plot(
        current_curve["time_us"],
        current_curve["current_mA"],
        color="tab:red",
        lw=1.0,
        label="digitized SI Fig. S1",
    )
    axes[0].plot(
        simulation.time_s * 1.0e6,
        simulation.current_A * 1.0e3,
        color="black",
        lw=1.0,
        label="literal-S3 repository model",
    )
    axes[0].set(xlabel="Time (µs)", ylabel="Current (mA)", title="12 V current")
    axes[1].plot(
        voltage_curve["time_us"],
        voltage_curve["device_voltage_V"],
        color="tab:red",
        lw=1.0,
        label="digitized SI Fig. S1",
    )
    axes[1].plot(
        simulation.time_s * 1.0e6,
        simulation.voltage_V,
        color="black",
        lw=1.0,
        label="literal-S3 repository model",
    )
    axes[1].set(xlabel="Time (µs)", ylabel="Device voltage (V)", title="12 V voltage")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.legend(fontsize=7)
    fig.suptitle("Post-lock source-equation correction; no holdout vote", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _report(payload: Mapping[str, Any]) -> str:
    setting = payload["setting_curve"]
    preflight = payload["effective_coordinate_preflight"]
    return "\n".join(
        [
            "# E1F-R Qiu literal-S3 corrective audit",
            "",
            f"- Status: `{payload['status']}`.",
            "- This is a post-lock corrective source-figure audit, not an independent holdout or exact author-code reproduction.",
            "- The original E1F run remains `implementation_contract_invalid`; none of its numerical curve errors casts a scientific vote.",
            "- Main Fig. 2b remains `implementation_contract_invalid/unassessed` because legend pixels contaminated the extraction. It was neither simulated nor scored here.",
            "",
            "## Locked numerical results",
            "",
            f"- DOP853/Radau parity passed: `{payload['gates']['solver_parity_all_pass']}`; worst waveform NRMSE `{payload['solver_parity_worst_nrmse']:.9g}`.",
            f"- SI Fig. S1 current NRMSE: `{setting['current']['range_normalized_rmse']:.9g}`.",
            f"- SI Fig. S1 voltage NRMSE: `{setting['voltage']['range_normalized_rmse']:.9g}`.",
            f"- Locked setting gate (`<=0.10`) passed: `{payload['gates']['setting_curve_pass']}`.",
            f"- Effective-coordinate preflight: `{preflight['status']}`. Any local rank is not global identifiability.",
            f"- Formal integrations: `{payload['forward_integrations']}`; wall time `{payload['wall_time_s']:.3f} s`.",
            "",
            "## Claim boundary",
            "",
            payload["claim_disposition"],
            "",
            "Exact author-code reproduction, independent external validation, public-data inverse recovery, M41, trained-PINN success, and direct lumped-to-local-PDE parameter transfer remain forbidden.",
            "",
        ]
    )


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    result_path = _resolve(config["outputs"]["validation_json"])
    if result_path.exists():
        raise RuntimeError("E1F-R formal result exists; the one-run budget is consumed")
    prereg = _verify_preregistration(config)
    if config["correction_contract"]["main_fig2b_simulation_or_scoring_forbidden"] is not True:
        raise RuntimeError("E1F-R attempted to open the invalid holdout route")

    started = time.perf_counter()
    params = load_parameters(config)
    times = np.linspace(0.0, 20.0e-6, int(config["solvers"]["comparison_points"]))
    voltage = float(config["source"]["setting_curve"]["input_voltage_V"])
    primary = simulate(params, voltage, times, "DOP853", config)
    independent = simulate(params, voltage, times, "Radau", config)
    forward_integrations = 2

    current_curve, current_meta = _load_curve(
        config["source"]["setting_curve"]["current_curve_id"]
    )
    voltage_curve, voltage_meta = _load_curve(
        config["source"]["setting_curve"]["voltage_curve_id"]
    )
    current_score = _curve_score(
        primary,
        current_curve,
        observed_name="current_mA",
        observed_scale=1.0e-3,
        simulated_name="current_A",
    )
    voltage_score = _curve_score(
        primary,
        voltage_curve,
        observed_name="device_voltage_V",
        observed_scale=1.0,
        simulated_name="voltage_V",
    )
    parity = _parity(primary, independent)
    parity_checks = {
        "current": parity["current_nrmse"]
        <= float(config["gates"]["dop853_radau_current_waveform_nrmse_max"]),
        "voltage": parity["voltage_nrmse"]
        <= float(config["gates"]["dop853_radau_voltage_waveform_nrmse_max"]),
        "temperature": parity["temperature_nrmse"]
        <= float(config["gates"]["dop853_radau_temperature_waveform_nrmse_max"]),
        "activity_class": bool(parity["activity_class_match"]),
        "event_count": bool(parity["event_count_match"]),
        "event_types": bool(parity["event_type_sequence_match"]),
    }
    solver_parity_pass = bool(all(parity_checks.values()))
    setting_max = max(
        float(current_score["range_normalized_rmse"]),
        float(voltage_score["range_normalized_rmse"]),
    )
    setting_pass = setting_max <= float(config["gates"]["setting_curve_nrmse_max"])

    if solver_parity_pass and setting_pass:
        try:
            preflight, extra_calls = _effective_coordinate_preflight(
                config, params, primary, times
            )
            forward_integrations += extra_calls
        except (RuntimeError, ValueError, FloatingPointError) as exc:
            preflight = {
                "schema_version": "e1fr_effective_coordinate_preflight_v1",
                "status": "failed_but_informative_runtime",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "scientific_claim_authorized": False,
                "inverse_network_run": False,
            }
    else:
        preflight = {
            "schema_version": "e1fr_effective_coordinate_preflight_v1",
            "status": "not_run_upstream_gate_failed",
            "solver_parity_pass": solver_parity_pass,
            "setting_curve_pass": setting_pass,
            "scientific_claim_authorized": False,
            "inverse_network_run": False,
        }
    _write_json(_resolve(config["outputs"]["coordinate_preflight_json"]), preflight)
    _plot_setting(
        _resolve(config["outputs"]["figure_setting"]),
        primary,
        current_curve,
        voltage_curve,
    )

    status = "qualified_supported" if solver_parity_pass and setting_pass else "failed_but_informative"
    if status == "qualified_supported":
        claim = (
            "Under the reported lumped parameters and declared initial/event assumptions, "
            "the literal-S3 reimplementation passed independent-solver parity and the "
            "same-source SI Fig. S1 implementation-check gate. This is qualified "
            "source-equation evidence only, not external validation."
        )
    else:
        failed = []
        if not solver_parity_pass:
            failed.append("independent-solver parity")
        if not setting_pass:
            failed.append("SI Fig. S1 setting curve")
        claim = (
            "The literal-S3 corrective audit failed at "
            + " and ".join(failed)
            + ". The result defines a source-equation implementation boundary; no refit, "
            "replacement curve, or downstream inverse route is authorized."
        )

    rows: list[dict[str, Any]] = []
    for metric in ("current_nrmse", "voltage_nrmse", "temperature_nrmse"):
        threshold_key = (
            "dop853_radau_" + metric.replace("_nrmse", "") + "_waveform_nrmse_max"
        )
        rows.append(
            {
                "block": "solver_parity",
                "case": "12V",
                "metric": metric,
                "value": parity[metric],
                "threshold": float(config["gates"][threshold_key]),
                "pass": parity_checks[metric.replace("_nrmse", "")],
            }
        )
    for name, score in (("setting_current", current_score), ("setting_voltage", voltage_score)):
        rows.append(
            {
                "block": "source_figure_setting",
                "case": name,
                "metric": "range_normalized_rmse",
                "value": score["range_normalized_rmse"],
                "threshold": float(config["gates"]["setting_curve_nrmse_max"]),
                "pass": score["range_normalized_rmse"]
                <= float(config["gates"]["setting_curve_nrmse_max"]),
                "digitization_envelope_min": score["digitization_envelope_score_min"],
                "digitization_envelope_max": score["digitization_envelope_score_max"],
            }
        )
    _write_csv(_resolve(config["outputs"]["validation_csv"]), rows)

    worst_parity = max(
        float(parity[key])
        for key in ("current_nrmse", "voltage_nrmse", "temperature_nrmse")
    )
    payload: dict[str, Any] = {
        "schema_version": "e1fr_qiu_source_equation_correction_v1",
        "stage_id": config["stage_id"],
        "status": status,
        "formal_execution_attempt": 1,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": config["base_snapshot"],
        "preregistration_commit": _git("rev-parse", "HEAD"),
        "git_dirty_at_execution": bool(_git("status", "--short")),
        "post_lock_corrective_audit": True,
        "original_e1f_status": "implementation_contract_invalid",
        "original_e1f_scientific_vote": False,
        "literal_source_equation_s3": config["correction_contract"]["source_equation_s3_literal"],
        "main_fig2b": {
            "status": "implementation_contract_invalid_unassessed",
            "simulated": False,
            "scored": False,
            "independent_holdout": False,
        },
        "source_contract_complete_for_exact_author_code_reproduction": False,
        "exact_author_code_reproduction_status": "forbidden",
        "solver_parity": parity,
        "solver_parity_checks": parity_checks,
        "solver_parity_worst_nrmse": worst_parity,
        "setting_curve": {
            "current": current_score,
            "voltage": voltage_score,
            "current_metadata": current_meta,
            "voltage_metadata": voltage_meta,
        },
        "setting_curve_max_nrmse": setting_max,
        "gates": {
            "solver_parity_all_pass": solver_parity_pass,
            "setting_curve_pass": setting_pass,
            "all_authorized_positive_gates_pass": solver_parity_pass and setting_pass,
        },
        "effective_coordinate_preflight": preflight,
        "primary_12V_metrics": primary.metrics,
        "forward_integrations": forward_integrations,
        "wall_time_s": time.perf_counter() - started,
        "formal_budget_respected": forward_integrations
        <= int(config["budget"]["maximum_total_forward_integrations"]),
        "execution_file_hashes": {
            record["path"]: record["sha256"] for record in prereg["implementation_records"]
        },
        "preregistration_sha256": _sha256(
            _resolve(config["outputs"]["preregistration"])
        ),
        "m40_m40r_and_frozen_gt_hashes_reverified": True,
        "m40_or_m40r_solver_rerun": False,
        "holdout_refit": False,
        "inverse_network_run": False,
        "pinn_training_run": False,
        "sealed_zhang_13v_access": False,
        "m41_authorized": False,
        "claim_disposition": claim,
        "next_route": "q2_manuscript_evidence_compression_and_submission_lock",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
    }
    if not math.isfinite(float(payload["wall_time_s"])):
        raise RuntimeError("non-finite E1F-R wall time")
    _write_json(result_path, payload)
    report_path = _resolve(config["outputs"]["report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(payload), encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    payload = run(_resolve(args.config))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "solver_parity_worst_nrmse": payload["solver_parity_worst_nrmse"],
                "setting_current_nrmse": payload["setting_curve"]["current"]["range_normalized_rmse"],
                "setting_voltage_nrmse": payload["setting_curve"]["voltage"]["range_normalized_rmse"],
                "effective_coordinate_preflight": payload["effective_coordinate_preflight"]["status"],
                "holdout_simulated_or_scored": False,
                "forward_integrations": payload["forward_integrations"],
                "wall_time_s": payload["wall_time_s"],
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()

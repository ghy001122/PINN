"""Persist the observed fail-closed N0-CV-E v3 training outcome.

This script performs no training and changes no preregistered scientific file.
It exists because the locked trainer terminated inside L-BFGS before it could
write its normal result payload.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import yaml

from pinnpcm.pinn.n0_cv_evidence import stable_file_hash


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _baseline_rows(phase_a: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("strongest_global_baseline", "e3f5765_split_repair"):
        metrics = phase_a["unified_cv_rescore"][key]["metrics"]
        rows.append(
            {
                "model": key,
                "evaluation_status": "scored_common_frozen_registry",
                "port_nrmse95": metrics["port_full_trace_nrmse95"],
                "max_cv_residual": max(metrics["cv_residual_rms"].values()),
                "max_field_nrmse95": max(metrics["field_score_only_nrmse95"].values()),
                "max_interface_state": max(metrics["interface_state_rms"].values()),
                "terminal_current": metrics["terminal_current_conservation_normalized_error"],
                "defect_ledger": metrics["defect_mass_ledger"]["gate_value"],
                "energy_ledger": metrics["global_energy_ledger"]["gate_value"],
                "normalization": metrics["normalization"],
            }
        )
    rows.append(
        {
            "model": "n0_cv_e_v3_seed_20260715",
            "evaluation_status": "unscored_runtime_failure_before_checkpoint",
            "port_nrmse95": "",
            "max_cv_residual": "",
            "max_field_nrmse95": "",
            "max_interface_state": "",
            "terminal_current": "",
            "defect_ledger": "",
            "energy_ledger": "",
            "normalization": "preregistered_but_no_trajectory_available",
        }
    )
    return rows


def _write_comparison(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_figure(rows: list[dict[str, Any]], config: dict[str, Any], path: Path) -> None:
    gates = config["result_gates"]
    definitions = [
        ("port_nrmse95", float(gates["port_full_trace_nrmse95_max"]), "Port"),
        ("max_cv_residual", float(gates["residual_rms_max"]), "CV residual"),
        ("max_field_nrmse95", float(gates["field_score_only_nrmse95_max"]), "Field"),
        ("terminal_current", float(gates["terminal_current_conservation_max"]), "Current"),
        ("defect_ledger", float(gates["defect_mass_ledger_max"]), "Defect ledger"),
        ("energy_ledger", float(gates["global_energy_imbalance_max"]), "Energy ledger"),
    ]
    scored = rows[:2]
    labels = [row["model"] for row in scored]
    figure, axes = plt.subplots(2, 3, figsize=(13.5, 7.2), constrained_layout=True)
    figure.suptitle(
        "N0-CV-E v3 unscored: non-finite L-BFGS loss before checkpoint",
        fontsize=12,
    )
    for axis, (key, gate, title) in zip(axes.flat, definitions, strict=True):
        ratios = [max(float(row[key]) / gate, 1.0e-8) for row in scored]
        axis.bar(range(len(scored)), ratios, color=["#e76f51" if value > 1 else "#2a9d8f" for value in ratios])
        axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
        axis.set_yscale("log")
        axis.set_title(f"{title} / gate")
        axis.set_xticks(range(len(scored)), labels, rotation=24, ha="right", fontsize=8)
        axis.grid(axis="y", alpha=0.25)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/full_pinn_n0_cv_e_v3.yaml"))
    parser.add_argument("--observed-wall-clock-s", type=float, default=54.1)
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = _yaml(config_path)
    phase_a = _json(ROOT / config["outputs"]["phase_a_json"])
    preflight = _json(ROOT / config["outputs"]["preflight"])
    preregistration = _json(ROOT / config["outputs"]["preregistration"])
    mismatches = {
        relative: {"expected": expected, "actual": stable_file_hash(ROOT / relative)}
        for relative, expected in preregistration["locked_files"].items()
        if stable_file_hash(ROOT / relative) != expected
    }
    if mismatches:
        raise RuntimeError(f"Locked scientific files changed after preflight: {mismatches}")

    gate_checks = {
        name: "unassessed_fail_closed"
        for name in (
            "port",
            "cv_residuals",
            "discrete_electrical",
            "fields",
            "interface_state",
            "interface_flux",
            "current_conservation",
            "energy_ledger",
            "defect_ledger",
            "ic_bc",
            "finite_outputs",
            "bounded_states",
            "hash_and_operator",
        )
    }
    result = {
        "schema_version": "n0_cv_e_v3_training_failure_v1",
        "stage_id": "N0-CV-E-v3-training",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": config["base_commit"],
        "command": ".\\.venv\\Scripts\\python.exe scripts\\train_n0_cv_e_v3.py --config configs\\full_pinn_n0_cv_e_v3.yaml",
        "seed": int(config["training"]["seed"]),
        "arm": "primary_equal_weight",
        "status": "failed_but_informative",
        "failure_stage": "lbfgs_strong_wolfe_closure",
        "exception_type": "RuntimeError",
        "exception_message": "Non-finite N0-CV-E L-BFGS loss.",
        "traceback_terminal_location": "scripts/train_n0_cv_e_v3.py:350 in closure",
        "observed_wall_clock_s": float(args.observed_wall_clock_s),
        "adam_steps_completed": int(config["training"]["epochs"]),
        "adam_step_evidence": "control reached the L-BFGS block after all locked causal Adam loops; no per-step telemetry survived the exception",
        "lbfgs_optimizer_instances": 1,
        "lbfgs_closure_calls_before_failure": None,
        "training_semantics": "data_free_solver_exact_CV_and_ledger_only",
        "port_labels_used": [],
        "hidden_field_labels_used": [],
        "checkpoint": None,
        "checkpoint_reason": "trainer failed before checkpoint serialization",
        "metrics": None,
        "gates": {"checks": gate_checks, "all_pass": False},
        "balancing_arm_run": False,
        "balancing_arm_reason": "primary arm did not complete evaluation, so locked eligibility logic was never reached",
        "seed_expansion_run": False,
        "sparse_anchor_run": False,
        "hyperparameter_search_run": False,
        "N1_N3_or_SC_LOS_run": False,
        "scientific_lock_match_after_failure": True,
        "scientific_lock_mismatches": mismatches,
        "preflight_all_pass": bool(preflight["all_pass"]),
        "positive_forward_claim_allowed": False,
        "stop_reason": "The locked primary run produced a non-finite L-BFGS loss before checkpoint and gate evaluation; fail closed without rerun or tuning.",
        "seed_vote": {
            "pilot_passed": False,
            "evaluated_seeds": 0,
            "passing_seeds": 0,
            "minimum_passing_seeds": int(config["result_gates"]["minimum_passing_seeds"]),
            "total_seeds": int(config["result_gates"]["total_seeds"]),
            "overall_pass": False,
        },
    }
    pilot_path = ROOT / config["outputs"]["pilot_result"]
    pilot_path.parent.mkdir(parents=True, exist_ok=True)
    pilot_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema_version": "n0_cv_e_v3_checkpoint_manifest_v1",
        "checkpoints": [],
        "status": "no_checkpoint_runtime_failure_before_serialization",
        "result_path": config["outputs"]["pilot_result"],
    }
    manifest_path = ROOT / config["outputs"]["checkpoint_manifest"]
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    rows = _baseline_rows(phase_a)
    _write_comparison(rows, ROOT / config["outputs"]["comparison_csv"])
    _write_figure(rows, config, ROOT / config["outputs"]["gate_figure"])
    summary = {
        "schema_version": "n0_cv_e_v3_summary_v1",
        "base_commit": config["base_commit"],
        "phase_a": {
            "status": phase_a["status"],
            "completed": phase_a["phase_a_completed"],
            "v2_gate_gaps": phase_a["v2_gate_coverage"]["documented_gaps"],
            "checkpoint_classification": phase_a["v2_checkpoint"]["classification"],
            "remote_ci_status": phase_a["remote_ci"]["status"],
            "pytest_evidence": phase_a["pytest_evidence"]["classification"],
        },
        "preflight": {
            "status": preflight["status"],
            "all_pass": preflight["all_pass"],
            "checks": preflight["checks"],
            "training_authorized": preflight["training_authorized"],
        },
        "training": result,
        "training_status": "failed_but_informative",
        "comparison": rows,
        "validation": None,
        "claim_status": "failed_but_informative",
        "positive_forward_claim_allowed": False,
        "disposition": "N0_final_stop_training_runtime_failure",
        "forbidden_claims": [
            "successful_N0_forward_training",
            "experimental_validation",
            "cross_material_generalization",
            "universal_phase_transition_PINN",
            "inverse_problem_success",
            "novelty_of_analytic_electrostatics_CV_FVM_hard_constraints_or_balancing",
        ],
        "next_single_recommendation": "Close N0 without further tuning and return to the calibrated gamma_sub manuscript mainline.",
    }
    summary_path = ROOT / config["outputs"]["summary"]
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report = ROOT / config["outputs"]["report"]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# N0-CV-E v3 Final Bounded Attempt",
                "",
                f"Base commit: `{config['base_commit']}`",
                "",
                "Evidence type: frozen one-dimensional synthetic GT, solver-generated operator diagnostics, and an attempted data-free PINN optimization. No external-data fit or experimental validation was run.",
                "",
                "## Phase A and no-training preflight",
                "",
                f"Phase A: `{phase_a['status']}`. Preflight: `{preflight['status']}` with `{sum(preflight['checks'].values())}/{len(preflight['checks'])}` checks passing and training authorized.",
                "",
                "## Conditional training",
                "",
                "The locked seed `20260715` run reached its single L-BFGS stage after the scheduled 1200 Adam steps, then stopped when a strong-Wolfe closure produced a non-finite loss. The exception occurred before checkpoint serialization or result-gate evaluation.",
                "",
                "All training-result gates are therefore `unassessed_fail_closed`. No balancing arm, seed expansion, sparse anchor, hyperparameter search, N1-N3, or SC-LOS run was performed.",
                "",
                "## Claim disposition",
                "",
                "Final status: `failed_but_informative`. N0 is closed after this final bounded attempt. No positive full-PINN forward claim is allowed.",
                "",
                "Unique next step: return to the already supported calibrated `gamma_sub` manuscript mainline.",
                "",
                "Analytic electrostatics, control-volume/FVM residuals, hard constraints, causal training, and gradient balancing remain prior-art components and are not claimed as standalone novelty.",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": result["status"], "disposition": summary["disposition"]}))


if __name__ == "__main__":
    main()

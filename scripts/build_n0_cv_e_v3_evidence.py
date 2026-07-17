"""Build the N0-CV-E v3 comparison, figure, summary, and report."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _comparison_rows(
    config: dict[str, Any], phase_a: dict[str, Any], training: dict[str, Any] | None
) -> list[dict[str, Any]]:
    rows = []
    for model_key, label in (
        ("strongest_global_baseline", "strongest_global_baseline"),
        ("e3f5765_split_repair", "e3f5765_split_repair"),
    ):
        metrics = phase_a["unified_cv_rescore"][model_key]["metrics"]
        rows.append(
            {
                "model": label,
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
    if training is not None:
        metrics = training["selected_pilot"]["metrics"]
        rows.append(
            {
                "model": f"n0_cv_e_v3_{training['selected_pilot_arm']}",
                "port_nrmse95": metrics["port_full_trace_nrmse95"],
                "max_cv_residual": max(metrics["cv_residual_rms"].values()),
                "max_field_nrmse95": max(metrics["field_score_only_nrmse95"].values()),
                "max_interface_state": max(metrics["interface_state_rms"].values()),
                "terminal_current": metrics["terminal_current_conservation_normalized_error"],
                "defect_ledger": metrics["defect_mass_ledger"]["gate_value"],
                "energy_ledger": metrics["global_energy_ledger"]["gate_value"],
                "normalization": metrics["common_scale_normalization"],
            }
        )
    return rows


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot(rows: list[dict[str, Any]], config: dict[str, Any], path: Path) -> None:
    gates = config["result_gates"]
    metrics = [
        ("port_nrmse95", float(gates["port_full_trace_nrmse95_max"]), "Port"),
        ("max_cv_residual", float(gates["residual_rms_max"]), "CV residual"),
        ("max_field_nrmse95", float(gates["field_score_only_nrmse95_max"]), "Field"),
        ("terminal_current", float(gates["terminal_current_conservation_max"]), "Current"),
        ("defect_ledger", float(gates["defect_mass_ledger_max"]), "Defect ledger"),
        ("energy_ledger", float(gates["global_energy_imbalance_max"]), "Energy ledger"),
    ]
    labels = [row["model"] for row in rows]
    figure, axes = plt.subplots(2, 3, figsize=(13.5, 7.2), constrained_layout=True)
    for axis, (key, gate, title) in zip(axes.flat, metrics, strict=True):
        ratios = [max(float(row[key]) / gate, 1.0e-8) for row in rows]
        colors = ["#2a9d8f" if ratio <= 1.0 else "#e76f51" for ratio in ratios]
        axis.bar(range(len(rows)), ratios, color=colors)
        axis.axhline(1.0, color="black", linestyle="--", linewidth=1.0)
        axis.set_yscale("log")
        axis.set_title(f"{title} / gate")
        axis.set_xticks(range(len(rows)), labels, rotation=24, ha="right", fontsize=8)
        axis.grid(axis="y", alpha=0.25)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    phase_a = _load_json(ROOT / config["outputs"]["phase_a_json"])
    preflight = _load_json(ROOT / config["outputs"]["preflight"])
    training = _load_json(ROOT / config["outputs"]["pilot_result"])
    validation = _load_json(ROOT / "outputs/tables/n0_cv_e_v3_validation.json")
    assert phase_a is not None and preflight is not None
    rows = _comparison_rows(config, phase_a, training)
    _write_csv(rows, ROOT / config["outputs"]["comparison_csv"])
    _plot(rows, config, ROOT / config["outputs"]["gate_figure"])

    if not preflight["all_pass"]:
        final_status = "failed_but_informative"
        disposition = "N0_final_stop_preflight_failure"
        training_status = "not_run"
        positive_claim = False
    elif training is None:
        final_status = "forbidden"
        disposition = "training_pending"
        training_status = "not_run"
        positive_claim = False
    else:
        positive_claim = bool(training["seed_vote"]["overall_pass"])
        final_status = "qualified_supported" if positive_claim else "failed_but_informative"
        disposition = "bounded_forward_claim" if positive_claim else "N0_final_stop_training_failure"
        training_status = training["status"]

    payload = {
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
        "training": training,
        "training_status": training_status,
        "comparison": rows,
        "validation": validation,
        "claim_status": final_status,
        "positive_forward_claim_allowed": positive_claim,
        "disposition": disposition,
        "forbidden_claims": [
            "experimental_validation",
            "cross_material_generalization",
            "universal_phase_transition_PINN",
            "inverse_problem_success",
            "novelty_of_analytic_electrostatics_CV_FVM_hard_constraints_or_balancing",
        ],
        "next_single_recommendation": (
            "Lock the bounded frozen-1D forward result and return to the calibrated gamma_sub manuscript mainline."
            if positive_claim
            else "Close N0 without further tuning and return to the calibrated gamma_sub manuscript mainline."
        ),
    }
    return payload


def _write_report(summary: dict[str, Any], config: dict[str, Any], path: Path) -> None:
    preflight = summary["preflight"]
    training = summary["training"]
    lines = [
        "# N0-CV-E v3 Final Bounded Attempt",
        "",
        f"Base commit: `{summary['base_commit']}`",
        "",
        "Evidence type: frozen one-dimensional synthetic GT, solver-generated operator diagnostics, and PINN-predicted trajectories. No external-data fit or experimental validation was run.",
        "",
        "## Phase A",
        "",
        f"Status: `{summary['phase_a']['status']}`. v2 fail-closed gate gaps: `{', '.join(summary['phase_a']['v2_gate_gaps'])}`. The v2 checkpoint remains `{summary['phase_a']['checkpoint_classification']}`.",
        "",
        "## No-training preflight",
        "",
        f"Status: `{preflight['status']}`; all pass: `{preflight['all_pass']}`; training authorized: `{preflight['training_authorized']}`.",
        "",
    ]
    if training is None:
        lines.extend(["## Training", "", "Training was not run because it was not authorized or remains pending.", ""])
    else:
        selected = training["selected_pilot"]
        metrics = selected["metrics"]
        lines.extend(
            [
                "## Conditional training",
                "",
                f"Selected pilot arm: `{training['selected_pilot_arm']}`; pilot status: `{selected['status']}`; balancing arm run: `{training['balancing_arm_run']}`; seed expansion: `{training['seed_vote']['expansion_run']}`.",
                "",
                "| Gate | Value | Pass |",
                "| --- | ---: | --- |",
                f"| port NRMSE95 | {metrics['port_full_trace_nrmse95']:.6g} | {selected['gates']['checks']['port']} |",
                f"| max CV residual | {max(metrics['cv_residual_rms'].values()):.6g} | {selected['gates']['checks']['cv_residuals']} |",
                f"| max field NRMSE95 | {max(metrics['field_score_only_nrmse95'].values()):.6g} | {selected['gates']['checks']['fields']} |",
                f"| current conservation | {metrics['terminal_current_conservation_normalized_error']:.6g} | {selected['gates']['checks']['current_conservation']} |",
                f"| defect ledger | {metrics['defect_mass_ledger']['gate_value']:.6g} | {selected['gates']['checks']['defect_ledger']} |",
                f"| energy ledger | {metrics['global_energy_ledger']['gate_value']:.6g} | {selected['gates']['checks']['energy_ledger']} |",
                "",
            ]
        )
    validation = summary.get("validation")
    lines.extend(["## Validation", ""])
    if validation:
        for command in validation.get("commands", []):
            lines.append(f"- `{command['command']}`: `{command['result']}`")
    else:
        lines.append("Validation evidence pending final test execution.")
    lines.extend(
        [
            "",
            "## Claim disposition",
            "",
            f"Final status: `{summary['claim_status']}`. Positive frozen-1D forward wording allowed: `{summary['positive_forward_claim_allowed']}`.",
            "",
            f"Next single recommendation: {summary['next_single_recommendation']}",
            "",
            "Analytic electrostatics, control-volume/FVM residuals, hard constraints, causal training, and gradient balancing remain prior-art components and are not claimed as standalone novelty.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/full_pinn_n0_cv_e_v3.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = _load_yaml(config_path)
    summary = run(config_path)
    output = ROOT / config["outputs"]["summary"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_report(summary, config, ROOT / config["outputs"]["report"])
    print(json.dumps({"claim_status": summary["claim_status"], "disposition": summary["disposition"]}))


if __name__ == "__main__":
    main()

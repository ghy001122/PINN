"""Build the N0-R comparison table, summary, and cumulative report."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _fmt_dict(values: dict[str, float]) -> str:
    return ", ".join(f"{key}={value:.6g}" for key, value in values.items())


def build() -> dict[str, Any]:
    compatibility = _read("outputs/tables/n0_teacher_equation_compatibility_v1.json")
    conservation = _read("outputs/tables/n0_global_conservation_audit_v1.json")
    baseline_payload = _read("outputs/tables/full_pinn_n0_baseline_diagnostics_v2.json")
    repair_payload = _read("outputs/tables/full_pinn_n0_repair_data_free_seed_20260715_v2.json")
    preregistration = _read("outputs/tables/full_pinn_n0_repair_v2_preregistration.json")
    baseline = baseline_payload["metrics"]
    repair = repair_payload["result"]
    repaired = repair["metrics"]

    comparison = [
        {
            "metric": "port_full_trace_nrmse95",
            "gate": 0.10,
            "baseline": baseline["port_full_trace_nrmse95"],
            "repair": repaired["port_full_trace_nrmse95"],
        },
        {
            "metric": "max_heldout_residual_rms",
            "gate": 0.01,
            "baseline": max(baseline["heldout_residual_rms"].values()),
            "repair": max(repaired["heldout_residual_rms"].values()),
        },
        {
            "metric": "max_field_score_only_nrmse95",
            "gate": 0.25,
            "baseline": max(baseline["field_score_only_nrmse95"].values()),
            "repair": max(repaired["field_score_only_nrmse95"].values()),
        },
        {
            "metric": "max_interface_flux_rms",
            "gate": 0.05,
            "baseline": max(baseline["interface_flux_rms"].values()),
            "repair": max(repaired["interface_flux_rms"].values()),
        },
        {
            "metric": "terminal_current_conservation",
            "gate": 0.01,
            "baseline": baseline["terminal_current_conservation_normalized_error"],
            "repair": repaired["terminal_current_conservation_normalized_error"],
        },
        {
            "metric": "global_energy_imbalance",
            "gate": 0.05,
            "baseline": baseline["global_energy_account_normalized_imbalance"],
            "repair": repaired["global_energy_account_normalized_imbalance"],
        },
    ]
    table_path = ROOT / "outputs/tables/n0_baseline_repair_gate_comparison_v2.csv"
    with table_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    summary = {
        "schema_version": "n0_full_pinn_bounded_repair_v2_summary",
        "date": str(date.today()),
        "base_commit": repair_payload["git_commit"],
        "preregistration_config_sha256": preregistration["config_sha256"],
        "fixed_points_content_sha256": preregistration["fixed_points"]["content_sha256"],
        "compatibility_status": compatibility["status"],
        "compatibility_findings": {
            "v1_electrical_orientation_mismatch": compatibility["v1_electrical_orientation_mismatch"],
            "frozen_discrete_conservation_pass": compatibility["frozen_discrete_conservation_pass"],
            "interface_face_offset_m": compatibility["interface_discretization"]["face_offset_from_declared_m"],
            "grid_31_63_port_nrmse95": compatibility["grid_refinement"]["port_current_nrmse95_31_vs_63"],
        },
        "baseline_status": "failed_but_informative",
        "data_free_repair_status": "failed_but_informative",
        "data_free_repair_metrics": repaired,
        "gate_checks": repair["gates"],
        "route": {
            "anchor_run": False,
            "seed_expansion_run": False,
            "N1_N3_run": False,
            "reason": "residual/current/energy conditions did not authorize expansion",
        },
        "claim_changes": {
            "teacher_equation_compatibility_audit": "supported as a no-training numerical audit",
            "exact_interface_implementation": "supported as an implementation fact",
            "single_seed_exact_interface_metrics": "pilot sub-result only; no manuscript upgrade",
            "N0_trained_forward_evidence": "failed_but_informative",
            "reliable_full_PINN_forward_claim": "forbidden",
            "SC_LOS_or_N1_N3_authorized": False,
        },
        "comparison_table": comparison,
        "frozen_fvm_ledger": {
            "max_mass_imbalance": conservation["max_defect_mass_normalized_imbalance"],
            "max_energy_imbalance": conservation["max_global_energy_normalized_imbalance"],
            "max_current_spread": conservation["max_current_normalized_spread"],
        },
        "next_single_recommendation": (
            "Do not enter SC-LOS. If a new round is approved, preregister one solver-consistent control-volume/weak-form "
            "N0-R2 MVE that trains face-flux and global ledgers directly on the same frozen diagnostic set."
        ),
    }
    summary_path = ROOT / "outputs/tables/n0_full_pinn_bounded_repair_v2_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    report = f"""# N0-R Frozen-GT Compatibility and Bounded Full-PINN Repair Report

Date: {summary['date']}

Base commit: `{summary['base_commit']}`

Final commit: recorded in the execution handoff because a commit cannot contain its own hash.

Evidence type: frozen synthetic GT, solver-generated diagnostics, and PINN-predicted outputs. No experimental validation and no VO2 13 V access occurred.

## Executive disposition

N0 remains `failed_but_informative`; the reliable trained full-PINN forward claim remains `forbidden`.

- The frozen FVM is internally conservative: maximum normalized defect-mass, energy, and current ledger errors are `{conservation['max_defect_mass_normalized_imbalance']:.3e}`, `{conservation['max_global_energy_normalized_imbalance']:.3e}`, and `{conservation['max_current_normalized_spread']:.3e}`.
- The old v1 PINN reverses the frozen teacher's electrical boundary orientation. Frozen GT stores `phi(0,t)=V(t), phi(L,t)=0`, while v1 imposed the opposite orientation with the same `E=-dphi/dx` convention.
- The frozen `nx=31` material mask implies an arithmetic-average face `{compatibility['interface_discretization']['face_offset_from_declared_m']:.9e} m` from the declared interface. The `31 -> 63` non-frozen grid diagnostic gives port NRMSE95 `{compatibility['grid_refinement']['port_current_nrmse95_31_vs_63']:.6f}`, below the N0 port gate but explicitly retained as a continuum-discrete difference.
- A matched-budget dual-domain model was preregistered before training: `5704` parameters versus `5812` for the baseline, fixed-point SHA `{preregistration['fixed_points']['content_sha256']}`, config SHA `{preregistration['config_sha256']}`.
- The fixed seed `20260715` data-free MVE used 1200 causal Adam epochs and one bounded L-BFGS optimizer instance. It failed; neither seed expansion nor sparse-port anchor was run.

## Controlled baseline and repair

| Metric | Gate | Single-global baseline | Dual-domain repair | Disposition |
| --- | ---: | ---: | ---: | --- |
"""
    for row in comparison:
        disposition = "pass" if row["repair"] <= row["gate"] else "fail"
        report += f"| {row['metric']} | `{row['gate']:.6g}` | `{row['baseline']:.6g}` | `{row['repair']:.6g}` | **{disposition}** |\n"
    report += f"""

The repair's held-out residuals are `{_fmt_dict(repaired['heldout_residual_rms'])}`. Its score-only field errors are `{_fmt_dict(repaired['field_score_only_nrmse95'])}`. Exact-interface state errors are `{_fmt_dict(repaired['interface_state_rms'])}` and exact-interface flux errors are `{_fmt_dict(repaired['interface_flux_rms'])}`.

The repair passes `r_phi`, `r_m`, endpoint flux, all exact-interface state/flux gates, finite-state, and physical-bound checks. It fails `r_c`, `r_T`, port, field, terminal-current, and global-energy gates. The defect-mass ledger error is `{repaired['defect_mass_account_normalized_imbalance']:.6f}`. The worst current window is indices `{repaired['worst_time_window_current_error']['start_index']}:{repaired['worst_time_window_current_error']['end_index_exclusive']}` with normalized RMSE `{repaired['worst_time_window_current_error']['normalized_rmse']:.6f}`.

## Root-cause ranking

1. **Local strong-form loss does not guarantee the required global ledgers.** The repaired `r_phi` and exact current-flux interface metrics pass, yet terminal-current conservation is `{repaired['terminal_current_conservation_normalized_error']:.6f}` versus `0.01`. Energy imbalance is `{repaired['global_energy_account_normalized_imbalance']:.6f}` versus `0.05`. This is the dominant reason an apparently small local residual cannot support a forward claim.
2. **Defect transport is the largest unresolved state block, not simple collocation overfit.** Train/evaluation `r_c` are `{repair['metrics']['train_residual_rms']['r_c']:.6f}` and `{repaired['heldout_residual_rms']['r_c']:.6f}`; `c_v` score-only NRMSE95 is `{repaired['field_score_only_nrmse95']['c_v']:.6f}` and defect-mass imbalance is `{repaired['defect_mass_account_normalized_imbalance']:.6f}`. Similar train/evaluation failures point to formulation/optimization conflict rather than held-out sampling alone.
3. **The repair solves the interface representation defect but not the coupled trajectory.** Maximum exact interface flux RMS falls to `{max(repaired['interface_flux_rms'].values()):.6f}`, and `phi` field error falls to `{repaired['field_score_only_nrmse95']['phi']:.6f}`. However the port error only changes from `{baseline['port_full_trace_nrmse95']:.6f}` to `{repaired['port_full_trace_nrmse95']:.6f}`. Final gradients retain negative-cosine conflicts, including interface-state versus phase-relaxation.

## Conditional routing and leakage check

- Sparse-port anchor: **not run**. The preregistered route required residual, interface-flux, current, and energy gates to pass first; they did not.
- Seed expansion: **not run**. A single-seed data-free pass was required first.
- Frozen full fields: used only after optimization for scoring.
- N1-N3, SC-LOS, D0b-D0d, EC-OQ, ACAL, AA, TTLD, STL, and dynamic P3: not run.
- VO2 13 V numerical content: not read or unsealed.

## Claim disposition

| Claim | Status | Allowed wording |
| --- | --- | --- |
| Frozen FVM ledger and four manufactured operators are internally consistent | `supported` | No-training numerical audit only |
| v1 PINN electrode orientation conflicts with frozen teacher semantics | `supported` | Implementation root-cause finding |
| Exact dual-domain state/flux traces exist and pass the one-seed local interface gates | `supported` implementation fact / pilot sub-result | No P1, multidomain, or interface-innovation claim |
| Trained full-PINN forward evidence passes frozen GT | `forbidden` | N0 remains `failed_but_informative` |
| PINN sensitivity, quotient inverse, SC-LOS, or experimental validation | `forbidden` | Not run and upstream gates failed |

The distance to the paper goal shortened only in attribution and reproducibility: the teacher/PINN sign conflict, discrete-interface semantics, fixed evaluation set, gradient conflicts, and global-ledger failure are now explicit and hash-locked. It did **not** shorten the positive full-PINN evidence gap.

## Next single recommendation

Do not enter solver-first SC-LOS. If a new execution round is approved, the only high-value continuation is one newly preregistered solver-consistent control-volume/weak-form N0-R2 MVE that trains the face-flux and global conservation ledgers directly on the same fixed diagnostic set. This would be a numerical consistency repair, not a novelty claim, and it must retain the unchanged port/field/residual/conservation gates.

Primary machine evidence:

- `outputs/tables/n0_teacher_equation_compatibility_v1.json`
- `outputs/tables/n0_equation_parity_registry_v1.csv`
- `outputs/tables/n0_global_conservation_audit_v1.json`
- `outputs/tables/full_pinn_n0_baseline_diagnostics_v2.json`
- `outputs/tables/full_pinn_n0_repair_v2_preregistration.json`
- `outputs/tables/full_pinn_n0_repair_data_free_seed_20260715_v2.json`
- `outputs/tables/n0_baseline_repair_gate_comparison_v2.csv`
- `outputs/figures/full_pinn_n0_train_eval_gradient_v2.png`
- `outputs/figures/full_pinn_n0_baseline_repair_gates_v2.png`
"""
    report_path = ROOT / "docs/codex_reports/n0_full_pinn_bounded_repair_v2_report.md"
    report_path.write_text(report, encoding="utf-8")
    return summary


def main() -> None:
    summary = build()
    print(
        json.dumps(
            {
                "status": summary["data_free_repair_status"],
                "anchor_run": summary["route"]["anchor_run"],
                "seed_expansion_run": summary["route"]["seed_expansion_run"],
                "claim": summary["claim_changes"]["N0_trained_forward_evidence"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

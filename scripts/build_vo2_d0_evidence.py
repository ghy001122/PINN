"""Build the bounded D0a/N0 evidence figures, summary, and cumulative report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def _read_json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _save_d0a_figure(d0a: dict[str, Any], path: Path) -> None:
    source = d0a["source_si_metrics"]
    public = d0a["public_no_fit_metrics"]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), constrained_layout=True)
    labels = ["dynamic I", "dynamic T", "R-T"]
    values = [source["dynamic_current_nrmse95"], source["dynamic_temperature_nrmse95"], source["rt_nrmse95"]]
    axes[0].bar(labels, values, color="#31688e")
    axes[0].axhline(1.0e-6, color="#b2182b", linestyle="--", label="semantic parity gate")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("NRMSE$_{95}$")
    axes[0].set_title("Author implementation vs SI rewrite")
    axes[0].legend(frameon=False)

    labels2 = ["5 vs 2.5 ns", "R-T no fit", "theory vs exp 11 V", "code vs exp 11 V"]
    values2 = [
        source["medium_vs_fine_dt_current_nrmse95"],
        public["rt_author_no_fit_nrmse95"],
        public["publisher_theory_vs_experiment_11v_nrmse95"],
        public["author_code_vs_experiment_11v_nrmse95"],
    ]
    colors = ["#b2182b", "#4d9221", "#762a83", "#762a83"]
    axes[1].bar(np.arange(len(labels2)), values2, color=colors)
    axes[1].axhline(0.01, color="#b2182b", linestyle="--", label="D0a dt gate")
    axes[1].set_xticks(np.arange(len(labels2)), labels2, rotation=22, ha="right")
    axes[1].set_ylabel("NRMSE$_{95}$")
    axes[1].set_title("No-refit numerical and public-trace checks")
    axes[1].legend(frameon=False)
    fig.suptitle("D0a source semantics pass, time-step convergence fails")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _save_n0_figure(mve: dict[str, Any], path: Path) -> None:
    run = mve["results"][0]
    history = run["training_history"]
    epochs = [item["epoch"] for item in history]
    losses = [item["loss"] for item in history]
    metrics = run["metrics"]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), constrained_layout=True)
    axes[0].plot(epochs, losses, marker="o", color="#31688e")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("total normalized loss")
    axes[0].set_title("Fixed single-seed MVE")
    names = ["port", "r_phi", "r_c", "r_T", "r_m"]
    ratios = [
        metrics["port_full_trace_nrmse95"] / 0.10,
        metrics["residual_rms"]["r_phi"] / 0.01,
        metrics["residual_rms"]["r_c"] / 0.01,
        metrics["residual_rms"]["r_T"] / 0.01,
        metrics["residual_rms"]["r_m"] / 0.01,
    ]
    axes[1].bar(names, ratios, color=["#b2182b" if value > 1.0 else "#4d9221" for value in ratios])
    axes[1].axhline(1.0, color="black", linestyle="--", label="pre-registered gate")
    axes[1].set_ylabel("metric / gate (pass ≤ 1)")
    axes[1].set_title("All N0 training gates fail")
    axes[1].legend(frameon=False)
    fig.suptitle("N0 contract passes; trained full-PINN evidence does not")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def build() -> dict[str, Any]:
    d0a = _read_json("outputs/tables/vo2_d0a_source_reproduction.json")
    contract = _read_json("outputs/tables/full_pinn_contract_v1.json")
    pilot = _read_json("outputs/tables/full_pinn_pilot_v1.json")
    mve = _read_json("outputs/tables/full_pinn_single_seed_mve_v1.json")
    d0a_figure = ROOT / "outputs/figures/vo2_d0a_source_semantics_v2.png"
    n0_figure = ROOT / "outputs/figures/full_pinn_n0_mve_gate_v1.png"
    _save_d0a_figure(d0a, d0a_figure)
    _save_n0_figure(mve, n0_figure)

    n0_metrics = mve["results"][0]["metrics"]
    summary = {
        "schema_version": "vo2_protocol_quotient_full_pinn_v2_summary_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_hypothesis_status": "not_tested_due_upstream_failures",
        "d0a": {
            "status": d0a["claim_status"],
            "gate_passed": d0a["gate_passed"],
            "failed_gate": "finest_time_step_convergence",
            "medium_vs_fine_dt_current_nrmse95": d0a["source_si_metrics"]["medium_vs_fine_dt_current_nrmse95"],
            "threshold": 0.01,
            "forward_evaluations_latest_run": d0a["forward_evaluations"],
            "round_run_count": 2,
            "round_forward_evaluations": 2 * int(d0a["forward_evaluations"]),
            "rerun_reason": "same fixed configuration rerun once to add complete run-manifest hashes",
            "sealed_13v_untouched": d0a["gate_results"]["sealed_13v_untouched"],
        },
        "d0b_d0c_d0d": {"status": "not_run_upstream_gate", "fit_lock_created": False, "13v_unsealed": False},
        "n0": {
            "contract_preflight": contract["status"],
            "manufactured_residual_rms": contract["metrics"]["manufactured_residual_rms"],
            "pilot_status": pilot["status"],
            "single_seed_mve_status": mve["status"],
            "claim_status": "failed_but_informative",
            "full_pinn_training_claim": "forbidden",
            "port_full_trace_nrmse95": n0_metrics["port_full_trace_nrmse95"],
            "residual_rms": n0_metrics["residual_rms"],
            "finite_outputs": n0_metrics["finite_outputs"],
            "physical_state_bounds": n0_metrics["physical_state_bounds"],
            "gpu_hours": 0.0,
            "training_wall_clock_s": sum(
                run["wall_clock_s"] for payload in (pilot, mve) for run in payload["results"]
            ),
        },
        "n1_n2_n3": {"status": "not_run_upstream_gate"},
        "preserved_claims": {"gamma_sub_safe_mainline": "qualified_supported", "p1": "failed_but_informative"},
        "figures": [d0a_figure.relative_to(ROOT).as_posix(), n0_figure.relative_to(ROOT).as_posix()],
    }
    summary_path = ROOT / "outputs/tables/vo2_protocol_quotient_full_pinn_v2_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    report = f"""# VO2 Protocol-Quotient and Full-PINN v2 Execution Report

Date: 2026-07-15

Delivery mode: `Q2_SCI_DELIVERY_MODE`

Base commit: `{d0a['base_sha']}`

## Executive disposition

The candidate hypothesis was **not tested** because two upstream credibility gates failed. This is not evidence against or for protocol-conditioned quotient inversion.

- D0a: `failed_but_informative`. Author-code/SI semantic parity passed, but the preregistered 5 ns versus 2.5 ns full-trace current convergence metric was `{d0a['source_si_metrics']['medium_vs_fine_dt_current_nrmse95']:.6f}`, above the `0.01` gate.
- D0b, D0c, D0d: not run. No repository-side calibration was performed, no fit lock was created, and 13 V numerical content remains sealed.
- N0 contract audit: `{contract['status']}`. The new versioned implementation contains state outputs `phi,c_v,T,m`, physical conductivity closure, four residuals, IC/BC, interface diagnostics, and the series-resistance port operator.
- N0 trained single-seed MVE: `failed_but_informative`. At 1200 fixed epochs, port NRMSE95 was `{n0_metrics['port_full_trace_nrmse95']:.6f}` versus `0.10`; residual RMS values were `{n0_metrics['residual_rms']}` versus `0.01` each.
- N1-N3: not run because N0 did not pass. No solver-sensitivity, PINN-sensitivity-fidelity, or inverse claim is available.

Budget accounting: D0a was executed twice with the identical fixed configuration (the second run added complete config/data-manifest hashes), for `12/60` forward evaluations in this round. N0 used `0` GPU-hours and `{sum(run['wall_clock_s'] for payload in (pilot, mve) for run in payload['results']):.1f}` s of training wall time, below its 12 h cap. No budget transferred between stages.

## D0a evidence

| Check | Result | Gate |
| --- | ---: | ---: |
| Author/SI dynamic-current NRMSE95 | `{d0a['source_si_metrics']['dynamic_current_nrmse95']:.3e}` | `<=1e-6` |
| Author/SI dynamic-temperature NRMSE95 | `{d0a['source_si_metrics']['dynamic_temperature_nrmse95']:.3e}` | `<=1e-6` |
| Author/SI R-T NRMSE95 | `{d0a['source_si_metrics']['rt_nrmse95']:.3e}` | `<=1e-6` |
| Event count | `{d0a['source_si_metrics']['author_dynamic_event_count']}` vs `{d0a['source_si_metrics']['repository_dynamic_event_count']}` | exact |
| 5 ns vs 2.5 ns current NRMSE95 | `{d0a['source_si_metrics']['medium_vs_fine_dt_current_nrmse95']:.6f}` | `<=0.01` **failed** |
| Author no-fit R-T NRMSE95 | `{d0a['public_no_fit_metrics']['rt_author_no_fit_nrmse95']:.6f}` | report only |
| Author code vs experiment 11 V NRMSE95 | `{d0a['public_no_fit_metrics']['author_code_vs_experiment_11v_nrmse95']:.6f}` | report only |

Evidence semantics: `source_paper_model_reproduction` only. It is not a repository refit, cross-voltage evaluation, independent external validation, or project-generated experiment.

## N0 evidence

The hard electrical BC error was `{contract['metrics']['hard_phi_boundary_max_normalized_error']:.3e}` and the normalized IC error was `{contract['metrics']['initial_condition_max_normalized_error']:.3e}`. The constant-equilibrium manufactured solution returned zero for all four normalized residuals.

The trained MVE remained outside every training gate despite finite values and valid state bounds. Frozen full fields were read only after optimization and are labeled `synthetic_gt`; the network output is `pinn_predicted`. No full field entered training.

## Claim disposition

| Candidate claim | Status | Allowed use |
| --- | --- | --- |
| Source code and SI rewrite have matching declared semantics at 10 ns | `qualified_supported` sub-result | Reproduction-method check only |
| D0a exact-source reproduction gate | `failed_but_informative` | Time-step sensitivity boundary |
| 13 V external holdout/validation | `forbidden` | 13 V was not read or evaluated |
| Complete 1D PINN implementation contract exists | `supported` as code/contract fact | Architecture description, not trained accuracy |
| Complete 1D PINN forward evidence passes frozen GT | `forbidden` | N0 MVE failed |
| PINN sensitivity fidelity or inverse recovery | `forbidden` | N1-N3 not run |
| Historical calibrated rank-1 `gamma_sub` inverse | `qualified_supported` | Preserved safe manuscript fallback |

## Files and reproducibility

- Configs: `configs/vo2_d0a_exact_source_v2.yaml`, `configs/full_pinn_architecture_v1.yaml`.
- Code: `src/pinnpcm/external_data/vo2_zhang.py`, `src/pinnpcm/physics/vo2_thermal_neuristor.py`, `src/pinnpcm/pinn/full_pinn_1d.py`, `src/pinnpcm/pinn/full_residuals_1d.py`.
- Machine evidence: `outputs/tables/vo2_d0a_source_reproduction.json`, `outputs/tables/vo2_d0a_source_discrepancies.csv`, `outputs/tables/full_pinn_contract_v1.json`, `outputs/tables/full_pinn_pilot_v1.json`, `outputs/tables/full_pinn_single_seed_mve_v1.json`.
- Figures: `{d0a_figure.relative_to(ROOT).as_posix()}`, `{n0_figure.relative_to(ROOT).as_posix()}`.
- External raw archives and generated checkpoints/NPZ remain local and ignored; lightweight provenance, licenses, hashes, configs, code, tests, summaries, and figures are tracked.

Reproduction commands (PowerShell, repository root):

```powershell
.\\.venv\\Scripts\\python.exe scripts\\prepare_vo2_d0_sources.py --config configs\\vo2_d0a_exact_source_v2.yaml --quarantine-13v
.\\.venv\\Scripts\\python.exe scripts\\run_vo2_d0a_exact_source.py --config configs\\vo2_d0a_exact_source_v2.yaml
.\\.venv\\Scripts\\python.exe scripts\\audit_full_pinn_contract.py --config configs\\full_pinn_architecture_v1.yaml
.\\.venv\\Scripts\\python.exe scripts\\train_full_pinn_1d.py --config configs\\full_pinn_architecture_v1.yaml --pilot
.\\.venv\\Scripts\\python.exe scripts\\train_full_pinn_1d.py --config configs\\full_pinn_architecture_v1.yaml --single-seed-mve
.\\.venv\\Scripts\\python.exe scripts\\build_vo2_d0_evidence.py
.\\.venv\\Scripts\\python.exe -m pytest -q
```

Both training commands intentionally exit non-zero when the recorded gate fails. Do not continue to N1-N3 after that exit.

## Failure boundary and next single priority

The shortest next priority is a bounded N0 numerical diagnosis that separates collocation generalization error from residual scaling and bilayer-interface error, using the same frozen GT and unchanged gates. It must not proceed to inverse work until at least 2/3 fixed seeds pass. D0 can be revisited only with a preregistered stable integration policy that resolves the current time-step failure without fitting public traces.
"""
    report_path = ROOT / "docs/codex_reports/vo2_protocol_quotient_full_pinn_v2_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))

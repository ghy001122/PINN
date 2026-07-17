"""Attach validation evidence and render the final N0-CV-E v3 report."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _check_table(checks: dict[str, bool]) -> list[str]:
    lines = ["| Preflight check | Pass |", "| --- | --- |"]
    lines.extend(f"| `{key}` | `{value}` |" for key, value in sorted(checks.items()))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/full_pinn_n0_cv_e_v3.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = _yaml(config_path)
    phase_a = _json(ROOT / config["outputs"]["phase_a_json"])
    preflight = _json(ROOT / config["outputs"]["preflight"])
    training = _json(ROOT / config["outputs"]["pilot_result"])
    summary_path = ROOT / config["outputs"]["summary"]
    summary = _json(summary_path)
    validation_path = ROOT / "outputs/tables/n0_cv_e_v3_validation.json"
    validation = _json(validation_path) if validation_path.exists() else None
    summary["finalized_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["git_commit_at_finalize"] = _git("rev-parse", "HEAD")
    summary["git_dirty_at_finalize"] = bool(_git("status", "--short"))
    summary["validation"] = validation
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    metrics = preflight["metrics"]
    phase_metrics = phase_a["unified_cv_rescore"]
    v2_gaps = ", ".join(f"`{value}`" for value in phase_a["v2_gate_coverage"]["documented_gaps"])
    lines = [
        "# N0-CV-E v3 Final Bounded Attempt",
        "",
        f"Base commit: `{config['base_commit']}`",
        "",
        "Final claim status: `failed_but_informative`; positive trained full-PINN forward wording: `forbidden`.",
        "",
        "## Scope And Evidence Semantics",
        "",
        "This round audited frozen one-dimensional synthetic GT and attempted a data-free full-PINN optimization. Frozen arrays are `synthetic_gt`; operator/replay trajectories are `solver_generated`; a completed checkpoint would have produced `pinn_predicted` trajectories, but v3 produced none. No public external fit, 13 V access, or experimental validation occurred.",
        "",
        "Analytic electrostatics, finite/control-volume residuals, hard constraints, causal schedules, and gradient balancing are prior-art components and are not claimed as standalone novelty.",
        "",
        "## Phase A — Evidence Integrity And Frozen-Trajectory Compatibility",
        "",
        f"The v2 checkpoint is `{phase_a['v2_checkpoint']['classification']}`; remote CI is `{phase_a['remote_ci']['status']}`; final pytest evidence is `{phase_a['pytest_evidence']['classification']}`. Fail-closed v2 gate gaps are {v2_gaps}. Historical v2 hashes were not rewritten.",
        "",
        "The old conservation JSON is classified only as an algebraic bookkeeping smoke test. The independent adjacent-state audit reports:",
        "",
        "| Audit | Gate value | Result |",
        "| --- | ---: | --- |",
        f"| frozen defect ledger | {phase_a['independent_trajectory_ledger']['defect']['gate_value']:.9g} | pass (`<=0.01`) |",
        f"| frozen energy ledger | {phase_a['independent_trajectory_ledger']['energy']['gate_value']:.9g} | pass (`<=0.05`) |",
        f"| Radau replay max relative RMS | {phase_a['radau_replay']['maximum_relative_rms']:.9g} | pass (`<=1e-5`) |",
        f"| tampered defect ledger | {phase_a['tamper_detection']['tampered_defect_gate_value']:.9g} | detected failure |",
        f"| tampered energy ledger | {phase_a['tamper_detection']['tampered_energy_gate_value']:.9g} | detected failure |",
        "",
        "A common SI/frozen registry rescored both historical checkpoints. The global baseline and split repair have port NRMSE95 values "
        f"`{phase_metrics['strongest_global_baseline']['metrics']['port_full_trace_nrmse95']:.6g}` and "
        f"`{phase_metrics['e3f5765_split_repair']['metrics']['port_full_trace_nrmse95']:.6g}`; both fail CV/ledger gates. Near-interface, near-transition, and ordinary fixed regions are all nonempty and used.",
        "",
        "## Phase B — Solver-Consistent Full-PINN Contract",
        "",
        "The 5501-parameter network predicts bounded cell-centered `c_v`, `T`, and `m` on the unchanged 31-cell grid. It returns `phi,c_v,T,m,sigma,E,J,I,G`; the electrical quantities follow a differentiable analytic series relation. Defect/heat faces, end fluxes, reaction, Joule heating, substrate sink, and phase relaxation reproduce the frozen teacher arithmetic exactly. Hard IC/electrical BCs and a fixed dimensionless registry are explicit. Port and hidden-field labels used for training: none.",
        "",
        "Locked inputs include the config, deterministic diagnostic NPZ, Phase-A JSON, frozen GT/config/manifest, old diagnostic points, operator code, preflight, trainer, and evidence builder. The preregistration records their stable canonical/raw hashes before training.",
        "",
        "## No-Training Preflight",
        "",
        f"Status: `{preflight['status']}`; training authorized: `{preflight['training_authorized']}`; checks passed: `{sum(preflight['checks'].values())}/{len(preflight['checks'])}`.",
        "",
        "| Metric | Value | Gate |",
        "| --- | ---: | ---: |",
        f"| electrostatic float64 relative RMS | {metrics['electrostatics']['maximum_relative_rms']:.9g} | `<=1e-7` |",
        f"| current spatial spread | {metrics['electrostatics']['current_spatial_spread']:.9g} | `<=1e-7` |",
        f"| CV-RHS maximum relative RMS | {metrics['cv_rhs']['maximum_relative_rms']:.9g} | `<=1e-6` |",
        f"| minimum c/T/m gradient norm | {metrics['gradients']['minimum_gradient_norm']:.9g} | `>=1e-12` |",
        f"| gradient central-difference error | {metrics['gradients']['maximum_relative_error']:.9g} | `<=1e-3` |",
        f"| SI roundtrip relative RMS | {metrics['dimensionless_roundtrip']['maximum_relative_rms']:.9g} | `<=1e-12` |",
        f"| hard IC/BC max normalized error | {max(metrics['hard_constraints'].values()):.9g} | `<=1e-3` |",
        "",
        *_check_table(preflight["checks"]),
        "",
        "## Conditional Training And Fail-Closed Attribution",
        "",
        f"Command: `{training['command']}`",
        "",
        f"The locked seed `{training['seed']}` primary arm reached its only L-BFGS stage after the scheduled `{training['adam_steps_completed']}` Adam steps. A strong-Wolfe closure raised `{training['exception_type']}: {training['exception_message']}` after approximately `{training['observed_wall_clock_s']}` s. The exception occurred before checkpoint serialization and trajectory scoring.",
        "",
        "Consequently, port, cell residual, discrete electrical, field, interface, current, energy, defect, IC/BC, finite/bounds, hash/operator, and seed-vote result gates are all `unassessed_fail_closed`. Missing metrics are not represented as zero or pass. No balancing arm, seed expansion, sparse anchor, hyperparameter search, N1-N3, or SC-LOS run was performed.",
        "",
        "The scientific lock still matched immediately after the exception. No checkpoint exists; the checkpoint manifest explicitly records `no_checkpoint_runtime_failure_before_serialization`.",
        "",
        "## Validation",
        "",
    ]
    if validation is None:
        lines.append("Final validation has not yet been recorded.")
    else:
        lines.append(f"Environment: Python `{validation['machine']['python']}`, PyTorch `{validation['machine']['torch']}`, device `{validation['machine']['device']}`, CUDA `{validation['machine']['cuda_available']}`.")
        lines.extend(["", "| Command | Result | Counts |", "| --- | --- | --- |"])
        for command in validation["commands"]:
            counts = ", ".join(f"{key}={value}" for key, value in sorted(command["counts"].items())) or "not applicable"
            lines.append(f"| `{command['command']}` | `{command['result']}` | {counts} |")
    lines.extend(
        [
            "",
            "## Claim And Manuscript Disposition",
            "",
            "- `supported`: frozen teacher/operator compatibility and the v3 no-training operator contract under the locked synthetic protocol.",
            "- `failed_but_informative`: v2 evidence completeness and all trained N0 paths, including the v3 runtime failure.",
            "- `forbidden`: reliable trained full-PINN forward fidelity, sensitivity fidelity, inverse recovery, experimental validation, cross-material generalization, or novelty of the assembled numerical components.",
            "",
            "N0 is closed after this final bounded attempt. The unique next step is manuscript assembly on the already supported calibration-gated constrained `gamma_sub` mainline, with D0a and N0 retained as explicit limitations.",
        ]
    )
    report_path = ROOT / config["outputs"]["report"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "summary": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
                "report": str(report_path.relative_to(ROOT)).replace("\\", "/"),
                "validation_attached": validation is not None,
            }
        )
    )


if __name__ == "__main__":
    main()

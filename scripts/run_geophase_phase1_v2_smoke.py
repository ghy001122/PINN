from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    derive_nominal_s2_source_scale,
    effective_vo2_closure_from_v2_config,
    s2_uniform_mode_identities,
)
from pinnpcm.solvers.geophase_phase1_v2_fvm import (
    solve_s2_thermal_backward_euler,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    advance_s2_backward_euler,
    initial_s2_state,
    simulate_s2_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
PREREG_PATH = ROOT / "outputs" / "tables" / "geophase_phase1_v2" / "preregistration.json"
OUTPUT_DIR = ROOT / "outputs" / "tables" / "geophase_phase1_v2"
SUMMARY_PATH = OUTPUT_DIR / "s2_smoke_summary.json"
LEDGER_PATH = OUTPUT_DIR / "s2_smoke_ledgers.csv"
REPORT_PATH = ROOT / "docs" / "codex_reports" / "geophase_phase1_v2_s2_readiness.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a mapping")
    return value


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _relative_error(candidate: float, reference: float) -> float:
    return abs(candidate - reference) / max(abs(reference), 1.0e-30)


def _ledger_rows(case_id: str, result: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_time = 0.0
    for index, step in enumerate(result.steps, start=1):
        dt = step.state.time_s - previous_time
        previous_time = step.state.time_s
        rows.append(
            {
                "case_id": case_id,
                "step_index": index,
                "time_s": step.state.time_s,
                "dt_s": dt,
                "device_voltage_V": step.state.device_voltage_V,
                "terminal_current_A": step.electrical.source_current_A,
                "maximum_temperature_K": float(np.max(step.state.temperature_K)),
                "domain_mean_s": float(np.mean(step.state.conductive_state)),
                "domain_mean_b": float(np.mean(step.state.branch_memory)),
                "nonlinear_method": step.nonlinear.method,
                "thermal_relative_residual": step.ledgers.thermal.relative_residual,
                "circuit_relative_residual": step.ledgers.circuit.relative_residual,
                "combined_relative_residual": step.ledgers.combined.relative_residual,
                "device_power_relative_residual": step.ledgers.device_power.relative_residual,
                "lateral_matrix_face_relative_mismatch": step.lateral_flux.matrix_face_relative_mismatch,
                "lateral_matrix_face_roundoff_ratio": step.lateral_flux.matrix_face_roundoff_ratio,
                "lateral_global_residual_W": step.lateral_flux.face_to_cell_global_residual_W,
            }
        )
    return rows


def _case_summary(case_id: str, result: Any, gates: dict[str, Any]) -> dict[str, Any]:
    rows = _ledger_rows(case_id, result)
    maxima = {
        "thermal": max((row["thermal_relative_residual"] for row in rows), default=0.0),
        "circuit": max((row["circuit_relative_residual"] for row in rows), default=0.0),
        "combined": max((row["combined_relative_residual"] for row in rows), default=0.0),
        "device_power": max((row["device_power_relative_residual"] for row in rows), default=0.0),
        "lateral_matrix_face": max((row["lateral_matrix_face_relative_mismatch"] for row in rows), default=0.0),
        "lateral_matrix_face_roundoff": max((row["lateral_matrix_face_roundoff_ratio"] for row in rows), default=0.0),
    }
    ledgers_pass = bool(
        maxima["thermal"] <= float(gates["thermal_ledger_relative_residual_max"])
        and maxima["circuit"] <= float(gates["circuit_ledger_relative_residual_max"])
        and maxima["combined"] <= float(gates["combined_ledger_relative_residual_max"])
        and maxima["device_power"] <= float(gates["device_power_identity_relative_residual_max"])
        and (
            maxima["lateral_matrix_face"] <= 1.0e-10
            or maxima["lateral_matrix_face_roundoff"] <= 1.0
        )
    )
    final = result.steps[-1].state if result.steps else None
    finite = bool(
        final is not None
        and np.isfinite(final.temperature_K).all()
        and np.isfinite(final.conductive_state).all()
        and np.isfinite(final.branch_memory).all()
        and np.isfinite(final.device_voltage_V)
    )
    return {
        "case_id": case_id,
        "nonvoting": True,
        "completed": bool(result.completed),
        "stop_reason": result.stop_reason,
        "accepted_steps": result.diagnostics.accepted_steps,
        "rejected_steps": result.diagnostics.rejected_steps,
        "fallback_steps": result.diagnostics.fallback_steps,
        "maximum_transition_increment": result.diagnostics.maximum_transition_increment,
        "maximum_ledger_residuals": maxima,
        "finite": finite,
        "implementation_smoke_pass": bool(result.completed and finite and ledgers_pass),
        "final_maximum_temperature_K": None if final is None else float(np.max(final.temperature_K)),
        "final_domain_mean_s": None if final is None else float(np.mean(final.conductive_state)),
    }


def build_smoke_evidence(config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if prereg["config_sha256"] != _sha256(CONFIG_PATH):
        raise RuntimeError("Phase 1-v2 config hash no longer matches preregistration")
    if prereg["formal_execution_count"] != 0:
        raise RuntimeError("smoke cannot run after formal execution is consumed")

    grid = build_geophase_grid(config)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    scale = derive_nominal_s2_source_scale(config)
    identities = s2_uniform_mode_identities(grid, fields)
    preflight_gates = config["analytic_source_scale_preflights"]
    source_preflight_pass = bool(
        scale["nominal_memory_coefficient_J_K"] > 0.0
        and identities["capacity_relative_error"]
        <= float(preflight_gates["area_integrated_explicit_plus_memory_coefficient_relative_error_max"])
        and identities["conductance_relative_error"]
        <= float(preflight_gates["area_integrated_dc_thermal_conductance_relative_error_max"])
    )
    if not source_preflight_pass:
        raise RuntimeError("S2 analytic source-scale preflight failed")

    protocols = config["formal_protocols"]["protocols"]
    smoke_protocols = {
        "SMOKE-S2-ZERO": protocols["zero_drive"],
        "SMOKE-S2-9V": protocols["quiescent_9V"],
        "SMOKE-S2-12P5V": protocols["transition_probe_12p5V"],
        "SMOKE-S2-15V": protocols["high_bias_15V"],
    }
    cases: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    for case_id, protocol in smoke_protocols.items():
        result = simulate_s2_protocol(
            initial_s2_state(grid, closure, fields, config),
            protocol=protocol,
            grid=grid,
            closure=closure,
            fields=fields,
            config=config,
            time_divisor=1,
            final_time_s=4.0e-8,
            maximum_accepted_steps=8,
        )
        cases.append(_case_summary(case_id, result, config["gates"]))
        ledger_rows.extend(_ledger_rows(case_id, result))

    # A separately named one-step ledger case makes the audit independent of
    # whether a literature-trend smoke later changes duration.
    ledger_step = advance_s2_backward_euler(
        initial_s2_state(grid, closure, fields, config),
        input_voltage_V=1.0,
        dt_s=1.0e-8,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
    )
    ledger_result = type("LedgerSmokeResult", (), {})()
    ledger_result.steps = (ledger_step,)
    ledger_result.completed = True
    ledger_result.stop_reason = "single_locked_backward_euler_step"
    ledger_result.diagnostics = type(
        "LedgerSmokeDiagnostics",
        (),
        {
            "accepted_steps": 1,
            "rejected_steps": 0,
            "fallback_steps": int(
                ledger_step.nonlinear.method == "fail_closed_fixed_point_fallback"
            ),
            "maximum_transition_increment": max(
                float(np.max(np.abs(ledger_step.state.conductive_state - initial_s2_state(grid, closure, fields, config).conductive_state))),
                float(np.max(np.abs(ledger_step.state.branch_memory - initial_s2_state(grid, closure, fields, config).branch_memory))),
            ),
        },
    )()
    cases.append(_case_summary("SMOKE-S2-LEDGER", ledger_result, config["gates"]))
    ledger_rows.extend(_ledger_rows("SMOKE-S2-LEDGER", ledger_result))

    # Forced-uniform manufactured update. The source is assembled from the
    # target state, not recovered from the solver output.
    dt = 1.0e-8
    delta = 1.0e-2
    old = np.full(grid.shape, fields.ambient_temperature_K)
    target = old + delta
    source = (
        fields.effective_areal_capacity_J_m2K * delta / dt
        + fields.vertical_conductance_W_m2K * delta
    )
    manufactured = solve_s2_thermal_backward_euler(
        grid,
        fields,
        old,
        np.zeros(grid.shape),
        dt,
        external_areal_source_W_m2=source,
    )
    manufactured_error = float(
        np.linalg.norm(manufactured - target) / max(np.linalg.norm(target), 1.0e-30)
    )
    cases.append(
        {
            "case_id": "SMOKE-S2-MANUFACTURED-THERMAL",
            "nonvoting": True,
            "manufactured_relative_l2": manufactured_error,
            "implementation_smoke_pass": manufactured_error
            <= float(config["gates"]["manufactured_thermal_relative_l2_max"]),
        }
    )

    # Short coarse/fine parity is diagnostic only; no formal convergence vote.
    coarse = cases[2]
    fine_grid = build_geophase_grid(config, spatial_level=2)
    fine_fields = build_s2_thermal_fields(fine_grid, config)
    fine_result = simulate_s2_protocol(
        initial_s2_state(fine_grid, closure, fine_fields, config),
        protocol=protocols["transition_probe_12p5V"],
        grid=fine_grid,
        closure=closure,
        fields=fine_fields,
        config=config,
        time_divisor=1,
        final_time_s=2.0e-8,
        maximum_accepted_steps=4,
    )
    fine_final = fine_result.steps[-1].state
    coarse_reference_result = simulate_s2_protocol(
        initial_s2_state(grid, closure, fields, config),
        protocol=protocols["transition_probe_12p5V"],
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        time_divisor=1,
        final_time_s=2.0e-8,
        maximum_accepted_steps=4,
    )
    coarse_final = coarse_reference_result.steps[-1].state
    coarse_fine = {
        "case_id": "SMOKE-S2-COARSE-FINE",
        "nonvoting": True,
        "coarse_final_mean_temperature_K": float(np.mean(coarse_final.temperature_K)),
        "fine_final_mean_temperature_K": float(np.mean(fine_final.temperature_K)),
        "mean_temperature_relative_difference": _relative_error(
            float(np.mean(fine_final.temperature_K - fields.ambient_temperature_K)),
            float(np.mean(coarse_final.temperature_K - fields.ambient_temperature_K)),
        ),
        "coarse_final_mean_s": float(np.mean(coarse_final.conductive_state)),
        "fine_final_mean_s": float(np.mean(fine_final.conductive_state)),
        "implementation_smoke_pass": bool(
            coarse_reference_result.completed
            and fine_result.completed
            and np.isfinite(fine_final.temperature_K).all()
        ),
    }
    cases.append(coarse_fine)
    ledger_rows.extend(_ledger_rows("SMOKE-S2-COARSE-FINE-L1", coarse_reference_result))
    ledger_rows.extend(_ledger_rows("SMOKE-S2-COARSE-FINE-L2", fine_result))

    all_pass = all(bool(case["implementation_smoke_pass"]) for case in cases)
    summary = {
        "task_id": "Q2_PHASE1_V2_S2_NONVOTING_SMOKE",
        "schema_version": "geophase_phase1_v2_s2_smoke_v1",
        "status": "completed_nonvoting_smoke_pass" if all_pass else "failed_nonvoting_smoke",
        "evidence_type": "nonvoting_implementation_smoke",
        "config_sha256": _sha256(CONFIG_PATH),
        "preregistration_status": prereg["status"],
        "formal_execution_count": 0,
        "formal_execution_consumed": False,
        "formal_case_artifacts_generated": False,
        "source_scale": scale,
        "uniform_mode_identities": identities,
        "source_scale_preflight_pass": source_preflight_pass,
        "cases": cases,
        "all_smoke_cases_pass": all_pass,
        "S2_nominal_unchanged": True,
        "scientific_gate_vote": False,
        "implementation_repair_count": 1,
        "implementation_repair_record": "outputs/tables/geophase_phase1_v2/s2_smoke_implementation_repair.json",
        "allowed_claim": "Phase 1-v2 S2 implementation completed its bounded non-voting smoke checks.",
        "forbidden_claims": [
            "Phase 1-v2 formal gates passed",
            "Qiu device reproduced or calibrated",
            "experimental validation completed",
            "Phase 2 or PINN unlocked",
        ],
    }
    return summary, ledger_rows


def _csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("S2 smoke ledger table cannot be empty")
    fieldnames = list(rows[0])
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _report(summary: dict[str, Any]) -> str:
    lines = [
        "# Phase 1-v2 S2 non-voting readiness smoke",
        "",
        f"Status: `{summary['status']}`",
        "",
        "Implementation repair: `1/1` authorized bounded repair. The first",
        "attempt exposed a zero-signal relative-denominator defect in the",
        "matrix/face audit; the physical equations and scientific gates were unchanged.",
        "",
        "This is implementation smoke only. It consumed no formal execution,",
        "created no formal case artifact, and does not unlock Phase 2 or PINN training.",
        "",
        "## Cases",
        "",
        "| Case | Pass | Key diagnostic |",
        "|---|---:|---|",
    ]
    for case in summary["cases"]:
        diagnostic = (
            f"manufactured L2={case['manufactured_relative_l2']:.3e}"
            if "manufactured_relative_l2" in case
            else (
                f"mean-T difference={case['mean_temperature_relative_difference']:.3e}"
                if "mean_temperature_relative_difference" in case
                else f"accepted={case['accepted_steps']}, rejected={case['rejected_steps']}"
            )
        )
        lines.append(
            f"| `{case['case_id']}` | {str(case['implementation_smoke_pass']).lower()} | {diagnostic} |"
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            summary["allowed_claim"],
            "",
            "The formal 63-item campaign remains blocked and `formal_execution_count` remains zero.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 1-v2 bounded S2 smoke only.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = _load_yaml(CONFIG_PATH)
    summary, rows = build_smoke_evidence(config)
    csv_text = _csv_text(rows)
    json_text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    report_text = _report(summary)
    if args.check:
        if LEDGER_PATH.read_text(encoding="utf-8") != csv_text:
            raise SystemExit("S2 smoke ledger artifact is stale")
        if SUMMARY_PATH.read_text(encoding="utf-8") != json_text:
            raise SystemExit("S2 smoke summary artifact is stale")
        if REPORT_PATH.read_text(encoding="utf-8") != report_text:
            raise SystemExit("S2 smoke report artifact is stale")
        return
    _atomic_text(LEDGER_PATH, csv_text)
    _atomic_text(SUMMARY_PATH, json_text)
    _atomic_text(REPORT_PATH, report_text)


if __name__ == "__main__":
    main()

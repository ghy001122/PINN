"""Run Phase 1 Checkpoint A only; the formal campaign is intentionally absent.

This entry point creates the locked 96-case manifest, source-scale preflights,
environment identity, and bounded smoke evidence.  It cannot increment the
formal execution count or run any formal case.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import scipy
import yaml

from pinnpcm.evaluation.geophase_phase1_gates import (
    build_formal_case_inventory,
    sha256_file,
    source_scale_preflight,
    substrate_depth_truncation_metrics,
)
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.vertical_thermal_memory import initial_passive_ladder
from pinnpcm.physics.vo2_effective_conductivity import EffectiveVO2Closure
from pinnpcm.solvers.geophase_2p5d_implicit import (
    advance_backward_euler,
    initial_state,
    simulate_adaptive_protocol,
    simulate_decoupled_copies,
)
from pinnpcm.solvers.vertical_multilayer_reference import (
    build_normalized_vertical_references,
)


ROOT = Path(__file__).resolve().parents[1]


def _git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    preferred = [
        "case_id",
        "case_group",
        "group_index",
        "formal_status",
        "evidence_type",
    ]
    discovered = {key for row in rows for key in row}
    columns = [key for key in preferred if key in discovered]
    columns.extend(sorted(discovered - set(columns)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _ledger_rows(case_id: str, result: object, *, voting: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    balances = (
        result.thermal_balance,
        result.circuit_balance,
        result.combined_balance,
        result.device_power_balance,
    )
    for balance in balances:
        rows.append(
            {
                "case_id": case_id,
                "ledger": balance.name,
                "relative_residual": balance.relative_residual,
                "signed_residual_W": balance.signed_residual_W,
                "input_power_W": balance.input_power_W,
                "accounted_power_W": balance.accounted_power_W,
                "voting": voting,
                "evidence_type": "checkpoint_a_smoke_nonclaim_evidence",
            }
        )
    return rows


def _assert_smoke_ledgers(config: dict, rows: Iterable[dict[str, object]]) -> None:
    thresholds = {
        "thermal": float(config["gates"]["thermal_ledger_relative_residual_max"]),
        "circuit": float(config["gates"]["circuit_ledger_relative_residual_max"]),
        "combined_electrothermal": float(
            config["gates"]["combined_ledger_relative_residual_max"]
        ),
        "device_power_identity": float(
            config["gates"]["device_power_identity_relative_residual_max"]
        ),
    }
    for row in rows:
        if bool(row["voting"]) and float(row["relative_residual"]) > thresholds[str(row["ledger"])]:
            raise RuntimeError(
                f"smoke ledger {row['ledger']} failed at {row['relative_residual']}"
            )


def run_checkpoint_a(config_path: Path, preregistration_sha: str) -> dict[str, object]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    execution = config["execution_contract"]
    if int(execution["formal_execution_count"]) != 0:
        raise RuntimeError("Checkpoint A requires formal_execution_count == 0")
    if not bool(execution["checkpoint_a_must_stop_before_formal_campaign"]):
        raise RuntimeError("Checkpoint A stop boundary is not locked")
    if len(preregistration_sha) != 40:
        raise ValueError("a full 40-character preregistration SHA is required")
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    if branch == "main":
        raise RuntimeError("Checkpoint A implementation must not run from main")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", preregistration_sha, head],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("preregistration SHA is not an ancestor of the implementation")

    config_hash = sha256_file(config_path)
    references = build_normalized_vertical_references(config)
    preflight = source_scale_preflight(config, normalized_references=references)
    inventory = build_formal_case_inventory(config)
    depth_audit = substrate_depth_truncation_metrics(config)

    grid = build_geophase_grid(config, nx_override=10, ny_override=5)
    ladders = {
        region: initial_passive_ladder(
            region_id=region,
            order=3,
            total_capacity_J_m2K=reference.total_capacity_J_m2K,
            dc_conductance_W_m2K=reference.dc_conductance_W_m2K,
        )
        for region, reference in references.references.items()
    }
    closure = EffectiveVO2Closure.from_config(config)
    equilibrium = initial_state(grid, closure, ladders, config)
    zero = advance_backward_euler(
        equilibrium,
        input_voltage_V=0.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    low = advance_backward_euler(
        equilibrium,
        input_voltage_V=1.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    adaptive = simulate_adaptive_protocol(
        equilibrium,
        input_voltage=lambda _time: 1.0,
        final_time_s=2.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    copy_a, copy_b = simulate_decoupled_copies(
        equilibrium,
        equilibrium,
        input_voltage_a_V=1.0,
        input_voltage_b_V=1.0,
        dt_s=1.0e-9,
        grid=grid,
        closure=closure,
        ladders=ladders,
        config=config,
    )
    copy_error = float(
        np.max(np.abs(copy_a.state.temperature_K - copy_b.state.temperature_K))
    )
    if copy_error > float(config["gates"]["dual_copy_symmetry_relative_error_max"]):
        raise RuntimeError("zero-coupled duplicate smoke lost label symmetry")
    zero_drift = float(np.max(np.abs(zero.state.temperature_K - equilibrium.temperature_K)))
    if zero_drift > float(config["gates"]["zero_drive_temperature_drift_K_max"]):
        raise RuntimeError("zero-drive smoke exceeded its analytic drift gate")

    ledger_rows = _ledger_rows("smoke_zero_drive", zero, voting=False)
    ledger_rows.extend(_ledger_rows("smoke_low_drive", low, voting=True))
    _assert_smoke_ledgers(config, ledger_rows)

    output_paths = config["outputs"]
    preregistration_path = ROOT / output_paths["preregistration"]
    summary_path = ROOT / output_paths["checkpoint_a_summary"]
    ledger_path = ROOT / output_paths["checkpoint_a_ledger_csv"]
    environment_path = ROOT / output_paths["environment_manifest"]
    inventory_path = ROOT / output_paths["case_inventory_csv"]
    preregistration = {
        "task_id": config["task_id"],
        "schema_version": config["schema_version"],
        "preregistration_sha": preregistration_sha,
        "checkpoint_a_smoke_start_head": head,
        "implementation_commit": "SELF",
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": config_hash,
        "formal_execution_limit": int(execution["formal_execution_limit"]),
        "formal_execution_count": 0,
        "formal_campaign_executed": False,
        "fresh_user_authorization_for_checkpoint_b": False,
        "case_inventory_count": len(inventory),
        "claim_status": "forbidden_pending_formal_campaign",
    }
    summary = {
        "task_id": config["task_id"],
        "status": "checkpoint_a_complete_formal_campaign_not_run",
        "evidence_type": "implementation_behavior_tests_and_smoke_only",
        "formal_execution_count": 0,
        "formal_campaign_executed": False,
        "formal_case_results_generated": 0,
        "formal_case_manifest_count": len(inventory),
        "source_scale_preflight": preflight,
        "checkpoint_a_nonvoting_prior_audit": {
            "substrate_depth": depth_audit,
            "formal_gate_evaluated": False,
            "contact_overlap_qoi_audit": "implemented_behavior_tested_formal_values_not_generated",
            "source_envelope_noise_audit": "implemented_behavior_tested_formal_values_not_generated",
        },
        "smoke": {
            "grid_nx": grid.nx,
            "grid_ny": grid.ny,
            "k_order": 3,
            "zero_drive_temperature_drift_K": zero_drift,
            "low_drive_max_temperature_K": float(np.max(low.state.temperature_K)),
            "low_drive_device_voltage_V": low.state.device_voltage_V,
            "low_drive_device_current_A": low.electrical.source_current_A,
            "dual_copy_temperature_absolute_error_K": copy_error,
            "adaptive_protocol": {
                "accepted_steps": adaptive.diagnostics.accepted_steps,
                "rejected_steps": adaptive.diagnostics.rejected_steps,
                "transition_rejections": adaptive.diagnostics.transition_rejections,
                "nonlinear_rejections": adaptive.diagnostics.nonlinear_rejections,
                "minimum_accepted_step_s": adaptive.diagnostics.minimum_accepted_step_s,
                "maximum_accepted_step_s": adaptive.diagnostics.maximum_accepted_step_s,
                "maximum_transition_increment": adaptive.diagnostics.maximum_transition_increment,
            },
            "nonlinear_methods": [
                zero.nonlinear.method,
                low.nonlinear.method,
                copy_a.nonlinear.method,
                copy_b.nonlinear.method,
            ],
        },
        "nominal_metallic_endmember_resistance_ohm": float(
            config["parameter_contract"]["vo2_conductivity"][
                "source_metallic_resistance_ohm"
            ]
        ),
        "qiu_s7_dynamic_channel_correction_in_formal_matrix": False,
        "nonzero_dual_device_coupling": "forbidden",
        "reported_500nm_placement_semantics": "unresolved_and_nonvoting_in_phase1",
        "scientific_gate_disposition": "not_evaluated_until_checkpoint_b",
        "claim_status": "forbidden_pending_formal_campaign",
        "next_action": "stop_and_wait_for_explicit_checkpoint_b_authorization",
    }
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "branch": branch,
        "head_when_checkpoint_a_smoke_started": head,
        "preregistration_sha": preregistration_sha,
        "config_sha256": config_hash,
        "cpu_only": True,
        "formal_execution_count": 0,
    }
    _write_json(preregistration_path, preregistration)
    _write_json(summary_path, summary)
    _write_csv(ledger_path, ledger_rows)
    _write_json(environment_path, environment)
    _write_csv(inventory_path, inventory)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml",
    )
    parser.add_argument("--preregistration-sha", required=True)
    parser.add_argument(
        "--checkpoint",
        choices=["a"],
        default="a",
        help="Only Checkpoint A exists; formal execution is intentionally unavailable.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    config_path = arguments.config.resolve()
    summary = run_checkpoint_a(config_path, arguments.preregistration_sha)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

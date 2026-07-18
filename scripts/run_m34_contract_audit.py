"""Run the preregistered M34 low-compute audit exactly once."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from pinnpcm.pinn.m34_contract_audit import (
    build_m33_model,
    gradient_contract_audit,
    ledger_contract_audit,
    representability_smoke,
    toy_alm_benchmark,
)
from pinnpcm.pinn.n0_cv_evidence import raw_sha256, stable_file_hash


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _finite(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    return True


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output_path = ROOT / config["outputs"]["audit_summary"]
    if output_path.exists():
        raise RuntimeError("M34 audit result already exists; do not rerun it.")
    prereg_path = ROOT / config["outputs"]["preregistration"]
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    mismatches = {
        path: {"expected": expected, "actual": stable_file_hash(ROOT / path)}
        for path, expected in prereg["locked_files"].items()
        if stable_file_hash(ROOT / path) != expected
    }
    if mismatches:
        raise RuntimeError(f"M34 preregistration lock mismatch: {mismatches}")
    commit = _git("rev-parse", "HEAD")
    if commit == config["base_snapshot"]:
        raise RuntimeError("M34 audit code must be committed before execution.")
    if _git("status", "--short"):
        raise RuntimeError("M34 audit requires a clean committed worktree.")

    m33_config = yaml.safe_load((ROOT / config["frozen_inputs"]["m33_config"]).read_text(encoding="utf-8"))
    history = json.loads((ROOT / config["frozen_inputs"]["m33_history"]).read_text(encoding="utf-8"))
    with np.load(ROOT / config["frozen_inputs"]["diagnostic_dataset"], allow_pickle=False) as archive:
        arrays = {key: np.asarray(archive[key]) for key in archive.files}

    toy_rows = toy_alm_benchmark(config["alm_toy"])
    gradient_rows, gradient_summary = gradient_contract_audit(
        m33_config,
        config["gradient_audit"],
        ROOT / config["frozen_inputs"]["m33_checkpoint"],
        arrays,
        history,
    )
    model, gt, params, _ = build_m33_model(
        m33_config, ROOT / config["frozen_inputs"]["m33_checkpoint"], dtype=torch.float64
    )
    ledger_rows, ledger_summary = ledger_contract_audit(model, gt, params, config["ledger_audit"])
    capacity = representability_smoke(
        m33_config, config["representability_smoke"], ROOT / config["frozen_inputs"]["m33_checkpoint"]
    )

    _write_csv(ROOT / config["outputs"]["alm_toy_benchmark"], toy_rows)
    _write_csv(ROOT / config["outputs"]["gradient_geometry"], gradient_rows)
    _write_csv(ROOT / config["outputs"]["ledger_reconciliation"], ledger_rows)

    signed_rows = [row for row in toy_rows if row["method"] == "signed_vector_alm"]
    toy_pass = bool(
        signed_rows
        and max(row["constraint_abs"] for row in signed_rows) <= float(config["alm_toy"]["corrected_constraint_abs_max"])
        and max(row["dual_abs_error"] for row in signed_rows) <= float(config["alm_toy"]["corrected_dual_abs_error_max"])
    )
    parity = gradient_summary["coordinate_parity"]
    gradient_pass = bool(
        parity["nonzero_count"] >= int(config["gradient_audit"]["minimum_nonzero_coordinates"])
        and parity["all_nonzero_pass"]
        and all(parity["module_nonzero_counts"].values())
    )
    ledger_pass = bool(
        ledger_summary["maximum_training_independent_implementation_difference"]
        <= float(config["ledger_audit"]["implementation_parity_abs_max"])
    )
    contract = model.contract()
    architecture_pass = bool(
        contract["learned_cell_states"] == ["c_v", "T", "m"]
        and contract["explicit_face_flux_heads"] == ["q_c", "q_T"]
        and contract["hard_series_electrostatics"]
        and contract["hard_outer_flux_boundaries"]
    )
    parameter_pass = abs(float(contract["relative_parameter_difference"])) <= float(config["corrected_run"]["parameter_count_relative_difference_max"])
    input_hashes = {path: stable_file_hash(ROOT / path) for path in prereg["locked_files"]}
    frozen_pass = not mismatches and raw_sha256(ROOT / config["frozen_inputs"]["m33_checkpoint"]) == prereg["checkpoint_raw_sha256"]
    controls_pass = bool(
        config["corrected_run"]["hidden_field_labels"] == "forbidden"
        and config["corrected_run"]["port_labels"] == "forbidden"
        and config["corrected_run"]["optimizer_search"] == "forbidden"
        and config["corrected_run"]["seed_expansion"] == "forbidden"
        and config["frozen_inputs"]["sealed_13v_access"] == "forbidden"
    )

    alm_classification = "adaptive_group_norm_exact_penalty_with_nonnegative_scalar_accumulators"
    material_defect = True
    corrected_preflight_checks = {
        "signed_vector_toy": toy_pass,
        "stratified_nonzero_gradient_parity": gradient_pass,
        "unified_ledger_implementation_parity": ledger_pass,
        "all_gradient_and_dtype_values_finite": bool(gradient_summary["dtype"]["float32"]["all_finite"] and gradient_summary["dtype"]["float64"]["all_finite"]),
        "frozen_inputs_and_checkpoint": frozen_pass,
        "complete_architecture": architecture_pass,
        "parameter_budget": parameter_pass,
        "no_labels_13v_or_search": controls_pass,
    }
    corrected_preflight_all = all(corrected_preflight_checks.values())
    authorization = {
        "material_m33_contract_defect": material_defect,
        "corrected_toy_problem_pass": toy_pass,
        "at_least_20_nonzero_gradient_directions_pass_parity": gradient_pass,
        "unified_ledger_implementation_parity_pass": ledger_pass,
        "corrected_preflight_all_pass": corrected_preflight_all,
        "frozen_gt_and_equations_unchanged": frozen_pass,
        "complete_state_flux_electrical_interface_contract_retained": architecture_pass,
        "parameter_count_within_3_percent": parameter_pass,
        "no_labels_no_13v_no_search": controls_pass,
    }
    training_authorized = all(authorization.values())

    payload = {
        "schema_version": "m34_contract_audit_summary_v1",
        "stage_id": config["stage_id"],
        "status": "supported" if corrected_preflight_all else "failed_but_informative",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "preregistration_commit": commit,
        "base_snapshot": config["base_snapshot"],
        "evidence_types": {
            "alm_and_static_contract": "implementation_fact",
            "gradient_dtype_ledger_and_capacity": "diagnostic_evidence",
            "positive_full_pinn_scientific_evidence": False,
        },
        "input_hashes": input_hashes,
        "checkpoint_raw_sha256": prereg["checkpoint_raw_sha256"],
        "dtype": config["gradient_audit"]["dtypes"],
        "time_grids": config["ledger_audit"]["time_grid_counts"],
        "normalization": {
            "training_parallel_metric": config["ledger_audit"]["fixed_scale_normalization"],
            "historical_gate": "interval_relative_plus_total_relative_unchanged",
        },
        "alm": {
            "m33_classification": alm_classification,
            "faithful_signed_vector_alm": False,
            "unconditional_penalty_growth": True,
            "multiplier_cap": 100.0,
            "gradient_clip_norm": config["gradient_audit"]["m33_gradient_clip_norm"],
            "toy": toy_rows,
            "literature_boundary": "PECANN/PECANN-CAPU use constrained-optimization ALM machinery; M33-v1 does not test those methods generally.",
        },
        "gradient_geometry": gradient_summary,
        "ledger_reconciliation": ledger_summary,
        "representability_smoke": capacity,
        "architecture_classification": "fixed-grid neural temporal trajectory with control-volume physics; not a continuous (x,t,mu) PINN",
        "generalization_forbidden": ["cross_grid", "cross_geometry", "cross_material", "cross_waveform"],
        "m33_interpretation": {
            "still_valid": "The locked M33-v1 run failed its unchanged forward gates.",
            "must_shrink": "M33-v1 cannot by itself permanently close every corrected full-PINN training contract because its optimizer was not the declared signed/vector ALM.",
            "does_not_imply": ["mixed_PINNs_are_generally_ineffective", "PECANN_or_ALM_are_generally_ineffective"],
        },
        "corrected_preflight": {"checks": corrected_preflight_checks, "all_pass": corrected_preflight_all},
        "authorization_conditions": authorization,
        "corrected_training_authorized": training_authorized,
        "authorization_disposition": "one_corrected_run_authorized" if training_authorized else "M33-v1 contract closed; no corrected run authorized",
        "sealed_13v_access": False,
        "finite_payload": True,
    }
    if not _finite(payload):
        raise RuntimeError("M34 audit produced a non-finite payload.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m34_optimization_contract_audit.yaml"))
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(path)
    print(json.dumps({"status": result["status"], "corrected_training_authorized": result["corrected_training_authorized"]}, allow_nan=False))


if __name__ == "__main__":
    main()

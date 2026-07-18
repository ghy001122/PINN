"""Execute the single conditionally authorized M34 corrected run."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from pinnpcm.pinn.m34_contract_audit import GROUPS, vector_alm_loss
from pinnpcm.pinn.mixed_flux_pinn import grouped_constraint_tensors, rms
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt, raw_sha256, stable_file_hash
from train_m33_mixed_flux import _build, _evaluate, _nested


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _authorize(config: Mapping[str, Any]) -> dict[str, Any]:
    prereg = _load_json(ROOT / config["outputs"]["preregistration"])
    audit = _load_json(ROOT / config["outputs"]["audit_summary"])
    mismatches = {
        path: {"expected": expected, "actual": stable_file_hash(ROOT / path)}
        for path, expected in prereg["locked_files"].items()
        if stable_file_hash(ROOT / path) != expected
    }
    expected_status = sorted(
        f"?? {config['outputs'][key]}"
        for key in ("audit_summary", "gradient_geometry", "ledger_reconciliation", "alm_toy_benchmark")
    )
    status = sorted(line for line in _git("status", "--short").splitlines() if line)
    checks = {
        "audit_authorized": audit.get("corrected_training_authorized") is True,
        "all_nine_conditions": all(audit.get("authorization_conditions", {}).values()),
        "preregistration_commit": _git("rev-parse", "HEAD") == audit.get("preregistration_commit"),
        "locked_files": not mismatches,
        "worktree_contains_only_audit_outputs": status == expected_status,
        "single_result_absent": not (ROOT / config["outputs"]["corrected_summary"]).exists(),
    }
    record = {
        "authorized": all(checks.values()),
        "checks": checks,
        "hash_mismatches": mismatches,
        "worktree_status": status,
        "expected_worktree_status": expected_status,
        "preregistration_commit": audit.get("preregistration_commit"),
    }
    if not record["authorized"]:
        raise RuntimeError(f"M34 corrected training failed closed: {record}")
    return record


def _snapshot(
    model: torch.nn.Module,
    train_t: torch.Tensor,
    ledger_t: torch.Tensor,
    multipliers: Mapping[str, torch.Tensor],
    penalties: Mapping[str, float],
    *,
    step: int,
    stage: str,
    gradient_norm: float | None,
    clip_ratio: float | None,
    elapsed_s: float,
    dual_reset: bool,
) -> dict[str, Any]:
    groups = grouped_constraint_tensors(model, train_t, ledger_t)
    with torch.no_grad():
        output = model(train_t)
    return {
        "step": step,
        "stage": stage,
        "group_rms": {name: float(rms(groups[name]).detach().cpu()) for name in GROUPS},
        "penalties": {name: float(penalties[name]) for name in GROUPS},
        "multiplier_norms": {name: float(torch.linalg.vector_norm(multipliers[name]).cpu()) for name in GROUPS},
        "multiplier_max_abs": {name: float(torch.max(torch.abs(multipliers[name])).cpu()) for name in GROUPS},
        "vector_alm_loss": float(vector_alm_loss(groups, multipliers, penalties).detach().cpu()),
        "gradient_norm_before_emergency_clip": gradient_norm,
        "emergency_clip_ratio": clip_ratio,
        "dual_reset_at_stage_start": dual_reset,
        "state_ranges": {
            name: [float(torch.min(output[name]).cpu()), float(torch.max(output[name]).cpu())]
            for name in ("c_v", "T", "m", "phi", "q_c", "q_T")
        },
        "finite": bool(
            all(torch.isfinite(value).all() for value in output.values())
            and all(math.isfinite(float(value)) for value in penalties.values())
            and all(torch.isfinite(value).all() for value in multipliers.values())
        ),
        "elapsed_s": elapsed_s,
    }


def _write_comparison(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    authorization = _authorize(config)
    m33_config = yaml.safe_load((ROOT / config["frozen_inputs"]["m33_config"]).read_text(encoding="utf-8"))
    gt, params = load_frozen_gt(ROOT / config["frozen_inputs"]["gt_path"])
    with np.load(ROOT / config["frozen_inputs"]["diagnostic_dataset"], allow_pickle=False) as archive:
        arrays = {key: np.asarray(archive[key]) for key in archive.files}

    corrected = config["corrected_run"]
    model = _build(m33_config, params, float(gt["t"][-1])).double()
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=float(corrected["learning_rate"]))
    penalty_config = corrected["penalty"]
    emergency_clip = float(corrected["emergency_gradient_clip_norm"])
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    global_step = 0

    for stage_index, stage in enumerate(corrected["causal_schedule"]):
        stage_name = f"causal_{stage_index + 1}" if stage_index < 4 else "coupled_full_window"
        fraction = float(stage["t_norm_max"])
        train_t = torch.as_tensor(arrays[stage["dataset_key"]], dtype=torch.float64)
        ledger_source = arrays["ledger_t"]
        ledger_t = torch.as_tensor(ledger_source[ledger_source[:, 0] <= fraction], dtype=torch.float64)
        initial_groups = grouped_constraint_tensors(model, train_t, ledger_t)
        multipliers = {name: torch.zeros_like(initial_groups[name].reshape(-1)) for name in GROUPS}
        penalties = {name: float(penalty_config["initial"]) for name in GROUPS}
        previous_rms: dict[str, float] | None = None
        history.append(
            _snapshot(
                model, train_t, ledger_t, multipliers, penalties,
                step=global_step, stage=stage_name, gradient_norm=None, clip_ratio=None,
                elapsed_s=time.perf_counter() - started, dual_reset=True,
            )
        )
        for _ in range(int(stage["steps"])):
            optimizer.zero_grad(set_to_none=True)
            groups = grouped_constraint_tensors(model, train_t, ledger_t)
            loss = vector_alm_loss(groups, multipliers, penalties)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite M34 vector-ALM loss at step {global_step}.")
            loss.backward()
            gradient_norm_tensor = torch.nn.utils.clip_grad_norm_(model.parameters(), emergency_clip)
            gradient_norm = float(gradient_norm_tensor.detach().cpu())
            if not math.isfinite(gradient_norm):
                raise RuntimeError(f"Non-finite M34 gradient at step {global_step}.")
            clip_ratio = min(1.0, emergency_clip / max(gradient_norm, 1.0e-300))
            optimizer.step()
            global_step += 1

            if global_step % int(penalty_config["update_frequency_steps"]) == 0:
                current_groups = grouped_constraint_tensors(model, train_t, ledger_t)
                current_rms = {name: float(rms(current_groups[name]).detach().cpu()) for name in GROUPS}
                for name in GROUPS:
                    multipliers[name] = multipliers[name] + penalties[name] * current_groups[name].detach().reshape(-1)
                    if previous_rms is not None and current_rms[name] > float(penalty_config["grow_only_if_current_rms_exceeds_previous_fraction"]) * previous_rms[name]:
                        penalties[name] = min(float(penalty_config["cap"]), penalties[name] * float(penalty_config["growth"]))
                previous_rms = current_rms
                history.append(
                    _snapshot(
                        model, train_t, ledger_t, multipliers, penalties,
                        step=global_step, stage=stage_name, gradient_norm=gradient_norm,
                        clip_ratio=clip_ratio, elapsed_s=time.perf_counter() - started,
                        dual_reset=False,
                    )
                )

    if global_step != int(corrected["total_steps"]):
        raise RuntimeError(f"M34 step count mismatch: {global_step}")

    checkpoint_path = ROOT / config["outputs"]["corrected_checkpoint"]
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "seed": int(corrected["seed"]),
            "steps": global_step,
            "dtype": corrected["dtype"],
            "contract": corrected["constraint_contract"],
            "preregistration_commit": authorization["preregistration_commit"],
        },
        checkpoint_path,
    )

    history_payload = {
        "schema_version": "m34_corrected_training_history_v1",
        "stage_id": config["stage_id"],
        "seed": int(corrected["seed"]),
        "total_steps": global_step,
        "dtype": corrected["dtype"],
        "optimizer": corrected["optimizer"],
        "records": history,
        "post_result_changes": [],
    }
    history_path = ROOT / config["outputs"]["corrected_history"]
    history_path.write_text(json.dumps(history_payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")

    evaluation_model = _build(m33_config, params, float(gt["t"][-1])).float()
    evaluation_model.load_state_dict({name: value.float() for name, value in model.state_dict().items()})
    metrics, gates, v3r_comparison, _ = _evaluate(evaluation_model, gt, params, arrays, m33_config)
    m33_summary = _load_json(ROOT / config["frozen_inputs"]["m33_summary"])
    m33_metrics = m33_summary["metrics"]
    v3r_by_name = {row["metric"]: row["v3r_post_adam"] for row in v3r_comparison["rows"]}
    comparison_rows = []
    tolerance_r = float(m33_config["comparison_to_v3r"]["no_worse_relative_tolerance"])
    tolerance_a = float(m33_config["comparison_to_v3r"]["no_worse_absolute_tolerance"])
    for name in m33_config["comparison_to_v3r"]["required_metrics"]:
        current = _nested(metrics, name)
        previous_m33 = _nested(m33_metrics, name)
        previous_v3r = float(v3r_by_name[name])
        comparison_rows.append(
            {
                "metric": name,
                "v3r_post_adam": previous_v3r,
                "m33_v1": previous_m33,
                "m34_corrected": current,
                "no_worse_vs_v3r": current <= previous_v3r * (1.0 + tolerance_r) + tolerance_a,
                "no_worse_vs_m33": current <= previous_m33 * (1.0 + tolerance_r) + tolerance_a,
            }
        )
    m33_no_regression = all(row["no_worse_vs_m33"] for row in comparison_rows)
    gate_checks = dict(gates["checks"])
    gate_checks["m33_no_regression"] = m33_no_regression
    all_pass = all(gate_checks.values())
    _write_comparison(ROOT / config["outputs"]["corrected_comparison"], comparison_rows)

    result = {
        "schema_version": "m34_corrected_final_summary_v1",
        "stage_id": config["stage_id"],
        "status": "qualified_supported" if all_pass else "failed_but_informative",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "authorization": authorization,
        "training_executed": True,
        "training_runs": 1,
        "seed": int(corrected["seed"]),
        "steps": global_step,
        "dtype": corrected["dtype"],
        "optimizer": corrected["optimizer"],
        "constraint_contract": corrected["constraint_contract"],
        "hidden_field_labels_used": [],
        "port_labels_used": [],
        "sealed_13v_access": False,
        "checkpoint": config["outputs"]["corrected_checkpoint"],
        "checkpoint_raw_sha256": raw_sha256(checkpoint_path),
        "metrics": metrics,
        "gates": {"checks": gate_checks, "all_pass": all_pass},
        "comparison": {
            "rows": comparison_rows,
            "no_worse_vs_v3r_count": sum(row["no_worse_vs_v3r"] for row in comparison_rows),
            "no_worse_vs_m33_count": sum(row["no_worse_vs_m33"] for row in comparison_rows),
            "required_metrics": len(comparison_rows),
        },
        "positive_forward_claim_allowed": all_pass,
        "disposition": "register_N1_design_only" if all_pass else "all_further_full_pinn_training_closed_after_corrected_one_shot_failure",
        "wall_clock_s": time.perf_counter() - started,
        "post_result_changes": [],
    }
    summary_path = ROOT / config["outputs"]["corrected_summary"]
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m34_optimization_contract_audit.yaml"))
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(path)
    print(json.dumps({"status": result["status"], "all_pass": result["gates"]["all_pass"]}, allow_nan=False))


if __name__ == "__main__":
    main()

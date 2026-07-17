"""Instrumented exact replay and one preregistered conditional N0 recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml

from pinnpcm.pinn.full_pinn_n0_cv_e import (
    ControlVolumeFullPINN,
    control_volume_residuals,
    differentiable_ledger_residuals,
    hard_constraint_metrics,
)
from pinnpcm.pinn.n0_cv_evidence import (
    common_cv_score,
    load_frozen_gt,
    raw_sha256,
    stable_file_hash,
)
from pinnpcm.pinn.optimizer_forensics import (
    append_jsonl,
    atomic_json_write,
    atomic_torch_save,
    first_nonfinite_attribution,
    loss_gradient_diagnostics,
    parameter_optimizer_finiteness,
    physical_diagnostics,
    restore_checkpoint,
)


ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_float(value: torch.Tensor | float) -> float | None:
    number = float(value.detach().cpu()) if torch.is_tensor(value) else float(value)
    return number if math.isfinite(number) else None


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _build_model(
    source: Mapping[str, Any], params: Mapping[str, Any], duration_s: float, seed: int
) -> ControlVolumeFullPINN:
    architecture = source["architecture"]
    return ControlVolumeFullPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=duration_s,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=source["dimensionless_registry"],
        seed=int(seed),
    )


def _loss_blocks(
    model: ControlVolumeFullPINN, train_t: torch.Tensor, ledger_t: torch.Tensor
) -> dict[str, torch.Tensor]:
    residuals = control_volume_residuals(model, train_t)
    ledgers = differentiable_ledger_residuals(model, ledger_t)
    return {
        "r_c": torch.mean(residuals["r_c"].square()),
        "r_T": torch.mean(residuals["r_T"].square()),
        "r_m": torch.mean(residuals["r_m"].square()),
        "discrete_electrical": torch.mean(residuals["discrete_electrical"].square()),
        "defect_mass_ledger": torch.mean(ledgers["defect_mass_ledger"].square()),
        "energy_ledger": torch.mean(ledgers["energy_ledger"].square()),
    }


def _total(blocks: Mapping[str, torch.Tensor], weights: Mapping[str, float]) -> torch.Tensor:
    return torch.stack([float(weights[name]) * value for name, value in blocks.items()]).sum()


def _authorization(config: Mapping[str, Any]) -> dict[str, Any]:
    lock_path = ROOT / config["outputs"]["preregistration"]
    if not lock_path.exists():
        raise RuntimeError("The clean-tree preregistration lock is required.")
    lock = _json(lock_path)
    mismatches = {}
    for relative, expected in lock["locked_files"].items():
        actual = stable_file_hash(ROOT / relative)
        if actual != expected:
            mismatches[relative] = {"expected": expected, "actual": actual}
    head = _git("rev-parse", "HEAD")
    authorized = bool(
        lock.get("worktree_clean_before_lock")
        and lock.get("git_commit") == head
        and lock.get("git_commit") == lock.get("origin_main_commit")
        and not mismatches
    )
    result = {
        "authorized": authorized,
        "lock_path": str(lock_path.relative_to(ROOT)).replace("\\", "/"),
        "lock_sha256": raw_sha256(lock_path),
        "locked_commit": lock.get("git_commit"),
        "current_commit": head,
        "clean_before_lock": lock.get("worktree_clean_before_lock"),
        "hash_mismatches": mismatches,
    }
    if not authorized:
        raise RuntimeError(f"v3r authorization failed closed: {result}")
    return result


def _validate_exact_replay_lock(config: Mapping[str, Any], source: Mapping[str, Any]) -> None:
    lock = config["exact_replay_lock"]
    training = source["training"]
    observed = {
        "seed": int(training["seed"]),
        "learning_rate": float(training["learning_rate"]),
        "adam_steps": int(sum(int(stage["epochs"]) for stage in training["causal_stages"])),
        "causal_stages": training["causal_stages"],
        "gradient_clip_norm": float(training["gradient_clip_norm"]),
        "lbfgs": {
            "max_iter": int(training["lbfgs"]["max_iter"]),
            "history_size": int(training["lbfgs"]["history_size"]),
            "tolerance_grad": float(training["lbfgs"]["tolerance_grad"]),
            "tolerance_change": float(training["lbfgs"]["tolerance_change"]),
            "line_search_fn": "strong_wolfe",
        },
    }
    expected = {
        "seed": int(lock["seed"]),
        "learning_rate": float(lock["learning_rate"]),
        "adam_steps": int(lock["adam_steps"]),
        "causal_stages": lock["causal_stages"],
        "gradient_clip_norm": float(lock["gradient_clip_norm"]),
        "lbfgs": lock["lbfgs"],
    }
    if observed != expected:
        raise RuntimeError(f"Exact-replay lock mismatch: expected={expected}, observed={observed}")


def _atomic_checkpoint(
    path: Path,
    *,
    model: ControlVolumeFullPINN,
    optimizer: torch.optim.Optimizer | None,
    seed: int,
    step: int,
    label: str,
    arm: str,
    weights: Mapping[str, float],
    lock_sha256: str,
) -> dict[str, Any]:
    atomic_torch_save(
        path,
        {
            "schema_version": "n0_cv_e_v3r_checkpoint_v1",
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict() if optimizer is not None else None,
            "seed": int(seed),
            "adam_step": int(step),
            "label": label,
            "arm": arm,
            "loss_weights": dict(weights),
            "preregistration_sha256": lock_sha256,
            "git_commit": _git("rev-parse", "HEAD"),
        },
    )
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": raw_sha256(path),
        "size_bytes": path.stat().st_size,
        "seed": int(seed),
        "adam_step": int(step),
        "label": label,
        "arm": arm,
    }


def _telemetry_record(
    *,
    model: ControlVolumeFullPINN,
    optimizer: torch.optim.Optimizer,
    train_t: torch.Tensor,
    ledger_t: torch.Tensor,
    eval_t: torch.Tensor,
    weights: Mapping[str, float],
    step: int,
    stage: str,
    arm: str,
    started: float,
) -> dict[str, Any]:
    blocks = _loss_blocks(model, train_t, ledger_t)
    gradients = loss_gradient_diagnostics(model, blocks)
    total = _total(blocks, weights)
    finite = parameter_optimizer_finiteness(model, optimizer)
    return {
        "schema_version": "n0_cv_e_v3r_telemetry_event_v1",
        "event": "optimizer_snapshot",
        "arm": arm,
        "stage": stage,
        "adam_step": int(step),
        "wall_clock_s": float(time.perf_counter() - started),
        "block_losses": {name: float(value.detach().cpu()) for name, value in blocks.items()},
        "weighted_total_loss": float(total.detach().cpu()),
        "gradient_diagnostics": gradients,
        "finite_state": finite,
        "physical": physical_diagnostics(model, eval_t),
    }


def _model_trajectory(model: ControlVolumeFullPINN, gt: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    t = np.asarray(gt["t"], dtype=float)
    dtype = next(model.parameters()).dtype
    t_norm = torch.as_tensor((t / t[-1])[:, None], dtype=dtype)
    model.eval()
    with torch.no_grad():
        output = model(t_norm)
    return {
        "x": np.asarray(gt["x"], dtype=float).copy(),
        "t": t.copy(),
        "V": np.asarray(gt["V"], dtype=float).copy(),
        "c_v": output["c_v"].cpu().numpy(),
        "T": output["T"].cpu().numpy(),
        "m": output["m"].cpu().numpy(),
    }


def scientific_score(
    model: ControlVolumeFullPINN,
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    dtype = next(model.parameters()).dtype
    eval_t = torch.as_tensor(arrays["eval_t"], dtype=dtype)
    residuals = control_volume_residuals(model, eval_t)
    cv_rms = {
        name: float(torch.sqrt(torch.mean(residuals[name].detach().square())).cpu())
        for name in ("r_c", "r_T", "r_m")
    }
    electrical = float(
        torch.sqrt(torch.mean(residuals["discrete_electrical"].detach().square())).cpu()
    )
    trajectory = _model_trajectory(model, gt)
    common = common_cv_score(trajectory, gt, dict(params), source["dimensionless_registry"])
    constraints = hard_constraint_metrics(model, eval_t[:32])
    flux_numeric = {
        name: value
        for name, value in common["interface_flux_accuracy_nrmse95"].items()
        if isinstance(value, (int, float))
    }
    state_numeric = {
        name: value
        for name, value in common["interface_state_rms"].items()
        if isinstance(value, (int, float))
    }
    metrics = {
        "cv_residual_rms": cv_rms,
        "discrete_electrical_rms": electrical,
        "port_full_trace_nrmse95": common["port_full_trace_nrmse95"],
        "field_score_only_nrmse95": common["field_score_only_nrmse95"],
        "interface_state_score_only_rms": common["interface_state_rms"],
        "interface_flux_score_only_nrmse95": common["interface_flux_accuracy_nrmse95"],
        "structural_face_conservation_nonvote": common["structural_face_conservation"],
        "analytic_current_conservation_nonvote": common[
            "terminal_current_conservation_normalized_error"
        ],
        "global_energy_ledger": common["global_energy_ledger"],
        "defect_mass_ledger": common["defect_mass_ledger"],
        "ic_bc_normalized_errors": constraints,
        "finite_outputs": common["finite_outputs"],
        "bounded_states": common["bounded_states"],
        "region_diagnostics": common["region_diagnostics"],
    }
    gates = source["result_gates"]
    checks = {
        "port": metrics["port_full_trace_nrmse95"] <= float(gates["port_full_trace_nrmse95_max"]),
        "cv_residuals": bool(cv_rms) and all(
            math.isfinite(value) and value <= float(gates["residual_rms_max"])
            for value in cv_rms.values()
        ),
        "discrete_electrical": math.isfinite(electrical)
        and electrical <= float(gates["discrete_electrical_rms_max"]),
        "fields": bool(metrics["field_score_only_nrmse95"])
        and all(
            math.isfinite(value) and value <= float(gates["field_score_only_nrmse95_max"])
            for value in metrics["field_score_only_nrmse95"].values()
        ),
        "interface_state_score_only": bool(state_numeric)
        and all(
            math.isfinite(value) and value <= float(gates["interface_state_rms_max"])
            for value in state_numeric.values()
        ),
        "interface_flux_score_only": bool(flux_numeric)
        and all(
            math.isfinite(value) and value <= float(gates["interface_flux_rms_max"])
            for value in flux_numeric.values()
        ),
        "energy_ledger": metrics["global_energy_ledger"]["gate_value"]
        <= float(gates["global_energy_imbalance_max"]),
        "defect_ledger": metrics["defect_mass_ledger"]["gate_value"]
        <= float(gates["defect_mass_ledger_max"]),
        "ic_bc": bool(constraints)
        and all(math.isfinite(value) for value in constraints.values())
        and max(constraints.values()) <= float(gates["result_ic_bc_max_normalized_error"]),
        "finite_outputs": bool(metrics["finite_outputs"]),
        "bounded_states": bool(metrics["bounded_states"]),
    }
    structural = {
        "sigma_times_E_equals_J": True,
        "analytic_head_current_continuity": True,
        "shared_cv_face_equal_and_opposite": all(
            value is True
            for name, value in common["structural_face_conservation"].items()
            if name != "semantics"
        ),
        "learned_performance_vote": False,
    }
    return {
        "metrics": metrics,
        "gates": {"checks": checks, "all_pass": bool(checks) and all(checks.values())},
        "structural_invariants": structural,
        "trajectory_semantics": "pinn_predicted_score_only_against_frozen_synthetic_gt",
    }


def _metric_exceedances(score: Mapping[str, Any], source: Mapping[str, Any], factor: float) -> list[dict[str, Any]]:
    metrics = score["metrics"]
    gates = source["result_gates"]
    candidates = [
        ("port_full_trace_nrmse95", metrics["port_full_trace_nrmse95"], gates["port_full_trace_nrmse95_max"]),
        *[(f"cv_residual_rms.{key}", value, gates["residual_rms_max"]) for key, value in metrics["cv_residual_rms"].items()],
        ("discrete_electrical_rms", metrics["discrete_electrical_rms"], gates["discrete_electrical_rms_max"]),
        *[(f"field_score_only_nrmse95.{key}", value, gates["field_score_only_nrmse95_max"]) for key, value in metrics["field_score_only_nrmse95"].items()],
        *[(f"interface_state.{key}", value, gates["interface_state_rms_max"]) for key, value in metrics["interface_state_score_only_rms"].items() if isinstance(value, (int, float))],
        *[(f"interface_flux.{key}", value, gates["interface_flux_rms_max"]) for key, value in metrics["interface_flux_score_only_nrmse95"].items() if isinstance(value, (int, float))],
        ("global_energy_ledger", metrics["global_energy_ledger"]["gate_value"], gates["global_energy_imbalance_max"]),
        ("defect_mass_ledger", metrics["defect_mass_ledger"]["gate_value"], gates["defect_mass_ledger_max"]),
    ]
    return [
        {"metric": name, "value": float(value), "gate": float(gate), "factor": float(value) / max(float(gate), 1.0e-30)}
        for name, value, gate in candidates
        if not math.isfinite(float(value)) or float(value) > factor * float(gate)
    ]


def _balancing_weights(base: Mapping[str, float], diagnostics: Mapping[str, Any], clip: list[float]) -> dict[str, float]:
    norms = {name: float(entry["norm"]) for name, entry in diagnostics["per_block"].items()}
    positive = [value for value in norms.values() if value > 1.0e-30 and math.isfinite(value)]
    reference = float(np.median(positive)) if positive else 1.0
    lower, upper = map(float, clip)
    return {
        name: float(np.clip(reference / max(norms[name], 1.0e-30), lower, upper)) * float(base[name])
        for name in base
    }


def _run_adam(
    *,
    model: ControlVolumeFullPINN,
    source: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
    seed: int,
    arm: str,
    config: Mapping[str, Any],
    authorization: Mapping[str, Any],
    telemetry_path: Path,
    checkpoint_dir: Path,
    manifest_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    training = source["training"]
    optimizer = torch.optim.Adam(model.parameters(), lr=float(training["learning_rate"]))
    eval_t = torch.as_tensor(arrays["eval_t"], dtype=next(model.parameters()).dtype)
    started = time.perf_counter()
    step = 0
    initial_train = torch.as_tensor(arrays["train_t_stage_025"], dtype=next(model.parameters()).dtype)
    initial_ledger = torch.as_tensor(
        arrays["ledger_t"][arrays["ledger_t"][:, 0] <= 0.25], dtype=next(model.parameters()).dtype
    )
    initial_record = _telemetry_record(
        model=model, optimizer=optimizer, train_t=initial_train, ledger_t=initial_ledger,
        eval_t=eval_t, weights=weights, step=0, stage="025", arm=arm, started=started
    )
    append_jsonl(telemetry_path, initial_record)
    initial_path = checkpoint_dir / f"{arm}_seed_{seed}_initial.pt"
    manifest_rows.append(_atomic_checkpoint(
        initial_path, model=model, optimizer=optimizer, seed=seed, step=0, label="initial",
        arm=arm, weights=weights, lock_sha256=authorization["lock_sha256"]
    ))
    latest_record = initial_record
    for stage in training["causal_stages"]:
        fraction = float(stage["t_norm_max"])
        label = f"{int(fraction * 100):03d}"
        train_t = torch.as_tensor(arrays[f"train_t_stage_{label}"], dtype=next(model.parameters()).dtype)
        ledger_t = torch.as_tensor(
            arrays["ledger_t"][arrays["ledger_t"][:, 0] <= fraction], dtype=next(model.parameters()).dtype
        )
        for _ in range(int(stage["epochs"])):
            optimizer.zero_grad(set_to_none=True)
            blocks = _loss_blocks(model, train_t, ledger_t)
            loss = _total(blocks, weights)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite Adam loss before backward at step {step}.")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=float(training["gradient_clip_norm"]),
                error_if_nonfinite=True,
            )
            optimizer.step()
            step += 1
            if step % int(config["instrumentation"]["telemetry_every_adam_steps"]) == 0:
                latest_record = _telemetry_record(
                    model=model, optimizer=optimizer, train_t=train_t, ledger_t=ledger_t,
                    eval_t=eval_t, weights=weights, step=step, stage=label, arm=arm, started=started
                )
                append_jsonl(telemetry_path, latest_record)
            if step % int(config["instrumentation"]["checkpoint_every_adam_steps"]) == 0:
                checkpoint_path = checkpoint_dir / f"{arm}_seed_{seed}_adam_{step:04d}.pt"
                manifest_rows.append(_atomic_checkpoint(
                    checkpoint_path, model=model, optimizer=optimizer, seed=seed, step=step,
                    label=f"adam_{step:04d}", arm=arm, weights=weights,
                    lock_sha256=authorization["lock_sha256"]
                ))
    post_path = checkpoint_dir / f"{arm}_seed_{seed}_pre_lbfgs.pt"
    manifest_rows.append(_atomic_checkpoint(
        post_path, model=model, optimizer=optimizer, seed=seed, step=step, label="pre_lbfgs",
        arm=arm, weights=weights, lock_sha256=authorization["lock_sha256"]
    ))
    return {
        "optimizer": optimizer,
        "initial_record": initial_record,
        "post_record": latest_record,
        "post_checkpoint": post_path,
        "adam_steps": step,
        "wall_clock_s": float(time.perf_counter() - started),
    }


def _run_lbfgs(
    *,
    model: ControlVolumeFullPINN,
    source: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
    arm: str,
    telemetry_path: Path,
    crash_path: Path,
    pre_checkpoint: Path,
) -> dict[str, Any]:
    dtype = next(model.parameters()).dtype
    train_t = torch.as_tensor(arrays["train_t_stage_100"], dtype=dtype)
    ledger_t = torch.as_tensor(arrays["ledger_t"], dtype=dtype)
    pre_payload = torch.load(pre_checkpoint, map_location="cpu", weights_only=False)
    pre_vector = torch.cat(
        [
            pre_payload["model_state_dict"][name].detach().to(dtype=dtype).reshape(-1)
            for name, _ in model.named_parameters()
        ]
    )
    settings = source["training"]["lbfgs"]
    optimizer = torch.optim.LBFGS(
        model.parameters(), max_iter=int(settings["max_iter"]),
        history_size=int(settings["history_size"]), tolerance_grad=float(settings["tolerance_grad"]),
        tolerance_change=float(settings["tolerance_change"]), line_search_fn="strong_wolfe"
    )
    closure_index = 0
    crash: dict[str, Any] | None = None
    started = time.perf_counter()

    def closure() -> torch.Tensor:
        nonlocal closure_index, crash
        closure_index += 1
        optimizer.zero_grad(set_to_none=True)
        blocks = _loss_blocks(model, train_t, ledger_t)
        total = _total(blocks, weights)
        with torch.no_grad():
            physical = model(train_t)
            current_vector = torch.cat([parameter.detach().reshape(-1) for parameter in model.parameters()])
            step_norm = float(torch.linalg.vector_norm(current_vector - pre_vector).cpu())
        event = {
            "schema_version": "n0_cv_e_v3r_telemetry_event_v1",
            "event": "lbfgs_closure",
            "arm": arm,
            "closure_index": closure_index,
            "line_search": "strong_wolfe",
            "wall_clock_s": float(time.perf_counter() - started),
            "block_losses": {name: _safe_float(value) for name, value in blocks.items()},
            "block_finite": {name: bool(torch.isfinite(value).all().item()) for name, value in blocks.items()},
            "weighted_total_loss": _safe_float(total),
            "weighted_total_finite": bool(torch.isfinite(total).all().item()),
            "parameter_step_norm_from_pre_lbfgs": _safe_float(step_norm),
            "parameter_state_before_backward": parameter_optimizer_finiteness(model, optimizer),
        }
        append_jsonl(telemetry_path, event)
        if not torch.isfinite(total):
            attribution = first_nonfinite_attribution(model, blocks, physical)
            crash = {
                "schema_version": "n0_cv_e_v3r_crash_manifest_v1",
                "status": "nonfinite_detected",
                "failure_stage": "lbfgs_strong_wolfe_closure",
                "closure_index": closure_index,
                "first_nonfinite": attribution,
                "block_finiteness": {name: bool(torch.isfinite(value).all().item()) for name, value in blocks.items()},
                "physical_finiteness": {name: bool(torch.isfinite(value).all().item()) for name, value in physical.items() if torch.is_tensor(value)},
                "parameter_step_norm_from_pre_lbfgs": _safe_float(step_norm),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            atomic_json_write(crash_path, crash)
            raise RuntimeError("Non-finite N0-CV-E v3r L-BFGS loss.")
        total.backward()
        finite_after = parameter_optimizer_finiteness(model, optimizer)
        if not finite_after["gradients_finite"]:
            attribution = first_nonfinite_attribution(model, blocks, physical)
            crash = {
                "schema_version": "n0_cv_e_v3r_crash_manifest_v1",
                "status": "nonfinite_detected",
                "failure_stage": "lbfgs_strong_wolfe_backward",
                "closure_index": closure_index,
                "first_nonfinite": attribution,
                "finite_state": finite_after,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            atomic_json_write(crash_path, crash)
            raise RuntimeError("Non-finite N0-CV-E v3r L-BFGS gradient.")
        return total

    try:
        optimizer.step(closure)
        return {"completed": True, "closure_calls": closure_index, "crash": None}
    except Exception as error:  # evidence capture, then scientific fail-closed
        trace = traceback.format_exc()
        if crash is None:
            crash = {
                "schema_version": "n0_cv_e_v3r_crash_manifest_v1",
                "status": "runtime_exception",
                "failure_stage": "lbfgs_strong_wolfe_driver",
                "closure_index": closure_index,
                "first_nonfinite": first_nonfinite_attribution(model),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        crash.update(
            {
                "exception_type": type(error).__name__,
                "exception_message": str(error),
                "traceback": trace,
                "traceback_sha256": _sha_text(trace),
                "stderr_semantics": "captured_exception_traceback",
                "stderr_sha256": _sha_text(trace),
                "stdout_semantics": "machine_events_persisted_in_jsonl",
                "stdout_sha256": raw_sha256(telemetry_path),
            }
        )
        atomic_json_write(crash_path, crash)
        return {"completed": False, "closure_calls": closure_index, "crash": crash}


def _write_report(summary: Mapping[str, Any], path: Path) -> None:
    post = summary["post_adam"]
    decision = summary["recovery_decision"]
    first = summary["primary_lbfgs"].get("crash") or {}
    metrics = post["score"]["metrics"]
    lines = [
        "# N0-CV-E v3r Optimizer Forensics",
        "",
        f"Preregistered commit: `{summary['authorization']['locked_commit']}`.",
        "",
        "## Historical b380 status",
        "",
        "The historical result remains `failed_but_informative`, with the narrower substatus "
        "`runtime_abort_unassessed`; the absence of a scored trajectory is not scientific model falsification.",
        "",
        "## Exact replay",
        "",
        f"Adam steps: `{post['adam_steps']}`; post-Adam scoreable: `{post['scoreable']}`; "
        f"primary L-BFGS completed: `{summary['primary_lbfgs']['completed']}`.",
        f"First nonfinite attribution: `{first.get('first_nonfinite')}`.",
        "",
        "## Post-Adam scientific score",
        "",
        f"Port NRMSE95: `{metrics['port_full_trace_nrmse95']:.9g}`; "
        f"max CV residual RMS: `{max(metrics['cv_residual_rms'].values()):.9g}`; "
        f"energy ledger: `{metrics['global_energy_ledger']['gate_value']:.9g}`; "
        f"defect ledger: `{metrics['defect_mass_ledger']['gate_value']:.9g}`.",
        "",
        "Structural analytic current and shared-face conservation are reported as invariants and do not vote "
        "for learned performance. Interface state uses one-sided face reconstruction; interface flux is scored "
        "against frozen-GT face flux.",
        "",
        "## Recovery decision",
        "",
        f"Decision: `{decision['decision']}`. Reason: {decision['reason']}",
        "",
        "No hidden-field or port labels, public data, 13 V data, gate relaxation, `nan_to_num`, or post-hoc "
        "multi-factor tuning were used.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run(config_path: Path) -> dict[str, Any]:
    config = _yaml(config_path)
    source = _yaml(ROOT / config["scientific_source_config"])
    _validate_exact_replay_lock(config, source)
    authorization = _authorization(config)
    telemetry_path = ROOT / config["outputs"]["telemetry"]
    run_log = ROOT / config["outputs"]["run_log"]
    crash_path = ROOT / config["outputs"]["crash_manifest"]
    summary_path = ROOT / config["outputs"]["summary"]
    checkpoint_dir = ROOT / config["outputs"]["checkpoint_dir"]
    for path in (telemetry_path, run_log, crash_path, summary_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite v3r evidence: {path}")
    if checkpoint_dir.exists():
        raise FileExistsError(f"Refusing to overwrite v3r checkpoints: {checkpoint_dir}")
    checkpoint_dir.mkdir(parents=True)
    append_jsonl(run_log, {"event": "run_started", "utc": datetime.now(timezone.utc).isoformat(), "commit": authorization["locked_commit"]})
    gt, params = load_frozen_gt(ROOT / source["frozen_inputs"]["gt_path"])
    with np.load(ROOT / source["diagnostics"]["dataset_path"], allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    seed = int(config["exact_replay_lock"]["seed"])
    torch.manual_seed(seed)
    model = _build_model(source, params, float(gt["t"][-1]), seed).float()
    weights = {name: float(value) for name, value in source["training"]["loss_weights"].items()}
    manifest_rows: list[dict[str, Any]] = []
    adam = _run_adam(
        model=model, source=source, arrays=arrays, weights=weights, seed=seed,
        arm="primary_equal_weight", config=config, authorization=authorization,
        telemetry_path=telemetry_path, checkpoint_dir=checkpoint_dir, manifest_rows=manifest_rows
    )
    score = scientific_score(model, gt, params, arrays, source)
    post_finite = parameter_optimizer_finiteness(model, adam["optimizer"])
    exceedances = _metric_exceedances(
        score, source, float(config["conditional_single_recovery"]["stop_if_any_post_adam_metric_exceeds_gate_factor"])
    )
    post_payload = {
        "schema_version": "n0_cv_e_v3r_post_adam_score_v1",
        "seed": seed,
        "adam_steps": adam["adam_steps"],
        "initial_total_loss": adam["initial_record"]["weighted_total_loss"],
        "post_total_loss": adam["post_record"]["weighted_total_loss"],
        "loss_declined": adam["post_record"]["weighted_total_loss"] < adam["initial_record"]["weighted_total_loss"],
        "finite_state": post_finite,
        "post_gradient_diagnostics": adam["post_record"]["gradient_diagnostics"],
        "initial_gradient_diagnostics": adam["initial_record"]["gradient_diagnostics"],
        "score": score,
        "scoreable": True,
        "metrics_exceeding_20x_gate": exceedances,
        "checkpoint": str(adam["post_checkpoint"].relative_to(ROOT)).replace("\\", "/"),
    }
    atomic_json_write(ROOT / config["outputs"]["post_adam_score"], post_payload)
    primary_lbfgs = _run_lbfgs(
        model=model, source=source, arrays=arrays, weights=weights, arm="primary_equal_weight",
        telemetry_path=telemetry_path, crash_path=crash_path, pre_checkpoint=adam["post_checkpoint"]
    )
    if primary_lbfgs["completed"]:
        atomic_json_write(crash_path, {
            "schema_version": "n0_cv_e_v3r_crash_manifest_v1", "status": "no_nonfinite_observed",
            "failure_stage": None, "first_nonfinite": None, "closure_calls": primary_lbfgs["closure_calls"]
        })

    all_post_finite = all(
        post_finite[key]
        for key in ("parameters_finite", "gradients_finite", "optimizer_state_finite", "adam_exp_avg_finite", "adam_exp_avg_sq_finite")
    )
    first_nonfinite_strong_wolfe = bool(
        primary_lbfgs.get("crash")
        and str(primary_lbfgs["crash"].get("failure_stage", "")).startswith("lbfgs_strong_wolfe")
    )
    eligible = bool(
        all_post_finite
        and post_payload["loss_declined"]
        and post_payload["scoreable"]
        and not exceedances
        and first_nonfinite_strong_wolfe
    )
    recovery_result: dict[str, Any] | None = None
    if not eligible:
        reason_parts = []
        if not all_post_finite:
            reason_parts.append("post-Adam parameter/gradient/optimizer state was nonfinite")
        if exceedances:
            reason_parts.append("at least one physics or ledger metric exceeded 20x its locked gate")
        if not post_payload["loss_declined"]:
            reason_parts.append("total loss did not decline")
        if not first_nonfinite_strong_wolfe:
            reason_parts.append("first nonfinite was not isolated to a strong-Wolfe trial")
        decision = {"eligible": False, "decision": "no_recovery_stop", "reason": "; ".join(reason_parts) or "eligibility failed"}
    else:
        post_diag = post_payload["post_gradient_diagnostics"]
        initial_diag = post_payload["initial_gradient_diagnostics"]
        alignment_delta = float(post_diag["minimum_pairwise_cosine"] - initial_diag["minimum_pairwise_cosine"])
        gradient_trigger = bool(
            post_diag["gradient_norm_ratio"] >= float(config["conditional_single_recovery"]["gradient_ratio_trigger"])
            or alignment_delta <= float(config["conditional_single_recovery"]["alignment_worsening_trigger"])
        )
        if gradient_trigger:
            choice = "gradient_statistics_balancing"
            decision_reason = (
                f"post-Adam gradient ratio={post_diag['gradient_norm_ratio']:.6g}, alignment delta={alignment_delta:.6g}; "
                "the preregistered gradient trigger fired"
            )
            recovery_model = _build_model(source, params, float(gt["t"][-1]), seed).float()
            recovery_weights = _balancing_weights(
                weights, initial_diag, config["conditional_single_recovery"]["balancing_weight_clip"]
            )
            recovery_adam = _run_adam(
                model=recovery_model, source=source, arrays=arrays, weights=recovery_weights, seed=seed,
                arm=choice, config=config, authorization=authorization, telemetry_path=telemetry_path,
                checkpoint_dir=checkpoint_dir, manifest_rows=manifest_rows
            )
            recovery_score = scientific_score(recovery_model, gt, params, arrays, source)
            recovery_lbfgs = _run_lbfgs(
                model=recovery_model, source=source, arrays=arrays, weights=recovery_weights, arm=choice,
                telemetry_path=telemetry_path,
                crash_path=checkpoint_dir / "gradient_statistics_balancing_crash.json",
                pre_checkpoint=recovery_adam["post_checkpoint"]
            )
            final_score = scientific_score(recovery_model, gt, params, arrays, source) if recovery_lbfgs["completed"] else recovery_score
            recovery_result = {"arm": choice, "weights": recovery_weights, "adam": {"steps": recovery_adam["adam_steps"]}, "lbfgs": recovery_lbfgs, "score": final_score, "all_gates_pass": final_score["gates"]["all_pass"] and recovery_lbfgs["completed"]}
        else:
            choice = "promoted_float64_lbfgs"
            decision_reason = (
                f"post-Adam gradient ratio={post_diag['gradient_norm_ratio']:.6g}, alignment delta={alignment_delta:.6g}; "
                "the preregistered gradient trigger did not fire"
            )
            recovery_model = _build_model(source, params, float(gt["t"][-1]), seed).double()
            restore_checkpoint(adam["post_checkpoint"], recovery_model)
            recovery_pre = checkpoint_dir / f"{choice}_seed_{seed}_pre_lbfgs.pt"
            manifest_rows.append(_atomic_checkpoint(
                recovery_pre, model=recovery_model, optimizer=None, seed=seed, step=adam["adam_steps"],
                label="pre_lbfgs", arm=choice, weights=weights, lock_sha256=authorization["lock_sha256"]
            ))
            recovery_lbfgs = _run_lbfgs(
                model=recovery_model, source=source, arrays=arrays, weights=weights, arm=choice,
                telemetry_path=telemetry_path, crash_path=checkpoint_dir / "promoted_float64_lbfgs_crash.json",
                pre_checkpoint=recovery_pre
            )
            final_score = scientific_score(recovery_model, gt, params, arrays, source)
            recovery_result = {"arm": choice, "weights": weights, "lbfgs": recovery_lbfgs, "score": final_score, "all_gates_pass": final_score["gates"]["all_pass"] and recovery_lbfgs["completed"]}
        decision = {"eligible": True, "decision": choice, "reason": decision_reason, "maximum_arms_respected": True}

    pilot_pass = bool(
        recovery_result["all_gates_pass"] if recovery_result is not None else primary_lbfgs["completed"] and scientific_score(model, gt, params, arrays, source)["gates"]["all_pass"]
    )
    # Expansion is fail-closed unless the pilot clears every locked gate.
    expansion = {"run": False, "reason": "pilot_did_not_pass_all_scientific_gates", "seeds": []}
    if pilot_pass:
        expansion_rows = []
        selected_arm = recovery_result["arm"] if recovery_result is not None else "primary_equal_weight"
        selected_weights = (
            recovery_result["weights"] if recovery_result is not None else weights
        )
        for expansion_seed in config["conditional_single_recovery"]["expansion_seeds"]:
            expansion_seed = int(expansion_seed)
            expansion_model = _build_model(source, params, float(gt["t"][-1]), expansion_seed).float()
            expansion_adam = _run_adam(
                model=expansion_model,
                source=source,
                arrays=arrays,
                weights=selected_weights,
                seed=expansion_seed,
                arm=f"{selected_arm}_expansion",
                config=config,
                authorization=authorization,
                telemetry_path=telemetry_path,
                checkpoint_dir=checkpoint_dir,
                manifest_rows=manifest_rows,
            )
            lbfgs_model = expansion_model
            lbfgs_checkpoint = expansion_adam["post_checkpoint"]
            if selected_arm == "promoted_float64_lbfgs":
                lbfgs_model = _build_model(source, params, float(gt["t"][-1]), expansion_seed).double()
                restore_checkpoint(expansion_adam["post_checkpoint"], lbfgs_model)
                lbfgs_checkpoint = checkpoint_dir / f"promoted_float64_lbfgs_expansion_seed_{expansion_seed}_pre_lbfgs.pt"
                manifest_rows.append(
                    _atomic_checkpoint(
                        lbfgs_checkpoint,
                        model=lbfgs_model,
                        optimizer=None,
                        seed=expansion_seed,
                        step=expansion_adam["adam_steps"],
                        label="pre_lbfgs",
                        arm="promoted_float64_lbfgs_expansion",
                        weights=selected_weights,
                        lock_sha256=authorization["lock_sha256"],
                    )
                )
            expansion_lbfgs = _run_lbfgs(
                model=lbfgs_model,
                source=source,
                arrays=arrays,
                weights=selected_weights,
                arm=f"{selected_arm}_expansion",
                telemetry_path=telemetry_path,
                crash_path=checkpoint_dir / f"{selected_arm}_expansion_seed_{expansion_seed}_crash.json",
                pre_checkpoint=lbfgs_checkpoint,
            )
            expansion_score = scientific_score(lbfgs_model, gt, params, arrays, source)
            expansion_rows.append(
                {
                    "seed": expansion_seed,
                    "lbfgs": expansion_lbfgs,
                    "score": expansion_score,
                    "all_gates_pass": bool(
                        expansion_lbfgs["completed"] and expansion_score["gates"]["all_pass"]
                    ),
                }
            )
        expansion = {"run": True, "reason": "pilot_passed_all_scientific_gates", "seeds": expansion_rows}

    pilot_vote = int(pilot_pass)
    expansion_votes = sum(bool(row["all_gates_pass"]) for row in expansion["seeds"])
    evaluated_seeds = 1 + len(expansion["seeds"])
    overall_seed_pass = bool(
        evaluated_seeds == int(config["conditional_single_recovery"]["total_seeds"])
        and pilot_vote + expansion_votes
        >= int(config["conditional_single_recovery"]["minimum_passing_seeds"])
    )

    manifest = {
        "schema_version": "n0_cv_e_v3r_checkpoint_manifest_v1",
        "checkpoints": manifest_rows,
        "last_finite_adam_checkpoint": str(adam["post_checkpoint"].relative_to(ROOT)).replace("\\", "/"),
        "all_atomic": True,
    }
    atomic_json_write(ROOT / config["outputs"]["checkpoint_manifest"], manifest)
    summary = {
        "schema_version": "n0_cv_e_v3r_summary_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "authorization": authorization,
        "historical_b380": {
            "status": "failed_but_informative",
            "failure_substatus": "runtime_abort_unassessed",
            "scientific_model_falsification": False,
            "adam_1200_evidence": "config_and_control_flow_derived_only",
            "original_stdout_stderr_traceback_history": "absent",
            "pinn_predicted_trajectory": "absent",
        },
        "post_adam": post_payload,
        "primary_lbfgs": primary_lbfgs,
        "exact_b380_failure_reproduced": bool(primary_lbfgs.get("crash") and primary_lbfgs["crash"].get("failure_stage") == "lbfgs_strong_wolfe_closure"),
        "recovery_decision": decision,
        "recovery_result": recovery_result,
        "seed_expansion": expansion,
        "seed_vote": {
            "passing": int(pilot_vote + expansion_votes),
            "evaluated": int(evaluated_seeds),
            "required": int(config["conditional_single_recovery"]["minimum_passing_seeds"]),
            "total": int(config["conditional_single_recovery"]["total_seeds"]),
            "overall_pass": overall_seed_pass,
        },
        "claim_status": "qualified_supported" if overall_seed_pass else "failed_but_informative",
        "positive_full_pinn_forward_claim_allowed": overall_seed_pass,
        "permanent_n0_optimizer_stop": bool(decision["decision"] == "no_recovery_stop" or recovery_result is not None and not recovery_result["all_gates_pass"]),
        "machine": {"platform": platform.platform(), "python": platform.python_version(), "torch": torch.__version__, "device": "cpu"},
        "checkpoint_manifest": manifest,
        "telemetry_sha256": raw_sha256(telemetry_path),
        "run_log_sha256_before_final_event": raw_sha256(run_log),
    }
    atomic_json_write(summary_path, summary)
    _write_report(summary, ROOT / config["outputs"]["report"])
    append_jsonl(run_log, {"event": "run_finished", "utc": datetime.now(timezone.utc).isoformat(), "status": summary["claim_status"], "summary_sha256": raw_sha256(summary_path)})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/n0_cv_e_v3r_optimizer_forensics.yaml"))
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(path)
    print(json.dumps({"status": result["claim_status"], "exact_failure_reproduced": result["exact_b380_failure_reproduced"], "recovery": result["recovery_decision"]["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Post-hoc, non-voting gradient semantics diagnostics for the locked M34 result.

This module never authorizes training.  It evaluates the immutable M33 final
checkpoint in float64 and distinguishes automatic-differentiation errors from
finite-difference cancellation and directions without a stable step interval.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

from pinnpcm.pinn.m34_contract_audit import (
    GROUPS,
    build_m33_model,
    m33_augmented_loss,
)
from pinnpcm.pinn.mixed_flux_pinn import grouped_constraint_tensors


def _longest_true_run(values: list[bool]) -> int:
    best = 0
    current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def _median_taylor_slope(steps: list[float], remainders: list[float], base: float) -> float | None:
    threshold = 100.0 * np.finfo(np.float64).eps * max(abs(base), 1.0)
    slopes: list[float] = []
    for left, right, r_left, r_right in zip(steps[:-1], steps[1:], remainders[:-1], remainders[1:]):
        if r_left <= threshold or r_right <= threshold:
            continue
        slope = math.log(r_left / r_right) / math.log(left / right)
        if math.isfinite(slope):
            slopes.append(float(slope))
    return float(np.median(slopes)) if slopes else None


def _objective_values(
    model: torch.nn.Module,
    train_t: torch.Tensor,
    ledger_t: torch.Tensor,
    multipliers: Mapping[str, float],
    penalties: Mapping[str, float],
    group_scales: Mapping[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor]:
    groups = grouped_constraint_tensors(model, train_t, ledger_t)
    raw = m33_augmented_loss(groups, multipliers, penalties)
    normalized = torch.stack(
        [torch.mean(groups[name].reshape(-1).square()) / group_scales[name] for name in GROUPS]
    ).mean()
    return raw, normalized


def _module_direction(
    model: torch.nn.Module, module: str, seed: int
) -> tuple[list[tuple[str, torch.nn.Parameter]], dict[str, torch.Tensor], float]:
    parameters = [(name, parameter) for name, parameter in model.named_parameters() if name.startswith(module)]
    if not parameters:
        raise ValueError(f"No parameters found for module {module!r}.")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    direction = {
        name: torch.randn(parameter.shape, dtype=parameter.dtype, device=parameter.device, generator=generator)
        for name, parameter in parameters
    }
    random_norm = torch.sqrt(sum(torch.sum(value.square()) for value in direction.values()))
    parameter_norm = torch.sqrt(sum(torch.sum(parameter.detach().square()) for _, parameter in parameters))
    target_norm = max(float(parameter_norm.cpu()), 1.0)
    scale = target_norm / max(float(random_norm.cpu()), 1.0e-300)
    direction = {name: value * scale for name, value in direction.items()}
    return parameters, direction, target_norm


def gradient_semantics_amendment(
    m33_config: Mapping[str, Any],
    audit_config: Mapping[str, Any],
    checkpoint_path: Path,
    diagnostic_arrays: Mapping[str, np.ndarray],
    history: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the fixed-seed multi-step directional audit on the M33 objective."""

    model, _, _, _ = build_m33_model(m33_config, checkpoint_path, dtype=torch.float64)
    train_source = np.asarray(diagnostic_arrays["train_t_stage_100"], dtype=np.float64)
    ledger_source = np.asarray(diagnostic_arrays["ledger_t"], dtype=np.float64)
    train_indices = np.linspace(0, train_source.size - 1, int(audit_config["train_time_count"]), dtype=int)
    ledger_indices = np.linspace(0, ledger_source.size - 1, int(audit_config["ledger_time_count"]), dtype=int)
    train_t = torch.as_tensor(train_source[train_indices], dtype=torch.float64)
    ledger_t = torch.as_tensor(ledger_source[ledger_indices], dtype=torch.float64)
    multipliers = history["final_multipliers"]
    penalties = history["final_penalties"]

    base_groups = grouped_constraint_tensors(model, train_t, ledger_t)
    floor = float(audit_config["normalized_group_floor"])
    group_scales = {
        name: torch.clamp(torch.mean(base_groups[name].reshape(-1).square()).detach(), min=floor)
        for name in GROUPS
    }
    raw_base, normalized_base = _objective_values(
        model, train_t, ledger_t, multipliers, penalties, group_scales
    )
    all_parameters = list(model.parameters())
    raw_gradients = torch.autograd.grad(raw_base, all_parameters, retain_graph=True, allow_unused=True)
    normalized_gradients = torch.autograd.grad(
        normalized_base, all_parameters, allow_unused=True
    )
    raw_gradient_by_id = {
        id(parameter): gradient for parameter, gradient in zip(all_parameters, raw_gradients)
    }
    normalized_gradient_by_id = {
        id(parameter): gradient for parameter, gradient in zip(all_parameters, normalized_gradients)
    }

    steps = [float(value) for value in audit_config["relative_steps"]]
    parity_gate = float(audit_config["parity_relative_error_max"])
    stable_min = int(audit_config["stable_steps_min"])
    plateau_gate = float(audit_config["stable_fd_plateau_relative_change_max"])
    slope_min, slope_max = (float(value) for value in audit_config["taylor_slope_range"])
    rows: list[dict[str, Any]] = []
    direction_summaries: list[dict[str, Any]] = []

    for module in audit_config["modules"]:
        for seed in audit_config["direction_seeds"]:
            parameters, direction, direction_norm = _module_direction(model, str(module), int(seed))
            ad_raw = 0.0
            ad_normalized = 0.0
            for name, parameter in parameters:
                raw_gradient = raw_gradient_by_id[id(parameter)]
                normalized_gradient = normalized_gradient_by_id[id(parameter)]
                if raw_gradient is not None:
                    ad_raw += float(torch.sum(raw_gradient * direction[name]).detach().cpu())
                if normalized_gradient is not None:
                    ad_normalized += float(
                        torch.sum(normalized_gradient * direction[name]).detach().cpu()
                    )

            raw_fd: list[float] = []
            normalized_fd: list[float] = []
            raw_remainder: list[float] = []
            normalized_remainder: list[float] = []
            direction_rows: list[dict[str, Any]] = []
            for step in steps:
                with torch.no_grad():
                    for name, parameter in parameters:
                        parameter.add_(step * direction[name])
                raw_plus, normalized_plus = _objective_values(
                    model, train_t, ledger_t, multipliers, penalties, group_scales
                )
                with torch.no_grad():
                    for name, parameter in parameters:
                        parameter.add_(-2.0 * step * direction[name])
                raw_minus, normalized_minus = _objective_values(
                    model, train_t, ledger_t, multipliers, penalties, group_scales
                )
                with torch.no_grad():
                    for name, parameter in parameters:
                        parameter.add_(step * direction[name])

                raw_plus_value = float(raw_plus.detach().cpu())
                raw_minus_value = float(raw_minus.detach().cpu())
                normalized_plus_value = float(normalized_plus.detach().cpu())
                normalized_minus_value = float(normalized_minus.detach().cpu())
                fd_raw = (raw_plus_value - raw_minus_value) / (2.0 * step)
                fd_normalized = (normalized_plus_value - normalized_minus_value) / (2.0 * step)
                raw_error = abs(ad_raw - fd_raw) / max(abs(ad_raw), abs(fd_raw), 1.0e-12)
                normalized_error = abs(ad_normalized - fd_normalized) / max(
                    abs(ad_normalized), abs(fd_normalized), 1.0e-12
                )
                raw_taylor = abs(raw_plus_value - float(raw_base.detach().cpu()) - step * ad_raw)
                normalized_taylor = abs(
                    normalized_plus_value
                    - float(normalized_base.detach().cpu())
                    - step * ad_normalized
                )
                raw_fd.append(fd_raw)
                normalized_fd.append(fd_normalized)
                raw_remainder.append(raw_taylor)
                normalized_remainder.append(normalized_taylor)
                row = {
                    "module": module,
                    "seed": int(seed),
                    "relative_step": step,
                    "direction_l2_norm": direction_norm,
                    "raw_objective_base": float(raw_base.detach().cpu()),
                    "normalized_objective_base": float(normalized_base.detach().cpu()),
                    "vjp_raw": ad_raw,
                    "vjp_normalized": ad_normalized,
                    "central_fd_raw": fd_raw,
                    "central_fd_normalized": fd_normalized,
                    "relative_error_raw": raw_error,
                    "relative_error_normalized": normalized_error,
                    "taylor_remainder_raw": raw_taylor,
                    "taylor_remainder_normalized": normalized_taylor,
                    "raw_parity_pass": bool(raw_error <= parity_gate),
                    "normalized_parity_pass": bool(normalized_error <= parity_gate),
                }
                direction_rows.append(row)
                rows.append(row)

            raw_flags = [row["raw_parity_pass"] for row in direction_rows]
            normalized_flags = [row["normalized_parity_pass"] for row in direction_rows]
            raw_stable = _longest_true_run(raw_flags)
            normalized_stable = _longest_true_run(normalized_flags)
            plateau_flags = []
            for left, right in zip(normalized_fd[:-1], normalized_fd[1:]):
                plateau_flags.append(
                    abs(left - right) / max(abs(left), abs(right), 1.0e-12)
                    <= plateau_gate
                )
            plateau_run = 1 + _longest_true_run(plateau_flags) if plateau_flags else 0
            raw_slope = _median_taylor_slope(
                steps, raw_remainder, float(raw_base.detach().cpu())
            )
            normalized_slope = _median_taylor_slope(
                steps, normalized_remainder, float(normalized_base.detach().cpu())
            )
            slope_ok = bool(
                normalized_slope is not None
                and slope_min <= normalized_slope <= slope_max
            )
            best_raw_error = min(row["relative_error_raw"] for row in direction_rows)
            best_normalized_error = min(
                row["relative_error_normalized"] for row in direction_rows
            )
            if normalized_stable >= stable_min and slope_ok:
                if raw_stable < stable_min or best_raw_error > max(
                    parity_gate, 10.0 * best_normalized_error
                ):
                    classification = "total_loss_scale_fd_cancellation"
                else:
                    classification = "stable_parity_no_autograd_error"
            elif plateau_run >= stable_min and best_normalized_error > parity_gate:
                classification = "autograd_implementation_error_supported"
            else:
                classification = "no_stable_step_interval_uncertain"
            summary = {
                "module": module,
                "seed": int(seed),
                "classification": classification,
                "raw_stable_step_run": raw_stable,
                "normalized_stable_step_run": normalized_stable,
                "normalized_fd_plateau_run": plateau_run,
                "best_raw_relative_error": best_raw_error,
                "best_normalized_relative_error": best_normalized_error,
                "raw_taylor_median_slope": raw_slope,
                "normalized_taylor_median_slope": normalized_slope,
            }
            direction_summaries.append(summary)
            for row in direction_rows:
                row["direction_classification"] = classification

    counts = {
        name: sum(item["classification"] == name for item in direction_summaries)
        for name in (
            "stable_parity_no_autograd_error",
            "total_loss_scale_fd_cancellation",
            "autograd_implementation_error_supported",
            "no_stable_step_interval_uncertain",
        )
    }
    total = len(direction_summaries)
    error_fraction = counts["autograd_implementation_error_supported"] / max(total, 1)
    cancellation_fraction = counts["total_loss_scale_fd_cancellation"] / max(total, 1)
    autograd_error_supported = error_fraction >= float(
        audit_config["implementation_error_min_direction_fraction"]
    )
    cancellation_supported = cancellation_fraction >= float(
        audit_config["scale_cancellation_min_direction_fraction"]
    )
    if autograd_error_supported:
        global_classification = "autograd_implementation_error_supported"
    elif cancellation_supported:
        global_classification = "total_loss_scale_fd_cancellation_supported"
    elif counts["no_stable_step_interval_uncertain"]:
        global_classification = "mixed_stable_and_uncertain_no_autograd_error_evidence"
    else:
        global_classification = "stable_directional_parity_no_autograd_error_evidence"
    finite = all(
        math.isfinite(float(row[key]))
        for row in rows
        for key in (
            "vjp_raw",
            "vjp_normalized",
            "central_fd_raw",
            "central_fd_normalized",
            "relative_error_raw",
            "relative_error_normalized",
            "taylor_remainder_raw",
            "taylor_remainder_normalized",
        )
    )
    return rows, {
        "direction_count": total,
        "directions_per_module": {
            module: sum(item["module"] == module for item in direction_summaries)
            for module in audit_config["modules"]
        },
        "classification_counts": counts,
        "global_classification": global_classification,
        "autograd_implementation_error_supported": autograd_error_supported,
        "total_loss_scale_fd_cancellation_supported": cancellation_supported,
        "uncertain_direction_count": counts["no_stable_step_interval_uncertain"],
        "direction_summaries": direction_summaries,
        "group_normalization_scales": {
            name: float(value.cpu()) for name, value in group_scales.items()
        },
        "all_finite": finite,
        "diagnostic_only": True,
        "scientific_vote": False,
        "training_authorization": False,
    }

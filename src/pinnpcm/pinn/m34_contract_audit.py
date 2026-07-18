"""Low-compute contract diagnostics for the M33 mixed state--flux model.

The routines in this module do not mutate M33 artifacts.  They distinguish
implementation facts, non-voting diagnostics, and scientific evidence.
"""

from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import torch

from pinnpcm.pinn.full_pinn_n0_cv_e import model_state_time_derivatives, torch_cv_rhs
from pinnpcm.pinn.mixed_flux_pinn import (
    MixedStateFluxPINN,
    grouped_constraint_tensors,
    mixed_ledger_residuals,
    mixed_state_flux_residuals,
    rms,
)
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt, nrmse95, trajectory_ledgers


GROUPS = ("constitutive", "conservation", "phase_current", "ic_bc", "interface", "ledgers")


def build_m33_model(
    m33_config: Mapping[str, Any], checkpoint_path: Path, *, dtype: torch.dtype
) -> tuple[MixedStateFluxPINN, dict[str, np.ndarray], dict[str, Any], dict[str, Any]]:
    """Rebuild the exact M33 architecture and load its immutable checkpoint."""

    gt, params = load_frozen_gt(Path(m33_config["frozen_inputs"]["gt_path"]))
    architecture = m33_config["architecture"]
    model = MixedStateFluxPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=float(gt["t"][-1]),
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=m33_config["dimensionless_registry"],
        seed=int(m33_config["training"]["seed"]),
    ).to(dtype=dtype)
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(dtype=dtype)
    model.eval()
    return model, gt, params, checkpoint


def toy_alm_benchmark(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compare exact scalar subproblem updates for three constrained methods."""

    rows: list[dict[str, Any]] = []
    outer = int(config["outer_iterations"])
    rho = float(config["penalty"])
    for case in config["cases"]:
        a = float(case["objective_center"])
        b = float(case["constraint_target"])
        true_dual = a - b

        lam = 0.0
        x_signed = a
        for _ in range(outer):
            x_signed = (a + rho * b - lam) / (1.0 + rho)
            lam = lam + rho * (x_signed - b)

        mu = 0.0
        x_norm = a
        for _ in range(outer):
            offset = a - b
            shrink = math.copysign(max(abs(offset) - mu, 0.0), offset) if offset else 0.0
            x_norm = b + shrink / (1.0 + rho)
            mu = mu + rho * abs(x_norm - b)

        x_penalty = (a + rho * b) / (1.0 + rho)
        methods = (
            ("signed_vector_alm", x_signed, lam, "signed_dual"),
            ("group_rms_scalar_multiplier", x_norm, mu, "nonnegative_norm_weight"),
            ("quadratic_penalty", x_penalty, None, "no_dual"),
        )
        for method, x_value, dual, dual_semantics in methods:
            rows.append(
                {
                    "case_id": case["case_id"],
                    "method": method,
                    "analytic_solution": b,
                    "estimated_x": x_value,
                    "constraint_abs": abs(x_value - b),
                    "objective": 0.5 * (x_value - a) ** 2,
                    "true_signed_dual": true_dual,
                    "reported_multiplier": dual,
                    "dual_abs_error": None if dual is None else abs(dual - true_dual),
                    "dual_semantics": dual_semantics,
                }
            )
    return rows


def m33_augmented_loss(
    groups: Mapping[str, torch.Tensor], multipliers: Mapping[str, float], penalties: Mapping[str, float]
) -> torch.Tensor:
    """Reproduce the final coupled M33 scalar group-RMS objective exactly."""

    terms = []
    for name in GROUPS:
        value = rms(groups[name])
        terms.append(float(multipliers[name]) * value + 0.5 * float(penalties[name]) * value.square() + value.square())
    return torch.stack(terms).sum()


def vector_alm_loss(
    groups: Mapping[str, torch.Tensor], multipliers: Mapping[str, torch.Tensor], penalties: Mapping[str, float]
) -> torch.Tensor:
    """Stagewise signed/vector equality-constrained augmented Lagrangian."""

    terms = []
    for name in GROUPS:
        constraint = groups[name].reshape(-1)
        multiplier = multipliers[name].reshape(-1).to(constraint)
        terms.append(torch.mean(multiplier * constraint) + 0.5 * float(penalties[name]) * torch.mean(constraint.square()))
    return torch.stack(terms).sum()


def _flatten_gradients(
    gradients: Iterable[torch.Tensor | None], parameters: Iterable[torch.nn.Parameter]
) -> torch.Tensor:
    pieces = []
    for gradient, parameter in zip(gradients, parameters):
        pieces.append(torch.zeros_like(parameter).reshape(-1) if gradient is None else gradient.reshape(-1))
    return torch.cat(pieces)


def _candidate_coordinates(model: MixedStateFluxPINN, count_per_module: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    named = dict(model.named_parameters())
    for module in ("shared_trunk", "state_head", "heat_flux_head", "defect_flux_head"):
        names = [name for name in named if name.startswith(module) and name.endswith("weight")]
        total = sum(named[name].numel() for name in names)
        if total == 0:
            continue
        offsets = np.unique(np.linspace(0, total - 1, count_per_module, dtype=int))
        boundaries = np.cumsum([named[name].numel() for name in names])
        for offset in offsets:
            name_index = int(np.searchsorted(boundaries, offset, side="right"))
            previous = 0 if name_index == 0 else int(boundaries[name_index - 1])
            candidates.append(
                {
                    "module": module,
                    "parameter": names[name_index],
                    "flat_index": int(offset - previous),
                }
            )
    return candidates


def gradient_contract_audit(
    m33_config: Mapping[str, Any],
    audit_config: Mapping[str, Any],
    checkpoint_path: Path,
    diagnostic_arrays: Mapping[str, np.ndarray],
    history: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Audit coordinate parity, group conflicts, dtype drift, and clipping."""

    train_count = int(audit_config["train_time_count"])
    ledger_count = int(audit_config["ledger_time_count"])
    train_source = np.asarray(diagnostic_arrays["train_t_stage_100"])
    ledger_source = np.asarray(diagnostic_arrays["ledger_t"])
    train_indices = np.linspace(0, len(train_source) - 1, train_count, dtype=int)
    ledger_indices = np.linspace(0, len(ledger_source) - 1, ledger_count, dtype=int)
    final_multipliers = history["final_multipliers"]
    final_penalties = history["final_penalties"]
    clip_norm = float(audit_config["m33_gradient_clip_norm"])

    rows: list[dict[str, Any]] = []
    dtype_payload: dict[str, Any] = {}
    gradient_vectors: dict[str, dict[str, torch.Tensor]] = {}
    for dtype_name, dtype in (("float32", torch.float32), ("float64", torch.float64)):
        model, _, _, _ = build_m33_model(m33_config, checkpoint_path, dtype=dtype)
        train_t = torch.as_tensor(train_source[train_indices], dtype=dtype)
        ledger_t = torch.as_tensor(ledger_source[ledger_indices], dtype=dtype)
        groups = grouped_constraint_tensors(model, train_t, ledger_t)
        parameters = list(model.parameters())
        vectors: dict[str, torch.Tensor] = {}
        group_summary: dict[str, Any] = {}
        for name in GROUPS:
            objective = torch.mean(groups[name].reshape(-1).square())
            gradients = torch.autograd.grad(objective, parameters, retain_graph=True, allow_unused=True)
            vector = _flatten_gradients(gradients, parameters).detach()
            norm = float(torch.linalg.vector_norm(vector).cpu())
            ratio = min(1.0, clip_norm / max(norm, 1.0e-300))
            vectors[name] = vector
            group_summary[name] = {
                "constraint_rms": float(rms(groups[name]).detach().cpu()),
                "squared_loss": float(objective.detach().cpu()),
                "gradient_norm": norm,
                "clip_effective_ratio": ratio,
                "finite": bool(torch.isfinite(groups[name]).all() and torch.isfinite(vector).all()),
            }
            rows.append({"row_type": "group", "dtype": dtype_name, "group_a": name, **group_summary[name]})

        cosines = []
        for left_index, left in enumerate(GROUPS):
            for right in GROUPS[left_index + 1 :]:
                denominator = torch.linalg.vector_norm(vectors[left]) * torch.linalg.vector_norm(vectors[right])
                cosine = float((torch.dot(vectors[left], vectors[right]) / denominator).cpu()) if float(denominator) > 0 else 0.0
                cosines.append({"group_a": left, "group_b": right, "cosine": cosine})
                rows.append({"row_type": "pair_cosine", "dtype": dtype_name, "group_a": left, "group_b": right, "cosine": cosine})

        total = m33_augmented_loss(groups, final_multipliers, final_penalties)
        total_gradients = torch.autograd.grad(total, parameters, allow_unused=True)
        total_vector = _flatten_gradients(total_gradients, parameters).detach()
        total_norm = float(torch.linalg.vector_norm(total_vector).cpu())
        gradient_vectors[dtype_name] = vectors
        dtype_payload[dtype_name] = {
            "groups": group_summary,
            "total_loss": float(total.detach().cpu()),
            "total_gradient_norm": total_norm,
            "total_clip_effective_ratio": min(1.0, clip_norm / max(total_norm, 1.0e-300)),
            "most_severe_conflict": min(cosines, key=lambda row: row["cosine"]),
            "all_finite": bool(torch.isfinite(total) and torch.isfinite(total_vector).all() and all(item["finite"] for item in group_summary.values())),
        }

    dtype_comparison: dict[str, Any] = {}
    for name in GROUPS:
        left = gradient_vectors["float32"][name].double()
        right = gradient_vectors["float64"][name].double()
        denominator = torch.linalg.vector_norm(left) * torch.linalg.vector_norm(right)
        cosine = float(torch.dot(left, right) / denominator) if float(denominator) > 0 else 0.0
        r32 = dtype_payload["float32"]["groups"][name]["constraint_rms"]
        r64 = dtype_payload["float64"]["groups"][name]["constraint_rms"]
        comparison = {
            "gradient_cosine": cosine,
            "residual_relative_difference": abs(r32 - r64) / max(abs(r64), 1.0e-300),
            "gradient_norm_ratio_32_to_64": dtype_payload["float32"]["groups"][name]["gradient_norm"] / max(dtype_payload["float64"]["groups"][name]["gradient_norm"], 1.0e-300),
        }
        dtype_comparison[name] = comparison
        rows.append({"row_type": "dtype_comparison", "dtype": "float32_vs_float64", "group_a": name, **comparison})

    model, _, _, _ = build_m33_model(m33_config, checkpoint_path, dtype=torch.float64)
    train_t = torch.as_tensor(train_source[train_indices], dtype=torch.float64)
    ledger_t = torch.as_tensor(ledger_source[ledger_indices], dtype=torch.float64)
    groups = grouped_constraint_tensors(model, train_t, ledger_t)
    total = m33_augmented_loss(groups, final_multipliers, final_penalties)
    total.backward()
    named = dict(model.named_parameters())
    candidates = _candidate_coordinates(model, int(audit_config["candidates_per_module"]))
    g_min = float(audit_config["nonzero_gradient_min"])
    fd_relative = float(audit_config["central_difference_relative_step"])
    fd_absolute = float(audit_config["central_difference_absolute_step"])
    coordinate_rows = []
    for candidate in candidates:
        parameter = named[candidate["parameter"]]
        index = int(candidate["flat_index"])
        ad = float(parameter.grad.reshape(-1)[index].detach().cpu())
        original = float(parameter.detach().reshape(-1)[index].cpu())
        step = max(fd_absolute, fd_relative * max(1.0, abs(original)))
        with torch.no_grad():
            parameter.reshape(-1)[index] = original + step
        plus = float(m33_augmented_loss(grouped_constraint_tensors(model, train_t, ledger_t), final_multipliers, final_penalties).detach().cpu())
        with torch.no_grad():
            parameter.reshape(-1)[index] = original - step
        minus = float(m33_augmented_loss(grouped_constraint_tensors(model, train_t, ledger_t), final_multipliers, final_penalties).detach().cpu())
        with torch.no_grad():
            parameter.reshape(-1)[index] = original
        fd = (plus - minus) / (2.0 * step)
        nonzero = max(abs(ad), abs(fd)) > g_min
        relative_error = abs(ad - fd) / max(abs(ad), abs(fd), g_min)
        row = {
            "row_type": "coordinate_parity",
            "dtype": "float64",
            **candidate,
            "autograd": ad,
            "finite_difference": fd,
            "step": step,
            "nonzero": nonzero,
            "relative_error": relative_error,
            "pass": bool((not nonzero) or relative_error <= float(audit_config["parity_relative_error_max"])),
        }
        coordinate_rows.append(row)
        rows.append(row)

    nonzero_rows = [row for row in coordinate_rows if row["nonzero"]]
    parity = {
        "candidate_count": len(coordinate_rows),
        "nonzero_count": len(nonzero_rows),
        "module_nonzero_counts": {module: sum(row["nonzero"] and row["module"] == module for row in coordinate_rows) for module in audit_config["modules"]},
        "maximum_nonzero_relative_error": max((row["relative_error"] for row in nonzero_rows), default=math.inf),
        "all_nonzero_pass": bool(nonzero_rows and all(row["pass"] for row in nonzero_rows)),
    }
    return rows, {
        "coordinate_parity": parity,
        "dtype": dtype_payload,
        "dtype_comparison": dtype_comparison,
        "semantics": "M33 final checkpoint, identical batches, squared group objectives for geometry and exact M33 group-RMS objective for coordinate parity",
    }


def _cumulative_trapezoid(values: np.ndarray, time: np.ndarray) -> np.ndarray:
    increments = 0.5 * (values[:-1] + values[1:]) * np.diff(time)
    return np.concatenate([[0.0], np.cumsum(increments)])


def ledger_contract_audit(
    model: MixedStateFluxPINN,
    gt: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    audit_config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reconcile training, independent, prefix, and local-residual ledgers."""

    rows: list[dict[str, Any]] = []
    grid_payload: dict[str, Any] = {}
    dtype = next(model.parameters()).dtype
    rho_cp = float(params["rho"]) * float(params["Cp"])
    mass_scale = float(params["L_eff"])
    energy_scale = rho_cp * float(model.registry["temperature_scale_K"]) * float(params["L_eff"])
    low_fraction = float(audit_config["low_activity_denominator_fraction_of_fixed_scale"])

    for count in audit_config["time_grid_counts"]:
        count = int(count)
        t_norm = torch.linspace(0.0, 1.0, count, dtype=dtype).reshape(-1, 1)
        residuals = mixed_state_flux_residuals(model, t_norm)
        head_ledgers = mixed_ledger_residuals(model, t_norm)
        with torch.no_grad():
            outputs = model(t_norm)
            frozen = torch_cv_rhs(model, t_norm, outputs["c_v"], outputs["T"], outputs["m"])
        time = t_norm[:, 0].detach().cpu().numpy() * model.t_max_s
        dx = model.dx_m
        c = outputs["c_v"].detach().cpu().numpy()
        temperature = outputs["T"].detach().cpu().numpy()
        q_c = outputs["q_c"].detach().cpu().numpy()
        q_T = outputs["q_T"].detach().cpu().numpy()
        reaction = np.sum(frozen["reaction"].detach().cpu().numpy(), axis=1) * dx
        joule = np.sum(frozen["joule"].detach().cpu().numpy(), axis=1) * dx
        sink = np.sum(frozen["sink"].detach().cpu().numpy(), axis=1) * dx
        mass = np.sum(c, axis=1) * dx
        energy = np.sum(rho_cp * temperature, axis=1) * dx
        mass_boundary = q_c[:, -1] - q_c[:, 0]
        heat_boundary = q_T[:, -1] - q_T[:, 0]

        components = {
            "defect": {
                "storage": np.diff(mass),
                "boundary": 0.5 * (mass_boundary[:-1] + mass_boundary[1:]) * np.diff(time),
                "source": 0.5 * (reaction[:-1] + reaction[1:]) * np.diff(time),
                "fixed_scale": mass_scale,
                "training": head_ledgers["defect_mass_ledger"].detach().cpu().numpy(),
                "local_integrand": np.sum(residuals["r_c"].detach().cpu().numpy() * float(model.registry["residual_scales"]["r_c_per_s"]), axis=1) * dx,
            },
            "energy": {
                "storage": np.diff(energy),
                "boundary": 0.5 * (heat_boundary[:-1] + heat_boundary[1:]) * np.diff(time),
                "source": 0.5 * ((-joule + sink)[:-1] + (-joule + sink)[1:]) * np.diff(time),
                "fixed_scale": energy_scale,
                "training": head_ledgers["energy_ledger"].detach().cpu().numpy(),
                "local_integrand": np.sum(residuals["r_T"].detach().cpu().numpy() * float(model.registry["residual_scales"]["r_T_K_per_s"]) * rho_cp, axis=1) * dx,
            },
        }

        trajectory = {
            "t": time,
            "x": np.asarray(gt["x"], dtype=float),
            "V": model.voltage(t_norm).detach().cpu().numpy().reshape(-1),
            "c_v": c,
            "T": temperature,
            "m": outputs["m"].detach().cpu().numpy(),
        }
        independent = trajectory_ledgers(trajectory, dict(params))
        grid_payload[str(count)] = {}
        for ledger_name, component in components.items():
            balance = component["storage"] + component["boundary"] + component["source"]
            scale = float(component["fixed_scale"])
            fixed = balance / scale
            denominator = np.abs(component["storage"]) + np.abs(component["boundary"]) + np.abs(component["source"])
            relative = np.abs(balance) / np.maximum(denominator, float(audit_config["historical_interval_relative_floor"]))
            prefix = np.concatenate([[0.0], np.cumsum(balance)]) / scale
            local_prefix = _cumulative_trapezoid(component["local_integrand"], time) / scale
            training = np.asarray(component["training"], dtype=float)
            implementation_difference = float(np.max(np.abs(training - fixed)))
            payload = {
                "fixed_scale_rms": float(np.sqrt(np.mean(fixed**2))),
                "fixed_scale_max": float(np.max(np.abs(fixed))),
                "interval_relative_max": float(np.max(relative)),
                "interval_relative_p95": float(np.quantile(relative, 0.95)),
                "prefix_fixed_scale_rms": float(np.sqrt(np.mean(prefix**2))),
                "prefix_fixed_scale_max": float(np.max(np.abs(prefix))),
                "local_residual_prefix_fixed_scale_rms": float(np.sqrt(np.mean(local_prefix**2))),
                "local_residual_prefix_fixed_scale_max": float(np.max(np.abs(local_prefix))),
                "training_implementation_abs_difference": implementation_difference,
                "low_activity_interval_fraction": float(np.mean(denominator < low_fraction * scale)),
                "denominator_min": float(np.min(denominator)),
                "denominator_median": float(np.median(denominator)),
                "independent_gate_value": float(independent[ledger_name]["gate_value"] if ledger_name == "energy" else independent["defect"]["gate_value"]),
            }
            grid_payload[str(count)][ledger_name] = payload
            rows.append({"grid_count": count, "ledger": ledger_name, "dtype": str(dtype).replace("torch.", ""), "normalization": "fixed_physical_and_interval_relative_parallel", **payload})

    maximum_difference = max(row["training_implementation_abs_difference"] for row in rows)
    available_counts = sorted(int(key) for key in grid_payload)
    fine_count = available_counts[-1]
    medium_count = available_counts[-2] if len(available_counts) > 1 else fine_count
    fine = {name: grid_payload[str(fine_count)][name] for name in ("defect", "energy")}
    medium = {name: grid_payload[str(medium_count)][name] for name in ("defect", "energy")}
    sampling_changes = {
        name: abs(fine[name]["fixed_scale_rms"] - medium[name]["fixed_scale_rms"]) / max(abs(fine[name]["fixed_scale_rms"]), 1.0e-300)
        for name in ("defect", "energy")
    }
    return rows, {
        "grids": grid_payload,
        "maximum_training_independent_implementation_difference": maximum_difference,
        "sampling_relative_change_two_finest_grids": {
            "coarse_count": medium_count,
            "fine_count": fine_count,
            "values": sampling_changes,
        },
        "historical_gate_preserved": True,
        "root_cause_votes": {
            "normalization_mismatch": bool(any(row["fixed_scale_rms"] < 0.05 and row["independent_gate_value"] > 0.05 for row in rows)),
            "low_activity_denominator_pathology": bool(any(row["low_activity_interval_fraction"] > 0.10 and row["interval_relative_max"] > 0.90 for row in rows)),
            "state_flux_or_local_residual_incompatibility": bool(any(fine[name]["prefix_fixed_scale_max"] > (0.01 if name == "defect" else 0.05) for name in fine)),
            "time_sampling_primary": bool(any(value > float(audit_config["sampling_convergence_relative_change_max"]) for value in sampling_changes.values())),
            "sign_unit_boundary_implementation_error": bool(maximum_difference > float(audit_config["implementation_parity_abs_max"])),
        },
    }


def representability_smoke(
    m33_config: Mapping[str, Any], audit_config: Mapping[str, Any], checkpoint_path: Path
) -> dict[str, Any]:
    """Non-voting 200-step hidden-field capacity diagnostic."""

    model, gt, _, _ = build_m33_model(m33_config, checkpoint_path, dtype=torch.float32)
    train_count = int(audit_config["train_time_count"])
    indices = np.linspace(0, len(gt["t"]) - 1, train_count, dtype=int)
    t_train = torch.as_tensor((np.asarray(gt["t"])[indices] / float(gt["t"][-1]))[:, None], dtype=torch.float32)
    targets = {
        "c_v": torch.as_tensor(np.asarray(gt["c_v"])[indices], dtype=torch.float32),
        "T": torch.as_tensor(np.asarray(gt["T"])[indices], dtype=torch.float32),
        "m": torch.as_tensor(np.asarray(gt["m"])[indices], dtype=torch.float32),
    }
    scales = {"c_v": 1.0, "T": float(model.registry["temperature_scale_K"]), "m": 1.0}

    def score() -> dict[str, float]:
        t_all = torch.as_tensor((np.asarray(gt["t"]) / float(gt["t"][-1]))[:, None], dtype=torch.float32)
        with torch.no_grad():
            states = model.dynamic_states(t_all)
        return {name: nrmse95(states[name].cpu().numpy(), np.asarray(gt[name])) for name in targets}

    before = score()
    optimizer = torch.optim.Adam(model.parameters(), lr=float(audit_config["learning_rate"]))
    for _ in range(int(audit_config["maximum_steps"])):
        optimizer.zero_grad(set_to_none=True)
        states = model.dynamic_states(t_train)
        loss = sum(torch.mean(((states[name] - targets[name]) / scales[name]) ** 2) for name in targets)
        if not torch.isfinite(loss):
            break
        loss.backward()
        optimizer.step()
    after = score()
    return {
        "diagnostic_only": True,
        "scientific_vote": False,
        "hidden_field_labels_used": list(targets),
        "steps": int(audit_config["maximum_steps"]),
        "before_field_nrmse95": before,
        "after_field_nrmse95": after,
        "interpretation": "capacity/local-optimization smoke only; not forward evidence and not an inverse-training result",
    }

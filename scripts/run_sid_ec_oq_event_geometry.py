"""Solver-first event-window SID/EC-OQ discovery map for prompt 29."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np
import torch
import yaml

from pinnpcm.identifiability import (
    WINDOW_NAMES,
    bootstrap_switch_geometry,
    derivative_convergence,
    event_window_indices,
    principal_angles_deg,
    sid_decision,
    svd_geometry,
)
from pinnpcm.physics.gt_solver import simulate_ground_truth
from pinnpcm.pinn.full_pinn_n0_cv_e import ControlVolumeFullPINN, control_volume_residuals
from pinnpcm.pinn.n0_cv_evidence import load_frozen_gt, raw_sha256, stable_file_hash
from pinnpcm.pinn.optimizer_forensics import atomic_json_write, loss_gradient_diagnostics


ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _authorization(config: Mapping[str, Any]) -> dict[str, Any]:
    path = ROOT / config["outputs"]["preregistration"]
    lock = _json(path)
    mismatches = {}
    for relative, expected in lock["locked_files"].items():
        actual = stable_file_hash(ROOT / relative)
        if actual != expected:
            mismatches[relative] = {"expected": expected, "actual": actual}
    head = _git("rev-parse", "HEAD")
    authorized = bool(
        lock.get("worktree_clean_before_lock")
        and lock.get("git_commit") == head
        and lock.get("origin_main_commit") == head
        and not mismatches
    )
    result = {
        "authorized": authorized,
        "lock_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "lock_sha256": raw_sha256(path),
        "locked_commit": lock.get("git_commit"),
        "hash_mismatches": mismatches,
    }
    if not authorized:
        raise RuntimeError(f"SID preregistration failed closed: {result}")
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _apply_neighborhood(
    params: Mapping[str, Any], coordinate_config: Mapping[str, Any], signs: list[int]
) -> dict[str, Any]:
    result = dict(params)
    fraction = float(coordinate_config["neighborhood_fraction"])
    for name, sign in zip(coordinate_config["names"], signs, strict=True):
        if not sign:
            continue
        if name == "T_sw":
            result[name] = float(result[name]) + sign * fraction * float(coordinate_config["T_sw_scale_K"])
        else:
            result[name] = float(result[name]) * math.exp(sign * fraction)
    return result


def _perturb(
    params: Mapping[str, Any], name: str, step: float, sign: int, coordinates: Mapping[str, Any]
) -> dict[str, Any]:
    result = dict(params)
    if name == "T_sw":
        result[name] = float(result[name]) + sign * float(step) * float(coordinates["T_sw_scale_K"])
    else:
        result[name] = float(result[name]) * math.exp(sign * float(step))
    return result


def _simulate(
    protocol: Mapping[str, Any], params: Mapping[str, Any], solver: Mapping[str, Any]
) -> dict[str, Any]:
    overrides = {**params, **protocol.get("params", {})}
    return simulate_ground_truth(
        str(protocol["protocol"]),
        overrides,
        nx=int(solver["nx"]),
        nt=int(solver["nt"]),
        t_max=float(protocol["t_max_s"]),
        rtol=float(solver["rtol"]),
        atol=float(solver["atol"]),
        method=str(solver["method"]),
    )


def _whitened_jacobians(
    protocol: Mapping[str, Any],
    params: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    solver = config["solver"]
    coordinates = config["coordinates"]
    base = _simulate(protocol, params, solver)
    noise_sigma = max(
        float(config["observation"]["relative_noise"]) * float(np.max(np.abs(base["I"]))),
        float(config["observation"]["absolute_noise_floor_A"]),
    )
    columns_h: list[np.ndarray] = []
    columns_h2: list[np.ndarray] = []
    for name in coordinates["names"]:
        h = float(coordinates["relative_steps"][name])
        plus_h = _simulate(protocol, _perturb(params, name, h, 1, coordinates), solver)
        minus_h = _simulate(protocol, _perturb(params, name, h, -1, coordinates), solver)
        plus_h2 = _simulate(protocol, _perturb(params, name, h / 2.0, 1, coordinates), solver)
        minus_h2 = _simulate(protocol, _perturb(params, name, h / 2.0, -1, coordinates), solver)
        columns_h.append((np.asarray(plus_h["I"]) - np.asarray(minus_h["I"])) / (2.0 * h * noise_sigma))
        columns_h2.append((np.asarray(plus_h2["I"]) - np.asarray(minus_h2["I"])) / (h * noise_sigma))
    jacobian_h = np.column_stack(columns_h)
    jacobian_h2 = np.column_stack(columns_h2)
    audit = derivative_convergence(
        jacobian_h,
        jacobian_h2,
        maximum_relative_difference=float(config["derivative_audit"]["maximum_relative_difference"]),
    )
    return {
        "base": base,
        "noise_sigma_A": noise_sigma,
        "jacobian_h": jacobian_h,
        "jacobian_h_over_2": jacobian_h2,
        "jacobian": audit["richardson_jacobian"],
        "derivative_audit": audit,
        "forward_evaluations": 1 + 4 * len(coordinates["names"]),
    }


def _geometry_rows(
    protocol_name: str,
    neighborhood_name: str,
    jacobian: np.ndarray,
    windows: Mapping[str, np.ndarray],
    derivative_audit: Mapping[str, Any],
    rank_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = []
    geometries = {}
    for window_name in WINDOW_NAMES:
        indices = np.asarray(windows[window_name], dtype=int)
        geometry = svd_geometry(jacobian[indices], relative_rank_threshold=rank_threshold)
        geometries[window_name] = geometry
        singular = np.asarray(geometry["singular_values"])
        row = {
            "protocol": protocol_name,
            "neighborhood": neighborhood_name,
            "window": window_name,
            "observation_count": int(indices.size),
            "derivative_pass": bool(derivative_audit["pass"]),
            "derivative_max_relative_difference": float(derivative_audit["maximum_relative_difference"]),
            "threshold_rank": int(geometry["threshold_rank"]),
            "effective_rank": float(geometry["effective_rank"]),
            "spectral_gap": float(geometry["spectral_gap"]),
            "retained_condition_number": float(geometry["retained_condition_number"]),
            "information_trace": float(geometry["information_trace"]),
        }
        for index, value in enumerate(singular, start=1):
            row[f"singular_{index}"] = float(value)
        rows.append(row)
    return rows, geometries


def _build_training_model(checkpoint: Path, gt: Mapping[str, np.ndarray], params: Mapping[str, Any]) -> ControlVolumeFullPINN:
    source = _yaml(ROOT / "configs/full_pinn_n0_cv_e_v3.yaml")
    architecture = source["architecture"]
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model = ControlVolumeFullPINN(
        params=params,
        nx=int(architecture["nx"]),
        t_max_s=float(np.asarray(gt["t"])[-1]),
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        temperature_min_k=float(architecture["temperature_min_K"]),
        temperature_max_k=float(architecture["temperature_max_K"]),
        registry=source["dimensionless_registry"],
        seed=int(payload["seed"]),
    ).float()
    model.load_state_dict(payload["model_state_dict"])
    return model


def _residual_vector(model: ControlVolumeFullPINN, t_norm: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    residuals = control_volume_residuals(model, t_norm)
    blocks = {name: residuals[name].reshape(-1) for name in ("r_c", "r_T", "r_m", "discrete_electrical")}
    return torch.cat(list(blocks.values())), blocks


def _training_geometry(
    model: ControlVolumeFullPINN,
    t: np.ndarray,
    windows: Mapping[str, np.ndarray],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    parameter_count = sum(parameter.numel() for parameter in parameters)
    rng = np.random.default_rng(int(config["training_geometry"]["seed"]))
    probes = int(config["training_geometry"]["vjp_random_probes"])
    results: dict[str, Any] = {}
    for window_name in WINDOW_NAMES:
        indices = np.asarray(windows[window_name], dtype=int)
        times = torch.as_tensor((t[indices] / t[-1])[:, None], dtype=torch.float32)
        sketch_rows = []
        for _ in range(probes):
            vector, _ = _residual_vector(model, times)
            probe = torch.as_tensor(rng.choice([-1.0, 1.0], size=vector.numel()), dtype=vector.dtype)
            scalar = torch.dot(vector, probe) / math.sqrt(vector.numel())
            gradients = torch.autograd.grad(scalar, parameters, allow_unused=True)
            sketch_rows.append(
                torch.cat(
                    [
                        torch.zeros_like(parameter).reshape(-1)
                        if gradient is None
                        else gradient.detach().reshape(-1)
                        for parameter, gradient in zip(parameters, gradients, strict=True)
                    ]
                ).cpu().numpy()
            )
        sketch = np.vstack(sketch_rows)
        singular = np.linalg.svd(sketch, compute_uv=False)
        positive = singular[singular > max(float(singular[0]) * 1.0e-8, 1.0e-30)]
        condition = float(positive[0] / positive[-1]) if positive.size else 1.0e30
        _, block_vectors = _residual_vector(model, times)
        block_losses = {name: torch.mean(value.square()) for name, value in block_vectors.items()}
        conflict = loss_gradient_diagnostics(model, block_losses)
        results[window_name] = {
            "method": "randomized_vjp_residual_jacobian_sketch",
            "probe_count": probes,
            "parameter_count": parameter_count,
            "singular_values": singular.tolist(),
            "condition_proxy": condition,
            "gradient_conflict": conflict,
        }
    ordinary_conditions = [results[name]["condition_proxy"] for name in ("pre_switch", "post_switch", "cooling_recovery")]
    results["switch_condition_ratio"] = float(
        results["switch"]["condition_proxy"] / max(float(np.median(ordinary_conditions)), 1.0e-30)
    )
    results["dense_hessian_constructed"] = False
    results["protocol_coverage"] = ["locked_triangle_0p20"]
    return results


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _figures(
    anchor: Mapping[str, Any], bootstrap_summary: Mapping[str, Any], training: Mapping[str, Any], config: Mapping[str, Any]
) -> None:
    spectrum_path = ROOT / config["outputs"]["spectrum_figure"]
    spectrum_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for protocol, payload in anchor.items():
        for window, style in (("switch", "-"), ("pre_switch", "--")):
            values = payload["geometries"][window]["singular_values"]
            ax.semilogy(np.arange(1, len(values) + 1), values, style, marker="o", label=f"{protocol}:{window}")
    ax.set(xlabel="singular-value index", ylabel="noise-whitened singular value", title="Solver event-window sensitivity spectra")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(spectrum_path, dpi=180)
    plt.close(fig)

    angle_path = ROOT / config["outputs"]["angle_figure"]
    labels = list(bootstrap_summary)
    centers = [float(np.median(bootstrap_summary[name]["angles"])) for name in labels]
    low = [center - bootstrap_summary[name]["angle_ci_95"][0] for name, center in zip(labels, centers, strict=True)]
    high = [bootstrap_summary[name]["angle_ci_95"][1] - center for name, center in zip(labels, centers, strict=True)]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.errorbar(np.arange(len(labels)), centers, yerr=[low, high], fmt="o", capsize=4)
    ax.axhline(float(config["gates"]["ec_oq_angle_bootstrap_lower_deg_min"]), color="tab:red", linestyle="--", label="15 degree lower-CI gate")
    ax.set_xticks(np.arange(len(labels)), labels, rotation=20, ha="right")
    ax.set(ylabel="maximum principal angle (deg)", title="Switch versus ordinary subspace bootstrap")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(angle_path, dpi=180)
    plt.close(fig)

    dual_path = ROOT / config["outputs"]["dual_geometry_figure"]
    protocols = list(anchor)
    information = [anchor[name]["information_ratio"] for name in protocols]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = np.arange(len(protocols))
    ax.bar(x - 0.18, information, width=0.36, label="solver information ratio")
    ax.bar(x + 0.18, [training.get("switch_condition_ratio", 0.0)] + [0.0] * (len(protocols) - 1), width=0.36, label="PINN condition ratio (locked protocol only)")
    ax.axhline(float(config["gates"]["switch_information_ratio_min"]), color="tab:blue", linestyle="--")
    ax.axhline(float(config["gates"]["switch_training_condition_ratio_min"]), color="tab:orange", linestyle=":")
    ax.set_xticks(x, protocols, rotation=20, ha="right")
    ax.set(ylabel="switch / ordinary ratio", title="Information and training geometry are distinct")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(dual_path, dpi=180)
    plt.close(fig)


def _report(summary: Mapping[str, Any], path: Path) -> None:
    decision = summary["decision"]
    lines = [
        "# Solver-first SID / EC-OQ strict review",
        "",
        f"Preregistered commit: `{summary['authorization']['locked_commit']}`.",
        "",
        "All physical-identifiability geometry uses solver-generated, noise-whitened terminal current only. "
        "No hidden fields, public labels, 13 V data, or PINN-predicted physics were used.",
        "",
        "## Numerical derivative gate",
        "",
        f"Converged cases: `{summary['derivative_audit']['passing_cases']}/{summary['derivative_audit']['total_cases']}`; "
        f"maximum relative discrepancy: `{summary['derivative_audit']['maximum_relative_difference']:.6g}`.",
        "",
        "## Event-window evidence",
        "",
        f"Best 95% bootstrap angle lower bound: `{summary['gate_metrics']['angle_ci_lower_deg']:.6g}` degrees; "
        f"best rank-change consistency: `{summary['gate_metrics']['rank_change_consistency']:.6g}`; "
        f"best switch information ratio: `{summary['gate_metrics']['switch_information_ratio']:.6g}`.",
        "",
        "## Training geometry boundary",
        "",
        f"The last finite Adam checkpoint supports only `{summary['training_geometry']['protocol_coverage']}`. "
        "It is therefore not evidence of a three-protocol dual geometry, even when its matrix-free VJP sketch is finite.",
        "",
        "## Decision",
        "",
        f"SID retained: `{decision['sid_retained']}`; EC-OQ retained: `{decision['ec_oq_retained']}`; "
        f"disposition: `{decision['disposition']}`.",
        "",
        "A finite targeted search cannot establish world-first novelty. Fisher/SVD identifiable combinations, "
        "event-aware differentiation, gradient balancing, NNCG/SOAP, PirateNet, causal schedules, IRK-PINN, "
        "DWR, PINO, DeepONet, and Preisach/LLP remain prior components or baselines.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run(config_path: Path) -> dict[str, Any]:
    config = _yaml(config_path)
    authorization = _authorization(config)
    output_paths = [ROOT / value for key, value in config["outputs"].items() if key != "preregistration"]
    if any(path.exists() for path in output_paths):
        existing = [str(path) for path in output_paths if path.exists()]
        raise FileExistsError(f"Refusing to overwrite SID evidence: {existing}")
    frozen_gt, frozen_params = load_frozen_gt(ROOT / "data/processed/gt_v1_acceptance/gt_triangle.npz")
    rank_threshold = float(config["derivative_audit"]["rank_relative_singular_threshold"])
    all_rows: list[dict[str, Any]] = []
    forward_evaluations = 0
    neighborhood_results: dict[str, Any] = {}
    event_payload: dict[str, Any] = {
        "schema_version": "sid_ec_oq_event_windows_v1",
        "definition": config["event_windows"],
        "posthoc_window_motion": False,
        "protocols": {},
    }
    for neighborhood in config["coordinates"]["neighborhoods"]:
        neighborhood_name = str(neighborhood["name"])
        params = _apply_neighborhood(frozen_params, config["coordinates"], neighborhood["signs"])
        neighborhood_results[neighborhood_name] = {}
        for protocol in config["protocols"]:
            name = str(protocol["name"])
            jacobian_result = _whitened_jacobians(protocol, params, config)
            forward_evaluations += int(jacobian_result["forward_evaluations"])
            base = jacobian_result["base"]
            windows = event_window_indices(
                np.asarray(base["t"]), np.asarray(base["I"]), np.asarray(base["m"]), np.asarray(base["T"]),
                switch_threshold_fraction=float(config["event_windows"]["switch_threshold_fraction"]),
                cooling_temperature_rate_fraction=float(config["event_windows"]["cooling_temperature_rate_fraction"]),
                minimum_points=int(config["event_windows"]["minimum_points"]),
                fallback_half_width_points=int(config["event_windows"]["fallback_half_width_points"]),
            )
            rows, geometries = _geometry_rows(
                name, neighborhood_name, jacobian_result["jacobian"], windows,
                jacobian_result["derivative_audit"], rank_threshold
            )
            all_rows.extend(rows)
            neighborhood_results[neighborhood_name][name] = {
                "jacobian": jacobian_result["jacobian"],
                "derivative_audit": jacobian_result["derivative_audit"],
                "windows": windows,
                "geometries": geometries,
                "base": base,
                "noise_sigma_A": jacobian_result["noise_sigma_A"],
            }
            if neighborhood_name == "anchor":
                event_payload["protocols"][name] = {
                    window: {
                        "indices": indices.tolist(),
                        "count": int(indices.size),
                        "t_start_s": float(np.asarray(base["t"])[indices[0]]),
                        "t_end_s": float(np.asarray(base["t"])[indices[-1]]),
                    }
                    for window, indices in windows.items()
                }

    if forward_evaluations > int(config["budget"]["solver_forward_evaluations_max"]):
        raise RuntimeError("SID solver budget exceeded before evidence write.")
    anchor = neighborhood_results["anchor"]
    bootstrap_rows: list[dict[str, Any]] = []
    bootstrap_summary: dict[str, Any] = {}
    for protocol_name, payload in anchor.items():
        windows = payload["windows"]
        ordinary_indices = np.concatenate([windows[name] for name in ("pre_switch", "post_switch", "cooling_recovery")])
        bootstrap = bootstrap_switch_geometry(
            payload["jacobian"][windows["switch"]],
            payload["jacobian"][ordinary_indices],
            replicates=int(config["bootstrap"]["replicates"]),
            seed=int(config["bootstrap"]["seed"]),
            relative_rank_threshold=rank_threshold,
        )
        for index, (angle, switch_rank, ordinary_rank) in enumerate(
            zip(bootstrap["maximum_principal_angle_deg"], bootstrap["switch_rank"], bootstrap["ordinary_rank"], strict=True)
        ):
            bootstrap_rows.append({
                "protocol": protocol_name, "replicate": index, "maximum_principal_angle_deg": float(angle),
                "switch_rank": int(switch_rank), "ordinary_rank": int(ordinary_rank),
                "rank_changed": bool(switch_rank != ordinary_rank),
            })
        switch_information = payload["geometries"]["switch"]["information_trace"]
        ordinary_information = [payload["geometries"][name]["information_trace"] for name in ("pre_switch", "post_switch", "cooling_recovery")]
        payload["information_ratio"] = float(switch_information / max(float(np.median(ordinary_information)), 1.0e-30))
        bootstrap_summary[protocol_name] = {
            "angles": bootstrap["maximum_principal_angle_deg"].tolist(),
            "angle_ci_95": bootstrap["angle_ci_95"],
            "rank_change_consistency": bootstrap["rank_change_consistency"],
        }

    pairwise_protocol_angles = []
    for first, second in combinations(anchor, 2):
        angles = principal_angles_deg(
            anchor[first]["geometries"]["switch"]["right_subspace"],
            anchor[second]["geometries"]["switch"]["right_subspace"],
        )
        pairwise_protocol_angles.append({"first": first, "second": second, "angles_deg": angles.tolist(), "maximum_deg": float(np.max(angles))})

    stable_protocols = []
    neighborhood_angles: list[dict[str, Any]] = []
    for protocol_name in anchor:
        stable = bool(anchor[protocol_name]["derivative_audit"]["pass"])
        for neighborhood_name in ("alternating_plus", "alternating_minus"):
            comparison = neighborhood_results[neighborhood_name][protocol_name]
            angles = principal_angles_deg(
                anchor[protocol_name]["geometries"]["switch"]["right_subspace"],
                comparison["geometries"]["switch"]["right_subspace"],
            )
            maximum = float(np.max(angles))
            neighborhood_angles.append({"protocol": protocol_name, "neighborhood": neighborhood_name, "maximum_angle_deg": maximum})
            stable = stable and bool(comparison["derivative_audit"]["pass"]) and maximum <= float(config["gates"]["direction_neighborhood_max_angle_deg"])
        if stable:
            stable_protocols.append(protocol_name)

    checkpoint_manifest = _json(ROOT / config["training_geometry"]["checkpoint_manifest"])
    checkpoint = ROOT / checkpoint_manifest["last_finite_adam_checkpoint"]
    model = _build_training_model(checkpoint, frozen_gt, frozen_params)
    training_base = _simulate(
        {"name": "locked_triangle_0p20", "protocol": "triangle", "t_max_s": 3.0e-3, "params": {"triangle_v_peak": 0.20}},
        frozen_params,
        config["solver"],
    )
    training_windows = event_window_indices(
        np.asarray(training_base["t"]), np.asarray(training_base["I"]), np.asarray(training_base["m"]), np.asarray(training_base["T"]),
        switch_threshold_fraction=float(config["event_windows"]["switch_threshold_fraction"]),
        cooling_temperature_rate_fraction=float(config["event_windows"]["cooling_temperature_rate_fraction"]),
        minimum_points=int(config["event_windows"]["minimum_points"]),
        fallback_half_width_points=int(config["event_windows"]["fallback_half_width_points"]),
    )
    training_geometry = _training_geometry(model, np.asarray(training_base["t"]), training_windows, config)

    derivative_cases = [
        payload["derivative_audit"]
        for neighborhood in neighborhood_results.values()
        for payload in neighborhood.values()
    ]
    best_angle_lower = max(value["angle_ci_95"][0] for value in bootstrap_summary.values())
    best_rank_consistency = max(value["rank_change_consistency"] for value in bootstrap_summary.values())
    best_information_ratio = max(payload["information_ratio"] for payload in anchor.values())
    dual_geometry_protocol_count = min(len(stable_protocols), len(training_geometry["protocol_coverage"]))
    gate_metrics = {
        "derivative_pass": all(value["pass"] for value in derivative_cases),
        "angle_ci_lower_deg": float(best_angle_lower),
        "rank_change_consistency": float(best_rank_consistency),
        "switch_information_ratio": float(best_information_ratio),
        "training_geometry_available": True,
        "switch_training_condition_ratio": float(training_geometry["switch_condition_ratio"]),
        "physical_stable_protocol_count": len(stable_protocols),
        "stable_protocol_count": dual_geometry_protocol_count,
        "neighborhood_direction_stable": len(stable_protocols) == len(config["protocols"]),
    }
    decision = sid_decision(gate_metrics, config["gates"])
    summary = {
        "schema_version": "sid_ec_oq_summary_v1",
        "stage_id": config["stage_id"],
        "authorization": authorization,
        "evidence_semantics": "solver_generated_noise_whitened_terminal_current_only",
        "solver_forward_evaluations": forward_evaluations,
        "budget_cap": int(config["budget"]["solver_forward_evaluations_max"]),
        "coordinates": config["coordinates"],
        "protocols": [protocol["name"] for protocol in config["protocols"]],
        "derivative_audit": {
            "passing_cases": int(sum(value["pass"] for value in derivative_cases)),
            "total_cases": len(derivative_cases),
            "maximum_relative_difference": float(max(value["maximum_relative_difference"] for value in derivative_cases)),
            "claim_allowed": all(value["pass"] for value in derivative_cases),
        },
        "anchor_protocols": {
            name: {
                "information_ratio": payload["information_ratio"],
                "derivative_audit": _jsonable({key: value for key, value in payload["derivative_audit"].items() if key != "richardson_jacobian"}),
                "windows": {window: _jsonable(geometry) for window, geometry in payload["geometries"].items()},
                "bootstrap": {key: value for key, value in bootstrap_summary[name].items() if key != "angles"},
            }
            for name, payload in anchor.items()
        },
        "pairwise_protocol_angles": pairwise_protocol_angles,
        "neighborhood_angles": neighborhood_angles,
        "stable_physical_protocols": stable_protocols,
        "training_geometry": training_geometry,
        "gate_metrics": gate_metrics,
        "decision": decision,
        "gamma_sub_mainline_preserved": True,
        "allowed_claim": "qualified solver-only event-window identifiability evidence" if decision["ec_oq_retained"] else "no new SID or EC-OQ claim",
        "forbidden_claims": ["PINN sensitivity fidelity", "physical parameter recovery", "experimental validation", "world-first SID or EC-OQ mechanism"],
    }
    atomic_json_write(ROOT / config["outputs"]["event_windows"], _jsonable(event_payload))
    _write_csv(ROOT / config["outputs"]["cases_csv"], all_rows)
    _write_csv(ROOT / config["outputs"]["bootstrap_csv"], bootstrap_rows)
    atomic_json_write(ROOT / config["outputs"]["summary"], _jsonable(summary))
    _figures(anchor, bootstrap_summary, training_geometry, config)
    _report(summary, ROOT / config["outputs"]["report"])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/sid_ec_oq_event_geometry.yaml"))
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    result = run(path)
    print(json.dumps({"decision": result["decision"]["disposition"], "sid": result["decision"]["sid_retained"], "ec_oq": result["decision"]["ec_oq_retained"]}, sort_keys=True))


if __name__ == "__main__":
    main()

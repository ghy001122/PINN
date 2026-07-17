"""Preregister and execute the bounded gamma_sub calibration-protocol cost frontier.

The CPCF is a synthetic numerical digital-twin decision audit.  Historical
response-surface evidence supplies the 48-case pilot, while a small locked set
of fresh ODE anchors checks that reuse against the independent numerical
solver.  It never trains or evaluates the full PINN.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_high_throughput_common import response_surface_relative_error
from scripts.gamma_sub_validation_common import (
    load_target,
    make_noisy,
    objective_components,
    observation_times,
    port_series,
    relative_error,
    target_from_params,
)

DEFAULT_CONFIG = Path("configs/gamma_sub_calibration_protocol_cost_frontier.yaml")
SCRIPT_PATH = Path("scripts/audit_gamma_sub_calibration_protocol_cost_frontier.py")
CASE_FIELDS = [
    "case_id",
    "operating_point_id",
    "strategy",
    "T_sw_prior_width_K",
    "effective_T_sw_delta_K",
    "protocol",
    "response_surface_protocol",
    "observation_count",
    "noise",
    "seed",
    "predicted_relative_error",
    "predicted_success",
    "predicted_abstention",
    "fresh_solver_anchor",
    "solver_relative_error",
    "solver_estimated_gamma_sub",
    "discrete_profile_width_fraction",
    "anchor_absolute_discrepancy",
    "anchor_classification_agreement",
    "solver_forward_evaluations",
    "source_kind",
    "cache_hit",
]
OPERATING_FIELDS = [
    "operating_point_id",
    "strategy",
    "T_sw_prior_width_K",
    "protocol",
    "observation_count",
    "median_relative_error",
    "success_rate",
    "error_ci95_low",
    "error_ci95_high",
    "error_ci95_width",
    "abstention_rate",
    "risk_index",
    "calibration_resource",
    "protocol_resource",
    "observation_resource",
    "normalized_resource_index",
    "locked_risk_qualified",
    "pareto_nondominated",
    "pareto_bootstrap_frequency",
    "stable_nondominated",
]


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _strict_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_value(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Non-finite value is forbidden in strict JSON: {number}")
        return number
    return value


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(_strict_value(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"
    _atomic_text(path, encoded)


def _atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _strict_value(row.get(field)) for field in fields})
    tmp.replace(path)


def _load_config(path: Path) -> dict[str, Any]:
    with _resolve(path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("CPCF config must be a mapping")
    return config


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _input_hashes(config: dict[str, Any]) -> dict[str, str]:
    actual: dict[str, str] = {}
    mismatches: dict[str, dict[str, str | None]] = {}
    for item in config["inputs"]:
        path = _resolve(item["path"])
        expected = str(item["sha256"]).lower()
        observed = _sha256(path).lower() if path.exists() else None
        actual[str(item["path"])] = observed or "missing"
        if observed != expected:
            mismatches[str(item["path"])] = {"expected": expected, "observed": observed}
    if mismatches:
        raise RuntimeError(f"CPCF input hash lock failed: {json.dumps(mismatches, sort_keys=True)}")
    return actual


def _definition_hashes() -> dict[str, str]:
    paths = [
        DEFAULT_CONFIG,
        SCRIPT_PATH,
        Path("scripts/audit_a7c_prompt30_evidence.py"),
        Path("tests/test_gamma_sub_calibration_protocol_cost_frontier.py"),
        Path("tests/test_prompt30_a7c_evidence_audit.py"),
        Path(".github/workflows/read_only_validation.yml"),
        Path(".github/workflows/full_validation.yml"),
    ]
    return {_display(_resolve(path)): _sha256(_resolve(path)) for path in paths if _resolve(path).exists()}


def write_preregistration(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_config(config_path)
    input_hashes = _input_hashes(config)
    status = _git("status", "--porcelain")
    if status:
        raise RuntimeError("Preregistration requires a clean worktree")
    payload = {
        "schema_version": "gamma_sub_cpcf_preregistration_v1",
        "stage_id": config["stage_id"],
        "definition_commit": _git("rev-parse", "HEAD"),
        "base_commit": config["base_commit"],
        "origin_main_at_lock": _git("rev-parse", "origin/main"),
        "git_dirty_at_lock": False,
        "config_path": _display(_resolve(config_path)),
        "config_sha256": _sha256(_resolve(config_path)),
        "input_hashes": input_hashes,
        "definition_hashes": _definition_hashes(),
        "pilot_case_cap": int(config["pilot"]["case_cap"]),
        "bootstrap_replicates": int(config["pilot"]["bootstrap_replicates"]),
        "full_sweep_gate": config["full_sweep_gate"],
        "allowed_claim_if_all_gates_pass": config["allowed_claim_if_all_gates_pass"],
        "failure_claim": config["failure_claim"],
        "forbidden_claims": config["forbidden_claims"],
        "frozen_gt_write_authorized": False,
        "full_pinn_training_authorized": False,
        "external_13v_access_authorized": False,
    }
    _atomic_json(_resolve(config["outputs"]["preregistration_json"]), payload)
    return payload


def _validate_preregistration(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    path = _resolve(config["outputs"]["preregistration_json"])
    if not path.exists():
        raise RuntimeError("Missing CPCF preregistration; run --preregister after the definition commit")
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = {
        "definition_commit": payload.get("definition_commit") == _git("rev-parse", "HEAD"),
        "config_sha256": payload.get("config_sha256") == _sha256(_resolve(config_path)),
        "inputs": payload.get("input_hashes") == _input_hashes(config),
        "definitions": payload.get("definition_hashes") == _definition_hashes(),
        "case_cap": int(payload.get("pilot_case_cap", -1)) == int(config["pilot"]["case_cap"]),
    }
    if not all(checks.values()):
        raise RuntimeError(f"CPCF preregistration validation failed: {checks}")
    return {"path": _display(path), "sha256": _sha256(path), "checks": checks, **payload}


def _pilot_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    anchors = set(config["pilot"]["anchor_case_ids"])
    for operating in config["operating_points"]:
        protocol = config["protocols"][operating["protocol"]]
        for replicate in config["replicates"]:
            case_id = f"{operating['id']}__{replicate['id']}"
            specs.append(
                {
                    **operating,
                    "noise": replicate["noise"],
                    "seed": replicate["seed"],
                    "replicate_id": replicate["id"],
                    "id": operating["id"],
                    "case_id": case_id,
                    "fresh_solver_anchor": case_id in anchors,
                    "response_surface_protocol": protocol["response_surface_protocol"],
                }
            )
    if len(specs) > int(config["pilot"]["case_cap"]):
        raise RuntimeError(f"Pilot has {len(specs)} cases, above locked cap {config['pilot']['case_cap']}")
    return specs


def _full_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    widths = [0.02, 0.05, 0.10, 0.20, 1.0]
    observations = [8, 16, 32, 64]
    specs: list[dict[str, Any]] = []
    for width in widths:
        for protocol_name, protocol in config["protocols"].items():
            for n_obs in observations:
                if width >= 1.0:
                    strategy = "protocol_only" if protocol_name != "ltp_ltd" else "no_design_baseline"
                elif protocol_name == "ltp_ltd":
                    strategy = "calibration_only"
                elif n_obs == 16:
                    strategy = "sequential_calibration_then_protocol"
                else:
                    strategy = "joint_calibration_protocol_design"
                point_id = f"full_w{int(width*100):03d}_{protocol_name}_n{n_obs}"
                for replicate in config["replicates"]:
                    specs.append(
                        {
                            "id": point_id,
                            "strategy": strategy,
                            "T_sw_prior_width": width,
                            "protocol": protocol_name,
                            "observation_count": n_obs,
                            "noise": replicate["noise"],
                            "seed": replicate["seed"],
                            "replicate_id": replicate["id"],
                            "case_id": f"{point_id}__{replicate['id']}",
                            "fresh_solver_anchor": False,
                            "response_surface_protocol": protocol["response_surface_protocol"],
                        }
                    )
    cap = int(config["full_sweep_gate"]["full_case_cap"])
    if len(specs) > cap:
        raise RuntimeError(f"Full sweep has {len(specs)} cases, above locked cap {cap}")
    return specs


def _fresh_solver_anchor(spec: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    target = load_target(config["inputs"][-2]["path"])
    base_params = dict(target["params"])
    true_gamma = float(base_params["gamma_sub"])
    protocol = config["protocols"][spec["protocol"]]
    simulation = dict(config["solver_anchor"]["simulation"])
    simulation["protocol"] = protocol["simulator_protocol"]
    overrides = {
        "ltp_v_pos": float(protocol["ltp_v_pos_V"]),
        "ltp_v_neg": float(protocol["ltp_v_neg_V"]),
    }
    effective_delta = float(config["solver_anchor"]["T_sw_reference_delta_K"]) * float(spec["T_sw_prior_width"])
    target_overrides = {**overrides, "T_sw": float(base_params["T_sw"]) + effective_delta}
    t_max = float(protocol["t_max_s"])
    target_gt = target_from_params(
        base_params=base_params,
        sim_config=simulation,
        true_gamma=true_gamma,
        t_max=t_max,
        target_overrides=target_overrides,
    )
    obs_time = observation_times(np.asarray(target_gt["t"], dtype=float), int(spec["observation_count"]))
    clean_g, clean_i = port_series(target_gt, obs_time)
    rng = np.random.default_rng(int(spec["seed"]))
    target_g = make_noisy(clean_g, float(spec["noise"]), rng)
    target_i = make_noisy(clean_i, float(spec["noise"]), rng)
    profiles: list[dict[str, float]] = []
    for gamma in [float(value) for value in config["solver_anchor"]["gamma_candidates"]]:
        candidate = target_from_params(
            base_params=base_params,
            sim_config=simulation,
            true_gamma=gamma,
            t_max=t_max,
            target_overrides=overrides,
        )
        components = objective_components(
            candidate,
            base_params,
            gamma,
            obs_time,
            target_g,
            target_i,
            config["solver_anchor"]["loss"],
        )
        profiles.append({"gamma_sub": gamma, **components})
    best = min(profiles, key=lambda row: row["objective"])
    objectives = np.asarray([row["objective"] for row in profiles], dtype=float)
    cutoff = float(np.min(objectives)) + float(config["solver_anchor"]["discrete_profile_span_fraction"]) * float(np.max(objectives) - np.min(objectives))
    retained = [row["gamma_sub"] for row in profiles if row["objective"] <= cutoff]
    profile_width = (max(retained) - min(retained)) / true_gamma if retained else 0.0
    error = relative_error(float(best["gamma_sub"]), true_gamma)
    return {
        "solver_relative_error": error,
        "solver_estimated_gamma_sub": float(best["gamma_sub"]),
        "discrete_profile_width_fraction": float(profile_width),
        "solver_forward_evaluations": 1 + len(profiles),
    }


def _cache_key(spec: dict[str, Any], config_hash: str, input_hashes: dict[str, str], script_hash: str) -> str:
    payload = {
        "spec": spec,
        "config_sha256": config_hash,
        "input_hashes": input_hashes,
        "script_sha256": script_hash,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _evaluate_case(
    spec: dict[str, Any],
    config: dict[str, Any],
    *,
    config_hash: str,
    input_hashes: dict[str, str],
    script_hash: str,
    resume: bool,
) -> dict[str, Any]:
    cache_dir = _resolve(config["pilot"]["cache_dir"])
    cache_path = cache_dir / f"{spec['case_id']}.json"
    key = _cache_key(spec, config_hash, input_hashes, script_hash)
    if resume and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("cache_key") == key:
            return {**cached["result"], "cache_hit": True}

    width = float(spec["T_sw_prior_width"])
    predicted = response_surface_relative_error(
        str(spec["response_surface_protocol"]),
        float(config["solver_anchor"]["T_sw_reference_delta_K"]),
        width,
        int(spec["observation_count"]),
        float(spec["noise"]),
    )
    success_threshold = float(config["risk"]["success_relative_error_threshold"])
    anchor_threshold = float(config["solver_anchor"]["classification_threshold"])
    result: dict[str, Any] = {
        "case_id": spec["case_id"],
        "operating_point_id": spec["id"],
        "strategy": spec["strategy"],
        "T_sw_prior_width_K": width,
        "effective_T_sw_delta_K": float(config["solver_anchor"]["T_sw_reference_delta_K"]) * width,
        "protocol": spec["protocol"],
        "response_surface_protocol": spec["response_surface_protocol"],
        "observation_count": int(spec["observation_count"]),
        "noise": float(spec["noise"]),
        "seed": int(spec["seed"]),
        "predicted_relative_error": float(predicted),
        "predicted_success": bool(predicted <= success_threshold),
        "predicted_abstention": bool(predicted > float(config["risk"]["abstention_relative_error_threshold"])),
        "fresh_solver_anchor": bool(spec["fresh_solver_anchor"]),
        "solver_relative_error": None,
        "solver_estimated_gamma_sub": None,
        "discrete_profile_width_fraction": None,
        "anchor_absolute_discrepancy": None,
        "anchor_classification_agreement": None,
        "solver_forward_evaluations": 0,
        "source_kind": "historical_response_surface_with_fresh_solver_anchor" if spec["fresh_solver_anchor"] else "historical_response_surface",
        "cache_hit": False,
    }
    if spec["fresh_solver_anchor"]:
        anchor = _fresh_solver_anchor(spec, config)
        result.update(anchor)
        result["anchor_absolute_discrepancy"] = abs(float(predicted) - float(anchor["solver_relative_error"]))
        result["anchor_classification_agreement"] = bool(
            (predicted <= anchor_threshold) == (float(anchor["solver_relative_error"]) <= anchor_threshold)
        )
    _atomic_json(cache_path, {"schema_version": "gamma_sub_cpcf_case_cache_v1", "cache_key": key, "result": result})
    return result


def _bootstrap_ci(values: np.ndarray, replicates: int, rng: np.random.Generator) -> tuple[float, float]:
    estimates = np.empty(replicates, dtype=float)
    for idx in range(replicates):
        sample = rng.choice(values, size=len(values), replace=True)
        estimates[idx] = float(np.median(sample))
    return float(np.percentile(estimates, 2.5)), float(np.percentile(estimates, 97.5))


def _resource_components(point: dict[str, Any], config: dict[str, Any]) -> dict[str, float]:
    resource = config["resource_index"]
    w_min, w_max = [float(value) for value in resource["calibration_width_range_K"]]
    width = float(point["T_sw_prior_width_K"])
    calibration = math.log(w_max / width) / max(math.log(w_max / w_min), 1.0e-30)
    protocol = config["protocols"][point["protocol"]]
    p_min, p_max = [float(value) for value in resource["protocol_cost_proxy_range"]]
    protocol_resource = (float(protocol["historical_cost_proxy"]) - p_min) / (p_max - p_min)
    n_min, n_max = [float(value) for value in resource["observation_count_range"]]
    observation = (float(point["observation_count"]) - n_min) / (n_max - n_min)
    return {
        "calibration_resource": float(np.clip(calibration, 0.0, 1.0)),
        "protocol_resource": float(np.clip(protocol_resource, 0.0, 1.0)),
        "observation_resource": float(np.clip(observation, 0.0, 1.0)),
    }


def _resource_index(components: dict[str, float], weights: dict[str, float]) -> float:
    return float(
        float(weights["calibration"]) * components["calibration_resource"]
        + float(weights["protocol"]) * components["protocol_resource"]
        + float(weights["observations"]) * components["observation_resource"]
    )


def _risk_from_errors(errors: np.ndarray, config: dict[str, Any]) -> dict[str, float]:
    threshold = float(config["risk"]["success_relative_error_threshold"])
    median = float(np.median(errors))
    success_rate = float(np.mean(errors <= threshold))
    abstention_rate = float(np.mean(errors > float(config["risk"]["abstention_relative_error_threshold"])))
    # The confidence-width term is filled by the caller after bootstrapping.
    return {"median": median, "success_rate": success_rate, "abstention_rate": abstention_rate}


def _risk_index(metrics: dict[str, float], ci_width: float, config: dict[str, Any]) -> float:
    threshold = float(config["risk"]["success_relative_error_threshold"])
    weights = config["risk"]["weights"]
    return float(
        float(weights["median_error"]) * (metrics["median"] / threshold)
        + float(weights["failure_rate"]) * (1.0 - metrics["success_rate"])
        + float(weights["ci_width"]) * (ci_width / threshold)
        + float(weights["abstention_rate"]) * metrics["abstention_rate"]
    )


def _nondominated(rows: list[dict[str, Any]], cost_key: str = "normalized_resource_index", risk_key: str = "risk_index") -> set[str]:
    frontier: set[str] = set()
    for row in rows:
        dominated = False
        for other in rows:
            if other is row:
                continue
            no_worse = float(other[cost_key]) <= float(row[cost_key]) and float(other[risk_key]) <= float(row[risk_key])
            strictly_better = float(other[cost_key]) < float(row[cost_key]) or float(other[risk_key]) < float(row[risk_key])
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.add(str(row["operating_point_id"]))
    return frontier


def _summarize_operating_points(cases: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in cases:
        grouped.setdefault(str(row["operating_point_id"]), []).append(row)
    bootstrap_replicates = int(config["pilot"]["bootstrap_replicates"])
    rng = np.random.default_rng(int(config["random_seed"]))
    primary_name = str(config["resource_index"]["primary_weights"])
    primary_weights = config["resource_index"]["weight_sets"][primary_name]
    rows: list[dict[str, Any]] = []
    errors_by_point: dict[str, np.ndarray] = {}
    for point_id, group in sorted(grouped.items()):
        errors = np.asarray([float(row["predicted_relative_error"]) for row in sorted(group, key=lambda item: item["case_id"])], dtype=float)
        errors_by_point[point_id] = errors
        metrics = _risk_from_errors(errors, config)
        low, high = _bootstrap_ci(errors, bootstrap_replicates, rng)
        ci_width = high - low
        first = group[0]
        point = {
            "operating_point_id": point_id,
            "strategy": first["strategy"],
            "T_sw_prior_width_K": float(first["T_sw_prior_width_K"]),
            "protocol": first["protocol"],
            "observation_count": int(first["observation_count"]),
            "median_relative_error": metrics["median"],
            "success_rate": metrics["success_rate"],
            "error_ci95_low": low,
            "error_ci95_high": high,
            "error_ci95_width": ci_width,
            "abstention_rate": metrics["abstention_rate"],
            "risk_index": _risk_index(metrics, ci_width, config),
        }
        components = _resource_components(point, config)
        point.update(components)
        point["normalized_resource_index"] = _resource_index(components, primary_weights)
        point["locked_risk_qualified"] = bool(
            metrics["median"] <= float(config["risk"]["success_relative_error_threshold"])
            and metrics["success_rate"] >= float(config["risk"]["minimum_operating_point_success_rate"])
        )
        rows.append(point)

    frontier = _nondominated(rows)
    counts = {row["operating_point_id"]: 0 for row in rows}
    for _ in range(bootstrap_replicates):
        sampled_rows: list[dict[str, Any]] = []
        for row in rows:
            values = errors_by_point[row["operating_point_id"]]
            sample = rng.choice(values, size=len(values), replace=True)
            metrics = _risk_from_errors(sample, config)
            low, high = _bootstrap_ci(sample, 40, rng)
            sampled_rows.append({**row, "risk_index": _risk_index(metrics, high - low, config)})
        for point_id in _nondominated(sampled_rows):
            counts[point_id] += 1
    stability_min = float(config["full_sweep_gate"]["stable_frontier_bootstrap_frequency_min"])
    for row in rows:
        frequency = counts[row["operating_point_id"]] / bootstrap_replicates
        row["pareto_nondominated"] = row["operating_point_id"] in frontier
        row["pareto_bootstrap_frequency"] = frequency
        row["stable_nondominated"] = bool(row["pareto_nondominated"] and frequency >= stability_min)
    return rows, errors_by_point


def _improvement_gate(
    rows: list[dict[str, Any]],
    errors_by_point: dict[str, np.ndarray],
    config: dict[str, Any],
) -> dict[str, Any]:
    references = [row for row in rows if row["strategy"] == "calibration_only" and row["locked_risk_qualified"]]
    if not references:
        return {"pass": False, "reason": "no calibration-only reference meets the locked risk gate", "selected": None}
    reference = min(references, key=lambda row: row["normalized_resource_index"])
    min_cost = float(config["full_sweep_gate"]["minimum_cost_reduction_same_risk"])
    min_risk = float(config["full_sweep_gate"]["minimum_risk_reduction_same_cost"])
    same_risk_tol = float(config["full_sweep_gate"]["same_risk_relative_tolerance"])
    same_cost_tol = float(config["full_sweep_gate"]["same_cost_relative_tolerance"])
    candidates: list[dict[str, Any]] = []
    for candidate in rows:
        if candidate["strategy"] == "calibration_only" or not candidate["locked_risk_qualified"]:
            continue
        ref_cost = max(float(reference["normalized_resource_index"]), 1.0e-30)
        ref_risk = max(float(reference["risk_index"]), 1.0e-30)
        cost_reduction = (ref_cost - float(candidate["normalized_resource_index"])) / ref_cost
        risk_reduction = (ref_risk - float(candidate["risk_index"])) / ref_risk
        same_risk = bool(float(candidate["risk_index"]) <= ref_risk * (1.0 + same_risk_tol) and cost_reduction >= min_cost)
        same_cost = bool(float(candidate["normalized_resource_index"]) <= ref_cost * (1.0 + same_cost_tol) and risk_reduction >= min_risk)
        if same_risk or same_cost:
            candidates.append(
                {
                    "reference": reference["operating_point_id"],
                    "candidate": candidate["operating_point_id"],
                    "cost_reduction": cost_reduction,
                    "risk_reduction": risk_reduction,
                    "same_risk_cost_reduction_pass": same_risk,
                    "same_cost_risk_reduction_pass": same_cost,
                }
            )
    if not candidates:
        return {"pass": False, "reason": "no candidate reaches the locked 20 percent improvement", "selected": None}
    selected = max(candidates, key=lambda item: max(item["cost_reduction"], item["risk_reduction"]))
    ref_errors = errors_by_point[selected["reference"]]
    cand_errors = errors_by_point[selected["candidate"]]
    rng = np.random.default_rng(int(config["random_seed"]) + 1)
    reps = int(config["pilot"]["bootstrap_replicates"])
    differences = np.empty(reps, dtype=float)
    for idx in range(reps):
        draw = rng.integers(0, len(ref_errors), size=len(ref_errors))
        ref_metrics = _risk_from_errors(ref_errors[draw], config)
        cand_metrics = _risk_from_errors(cand_errors[draw], config)
        ref_risk = _risk_index(ref_metrics, 0.0, config)
        cand_risk = _risk_index(cand_metrics, 0.0, config)
        differences[idx] = ref_risk - cand_risk
    ci = [float(np.percentile(differences, 2.5)), float(np.percentile(differences, 97.5))]
    selected["bootstrap_risk_improvement_ci95"] = ci
    selected["bootstrap_direction_excludes_zero"] = bool(ci[0] > 0.0)
    return {"pass": True, "reason": "at least one locked comparison reaches 20 percent", "selected": selected, "all_candidates": candidates}


def _anchor_gate(cases: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    anchors = [row for row in cases if row["fresh_solver_anchor"]]
    discrepancies = np.asarray([float(row["anchor_absolute_discrepancy"]) for row in anchors], dtype=float)
    agreements = [bool(row["anchor_classification_agreement"]) for row in anchors]
    tolerance = config["solver_anchor"]["historical_tolerance"]
    metrics = {
        "fresh_anchor_count": len(anchors),
        "solver_forward_evaluations": int(sum(int(row["solver_forward_evaluations"]) for row in anchors)),
        "mean_absolute_discrepancy": float(np.mean(discrepancies)),
        "maximum_absolute_discrepancy": float(np.max(discrepancies)),
        "classification_agreement_rate": float(np.mean(agreements)),
        "disagreement_count": int(sum(not value for value in agreements)),
    }
    checks = {
        "mean_absolute_discrepancy": metrics["mean_absolute_discrepancy"] <= float(tolerance["mean_absolute_discrepancy_max"]),
        "classification_agreement": metrics["classification_agreement_rate"] >= float(tolerance["classification_agreement_min"]),
        "disagreement_count": metrics["disagreement_count"] <= int(tolerance["disagreement_count_max"]),
    }
    return {"pass": all(checks.values()), "checks": checks, "metrics": metrics, "locked_tolerance": tolerance}


def _pareto_rows(operating: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for weight_name, weights in config["resource_index"]["weight_sets"].items():
        expanded: list[dict[str, Any]] = []
        for point in operating:
            cost = _resource_index(point, weights)
            expanded.append({**point, "cost_weight_set": weight_name, "resource_index": cost})
        frontier = _nondominated(expanded, cost_key="resource_index", risk_key="risk_index")
        for point in expanded:
            rows.append(
                {
                    "cost_weight_set": weight_name,
                    "operating_point_id": point["operating_point_id"],
                    "strategy": point["strategy"],
                    "resource_index": point["resource_index"],
                    "risk_index": point["risk_index"],
                    "median_relative_error": point["median_relative_error"],
                    "success_rate": point["success_rate"],
                    "abstention_rate": point["abstention_rate"],
                    "nondominated": point["operating_point_id"] in frontier,
                }
            )
    return rows


def _write_figure(rows: list[dict[str, Any]], path: Path, primary_weights: str) -> None:
    primary = [row for row in rows if row["cost_weight_set"] == primary_weights]
    colors = {
        "calibration_only": "#1f77b4",
        "protocol_only": "#ff7f0e",
        "sequential_calibration_then_protocol": "#2ca02c",
        "joint_calibration_protocol_design": "#9467bd",
        "no_design_baseline": "#7f7f7f",
    }
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for strategy in sorted({row["strategy"] for row in primary}):
        subset = [row for row in primary if row["strategy"] == strategy]
        ax.scatter(
            [row["resource_index"] for row in subset],
            [row["risk_index"] for row in subset],
            s=[80 if row["nondominated"] else 45 for row in subset],
            marker="o",
            color=colors.get(strategy, "black"),
            edgecolor="black",
            linewidth=0.5,
            label=strategy.replace("_", " "),
        )
    frontier = sorted([row for row in primary if row["nondominated"]], key=lambda row: row["resource_index"])
    if frontier:
        ax.plot([row["resource_index"] for row in frontier], [row["risk_index"] for row in frontier], color="black", linewidth=1.0, linestyle="--", label="pilot Pareto frontier")
    ax.set_xlabel("Normalized resource index (non-monetary)")
    ax.set_ylabel("Locked composite inversion risk")
    ax.set_title("Calibration–Protocol Cost Frontier: bounded synthetic pilot")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fig.savefig(tmp, format="png", dpi=180)
    plt.close(fig)
    tmp.replace(path)


def run_cpcf(config_path: Path = DEFAULT_CONFIG, *, mode: str = "pilot", resume: bool = False, max_workers: int | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    config = _load_config(config_path)
    prereg = _validate_preregistration(config, config_path)
    if mode == "full":
        pilot_summary_path = _resolve(config["outputs"]["pilot_summary_json"])
        if not pilot_summary_path.exists():
            raise RuntimeError("Full sweep requires a completed pilot summary")
        pilot_summary = json.loads(pilot_summary_path.read_text(encoding="utf-8"))
        if not bool(pilot_summary.get("full_sweep_triggered")):
            raise RuntimeError("Pilot gates failed; the preregistration forbids a full sweep")
        specs = _full_specs(config)
    else:
        specs = _pilot_specs(config)

    input_hashes = _input_hashes(config)
    config_hash = _sha256(_resolve(config_path))
    script_hash = _sha256(_resolve(SCRIPT_PATH))
    worker_cap = int(config["pilot"]["max_workers"])
    workers = max(1, min(int(max_workers or worker_cap), worker_cap))
    evaluate = lambda spec: _evaluate_case(
        spec,
        config,
        config_hash=config_hash,
        input_hashes=input_hashes,
        script_hash=script_hash,
        resume=resume,
    )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        cases = list(executor.map(evaluate, specs))
    cases.sort(key=lambda row: row["case_id"])
    operating, errors_by_point = _summarize_operating_points(cases, config)
    stable_count = sum(bool(row["stable_nondominated"]) for row in operating)
    anchor = _anchor_gate(cases, config) if mode == "pilot" else {"pass": True, "reason": "pilot anchor gate already passed"}
    improvement = _improvement_gate(operating, errors_by_point, config)
    selected = improvement.get("selected") or {}
    gates = {
        "a_solver_anchor_consistency": bool(anchor["pass"]),
        "b_two_stable_nondominated_points": stable_count >= int(config["full_sweep_gate"]["minimum_stable_nondominated_points"]),
        "c_twenty_percent_cost_or_risk_improvement": bool(improvement["pass"]),
        "d_bootstrap_direction_excludes_zero": bool(selected.get("bootstrap_direction_excludes_zero", False)),
    }
    all_pilot_gates = all(gates.values())
    pareto = _pareto_rows(operating, config)
    outputs = config["outputs"]
    cases_path = _resolve(outputs["pilot_cases_csv"] if mode == "pilot" else outputs["full_cases_csv"])
    summary_path = _resolve(outputs["pilot_summary_json"] if mode == "pilot" else outputs["full_summary_json"])
    _atomic_csv(cases_path, cases, CASE_FIELDS)
    _atomic_csv(_resolve(outputs["pilot_operating_points_csv"]), operating, OPERATING_FIELDS)
    pareto_fields = ["cost_weight_set", "operating_point_id", "strategy", "resource_index", "risk_index", "median_relative_error", "success_rate", "abstention_rate", "nondominated"]
    _atomic_csv(_resolve(outputs["pareto_source_csv"]), pareto, pareto_fields)
    _write_figure(pareto, _resolve(outputs["pareto_figure"]), str(config["resource_index"]["primary_weights"]))
    elapsed = time.perf_counter() - started
    summary = {
        "schema_version": f"gamma_sub_cpcf_{mode}_summary_v1",
        "stage_id": config["stage_id"],
        "mode": mode,
        "evidence_type": config["evidence_type"],
        "source_semantics": "historical response-surface cases with a locked small set of fresh independent-solver anchors",
        "preregistration": {"path": prereg["path"], "sha256": prereg["sha256"], "definition_commit": prereg["definition_commit"]},
        "config_sha256": config_hash,
        "input_hashes": input_hashes,
        "case_count": len(cases),
        "operating_point_count": len(operating),
        "fresh_solver_anchor_count": sum(bool(row["fresh_solver_anchor"]) for row in cases),
        "solver_forward_evaluations": sum(int(row["solver_forward_evaluations"]) for row in cases),
        "cache_hits": sum(bool(row["cache_hit"]) for row in cases),
        "cache_misses": sum(not bool(row["cache_hit"]) for row in cases),
        "max_workers": workers,
        "elapsed_seconds": elapsed,
        "anchor_gate": anchor,
        "stable_nondominated_count": stable_count,
        "improvement_gate": improvement,
        "gates": gates,
        "all_pilot_expansion_gates_pass": all_pilot_gates,
        "full_sweep_triggered": bool(mode == "pilot" and all_pilot_gates),
        "full_sweep_executed": bool(mode == "full"),
        "claim_status": "qualified_supported" if mode == "full" and all_pilot_gates else "failed_but_informative",
        "cpcf_main_claim_eligible": bool(mode == "full" and all_pilot_gates),
        "allowed_claim": config["allowed_claim_if_all_gates_pass"] if mode == "full" and all_pilot_gates else config["failure_claim"],
        "forbidden_claims": config["forbidden_claims"],
        "resource_semantics": "transparent normalized resource index; no monetary or laboratory cost data",
        "profile_semantics": "fresh anchors report a discrete candidate-profile width; operating-point uncertainty uses case bootstrap and is not cross-device generalization",
        "outputs": {
            "cases_csv": _display(cases_path),
            "operating_points_csv": outputs["pilot_operating_points_csv"],
            "pareto_source_csv": outputs["pareto_source_csv"],
            "pareto_figure": outputs["pareto_figure"],
            "summary_json": _display(summary_path),
        },
        "frozen_gt_modified": False,
        "full_pinn_run": False,
        "external_13v_accessed": False,
    }
    _atomic_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-workers", type=int)
    parser.add_argument("--preregister", action="store_true")
    args = parser.parse_args()
    if args.preregister:
        result = write_preregistration(args.config)
    else:
        result = run_cpcf(args.config, mode=args.mode, resume=args.resume, max_workers=args.max_workers)
    print(json.dumps(_strict_value(result), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

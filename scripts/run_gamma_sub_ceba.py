"""Run commit-ordered CEBA preregistration, parity, and a fail-closed pilot."""

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
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pinnpcm.physics.voltage_protocols import ltp_ltd_voltage, triangle_voltage
from scripts.audit_gamma_sub_multi_protocol_recoverability import _loss_from_series as historical_objective
from scripts.gamma_sub_validation_common import load_target, make_noisy, observation_times, port_series, simulate_with_overrides

DEFAULT_CONFIG = ROOT / "configs" / "gamma_sub_ceba_v1.yaml"
SCRIPT_PATH = ROOT / "scripts" / "run_gamma_sub_ceba.py"

PARITY_FIELDS = [
    "anchor_id",
    "protocol",
    "source_scenario",
    "delta_T_sw_K",
    "observation_count",
    "historical_gamma_est",
    "ceba_gamma_est",
    "historical_relative_error",
    "ceba_relative_error",
    "historical_objective",
    "ceba_objective",
    "best_gamma_pass",
    "relative_error_pass",
    "recoverable_classification_pass",
    "objective_value_pass",
    "objective_ordering_pass",
    "waveform_hash_pass",
    "solver_config_hash_pass",
    "all_core_gates_pass",
]

PILOT_FIELDS = [
    "phase",
    "protocol",
    "delta_T_sw_K",
    "observation_count",
    "noise",
    "seed",
    "solver_level",
    "gamma_est",
    "relative_error",
    "objective",
    "retained_candidate_count",
    "abstained",
    "success",
    "target_cache_key",
]


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = yaml.safe_load(_resolve(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CEBA config must be a mapping")
    return payload


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Non-finite JSON value: {number}")
        return number
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _jsonable(row.get(field)) for field in fields})
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _array_hash(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes(order="C")).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _protocol_target_path(config: dict[str, Any], protocol: str) -> Path:
    key = "triangle_target" if protocol == "triangle" else "ltp_ltd_target"
    return _resolve(config["source_contract"][key])


def _source_simulation(config: dict[str, Any], protocol: str, level: str = "base") -> dict[str, Any]:
    solver = config["solver"][level]
    nt_key = "nt_triangle" if protocol == "triangle" else "nt_ltp_ltd"
    return {
        "nx": int(solver["nx"]),
        "nt": int(solver[nt_key]),
        "protocol": protocol,
        "method": str(solver["method"]),
        "rtol": float(solver["rtol"]),
        "atol": float(solver["atol"]),
    }


def _protocol_params(config: dict[str, Any], protocol: str, base_params: dict[str, Any]) -> dict[str, Any]:
    params = dict(base_params)
    waveform = config["protocols"][protocol]["waveform_parameters"]
    if protocol == "triangle":
        params["triangle_v_peak"] = float(waveform["triangle_v_peak"])
    else:
        params["ltp_v_pos"] = float(waveform["ltp_v_pos"])
        params["ltp_v_neg"] = float(waveform["ltp_v_neg"])
    return params


def waveform_contract(config: dict[str, Any], protocol: str) -> dict[str, Any]:
    spec = config["protocols"][protocol]
    t_max = float(spec["t_max_s"])
    time_grid = np.linspace(0.0, t_max, int(config["waveform_hash_grid_points"]), dtype=float)
    params = spec["waveform_parameters"]
    if protocol == "triangle":
        voltage = triangle_voltage(time_grid, t_max, v_peak=float(params["triangle_v_peak"]))
    else:
        voltage = ltp_ltd_voltage(
            time_grid,
            t_max,
            v_pos=float(params["ltp_v_pos"]),
            v_neg=float(params["ltp_v_neg"]),
            n_pos=int(params["n_pos"]),
            n_neg=int(params["n_neg"]),
        )
    return {
        "protocol": protocol,
        "simulator_protocol": spec["simulator_protocol"],
        "t_max_s": t_max,
        "waveform_parameters": params,
        "pulse_count": spec["pulse_count"],
        "pulse_width_s": spec.get("pulse_width_s"),
        "pulse_spacing_s": spec.get("pulse_spacing_s"),
        "pulse_width_fraction_of_period": spec.get("pulse_width_fraction_of_period"),
        "pulse_spacing_fraction_of_period": spec.get("pulse_spacing_fraction_of_period"),
        "time_grid_points": int(time_grid.size),
        "time_grid_sha256": _array_hash(time_grid),
        "waveform_sha256": _array_hash(voltage),
    }


def solver_contract(config: dict[str, Any], protocol: str, level: str, base_params: dict[str, Any]) -> dict[str, Any]:
    simulation = _source_simulation(config, protocol, level)
    physical_params = _protocol_params(config, protocol, base_params)
    payload = {
        "solver_level": level,
        "protocol": protocol,
        "simulation": simulation,
        "t_max_s": float(config["protocols"][protocol]["t_max_s"]),
        "physical_parameter_sha256": _canonical_hash(physical_params),
        "objective": config["inverse"]["objective"],
        "gamma_candidates": [float(value) for value in config["inverse"]["gamma_candidates"]],
    }
    return payload | {"solver_config_sha256": _canonical_hash(payload)}


def _candidate_cache_key(waveform_hash: str, gamma_sub: float, solver_hash: str) -> str:
    return f"{waveform_hash}|gamma_sub={float(gamma_sub):.17g}|{solver_hash}"


def _target_cache_key(waveform_hash: str, delta_T_sw_K: float, solver_hash: str) -> str:
    return f"{waveform_hash}|delta_T_sw_K={float(delta_T_sw_K):.17g}|{solver_hash}"


class TrajectoryCache:
    def __init__(self, config: dict[str, Any], *, elapsed_offset_seconds: float = 0.0) -> None:
        self.config = config
        self.root = _resolve(config["budget"]["trajectory_cache"])
        self.root.mkdir(parents=True, exist_ok=True)
        self.resume_path = _resolve(config["budget"]["resume_state"])
        self.started = time.perf_counter()
        self.elapsed_offset = float(elapsed_offset_seconds)
        self.seen_keys: set[str] = set()
        self.hits = 0
        self.misses = 0

    def elapsed_seconds(self) -> float:
        return self.elapsed_offset + time.perf_counter() - self.started

    def _save_resume(self, reason: str) -> None:
        _atomic_json(
            self.resume_path,
            {
                "schema_version": "gamma_sub_ceba_resume_v1",
                "reason": reason,
                "seen_unique_solver_trajectory_count": len(self.seen_keys),
                "cache_hits": self.hits,
                "cache_misses": self.misses,
                "elapsed_seconds": self.elapsed_seconds(),
            },
        )

    def _check_budget(self, prospective_key: str) -> None:
        maximum = int(self.config["budget"]["maximum_unique_solver_trajectories"])
        if prospective_key not in self.seen_keys and len(self.seen_keys) >= maximum:
            self._save_resume("maximum_unique_solver_trajectories")
            raise RuntimeError("CEBA unique solver trajectory budget exhausted")
        seconds = 60.0 * float(self.config["budget"]["maximum_wall_time_minutes"])
        if self.elapsed_seconds() >= seconds:
            self._save_resume("maximum_wall_time")
            raise RuntimeError("CEBA wall-time budget exhausted")

    def load_or_simulate(
        self,
        *,
        role: str,
        protocol: str,
        coordinate: float,
        solver_level: str,
        base_params: dict[str, Any],
        waveform: dict[str, Any],
        solver: dict[str, Any],
    ) -> tuple[dict[str, np.ndarray], str, bool]:
        if role == "candidate":
            key = _candidate_cache_key(waveform["waveform_sha256"], coordinate, solver["solver_config_sha256"])
        elif role == "target":
            key = _target_cache_key(waveform["waveform_sha256"], coordinate, solver["solver_config_sha256"])
        else:
            raise ValueError(f"Unsupported trajectory role: {role}")
        self._check_budget(key)
        self.seen_keys.add(key)
        path = self.root / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as payload:
                observed_key = str(payload["cache_key"].item())
                if observed_key != key:
                    raise RuntimeError(f"Trajectory cache key mismatch: {path}")
                trace = {name: np.asarray(payload[name], dtype=float) for name in ("t", "G", "I")}
            self.hits += 1
            return trace, key, True

        params = _protocol_params(self.config, protocol, base_params)
        overrides: dict[str, float] = {}
        true_gamma = float(self.config["inverse"]["true_gamma_sub"])
        gamma = float(coordinate) if role == "candidate" else true_gamma
        if role == "target":
            overrides["T_sw"] = float(params["T_sw"]) + float(coordinate)
        trace_full = simulate_with_overrides(
            params,
            _source_simulation(self.config, protocol, solver_level),
            gamma_sub=gamma,
            t_max=float(self.config["protocols"][protocol]["t_max_s"]),
            param_overrides=overrides,
        )
        trace = {name: np.asarray(trace_full[name], dtype=float) for name in ("t", "G", "I")}
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, cache_key=np.asarray(key), **trace)
        temporary.replace(path)
        self.misses += 1
        self._save_resume("in_progress")
        return trace, key, False


def ceba_objective(
    pred_g: np.ndarray,
    pred_i: np.ndarray,
    target_g: np.ndarray,
    target_i: np.ndarray,
    weights: dict[str, Any],
) -> dict[str, float]:
    denom_g = max(float(np.sqrt(np.mean(np.asarray(target_g, dtype=float) ** 2))), 1.0e-30)
    denom_i = max(float(np.sqrt(np.mean(np.asarray(target_i, dtype=float) ** 2))), 1.0e-30)
    g_loss = float(np.sqrt(np.mean((np.asarray(pred_g) - np.asarray(target_g)) ** 2)) / denom_g) ** 2
    i_loss = float(np.sqrt(np.mean((np.asarray(pred_i) - np.asarray(target_i)) ** 2)) / denom_i) ** 2
    objective = float(weights["w_g"]) * g_loss + float(weights["w_i"]) * i_loss
    return {"objective": objective, "G_loss": g_loss, "I_loss": i_loss}


def _relative_error(value: float, truth: float) -> float:
    return abs(float(value) - float(truth)) / max(abs(float(truth)), 1.0e-30)


def _score_trace(
    *,
    target: dict[str, np.ndarray],
    candidates: dict[float, dict[str, np.ndarray]],
    observation_count: int,
    noise: float,
    seed: int,
    weights: dict[str, Any],
    true_gamma: float,
    retention_span_fraction: float,
) -> tuple[dict[str, Any], list[dict[str, float]]]:
    obs_time = observation_times(target["t"], observation_count)
    target_g_clean, target_i_clean = port_series(target, obs_time)
    rng = np.random.default_rng(seed)
    target_g = make_noisy(target_g_clean, noise, rng)
    target_i = make_noisy(target_i_clean, noise, rng)
    profile: list[dict[str, float]] = []
    for gamma, candidate in sorted(candidates.items()):
        pred_g, pred_i = port_series(candidate, obs_time)
        components = ceba_objective(pred_g, pred_i, target_g, target_i, weights)
        source_components = historical_objective(pred_g, pred_i, target_g, target_i, weights)
        profile.append({"gamma_sub": float(gamma), **components, "historical_objective": float(source_components["objective"])})
    ordered = sorted(profile, key=lambda row: (float(row["objective"]), float(row["gamma_sub"])))
    best = ordered[0]
    objectives = np.asarray([float(row["objective"]) for row in profile], dtype=float)
    span = float(np.max(objectives) - np.min(objectives))
    cutoff = float(best["objective"]) + float(retention_span_fraction) * span
    retained = [row for row in profile if float(row["objective"]) <= cutoff + 1.0e-18]
    threshold = 0.15
    retained_classes = {_relative_error(row["gamma_sub"], true_gamma) <= threshold + 1.0e-15 for row in retained}
    abstained = len(retained_classes) > 1
    error = _relative_error(best["gamma_sub"], true_gamma)
    return (
        {
            "gamma_est": float(best["gamma_sub"]),
            "relative_error": float(error),
            "objective": float(best["objective"]),
            "retained_candidate_count": len(retained),
            "retained_gamma_sub": [float(row["gamma_sub"]) for row in retained],
            "abstained": bool(abstained),
            "success": bool(error <= threshold + 1.0e-15 and not abstained),
            "objective_ordering": [float(row["gamma_sub"]) for row in ordered],
            "historical_objective_ordering": [
                float(row["gamma_sub"])
                for row in sorted(profile, key=lambda item: (float(item["historical_objective"]), float(item["gamma_sub"])))
            ],
        },
        profile,
    )


def _definition_locks(config: dict[str, Any]) -> dict[str, Any]:
    protocols: dict[str, Any] = {}
    physical_params: dict[str, Any] = {}
    for protocol in config["protocols"]:
        target = load_target(_protocol_target_path(config, protocol))
        params = _protocol_params(config, protocol, dict(target["params"]))
        physical_params[protocol] = params
        protocols[protocol] = {
            "waveform": waveform_contract(config, protocol),
            "base_solver": solver_contract(config, protocol, "base", params),
            "refinement_solver": solver_contract(config, protocol, "refinement", params),
        }
    locked_files = {
        "config": _resolve(DEFAULT_CONFIG),
        "implementation": SCRIPT_PATH,
        "source_config": _resolve(config["source_contract"]["config"]),
        "source_implementation": _resolve(config["source_contract"]["implementation"]),
        "source_cases": _resolve(config["source_contract"]["cases"]),
        "triangle_target": _resolve(config["source_contract"]["triangle_target"]),
        "ltp_ltd_target": _resolve(config["source_contract"]["ltp_ltd_target"]),
    }
    return {
        "definition_file_sha256": {name: _sha256_file(path) for name, path in locked_files.items()},
        "definition_file_paths": {name: _display(path) for name, path in locked_files.items()},
        "protocol_contracts": protocols,
        "physical_parameters": physical_params,
        "physical_parameter_sha256": {protocol: _canonical_hash(params) for protocol, params in physical_params.items()},
    }


def preregister(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_config(config_path)
    if len(config["parity"]["anchors"]) > int(config["parity"]["maximum_anchors"]):
        raise RuntimeError("Parity anchor cap exceeded")
    locks = _definition_locks(config)
    output = _resolve(config["outputs"]["preregistration"])
    result = {
        "schema_version": "gamma_sub_ceba_preregistration_v1",
        "stage_id": config["stage_id"],
        "definition_commit": _git("rev-parse", "HEAD"),
        "git_dirty_before_registration": bool(_git("status", "--porcelain")),
        "registration_semantics": "internal commit-ordered preregistration; not an independent remote timestamp",
        "internal_commit_ordered_preregistration": True,
        "independent_remote_timestamp": False,
        "scientific_hypothesis": "A direct-solver calibration-excitation boundary may exist for gamma_sub within the locked synthetic configuration, with explicit abstention when the discrete profile is ambiguous.",
        "research_quantity": "delta_T_sw_star(protocol, observation_count, noise) in absolute K",
        "parity": config["parity"],
        "pilot": config["pilot"],
        "budget": config["budget"],
        "inverse": config["inverse"],
        "allowed_claim_if_all_gates_pass": config["allowed_claim_if_all_gates_pass"],
        "forbidden_claims": config["forbidden_claims"],
        "locks": locks,
        "no_solver_run": True,
        "full_pinn_run": False,
        "external_13v_accessed": False,
    }
    _atomic_json(output, result)
    return result


def _validate_preregistration(config: dict[str, Any]) -> dict[str, Any]:
    path = _resolve(config["outputs"]["preregistration"])
    if not path.exists():
        raise RuntimeError("CEBA preregistration is missing")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    current = _definition_locks(config)
    if prereg.get("locks", {}).get("definition_file_sha256") != current["definition_file_sha256"]:
        raise RuntimeError("CEBA definition changed after preregistration")
    definition_commit = str(prereg["definition_commit"])
    subprocess.check_call(["git", "merge-base", "--is-ancestor", definition_commit, "HEAD"], cwd=ROOT)
    return prereg


def _load_source_cases(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _historical_anchor_row(rows: list[dict[str, str]], anchor: dict[str, Any], observation_count: int) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if row["protocol"] == anchor["protocol"]
        and row["scenario"] == anchor["source_scenario"]
        and int(row["observation_count"]) == observation_count
        and float(row["noise"]) == 0.0
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one historical row for {anchor['anchor_id']}; found {len(matches)}")
    return matches[0]


def _candidate_traces(
    cache: TrajectoryCache,
    config: dict[str, Any],
    protocol: str,
    level: str,
    base_params: dict[str, Any],
    waveform: dict[str, Any],
    solver: dict[str, Any],
    gamma_values: Iterable[float] | None = None,
) -> dict[float, dict[str, np.ndarray]]:
    values = list(gamma_values) if gamma_values is not None else [float(value) for value in config["inverse"]["gamma_candidates"]]
    traces: dict[float, dict[str, np.ndarray]] = {}
    for gamma in values:
        trace, _, _ = cache.load_or_simulate(
            role="candidate",
            protocol=protocol,
            coordinate=float(gamma),
            solver_level=level,
            base_params=base_params,
            waveform=waveform,
            solver=solver,
        )
        traces[float(gamma)] = trace
    return traces


def run_parity(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    started = time.perf_counter()
    config = _load_config(config_path)
    prereg = _validate_preregistration(config)
    cache = TrajectoryCache(config)
    source_cases = _load_source_cases(_resolve(config["source_contract"]["cases"]))
    observation_count = int(config["parity"]["observation_count"])
    tolerances = config["parity"]["tolerances"]
    true_gamma = float(config["inverse"]["true_gamma_sub"])
    threshold = float(config["inverse"]["success_relative_error_threshold"])
    rows: list[dict[str, Any]] = []
    protocol_state: dict[str, Any] = {}
    for protocol in config["protocols"]:
        target_source = load_target(_protocol_target_path(config, protocol))
        params = _protocol_params(config, protocol, dict(target_source["params"]))
        waveform = waveform_contract(config, protocol)
        solver = solver_contract(config, protocol, "base", params)
        candidates = _candidate_traces(cache, config, protocol, "base", params, waveform, solver)
        protocol_state[protocol] = {"params": params, "waveform": waveform, "solver": solver, "candidates": candidates}

    for anchor in config["parity"]["anchors"]:
        protocol = str(anchor["protocol"])
        state = protocol_state[protocol]
        target, _, _ = cache.load_or_simulate(
            role="target",
            protocol=protocol,
            coordinate=float(anchor["delta_T_sw_K"]),
            solver_level="base",
            base_params=state["params"],
            waveform=state["waveform"],
            solver=state["solver"],
        )
        score, profile = _score_trace(
            target=target,
            candidates=state["candidates"],
            observation_count=observation_count,
            noise=0.0,
            seed=0,
            weights=config["inverse"]["objective"],
            true_gamma=true_gamma,
            retention_span_fraction=float(config["pilot"]["profile_retention_span_fraction"]),
        )
        historical = _historical_anchor_row(source_cases, anchor, observation_count)
        historic_gamma = float(historical["gamma_est"])
        historic_relative = float(historical["relative_error"])
        historic_objective_value = float(historical["objective"])
        objective_tolerance = float(tolerances["objective_absolute"]) + float(tolerances["objective_relative"]) * abs(historic_objective_value)
        locked_waveform = prereg["locks"]["protocol_contracts"][protocol]["waveform"]["waveform_sha256"]
        locked_solver = prereg["locks"]["protocol_contracts"][protocol]["base_solver"]["solver_config_sha256"]
        gates = {
            "best_gamma_pass": abs(score["gamma_est"] - historic_gamma) <= float(tolerances["best_gamma_absolute"]),
            "relative_error_pass": abs(score["relative_error"] - historic_relative) <= float(tolerances["relative_error_absolute"]),
            "recoverable_classification_pass": (score["relative_error"] <= threshold) == (historic_relative <= threshold),
            "objective_value_pass": abs(score["objective"] - historic_objective_value) <= objective_tolerance,
            "objective_ordering_pass": score["objective_ordering"] == score["historical_objective_ordering"],
            "waveform_hash_pass": state["waveform"]["waveform_sha256"] == locked_waveform,
            "solver_config_hash_pass": state["solver"]["solver_config_sha256"] == locked_solver,
        }
        rows.append(
            {
                "anchor_id": anchor["anchor_id"],
                "protocol": protocol,
                "source_scenario": anchor["source_scenario"],
                "delta_T_sw_K": float(anchor["delta_T_sw_K"]),
                "observation_count": observation_count,
                "historical_gamma_est": historic_gamma,
                "ceba_gamma_est": score["gamma_est"],
                "historical_relative_error": historic_relative,
                "ceba_relative_error": score["relative_error"],
                "historical_objective": historic_objective_value,
                "ceba_objective": score["objective"],
                **gates,
                "all_core_gates_pass": all(gates.values()),
                "profile": profile,
            }
        )
    all_passed = len(rows) <= int(config["budget"]["maximum_parity_anchors"]) and all(row["all_core_gates_pass"] for row in rows)
    elapsed = time.perf_counter() - started
    cases_path = _resolve(config["outputs"]["parity_cases"])
    summary_path = _resolve(config["outputs"]["parity_summary"])
    _atomic_csv(cases_path, rows, PARITY_FIELDS)
    summary = {
        "schema_version": "gamma_sub_ceba_parity_summary_v1",
        "stage_id": config["stage_id"],
        "claim_status": "supported" if all_passed else "forbidden",
        "implementation_status": "parity_passed" if all_passed else "implementation_blocker",
        "all_parity_gates_pass": all_passed,
        "pilot_authorized": all_passed,
        "anchor_count": len(rows),
        "anchor_cap": int(config["budget"]["maximum_parity_anchors"]),
        "gate_pass_counts": {
            field: sum(bool(row[field]) for row in rows)
            for field in (
                "best_gamma_pass",
                "relative_error_pass",
                "recoverable_classification_pass",
                "objective_value_pass",
                "objective_ordering_pass",
                "waveform_hash_pass",
                "solver_config_hash_pass",
            )
        },
        "unique_solver_trajectories": len(cache.seen_keys),
        "new_solver_trajectory_evaluations": cache.misses,
        "cache_hits": cache.hits,
        "max_workers_used": 1,
        "elapsed_seconds": elapsed,
        "preregistration_path": _display(_resolve(config["outputs"]["preregistration"])),
        "preregistration_sha256": _sha256_file(_resolve(config["outputs"]["preregistration"])),
        "cases_path": _display(cases_path),
        "failure_action": "Stop CEBA pilot and return to calibrated gamma_sub manuscript assembly." if not all_passed else None,
        "no_full_pinn_run": True,
        "external_13v_accessed": False,
    }
    _atomic_json(summary_path, summary)
    return summary


def _condition_key(protocol: str, observation_count: int, noise: float) -> tuple[str, int, float]:
    return protocol, int(observation_count), round(float(noise), 12)


def _aggregate(rows: list[dict[str, Any]], success_probability: float, max_abstention: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("Cannot aggregate empty CEBA seed rows")
    probability = float(np.mean([bool(row["success"]) for row in rows]))
    abstention = float(np.mean([bool(row["abstained"]) for row in rows]))
    return {
        "seed_count": len(rows),
        "success_probability": probability,
        "abstention_rate": abstention,
        "passes_locked_gate": probability >= success_probability and abstention <= max_abstention,
    }


def _find_bracket(delta_results: dict[float, dict[str, Any]]) -> tuple[float, float] | None:
    passed = sorted(delta for delta, result in delta_results.items() if result["passes_locked_gate"])
    if not passed:
        return None
    lower = max(passed)
    failures = sorted(delta for delta, result in delta_results.items() if delta > lower and not result["passes_locked_gate"])
    if not failures:
        return None
    return float(lower), float(min(failures))


def _score_row(
    *,
    phase: str,
    protocol: str,
    delta: float,
    observation_count: int,
    noise: float,
    seed: int,
    solver_level: str,
    target_key: str,
    score: dict[str, Any],
) -> dict[str, Any]:
    return {
        "phase": phase,
        "protocol": protocol,
        "delta_T_sw_K": float(delta),
        "observation_count": int(observation_count),
        "noise": float(noise),
        "seed": int(seed),
        "solver_level": solver_level,
        "gamma_est": score["gamma_est"],
        "relative_error": score["relative_error"],
        "objective": score["objective"],
        "retained_candidate_count": score["retained_candidate_count"],
        "abstained": score["abstained"],
        "success": score["success"],
        "target_cache_key": target_key,
    }


def _write_boundary_figure(results: dict[str, Any], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    names = list(results)
    for index, protocol in enumerate(names):
        record = results[protocol]
        bracket = record.get("heldout_success_failure_bracket_K")
        if bracket:
            lower, upper = bracket
            ax.errorbar(
                [index],
                [(lower + upper) / 2.0],
                yerr=[[(upper - lower) / 2.0], [(upper - lower) / 2.0]],
                fmt="o",
                capsize=6,
                color="#1f77b4" if record.get("solver_refinement_consistent") else "#d62728",
            )
        else:
            ax.scatter([index], [0.0], marker="x", color="#d62728", s=70)
    ax.set_xticks(range(len(names)), [name.replace("_", " ") for name in names])
    ax.set_ylabel("Absolute T_sw error boundary (K)")
    ax.set_title("CEBA direct-solver boundary (locked claim condition)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fig.savefig(temporary, format="png", dpi=180)
    plt.close(fig)
    temporary.replace(path)


def run_pilot(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    process_started = time.perf_counter()
    config = _load_config(config_path)
    prereg = _validate_preregistration(config)
    parity_path = _resolve(config["outputs"]["parity_summary"])
    if not parity_path.exists():
        raise RuntimeError("CEBA parity summary is missing")
    parity = json.loads(parity_path.read_text(encoding="utf-8"))
    if not bool(parity.get("all_parity_gates_pass")):
        raise RuntimeError("CEBA parity failed; pilot is forbidden")
    expected_prereg_sha = str(parity["preregistration_sha256"])
    if _sha256_file(_resolve(config["outputs"]["preregistration"])) != expected_prereg_sha:
        raise RuntimeError("CEBA preregistration changed after parity")
    cache = TrajectoryCache(config, elapsed_offset_seconds=float(parity.get("elapsed_seconds", 0.0)))
    true_gamma = float(config["inverse"]["true_gamma_sub"])
    weights = config["inverse"]["objective"]
    retention = float(config["pilot"]["profile_retention_span_fraction"])
    locked_probability = float(config["pilot"]["locked_success_probability"])
    locked_abstention = float(config["pilot"]["locked_maximum_abstention_rate"])
    protocols = list(config["protocols"])
    state: dict[str, Any] = {}
    for protocol in protocols:
        source = load_target(_protocol_target_path(config, protocol))
        params = _protocol_params(config, protocol, dict(source["params"]))
        waveform = waveform_contract(config, protocol)
        solver = solver_contract(config, protocol, "base", params)
        state[protocol] = {
            "params": params,
            "waveform": waveform,
            "solver": solver,
            "candidates": _candidate_traces(cache, config, protocol, "base", params, waveform, solver),
            "targets": {},
            "target_keys": {},
        }

    all_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    profile_cache: dict[tuple[Any, ...], list[dict[str, float]]] = {}

    def ensure_target(protocol: str, delta: float, level: str = "base") -> tuple[dict[str, np.ndarray], str]:
        rounded = round(float(delta), 12)
        key = (level, rounded)
        protocol_state = state[protocol]
        targets = protocol_state.setdefault(f"targets_{level}", {})
        keys = protocol_state.setdefault(f"target_keys_{level}", {})
        if key not in targets:
            solver = protocol_state["solver"] if level == "base" else solver_contract(config, protocol, "refinement", protocol_state["params"])
            trace, cache_key, _ = cache.load_or_simulate(
                role="target",
                protocol=protocol,
                coordinate=rounded,
                solver_level=level,
                base_params=protocol_state["params"],
                waveform=protocol_state["waveform"],
                solver=solver,
            )
            targets[key] = trace
            keys[key] = cache_key
        return targets[key], keys[key]

    def ensure_scores(protocol: str, delta: float, observation_count: int, noise: float, phase: str, seeds: list[int]) -> list[dict[str, Any]]:
        target, target_key = ensure_target(protocol, delta, "base")
        selected: list[dict[str, Any]] = []
        for seed in seeds:
            row_key = (phase, protocol, round(delta, 12), observation_count, round(noise, 12), seed, "base")
            if row_key not in all_rows:
                score, profile = _score_trace(
                    target=target,
                    candidates=state[protocol]["candidates"],
                    observation_count=observation_count,
                    noise=noise,
                    seed=seed,
                    weights=weights,
                    true_gamma=true_gamma,
                    retention_span_fraction=retention,
                )
                all_rows[row_key] = _score_row(
                    phase=phase,
                    protocol=protocol,
                    delta=delta,
                    observation_count=observation_count,
                    noise=noise,
                    seed=seed,
                    solver_level="base",
                    target_key=target_key,
                    score=score,
                )
                profile_cache[row_key] = profile
            selected.append(all_rows[row_key])
        return selected

    initial_deltas = sorted({float(anchor["delta_T_sw_K"]) for anchor in config["parity"]["anchors"]})
    observation_counts = [int(value) for value in config["pilot"]["observation_counts"]]
    noise_levels = [float(value) for value in config["pilot"]["noise_levels"]]
    discovery_seeds = [int(value) for value in config["pilot"]["discovery_seeds"]]
    heldout_seeds = [int(value) for value in config["pilot"]["heldout_seeds"]]
    queried_deltas = set(initial_deltas)

    def discovery_results() -> dict[tuple[str, int, float], dict[float, dict[str, Any]]]:
        results: dict[tuple[str, int, float], dict[float, dict[str, Any]]] = {}
        for protocol in protocols:
            for observation_count in observation_counts:
                for noise in noise_levels:
                    seeds = discovery_seeds if noise > 0.0 else [discovery_seeds[0]]
                    condition = _condition_key(protocol, observation_count, noise)
                    results[condition] = {}
                    for delta in sorted(queried_deltas):
                        rows = ensure_scores(protocol, delta, observation_count, noise, "discovery", seeds)
                        results[condition][delta] = _aggregate(rows, locked_probability, locked_abstention)
        return results

    discovery = discovery_results()
    maximum_rounds = int(config["pilot"]["maximum_bisection_rounds"])
    tolerance_K = float(config["pilot"]["boundary_tolerance_K"])
    maximum_target_trajectories = int(config["pilot"]["maximum_additional_base_target_trajectories"])
    added_target_trajectories = 0
    search_rounds: list[dict[str, Any]] = []
    for round_index in range(maximum_rounds):
        candidates: list[tuple[float, float, float, tuple[str, int, float]]] = []
        for condition, results in discovery.items():
            bracket = _find_bracket(results)
            if bracket and bracket[1] - bracket[0] > tolerance_K:
                midpoint = round((bracket[0] + bracket[1]) / 2.0, 12)
                if midpoint not in queried_deltas:
                    candidates.append((bracket[1] - bracket[0], midpoint, bracket[0], condition))
        if not candidates or added_target_trajectories + len(protocols) > maximum_target_trajectories:
            break
        candidates.sort(key=lambda item: (-item[0], item[1], item[3]))
        _, midpoint, _, selected_condition = candidates[0]
        queried_deltas.add(midpoint)
        for protocol in protocols:
            ensure_target(protocol, midpoint, "base")
        added_target_trajectories += len(protocols)
        search_rounds.append({"round": round_index + 1, "selected_delta_T_sw_K": midpoint, "trigger_condition": list(selected_condition)})
        discovery = discovery_results()

    condition_results: dict[str, Any] = {}
    brackets: dict[tuple[str, int, float], tuple[float, float] | None] = {}
    for condition, results in discovery.items():
        bracket = _find_bracket(results)
        brackets[condition] = bracket
        protocol, observation_count, noise = condition
        key = f"{protocol}|n={observation_count}|noise={noise:.6g}"
        record: dict[str, Any] = {"discovery_delta_results": {str(delta): value for delta, value in sorted(results.items())}, "discovery_bracket_K": bracket}
        if bracket:
            seeds = heldout_seeds if noise > 0.0 else [heldout_seeds[0]]
            lower_rows = ensure_scores(protocol, bracket[0], observation_count, noise, "heldout", seeds)
            upper_rows = ensure_scores(protocol, bracket[1], observation_count, noise, "heldout", seeds)
            lower = _aggregate(lower_rows, locked_probability, locked_abstention)
            upper = _aggregate(upper_rows, locked_probability, locked_abstention)
            record.update(
                {
                    "heldout_lower": lower,
                    "heldout_upper": upper,
                    "heldout_success_failure_bracket_K": bracket if lower["passes_locked_gate"] and not upper["passes_locked_gate"] else None,
                    "heldout_gate_pass": bool(lower["passes_locked_gate"] and not upper["passes_locked_gate"]),
                }
            )
        else:
            record.update({"heldout_success_failure_bracket_K": None, "heldout_gate_pass": False})
        condition_results[key] = record

    claim_condition = config["pilot"]["claim_condition"]
    claim_n = int(claim_condition["observation_count"])
    claim_noise = float(claim_condition["noise"])
    protocol_results: dict[str, Any] = {}
    refinement_trajectory_count = 0
    for protocol in protocols:
        condition = _condition_key(protocol, claim_n, claim_noise)
        condition_key = f"{protocol}|n={claim_n}|noise={claim_noise:.6g}"
        base_record = condition_results[condition_key]
        bracket = base_record.get("heldout_success_failure_bracket_K")
        protocol_record: dict[str, Any] = {
            "claim_observation_count": claim_n,
            "claim_noise": claim_noise,
            "delta_T_sw_star_K": bracket[0] if bracket else None,
            "heldout_success_failure_bracket_K": bracket,
            "heldout_gate_pass": bool(base_record.get("heldout_gate_pass")),
            "solver_refinement_consistent": False,
        }
        if bracket:
            profile_means: dict[float, list[float]] = {float(gamma): [] for gamma in config["inverse"]["gamma_candidates"]}
            for delta in bracket:
                rows = ensure_scores(protocol, delta, claim_n, claim_noise, "discovery", discovery_seeds)
                for row in rows:
                    row_key = ("discovery", protocol, round(delta, 12), claim_n, round(claim_noise, 12), int(row["seed"]), "base")
                    for item in profile_cache[row_key]:
                        profile_means[float(item["gamma_sub"])].append(float(item["objective"]))
            top_count = int(config["pilot"]["refinement"]["candidate_count_per_protocol"])
            top_gamma = [
                gamma
                for gamma, _ in sorted(
                    ((gamma, float(np.mean(values))) for gamma, values in profile_means.items()),
                    key=lambda item: (item[1], item[0]),
                )[:top_count]
            ]
            refined_solver = solver_contract(config, protocol, "refinement", state[protocol]["params"])
            refined_candidates = _candidate_traces(
                cache,
                config,
                protocol,
                "refinement",
                state[protocol]["params"],
                state[protocol]["waveform"],
                refined_solver,
                top_gamma,
            )
            refinement_trajectory_count += len(top_gamma)
            refined_endpoint: dict[str, Any] = {}
            for label, delta in (("lower", bracket[0]), ("upper", bracket[1])):
                target, target_key = ensure_target(protocol, delta, "refinement")
                refinement_trajectory_count += 1
                endpoint_rows: list[dict[str, Any]] = []
                for seed in heldout_seeds:
                    score, _ = _score_trace(
                        target=target,
                        candidates=refined_candidates,
                        observation_count=claim_n,
                        noise=claim_noise,
                        seed=seed,
                        weights=weights,
                        true_gamma=true_gamma,
                        retention_span_fraction=retention,
                    )
                    row = _score_row(
                        phase="refinement",
                        protocol=protocol,
                        delta=delta,
                        observation_count=claim_n,
                        noise=claim_noise,
                        seed=seed,
                        solver_level="refinement",
                        target_key=target_key,
                        score=score,
                    )
                    all_rows[("refinement", protocol, round(delta, 12), claim_n, round(claim_noise, 12), seed, "refinement")] = row
                    endpoint_rows.append(row)
                refined_endpoint[label] = _aggregate(endpoint_rows, locked_probability, locked_abstention)
            consistent = refined_endpoint["lower"]["passes_locked_gate"] and not refined_endpoint["upper"]["passes_locked_gate"]
            protocol_record.update(
                {
                    "refinement_top3_gamma_sub": top_gamma,
                    "refinement_lower": refined_endpoint["lower"],
                    "refinement_upper": refined_endpoint["upper"],
                    "solver_refinement_consistent": bool(consistent),
                }
            )
        protocol_results[protocol] = protocol_record

    maximum_refinement = int(config["pilot"]["refinement"]["maximum_additional_trajectories"])
    refinement_budget_pass = refinement_trajectory_count <= maximum_refinement
    all_protocol_gates = all(
        record["heldout_gate_pass"] and record["solver_refinement_consistent"] for record in protocol_results.values()
    )
    no_semantic_mixing = all(
        state[protocol]["waveform"]["waveform_sha256"]
        == prereg["locks"]["protocol_contracts"][protocol]["waveform"]["waveform_sha256"]
        for protocol in protocols
    )
    total_elapsed = cache.elapsed_seconds()
    budget_gates = {
        "unique_solver_trajectories_le_60": len(cache.seen_keys) <= int(config["budget"]["maximum_unique_solver_trajectories"]),
        "max_workers_le_2": 1 <= int(config["budget"]["maximum_workers"]),
        "wall_time_le_30_min": total_elapsed <= 60.0 * float(config["budget"]["maximum_wall_time_minutes"]),
        "refinement_trajectories_le_10": refinement_budget_pass,
    }
    claim_eligible = bool(parity["all_parity_gates_pass"] and all_protocol_gates and no_semantic_mixing and all(budget_gates.values()))
    rows = sorted(all_rows.values(), key=lambda row: (row["phase"], row["protocol"], row["delta_T_sw_K"], row["observation_count"], row["noise"], row["seed"], row["solver_level"]))
    cases_path = _resolve(config["outputs"]["pilot_cases"])
    summary_path = _resolve(config["outputs"]["pilot_summary"])
    figure_path = _resolve(config["outputs"]["pilot_figure"])
    _atomic_csv(cases_path, rows, PILOT_FIELDS)
    _write_boundary_figure(protocol_results, figure_path)
    summary = {
        "schema_version": "gamma_sub_ceba_pilot_summary_v1",
        "stage_id": config["stage_id"],
        "claim_status": "qualified_supported" if claim_eligible else "failed_but_informative",
        "ceba_configuration_claim_eligible": claim_eligible,
        "parity_all_passed": bool(parity["all_parity_gates_pass"]),
        "definition_commit": prereg["definition_commit"],
        "protocol_results": protocol_results,
        "condition_results": condition_results,
        "queried_delta_T_sw_K": sorted(queried_deltas),
        "adaptive_search_rounds": search_rounds,
        "additional_base_target_trajectories": added_target_trajectories,
        "refinement_trajectory_count": refinement_trajectory_count,
        "scoring_case_count": len(rows),
        "unique_solver_trajectories": len(cache.seen_keys),
        "new_solver_trajectory_evaluations_this_process": cache.misses,
        "cache_hits_this_process": cache.hits,
        "max_workers_used": 1,
        "elapsed_seconds_total_parity_and_pilot": total_elapsed,
        "elapsed_seconds_pilot_process": time.perf_counter() - process_started,
        "budget_gates": budget_gates,
        "no_protocol_unit_or_source_mixing": no_semantic_mixing,
        "bootstrap_semantics": config["pilot"]["bootstrap_semantics"],
        "allowed_claim": config["allowed_claim_if_all_gates_pass"] if claim_eligible else "The bounded direct-solver pilot did not satisfy every preregistered CEBA claim gate; it is retained as a failure/abstention boundary only.",
        "forbidden_claims": config["forbidden_claims"],
        "outputs": {"cases": _display(cases_path), "summary": _display(summary_path), "figure": _display(figure_path)},
        "full_pinn_run": False,
        "external_13v_accessed": False,
    }
    _atomic_json(summary_path, summary)
    cache._save_resume("complete")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=["preregister", "parity", "pilot"], required=True)
    args = parser.parse_args()
    if args.mode == "preregister":
        result = preregister(args.config)
    elif args.mode == "parity":
        result = run_parity(args.config)
    else:
        result = run_pilot(args.config)
    keys = [key for key in ("schema_version", "claim_status", "all_parity_gates_pass", "pilot_authorized", "ceba_configuration_claim_eligible", "unique_solver_trajectories", "elapsed_seconds", "elapsed_seconds_total_parity_and_pilot") if key in result]
    print(json.dumps({key: result[key] for key in keys}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

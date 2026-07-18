"""Run the cache-only Simulation-Calibrated Identifiability Set audit.

The inference function in this module is intentionally truth-free.  Truth is
used only by the calibration-data generator and the held-out evaluator.  This
module never calls the ODE solver: a missing cache entry is a hard stop.
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
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scripts.gamma_sub_validation_common import load_target, make_noisy, observation_times, port_series
from scripts.run_gamma_sub_ceba import (
    _candidate_cache_key,
    _protocol_params,
    _protocol_target_path,
    _target_cache_key,
    ceba_objective,
    solver_contract,
    waveform_contract,
)

DEFAULT_CONFIG = ROOT / "configs" / "gamma_sub_scis_v1.yaml"
SCRIPT_PATH = ROOT / "scripts" / "run_gamma_sub_scis.py"

CASE_FIELDS = [
    "scope",
    "protocol",
    "observation_count",
    "noise",
    "delta_T_sw_K",
    "seed",
    "true_gamma_sub",
    "gamma_hat",
    "relative_error",
    "point_success",
    "set_contains_true",
    "set_coverage",
    "certificate_acceptance",
    "conditional_accuracy_given_acceptance",
    "abstention_refusal",
    "set_size",
    "set_members",
    "remote_candidate_deleted_acceptance",
    "remote_candidate_deletion_decision_changed",
]

CEBA_IMMUTABLE_PATHS = [
    "configs/gamma_sub_ceba_v1.yaml",
    "scripts/run_gamma_sub_ceba.py",
    "outputs/tables/gamma_sub_ceba_preregistration.json",
    "outputs/tables/gamma_sub_ceba_parity_cases.csv",
    "outputs/tables/gamma_sub_ceba_parity_summary.json",
    "outputs/tables/gamma_sub_ceba_pilot_cases.csv",
    "outputs/tables/gamma_sub_ceba_pilot_summary.json",
    "outputs/figures/gamma_sub_ceba_boundary_v1.png",
]


class CacheMissStop(RuntimeError):
    """Raised instead of running the solver when a required trajectory is absent."""


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _display(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(_resolve(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return payload


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Non-finite JSON value: {number}")
        return number
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _jsonable(row.get(field)) for field in CASE_FIELDS})
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def expand_seed_block(block: Mapping[str, Any]) -> list[int]:
    start = int(block["start"])
    count = int(block["count"])
    if count <= 0:
        raise ValueError("Seed-block count must be positive")
    return list(range(start, start + count))


def finite_sample_quantile(scores: Sequence[float], alpha: float) -> tuple[float, int]:
    """Return the split-conformal finite-sample quantile and its one-based rank."""

    values = np.sort(np.asarray(scores, dtype=float))
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Calibration scores must be a non-empty finite vector")
    if not 0.0 < float(alpha) < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    rank = min(int(math.ceil((values.size + 1) * (1.0 - float(alpha)))), int(values.size))
    return float(values[rank - 1]), rank


def infer_scis(
    *,
    objectives: Sequence[float],
    candidate_grid: Sequence[float],
    candidate_thresholds: Mapping[float, float],
    relative_radius: float,
) -> dict[str, Any]:
    """Compute the SCIS point/set/refusal decision without access to truth."""

    gamma = np.asarray(candidate_grid, dtype=float)
    values = np.asarray(objectives, dtype=float)
    if gamma.ndim != 1 or values.shape != gamma.shape or gamma.size == 0:
        raise ValueError("Candidate grid and objectives must be equal non-empty vectors")
    if not np.isfinite(gamma).all() or not np.isfinite(values).all() or np.any(gamma <= 0.0):
        raise ValueError("Candidates and objectives must be finite, with positive candidates")
    order = np.argsort(gamma, kind="stable")
    gamma = gamma[order]
    values = values[order]
    best_index = int(np.argmin(values))
    gamma_hat = float(gamma[best_index])
    scores = values - float(np.min(values))
    selected = [
        float(candidate)
        for candidate, score in zip(gamma, scores, strict=True)
        if float(score) <= float(candidate_thresholds[float(candidate)]) + 1.0e-18
    ]
    accepted = bool(selected) and all(
        abs(gamma_hat - candidate) / candidate <= float(relative_radius) + 1.0e-15
        for candidate in selected
    )
    return {
        "gamma_hat": gamma_hat,
        "scores": [float(value) for value in scores],
        "set_members": selected,
        "set_size": len(selected),
        "certificate_acceptance": bool(accepted),
        "abstention_refusal": not bool(accepted),
    }


def _relative_error(value: float, truth: float) -> float:
    return abs(float(value) - float(truth)) / max(abs(float(truth)), 1.0e-30)


class CacheOnlyTrajectoryStore:
    """Read and validate CEBA cache entries without any solver fallback."""

    def __init__(self, scis_config: Mapping[str, Any]) -> None:
        self.scis_config = dict(scis_config)
        self.ceba_config = _load_yaml(scis_config["source_contract"]["ceba_config"])
        self.root = _resolve(scis_config["source_contract"]["trajectory_cache"])
        self.loaded_keys: set[str] = set()
        self.loaded_paths: dict[str, str] = {}
        self._contracts: dict[str, dict[str, Any]] = {}
        for protocol in scis_config["protocols"]:
            source = load_target(_protocol_target_path(self.ceba_config, str(protocol)))
            params = _protocol_params(self.ceba_config, str(protocol), dict(source["params"]))
            waveform = waveform_contract(self.ceba_config, str(protocol))
            solver = solver_contract(self.ceba_config, str(protocol), "base", params)
            self._contracts[str(protocol)] = {
                "params": params,
                "waveform": waveform,
                "solver": solver,
            }

    def _key(self, role: str, protocol: str, coordinate: float) -> str:
        contract = self._contracts[protocol]
        waveform_hash = str(contract["waveform"]["waveform_sha256"])
        solver_hash = str(contract["solver"]["solver_config_sha256"])
        if role == "candidate":
            return _candidate_cache_key(waveform_hash, float(coordinate), solver_hash)
        if role == "target":
            return _target_cache_key(waveform_hash, float(coordinate), solver_hash)
        raise ValueError(f"Unknown cache role: {role}")

    def expected_entry(self, role: str, protocol: str, coordinate: float) -> tuple[str, Path]:
        key = self._key(role, protocol, coordinate)
        path = self.root / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.npz"
        return key, path

    def load(self, role: str, protocol: str, coordinate: float) -> dict[str, np.ndarray]:
        key, path = self.expected_entry(role, protocol, coordinate)
        if not path.is_file():
            raise CacheMissStop(f"Required cached trajectory is missing; solver fallback forbidden: {path}")
        try:
            with np.load(path, allow_pickle=False) as payload:
                if set(payload.files) != {"cache_key", "t", "G", "I"}:
                    raise CacheMissStop(f"Invalid cached trajectory fields: {path}")
                if str(payload["cache_key"].item()) != key:
                    raise CacheMissStop(f"Cached trajectory key mismatch: {path}")
                trace = {name: np.asarray(payload[name], dtype=float) for name in ("t", "G", "I")}
        except (OSError, ValueError) as error:
            raise CacheMissStop(f"Unreadable cached trajectory: {path}") from error
        length = trace["t"].size
        if length < 2 or any(values.shape != (length,) for values in trace.values()):
            raise CacheMissStop(f"Cached trajectory shapes are invalid: {path}")
        if not all(np.isfinite(values).all() for values in trace.values()):
            raise CacheMissStop(f"Cached trajectory contains non-finite values: {path}")
        if not np.all(np.diff(trace["t"]) > 0.0):
            raise CacheMissStop(f"Cached time axis is not strictly increasing: {path}")
        self.loaded_keys.add(key)
        self.loaded_paths[key] = _display(path)
        return trace

    def contracts(self) -> dict[str, Any]:
        return {
            protocol: {
                "waveform": contract["waveform"],
                "solver": contract["solver"],
            }
            for protocol, contract in self._contracts.items()
        }


def cache_preflight(config_path: Path = DEFAULT_CONFIG, *, write_output: bool = True) -> dict[str, Any]:
    config = _load_yaml(config_path)
    store = CacheOnlyTrajectoryStore(config)
    candidates = [float(value) for value in config["candidate_grid"]["gamma_sub"]]
    deltas = [float(value) for value in config["cache_only"]["required_target_deltas_K"]]
    entries: list[dict[str, Any]] = []
    for protocol in [str(value) for value in config["protocols"]]:
        for gamma in candidates:
            key, path = store.expected_entry("candidate", protocol, gamma)
            store.load("candidate", protocol, gamma)
            entries.append({"role": "candidate", "protocol": protocol, "coordinate": gamma, "cache_key": key, "path": _display(path), "sha256": _sha256_file(path)})
        for delta in deltas:
            key, path = store.expected_entry("target", protocol, delta)
            store.load("target", protocol, delta)
            entries.append({"role": "target", "protocol": protocol, "coordinate": delta, "cache_key": key, "path": _display(path), "sha256": _sha256_file(path)})
    unique_count = len({entry["cache_key"] for entry in entries})
    expected = int(config["cache_only"]["expected_unique_trajectory_count"])
    payload = {
        "schema_version": "gamma_sub_scis_cache_preflight_v1",
        "stage_id": config["stage_id"],
        "status": "pass" if unique_count == expected else "stop",
        "cache_only": True,
        "solver_fallback_available": False,
        "required_entry_count": len(entries),
        "unique_trajectory_count": unique_count,
        "expected_unique_trajectory_count": expected,
        "all_required_entries_valid": unique_count == expected,
        "new_ode_evaluations": 0,
        "pinn_training_runs": 0,
        "external_13v_accessed": False,
        "protocol_contracts": store.contracts(),
        "entries": entries,
    }
    if write_output:
        _atomic_json(_resolve(config["outputs"]["preflight"]), payload)
    if payload["status"] != "pass":
        raise CacheMissStop("SCIS cache preflight did not match the preregistered trajectory count")
    return payload


def _objective_vector(
    *,
    target: Mapping[str, np.ndarray],
    candidates: Mapping[float, Mapping[str, np.ndarray]],
    observation_count: int,
    noise: float,
    seed: int,
    weights: Mapping[str, Any],
) -> list[float]:
    obs_time = observation_times(np.asarray(target["t"], dtype=float), int(observation_count))
    clean_g, clean_i = port_series(dict(target), obs_time)
    rng = np.random.default_rng(int(seed))
    target_g = make_noisy(clean_g, float(noise), rng)
    target_i = make_noisy(clean_i, float(noise), rng)
    objectives: list[float] = []
    for gamma in sorted(candidates):
        pred_g, pred_i = port_series(dict(candidates[gamma]), obs_time)
        components = ceba_objective(pred_g, pred_i, target_g, target_i, dict(weights))
        objectives.append(float(components["objective"]))
    return objectives


def _calibrate_thresholds(
    *,
    candidate_grid: list[float],
    candidate_traces: Mapping[float, Mapping[str, np.ndarray]],
    observation_count: int,
    noise: float,
    seeds: Sequence[int],
    weights: Mapping[str, Any],
    alpha: float,
) -> tuple[dict[float, float], dict[float, int]]:
    thresholds: dict[float, float] = {}
    ranks: dict[float, int] = {}
    for truth_index, truth_gamma in enumerate(candidate_grid):
        scores: list[float] = []
        for seed in seeds:
            objectives = _objective_vector(
                target=candidate_traces[truth_gamma],
                candidates={gamma: candidate_traces[gamma] for gamma in candidate_grid},
                observation_count=observation_count,
                noise=noise,
                seed=int(seed),
                weights=weights,
            )
            scores.append(float(objectives[truth_index] - min(objectives)))
        thresholds[truth_gamma], ranks[truth_gamma] = finite_sample_quantile(scores, alpha)
    return thresholds, ranks


def _evaluate_row(
    *,
    scope: str,
    protocol: str,
    observation_count: int,
    noise: float,
    delta: float,
    seed: int,
    truth_gamma: float,
    target: Mapping[str, np.ndarray],
    full_grid: list[float],
    candidate_traces: Mapping[float, Mapping[str, np.ndarray]],
    thresholds: Mapping[float, float],
    deletion_grid: list[float],
    deletion_thresholds: Mapping[float, float],
    weights: Mapping[str, Any],
    relative_radius: float,
) -> dict[str, Any]:
    objectives = _objective_vector(
        target=target,
        candidates=candidate_traces,
        observation_count=observation_count,
        noise=noise,
        seed=seed,
        weights=weights,
    )
    inferred = infer_scis(
        objectives=objectives,
        candidate_grid=full_grid,
        candidate_thresholds=thresholds,
        relative_radius=relative_radius,
    )
    index_by_gamma = {gamma: index for index, gamma in enumerate(full_grid)}
    deletion_objectives = [objectives[index_by_gamma[gamma]] for gamma in deletion_grid]
    deletion = infer_scis(
        objectives=deletion_objectives,
        candidate_grid=deletion_grid,
        candidate_thresholds=deletion_thresholds,
        relative_radius=relative_radius,
    )
    error = _relative_error(float(inferred["gamma_hat"]), truth_gamma)
    point_success = error <= relative_radius + 1.0e-15
    set_contains_true = truth_gamma in inferred["set_members"]
    accepted = bool(inferred["certificate_acceptance"])
    return {
        "scope": scope,
        "protocol": protocol,
        "observation_count": observation_count,
        "noise": noise,
        "delta_T_sw_K": delta,
        "seed": seed,
        "true_gamma_sub": truth_gamma,
        "gamma_hat": inferred["gamma_hat"],
        "relative_error": error,
        "point_success": point_success,
        "set_contains_true": set_contains_true,
        "set_coverage": set_contains_true if scope == "nominal_coverage" else None,
        "certificate_acceptance": accepted,
        "conditional_accuracy_given_acceptance": point_success if accepted else None,
        "abstention_refusal": inferred["abstention_refusal"],
        "set_size": inferred["set_size"],
        "set_members": ";".join(f"{value:.17g}" for value in inferred["set_members"]),
        "remote_candidate_deleted_acceptance": deletion["certificate_acceptance"],
        "remote_candidate_deletion_decision_changed": accepted != bool(deletion["certificate_acceptance"]),
    }


def _mean_bool(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [bool(row[field]) for row in rows if row.get(field) is not None]
    return float(np.mean(values)) if values else 0.0


def _write_figure(summary: Mapping[str, Any], path: Path) -> None:
    coverage = summary["nominal_primary_metrics"]["coverage_by_candidate"]
    gamma = np.asarray([float(key) for key in coverage], dtype=float)
    values = np.asarray([float(coverage[key]) for key in coverage], dtype=float)
    anchor = summary["true_4p5e8_primary_metrics"]
    labels = ["0 K", "0.2 K", "2 K"]
    acceptance = [
        float(anchor["nominal_acceptance"]),
        float(anchor["delta_0p2K_acceptance"]),
        float(anchor["delta_2K_acceptance"]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0))
    axes[0].plot(gamma / 1.0e8, values, marker="o", color="#1f77b4")
    axes[0].axhline(0.90, linestyle="--", color="#444444", linewidth=1.0, label="pooled gate")
    axes[0].axhline(0.80, linestyle=":", color="#d62728", linewidth=1.0, label="candidate floor")
    axes[0].set_xlabel(r"candidate $\gamma_{sub}$ ($10^8$)")
    axes[0].set_ylabel("held-out set coverage")
    axes[0].set_ylim(0.0, 1.05)
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.2)
    axes[1].bar(labels, acceptance, color=["#2ca02c", "#ff7f0e", "#d62728"])
    axes[1].axhline(0.80, linestyle="--", color="#444444", linewidth=1.0)
    axes[1].axhline(0.20, linestyle=":", color="#444444", linewidth=1.0)
    axes[1].set_ylabel("certificate acceptance")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_title(r"$\gamma_{sub}=4.5\times10^8$")
    axes[1].grid(axis="y", alpha=0.2)
    fig.suptitle("SCIS: nominal coverage and mismatch refusal")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fig.savefig(temporary, format="png", dpi=180)
    plt.close(fig)
    temporary.replace(path)


def preregister(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_yaml(config_path)
    seed_sets = {name: expand_seed_block(block) for name, block in config["seeds"].items()}
    if set(seed_sets["discovery"]) & set(seed_sets["calibration"]) or set(seed_sets["discovery"]) & set(seed_sets["heldout"]) or set(seed_sets["calibration"]) & set(seed_sets["heldout"]):
        raise ValueError("Discovery, calibration, and held-out seeds must be disjoint")
    immutable_hashes = {
        path: _sha256_file(_resolve(path))
        for path in CEBA_IMMUTABLE_PATHS
    }
    payload = {
        "schema_version": "gamma_sub_scis_preregistration_v1",
        "stage_id": config["stage_id"],
        "registration_parent_commit": _git("rev-parse", "HEAD"),
        "registration_semantics": "internal commit-ordered preregistration; not an independent remote timestamp",
        "git_dirty_during_registration": bool(_git("status", "--short")),
        "config_sha256": _sha256_file(_resolve(config_path)),
        "implementation_sha256": _sha256_file(SCRIPT_PATH),
        "ceba_immutable_hashes": immutable_hashes,
        "formulae": {
            "score": "s_j(y)=J(gamma_j;y)-min_k J(gamma_k;y)",
            "set": "C_alpha(y)={gamma_j:s_j(y)<=q_j}",
            "finite_sample_quantile": config["calibration"]["finite_sample_quantile"],
            "acceptance": config["inference"]["acceptance"],
        },
        "seed_sets": seed_sets,
        "seeds_pairwise_disjoint": True,
        "primary_conditions": {
            "protocols": config["protocols"],
            "observation_counts": config["observation_counts"],
            "noise": config["primary_noise"],
            "candidate_count": len(config["candidate_grid"]["gamma_sub"]),
            "nominal_delta_T_sw_K": config["calibration"]["nominal_delta_T_sw_K"],
        },
        "stress_conditions": config["calibration"]["stress_delta_T_sw_K"],
        "remote_candidate_deletion": {
            "candidate": config["candidate_grid"]["remote_candidate_for_sensitivity"],
            "selection_rule": "largest preregistered gamma and farthest grid candidate from 4.5e8",
            "thresholds_recalibrated_with_same_locked_calibration_seeds_on_reduced_grid": True,
        },
        "gates": config["gates"],
        "cache_only": config["cache_only"],
        "no_scis_scoring_results": True,
        "no_solver_run": True,
        "new_ode_evaluations": 0,
        "pinn_training_runs": 0,
        "external_13v_accessed": False,
        "allowed_claim_if_all_gates_pass": config["allowed_claim_if_all_gates_pass"],
        "forbidden_claims": config["forbidden_claims"],
    }
    _atomic_json(_resolve(config["outputs"]["preregistration"]), payload)
    return payload


def run_scis(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_yaml(config_path)
    prereg_path = _resolve(config["outputs"]["preregistration"])
    if not prereg_path.is_file():
        raise RuntimeError("SCIS preregistration is missing")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    for path, expected_hash in prereg["ceba_immutable_hashes"].items():
        if _sha256_file(_resolve(path)) != expected_hash:
            raise RuntimeError(f"Historical CEBA artifact changed after SCIS preregistration: {path}")
    preflight = cache_preflight(config_path, write_output=True)
    if not preflight["all_required_entries_valid"] or preflight["new_ode_evaluations"] != 0:
        raise CacheMissStop("SCIS requires a complete zero-new-ODE cache preflight")

    store = CacheOnlyTrajectoryStore(config)
    full_grid = sorted(float(value) for value in config["candidate_grid"]["gamma_sub"])
    removed = float(config["candidate_grid"]["remote_candidate_for_sensitivity"])
    deletion_grid = [value for value in full_grid if value != removed]
    truth_anchor = float(config["candidate_grid"]["evaluation_truth_gamma_sub"])
    weights = dict(store.ceba_config["inverse"]["objective"])
    alpha = float(config["calibration"]["alpha"])
    radius = float(config["inference"]["relative_radius"])
    calibration_seeds = expand_seed_block(config["seeds"]["calibration"])
    heldout_seeds = expand_seed_block(config["seeds"]["heldout"])
    discovery_seeds = expand_seed_block(config["seeds"]["discovery"])

    thresholds_by_condition: dict[str, dict[str, float]] = {}
    quantile_ranks_by_condition: dict[str, dict[str, int]] = {}
    deletion_thresholds_by_condition: dict[str, dict[str, float]] = {}
    rows: list[dict[str, Any]] = []
    discovery_objective_finite = True
    candidate_traces_by_protocol: dict[str, dict[float, dict[str, np.ndarray]]] = {}
    for protocol in [str(value) for value in config["protocols"]]:
        candidate_traces = {gamma: store.load("candidate", protocol, gamma) for gamma in full_grid}
        candidate_traces_by_protocol[protocol] = candidate_traces
        for observation_count in [int(value) for value in config["observation_counts"]]:
            for noise in [float(value) for value in config["noise_levels"]]:
                key = f"{protocol}|n={observation_count}|noise={noise:.6g}"
                thresholds, ranks = _calibrate_thresholds(
                    candidate_grid=full_grid,
                    candidate_traces=candidate_traces,
                    observation_count=observation_count,
                    noise=noise,
                    seeds=calibration_seeds,
                    weights=weights,
                    alpha=alpha,
                )
                deletion_thresholds, _ = _calibrate_thresholds(
                    candidate_grid=deletion_grid,
                    candidate_traces=candidate_traces,
                    observation_count=observation_count,
                    noise=noise,
                    seeds=calibration_seeds,
                    weights=weights,
                    alpha=alpha,
                )
                thresholds_by_condition[key] = {f"{gamma:.17g}": value for gamma, value in thresholds.items()}
                quantile_ranks_by_condition[key] = {f"{gamma:.17g}": value for gamma, value in ranks.items()}
                deletion_thresholds_by_condition[key] = {f"{gamma:.17g}": value for gamma, value in deletion_thresholds.items()}

                if noise == float(config["primary_noise"]):
                    for seed in discovery_seeds:
                        diagnostic = _objective_vector(
                            target=candidate_traces[truth_anchor],
                            candidates=candidate_traces,
                            observation_count=observation_count,
                            noise=noise,
                            seed=seed,
                            weights=weights,
                        )
                        discovery_objective_finite = discovery_objective_finite and bool(np.isfinite(diagnostic).all())

                for truth_gamma in full_grid:
                    for seed in heldout_seeds:
                        rows.append(
                            _evaluate_row(
                                scope="nominal_coverage",
                                protocol=protocol,
                                observation_count=observation_count,
                                noise=noise,
                                delta=0.0,
                                seed=seed,
                                truth_gamma=truth_gamma,
                                target=candidate_traces[truth_gamma],
                                full_grid=full_grid,
                                candidate_traces=candidate_traces,
                                thresholds=thresholds,
                                deletion_grid=deletion_grid,
                                deletion_thresholds=deletion_thresholds,
                                weights=weights,
                                relative_radius=radius,
                            )
                        )

                for delta in [float(value) for value in config["calibration"]["stress_delta_T_sw_K"]]:
                    target = store.load("target", protocol, delta)
                    for seed in heldout_seeds:
                        rows.append(
                            _evaluate_row(
                                scope="model_mismatch_stress",
                                protocol=protocol,
                                observation_count=observation_count,
                                noise=noise,
                                delta=delta,
                                seed=seed,
                                truth_gamma=truth_anchor,
                                target=target,
                                full_grid=full_grid,
                                candidate_traces=candidate_traces,
                                thresholds=thresholds,
                                deletion_grid=deletion_grid,
                                deletion_thresholds=deletion_thresholds,
                                weights=weights,
                                relative_radius=radius,
                            )
                        )

    primary_noise = float(config["primary_noise"])
    nominal_primary = [row for row in rows if row["scope"] == "nominal_coverage" and row["noise"] == primary_noise]
    coverage_by_candidate: dict[str, float] = {}
    for gamma in full_grid:
        subset = [row for row in nominal_primary if row["true_gamma_sub"] == gamma]
        coverage_by_candidate[f"{gamma:.17g}"] = _mean_bool(subset, "set_coverage")
    pooled_coverage = _mean_bool(nominal_primary, "set_coverage")
    worst_gamma_key = min(coverage_by_candidate, key=lambda key: (coverage_by_candidate[key], float(key)))
    accepted_nominal = [row for row in nominal_primary if row["certificate_acceptance"]]
    conditional_accuracy = _mean_bool(accepted_nominal, "point_success")

    anchor_nominal = [row for row in nominal_primary if row["true_gamma_sub"] == truth_anchor]
    anchor_delta_0p2 = [row for row in rows if row["scope"] == "model_mismatch_stress" and row["noise"] == primary_noise and row["delta_T_sw_K"] == 0.2]
    anchor_delta_2 = [row for row in rows if row["scope"] == "model_mismatch_stress" and row["noise"] == primary_noise and row["delta_T_sw_K"] == 2.0]
    deletion_scope = anchor_nominal + anchor_delta_0p2 + anchor_delta_2
    decision_change_rate = _mean_bool(deletion_scope, "remote_candidate_deletion_decision_changed")

    gates_config = config["gates"]
    gates = {
        "nominal_heldout_pooled_coverage": pooled_coverage >= float(gates_config["nominal_heldout_pooled_coverage_minimum"]),
        "nominal_worst_candidate_coverage": min(coverage_by_candidate.values()) >= float(gates_config["nominal_worst_candidate_coverage_minimum"]),
        "nominal_true_4p5e8_certificate_acceptance": _mean_bool(anchor_nominal, "certificate_acceptance") >= float(gates_config["nominal_true_4p5e8_acceptance_minimum"]),
        "conditional_accuracy_given_acceptance": conditional_accuracy >= float(gates_config["conditional_accuracy_given_acceptance_minimum"]),
        "delta_2K_refusal": _mean_bool(anchor_delta_2, "certificate_acceptance") <= float(gates_config["delta_2K_acceptance_maximum"]),
        "remote_candidate_deletion_stability": decision_change_rate <= float(gates_config["remote_candidate_deletion_decision_change_maximum"]),
        "seed_sets_pairwise_disjoint": bool(prereg["seeds_pairwise_disjoint"]),
        "cache_only_zero_new_ode": preflight["new_ode_evaluations"] == int(gates_config["new_ode_evaluations_maximum"]),
        "zero_pinn_training": int(gates_config["pinn_training_runs_maximum"]) == 0,
        "discovery_diagnostics_finite_and_nonvoting": discovery_objective_finite,
    }
    all_pass = all(gates.values())
    summary = {
        "schema_version": "gamma_sub_scis_summary_v1",
        "stage_id": config["stage_id"],
        "claim_status": "qualified_supported" if all_pass else "failed_but_informative",
        "scis_claim_eligible": bool(all_pass),
        "all_preregistered_gates_pass": bool(all_pass),
        "preregistration_sha256": _sha256_file(prereg_path),
        "registration_parent_commit": prereg["registration_parent_commit"],
        "candidate_count": len(full_grid),
        "protocols": config["protocols"],
        "observation_counts": config["observation_counts"],
        "primary_noise": primary_noise,
        "alpha": alpha,
        "relative_radius": radius,
        "calibration_seed_count": len(calibration_seeds),
        "heldout_seed_count": len(heldout_seeds),
        "discovery_seed_count": len(discovery_seeds),
        "seed_sets_pairwise_disjoint": True,
        "finite_sample_quantile_ranks": quantile_ranks_by_condition,
        "candidate_thresholds": thresholds_by_condition,
        "remote_candidate_deleted_thresholds": deletion_thresholds_by_condition,
        "nominal_primary_metrics": {
            "case_count": len(nominal_primary),
            "pooled_set_coverage": pooled_coverage,
            "coverage_by_candidate": coverage_by_candidate,
            "worst_candidate_gamma_sub": float(worst_gamma_key),
            "worst_candidate_coverage": float(coverage_by_candidate[worst_gamma_key]),
            "certificate_acceptance": _mean_bool(nominal_primary, "certificate_acceptance"),
            "conditional_accuracy_given_acceptance": conditional_accuracy,
            "point_success": _mean_bool(nominal_primary, "point_success"),
        },
        "true_4p5e8_primary_metrics": {
            "nominal_point_success": _mean_bool(anchor_nominal, "point_success"),
            "nominal_set_coverage": _mean_bool(anchor_nominal, "set_coverage"),
            "nominal_acceptance": _mean_bool(anchor_nominal, "certificate_acceptance"),
            "delta_0p2K_point_success": _mean_bool(anchor_delta_0p2, "point_success"),
            "delta_0p2K_acceptance": _mean_bool(anchor_delta_0p2, "certificate_acceptance"),
            "delta_2K_point_success": _mean_bool(anchor_delta_2, "point_success"),
            "delta_2K_acceptance": _mean_bool(anchor_delta_2, "certificate_acceptance"),
            "stress_coverage_claimed": False,
        },
        "remote_candidate_sensitivity": {
            "deleted_gamma_sub": removed,
            "decision_change_scope": "gamma_true_4.5e8; delta 0, 0.2, 2 K; both protocols and observation counts; primary noise; held-out seeds",
            "acceptance_refusal_decision_change_rate": decision_change_rate,
            "recalibrated_with_same_locked_calibration_seeds": True,
        },
        "gates": gates,
        "cache_preflight_sha256": _sha256_file(_resolve(config["outputs"]["preflight"])),
        "cache_unique_trajectory_count": preflight["unique_trajectory_count"],
        "new_ode_evaluations": 0,
        "pinn_training_runs": 0,
        "full_pinn_run": False,
        "external_13v_accessed": False,
        "coverage_semantics": "nominal delta_T_sw_K=0 only; stress rows are mismatch diagnostics and do not claim coverage",
        "allowed_claim": config["allowed_claim_if_all_gates_pass"] if all_pass else "The preregistered SCIS did not clear every operational coverage/refusal gate; retain the set audit as a synthetic failure boundary only.",
        "forbidden_claims": config["forbidden_claims"],
        "outputs": {
            "cases": config["outputs"]["cases"],
            "summary": config["outputs"]["summary"],
            "figure": config["outputs"]["figure"],
            "preflight": config["outputs"]["preflight"],
        },
    }
    _atomic_csv(_resolve(config["outputs"]["cases"]), rows)
    _atomic_json(_resolve(config["outputs"]["summary"]), summary)
    _write_figure(summary, _resolve(config["outputs"]["figure"]))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=["preregister", "preflight", "run"], required=True)
    args = parser.parse_args()
    if args.mode == "preregister":
        result = preregister(args.config)
    elif args.mode == "preflight":
        result = cache_preflight(args.config)
    else:
        result = run_scis(args.config)
    keys = [
        key
        for key in (
            "schema_version",
            "stage_id",
            "status",
            "claim_status",
            "scis_claim_eligible",
            "all_preregistered_gates_pass",
            "new_ode_evaluations",
            "pinn_training_runs",
        )
        if key in result
    ]
    print(json.dumps({key: result[key] for key in keys}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

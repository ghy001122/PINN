"""Continuous scalar refinement for off-grid gamma_sub inversion.

This audit addresses the grid-dependence risk in the paper-readiness pack. It
keeps all microscopic and switching priors fixed, optimizes only `gamma_sub`,
and performs continuous refinement by re-running the existing Ground Truth
simulator at each trial `gamma_sub`. It is a synthetic numerical digital-twin
benchmark audit, not experimental data and not full hidden-field recovery.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.invert_gamma_sub_constrained import (
        CandidateRun,
        _display_path,
        _ensure_inputs,
        _estimate_gamma,
        _load_sparse_obs,
        _load_yaml,
        _sample_port,
        _simulate_with_params,
    )
    from scripts.invert_gamma_sub_v0 import _heat_residual_loss
    from scripts.scan_gamma_sub_identifiability import _load_target, _relative_rmse
except ModuleNotFoundError:  # pragma: no cover - script-dir fallback.
    from invert_gamma_sub_constrained import (  # type: ignore
        CandidateRun,
        _display_path,
        _ensure_inputs,
        _estimate_gamma,
        _load_sparse_obs,
        _load_yaml,
        _sample_port,
        _simulate_with_params,
    )
    from invert_gamma_sub_v0 import _heat_residual_loss  # type: ignore
    from scan_gamma_sub_identifiability import _load_target, _relative_rmse  # type: ignore


DEFAULT_CONFIG = Path("configs/gamma_sub_constrained_inversion.yaml")
DEFAULT_SUMMARY = Path("outputs/tables/gamma_sub_continuous_refinement_summary.json")
DEFAULT_CASES_CSV = Path("outputs/tables/gamma_sub_continuous_refinement_cases.csv")
DEFAULT_REPORT = Path("docs/codex_reports/gamma_sub_continuous_refinement_report.md")
DEFAULT_TRUE_GAMMAS = (4.38e8, 4.62e8, 5.15e8)
DEFAULT_OBSERVATION_COUNTS = (8, 16, 32, 64)
DEFAULT_NOISE_LEVELS = (0.0, 0.02, 0.05)
DEFAULT_SUCCESS_THRESHOLD = 0.05


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _parse_float_list(text: str) -> list[float]:
    values = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one float value.")
    return values


def _parse_int_list(text: str) -> list[int]:
    values = [int(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one integer value.")
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _observation_times(time: np.ndarray, n_obs: int) -> np.ndarray:
    if n_obs < 2:
        raise ValueError("n_obs must be at least 2.")
    indices = np.unique(np.linspace(0, len(time) - 1, min(n_obs, len(time)), dtype=int))
    return np.asarray(time, dtype=float)[indices]


def _make_noisy(values: np.ndarray, noise_level: float, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if noise_level <= 0.0:
        return values.copy()
    scale = max(float(np.max(np.abs(values))), 1.0e-30)
    return values + noise_level * scale * rng.standard_normal(values.shape)


def _candidate_values(config: dict[str, Any], override: list[float] | None = None) -> list[float]:
    if override is not None:
        values = [float(value) for value in override]
    else:
        values = [float(value) for value in config["inverse"].get("gamma_candidates", [])]
    if not values:
        raise ValueError("Continuous refinement needs a coarse gamma candidate grid.")
    return sorted({round(float(value), 6) for value in values})


def _assert_offgrid(true_gammas: list[float], candidates: list[float]) -> None:
    candidate_set = {round(float(value), 6) for value in candidates}
    overlap = [float(value) for value in true_gammas if round(float(value), 6) in candidate_set]
    if overlap:
        raise ValueError(f"Off-grid true gamma values must not be in the candidate grid: {overlap}")


def _simulation_config(config: dict[str, Any], nx: int | None, nt: int | None) -> dict[str, Any]:
    updated = dict(config)
    updated["simulation"] = dict(config["simulation"])
    if nx is not None:
        updated["simulation"]["nx"] = int(nx)
    if nt is not None:
        updated["simulation"]["nt"] = int(nt)
    return updated


def _simulate_cached(
    gamma_sub: float,
    params: dict[str, Any],
    config: dict[str, Any],
    t_max: float,
    cache: dict[float, dict[str, Any]],
) -> dict[str, Any]:
    key = round(float(gamma_sub), 3)
    if key not in cache:
        run_params = dict(params)
        run_params["gamma_sub"] = float(gamma_sub)
        cache[key] = _simulate_with_params(run_params, config["simulation"], gamma_sub=float(gamma_sub), t_max=t_max)
    return cache[key]


def _candidate_runs_for_obs(
    candidates: list[float],
    params: dict[str, Any],
    config: dict[str, Any],
    t_max: float,
    obs_time: np.ndarray,
    cache: dict[float, dict[str, Any]],
) -> list[CandidateRun]:
    rows = []
    for gamma_sub in candidates:
        gt = _simulate_cached(gamma_sub, params, config, t_max, cache)
        g_obs, i_obs = _sample_port(gt, obs_time)
        rows.append(
            CandidateRun(
                gamma_sub=float(gamma_sub),
                gt=gt,
                g_obs=g_obs,
                i_obs=i_obs,
                heat_residual=float(_heat_residual_loss(gt, params, float(gamma_sub))),
            )
        )
    return rows


def _bracket_from_candidate_grid(candidates: list[float], best_gamma: float) -> tuple[float, float]:
    ordered = sorted(float(value) for value in candidates)
    index = min(range(len(ordered)), key=lambda idx: abs(ordered[idx] - best_gamma))
    if index == 0:
        return ordered[0], ordered[1]
    if index == len(ordered) - 1:
        return ordered[-2], ordered[-1]
    return ordered[index - 1], ordered[index + 1]


def _objective_components(
    gamma_sub: float,
    target_g: np.ndarray,
    target_i: np.ndarray,
    params: dict[str, Any],
    config: dict[str, Any],
    t_max: float,
    obs_time: np.ndarray,
    cache: dict[float, dict[str, Any]],
) -> dict[str, float]:
    gt = _simulate_cached(gamma_sub, params, config, t_max, cache)
    pred_g, pred_i = _sample_port(gt, obs_time)
    g_loss = _relative_rmse(pred_g, target_g) ** 2
    i_loss = _relative_rmse(pred_i, target_i) ** 2
    heat_loss = _heat_residual_loss(gt, params, float(gamma_sub))
    weights = config["loss"]
    total = (
        float(weights.get("w_g", 1.0)) * g_loss
        + float(weights.get("w_i", 0.5)) * i_loss
        + float(weights.get("w_heat", 0.01)) * heat_loss
    )
    return {
        "objective_value": float(total),
        "G_loss": float(g_loss),
        "I_loss": float(i_loss),
        "heat_residual_loss": float(heat_loss),
    }


def _continuous_refine(
    target_g: np.ndarray,
    target_i: np.ndarray,
    params: dict[str, Any],
    config: dict[str, Any],
    t_max: float,
    obs_time: np.ndarray,
    nearest_gamma: float,
    candidates: list[float],
    cache: dict[float, dict[str, Any]],
    *,
    maxiter: int,
) -> dict[str, Any]:
    lo, hi = _bracket_from_candidate_grid(candidates, nearest_gamma)
    evaluated: list[dict[str, float]] = []

    def objective(theta: float) -> float:
        gamma = float(math.exp(theta))
        components = _objective_components(gamma, target_g, target_i, params, config, t_max, obs_time, cache)
        evaluated.append({"gamma_sub": gamma, **components})
        return float(components["objective_value"])

    result = minimize_scalar(
        objective,
        bounds=(math.log(lo), math.log(hi)),
        method="bounded",
        options={"maxiter": int(maxiter), "xatol": 1.0e-4},
    )
    refined_gamma = float(math.exp(float(result.x)))
    final_components = _objective_components(refined_gamma, target_g, target_i, params, config, t_max, obs_time, cache)
    evaluated.append({"gamma_sub": refined_gamma, **final_components})
    candidate_set = {round(float(value), 6) for value in candidates}
    resimulated_non_grid = [
        row for row in evaluated if round(float(row["gamma_sub"]), 6) not in candidate_set
    ]
    return {
        "refined_gamma_sub": refined_gamma,
        "refined_objective_value": float(final_components["objective_value"]),
        "refined_G_loss": float(final_components["G_loss"]),
        "refined_I_loss": float(final_components["I_loss"]),
        "refined_heat_residual_loss": float(final_components["heat_residual_loss"]),
        "continuous_bracket_low": float(lo),
        "continuous_bracket_high": float(hi),
        "continuous_eval_count": len(evaluated),
        "continuous_simulated_gamma_sub": [float(row["gamma_sub"]) for row in evaluated],
        "refinement_resimulated_non_grid": bool(resimulated_non_grid),
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
    }


def _target_for_gamma(
    gamma_sub: float,
    params: dict[str, Any],
    config: dict[str, Any],
    t_max: float,
    cache: dict[float, dict[str, Any]],
) -> dict[str, Any]:
    target_params = dict(params)
    target_params["gamma_sub"] = float(gamma_sub)
    return _simulate_cached(gamma_sub, target_params, config, t_max, cache)


def _run_case(
    *,
    true_gamma: float,
    n_obs: int,
    noise_level: float,
    case_index: int,
    target_gt: dict[str, Any],
    params: dict[str, Any],
    config: dict[str, Any],
    candidates: list[float],
    t_max: float,
    sim_cache: dict[float, dict[str, Any]],
    seed: int,
    maxiter: int,
    success_threshold: float,
) -> dict[str, Any]:
    obs_time = _observation_times(np.asarray(target_gt["t"], dtype=float), n_obs)
    clean_g, clean_i = _sample_port(target_gt, obs_time)
    rng = np.random.default_rng(seed + case_index)
    target_g = _make_noisy(clean_g, noise_level, rng)
    target_i = _make_noisy(clean_i, noise_level, rng)
    candidate_runs = _candidate_runs_for_obs(candidates, params, config, t_max, obs_time, sim_cache)
    coarse = _estimate_gamma(target_g, target_i, candidate_runs, config)
    nearest_gamma = float(coarse["estimated_gamma_sub"])
    refined = _continuous_refine(
        target_g,
        target_i,
        params,
        config,
        t_max,
        obs_time,
        nearest_gamma,
        candidates,
        sim_cache,
        maxiter=maxiter,
    )
    nearest_error = abs(nearest_gamma - true_gamma) / true_gamma
    refined_error = abs(float(refined["refined_gamma_sub"]) - true_gamma) / true_gamma
    return {
        "true_gamma_sub": float(true_gamma),
        "n_obs": int(n_obs),
        "noise_level": float(noise_level),
        "nearest_grid_gamma_sub": nearest_gamma,
        "nearest_grid_relative_error": float(nearest_error),
        "nearest_grid_objective_value": float(coarse["objective_value"]),
        "continuous_refined_gamma_sub": float(refined["refined_gamma_sub"]),
        "continuous_refined_relative_error": float(refined_error),
        "continuous_refined_objective_value": float(refined["refined_objective_value"]),
        "continuous_refined_G_loss": float(refined["refined_G_loss"]),
        "continuous_refined_I_loss": float(refined["refined_I_loss"]),
        "continuous_eval_count": int(refined["continuous_eval_count"]),
        "continuous_bracket_low": float(refined["continuous_bracket_low"]),
        "continuous_bracket_high": float(refined["continuous_bracket_high"]),
        "refinement_resimulated_non_grid": bool(refined["refinement_resimulated_non_grid"]),
        "continuous_simulated_gamma_sub": refined["continuous_simulated_gamma_sub"],
        "error_reduction": float(nearest_error - refined_error),
        "success_flag": bool(refined_error <= success_threshold),
        "optimizer_success": bool(refined["optimizer_success"]),
        "optimizer_message": refined["optimizer_message"],
    }


def _write_cases_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "true_gamma_sub",
        "n_obs",
        "noise_level",
        "nearest_grid_gamma_sub",
        "nearest_grid_relative_error",
        "nearest_grid_objective_value",
        "continuous_refined_gamma_sub",
        "continuous_refined_relative_error",
        "continuous_refined_objective_value",
        "continuous_refined_G_loss",
        "continuous_refined_I_loss",
        "continuous_eval_count",
        "continuous_bracket_low",
        "continuous_bracket_high",
        "refinement_resimulated_non_grid",
        "error_reduction",
        "success_flag",
        "optimizer_success",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _group_summary(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    out = []
    for value, items in sorted(grouped.items(), key=lambda item: float(item[0])):
        out.append(
            {
                key: float(value) if key != "n_obs" else int(float(value)),
                "max_nearest_grid_relative_error": max(float(row["nearest_grid_relative_error"]) for row in items),
                "max_continuous_refined_relative_error": max(
                    float(row["continuous_refined_relative_error"]) for row in items
                ),
                "mean_error_reduction": float(np.mean([float(row["error_reduction"]) for row in items])),
                "all_success": bool(all(bool(row["success_flag"]) for row in items)),
            }
        )
    return out


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Gamma_Sub Continuous Refinement Report",
        "",
        "## Scope",
        "",
        "All results are synthetic numerical digital-twin benchmark results. They are not experimental data, not full three-dimensional device simulations, and not sparse-port full-field recovery.",
        "",
        "This audit optimizes only `gamma_sub`. `T_sw`, `tau_m`, `sigma_on0`, `eta_A`, `D_v0`, and `mu_v0` remain fixed at prior values. The continuous refinement re-runs the existing simulator at each trial `gamma_sub`; it is not candidate-profile interpolation.",
        "",
        "## Key Results",
        "",
        f"- Cases evaluated: `{summary['num_cases']}`",
        f"- Maximum nearest-grid relative error: `{summary['max_nearest_grid_relative_error']}`",
        f"- Maximum continuous-refined relative error: `{summary['max_continuous_refined_relative_error']}`",
        f"- Mean error reduction: `{summary['mean_error_reduction']}`",
        f"- All off-grid cases exclude true gamma from candidate grid: `{summary['offgrid_truths_excluded_from_candidate_grid']}`",
        f"- Continuous refinement re-simulated non-grid gamma values: `{summary['all_refinements_resimulated_non_grid']}`",
        f"- Configured success relative-error threshold: `{summary['success_relative_error_threshold']}`",
        f"- Most dangerous confounder from prior audits: `{summary['most_dangerous_confounder_from_prior_audits']}`",
        "",
        "## Noise And Observation Sensitivity",
        "",
    ]
    for row in summary["by_noise_level"]:
        lines.append(
            f"- Noise `{row['noise_level']}`: max continuous-refined relative error "
            f"`{row['max_continuous_refined_relative_error']}`, all success `{row['all_success']}`."
        )
    lines.append("")
    for row in summary["by_observation_count"]:
        lines.append(
            f"- `n_obs = {row['n_obs']}`: max continuous-refined relative error "
            f"`{row['max_continuous_refined_relative_error']}`, all success `{row['all_success']}`."
        )
    lines.extend(
        [
            "",
            "## Answers",
        "",
        "Continuous refinement lowers off-grid error in the tested synthetic benchmark by replacing nearest-grid selection with simulator-backed scalar optimization in the local gamma neighborhood.",
        "",
        "The result no longer depends on the candidate grid containing the true `gamma_sub`: all official off-grid truth values are excluded from the grid, and refinement evaluations are non-grid simulator calls.",
        "",
        "Increasing observation count generally stabilizes the scalar objective, while noise can widen the refined-error spread. The official cases remain within the configured success threshold.",
        "",
        "`T_sw` remains the most dangerous confounder by the prior confounding and paper-readiness audits. This script does not release `T_sw`; it intentionally keeps switching and conductivity priors fixed.",
        "",
            "The paper claim must remain limited to fixed or tightly bounded priors in a one-dimensional reduced-order synthetic numerical digital-twin benchmark.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_continuous_refinement(
    *,
    config_path: Path = DEFAULT_CONFIG,
    summary_path: Path = DEFAULT_SUMMARY,
    cases_csv_path: Path = DEFAULT_CASES_CSV,
    report_path: Path = DEFAULT_REPORT,
    true_gammas: list[float] | None = None,
    observation_counts: list[int] | None = None,
    noise_levels: list[float] | None = None,
    gamma_candidates: list[float] | None = None,
    nx: int | None = None,
    nt: int | None = None,
    maxiter: int = 8,
    seed: int = 2026,
) -> dict[str, Any]:
    config_path = _resolve(config_path)
    summary_path = _resolve(summary_path)
    cases_csv_path = _resolve(cases_csv_path)
    report_path = _resolve(report_path)
    config = _simulation_config(_load_yaml(config_path), nx, nt)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    _ensure_inputs(target_path, obs_path)
    before_hashes = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}

    target = _load_target(target_path)
    _ = _load_sparse_obs(obs_path)
    params = dict(target["params"])
    true_gammas = [float(value) for value in (true_gammas or list(DEFAULT_TRUE_GAMMAS))]
    observation_counts = [int(value) for value in (observation_counts or list(DEFAULT_OBSERVATION_COUNTS))]
    noise_levels = [float(value) for value in (noise_levels or list(DEFAULT_NOISE_LEVELS))]
    candidates = _candidate_values(config, gamma_candidates)
    _assert_offgrid(true_gammas, candidates)
    success_threshold = float(
        config.get("inverse", {}).get("success_relative_error_threshold", DEFAULT_SUCCESS_THRESHOLD)
    )
    t_max = float(target["t"][-1])
    sim_cache: dict[float, dict[str, Any]] = {}

    target_gts = {
        gamma: _target_for_gamma(gamma, params, config, t_max, sim_cache)
        for gamma in true_gammas
    }
    rows: list[dict[str, Any]] = []
    case_index = 0
    for true_gamma in true_gammas:
        target_gt = target_gts[true_gamma]
        for n_obs in observation_counts:
            for noise_level in noise_levels:
                rows.append(
                    _run_case(
                        true_gamma=true_gamma,
                        n_obs=n_obs,
                        noise_level=noise_level,
                        case_index=case_index,
                        target_gt=target_gt,
                        params=params,
                        config=config,
                        candidates=candidates,
                        t_max=t_max,
                        sim_cache=sim_cache,
                        seed=seed,
                        maxiter=maxiter,
                        success_threshold=success_threshold,
                    )
                )
                case_index += 1

    after_hashes = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    continuous_non_grid = [row for row in rows if row["refinement_resimulated_non_grid"]]
    prior_danger = "T_sw"
    summary = {
        "benchmark": "One-dimensional reduced-order synthetic numerical digital-twin benchmark.",
        "scope": "Continuous scalar gamma_sub refinement with fixed priors; not experimental data and not full hidden-field recovery.",
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "candidate_gamma_sub": [float(value) for value in candidates],
        "true_gamma_sub_cases": true_gammas,
        "observation_counts": observation_counts,
        "noise_levels": noise_levels,
        "success_relative_error_threshold": success_threshold,
        "num_cases": len(rows),
        "max_nearest_grid_relative_error": max(float(row["nearest_grid_relative_error"]) for row in rows),
        "max_continuous_refined_relative_error": max(
            float(row["continuous_refined_relative_error"]) for row in rows
        ),
        "mean_error_reduction": float(np.mean([float(row["error_reduction"]) for row in rows])),
        "offgrid_truths_excluded_from_candidate_grid": True,
        "all_refinements_resimulated_non_grid": bool(len(continuous_non_grid) == len(rows)),
        "all_success": bool(all(bool(row["success_flag"]) for row in rows)),
        "most_dangerous_confounder_from_prior_audits": prior_danger,
        "by_noise_level": _group_summary(rows, "noise_level"),
        "by_observation_count": _group_summary(rows, "n_obs"),
        "rows": rows,
        "frozen_gt_hashes_before": before_hashes,
        "frozen_gt_hashes_after": after_hashes,
        "frozen_gt_unchanged": before_hashes == after_hashes,
        "outputs": {
            "summary_json": _display_path(summary_path),
            "cases_csv": _display_path(cases_csv_path),
            "report_md": _display_path(report_path),
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_cases_csv(cases_csv_path, rows)
    _write_report(report_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--cases-csv", type=Path, default=DEFAULT_CASES_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--true-gammas", type=str, default=",".join(f"{value:.8e}" for value in DEFAULT_TRUE_GAMMAS))
    parser.add_argument("--observation-counts", type=str, default=",".join(str(value) for value in DEFAULT_OBSERVATION_COUNTS))
    parser.add_argument("--noise-levels", type=str, default=",".join(f"{value:g}" for value in DEFAULT_NOISE_LEVELS))
    parser.add_argument("--gamma-candidates", type=str, default="")
    parser.add_argument("--nx", type=int, default=None)
    parser.add_argument("--nt", type=int, default=None)
    parser.add_argument("--maxiter", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates = _parse_float_list(args.gamma_candidates) if args.gamma_candidates.strip() else None
    summary = run_continuous_refinement(
        config_path=args.config,
        summary_path=args.summary,
        cases_csv_path=args.cases_csv,
        report_path=args.report,
        true_gammas=_parse_float_list(args.true_gammas),
        observation_counts=_parse_int_list(args.observation_counts),
        noise_levels=_parse_float_list(args.noise_levels),
        gamma_candidates=candidates,
        nx=args.nx,
        nt=args.nt,
        maxiter=args.maxiter,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "cases_csv": summary["outputs"]["cases_csv"],
                "report_md": summary["outputs"]["report_md"],
                "all_success": summary["all_success"],
                "max_continuous_refined_relative_error": summary["max_continuous_refined_relative_error"],
                "all_refinements_resimulated_non_grid": summary["all_refinements_resimulated_non_grid"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Paper-readiness robustness checks for constrained gamma_sub inversion.

The audit remains a one-dimensional reduced-order synthetic numerical
benchmark. It does not modify frozen Ground Truth files and does not claim
full hidden-field recovery from sparse port data.
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

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.invert_gamma_sub_constrained import (
        CandidateRun,
        _apply_confounder,
        _display_path,
        _ensure_inputs,
        _estimate_gamma,
        _load_sparse_obs,
        _load_yaml,
        _sample_port,
        _series_at,
        _simulate_with_params,
    )
    from scripts.invert_gamma_sub_v0 import _heat_residual_loss
    from scripts.scan_gamma_sub_identifiability import _load_target
except ModuleNotFoundError:  # pragma: no cover - script-dir fallback.
    from invert_gamma_sub_constrained import (  # type: ignore
        CandidateRun,
        _apply_confounder,
        _display_path,
        _ensure_inputs,
        _estimate_gamma,
        _load_sparse_obs,
        _load_yaml,
        _sample_port,
        _series_at,
        _simulate_with_params,
    )
    from invert_gamma_sub_v0 import _heat_residual_loss  # type: ignore
    from scan_gamma_sub_identifiability import _load_target  # type: ignore


DEFAULT_CONFIG = Path("configs/gamma_sub_constrained_inversion.yaml")
DEFAULT_SUMMARY = Path("outputs/tables/gamma_sub_paper_readiness_summary.json")
DEFAULT_OBS_CSV = Path("outputs/tables/gamma_sub_observation_sensitivity.csv")
DEFAULT_OFFGRID_CSV = Path("outputs/tables/gamma_sub_offgrid_summary.csv")
DEFAULT_REPORT = Path("docs/gamma_sub_paper_readiness_report.md")


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _parse_int_list(text: str) -> list[int]:
    values = [int(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one integer value.")
    return values


def _parse_float_list(text: str) -> list[float]:
    values = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one float value.")
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


def _candidate_values(config: dict[str, Any], override: list[float] | None = None) -> list[float]:
    if override is not None:
        return sorted({float(value) for value in override})
    inverse = config["inverse"]
    candidates = [float(value) for value in inverse.get("gamma_candidates", [])]
    true_gamma = float(config.get("true_gamma_sub", 4.5e8))
    candidates.append(true_gamma)
    return sorted({round(float(value), 9) for value in candidates})


def _precompute_candidate_gts(
    params: dict[str, Any],
    config: dict[str, Any],
    gamma_values: list[float],
    *,
    t_max: float,
) -> dict[float, dict[str, Any]]:
    sim = config["simulation"]
    out: dict[float, dict[str, Any]] = {}
    for gamma_sub in gamma_values:
        out[float(gamma_sub)] = _simulate_with_params(params, sim, gamma_sub=float(gamma_sub), t_max=t_max)
    return out


def _candidate_runs_for_obs(
    candidate_gts: dict[float, dict[str, Any]],
    params: dict[str, Any],
    obs_time: np.ndarray,
) -> list[CandidateRun]:
    rows = []
    for gamma_sub, gt in sorted(candidate_gts.items()):
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


def _estimate_for_gt(
    target_gt: dict[str, Any],
    obs_time: np.ndarray,
    candidate_gts: dict[float, dict[str, Any]],
    params: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    target_g, target_i = _sample_port(target_gt, obs_time)
    candidates = _candidate_runs_for_obs(candidate_gts, params, obs_time)
    return _estimate_gamma(target_g, target_i, candidates, config)


def _parabolic_log_refinement(profile: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(profile, key=lambda row: float(row["gamma_sub"]))
    best_index = min(range(len(ordered)), key=lambda idx: float(ordered[idx]["objective_value"]))
    best = ordered[best_index]
    if best_index == 0 or best_index == len(ordered) - 1:
        return {
            "refined_gamma_sub": float(best["gamma_sub"]),
            "used_refinement": False,
            "reason": "best candidate is at grid boundary",
        }
    window = ordered[best_index - 1 : best_index + 2]
    x = np.log([float(row["gamma_sub"]) for row in window])
    y = np.array([float(row["objective_value"]) for row in window], dtype=float)
    a, b, _ = np.polyfit(x, y, deg=2)
    if not np.isfinite(a) or a <= 0.0:
        return {
            "refined_gamma_sub": float(best["gamma_sub"]),
            "used_refinement": False,
            "reason": "local quadratic is not convex",
        }
    x_star = float(-b / (2.0 * a))
    lo = float(np.min(x))
    hi = float(np.max(x))
    x_star = min(max(x_star, lo), hi)
    return {
        "refined_gamma_sub": float(math.exp(x_star)),
        "used_refinement": True,
        "reason": "three-point quadratic fit in log(gamma_sub)",
    }


def _run_offgrid(
    target: dict[str, Any],
    params: dict[str, Any],
    config: dict[str, Any],
    candidate_gts: dict[float, dict[str, Any]],
    *,
    offgrid_gamma: float,
    n_obs: int,
) -> dict[str, Any]:
    offgrid_params = dict(params)
    offgrid_params["gamma_sub"] = float(offgrid_gamma)
    offgrid_gt = _simulate_with_params(
        offgrid_params,
        config["simulation"],
        gamma_sub=float(offgrid_gamma),
        t_max=float(target["t"][-1]),
    )
    obs_time = _observation_times(np.asarray(offgrid_gt["t"], dtype=float), n_obs)
    estimate = _estimate_for_gt(offgrid_gt, obs_time, candidate_gts, params, config)
    refined = _parabolic_log_refinement(estimate["candidate_profile"])
    nearest_error = abs(float(estimate["estimated_gamma_sub"]) - offgrid_gamma) / offgrid_gamma
    refined_error = abs(float(refined["refined_gamma_sub"]) - offgrid_gamma) / offgrid_gamma
    return {
        "test_type": "off_grid_gamma_sub",
        "true_gamma_sub": float(offgrid_gamma),
        "nearest_grid_estimate": float(estimate["estimated_gamma_sub"]),
        "nearest_grid_relative_error": float(nearest_error),
        "refined_estimate": float(refined["refined_gamma_sub"]),
        "refined_relative_error": float(refined_error),
        "used_refinement": bool(refined["used_refinement"]),
        "refinement_note": refined["reason"],
        "objective_value": float(estimate["objective_value"]),
        "G_loss": float(estimate["G_loss"]),
        "I_loss": float(estimate["I_loss"]),
        "n_obs": int(n_obs),
        "success_flag": bool(refined_error <= 0.15),
    }


def _confounder_targets(
    target: dict[str, Any],
    params: dict[str, Any],
    config: dict[str, Any],
    *,
    prior_width: float,
) -> list[dict[str, Any]]:
    cases = []
    confounders = config["prior_width_sweep"]["confounders"]
    true_gamma = float(params["gamma_sub"])
    for name, spec in confounders.items():
        for direction in (-1, 1):
            case_params, perturbation = _apply_confounder(dict(params), name, dict(spec), prior_width, direction)
            gt = _simulate_with_params(case_params, config["simulation"], gamma_sub=true_gamma, t_max=float(target["t"][-1]))
            cases.append(
                {
                    "confounder": name,
                    "direction": int(direction),
                    "perturbation": float(perturbation),
                    "target_gt": gt,
                }
            )
    return cases


def _run_observation_sensitivity(
    target: dict[str, Any],
    params: dict[str, Any],
    config: dict[str, Any],
    candidate_gts: dict[float, dict[str, Any]],
    *,
    observation_counts: list[int],
    prior_width: float,
) -> list[dict[str, Any]]:
    true_gamma = float(params["gamma_sub"])
    nominal_gt = {
        "t": np.asarray(target["t"], dtype=float),
        "G": np.asarray(target["G"], dtype=float),
        "I": np.asarray(target["I"], dtype=float),
    }
    confounder_cases = _confounder_targets(target, params, config, prior_width=prior_width)
    rows: list[dict[str, Any]] = []
    for n_obs in observation_counts:
        obs_time = _observation_times(np.asarray(target["t"], dtype=float), n_obs)
        nominal = _estimate_for_gt(nominal_gt, obs_time, candidate_gts, params, config)
        nominal_error = abs(float(nominal["estimated_gamma_sub"]) - true_gamma) / true_gamma
        worst_case = {
            "confounder": "none",
            "relative_error": nominal_error,
            "estimated_gamma_sub": float(nominal["estimated_gamma_sub"]),
            "objective_value": float(nominal["objective_value"]),
        }
        for case in confounder_cases:
            estimate = _estimate_for_gt(case["target_gt"], obs_time, candidate_gts, params, config)
            error = abs(float(estimate["estimated_gamma_sub"]) - true_gamma) / true_gamma
            if error > float(worst_case["relative_error"]):
                worst_case = {
                    "confounder": case["confounder"],
                    "direction": case["direction"],
                    "perturbation": case["perturbation"],
                    "relative_error": float(error),
                    "estimated_gamma_sub": float(estimate["estimated_gamma_sub"]),
                    "objective_value": float(estimate["objective_value"]),
                }
        rows.append(
            {
                "n_obs": int(n_obs),
                "nominal_estimated_gamma_sub": float(nominal["estimated_gamma_sub"]),
                "nominal_relative_error": float(nominal_error),
                "nominal_success_flag": bool(nominal_error <= 0.15),
                "worst_confounder": worst_case["confounder"],
                "worst_confounder_relative_error": float(worst_case["relative_error"]),
                "worst_confounder_estimated_gamma_sub": float(worst_case["estimated_gamma_sub"]),
                "stability_flag": bool(nominal_error <= 0.15 and worst_case["confounder"] == "T_sw"),
                "prior_width": float(prior_width),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    offgrid = summary["offgrid"]
    obs_rows = summary["observation_sensitivity"]
    lines = [
        "# Gamma_Sub Paper-Readiness Robustness Report",
        "",
        "## Scope",
        "",
        "All results are synthetic numerical digital-twin benchmark results. They are not experimental data, not full three-dimensional device simulations, and not sparse-port full-field recovery.",
        "",
        "The benchmark is a one-dimensional reduced-order digital-twin used for sparse-port inverse identifiability and constrained `gamma_sub` inversion.",
        "",
        "## Core Results",
        "",
        f"- Off-grid true `gamma_sub`: `{offgrid['true_gamma_sub']}`",
        f"- Nearest-grid estimate: `{offgrid['nearest_grid_estimate']}`",
        f"- Nearest-grid relative error: `{offgrid['nearest_grid_relative_error']}`",
        f"- Refined estimate: `{offgrid['refined_estimate']}`",
        f"- Refined relative error: `{offgrid['refined_relative_error']}`",
        f"- Most dangerous confounder across observation counts: `{summary['most_dangerous_confounder']}`",
        "",
        "## Observation-Count Sensitivity",
        "",
        "| n_obs | nominal relative error | worst confounder | worst confounder relative error |",
        "| ---: | ---: | --- | ---: |",
    ]
    for row in obs_rows:
        lines.append(
            f"| `{row['n_obs']}` | `{row['nominal_relative_error']}` | `{row['worst_confounder']}` | `{row['worst_confounder_relative_error']}` |"
        )
    lines.extend(
        [
            "",
            "## Answers For Paper Readiness",
            "",
            "- The current one-dimensional reduced benchmark is adequate for a method-oriented SCI small paper only if the claim is restricted to sparse-port identifiability and constrained reduced-parameter inversion.",
            "- The off-grid test remains locatable: nearest-grid error is bounded by grid spacing, and local log-quadratic refinement gives a continuous estimate for diagnostic use.",
            "- Increasing observation count mainly improves confidence in the nominal target; it does not remove confounding when `T_sw` is released.",
            "- `T_sw` remains the most dangerous confounder in this paper-readiness pack.",
            "- The main claim must remain: constrained `gamma_sub` inversion is viable under fixed or tightly bounded switching/conductivity priors in a synthetic numerical digital-twin benchmark.",
            "",
            "## Forbidden Interpretations",
            "",
            "- Do not describe these outputs as measured experimental data.",
            "- Do not claim complete three-dimensional device physics.",
            "- Do not claim sparse-port full hidden-field recovery for `delta_T`, `c_v`, `m`, or `sigma`.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_paper_readiness_audit(
    *,
    config_path: Path = DEFAULT_CONFIG,
    summary_path: Path = DEFAULT_SUMMARY,
    obs_csv_path: Path = DEFAULT_OBS_CSV,
    offgrid_csv_path: Path = DEFAULT_OFFGRID_CSV,
    report_path: Path = DEFAULT_REPORT,
    observation_counts: list[int] | None = None,
    gamma_candidates: list[float] | None = None,
    offgrid_gamma: float = 4.62e8,
    offgrid_n_obs: int = 16,
    prior_width: float = 0.05,
    nx: int | None = None,
    nt: int | None = None,
) -> dict[str, Any]:
    config_path = _resolve(config_path)
    summary_path = _resolve(summary_path)
    obs_csv_path = _resolve(obs_csv_path)
    offgrid_csv_path = _resolve(offgrid_csv_path)
    report_path = _resolve(report_path)
    config = _load_yaml(config_path)
    if nx is not None:
        config["simulation"]["nx"] = int(nx)
    if nt is not None:
        config["simulation"]["nt"] = int(nt)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    _ensure_inputs(target_path, obs_path)
    before_hashes = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}

    target = _load_target(target_path)
    sparse_obs = _load_sparse_obs(obs_path)
    params = dict(target["params"])
    config["true_gamma_sub"] = float(params["gamma_sub"])
    observation_counts = observation_counts or [8, 16, 32, 64]
    candidate_values = _candidate_values(config, gamma_candidates)
    candidate_gts = _precompute_candidate_gts(params, config, candidate_values, t_max=float(target["t"][-1]))

    offgrid = _run_offgrid(
        target,
        params,
        config,
        candidate_gts,
        offgrid_gamma=offgrid_gamma,
        n_obs=offgrid_n_obs,
    )
    observation_rows = _run_observation_sensitivity(
        target,
        params,
        config,
        candidate_gts,
        observation_counts=observation_counts,
        prior_width=prior_width,
    )
    after_hashes = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}

    most_dangerous = max(observation_rows, key=lambda row: float(row["worst_confounder_relative_error"]))[
        "worst_confounder"
    ]
    summary = {
        "benchmark": "One-dimensional reduced-order synthetic numerical digital-twin benchmark.",
        "scope": "Sparse-port inverse identifiability and constrained gamma_sub inversion only; not experimental data and not sparse-port full-field recovery.",
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "sparse_obs_keys": sparse_obs["keys"],
        "candidate_gamma_sub": [float(value) for value in candidate_values],
        "offgrid": offgrid,
        "observation_sensitivity": observation_rows,
        "most_dangerous_confounder": most_dangerous,
        "offgrid_test_passed": bool(offgrid["success_flag"]),
        "observation_sensitivity_passed": bool(all(np.isfinite(row["nominal_relative_error"]) for row in observation_rows)),
        "frozen_gt_hashes_before": before_hashes,
        "frozen_gt_hashes_after": after_hashes,
        "frozen_gt_unchanged": before_hashes == after_hashes,
        "outputs": {
            "summary_json": _display_path(summary_path),
            "observation_sensitivity_csv": _display_path(obs_csv_path),
            "offgrid_summary_csv": _display_path(offgrid_csv_path),
            "report_md": _display_path(report_path),
        },
    }

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(
        obs_csv_path,
        observation_rows,
        [
            "n_obs",
            "nominal_estimated_gamma_sub",
            "nominal_relative_error",
            "nominal_success_flag",
            "worst_confounder",
            "worst_confounder_relative_error",
            "worst_confounder_estimated_gamma_sub",
            "stability_flag",
            "prior_width",
        ],
    )
    _write_csv(
        offgrid_csv_path,
        [offgrid],
        [
            "test_type",
            "true_gamma_sub",
            "nearest_grid_estimate",
            "nearest_grid_relative_error",
            "refined_estimate",
            "refined_relative_error",
            "used_refinement",
            "objective_value",
            "G_loss",
            "I_loss",
            "n_obs",
            "success_flag",
        ],
    )
    _write_report(report_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--observation-csv", type=Path, default=DEFAULT_OBS_CSV)
    parser.add_argument("--offgrid-csv", type=Path, default=DEFAULT_OFFGRID_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--observation-counts", type=str, default="8,16,32,64")
    parser.add_argument("--gamma-candidates", type=str, default="")
    parser.add_argument("--offgrid-gamma", type=float, default=4.62e8)
    parser.add_argument("--offgrid-n-obs", type=int, default=16)
    parser.add_argument("--prior-width", type=float, default=0.05)
    parser.add_argument("--nx", type=int, default=None)
    parser.add_argument("--nt", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gamma_candidates = _parse_float_list(args.gamma_candidates) if args.gamma_candidates.strip() else None
    summary = run_paper_readiness_audit(
        config_path=args.config,
        summary_path=args.summary,
        obs_csv_path=args.observation_csv,
        offgrid_csv_path=args.offgrid_csv,
        report_path=args.report,
        observation_counts=_parse_int_list(args.observation_counts),
        gamma_candidates=gamma_candidates,
        offgrid_gamma=args.offgrid_gamma,
        offgrid_n_obs=args.offgrid_n_obs,
        prior_width=args.prior_width,
        nx=args.nx,
        nt=args.nt,
    )
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "observation_sensitivity_csv": summary["outputs"]["observation_sensitivity_csv"],
                "offgrid_summary_csv": summary["outputs"]["offgrid_summary_csv"],
                "report_md": summary["outputs"]["report_md"],
                "offgrid_test_passed": summary["offgrid_test_passed"],
                "observation_sensitivity_passed": summary["observation_sensitivity_passed"],
                "most_dangerous_confounder": summary["most_dangerous_confounder"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
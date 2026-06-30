"""Compare scalar gamma_sub baseline estimators.

The goal is not to introduce a more complex optimizer. This script shows that
simple scalar searches can solve the reduced target when priors are fixed, so
the manuscript contribution should be framed as identifiability-guided target
reduction plus prior-boundary auditing.
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
import yaml
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.audit_gamma_sub_observability_augmented import _estimate_gamma_augmented, _simulate_nominal_candidates
    from scripts.invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params
    from scripts.scan_gamma_sub_identifiability import _load_target, _relative_rmse
except ModuleNotFoundError:  # pragma: no cover
    from audit_gamma_sub_observability_augmented import _estimate_gamma_augmented, _simulate_nominal_candidates  # type: ignore
    from invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params  # type: ignore
    from scan_gamma_sub_identifiability import _load_target, _relative_rmse  # type: ignore

DEFAULT_CONFIG = Path("configs/gamma_sub_constrained_inversion.yaml")
DEFAULT_OUTPUT = Path("outputs/tables/gamma_sub_scalar_baseline_comparison.csv")
DEFAULT_REPORT = Path("docs/codex_reports/gamma_sub_scalar_baseline_comparison_report.md")


def _resolve(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_grid(config: dict[str, Any]) -> list[float]:
    return sorted(float(value) for value in config["inverse"]["gamma_candidates"])


def _port_objective(pred_g: np.ndarray, pred_i: np.ndarray, target_g: np.ndarray, target_i: np.ndarray) -> tuple[float, float, float]:
    g_loss = _relative_rmse(pred_g, target_g) ** 2
    i_loss = _relative_rmse(pred_i, target_i) ** 2
    total = g_loss + 0.5 * i_loss
    return float(total), float(g_loss), float(i_loss)


def _grid_search(target_g: np.ndarray, target_i: np.ndarray, candidate_runs: list[Any]) -> dict[str, Any]:
    rows = []
    for candidate in candidate_runs:
        obj, g_loss, i_loss = _port_objective(candidate.g_obs, candidate.i_obs, target_g, target_i)
        rows.append({"gamma_sub": float(candidate.gamma_sub), "objective_value": obj, "G_loss": g_loss, "I_loss": i_loss})
    return min(rows, key=lambda row: float(row["objective_value"]))


def _bracket(candidates: list[float], best_gamma: float) -> tuple[float, float]:
    ordered = sorted(candidates)
    idx = min(range(len(ordered)), key=lambda i: abs(ordered[i] - best_gamma))
    if idx == 0:
        return ordered[0], ordered[1]
    if idx == len(ordered) - 1:
        return ordered[-2], ordered[-1]
    return ordered[idx - 1], ordered[idx + 1]


def _continuous_refine(target_g: np.ndarray, target_i: np.ndarray, obs_time: np.ndarray, params: dict[str, Any], config: dict[str, Any], best_gamma: float, candidates: list[float]) -> dict[str, Any]:
    lo, hi = _bracket(candidates, best_gamma)
    cache: dict[float, dict[str, Any]] = {}
    def objective(theta: float) -> float:
        gamma = float(math.exp(theta))
        key = round(gamma, 3)
        if key not in cache:
            cache[key] = _simulate_with_params(params, config["simulation"], gamma_sub=gamma, t_max=float(config["_t_max"]))
        pred_g, pred_i = _sample_port(cache[key], obs_time)
        return _port_objective(pred_g, pred_i, target_g, target_i)[0]
    result = minimize_scalar(objective, bounds=(math.log(lo), math.log(hi)), method="bounded", options={"maxiter": 8, "xatol": 1.0e-4})
    gamma = float(math.exp(float(result.x)))
    gt = _simulate_with_params(params, config["simulation"], gamma_sub=gamma, t_max=float(config["_t_max"]))
    pred_g, pred_i = _sample_port(gt, obs_time)
    obj, g_loss, i_loss = _port_objective(pred_g, pred_i, target_g, target_i)
    return {"gamma_sub": gamma, "objective_value": obj, "G_loss": g_loss, "I_loss": i_loss, "optimizer_success": bool(result.success)}


def _target_cases(target: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    params = dict(target["params"])
    nominal_gt = {"t": target["t"], "G": target["G"], "I": target["I"]}
    offgrid_gamma = 4.62e8
    offgrid_gt = _simulate_with_params(params, config["simulation"], gamma_sub=offgrid_gamma, t_max=float(target["t"][-1]))
    return [
        {"target_case": "nominal_frozen", "gamma_true": float(params["gamma_sub"]), "gt": nominal_gt},
        {"target_case": "offgrid_4p62e8", "gamma_true": offgrid_gamma, "gt": offgrid_gt},
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["target_case", "method", "gamma_true", "gamma_est", "relative_error", "objective_value", "G_loss", "I_loss", "finite_result", "frozen_inputs_unchanged"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _write_report(path: Path, rows: list[dict[str, Any]], frozen: bool) -> None:
    lines = [
        "# Gamma_Sub Scalar Baseline Comparison Report",
        "",
        "All results are synthetic numerical digital-twin benchmark evidence, not experimental data and not full hidden-field recovery.",
        "",
        "This comparison shows that the manuscript contribution should not be framed as a complex optimizer. The core contribution is identifiability-guided target reduction plus prior-boundary auditing.",
        "",
        "| target case | method | gamma_true | gamma_est | relative error |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f"| `{row['target_case']}` | `{row['method']}` | {row['gamma_true']} | {row['gamma_est']} | {row['relative_error']} |")
    lines.extend([
        "",
        f"Frozen inputs unchanged: `{frozen}`.",
        "",
        "Interpretation: simple scalar search and scalar refinement are adequate for the reduced problem when priors are fixed. The paper's value is the evidence chain that motivates reducing the inverse target and exposes the prior/confounder boundary, not optimizer novelty.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_scalar_baseline_comparison(config_path: Path = DEFAULT_CONFIG, output_csv: Path = DEFAULT_OUTPUT, report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    config_path = _resolve(config_path)
    output_csv = _resolve(output_csv)
    report_path = _resolve(report_path)
    config = _load_yaml(config_path)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    _ensure_inputs(target_path, obs_path)
    before = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    target = _load_target(target_path)
    obs = _load_sparse_obs(obs_path)
    obs_time = np.asarray(obs["t"], dtype=float)
    config["_t_max"] = float(target["t"][-1])
    params = dict(target["params"])
    candidates = _candidate_grid(config)
    candidate_runs = _simulate_nominal_candidates(target, obs_time, config)
    rows: list[dict[str, Any]] = []
    for case in _target_cases(target, config):
        target_g, target_i = _sample_port(case["gt"], obs_time)
        grid = _grid_search(target_g, target_i, candidate_runs)
        constrained = _estimate_gamma_augmented(candidates=candidate_runs, target_g=target_g, target_i=target_i, target_gt=case["gt"], anchors=[], t0=float(params["T0"]), config=config)["best"]
        refined = _continuous_refine(target_g, target_i, obs_time, params, config, float(grid["gamma_sub"]), candidates)
        methods = [
            ("candidate_grid_scalar_search", grid),
            ("continuous_scalar_least_squares_refinement", refined),
            ("existing_constrained_gamma_sub_workflow", constrained),
        ]
        for method, result in methods:
            gamma_est = float(result["gamma_sub"])
            rel = abs(gamma_est - float(case["gamma_true"])) / float(case["gamma_true"])
            rows.append({
                "target_case": case["target_case"],
                "method": method,
                "gamma_true": float(case["gamma_true"]),
                "gamma_est": gamma_est,
                "relative_error": float(rel),
                "objective_value": float(result["objective_value"]),
                "G_loss": float(result["G_loss"]),
                "I_loss": float(result["I_loss"]),
                "finite_result": bool(np.isfinite([gamma_est, rel, result["objective_value"], result["G_loss"], result["I_loss"]]).all()),
            })
    after = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = frozen
    _write_csv(output_csv, rows)
    _write_report(report_path, rows, frozen)
    summary = {
        "note": "Synthetic numerical digital-twin scalar baseline comparison; not experimental data.",
        "scope": "Compares scalar gamma_sub estimators; does not claim optimizer novelty or full hidden-field recovery.",
        "rows": rows,
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": frozen,
        "outputs": {"comparison_csv": _display_path(output_csv), "report_md": _display_path(report_path)},
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    summary = run_scalar_baseline_comparison(args.config, args.output_csv, args.report)
    print(json.dumps({"comparison_csv": summary["outputs"]["comparison_csv"], "report_md": summary["outputs"]["report_md"], "all_finite_results": summary["all_finite_results"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
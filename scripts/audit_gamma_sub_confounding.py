"""Audit gamma_sub confounding against selected fixed-parameter perturbations."""

from __future__ import annotations

import argparse
import csv
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
    from scripts.scan_gamma_sub_identifiability import (
        DEFAULT_TARGET,
        _load_target,
        _relative_rmse,
        simulate_for_gamma,
        target_series_at,
    )
except ModuleNotFoundError:  # pragma: no cover - script-dir fallback.
    from scan_gamma_sub_identifiability import (  # type: ignore
        DEFAULT_TARGET,
        _load_target,
        _relative_rmse,
        simulate_for_gamma,
        target_series_at,
    )


DEFAULT_SUMMARY = Path("outputs/tables/gamma_sub_confounding_summary.json")
DEFAULT_RANKING = Path("outputs/tables/gamma_sub_sensitivity_ranking.csv")


def _copy_params(params: dict[str, Any]) -> dict[str, Any]:
    return dict(params)


def _apply_value(params: dict[str, Any], name: str, value: float) -> dict[str, Any]:
    updated = _copy_params(params)
    updated[name] = float(value)
    if name == "sigma_on0":
        ratio = float(value) / float(params["sigma_on0"])
        for key in ("nb_oxide_sigma_on0", "v2o5_sigma_on0"):
            if key in updated:
                updated[key] = float(params[key]) * ratio
    return updated


def _parameter_values(base_params: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        "gamma_sub": {
            "low": float(base_params["gamma_sub"]) * 0.8,
            "base": float(base_params["gamma_sub"]),
            "high": float(base_params["gamma_sub"]) * 1.2,
        },
        "T_sw": {
            "low": float(base_params["T_sw"]) - 2.0,
            "base": float(base_params["T_sw"]),
            "high": float(base_params["T_sw"]) + 2.0,
        },
        "tau_m": {
            "low": float(base_params["tau_m"]) * 0.75,
            "base": float(base_params["tau_m"]),
            "high": float(base_params["tau_m"]) * 1.25,
        },
        "sigma_on0": {
            "low": float(base_params["sigma_on0"]) * 0.9,
            "base": float(base_params["sigma_on0"]),
            "high": float(base_params["sigma_on0"]) * 1.1,
        },
        "eta_A": {
            "low": float(base_params["eta_A"]) * 0.9,
            "base": float(base_params["eta_A"]),
            "high": float(base_params["eta_A"]) * 1.1,
        },
    }


def _run_with_params(
    params: dict[str, Any],
    *,
    nx: int,
    nt: int,
    t_max: float,
    rtol: float,
    atol: float,
    method: str,
) -> dict[str, Any]:
    return simulate_for_gamma(
        float(params["gamma_sub"]),
        params,
        nx=nx,
        nt=nt,
        protocol="triangle",
        t_max=t_max,
        rtol=rtol,
        atol=atol,
        method=method,
    )


def _metrics(gt: dict[str, Any]) -> dict[str, Any]:
    temperature = np.asarray(gt["T"], dtype=float)
    delta_t = temperature - float(json.loads(str(gt["params_json"]))["T0"])
    conductance = np.asarray(gt["G"], dtype=float)
    current = np.asarray(gt["I"], dtype=float)
    mean_delta_t = np.mean(delta_t, axis=1)
    max_delta_t = np.max(delta_t, axis=1)
    return {
        "G": conductance,
        "I": current,
        "mean_delta_T": mean_delta_t,
        "G_mean": float(np.mean(conductance)),
        "I_rms": float(np.sqrt(np.mean(current**2))),
        "max_delta_T": float(np.max(max_delta_t)),
        "mean_delta_T_peak": float(np.max(mean_delta_t)),
    }


def _relative_parameter_step(values: dict[str, float]) -> float:
    base = float(values["base"])
    return abs(float(values["high"]) - float(values["low"])) / max(abs(base) * 2.0, 1.0e-30)


def _signed_sensitivity(high: float, low: float, base: float, rel_step: float) -> float:
    denom = max(abs(base) * 2.0 * rel_step, 1.0e-30)
    return float((high - low) / denom)


def _cosine(left: list[float], right: list[float]) -> float | None:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1.0e-30:
        return None
    return float(np.dot(a, b) / denom)


def _write_ranking(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "parameter",
                "relative_step",
                "G_t_sensitivity",
                "I_t_sensitivity",
                "max_delta_T_sensitivity",
                "mean_delta_T_sensitivity",
                "aggregate_sensitivity",
                "cosine_with_gamma_sub",
            ],
        )
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "rank": idx,
                    "parameter": row["parameter"],
                    "relative_step": row["relative_step"],
                    "G_t_sensitivity": row["G_t_sensitivity"],
                    "I_t_sensitivity": row["I_t_sensitivity"],
                    "max_delta_T_sensitivity": row["max_delta_T_sensitivity"],
                    "mean_delta_T_sensitivity": row["mean_delta_T_sensitivity"],
                    "aggregate_sensitivity": row["aggregate_sensitivity"],
                    "cosine_with_gamma_sub": row["cosine_with_gamma_sub"],
                }
            )


def run_confounding_audit(
    *,
    target_path: Path = DEFAULT_TARGET,
    summary_path: Path = DEFAULT_SUMMARY,
    ranking_path: Path = DEFAULT_RANKING,
    nx: int | None = None,
    nt: int | None = None,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
    method: str = "Radau",
) -> dict[str, Any]:
    target = _load_target(target_path)
    base_params = dict(target["params"])
    nx = int(nx or len(target["x"]))
    nt = int(nt or len(target["t"]))
    t_max = float(target["t"][-1])

    base_gt = _run_with_params(base_params, nx=nx, nt=nt, t_max=t_max, rtol=rtol, atol=atol, method=method)
    base_metrics = _metrics(base_gt)
    model_time = np.asarray(base_gt["t"], dtype=float)
    target_g = target_series_at(target, "G", model_time)
    target_i = target_series_at(target, "I", model_time)

    parameter_values = _parameter_values(base_params)
    rows: list[dict[str, Any]] = []
    signed_vectors: dict[str, list[float]] = {}
    perturbation_runs: dict[str, Any] = {}
    for parameter, values in parameter_values.items():
        low_params = _apply_value(base_params, parameter, values["low"])
        high_params = _apply_value(base_params, parameter, values["high"])
        low_gt = _run_with_params(low_params, nx=nx, nt=nt, t_max=t_max, rtol=rtol, atol=atol, method=method)
        high_gt = _run_with_params(high_params, nx=nx, nt=nt, t_max=t_max, rtol=rtol, atol=atol, method=method)
        low_metrics = _metrics(low_gt)
        high_metrics = _metrics(high_gt)
        rel_step = _relative_parameter_step(values)

        g_sens = _relative_rmse(high_metrics["G"], low_metrics["G"]) / max(2.0 * rel_step, 1.0e-30)
        i_sens = _relative_rmse(high_metrics["I"], low_metrics["I"]) / max(2.0 * rel_step, 1.0e-30)
        max_t_sens = abs(
            _signed_sensitivity(high_metrics["max_delta_T"], low_metrics["max_delta_T"], base_metrics["max_delta_T"], rel_step)
        )
        mean_t_sens = abs(
            _signed_sensitivity(
                high_metrics["mean_delta_T_peak"],
                low_metrics["mean_delta_T_peak"],
                base_metrics["mean_delta_T_peak"],
                rel_step,
            )
        )
        signed_vector = [
            _signed_sensitivity(high_metrics["G_mean"], low_metrics["G_mean"], base_metrics["G_mean"], rel_step),
            _signed_sensitivity(high_metrics["I_rms"], low_metrics["I_rms"], base_metrics["I_rms"], rel_step),
            _signed_sensitivity(high_metrics["max_delta_T"], low_metrics["max_delta_T"], base_metrics["max_delta_T"], rel_step),
            _signed_sensitivity(
                high_metrics["mean_delta_T_peak"],
                low_metrics["mean_delta_T_peak"],
                base_metrics["mean_delta_T_peak"],
                rel_step,
            ),
        ]
        signed_vectors[parameter] = signed_vector
        rows.append(
            {
                "parameter": parameter,
                "relative_step": rel_step,
                "low_value": values["low"],
                "base_value": values["base"],
                "high_value": values["high"],
                "G_t_sensitivity": float(g_sens),
                "I_t_sensitivity": float(i_sens),
                "max_delta_T_sensitivity": float(max_t_sens),
                "mean_delta_T_sensitivity": float(mean_t_sens),
                "aggregate_sensitivity": float(np.sqrt(np.mean(np.square([g_sens, i_sens, max_t_sens, mean_t_sens])))),
                "signed_response_vector": signed_vector,
                "low_relative_rmse_G_vs_target": _relative_rmse(np.asarray(low_gt["G"], dtype=float), target_g),
                "high_relative_rmse_G_vs_target": _relative_rmse(np.asarray(high_gt["G"], dtype=float), target_g),
                "low_relative_rmse_I_vs_target": _relative_rmse(np.asarray(low_gt["I"], dtype=float), target_i),
                "high_relative_rmse_I_vs_target": _relative_rmse(np.asarray(high_gt["I"], dtype=float), target_i),
            }
        )
        perturbation_runs[parameter] = {
            "low_value": values["low"],
            "high_value": values["high"],
            "low_max_delta_T": low_metrics["max_delta_T"],
            "high_max_delta_T": high_metrics["max_delta_T"],
            "low_G_mean": low_metrics["G_mean"],
            "high_G_mean": high_metrics["G_mean"],
        }

    gamma_vector = signed_vectors["gamma_sub"]
    for row in rows:
        row["cosine_with_gamma_sub"] = _cosine(gamma_vector, signed_vectors[row["parameter"]])

    ranked = sorted(rows, key=lambda row: float(row["aggregate_sensitivity"]), reverse=True)
    confounding_rank = sorted(
        [
            row
            for row in rows
            if row["parameter"] != "gamma_sub" and row["cosine_with_gamma_sub"] is not None
        ],
        key=lambda row: abs(float(row["cosine_with_gamma_sub"])),
        reverse=True,
    )

    summary = {
        "benchmark": "Frozen Ground Truth v1.1 triangle synthetic numerical digital-twin benchmark.",
        "target_path": str(target_path),
        "nx": nx,
        "nt": nt,
        "baseline_relative_rmse_G_vs_target": _relative_rmse(np.asarray(base_gt["G"], dtype=float), target_g),
        "baseline_relative_rmse_I_vs_target": _relative_rmse(np.asarray(base_gt["I"], dtype=float), target_i),
        "parameter_values": parameter_values,
        "sensitivity_rows": rows,
        "sensitivity_ranking": [
            {
                "rank": idx,
                "parameter": row["parameter"],
                "aggregate_sensitivity": row["aggregate_sensitivity"],
                "cosine_with_gamma_sub": row["cosine_with_gamma_sub"],
            }
            for idx, row in enumerate(ranked, start=1)
        ],
        "confounding_ranking": [
            {
                "rank": idx,
                "parameter": row["parameter"],
                "cosine_with_gamma_sub": row["cosine_with_gamma_sub"],
                "aggregate_sensitivity": row["aggregate_sensitivity"],
            }
            for idx, row in enumerate(confounding_rank, start=1)
        ],
        "perturbation_runs": perturbation_runs,
        "interpretation": {
            "most_sensitive_parameter": ranked[0]["parameter"],
            "closest_gamma_sub_confounder": confounding_rank[0]["parameter"] if confounding_rank else None,
            "gamma_sub_rank_by_aggregate_sensitivity": next(
                idx for idx, row in enumerate(ranked, start=1) if row["parameter"] == "gamma_sub"
            ),
        },
        "outputs": {
            "summary_json": str(summary_path),
            "sensitivity_ranking_csv": str(ranking_path),
        },
        "note": "Synthetic numerical digital-twin confounding audit, not experimental data.",
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_ranking(ranking_path, ranked)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--ranking", type=Path, default=DEFAULT_RANKING)
    parser.add_argument("--nx", type=int, default=None)
    parser.add_argument("--nt", type=int, default=None)
    parser.add_argument("--rtol", type=float, default=1.0e-6)
    parser.add_argument("--atol", type=float, default=1.0e-8)
    parser.add_argument("--method", type=str, default="Radau")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_confounding_audit(
        target_path=args.target,
        summary_path=args.summary,
        ranking_path=args.ranking,
        nx=args.nx,
        nt=args.nt,
        rtol=args.rtol,
        atol=args.atol,
        method=args.method,
    )
    print(json.dumps(summary["outputs"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

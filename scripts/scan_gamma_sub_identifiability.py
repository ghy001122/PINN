"""Scan gamma_sub sensitivity for the frozen synthetic triangle benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.gt_solver import simulate_ground_truth


DEFAULT_TARGET = Path("data/processed/gt_v1_acceptance/gt_triangle.npz")
DEFAULT_SUMMARY = Path("outputs/tables/gamma_sub_identifiability_summary.json")
DEFAULT_FIGURE_DIR = Path("outputs/figures/gamma_sub_identifiability")
DEFAULT_GAMMAS = (2.5e8, 3.25e8, 4.0e8, 4.5e8, 5.5e8, 7.0e8, 9.0e8)


def _parse_float_list(text: str) -> list[float]:
    values = [float(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one float value.")
    return values


def _load_target(path: Path) -> dict[str, Any]:
    with np.load(path) as data:
        params_json = json.loads(str(data["params_json"]))
        return {
            "path": str(path),
            "keys": list(data.files),
            "x": data["x"].astype(float),
            "t": data["t"].astype(float),
            "V": data["V"].astype(float),
            "I": data["I"].astype(float),
            "G": data["G"].astype(float),
            "T": data["T"].astype(float),
            "params": params_json,
        }


def _relative_rmse(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = max(float(np.sqrt(np.mean(b**2))), 1.0e-30)
    return float(np.sqrt(np.mean((a - b) ** 2)) / denom)


def target_series_at(target: dict[str, Any], key: str, time: np.ndarray) -> np.ndarray:
    """Interpolate a frozen target time series onto a model time grid."""

    return np.interp(np.asarray(time, dtype=float), target["t"], target[key])


def target_mean_delta_t_at(target: dict[str, Any], time: np.ndarray) -> np.ndarray:
    target_mean_delta_t = np.mean(target["T"] - float(target["params"]["T0"]), axis=1)
    return np.interp(np.asarray(time, dtype=float), target["t"], target_mean_delta_t)


def _loop_area(voltage: np.ndarray, current: np.ndarray) -> float:
    return float(abs(np.trapz(current, voltage)))


def simulate_for_gamma(
    gamma_sub: float,
    base_params: dict[str, Any],
    *,
    nx: int,
    nt: int,
    protocol: str = "triangle",
    t_max: float | None = None,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
    method: str = "Radau",
) -> dict[str, Any]:
    params = dict(base_params)
    params["gamma_sub"] = float(gamma_sub)
    return simulate_ground_truth(
        protocol=protocol,
        params=params,
        nx=nx,
        nt=nt,
        t_max=t_max,
        rtol=rtol,
        atol=atol,
        method=method,
    )


def _summarize_run(
    gamma_sub: float,
    gt: dict[str, Any],
    target: dict[str, Any],
    trajectory_indices: np.ndarray,
) -> dict[str, Any]:
    temperature = np.asarray(gt["T"], dtype=float)
    delta_t = temperature - float(target["params"]["T0"])
    mean_delta_t = np.mean(delta_t, axis=1)
    max_delta_t = np.max(delta_t, axis=1)
    voltage = np.asarray(gt["V"], dtype=float)
    current = np.asarray(gt["I"], dtype=float)
    conductance = np.asarray(gt["G"], dtype=float)
    time = np.asarray(gt["t"], dtype=float)
    target_g = target_series_at(target, "G", time)
    target_i = target_series_at(target, "I", time)
    target_mean_delta_t = target_mean_delta_t_at(target, time)

    return {
        "gamma_sub": float(gamma_sub),
        "G_min": float(np.min(conductance)),
        "G_max": float(np.max(conductance)),
        "G_mean": float(np.mean(conductance)),
        "I_min": float(np.min(current)),
        "I_max": float(np.max(current)),
        "I_rms": float(np.sqrt(np.mean(current**2))),
        "max_delta_T": float(np.max(max_delta_t)),
        "mean_delta_T_peak": float(np.max(mean_delta_t)),
        "iv_loop_area": _loop_area(voltage, current),
        "relative_rmse_G_vs_target": _relative_rmse(conductance, target_g),
        "relative_rmse_I_vs_target": _relative_rmse(current, target_i),
        "relative_rmse_mean_delta_T_vs_target": _relative_rmse(
            mean_delta_t,
            target_mean_delta_t,
        ),
        "trajectories": {
            "G": conductance[trajectory_indices].tolist(),
            "I": current[trajectory_indices].tolist(),
            "mean_delta_T": mean_delta_t[trajectory_indices].tolist(),
            "max_delta_T": max_delta_t[trajectory_indices].tolist(),
        },
    }


def _local_log_sensitivities(rows: list[dict[str, Any]], target_gamma: float) -> dict[str, float | None]:
    gammas = np.array([row["gamma_sub"] for row in rows], dtype=float)
    below = np.where(gammas < target_gamma)[0]
    above = np.where(gammas > target_gamma)[0]
    if below.size == 0 or above.size == 0:
        return {}
    lo = int(below[-1])
    hi = int(above[0])
    denom = float(np.log(gammas[hi]) - np.log(gammas[lo]))
    out: dict[str, float | None] = {}
    for key in ["G_mean", "I_rms", "max_delta_T", "mean_delta_T_peak", "iv_loop_area"]:
        y_lo = max(float(rows[lo][key]), 1.0e-300)
        y_hi = max(float(rows[hi][key]), 1.0e-300)
        out[key] = float((np.log(y_hi) - np.log(y_lo)) / denom)
    return out


def _plot_scan(summary: dict[str, Any], figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    rows = summary["scan"]
    t_ms = np.asarray(summary["trajectory_time_s"], dtype=float) * 1.0e3
    gammas = np.array([row["gamma_sub"] for row in rows], dtype=float)

    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for row in rows:
        label = f"{row['gamma_sub']:.2e}"
        axes[0].plot(t_ms, row["trajectories"]["G"], linewidth=1.1, label=label)
        axes[1].plot(t_ms, row["trajectories"]["mean_delta_T"], linewidth=1.1, label=label)
    axes[0].set_ylabel("G (S)")
    axes[1].set_ylabel("mean delta_T (K)")
    axes[1].set_xlabel("time (ms)")
    axes[0].set_title("gamma_sub scan responses")
    axes[0].legend(title="gamma_sub", fontsize=7, ncols=2)
    fig.tight_layout()
    fig.savefig(figure_dir / "gamma_sub_scan_responses.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(gammas, [row["relative_rmse_G_vs_target"] for row in rows], marker="o", label="G")
    ax.plot(gammas, [row["relative_rmse_I_vs_target"] for row in rows], marker="o", label="I")
    ax.plot(
        gammas,
        [row["relative_rmse_mean_delta_T_vs_target"] for row in rows],
        marker="o",
        label="mean delta_T",
    )
    ax.axvline(summary["target_gamma_sub"], color="black", linestyle="--", linewidth=1.0)
    ax.set_xscale("log")
    ax.set_xlabel("gamma_sub (W m^-3 K^-1)")
    ax.set_ylabel("relative RMSE vs frozen target")
    ax.set_title("Sensitivity to gamma_sub")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "gamma_sub_sensitivity.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(gammas, [row["max_delta_T"] for row in rows], marker="o", label="max delta_T")
    ax.plot(gammas, [row["mean_delta_T_peak"] for row in rows], marker="o", label="peak mean delta_T")
    ax.axvline(summary["target_gamma_sub"], color="black", linestyle="--", linewidth=1.0)
    ax.set_xscale("log")
    ax.set_xlabel("gamma_sub (W m^-3 K^-1)")
    ax.set_ylabel("temperature rise (K)")
    ax.set_title("Thermal response versus gamma_sub")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "gamma_sub_temperature_response.png", dpi=200)
    plt.close(fig)


def run_scan(
    *,
    target_path: Path = DEFAULT_TARGET,
    summary_path: Path = DEFAULT_SUMMARY,
    figure_dir: Path = DEFAULT_FIGURE_DIR,
    gamma_values: list[float] | None = None,
    nx: int | None = None,
    nt: int | None = None,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
    method: str = "Radau",
) -> dict[str, Any]:
    target = _load_target(target_path)
    gamma_values = sorted(gamma_values or list(DEFAULT_GAMMAS))
    nx = int(nx or len(target["x"]))
    nt = int(nt or len(target["t"]))
    base_params = dict(target["params"])
    target_gamma = float(base_params["gamma_sub"])

    rows = []
    trajectory_indices = np.unique(np.linspace(0, nt - 1, min(nt, 120), dtype=int))
    model_time = np.linspace(0.0, float(target["t"][-1]), nt)
    for gamma_sub in gamma_values:
        gt = simulate_for_gamma(
            gamma_sub,
            base_params,
            nx=nx,
            nt=nt,
            protocol="triangle",
            t_max=float(target["t"][-1]),
            rtol=rtol,
            atol=atol,
            method=method,
        )
        rows.append(_summarize_run(gamma_sub, gt, target, trajectory_indices))

    summary = {
        "benchmark": "Frozen Ground Truth v1.1 triangle synthetic numerical digital-twin benchmark.",
        "target_path": str(target_path),
        "target_gamma_sub": target_gamma,
        "fixed_parameters": {
            key: float(base_params[key])
            for key in ["D_v0", "mu_v0", "T_sw", "tau_m", "gamma_sub"]
            if key in base_params
        },
        "nx": nx,
        "nt": nt,
        "trajectory_time_s": model_time[trajectory_indices].tolist(),
        "trajectory_stride_note": "Trajectories are downsampled for lightweight committed evidence; scalar metrics use full resolution.",
        "scan": rows,
        "local_log_sensitivity": _local_log_sensitivities(rows, target_gamma),
        "outputs": {
            "summary_json": str(summary_path),
            "figure_dir": str(figure_dir),
            "scan_responses": str(figure_dir / "gamma_sub_scan_responses.png"),
            "sensitivity": str(figure_dir / "gamma_sub_sensitivity.png"),
            "temperature_response": str(figure_dir / "gamma_sub_temperature_response.png"),
        },
        "note": "Synthetic numerical digital-twin parameter-identifiability scan, not experimental data.",
    }

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _plot_scan(summary, figure_dir)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--gamma-values", type=str, default=",".join(f"{v:.8e}" for v in DEFAULT_GAMMAS))
    parser.add_argument("--nx", type=int, default=None)
    parser.add_argument("--nt", type=int, default=None)
    parser.add_argument("--rtol", type=float, default=1.0e-6)
    parser.add_argument("--atol", type=float, default=1.0e-8)
    parser.add_argument("--method", type=str, default="Radau")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_scan(
        target_path=args.target,
        summary_path=args.summary,
        figure_dir=args.figure_dir,
        gamma_values=_parse_float_list(args.gamma_values),
        nx=args.nx,
        nt=args.nt,
        rtol=args.rtol,
        atol=args.atol,
        method=args.method,
    )
    print(json.dumps(summary["outputs"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

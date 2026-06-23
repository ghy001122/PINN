"""Invert only gamma_sub against frozen synthetic terminal observations."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pinnpcm.physics.params import spatial_param_profiles

try:  # Support both script execution and pytest import.
    from scripts.scan_gamma_sub_identifiability import (
        DEFAULT_FIGURE_DIR,
        DEFAULT_SUMMARY,
        DEFAULT_TARGET,
        _load_target,
        _parse_float_list,
        _relative_rmse,
        run_scan,
        simulate_for_gamma,
        target_series_at,
    )
except ModuleNotFoundError:  # pragma: no cover - script-dir fallback.
    from scan_gamma_sub_identifiability import (  # type: ignore
        DEFAULT_FIGURE_DIR,
        DEFAULT_SUMMARY,
        DEFAULT_TARGET,
        _load_target,
        _parse_float_list,
        _relative_rmse,
        run_scan,
        simulate_for_gamma,
        target_series_at,
    )


DEFAULT_INITIAL_GAMMAS = (2.0e8, 4.5e8, 9.0e8)
DEFAULT_NOISE_LEVELS = (0.0, 0.02, 0.05)


def _parse_bounds(text: str) -> tuple[float, float]:
    values = _parse_float_list(text)
    if len(values) != 2:
        raise ValueError("--gamma-bounds expects exactly two comma-separated values.")
    lo, hi = min(values), max(values)
    if lo <= 0.0:
        raise ValueError("gamma_sub bounds must be positive.")
    return lo, hi


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(values, dtype=float) ** 2)))


def _heat_residual_loss(gt: dict[str, Any], params: dict[str, Any], gamma_sub: float) -> float:
    """Return a normalized finite-volume heat-equation consistency residual.

    This is an internal numerical residual on the candidate simulation. It is
    not hidden-temperature supervision from the target data.
    """

    temperature = np.asarray(gt["T"], dtype=float)
    time = np.asarray(gt["t"], dtype=float)
    x = np.asarray(gt["x"], dtype=float)
    electric_field = np.asarray(gt["E"], dtype=float)
    current = np.asarray(gt["I"], dtype=float)

    if len(time) < 3:
        edge_order = 1
    else:
        edge_order = 2
    dtemp_dt = np.gradient(temperature, time, axis=0, edge_order=edge_order)
    dx = float(params["L_eff"]) / len(x)
    profiles = spatial_param_profiles(x, {**params, "gamma_sub": gamma_sub})
    k_th = np.asarray(profiles["k_th"], dtype=float)

    heat_flux = np.zeros((temperature.shape[0], temperature.shape[1] + 1), dtype=float)
    dtemp_dx = (temperature[:, 1:] - temperature[:, :-1]) / dx
    k_faces = 0.5 * (k_th[:-1] + k_th[1:])
    heat_flux[:, 1:-1] = -k_faces[None, :] * dtemp_dx
    conduction = -(heat_flux[:, 1:] - heat_flux[:, :-1]) / dx

    active_area = float(params["eta_A"]) * float(params["A_contact"])
    current_density = current / max(active_area, 1.0e-30)
    joule = current_density[:, None] * electric_field
    cooling = gamma_sub * (temperature - float(params["T0"]))
    storage = float(params["rho"]) * float(params["Cp"]) * dtemp_dt
    residual = storage - (conduction + joule - cooling)
    scale = _rms(storage) + _rms(conduction) + _rms(joule) + _rms(cooling) + 1.0e-30
    return float((_rms(residual) / scale) ** 2)


class GammaObjective:
    def __init__(
        self,
        target: dict[str, Any],
        target_g: np.ndarray,
        target_i: np.ndarray,
        *,
        nx: int,
        nt: int,
        gamma_bounds: tuple[float, float],
        rtol: float,
        atol: float,
        method: str,
        w_g: float,
        w_i: float,
        w_heat: float,
    ) -> None:
        self.target = target
        self.target_g = target_g
        self.target_i = target_i
        self.nx = nx
        self.nt = nt
        self.gamma_bounds = gamma_bounds
        self.rtol = rtol
        self.atol = atol
        self.method = method
        self.w_g = w_g
        self.w_i = w_i
        self.w_heat = w_heat
        self.cache: dict[float, dict[str, Any]] = {}

    def evaluate(self, theta: float) -> dict[str, Any]:
        lo, hi = self.gamma_bounds
        theta = float(np.clip(theta, math.log(lo), math.log(hi)))
        key = round(theta, 9)
        if key in self.cache:
            return self.cache[key]

        gamma_sub = float(math.exp(theta))
        gt = simulate_for_gamma(
            gamma_sub,
            self.target["params"],
            nx=self.nx,
            nt=self.nt,
            protocol="triangle",
            t_max=float(self.target["t"][-1]),
            rtol=self.rtol,
            atol=self.atol,
            method=self.method,
        )
        pred_g = np.asarray(gt["G"], dtype=float)
        pred_i = np.asarray(gt["I"], dtype=float)
        loss_g = _relative_rmse(pred_g, self.target_g) ** 2
        loss_i = _relative_rmse(pred_i, self.target_i) ** 2
        heat_loss = _heat_residual_loss(gt, self.target["params"], gamma_sub)
        total = self.w_g * loss_g + self.w_i * loss_i + self.w_heat * heat_loss
        value = {
            "theta": theta,
            "gamma_sub": gamma_sub,
            "total_loss": float(total),
            "G_loss": float(loss_g),
            "I_loss": float(loss_i),
            "heat_residual_loss": float(heat_loss),
        }
        self.cache[key] = value
        return value

    def loss(self, theta_array: np.ndarray) -> float:
        return float(self.evaluate(float(theta_array[0]))["total_loss"])

    def grad(self, theta: float, eps: float = 1.0e-3) -> float:
        lo, hi = (math.log(self.gamma_bounds[0]), math.log(self.gamma_bounds[1]))
        left = max(theta - eps, lo)
        right = min(theta + eps, hi)
        if right == left:
            return 0.0
        return float((self.evaluate(right)["total_loss"] - self.evaluate(left)["total_loss"]) / (right - left))


def _adam_coarse(
    objective: GammaObjective,
    initial_gamma: float,
    *,
    steps: int,
    lr: float,
) -> tuple[float, list[dict[str, float]]]:
    lo, hi = objective.gamma_bounds
    theta = float(np.clip(math.log(initial_gamma), math.log(lo), math.log(hi)))
    m = 0.0
    v = 0.0
    beta1 = 0.9
    beta2 = 0.999
    trace: list[dict[str, float]] = []
    for step in range(1, steps + 1):
        grad = objective.grad(theta)
        m = beta1 * m + (1.0 - beta1) * grad
        v = beta2 * v + (1.0 - beta2) * grad * grad
        m_hat = m / (1.0 - beta1**step)
        v_hat = v / (1.0 - beta2**step)
        theta = theta - lr * m_hat / (math.sqrt(v_hat) + 1.0e-8)
        theta = float(np.clip(theta, math.log(lo), math.log(hi)))
        state = objective.evaluate(theta)
        if step == 1 or step == steps or step % max(1, steps // 4) == 0:
            trace.append(
                {
                    "step": float(step),
                    "gamma_sub": float(state["gamma_sub"]),
                    "total_loss": float(state["total_loss"]),
                    "gradient": float(grad),
                }
            )
    return theta, trace


def _make_noisy_target(
    target: dict[str, Any],
    noise_level: float,
    seed: int,
    time: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    g_clean = target_series_at(target, "G", time)
    i_clean = target_series_at(target, "I", time)
    g_scale = max(float(np.max(np.abs(g_clean))), 1.0e-30)
    i_scale = max(float(np.max(np.abs(i_clean))), 1.0e-30)
    return (
        g_clean + noise_level * g_scale * rng.standard_normal(g_clean.shape),
        i_clean + noise_level * i_scale * rng.standard_normal(i_clean.shape),
    )


def _plot_inversion(summary: dict[str, Any], figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    target_gamma = float(summary["target_gamma_sub"])

    fig, ax = plt.subplots(figsize=(7, 5))
    for noise_case in summary["inversion"]["noise_cases"]:
        noise = noise_case["noise_level"]
        xs = [noise] * len(noise_case["runs"])
        ys = [run["estimated_gamma_sub"] for run in noise_case["runs"]]
        ax.scatter(xs, ys, label=f"noise={noise:g}")
    ax.axhline(target_gamma, color="black", linestyle="--", linewidth=1.0, label="target")
    ax.set_xlabel("relative noise level")
    ax.set_ylabel("estimated gamma_sub")
    ax.set_title("Multi-start gamma_sub inversion")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figure_dir / "gamma_sub_inversion_multistart.png", dpi=200)
    plt.close(fig)

    profile = summary["inversion"]["objective_profile_clean"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(profile["gamma_sub"], profile["total_loss"], marker="o")
    ax.axvline(target_gamma, color="black", linestyle="--", linewidth=1.0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("gamma_sub")
    ax.set_ylabel("total loss")
    ax.set_title("Clean objective profile")
    fig.tight_layout()
    fig.savefig(figure_dir / "gamma_sub_objective_profile.png", dpi=200)
    plt.close(fig)


def run_inversion(
    *,
    target_path: Path = DEFAULT_TARGET,
    summary_path: Path = DEFAULT_SUMMARY,
    figure_dir: Path = DEFAULT_FIGURE_DIR,
    initial_gammas: list[float] | None = None,
    noise_levels: list[float] | None = None,
    gamma_bounds: tuple[float, float] = (1.5e8, 1.0e9),
    nx: int | None = None,
    nt: int | None = None,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
    method: str = "Radau",
    adam_steps: int = 14,
    adam_lr: float = 0.18,
    lbfgs_maxiter: int = 10,
    seed: int = 2026,
    w_g: float = 1.0,
    w_i: float = 0.5,
    w_heat: float = 0.01,
) -> dict[str, Any]:
    target = _load_target(target_path)
    nx = int(nx or len(target["x"]))
    nt = int(nt or len(target["t"]))
    initial_gammas = initial_gammas or list(DEFAULT_INITIAL_GAMMAS)
    noise_levels = noise_levels or list(DEFAULT_NOISE_LEVELS)
    target_gamma = float(target["params"]["gamma_sub"])
    model_time = np.linspace(0.0, float(target["t"][-1]), nt)

    existing: dict[str, Any]
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        existing = run_scan(target_path=target_path, summary_path=summary_path, figure_dir=figure_dir, nx=nx, nt=nt)

    noise_cases = []
    for noise_index, noise_level in enumerate(noise_levels):
        target_g, target_i = _make_noisy_target(target, noise_level, seed + noise_index, model_time)
        objective = GammaObjective(
            target,
            target_g,
            target_i,
            nx=nx,
            nt=nt,
            gamma_bounds=gamma_bounds,
            rtol=rtol,
            atol=atol,
            method=method,
            w_g=w_g,
            w_i=w_i,
            w_heat=w_heat,
        )
        runs = []
        for initial_gamma in initial_gammas:
            theta_adam, trace = _adam_coarse(objective, initial_gamma, steps=adam_steps, lr=adam_lr)
            opt = minimize(
                objective.loss,
                x0=np.array([theta_adam], dtype=float),
                method="L-BFGS-B",
                bounds=[(math.log(gamma_bounds[0]), math.log(gamma_bounds[1]))],
                options={"maxiter": lbfgs_maxiter, "ftol": 1.0e-12},
            )
            final = objective.evaluate(float(opt.x[0]))
            runs.append(
                {
                    "initial_gamma_sub": float(initial_gamma),
                    "adam_gamma_sub": float(math.exp(theta_adam)),
                    "estimated_gamma_sub": float(final["gamma_sub"]),
                    "relative_gamma_error": float(abs(final["gamma_sub"] - target_gamma) / target_gamma),
                    "total_loss": float(final["total_loss"]),
                    "G_loss": float(final["G_loss"]),
                    "I_loss": float(final["I_loss"]),
                    "heat_residual_loss": float(final["heat_residual_loss"]),
                    "lbfgs_success": bool(opt.success),
                    "lbfgs_message": str(opt.message),
                    "adam_trace": trace,
                }
            )
        estimates = np.array([run["estimated_gamma_sub"] for run in runs], dtype=float)
        best = min(runs, key=lambda row: float(row["total_loss"]))
        noise_cases.append(
            {
                "noise_level": float(noise_level),
                "runs": runs,
                "best": best,
                "estimate_mean": float(np.mean(estimates)),
                "estimate_std": float(np.std(estimates)),
                "relative_estimate_std": float(np.std(estimates) / target_gamma),
                "mean_relative_gamma_error": float(np.mean(np.abs(estimates - target_gamma) / target_gamma)),
                "multi_start_consistent": bool(np.std(estimates) / target_gamma < 0.05),
            }
        )

    profile_gammas = np.geomspace(gamma_bounds[0], gamma_bounds[1], 21)
    clean_target_g, clean_target_i = _make_noisy_target(target, 0.0, seed, model_time)
    clean_objective = GammaObjective(
        target,
        clean_target_g,
        clean_target_i,
        nx=nx,
        nt=nt,
        gamma_bounds=gamma_bounds,
        rtol=rtol,
        atol=atol,
        method=method,
        w_g=w_g,
        w_i=w_i,
        w_heat=w_heat,
    )
    profile_losses = [clean_objective.evaluate(math.log(float(gamma)))["total_loss"] for gamma in profile_gammas]

    clean_case = next(case for case in noise_cases if case["noise_level"] == min(noise_levels))
    clean_best = clean_case["best"]
    noisy_cases = [case for case in noise_cases if case["noise_level"] > 0.0]
    max_noisy_error = max(
        [case["mean_relative_gamma_error"] for case in noisy_cases],
        default=0.0,
    )
    stable = bool(clean_best["relative_gamma_error"] < 0.02 and max_noisy_error < 0.12)

    inversion = {
        "optimizer": {
            "coarse": "manual finite-difference Adam on log(gamma_sub)",
            "fine": "scipy L-BFGS-B on log(gamma_sub)",
            "adam_steps": int(adam_steps),
            "adam_lr": float(adam_lr),
            "lbfgs_maxiter": int(lbfgs_maxiter),
            "gamma_bounds": [float(gamma_bounds[0]), float(gamma_bounds[1])],
        },
        "loss": {
            "w_g": float(w_g),
            "w_i": float(w_i),
            "w_heat": float(w_heat),
            "description": "Port G/I loss plus candidate heat-equation residual; no hidden target temperature supervision.",
        },
        "fixed_parameters": {
            key: float(target["params"][key])
            for key in ["D_v0", "mu_v0", "T_sw", "tau_m", "gamma_sub"]
            if key in target["params"]
        },
        "noise_cases": noise_cases,
        "objective_profile_clean": {
            "gamma_sub": [float(v) for v in profile_gammas],
            "total_loss": [float(v) for v in profile_losses],
        },
        "stability_summary": {
            "clean_best_gamma_sub": float(clean_best["estimated_gamma_sub"]),
            "clean_relative_gamma_error": float(clean_best["relative_gamma_error"]),
            "max_noisy_mean_relative_gamma_error": float(max_noisy_error),
            "gamma_sub_stably_invertible": stable,
        },
    }

    existing["inversion"] = inversion
    existing["outputs"] = {
        **existing.get("outputs", {}),
        "inversion_multistart": str(figure_dir / "gamma_sub_inversion_multistart.png"),
        "objective_profile": str(figure_dir / "gamma_sub_objective_profile.png"),
    }
    existing["note"] = "Synthetic numerical digital-twin gamma_sub identifiability audit, not experimental data."
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    _plot_inversion(existing, figure_dir)
    return existing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--figure-dir", type=Path, default=DEFAULT_FIGURE_DIR)
    parser.add_argument("--initial-gammas", type=str, default=",".join(f"{v:.8e}" for v in DEFAULT_INITIAL_GAMMAS))
    parser.add_argument("--noise-levels", type=str, default=",".join(f"{v:g}" for v in DEFAULT_NOISE_LEVELS))
    parser.add_argument("--gamma-bounds", type=str, default="1.5e8,1.0e9")
    parser.add_argument("--nx", type=int, default=None)
    parser.add_argument("--nt", type=int, default=None)
    parser.add_argument("--rtol", type=float, default=1.0e-6)
    parser.add_argument("--atol", type=float, default=1.0e-8)
    parser.add_argument("--method", type=str, default="Radau")
    parser.add_argument("--adam-steps", type=int, default=14)
    parser.add_argument("--adam-lr", type=float, default=0.18)
    parser.add_argument("--lbfgs-maxiter", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--w-g", type=float, default=1.0)
    parser.add_argument("--w-i", type=float, default=0.5)
    parser.add_argument("--w-heat", type=float, default=0.01)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_inversion(
        target_path=args.target,
        summary_path=args.summary,
        figure_dir=args.figure_dir,
        initial_gammas=_parse_float_list(args.initial_gammas),
        noise_levels=_parse_float_list(args.noise_levels),
        gamma_bounds=_parse_bounds(args.gamma_bounds),
        nx=args.nx,
        nt=args.nt,
        rtol=args.rtol,
        atol=args.atol,
        method=args.method,
        adam_steps=args.adam_steps,
        adam_lr=args.adam_lr,
        lbfgs_maxiter=args.lbfgs_maxiter,
        seed=args.seed,
        w_g=args.w_g,
        w_i=args.w_i,
        w_heat=args.w_heat,
    )
    print(json.dumps(summary["inversion"]["stability_summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

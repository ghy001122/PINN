"""Invert gamma_sub when the synthetic target contains parameter mismatch."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.audit_gamma_sub_confounding import DEFAULT_SUMMARY
    from scripts.invert_gamma_sub_v0 import GammaObjective, _adam_coarse, _make_noisy_target, _parse_bounds
    from scripts.scan_gamma_sub_identifiability import DEFAULT_TARGET, _load_target, _parse_float_list, simulate_for_gamma
except ModuleNotFoundError:  # pragma: no cover - script-dir fallback.
    from audit_gamma_sub_confounding import DEFAULT_SUMMARY  # type: ignore
    from invert_gamma_sub_v0 import GammaObjective, _adam_coarse, _make_noisy_target, _parse_bounds  # type: ignore
    from scan_gamma_sub_identifiability import DEFAULT_TARGET, _load_target, _parse_float_list, simulate_for_gamma  # type: ignore


DEFAULT_NOISE_LEVELS = (0.0, 0.02, 0.05)


def _mismatch_cases(base_params: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": "nominal", "overrides": {}},
        {"name": "T_sw_plus_2K", "overrides": {"T_sw": float(base_params["T_sw"]) + 2.0}},
        {"name": "tau_m_x1p5", "overrides": {"tau_m": float(base_params["tau_m"]) * 1.5}},
        {"name": "sigma_on0_x1p15", "overrides": {"sigma_on0": float(base_params["sigma_on0"]) * 1.15}},
        {"name": "eta_A_x1p15", "overrides": {"eta_A": float(base_params["eta_A"]) * 1.15}},
    ]


def _apply_mismatch(base_params: dict[str, Any], overrides: dict[str, float]) -> dict[str, Any]:
    params = dict(base_params)
    for key, value in overrides.items():
        params[key] = float(value)
        if key == "sigma_on0":
            ratio = float(value) / float(base_params["sigma_on0"])
            for layer_key in ("nb_oxide_sigma_on0", "v2o5_sigma_on0"):
                if layer_key in params:
                    params[layer_key] = float(base_params[layer_key]) * ratio
    return params


def _target_from_gt(gt: dict[str, Any], nominal_params: dict[str, Any], name: str, overrides: dict[str, float]) -> dict[str, Any]:
    return {
        "path": f"synthetic_mismatch:{name}",
        "keys": ["x", "t", "V", "I", "G", "T", "params_json"],
        "x": np.asarray(gt["x"], dtype=float),
        "t": np.asarray(gt["t"], dtype=float),
        "V": np.asarray(gt["V"], dtype=float),
        "I": np.asarray(gt["I"], dtype=float),
        "G": np.asarray(gt["G"], dtype=float),
        "T": np.asarray(gt["T"], dtype=float),
        "params": dict(nominal_params),
        "target_overrides": overrides,
    }


def _estimate_gamma_for_target(
    target: dict[str, Any],
    *,
    target_gamma: float,
    noise_level: float,
    initial_gamma: float,
    nx: int,
    nt: int,
    gamma_bounds: tuple[float, float],
    rtol: float,
    atol: float,
    method: str,
    adam_steps: int,
    adam_lr: float,
    lbfgs_maxiter: int,
    seed: int,
    w_g: float,
    w_i: float,
    w_heat: float,
) -> dict[str, Any]:
    model_time = np.linspace(0.0, float(target["t"][-1]), nt)
    target_g, target_i = _make_noisy_target(target, noise_level, seed, model_time)
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
    theta_adam, trace = _adam_coarse(objective, initial_gamma, steps=adam_steps, lr=adam_lr)
    opt = minimize(
        objective.loss,
        x0=np.array([theta_adam], dtype=float),
        method="L-BFGS-B",
        bounds=[(math.log(gamma_bounds[0]), math.log(gamma_bounds[1]))],
        options={"maxiter": lbfgs_maxiter, "ftol": 1.0e-12},
    )
    final = objective.evaluate(float(opt.x[0]))
    return {
        "noise_level": float(noise_level),
        "initial_gamma_sub": float(initial_gamma),
        "adam_gamma_sub": float(math.exp(theta_adam)),
        "estimated_gamma_sub": float(final["gamma_sub"]),
        "relative_gamma_bias": float((final["gamma_sub"] - target_gamma) / target_gamma),
        "absolute_relative_gamma_error": float(abs(final["gamma_sub"] - target_gamma) / target_gamma),
        "total_loss": float(final["total_loss"]),
        "G_loss": float(final["G_loss"]),
        "I_loss": float(final["I_loss"]),
        "heat_residual_loss": float(final["heat_residual_loss"]),
        "lbfgs_success": bool(opt.success),
        "lbfgs_message": str(opt.message),
        "adam_trace": trace,
    }


def run_mismatch_inversion(
    *,
    target_path: Path = DEFAULT_TARGET,
    summary_path: Path = DEFAULT_SUMMARY,
    noise_levels: list[float] | None = None,
    initial_gamma: float | None = None,
    gamma_bounds: tuple[float, float] = (1.5e8, 1.0e9),
    nx: int | None = None,
    nt: int | None = None,
    rtol: float = 1.0e-6,
    atol: float = 1.0e-8,
    method: str = "Radau",
    adam_steps: int = 10,
    adam_lr: float = 0.18,
    lbfgs_maxiter: int = 8,
    seed: int = 2026,
    w_g: float = 1.0,
    w_i: float = 0.5,
    w_heat: float = 0.01,
) -> dict[str, Any]:
    frozen = _load_target(target_path)
    nominal_params = dict(frozen["params"])
    target_gamma = float(nominal_params["gamma_sub"])
    initial_gamma = float(initial_gamma or target_gamma)
    noise_levels = noise_levels or list(DEFAULT_NOISE_LEVELS)
    nx = int(nx or len(frozen["x"]))
    nt = int(nt or len(frozen["t"]))
    t_max = float(frozen["t"][-1])

    existing: dict[str, Any] = {}
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))

    cases = []
    for case_index, case in enumerate(_mismatch_cases(nominal_params)):
        target_params = _apply_mismatch(nominal_params, case["overrides"])
        target_gt = simulate_for_gamma(
            target_gamma,
            target_params,
            nx=nx,
            nt=nt,
            protocol="triangle",
            t_max=t_max,
            rtol=rtol,
            atol=atol,
            method=method,
        )
        target = _target_from_gt(target_gt, nominal_params, case["name"], case["overrides"])
        results = []
        for noise_index, noise_level in enumerate(noise_levels):
            result = _estimate_gamma_for_target(
                target,
                target_gamma=target_gamma,
                noise_level=noise_level,
                initial_gamma=initial_gamma,
                nx=nx,
                nt=nt,
                gamma_bounds=gamma_bounds,
                rtol=rtol,
                atol=atol,
                method=method,
                adam_steps=adam_steps,
                adam_lr=adam_lr,
                lbfgs_maxiter=lbfgs_maxiter,
                seed=seed + 100 * case_index + noise_index,
                w_g=w_g,
                w_i=w_i,
                w_heat=w_heat,
            )
            results.append(result)
        clean = next(row for row in results if row["noise_level"] == min(noise_levels))
        noisy = [row for row in results if row["noise_level"] > 0.0]
        cases.append(
            {
                "name": case["name"],
                "target_overrides": case["overrides"],
                "results": results,
                "clean_relative_gamma_bias": clean["relative_gamma_bias"],
                "clean_absolute_relative_gamma_error": clean["absolute_relative_gamma_error"],
                "max_noisy_absolute_relative_gamma_error": max(
                    [row["absolute_relative_gamma_error"] for row in noisy],
                    default=clean["absolute_relative_gamma_error"],
                ),
            }
        )

    non_nominal = [case for case in cases if case["name"] != "nominal"]
    worst_case = max(non_nominal, key=lambda row: abs(float(row["clean_relative_gamma_bias"])))
    reliability = bool(
        abs(float(worst_case["clean_relative_gamma_bias"])) < 0.15
        and max(float(case["max_noisy_absolute_relative_gamma_error"]) for case in non_nominal) < 0.2
    )

    mismatch = {
        "target_path": str(target_path),
        "nominal_gamma_sub": target_gamma,
        "fixed_model_parameters": {
            key: float(nominal_params[key])
            for key in ["D_v0", "mu_v0", "T_sw", "tau_m", "sigma_on0", "eta_A", "gamma_sub"]
            if key in nominal_params
        },
        "optimizer": {
            "coarse": "manual finite-difference Adam on log(gamma_sub)",
            "fine": "scipy L-BFGS-B on log(gamma_sub)",
            "adam_steps": int(adam_steps),
            "lbfgs_maxiter": int(lbfgs_maxiter),
            "gamma_bounds": [float(gamma_bounds[0]), float(gamma_bounds[1])],
        },
        "noise_levels": [float(value) for value in noise_levels],
        "cases": cases,
        "summary": {
            "worst_clean_bias_case": worst_case["name"],
            "worst_clean_relative_bias": float(worst_case["clean_relative_gamma_bias"]),
            "gamma_sub_reliable_under_tested_mismatch": reliability,
        },
    }
    existing["mismatch_inversion"] = mismatch
    existing["outputs"] = {
        **existing.get("outputs", {}),
        "summary_json": str(summary_path),
    }
    existing["note"] = "Synthetic numerical digital-twin gamma_sub confounding and mismatch audit, not experimental data."
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    return existing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--noise-levels", type=str, default=",".join(f"{value:g}" for value in DEFAULT_NOISE_LEVELS))
    parser.add_argument("--initial-gamma", type=float, default=None)
    parser.add_argument("--gamma-bounds", type=str, default="1.5e8,1.0e9")
    parser.add_argument("--nx", type=int, default=None)
    parser.add_argument("--nt", type=int, default=None)
    parser.add_argument("--rtol", type=float, default=1.0e-6)
    parser.add_argument("--atol", type=float, default=1.0e-8)
    parser.add_argument("--method", type=str, default="Radau")
    parser.add_argument("--adam-steps", type=int, default=10)
    parser.add_argument("--adam-lr", type=float, default=0.18)
    parser.add_argument("--lbfgs-maxiter", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--w-g", type=float, default=1.0)
    parser.add_argument("--w-i", type=float, default=0.5)
    parser.add_argument("--w-heat", type=float, default=0.01)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_mismatch_inversion(
        target_path=args.target,
        summary_path=args.summary,
        noise_levels=_parse_float_list(args.noise_levels),
        initial_gamma=args.initial_gamma,
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
    print(json.dumps(summary["mismatch_inversion"]["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

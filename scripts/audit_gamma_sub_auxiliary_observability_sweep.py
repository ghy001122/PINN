"""Auxiliary observability sweep for constrained gamma_sub inversion.

The audit estimates only `gamma_sub` under a controlled synthetic `T_sw`
mismatch target. It compares terminal-only inversion against several synthetic
auxiliary-observation proxies. These auxiliary channels are not experimental
measurements and do not imply full hidden-field recovery; they are information
content probes for reviewer-facing claim boundaries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.audit_gamma_sub_observability_augmented import _anchor_indices
    from scripts.invert_gamma_sub_constrained import CandidateRun, _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params
    from scripts.invert_gamma_sub_v0 import _heat_residual_loss
    from scripts.scan_gamma_sub_identifiability import _load_target, _relative_rmse
except ModuleNotFoundError:  # pragma: no cover
    from audit_gamma_sub_observability_augmented import _anchor_indices  # type: ignore
    from invert_gamma_sub_constrained import CandidateRun, _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params  # type: ignore
    from invert_gamma_sub_v0 import _heat_residual_loss  # type: ignore
    from scan_gamma_sub_identifiability import _load_target, _relative_rmse  # type: ignore

DEFAULT_CONFIG = Path("configs/gamma_sub_auxiliary_observability_sweep.yaml")
PORT_ONLY = "port_only"
CALIBRATED_TSW = "port_plus_calibrated_T_sw"
DENSE_T = "port_plus_dense_T"


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


def _candidate_values(config: dict[str, Any], true_gamma: float) -> list[float]:
    values = [float(value) for value in config["inverse"].get("gamma_candidates", [])]
    if not values:
        raise ValueError("Expected at least one gamma candidate.")
    values.append(float(true_gamma))
    return sorted({round(float(value), 9) for value in values})


def _simulate_candidates(params: dict[str, Any], obs_time: np.ndarray, config: dict[str, Any], t_max: float) -> list[CandidateRun]:
    rows: list[CandidateRun] = []
    for gamma_sub in _candidate_values(config, float(params["gamma_sub"])):
        gt = _simulate_with_params(params, config["simulation"], gamma_sub=float(gamma_sub), t_max=t_max)
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


def _target_with_tsw_mismatch(target: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    params = dict(target["params"])
    delta = float(config["mismatch"].get("T_sw_direction", 1.0)) * float(config["mismatch"]["T_sw_delta_K"])
    params["T_sw"] = float(params["T_sw"]) + delta
    gt = _simulate_with_params(params, config["simulation"], gamma_sub=float(target["params"]["gamma_sub"]), t_max=float(target["t"][-1]))
    return {"gt": gt, "params": params, "T_sw_delta_K": float(delta), "T_sw_target": float(params["T_sw"])}


def _time_indices(nt: int, n: int) -> np.ndarray:
    if n <= 0:
        return np.zeros(0, dtype=int)
    lo = max(1, int(round(0.12 * (nt - 1))))
    hi = max(lo, int(round(0.88 * (nt - 1))))
    return np.unique(np.linspace(lo, hi, n, dtype=int))


def _field_values(gt: dict[str, Any], key: str, anchors: list[tuple[int, int]], t0: float = 0.0) -> np.ndarray:
    if not anchors:
        return np.zeros(0, dtype=float)
    values = np.asarray(gt[key], dtype=float)
    out = np.asarray([values[t_idx, x_idx] for t_idx, x_idx in anchors], dtype=float)
    if key == "T":
        out = out - float(t0)
    return out


def _mean_time_series(gt: dict[str, Any], key: str, t0: float = 0.0) -> np.ndarray:
    values = np.asarray(gt[key], dtype=float)
    if key == "T":
        values = values - float(t0)
    return np.mean(values, axis=1)


def _aux_vector(gt: dict[str, Any], mode: str, anchor_count: int, t0: float) -> np.ndarray:
    if mode in {PORT_ONLY, CALIBRATED_TSW}:
        return np.zeros(0, dtype=float)
    if mode == DENSE_T:
        return (np.asarray(gt["T"], dtype=float) - float(t0)).ravel()
    if mode == "port_plus_sparse_T":
        return _field_values(gt, "T", _anchor_indices(np.asarray(gt["T"]).shape, anchor_count), t0=t0)
    if mode == "port_plus_m_proxy":
        return _field_values(gt, "m", _anchor_indices(np.asarray(gt["m"]).shape, anchor_count), t0=0.0)
    if mode == "port_plus_T_temporal_derivative_proxy":
        time = np.asarray(gt["t"], dtype=float)
        mean_dt = _mean_time_series(gt, "T", t0=t0)
        derivative = np.gradient(mean_dt, time)
        idx = _time_indices(len(time), anchor_count)
        return derivative[idx]
    if mode == "port_plus_sigma_aggregate_proxy":
        mean_sigma = _mean_time_series(gt, "sigma", t0=0.0)
        idx = _time_indices(len(mean_sigma), anchor_count)
        return mean_sigma[idx]
    raise ValueError(f"Unsupported observation mode: {mode}")


def _make_noisy(values: np.ndarray, noise_level: float, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if noise_level <= 0.0 or values.size == 0:
        return values.copy()
    scale = max(float(np.max(np.abs(values))), 1.0e-30)
    return values + float(noise_level) * scale * rng.standard_normal(values.shape)


def _case_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    sweep = config["sweep"]
    modes = [str(value) for value in sweep["observation_modes"]]
    anchors = [int(value) for value in sweep["anchor_counts"]]
    weights = [float(value) for value in sweep["auxiliary_loss_weights"]]
    noises = [float(value) for value in sweep.get("noise_levels", [0.0])]
    specs: list[dict[str, Any]] = []
    for noise in noises:
        for mode in modes:
            if mode == PORT_ONLY:
                specs.append({"observation_mode": mode, "anchor_count": 0, "auxiliary_loss_weight": 0.0, "noise": noise})
            elif mode == CALIBRATED_TSW:
                specs.append({"observation_mode": mode, "anchor_count": 0, "auxiliary_loss_weight": 0.0, "noise": noise})
            elif mode == DENSE_T:
                for weight in weights:
                    specs.append({"observation_mode": mode, "anchor_count": 0, "auxiliary_loss_weight": weight, "noise": noise})
            else:
                for anchor_count in anchors:
                    for weight in weights:
                        specs.append({"observation_mode": mode, "anchor_count": anchor_count, "auxiliary_loss_weight": weight, "noise": noise})
    return specs


def _estimate_case(
    *,
    candidates: list[CandidateRun],
    target_g: np.ndarray,
    target_i: np.ndarray,
    target_aux: np.ndarray,
    mode: str,
    anchor_count: int,
    aux_weight: float,
    t0: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    weights = config["loss"]
    rows = []
    for candidate in candidates:
        g_loss = _relative_rmse(candidate.g_obs, target_g) ** 2
        i_loss = _relative_rmse(candidate.i_obs, target_i) ** 2
        aux_pred = _aux_vector(candidate.gt, mode, anchor_count, t0)
        aux_loss = 0.0 if target_aux.size == 0 else _relative_rmse(aux_pred, target_aux) ** 2
        objective = (
            float(weights.get("w_g", 1.0)) * g_loss
            + float(weights.get("w_i", 0.5)) * i_loss
            + float(weights.get("w_heat", 0.01)) * float(candidate.heat_residual)
            + float(aux_weight) * aux_loss
        )
        rows.append(
            {
                "gamma_sub": float(candidate.gamma_sub),
                "objective": float(objective),
                "G_loss": float(g_loss),
                "I_loss": float(i_loss),
                "auxiliary_loss": float(aux_loss),
                "heat_residual_loss": float(candidate.heat_residual),
            }
        )
    best = min(rows, key=lambda row: float(row["objective"]))
    return {"best": best, "candidate_profile": rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "observation_mode",
        "anchor_count",
        "auxiliary_loss_weight",
        "noise",
        "gamma_true",
        "gamma_est",
        "relative_error",
        "objective",
        "G_loss",
        "I_loss",
        "auxiliary_loss",
        "recoverable_le_0p1",
        "recoverable_le_0p2",
        "finite_result",
        "frozen_inputs_unchanged",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _best_by_mode(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for mode in sorted({str(row["observation_mode"]) for row in rows}):
        selected = [row for row in rows if row["observation_mode"] == mode]
        best = min(selected, key=lambda row: float(row["relative_error"]))
        out.append(best)
    return out


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Gamma_Sub Auxiliary Observability Sweep Report",
        "",
        "All results are synthetic numerical digital-twin benchmark evidence. The auxiliary observations are synthetic information probes, not experimental measurements, and they do not imply full hidden-field recovery.",
        "",
        "## Scope",
        "",
        "This audit estimates only `gamma_sub` under a controlled synthetic `T_sw` mismatch. It compares port-only inversion with sparse/dense temperature information, a temperature temporal-derivative proxy, switching-state `m` proxy, aggregate `sigma` proxy, and an independently calibrated `T_sw` case.",
        "",
        "## Key Results",
        "",
        f"- Cases evaluated: `{summary['num_cases']}`.",
        f"- All finite results: `{summary['all_finite_results']}`.",
        f"- Recoverable at <=0.1 relative error: `{summary['recoverable_count_le_0p1']}` / `{summary['num_cases']}`.",
        f"- Recoverable at <=0.2 relative error: `{summary['recoverable_count_le_0p2']}` / `{summary['num_cases']}`.",
        f"- Port-only baseline relative error: `{summary['port_only_baseline']['relative_error']}`.",
        f"- Best overall mode: `{summary['best_overall_case']['observation_mode']}` with relative error `{summary['best_overall_case']['relative_error']}`.",
        f"- Best non-calibrated auxiliary mode: `{summary['best_non_calibrated_auxiliary_case']['observation_mode']}` with relative error `{summary['best_non_calibrated_auxiliary_case']['relative_error']}`.",
        f"- Calibrated T_sw best relative error: `{summary['best_calibrated_tsw_case']['relative_error']}`.",
        f"- Frozen inputs unchanged: `{summary['frozen_gt_unchanged']}`.",
        "",
        "## Best Case By Mode",
        "",
        "| mode | anchor_count | weight | noise | gamma_est | relative_error | auxiliary_loss |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["best_by_mode"]:
        lines.append(
            f"| `{row['observation_mode']}` | {row['anchor_count']} | {row['auxiliary_loss_weight']} | {row['noise']} | "
            f"{row['gamma_est']} | {row['relative_error']} | {row['auxiliary_loss']} |"
        )
    if float(summary["best_calibrated_tsw_case"]["relative_error"]) < float(summary["port_only_baseline"]["relative_error"]):
        calibrated_text = "The calibrated `T_sw` case improves recovery, supporting the claim that independent switching-temperature calibration is the most direct way to control this confounder."
    else:
        calibrated_text = "The calibrated `T_sw` case did not improve recovery in this run, so the evidence would not support a calibration-dominance claim."
    best_aux_error = float(summary["best_non_calibrated_auxiliary_case"]["relative_error"])
    baseline_error = float(summary["port_only_baseline"]["relative_error"])
    if best_aux_error <= 0.2:
        aux_text = "At least one non-calibrated auxiliary proxy reaches the recoverable region; this should be written as observability design guidance, not as full hidden-field recovery."
    elif best_aux_error < baseline_error:
        aux_text = "The best non-calibrated auxiliary proxy reduces bias relative to port-only but remains outside the recoverable region; this is weak observability guidance and still supports `T_sw` calibration as dominant."
    else:
        aux_text = "The non-calibrated auxiliary proxies do not improve over port-only in this sweep; this strengthens the interpretation that `T_sw` calibration dominates under the tested wide mismatch."
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            calibrated_text,
            "",
            aux_text,
            "",
            "The manuscript claim remains conditional: auxiliary synthetic observability can guide experimental design, but the current evidence does not prove unconditional `gamma_sub` identifiability, real-device thermal extraction, or sparse-port full hidden-field recovery.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_auxiliary_observability_sweep(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = _resolve(config_path)
    config = _load_yaml(config_path)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    summary_path = _resolve(config["summary_json"])
    csv_path = _resolve(config["cases_csv"])
    report_path = _resolve(config["report_md"])
    _ensure_inputs(target_path, obs_path)
    before = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}

    target = _load_target(target_path)
    obs = _load_sparse_obs(obs_path)
    obs_time = np.asarray(obs["t"], dtype=float)
    true_gamma = float(target["params"]["gamma_sub"])
    t0 = float(target["params"]["T0"])
    target_case = _target_with_tsw_mismatch(target, config)
    target_gt = target_case["gt"]
    target_g_clean, target_i_clean = _sample_port(target_gt, obs_time)
    nominal_candidates = _simulate_candidates(dict(target["params"]), obs_time, config, t_max=float(target["t"][-1]))
    calibrated_candidates = _simulate_candidates(dict(target_case["params"]), obs_time, config, t_max=float(target["t"][-1]))
    thresholds = [float(value) for value in config["inverse"].get("recoverable_relative_error_thresholds", [0.1, 0.2])]
    seed = int(config["sweep"].get("seed", 2026))

    rows: list[dict[str, Any]] = []
    for idx, spec in enumerate(_case_specs(config)):
        mode = str(spec["observation_mode"])
        anchor_count = int(spec["anchor_count"])
        aux_weight = float(spec["auxiliary_loss_weight"])
        noise = float(spec["noise"])
        rng = np.random.default_rng(seed + idx)
        target_g = _make_noisy(target_g_clean, noise, rng)
        target_i = _make_noisy(target_i_clean, noise, rng)
        target_aux = _make_noisy(_aux_vector(target_gt, mode, anchor_count, t0), noise, rng)
        candidates = calibrated_candidates if mode == CALIBRATED_TSW else nominal_candidates
        estimate = _estimate_case(
            candidates=candidates,
            target_g=target_g,
            target_i=target_i,
            target_aux=target_aux,
            mode=mode,
            anchor_count=anchor_count,
            aux_weight=aux_weight,
            t0=t0,
            config=config,
        )
        best = estimate["best"]
        gamma_est = float(best["gamma_sub"])
        rel = abs(gamma_est - true_gamma) / true_gamma
        rows.append(
            {
                "observation_mode": mode,
                "anchor_count": anchor_count,
                "auxiliary_loss_weight": aux_weight,
                "noise": noise,
                "gamma_true": true_gamma,
                "gamma_est": gamma_est,
                "relative_error": float(rel),
                "objective": float(best["objective"]),
                "G_loss": float(best["G_loss"]),
                "I_loss": float(best["I_loss"]),
                "auxiliary_loss": float(best["auxiliary_loss"]),
                "heat_residual_loss": float(best["heat_residual_loss"]),
                "recoverable_le_0p1": bool(rel <= thresholds[0] + 1.0e-15),
                "recoverable_le_0p2": bool(rel <= thresholds[min(1, len(thresholds) - 1)] + 1.0e-15),
                "finite_result": bool(np.isfinite([gamma_est, rel, best["objective"], best["G_loss"], best["I_loss"], best["auxiliary_loss"]]).all()),
            }
        )

    after = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = frozen
    rows_sorted = sorted(rows, key=lambda row: (str(row["observation_mode"]), float(row["noise"]), int(row["anchor_count"]), float(row["auxiliary_loss_weight"])))
    baseline_zero = [row for row in rows_sorted if row["observation_mode"] == PORT_ONLY and float(row["noise"]) == 0.0]
    port_only_baseline = baseline_zero[0] if baseline_zero else next(row for row in rows_sorted if row["observation_mode"] == PORT_ONLY)
    calibrated_cases = [row for row in rows_sorted if row["observation_mode"] == CALIBRATED_TSW]
    non_calibrated_aux = [row for row in rows_sorted if row["observation_mode"] not in {PORT_ONLY, CALIBRATED_TSW}]
    best_by_mode = _best_by_mode(rows_sorted)
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin auxiliary observability sweep; not experimental data.",
        "scope": "Only gamma_sub is estimated. Auxiliary observations are synthetic information probes and do not imply full hidden-field recovery.",
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "true_gamma_sub": true_gamma,
        "controlled_T_sw_delta_K": float(target_case["T_sw_delta_K"]),
        "num_cases": len(rows_sorted),
        "recoverable_count_le_0p1": int(sum(bool(row["recoverable_le_0p1"]) for row in rows_sorted)),
        "recoverable_count_le_0p2": int(sum(bool(row["recoverable_le_0p2"]) for row in rows_sorted)),
        "port_only_baseline": port_only_baseline,
        "best_overall_case": min(rows_sorted, key=lambda row: float(row["relative_error"])),
        "best_non_calibrated_auxiliary_case": min(non_calibrated_aux, key=lambda row: float(row["relative_error"])),
        "best_calibrated_tsw_case": min(calibrated_cases, key=lambda row: float(row["relative_error"])),
        "best_by_mode": best_by_mode,
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows_sorted)),
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": frozen,
        "rows": rows_sorted,
        "outputs": {"summary_json": _display_path(summary_path), "cases_csv": _display_path(csv_path), "report_md": _display_path(report_path)},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(csv_path, rows_sorted)
    _write_report(report_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_auxiliary_observability_sweep(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "cases_csv": summary["outputs"]["cases_csv"],
                "num_cases": summary["num_cases"],
                "recoverable_count_le_0p1": summary["recoverable_count_le_0p1"],
                "recoverable_count_le_0p2": summary["recoverable_count_le_0p2"],
                "frozen_gt_unchanged": summary["frozen_gt_unchanged"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

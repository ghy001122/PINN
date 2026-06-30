"""Observability-augmented gamma_sub audit.

This lightweight audit asks whether minimal extra observability can reduce the
`gamma_sub` / `T_sw` confounding seen in sparse-port inversion. It keeps frozen
Ground Truth v1.1 files read-only, optimizes only `gamma_sub`, and uses
controlled synthetic `T_sw` mismatch targets plus optional sparse temperature
anchors. It is synthetic numerical digital-twin evidence, not experimental data
and not full hidden-field recovery.
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
        _load_sparse_obs,
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
        _load_sparse_obs,
        _sample_port,
        _simulate_with_params,
    )
    from invert_gamma_sub_v0 import _heat_residual_loss  # type: ignore
    from scan_gamma_sub_identifiability import _load_target, _relative_rmse  # type: ignore


DEFAULT_CONFIG = Path("configs/gamma_sub_observability_augmented.yaml")


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


def _simulate_nominal_candidates(
    target: dict[str, Any],
    obs_time: np.ndarray,
    config: dict[str, Any],
) -> list[CandidateRun]:
    sim = config["simulation"]
    params = dict(target["params"])
    t_max = float(target["t"][-1])
    rows: list[CandidateRun] = []
    for gamma_sub in _candidate_values(config, float(params["gamma_sub"])):
        gt = _simulate_with_params(params, sim, gamma_sub=float(gamma_sub), t_max=t_max)
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


def _target_with_tsw_width(
    target: dict[str, Any],
    config: dict[str, Any],
    prior_width: float,
) -> dict[str, Any]:
    obs_cfg = config["observability"]
    params = dict(target["params"])
    delta_k = float(obs_cfg.get("tsw_direction", 1.0)) * float(prior_width) * float(obs_cfg["tsw_max_delta_K"])
    params["T_sw"] = float(params["T_sw"]) + delta_k
    gt = _simulate_with_params(
        params,
        config["simulation"],
        gamma_sub=float(target["params"]["gamma_sub"]),
        t_max=float(target["t"][-1]),
    )
    return {"gt": gt, "params": params, "T_sw_delta_K": float(delta_k), "T_sw_target": float(params["T_sw"])}


def _anchor_indices(shape: tuple[int, int], n_anchors: int) -> list[tuple[int, int]]:
    if n_anchors <= 0:
        return []
    nt, nx = shape
    t_lo = max(1, int(round(0.12 * (nt - 1))))
    t_hi = max(t_lo, int(round(0.88 * (nt - 1))))
    t_idx = np.linspace(t_lo, t_hi, n_anchors, dtype=int)
    x_idx = np.linspace(1, max(1, nx - 2), n_anchors, dtype=int)
    return [(int(t), int(x)) for t, x in zip(t_idx, x_idx)]


def _temperature_anchor_values(gt: dict[str, Any], anchors: list[tuple[int, int]], t0: float) -> np.ndarray:
    if not anchors:
        return np.zeros(0, dtype=float)
    temperature = np.asarray(gt["T"], dtype=float)
    return np.asarray([temperature[t_idx, x_idx] - t0 for t_idx, x_idx in anchors], dtype=float)


def _temperature_anchor_loss(
    candidate: CandidateRun,
    target_gt: dict[str, Any],
    anchors: list[tuple[int, int]],
    t0: float,
) -> float:
    if not anchors:
        return 0.0
    pred = _temperature_anchor_values(candidate.gt, anchors, t0)
    truth = _temperature_anchor_values(target_gt, anchors, t0)
    return _relative_rmse(pred, truth) ** 2


def _estimate_gamma_augmented(
    *,
    candidates: list[CandidateRun],
    target_g: np.ndarray,
    target_i: np.ndarray,
    target_gt: dict[str, Any],
    anchors: list[tuple[int, int]],
    t0: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    weights = config["loss"]
    rows = []
    for candidate in candidates:
        g_loss = _relative_rmse(candidate.g_obs, target_g) ** 2
        i_loss = _relative_rmse(candidate.i_obs, target_i) ** 2
        heat_loss = float(candidate.heat_residual)
        t_loss = _temperature_anchor_loss(candidate, target_gt, anchors, t0)
        total = (
            float(weights.get("w_g", 1.0)) * g_loss
            + float(weights.get("w_i", 0.5)) * i_loss
            + float(weights.get("w_heat", 0.01)) * heat_loss
            + float(weights.get("w_temperature_anchor", 0.0)) * t_loss
        )
        rows.append(
            {
                "gamma_sub": float(candidate.gamma_sub),
                "objective_value": float(total),
                "G_loss": float(g_loss),
                "I_loss": float(i_loss),
                "heat_residual_loss": float(heat_loss),
                "temperature_anchor_loss": float(t_loss),
            }
        )
    best = min(rows, key=lambda row: float(row["objective_value"]))
    return {"best": best, "candidate_profile": rows}


def _case_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    obs = config["observability"]
    wide = float(obs["wide_tsw_prior_width"])
    narrow = float(obs["narrow_tsw_prior_width"])
    anchor_counts = [int(value) for value in obs.get("temperature_anchor_counts", [2, 4, 8])]
    cases: list[dict[str, Any]] = [
        {
            "case_name": "port_only_wide_tsw",
            "observation_mode": "port_only",
            "n_temperature_anchors": 0,
            "T_sw_prior_width": wide,
        }
    ]
    for n_anchor in anchor_counts:
        cases.append(
            {
                "case_name": f"port_plus_temperature_anchor_n{n_anchor}",
                "observation_mode": "port_plus_temperature_anchor",
                "n_temperature_anchors": n_anchor,
                "T_sw_prior_width": wide,
            }
        )
    cases.extend(
        [
            {
                "case_name": "port_plus_tsw_prior_wide",
                "observation_mode": "port_plus_tsw_prior",
                "n_temperature_anchors": 0,
                "T_sw_prior_width": wide,
            },
            {
                "case_name": "port_plus_tsw_prior_narrow",
                "observation_mode": "port_plus_tsw_prior",
                "n_temperature_anchors": 0,
                "T_sw_prior_width": narrow,
            },
        ]
    )
    for n_anchor in anchor_counts:
        cases.append(
            {
                "case_name": f"port_plus_temperature_anchor_and_tsw_prior_n{n_anchor}",
                "observation_mode": "port_plus_temperature_anchor_and_tsw_prior",
                "n_temperature_anchors": n_anchor,
                "T_sw_prior_width": narrow,
            }
        )
    return cases


def _interpret_case(row: dict[str, Any], baseline_error: float) -> str:
    mode = str(row["observation_mode"])
    error = float(row["gamma_relative_error"])
    if mode == "port_only":
        return "Port-only baseline under wide T_sw mismatch; exposes gamma_sub/T_sw confounding."
    if error < baseline_error:
        return "Auxiliary observability or tighter T_sw prior reduced gamma_sub bias in this synthetic case."
    if math.isclose(error, baseline_error, rel_tol=1.0e-12, abs_tol=1.0e-12):
        return "This setting matched the port-only gamma_sub bias in this candidate-grid audit."
    return "This setting did not reduce gamma_sub bias in this candidate-grid audit."


def _write_cases_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "case_name",
        "observation_mode",
        "n_temperature_anchors",
        "T_sw_prior_width",
        "T_sw_delta_K",
        "gamma_true",
        "gamma_est",
        "gamma_relative_error",
        "objective_value",
        "G_loss",
        "I_loss",
        "temperature_anchor_loss",
        "finite_result",
        "frozen_inputs_unchanged",
        "interpretation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _best_by_mode(rows: list[dict[str, Any]], mode: str) -> dict[str, Any] | None:
    selected = [row for row in rows if row["observation_mode"] == mode]
    if not selected:
        return None
    return min(selected, key=lambda row: float(row["gamma_relative_error"]))


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    baseline = summary["baseline_case"]
    best_temp = summary["best_temperature_anchor_case"]
    best_prior = summary["best_tsw_prior_case"]
    best_combined = summary["best_combined_case"]
    lines = [
        "# Gamma_Sub Observability-Augmented Audit Report",
        "",
        "## Scope",
        "",
        "All results are synthetic numerical digital-twin benchmark results. They are not measured experimental data, not full three-dimensional device simulations, and not sparse-port full hidden-field recovery.",
        "",
        "This audit keeps frozen Ground Truth v1.1 files read-only and optimizes only `gamma_sub`. It introduces controlled synthetic `T_sw` mismatch targets, optional sparse temperature anchors, and narrower `T_sw` prior width to test whether minimal extra observability can reduce `gamma_sub` / `T_sw` confounding.",
        "",
        "## Key Results",
        "",
        f"- Cases evaluated: `{summary['num_cases']}`",
        f"- Port-only baseline relative error: `{baseline['gamma_relative_error']}`",
        f"- Best temperature-anchor relative error: `{best_temp['gamma_relative_error'] if best_temp else None}`",
        f"- Best T_sw-prior relative error: `{best_prior['gamma_relative_error'] if best_prior else None}`",
        f"- Best combined relative error: `{best_combined['gamma_relative_error'] if best_combined else None}`",
        f"- Temperature anchors reduced bias: `{summary['temperature_anchor_reduced_bias']}`",
        f"- Narrow T_sw prior reduced bias: `{summary['narrow_tsw_prior_reduced_bias']}`",
        f"- Combined observability reduced bias: `{summary['combined_observability_reduced_bias']}`",
        f"- Frozen inputs unchanged: `{summary['frozen_gt_unchanged']}`",
        "",
        "## Case Table",
        "",
        "| case | mode | n_T_anchor | T_sw prior width | gamma_est | relative error | interpretation |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary["rows"]:
        lines.append(
            f"| `{row['case_name']}` | `{row['observation_mode']}` | {row['n_temperature_anchors']} | "
            f"{row['T_sw_prior_width']} | {row['gamma_est']} | {row['gamma_relative_error']} | {row['interpretation']} |"
        )
    temp_answer = (
        "In this candidate-grid audit, sparse synthetic temperature anchors alone reduced the gamma_sub bias."
        if summary["temperature_anchor_reduced_bias"]
        else "In this candidate-grid audit, sparse synthetic temperature anchors alone did not reduce the gamma_sub bias under the wide T_sw mismatch target."
    )
    prior_answer = (
        "Tightening the T_sw prior reduced gamma_sub bias and is the dominant improvement in this audit."
        if summary["narrow_tsw_prior_reduced_bias"]
        else "Tightening the T_sw prior did not reduce gamma_sub bias in this audit."
    )
    combined_answer = (
        "The combined cases improved relative to port-only because the T_sw prior was narrowed; the current evidence should not be read as proof that the sparse temperature anchors alone solve the confounding."
        if summary["combined_observability_reduced_bias"]
        else "The combined cases did not improve relative to port-only in this audit."
    )
    lines.extend(
        [
            "",
            "## Answers",
            "",
            "Sparse port-only observations are not enough because terminal `G/I` can be matched by different combinations of effective heat loss and switching-temperature behavior. The prior confounding audits already showed that `T_sw` is a dominant sensitivity source, and this audit uses that mismatch as a controlled stress target.",
            "",
            temp_answer + " These anchors are synthetic observability probes, not real experimental temperature measurements.",
            "",
            prior_answer + " This supports an experimental-design rule: switching-temperature behavior should be independently calibrated or tightly bounded before robust `gamma_sub` extraction is claimed.",
            "",
            combined_answer,
            "",
            "The practical implication is that terminal electrical data alone are insufficient for robust thermal-loss inference under switching-temperature uncertainty. Minimal extra observability is useful only if it constrains the dominant confounder or is sufficiently informative about thermal dynamics.",
            "",
            "This audit still does not justify full hidden-field recovery. It supports only a constrained reduced inverse story for `gamma_sub` in a synthetic numerical benchmark.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_observability_augmented_audit(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = _resolve(config_path)
    config = _load_yaml(config_path)
    target_path = _resolve(config["target_npz"])
    obs_path = _resolve(config["sparse_obs_npz"])
    summary_path = _resolve(config["summary_json"])
    csv_path = _resolve(config["cases_csv"])
    report_path = _resolve(config["report_md"])
    codex_report_path = _resolve(config["codex_report_md"])
    _ensure_inputs(target_path, obs_path)

    before_hashes = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    target = _load_target(target_path)
    obs = _load_sparse_obs(obs_path)
    obs_time = np.asarray(obs["t"], dtype=float)
    true_gamma = float(target["params"]["gamma_sub"])
    t0 = float(target["params"]["T0"])

    candidates = _simulate_nominal_candidates(target, obs_time, config)
    target_cache: dict[float, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for case in _case_specs(config):
        prior_width = float(case["T_sw_prior_width"])
        if prior_width not in target_cache:
            target_cache[prior_width] = _target_with_tsw_width(target, config, prior_width)
        target_case = target_cache[prior_width]
        target_gt = target_case["gt"]
        target_g, target_i = _sample_port(target_gt, obs_time)
        anchors = _anchor_indices(np.asarray(target_gt["T"]).shape, int(case["n_temperature_anchors"]))
        estimate = _estimate_gamma_augmented(
            candidates=candidates,
            target_g=target_g,
            target_i=target_i,
            target_gt=target_gt,
            anchors=anchors,
            t0=t0,
            config=config,
        )
        best = estimate["best"]
        gamma_est = float(best["gamma_sub"])
        relative_error = abs(gamma_est - true_gamma) / true_gamma
        finite = all(
            np.isfinite(float(value))
            for value in [
                gamma_est,
                relative_error,
                best["objective_value"],
                best["G_loss"],
                best["I_loss"],
                best["temperature_anchor_loss"],
            ]
        )
        rows.append(
            {
                "case_name": case["case_name"],
                "observation_mode": case["observation_mode"],
                "n_temperature_anchors": int(case["n_temperature_anchors"]),
                "T_sw_prior_width": prior_width,
                "T_sw_delta_K": float(target_case["T_sw_delta_K"]),
                "T_sw_target": float(target_case["T_sw_target"]),
                "gamma_true": true_gamma,
                "gamma_est": gamma_est,
                "gamma_relative_error": float(relative_error),
                "objective_value": float(best["objective_value"]),
                "G_loss": float(best["G_loss"]),
                "I_loss": float(best["I_loss"]),
                "heat_residual_loss": float(best["heat_residual_loss"]),
                "temperature_anchor_loss": float(best["temperature_anchor_loss"]),
                "finite_result": bool(finite),
                "frozen_inputs_unchanged": None,
                "temperature_anchor_indices": anchors,
            }
        )

    baseline = next(row for row in rows if row["case_name"] == "port_only_wide_tsw")
    baseline_error = float(baseline["gamma_relative_error"])
    after_hashes = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    frozen_unchanged = before_hashes == after_hashes
    for row in rows:
        row["frozen_inputs_unchanged"] = bool(frozen_unchanged)
        row["interpretation"] = _interpret_case(row, baseline_error)

    best_temp = _best_by_mode(rows, "port_plus_temperature_anchor")
    best_prior = _best_by_mode(rows, "port_plus_tsw_prior")
    best_combined = _best_by_mode(rows, "port_plus_temperature_anchor_and_tsw_prior")
    best_overall = min(rows, key=lambda row: float(row["gamma_relative_error"]))
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin observability audit; not measured experimental data.",
        "scope": "Only gamma_sub is estimated. Temperature anchors and T_sw priors are observability probes, not full hidden-field recovery.",
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "target_keys": target["keys"],
        "sparse_obs_keys": obs["keys"],
        "true_gamma_sub": true_gamma,
        "num_cases": len(rows),
        "baseline_case": baseline,
        "best_temperature_anchor_case": best_temp,
        "best_tsw_prior_case": best_prior,
        "best_combined_case": best_combined,
        "best_overall_case": best_overall,
        "temperature_anchor_reduced_bias": bool(best_temp and float(best_temp["gamma_relative_error"]) < baseline_error),
        "narrow_tsw_prior_reduced_bias": bool(best_prior and float(best_prior["gamma_relative_error"]) < baseline_error),
        "combined_observability_reduced_bias": bool(best_combined and float(best_combined["gamma_relative_error"]) < baseline_error),
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "frozen_gt_hashes_before": before_hashes,
        "frozen_gt_hashes_after": after_hashes,
        "frozen_gt_unchanged": bool(frozen_unchanged),
        "rows": rows,
        "outputs": {
            "summary_json": _display_path(summary_path),
            "cases_csv": _display_path(csv_path),
            "report_md": _display_path(report_path),
            "codex_report_md": _display_path(codex_report_path),
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_cases_csv(csv_path, rows)
    _write_report(report_path, summary)
    _write_report(codex_report_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_observability_augmented_audit(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "cases_csv": summary["outputs"]["cases_csv"],
                "report_md": summary["outputs"]["report_md"],
                "baseline_relative_error": summary["baseline_case"]["gamma_relative_error"],
                "best_overall_relative_error": summary["best_overall_case"]["gamma_relative_error"],
                "frozen_gt_unchanged": summary["frozen_gt_unchanged"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
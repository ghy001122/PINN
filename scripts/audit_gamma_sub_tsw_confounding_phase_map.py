"""Two-dimensional T_sw confounding phase-map for gamma_sub inversion.

This audit estimates only `gamma_sub`. It separates the calibration-error
stress amplitude (`T_sw_delta_K`) from the residual prior width
(`T_sw_prior_width`) by applying

    effective_T_sw_delta_K = T_sw_delta_K * T_sw_prior_width

to the synthetic target. The inversion candidates keep the frozen nominal
switching prior and vary only `gamma_sub`. Results are synthetic numerical
 digital-twin benchmark evidence, not experimental data and not full hidden-field
recovery.
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
    from scripts.audit_gamma_sub_observability_augmented import _estimate_gamma_augmented, _simulate_nominal_candidates
    from scripts.invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params
    from scripts.scan_gamma_sub_identifiability import _load_target
except ModuleNotFoundError:  # pragma: no cover
    from audit_gamma_sub_observability_augmented import _estimate_gamma_augmented, _simulate_nominal_candidates  # type: ignore
    from invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params  # type: ignore
    from scan_gamma_sub_identifiability import _load_target  # type: ignore

DEFAULT_CONFIG = Path("configs/gamma_sub_tsw_confounding_phase_map.yaml")


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


def _target_for_phase_cell(target: dict[str, Any], config: dict[str, Any], delta_k: float, prior_width: float) -> dict[str, Any]:
    params = dict(target["params"])
    direction = float(config["sweep"].get("T_sw_direction", 1.0))
    effective_delta = direction * float(delta_k) * float(prior_width)
    params["T_sw"] = float(params["T_sw"]) + effective_delta
    gt = _simulate_with_params(params, config["simulation"], gamma_sub=float(target["params"]["gamma_sub"]), t_max=float(target["t"][-1]))
    return {
        "gt": gt,
        "T_sw_delta_K": float(delta_k),
        "T_sw_prior_width": float(prior_width),
        "effective_T_sw_delta_K": float(effective_delta),
        "T_sw_target": float(params["T_sw"]),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "T_sw_delta_K",
        "T_sw_prior_width",
        "effective_T_sw_delta_K",
        "gamma_true",
        "gamma_est",
        "relative_error",
        "objective",
        "G_loss",
        "I_loss",
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


def _matrix(rows: list[dict[str, Any]], value_key: str) -> dict[str, Any]:
    deltas = sorted({float(row["T_sw_delta_K"]) for row in rows})
    widths = sorted({float(row["T_sw_prior_width"]) for row in rows})
    lookup = {(float(row["T_sw_prior_width"]), float(row["T_sw_delta_K"])): float(row[value_key]) for row in rows}
    values = [[lookup[(width, delta)] for delta in deltas] for width in widths]
    return {"T_sw_delta_K": deltas, "T_sw_prior_widths": widths, "values": values, "value_key": value_key}


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Gamma_Sub T_sw Confounding Phase-Map Report",
        "",
        "All results are synthetic numerical digital-twin benchmark evidence, not experimental data and not full hidden-field recovery.",
        "",
        "## Scope",
        "",
        "This audit estimates only `gamma_sub`. It scans two separate quantities:",
        "",
        "- `T_sw_delta_K`: the switching-temperature calibration-error stress amplitude;",
        "- `T_sw_prior_width`: the residual fraction of that calibration error after literature/engineering prior narrowing.",
        "",
        "The synthetic target applies `effective_T_sw_delta_K = T_sw_delta_K * T_sw_prior_width`. This keeps calibration-error effect and prior-width effect explicit instead of treating them as one variable.",
        "",
        "## Key Results",
        "",
        f"- Cases evaluated: `{summary['num_cases']}`.",
        f"- All finite results: `{summary['all_finite_results']}`.",
        f"- Recoverable at <=0.1 relative error: `{summary['recoverable_count_le_0p1']}` / `{summary['num_cases']}`.",
        f"- Recoverable at <=0.2 relative error: `{summary['recoverable_count_le_0p2']}` / `{summary['num_cases']}`.",
        f"- Worst case: `T_sw_delta_K={summary['worst_case']['T_sw_delta_K']}`, `T_sw_prior_width={summary['worst_case']['T_sw_prior_width']}`, relative error `{summary['worst_case']['relative_error']}`.",
        f"- Frozen inputs unchanged: `{summary['frozen_gt_unchanged']}`.",
        "",
        "## Phase Map Cases",
        "",
        "| T_sw_delta_K | T_sw_prior_width | effective_T_sw_delta_K | gamma_est | relative_error | objective | G_loss | I_loss | recoverable <=0.1 | recoverable <=0.2 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summary["rows"]:
        lines.append(
            f"| {row['T_sw_delta_K']} | {row['T_sw_prior_width']} | {row['effective_T_sw_delta_K']} | "
            f"{row['gamma_est']} | {row['relative_error']} | {row['objective']} | {row['G_loss']} | {row['I_loss']} | "
            f"{row['recoverable_le_0p1']} | {row['recoverable_le_0p2']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The phase map is intended for reviewer defense. Larger calibration-error amplitude increases the possible mismatch, while smaller residual prior width reduces the mismatch actually passed to the inverse model. Recoverable cells therefore identify where the reduced `gamma_sub` inverse target remains defensible under bounded `T_sw` uncertainty.",
            "",
            "The paper claim must remain conditional: `gamma_sub` is supportable as a constrained reduced inverse target only when `T_sw` is fixed or tightly bounded. This audit does not prove unconditional identifiability or full hidden-field recovery.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_tsw_confounding_phase_map(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
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
    candidates = _simulate_nominal_candidates(target, obs_time, config)
    true_gamma = float(target["params"]["gamma_sub"])
    thresholds = [float(value) for value in config["inverse"].get("recoverable_relative_error_thresholds", [0.1, 0.2])]

    rows: list[dict[str, Any]] = []
    for delta_k in [float(value) for value in config["sweep"]["T_sw_delta_K"]]:
        for prior_width in [float(value) for value in config["sweep"]["T_sw_prior_widths"]]:
            target_case = _target_for_phase_cell(target, config, delta_k, prior_width)
            target_g, target_i = _sample_port(target_case["gt"], obs_time)
            estimate = _estimate_gamma_augmented(
                candidates=candidates,
                target_g=target_g,
                target_i=target_i,
                target_gt=target_case["gt"],
                anchors=[],
                t0=float(target["params"]["T0"]),
                config=config,
            )
            best = estimate["best"]
            gamma_est = float(best["gamma_sub"])
            rel = abs(gamma_est - true_gamma) / true_gamma
            row = {
                "T_sw_delta_K": float(delta_k),
                "T_sw_prior_width": float(prior_width),
                "effective_T_sw_delta_K": float(target_case["effective_T_sw_delta_K"]),
                "gamma_true": true_gamma,
                "gamma_est": gamma_est,
                "relative_error": float(rel),
                "objective": float(best["objective_value"]),
                "G_loss": float(best["G_loss"]),
                "I_loss": float(best["I_loss"]),
                "heat_residual_loss": float(best["heat_residual_loss"]),
                "recoverable_le_0p1": bool(rel <= thresholds[0] + 1.0e-15),
                "recoverable_le_0p2": bool(rel <= thresholds[min(1, len(thresholds) - 1)] + 1.0e-15),
                "finite_result": bool(np.isfinite([gamma_est, rel, best["objective_value"], best["G_loss"], best["I_loss"]]).all()),
            }
            rows.append(row)

    after = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = frozen

    rows_sorted = sorted(rows, key=lambda row: (float(row["T_sw_delta_K"]), float(row["T_sw_prior_width"])))
    worst = max(rows_sorted, key=lambda row: float(row["relative_error"]))
    best_nonzero = min((row for row in rows_sorted if float(row["effective_T_sw_delta_K"]) > 0.0), key=lambda row: float(row["relative_error"]), default=rows_sorted[0])
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin T_sw confounding phase-map; not experimental data.",
        "scope": "Only gamma_sub is estimated. T_sw_delta_K is a calibration-error stress amplitude; T_sw_prior_width is a residual prior fraction.",
        "residual_delta_model": config["sweep"].get("residual_delta_model", "effective_T_sw_delta_K = T_sw_delta_K * T_sw_prior_width"),
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "true_gamma_sub": true_gamma,
        "num_cases": len(rows_sorted),
        "recoverable_thresholds": thresholds,
        "recoverable_count_le_0p1": int(sum(bool(row["recoverable_le_0p1"]) for row in rows_sorted)),
        "recoverable_count_le_0p2": int(sum(bool(row["recoverable_le_0p2"]) for row in rows_sorted)),
        "worst_case": worst,
        "best_nonzero_effective_delta_case": best_nonzero,
        "relative_error_matrix": _matrix(rows_sorted, "relative_error"),
        "gamma_est_matrix": _matrix(rows_sorted, "gamma_est"),
        "rows": rows_sorted,
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows_sorted)),
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": frozen,
        "outputs": {
            "summary_json": _display_path(summary_path),
            "cases_csv": _display_path(csv_path),
            "report_md": _display_path(report_path),
        },
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
    summary = run_tsw_confounding_phase_map(args.config)
    print(
        json.dumps(
            {
                "summary_json": summary["outputs"]["summary_json"],
                "cases_csv": summary["outputs"]["cases_csv"],
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

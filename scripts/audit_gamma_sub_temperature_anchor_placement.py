"""Temperature-anchor placement audit for gamma_sub / T_sw confounding.

This audit checks whether the previous sparse-temperature-anchor failure could
be caused by anchor placement. It compares uniform, random, and high-gradient
synthetic temperature anchors under the same controlled `T_sw` mismatch target.
All results are synthetic numerical digital-twin benchmark evidence.
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
    from scripts.audit_gamma_sub_observability_augmented import _anchor_indices, _estimate_gamma_augmented, _simulate_nominal_candidates
    from scripts.invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params
    from scripts.scan_gamma_sub_identifiability import _load_target
except ModuleNotFoundError:  # pragma: no cover
    from audit_gamma_sub_observability_augmented import _anchor_indices, _estimate_gamma_augmented, _simulate_nominal_candidates  # type: ignore
    from invert_gamma_sub_constrained import _display_path, _ensure_inputs, _load_sparse_obs, _sample_port, _simulate_with_params  # type: ignore
    from scan_gamma_sub_identifiability import _load_target  # type: ignore

DEFAULT_CONFIG = Path("configs/gamma_sub_temperature_anchor_placement.yaml")


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


def _target_gt(target: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    params = dict(target["params"])
    placement = config["placement"]
    params["T_sw"] = float(params["T_sw"]) + float(placement["T_sw_prior_width"]) * float(placement["T_sw_max_delta_K"])
    return _simulate_with_params(params, config["simulation"], gamma_sub=float(target["params"]["gamma_sub"]), t_max=float(target["t"][-1]))


def _random_anchors(shape: tuple[int, int], n_anchors: int, seed: int) -> list[tuple[int, int]]:
    rng = np.random.default_rng(seed)
    nt, nx = shape
    times = rng.integers(max(1, int(0.1 * nt)), max(2, int(0.9 * nt)), size=n_anchors)
    xs = rng.integers(1, max(2, nx - 1), size=n_anchors)
    return [(int(t), int(x)) for t, x in zip(times, xs)]


def _high_gradient_anchors(temperature: np.ndarray, n_anchors: int) -> list[tuple[int, int]]:
    temp = np.asarray(temperature, dtype=float)
    gt = np.zeros_like(temp)
    gx = np.zeros_like(temp)
    gt[1:-1, :] = np.abs(temp[2:, :] - temp[:-2, :])
    gx[:, 1:-1] = np.abs(temp[:, 2:] - temp[:, :-2])
    score = gt / max(float(np.max(gt)), 1.0e-30) + gx / max(float(np.max(gx)), 1.0e-30)
    score[:2, :] = -1.0
    score[-2:, :] = -1.0
    score[:, :1] = -1.0
    score[:, -1:] = -1.0
    flat = np.argsort(score.ravel())[::-1]
    anchors: list[tuple[int, int]] = []
    used: set[tuple[int, int]] = set()
    for idx in flat:
        t_idx, x_idx = np.unravel_index(int(idx), score.shape)
        key = (int(t_idx), int(x_idx))
        if key in used or score[key] < 0.0:
            continue
        if all(abs(key[0] - old[0]) > 3 or abs(key[1] - old[1]) > 1 for old in anchors):
            anchors.append(key)
            used.add(key)
        if len(anchors) >= n_anchors:
            break
    return anchors[:n_anchors]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["case_name", "placement_mode", "seed", "n_temperature_anchors", "gamma_true", "gamma_est", "gamma_relative_error", "objective_value", "G_loss", "I_loss", "temperature_anchor_loss", "finite_result", "frozen_inputs_unchanged"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Gamma_Sub Temperature-Anchor Placement Report",
        "",
        "All results are synthetic numerical digital-twin benchmark evidence, not experimental data and not full hidden-field recovery.",
        "",
        "This audit tests whether sparse temperature anchors failed because their placement was weak. It compares uniform, random, and high-gradient anchor locations under the same controlled wide `T_sw` mismatch target.",
        "",
        "## Key Results",
        "",
        f"- Port-only baseline relative error: `{summary['baseline_relative_error']}`.",
        f"- Best placement mode: `{summary['best_case']['placement_mode']}` with relative error `{summary['best_case']['gamma_relative_error']}`.",
        f"- Any placement reduced gamma bias: `{summary['any_anchor_placement_reduced_bias']}`.",
        f"- Frozen inputs unchanged: `{summary['frozen_gt_unchanged']}`.",
        "",
        "## Cases",
        "",
        "| case | placement | seed | gamma_est | relative error | temp anchor loss |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["rows"]:
        lines.append(f"| `{row['case_name']}` | `{row['placement_mode']}` | {row.get('seed')} | {row['gamma_est']} | {row['gamma_relative_error']} | {row['temperature_anchor_loss']} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "If high-gradient or random anchors still do not reduce `gamma_sub` bias, the earlier temperature-anchor failure is not just a uniform-placement artifact. It indicates that a small number of synthetic temperature points, at the tested loss weight and candidate grid, is insufficient to overcome the dominant `T_sw` mismatch. This supports a stricter manuscript claim: independent `T_sw` calibration is more important than sparse thermal anchors alone in the current benchmark.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_temperature_anchor_placement_audit(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
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
    target_gt = _target_gt(target, config)
    target_g, target_i = _sample_port(target_gt, obs_time)
    true_gamma = float(target["params"]["gamma_sub"])
    t0 = float(target["params"]["T0"])
    n_anchor = int(config["placement"]["n_temperature_anchors"])
    shape = np.asarray(target_gt["T"]).shape
    case_anchors: list[tuple[str, str, int | None, list[tuple[int, int]]]] = [
        ("port_only", "none", None, []),
        ("uniform_anchors", "uniform", None, _anchor_indices(shape, n_anchor)),
        ("high_gradient_anchors", "high_gradient", None, _high_gradient_anchors(np.asarray(target_gt["T"], dtype=float), n_anchor)),
    ]
    for seed in [int(value) for value in config["placement"].get("random_seeds", [])]:
        case_anchors.append((f"random_anchors_seed_{seed}", "random", seed, _random_anchors(shape, n_anchor, seed)))
    rows: list[dict[str, Any]] = []
    for case_name, mode, seed, anchors in case_anchors:
        estimate = _estimate_gamma_augmented(candidates=candidates, target_g=target_g, target_i=target_i, target_gt=target_gt, anchors=anchors, t0=t0, config=config)
        best = estimate["best"]
        gamma_est = float(best["gamma_sub"])
        rel = abs(gamma_est - true_gamma) / true_gamma
        rows.append({
            "case_name": case_name,
            "placement_mode": mode,
            "seed": seed,
            "n_temperature_anchors": len(anchors),
            "temperature_anchor_indices": anchors,
            "gamma_true": true_gamma,
            "gamma_est": gamma_est,
            "gamma_relative_error": float(rel),
            "objective_value": float(best["objective_value"]),
            "G_loss": float(best["G_loss"]),
            "I_loss": float(best["I_loss"]),
            "heat_residual_loss": float(best["heat_residual_loss"]),
            "temperature_anchor_loss": float(best["temperature_anchor_loss"]),
            "finite_result": bool(np.isfinite([gamma_est, rel, best["objective_value"], best["G_loss"], best["I_loss"], best["temperature_anchor_loss"]]).all()),
        })
    after = {"target_npz": _sha256(target_path), "sparse_obs_npz": _sha256(obs_path)}
    frozen = before == after
    for row in rows:
        row["frozen_inputs_unchanged"] = frozen
    baseline = next(row for row in rows if row["placement_mode"] == "none")
    anchor_rows = [row for row in rows if row["placement_mode"] != "none"]
    best = min(anchor_rows, key=lambda row: float(row["gamma_relative_error"])) if anchor_rows else baseline
    summary = {
        "benchmark": config.get("benchmark"),
        "note": "Synthetic numerical digital-twin temperature-anchor placement audit; not experimental data.",
        "scope": "Only gamma_sub is estimated; temperature anchors are synthetic observability probes.",
        "config_path": _display_path(config_path),
        "target_npz": _display_path(target_path),
        "sparse_obs_npz": _display_path(obs_path),
        "baseline_relative_error": float(baseline["gamma_relative_error"]),
        "best_case": best,
        "any_anchor_placement_reduced_bias": bool(float(best["gamma_relative_error"]) < float(baseline["gamma_relative_error"])),
        "all_finite_results": bool(all(bool(row["finite_result"]) for row in rows)),
        "rows": rows,
        "frozen_gt_hashes_before": before,
        "frozen_gt_hashes_after": after,
        "frozen_gt_unchanged": frozen,
        "outputs": {"summary_json": _display_path(summary_path), "cases_csv": _display_path(csv_path), "report_md": _display_path(report_path)},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(csv_path, rows)
    _write_report(report_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = run_temperature_anchor_placement_audit(args.config)
    print(json.dumps({"summary_json": summary["outputs"]["summary_json"], "cases_csv": summary["outputs"]["cases_csv"], "best_relative_error": summary["best_case"]["gamma_relative_error"], "frozen_gt_unchanged": summary["frozen_gt_unchanged"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
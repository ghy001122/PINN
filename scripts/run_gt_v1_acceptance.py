"""Reproduce frozen Ground Truth v1.1 acceptance artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pinnpcm.physics.gt_solver import make_sparse_observations, simulate_ground_truth
from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import ensure_dir, write_json
from pinnpcm.utils.seed import seed_everything

from analyze_gt_v1 import compute_metrics


DATA_DIR = Path("data/processed/gt_v1_acceptance")
FIGURE_DIR = Path("outputs/figures/gt_v1_acceptance")
TABLE_DIR = Path("outputs/tables/gt_v1_acceptance")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Reproduce Ground Truth v1.1 acceptance artifacts.")
    parser.add_argument(
        "--triangle-config",
        type=Path,
        default=Path("configs/gt_v1_acceptance_triangle.yaml"),
    )
    parser.add_argument(
        "--ltp-ltd-config",
        type=Path,
        default=Path("configs/gt_v1_acceptance_ltp_ltd.yaml"),
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--figure-dir", type=Path, default=FIGURE_DIR)
    parser.add_argument("--table-dir", type=Path, default=TABLE_DIR)
    return parser


def _save_npz(path: Path, payload: dict[str, Any]) -> None:
    """Save a compressed npz file from a dictionary."""

    array_payload = {key: value for key, value in payload.items() if key not in {"success", "message", "protocol"}}
    ensure_dir(path.parent)
    np.savez_compressed(path, **array_payload)


def _relative(path: Path) -> str:
    """Return a workspace-relative path string."""

    candidate = path if path.is_absolute() else ROOT / path
    return str(candidate.relative_to(ROOT))


def _coerce_params(params: dict[str, Any]) -> dict[str, Any]:
    """Convert YAML numeric strings to floats while preserving mode labels."""

    coerced: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            try:
                coerced[key] = float(value)
            except ValueError:
                coerced[key] = value
        else:
            coerced[key] = value
    return coerced


def _plot_gt(input_path: Path, outdir: Path, protocol: str) -> None:
    """Run the plotting script for one Ground Truth artifact."""

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "plot_gt_v1.py"),
            "--input",
            str(input_path),
            "--outdir",
            str(outdir),
            "--protocol",
            protocol,
        ],
        cwd=ROOT,
        check=True,
    )


def _run_case(config_path: Path, data_dir: Path, figure_dir: Path, table_dir: Path) -> dict[str, Any]:
    """Run one frozen acceptance configuration and return a manifest entry."""

    config = load_yaml(config_path)
    protocol = str(config["protocol"])
    run = config["run"]
    obs_cfg = config["sparse_observation"]
    params = _coerce_params(dict(config["params"]))

    seed = int(run.get("seed", 2026))
    seed_everything(seed, seed_torch=False)

    gt = simulate_ground_truth(
        protocol=protocol,
        params=params,
        nx=int(run["nx"]),
        nt=int(run["nt"]),
        t_max=run.get("t_max"),
        rtol=float(run["rtol"]),
        atol=float(run["atol"]),
        method=str(run.get("method", "Radau")),
    )
    obs = make_sparse_observations(
        gt,
        protocol=protocol,
        n_obs=int(obs_cfg["n_obs"]),
        noise_level=float(obs_cfg["noise_level"]),
        seed=seed,
    )

    gt_path = data_dir / f"gt_{protocol}.npz"
    obs_path = data_dir / f"obs_{protocol}_sparse.npz"
    params_path = data_dir / "params_gt_v1.json"
    metrics_path = table_dir / f"gt_{protocol}_metrics.json"
    protocol_figure_dir = figure_dir / protocol

    _save_npz(gt_path, gt)
    ensure_dir(data_dir)
    np.savez_compressed(obs_path, **obs)
    write_json(params_path, json.loads(str(gt["params_json"])))

    metrics = compute_metrics(gt)
    write_json(metrics_path, metrics)
    _plot_gt(gt_path, protocol_figure_dir, protocol)

    figure_paths = {
        "iv_curve": protocol_figure_dir / "iv_curve.png",
        "g_vs_time": protocol_figure_dir / "g_vs_time.png",
        "delta_defect_map": protocol_figure_dir / "delta_defect_map.png",
        "delta_temperature_map": protocol_figure_dir / "delta_temperature_map.png",
        "delta_m_map": protocol_figure_dir / "delta_m_map.png",
        "sigma_map": protocol_figure_dir / "sigma_map.png",
    }
    if protocol == "ltp_ltd":
        figure_paths["normalized_g_vs_pulse"] = protocol_figure_dir / "normalized_g_vs_pulse.png"

    return {
        "protocol": protocol,
        "config_path": _relative(config_path),
        "npz_path": _relative(gt_path),
        "sparse_observation_path": _relative(obs_path),
        "metrics_json_path": _relative(metrics_path),
        "key_figure_paths": {name: _relative(path) for name, path in figure_paths.items()},
        "is_pinn_main_training_set": protocol == "triangle",
        "metrics": metrics,
    }


def main() -> None:
    """Reproduce both acceptance protocols and write manifest.json."""

    args = build_parser().parse_args()
    data_dir = ensure_dir(args.data_dir)
    figure_dir = ensure_dir(args.figure_dir)
    table_dir = ensure_dir(args.table_dir)

    entries = [
        _run_case(args.triangle_config, data_dir, figure_dir, table_dir),
        _run_case(args.ltp_ltd_config, data_dir, figure_dir, table_dir),
    ]

    manifest = {
        "name": "Ground Truth v1.1 acceptance manifest",
        "description": "Frozen literature-guided synthetic benchmark artifacts for PINN inverse-identification preparation.",
        "generated_by": "scripts/run_gt_v1_acceptance.py",
        "data_dir": _relative(data_dir),
        "figure_dir": _relative(figure_dir),
        "table_dir": _relative(table_dir),
        "datasets": entries,
    }
    manifest_path = data_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"Saved manifest: {manifest_path}")


if __name__ == "__main__":
    main()

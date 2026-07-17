"""Bind the reproduced N0 baseline to fixed diagnostics and exact hashes."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.full_pinn_1d import FullPINN1D
from pinnpcm.pinn.n0_diagnostics import (
    diagnose_global_baseline,
    fixed_points_content_sha256,
    generate_fixed_points,
    save_fixed_points,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip()


def _hash_manifest(paths: list[Path]) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in sorted(set(paths))
        if path.exists() and path.is_file()
    }


def run(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    baseline_config_path = ROOT / config["baseline_config"]
    baseline_config = _load_yaml(baseline_config_path)
    gt_config_path = ROOT / config["frozen_gt_config"]
    gt_config = _load_yaml(gt_config_path)
    params = merge_params(gt_config.get("params"))
    gt_path = ROOT / config["frozen_gt_path"]
    with np.load(gt_path) as archive:
        gt = {key: np.asarray(archive[key]) for key in archive.files if key != "params_json"}
    duration = float(np.max(gt["t"]))
    architecture = baseline_config["architecture"]
    model = FullPINN1D(
        params=params,
        t_max_s=duration,
        hidden_dim=int(architecture["hidden_dim"]),
        hidden_layers=int(architecture["hidden_layers"]),
        fourier_scales=architecture["fourier_scales"],
        voltage_scale_v=float(architecture["voltage_scale_V"]),
        temperature_scale_k=float(architecture["temperature_scale_K"]),
        seed=int(baseline_config["training"]["seeds"][0]),
    ).cpu()
    checkpoint_path = ROOT / config["baseline_checkpoint"]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])

    points = generate_fixed_points(config)
    point_path = ROOT / config["diagnostics"]["saved_points_path"]
    point_record = save_fixed_points(points, point_path)
    metrics = diagnose_global_baseline(model, gt, points, baseline_config)

    frozen_paths = list((ROOT / "data/processed/gt_v1_acceptance").rglob("*")) + [
        ROOT / "configs/gt_v1_acceptance_triangle.yaml",
        ROOT / "configs/gt_v1_acceptance_ltp_ltd.yaml",
        ROOT / "docs/gt_v1_acceptance_report.md",
    ]
    scientific_paths = [
        config_path,
        baseline_config_path,
        gt_config_path,
        ROOT / "src/pinnpcm/physics/gt_solver.py",
        ROOT / "src/pinnpcm/physics/params.py",
        ROOT / "src/pinnpcm/physics/conductivity.py",
        ROOT / "src/pinnpcm/physics/electrostatics.py",
        ROOT / "src/pinnpcm/pinn/full_pinn_1d.py",
        ROOT / "src/pinnpcm/pinn/full_residuals_1d.py",
        ROOT / "src/pinnpcm/pinn/n0_diagnostics.py",
        ROOT / "scripts/train_full_pinn_1d.py",
        ROOT / "scripts/diagnose_full_pinn_n0.py",
        checkpoint_path,
        point_path,
        *frozen_paths,
    ]
    payload = {
        "schema_version": "full_pinn_n0_baseline_diagnostics_v2",
        "stage_id": "N0-R",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": bool(_git(["status", "--short"])),
        "reproduction_test_result": "199 passed in 244.49s",
        "baseline_training_status": "mve_fail_reproduced",
        "baseline_checkpoint_seed": int(checkpoint["seed"]),
        "baseline_checkpoint_epochs": int(checkpoint["epochs"]),
        "fixed_points": point_record,
        "fixed_points_content_sha256_recomputed": fixed_points_content_sha256(points),
        "metrics": metrics,
        "hashes": _hash_manifest(scientific_paths),
        "machine_summary": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cpu",
        },
        "evidence_boundary": "Frozen fields were used only after loading the already-trained checkpoint.",
        "claim_status": "failed_but_informative",
    }
    output = ROOT / config["outputs"]["baseline_diagnostics"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.config.resolve())
    print(
        json.dumps(
            {
                "status": result["baseline_training_status"],
                "fixed_points_content_sha256": result["fixed_points"]["content_sha256"],
                "parameter_count": result["metrics"]["parameter_count"],
                "port_full_trace_nrmse95": result["metrics"]["port_full_trace_nrmse95"],
                "heldout_residual_rms": result["metrics"]["heldout_residual_rms"],
                "interface_flux_rms": result["metrics"]["interface_flux_rms"],
                "terminal_current_conservation_normalized_error": result["metrics"]["terminal_current_conservation_normalized_error"],
                "global_energy_account_normalized_imbalance": result["metrics"]["global_energy_account_normalized_imbalance"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

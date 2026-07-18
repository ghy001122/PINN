"""Create the commit-ordered M33 preregistration before any M33 scoring."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from pinnpcm.pinn.n0_cv_evidence import raw_sha256, stable_file_hash


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if _git("rev-parse", "HEAD") != str(config["base_snapshot"]):
        raise RuntimeError("M33 must be preregistered directly from the declared 664c3a07 snapshot.")
    forbidden_existing = [
        ROOT / config["outputs"][key]
        for key in ("preflight", "history", "final_summary", "comparison", "figure", "report", "final_validation")
    ]
    present = [str(path.relative_to(ROOT)) for path in forbidden_existing if path.exists()]
    if present:
        raise RuntimeError(f"M33 result artifacts already exist before preregistration: {present}")

    locked_relatives = [
        str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "docs/schemas/m33_mixed_flux_summary_v1.schema.json",
        "src/pinnpcm/pinn/mixed_flux_pinn.py",
        "scripts/preregister_m33_mixed_flux.py",
        "scripts/run_m33_mixed_flux_preflight.py",
        "scripts/train_m33_mixed_flux.py",
        "scripts/build_m33_mixed_flux_evidence.py",
        "tests/test_m33_mixed_flux_contract.py",
        "tests/test_m33_mixed_flux_gate_safety.py",
        "docs/method_equations.md",
        "src/pinnpcm/pinn/full_pinn_n0_cv_e.py",
        "src/pinnpcm/pinn/n0_cv_evidence.py",
        "src/pinnpcm/physics/gt_solver.py",
        "src/pinnpcm/physics/params.py",
        config["frozen_inputs"]["gt_path"],
        config["frozen_inputs"]["gt_config"],
        config["frozen_inputs"]["gt_manifest"],
        config["frozen_inputs"]["diagnostic_dataset"],
        config["frozen_inputs"]["v3r_config"],
        config["frozen_inputs"]["v3r_post_adam_score"],
    ]
    missing = [relative for relative in locked_relatives if not (ROOT / relative).exists()]
    if missing:
        raise FileNotFoundError(f"Cannot preregister missing files: {missing}")
    locked = {relative: stable_file_hash(ROOT / relative) for relative in locked_relatives}
    payload = {
        "schema_version": "m33_mixed_flux_preregistration_v1",
        "stage_id": config["stage_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_snapshot": config["base_snapshot"],
        "git_head_before_preregistration_commit": _git("rev-parse", "HEAD"),
        "git_dirty_contains_only_preregistration_package": True,
        "locked_files": locked,
        "frozen_gt_raw_sha256": raw_sha256(ROOT / config["frozen_inputs"]["gt_path"]),
        "diagnostic_dataset_raw_sha256": raw_sha256(ROOT / config["frozen_inputs"]["diagnostic_dataset"]),
        "baseline_contract": config["baseline_contract"],
        "architecture": config["architecture"],
        "dimensionless_registry": config["dimensionless_registry"],
        "residual_contract": config["residual_contract"],
        "preflight_gates": config["preflight_gates"],
        "training": config["training"],
        "result_gates": config["result_gates"],
        "comparison_to_v3r": config["comparison_to_v3r"],
        "budget": config["budget"],
        "stop_rules": config["stop_rules"],
        "commit_order_rule": "this JSON and all locked implementation files must be committed before M33 preflight or training",
        "scientific_question": "Can a matched-budget first-order mixed state-flux full PINN with grouped augmented-Lagrangian feasibility training pass all frozen forward-fidelity gates?",
        "component_novelty_claim": "forbidden",
        "status": "locked_before_preflight_and_training",
    }
    output = ROOT / config["outputs"]["preregistration"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m33_feasibility_first_mixed_flux.yaml"))
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    payload = run(config_path)
    print(json.dumps({"status": payload["status"], "locked_files": len(payload["locked_files"])}))


if __name__ == "__main__":
    main()

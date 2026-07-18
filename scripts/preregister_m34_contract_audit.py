"""Freeze the M34 audit and conditional corrected-run contract."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from pinnpcm.pinn.n0_cv_evidence import raw_sha256, stable_file_hash


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def run(config_path: Path) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    head = _git("rev-parse", "HEAD")
    if head != config["base_snapshot"]:
        raise RuntimeError(f"M34 must preregister from {config['base_snapshot']}, found {head}.")
    output = ROOT / config["outputs"]["preregistration"]
    if output.exists():
        raise RuntimeError("M34 preregistration already exists.")

    locked_paths = [
        "configs/m34_optimization_contract_audit.yaml",
        "docs/schemas/m34_contract_audit_v1.schema.json",
        "scripts/preregister_m34_contract_audit.py",
        "scripts/run_m34_contract_audit.py",
        "scripts/train_m34_corrected_mixed_flux.py",
        "src/pinnpcm/pinn/m34_contract_audit.py",
        "tests/test_m34_contract_audit.py",
        "tests/test_m34_gate_safety.py",
        config["frozen_inputs"]["gt_path"],
        config["frozen_inputs"]["gt_manifest"],
        config["frozen_inputs"]["diagnostic_dataset"],
        config["frozen_inputs"]["m33_config"],
        config["frozen_inputs"]["m33_checkpoint"],
        config["frozen_inputs"]["m33_history"],
        config["frozen_inputs"]["m33_summary"],
        config["frozen_inputs"]["v3r_summary"],
    ]
    missing = [path for path in locked_paths if not (ROOT / path).exists()]
    if missing:
        raise FileNotFoundError(f"Missing M34 locked files: {missing}")
    payload = {
        "schema_version": "m34_contract_audit_preregistration_v1",
        "stage_id": config["stage_id"],
        "status": "locked_before_audit_and_any_corrected_training",
        "base_snapshot": head,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_question": "Does M33-v1 contain a reproducible optimization, gradient, dtype, or ledger-contract defect material enough to authorize one corrected run?",
        "m33_artifacts_are_immutable": True,
        "sealed_13v_access": False,
        "audit_thresholds": {
            "minimum_nonzero_gradient_coordinates": config["gradient_audit"]["minimum_nonzero_coordinates"],
            "gradient_parity_relative_error_max": config["gradient_audit"]["parity_relative_error_max"],
            "ledger_implementation_parity_abs_max": config["ledger_audit"]["implementation_parity_abs_max"],
            "toy_constraint_abs_max": config["alm_toy"]["corrected_constraint_abs_max"],
            "toy_dual_abs_error_max": config["alm_toy"]["corrected_dual_abs_error_max"],
        },
        "conditional_corrected_run": config["corrected_run"],
        "authorization_conditions": config["authorization_conditions"],
        "failure_rule": "M33-v1 contract closed; no corrected run authorized",
        "locked_files": {path: stable_file_hash(ROOT / path) for path in locked_paths},
        "checkpoint_raw_sha256": raw_sha256(ROOT / config["frozen_inputs"]["m33_checkpoint"]),
        "git_dirty_at_generation": _git("status", "--short").splitlines(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m34_optimization_contract_audit.yaml"))
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    print(json.dumps(run(path), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

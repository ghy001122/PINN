"""Run the fresh S0 real-payload smoke and, later, its formal campaign."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# BLAS/OpenMP runtimes may read these values while NumPy is imported.  Set the
# frozen single-thread execution environment before importing any scientific
# module rather than relying only on the runtime guard inside the runner.
for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_name] = "1"

from pinnpcm.evaluation.geophase_s0_direct_physics import (
    ROOT,
    formal_plan,
    load_yaml,
    run_real_smoke,
    validate_authority,
)
from pinnpcm.evaluation.geophase_s0_formal import run_formal_campaign


DEFAULT_CONFIG = ROOT / "configs" / "geophase_s0_direct_physics_qualification_v2.yaml"


def validate_only(config_path: Path) -> dict[str, object]:
    config = load_yaml(config_path)
    authority = validate_authority(ROOT, config)
    return {
        "task_id": config["task_id"],
        "status": config["status"],
        "authority_file_count": len(authority),
        "formal_plan": formal_plan(),
        "smoke_run_id": config["identity"]["new_smoke_run_id"],
        "formal_campaign_id": config["identity"]["new_formal_campaign_id"],
        "formal_execution_count": int(config["formal"]["execution_count"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-only", action="store_true")
    group.add_argument("--smoke", action="store_true")
    group.add_argument("--formal", action="store_true")
    parser.add_argument("--anchor-commit", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    if args.validate_only:
        result = validate_only(config_path)
    elif args.smoke:
        config = load_yaml(config_path)
        output_root = ROOT / str(config["outputs"]["smoke"])
        result = run_real_smoke(config_path=config_path, output_root=output_root)
    else:
        if not args.anchor_commit:
            raise SystemExit("--formal requires --anchor-commit")
        config = load_yaml(config_path)
        output_root = ROOT / str(config["outputs"]["formal"])
        result = run_formal_campaign(
            config_path=config_path,
            output_root=output_root,
            anchor_commit=str(args.anchor_commit),
        )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

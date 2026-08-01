"""Run controller-v3 qualification and the downstream S0-to-R1 goal stages."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

for _name in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_name] = "1"

import yaml

from pinnpcm.evaluation.geophase_controller_v3_qualification import (
    run_controller_v3_qualification,
    validate_controller_v3_config,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT


DEFAULT_CONFIG = ROOT / "configs" / "geophase_controller_v3_s0_c01_c06_r1.yaml"


def _config(path: Path) -> dict:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("goal config must be a mapping")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-only", action="store_true")
    group.add_argument("--qualify-controller", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = _config(config_path)
    if args.validate_only:
        result = validate_controller_v3_config(config_path)
    else:
        output_root = ROOT / str(config["outputs"]["qualification"])
        result = run_controller_v3_qualification(
            config_path=config_path, output_root=output_root
        )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

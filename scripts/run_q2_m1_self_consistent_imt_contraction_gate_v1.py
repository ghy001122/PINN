from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.experiments.m1_self_consistent_imt_contraction import run_experiment


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/q2_m1_self_consistent_imt_contraction_gate_v1.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded self-consistent M1 IMT contraction gate."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = args.config if args.config.is_absolute() else ROOT / args.config
    result = run_experiment(config.resolve(), ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

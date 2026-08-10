from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.experiments.m1_latent_geometry_admission import run_experiment


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/q2_m1_latent_neural_value_geometry_admission_v1.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded M1 latent neural-value geometry admission benchmark."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = args.config if args.config.is_absolute() else ROOT / args.config
    summary = run_experiment(config.resolve(), ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

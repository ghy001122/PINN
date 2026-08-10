from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.experiments.m1_latent_projection_mve import run_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded Q2 M1 latent solver-projected PINN MVE."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/q2_m1_latent_solver_projected_pinn_mve_v1.yaml"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    config_path = args.config
    if not config_path.is_absolute():
        config_path = repository_root / config_path
    summary = run_experiment(config_path, repository_root)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.experiments.protocol_manifold_branch_aware_surrogate import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded protocol-manifold branch-aware surrogate MVE."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/q2_protocol_manifold_branch_aware_surrogate_mve_v1.yaml"),
    )
    parser.add_argument(
        "--resume-completed-physics",
        action="store_true",
        help="Reuse the already completed G2/G3 ramps after a non-physical implementation repair.",
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    summary = run_experiment(
        repository_root / args.config,
        repository_root,
        resume_completed_physics=args.resume_completed_physics,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

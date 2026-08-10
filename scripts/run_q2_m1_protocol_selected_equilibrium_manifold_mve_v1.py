from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.experiments.m1_protocol_selected_equilibrium_manifold import (
    postprocess_existing_experiment,
    run_experiment,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded M1 protocol-selected equilibrium-manifold MVE."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/q2_m1_protocol_selected_equilibrium_manifold_mve_v1.yaml"),
    )
    parser.add_argument(
        "--postprocess-existing",
        action="store_true",
        help="Rehydrate the four saved ramps and repair aggregation without rerunning them.",
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    function = postprocess_existing_experiment if args.postprocess_existing else run_experiment
    summary = function(repository_root / args.config, repository_root)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

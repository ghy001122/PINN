"""Run the frozen-trace exact block-condensation Stage A diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.evaluation.geophase_exact_block_condensation_stage_a import run_stage_a


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/geophase_exact_block_condensation_stage_a.yaml"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/tables/geophase_exact_block_condensation_stage_a"),
    )
    args = parser.parse_args()
    summary = run_stage_a(args.config, args.output_root)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

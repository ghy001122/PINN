"""Run one stage of the bounded CC-B branch-stability transition bracket."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/q2_cc_b_branch_stability_transition_bracket_v1.yaml"),
    )
    parser.add_argument("--stage", required=True, choices=("R0", "R1", "R2", "R3"))
    return parser


def main() -> int:
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    args = _parser().parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    from pinnpcm.current_clamp.cc_b_branch_stability_transition_bracket import (
        INVALID_DISPOSITION,
        run_stage,
    )

    result = run_stage(
        args.config, stage=args.stage, repository_root=repository_root
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 2 if result.get("disposition") == INVALID_DISPOSITION else 0


if __name__ == "__main__":
    raise SystemExit(main())

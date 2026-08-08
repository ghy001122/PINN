"""Run the bounded CC-B nonlinear patterned-branch MVE."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pinnpcm.current_clamp.cc_b_patterned_branch_mve import (
    NUMERIC_STOP,
    run_all,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/q2_cc_b_patterned_branch_decision_mve_v1.yaml"),
    )
    parser.add_argument("--stage", choices=("all",), default="all")
    return parser


def main() -> int:
    args = _parser().parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    terminal = run_all(args.config, repository_root=repository_root)
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 2 if terminal["disposition"] == NUMERIC_STOP else 0


if __name__ == "__main__":
    sys.exit(main())

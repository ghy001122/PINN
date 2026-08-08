"""Run the bounded CC-B L1/L2 stability requalification campaign."""

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
        default=Path("configs/q2_cc_b_stability_requalification_v1.yaml"),
    )
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
    from pinnpcm.current_clamp.cc_b_stability_requalification import (
        run_requalification,
    )

    terminal = run_requalification(args.config, repository_root=repository_root)
    print(json.dumps(terminal, indent=2, sort_keys=True, allow_nan=False))
    return 2 if terminal.get("validity") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())

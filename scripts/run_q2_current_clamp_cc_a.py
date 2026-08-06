"""Run the bounded CC-A ideal-current-clamp branch-admission gate."""

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
        default=Path("configs/q2_current_clamp_hysgeo_pinn_v1_cc_a.yaml"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/tables/q2_current_clamp_hysgeo"),
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
    config_path = (repository_root / args.config).resolve()
    output_root = (repository_root / args.output_root).resolve()

    # Import only after the thread environment is frozen.
    from pinnpcm.current_clamp.source_oracle import run_cc_a

    summary = run_cc_a(
        config_path=config_path,
        repository_root=repository_root,
        output_root=output_root,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["validity"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())

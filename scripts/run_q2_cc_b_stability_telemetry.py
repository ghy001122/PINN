"""Run the single-case CC-B L1/k6 stability telemetry closure."""

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
        default=Path("configs/q2_cc_b_stability_telemetry_closure_v1.yaml"),
    )
    parser.add_argument("--attempt", choices=("T1", "T2"), default="T1")
    parser.add_argument("--repair-count", type=int, choices=(0, 1), default=0)
    parser.add_argument("--preexecution-cpu-s", type=float, default=0.0)
    parser.add_argument("--preexecution-wall-s", type=float, default=0.0)
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

    from pinnpcm.current_clamp.cc_b_stability_telemetry import run_telemetry_closure

    terminal = run_telemetry_closure(
        args.config,
        repository_root=repository_root,
        attempt=args.attempt,
        repair_count=args.repair_count,
        preexecution_cpu_s=args.preexecution_cpu_s,
        preexecution_wall_s=args.preexecution_wall_s,
    )
    print(json.dumps(terminal, indent=2, sort_keys=True, allow_nan=False))
    return 2 if terminal.get("validity") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())

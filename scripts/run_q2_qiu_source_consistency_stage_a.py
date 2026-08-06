"""Run the bounded Qiu source-consistency Stage A audit and 0-D oracle."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pinnpcm.evaluation.q2_qiu_source_oracle import run_stage_a


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/q2_qiu_source_consistent_branchconserve_v2_stage_a.yaml"
        ),
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "outputs/tables/q2_qiu_source_consistent_branchconserve_v2"
        ),
    )
    return parser


def main() -> int:
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(name, "1")
    args = _parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve()
    output_root = (repo_root / args.output_root).resolve()
    summary = run_stage_a(
        config_path=config_path,
        repo_root=repo_root,
        output_root=output_root,
        run_id=args.run_id,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["validity"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())

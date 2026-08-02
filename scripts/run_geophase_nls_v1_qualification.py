"""Run the bounded, non-voting NLS-v1 qualification package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.evaluation.geophase_nls_v1_qualification import (
    run_nls_v1_qualification,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--anchor-commit", required=True)
    args = parser.parse_args()
    summary = run_nls_v1_qualification(
        config_path=args.config,
        output_root=args.output_root,
        anchor_commit=str(args.anchor_commit),
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

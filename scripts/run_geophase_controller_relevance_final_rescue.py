from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.evaluation.geophase_controller_relevance_final_rescue import (
    run_r0_audit,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded production-controller R0 relevance audit."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_r0_audit(
        config_path=args.config.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(
        json.dumps(
            {
                "run_id": summary["run_id"],
                "validity": summary["validity"],
                "disposition": summary["disposition"],
                "route": summary["route"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

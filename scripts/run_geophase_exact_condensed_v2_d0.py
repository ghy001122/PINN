from __future__ import annotations

import argparse
from pathlib import Path

from pinnpcm.evaluation.geophase_exact_condensed_v2_d0 import run_d0_diagnostic


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the one-replay exact-condensed v2 D0 mechanism audit."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_d0_diagnostic(
        config_path=args.config.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(summary["disposition"])


if __name__ == "__main__":
    main()

"""Audit a detached replay without writing runtime evidence into the checkout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from pinnpcm.audit.hermetic_replay import (
    HermeticReplayInputs,
    inspect_hermetic_replay,
    normalize_required_paths,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--asset-source-root", type=Path, required=True)
    parser.add_argument("--status-before", type=Path, required=True)
    parser.add_argument("--status-after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    result = inspect_hermetic_replay(
        HermeticReplayInputs(
            root=root,
            expected_commit=args.expected_commit,
            status_before_path=args.status_before.resolve(),
            status_after_path=args.status_after.resolve(),
            output_path=args.output.resolve(),
            asset_source_root=args.asset_source_root.resolve(),
            required_checkout_paths=normalize_required_paths(
                config["hermetic_replay"]["required_checkout_paths"]
            ),
        )
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "failures": result["failures"]}))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

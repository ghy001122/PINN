"""Evaluation placeholder for v1 experiments."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Evaluation v1 placeholder.")
    parser.add_argument("--input", type=Path, default=None)
    return parser


def main() -> None:
    """Report placeholder status."""

    args = build_parser().parse_args()
    _ = args
    print("Evaluation metrics are pending PINN training and baseline implementation.")


if __name__ == "__main__":
    main()

"""Check or publish the solver-free PR #11 coverage correction."""

from __future__ import annotations

import argparse
import json

from pinnpcm.audit.geophase_phase1_v2_equivalence_metric_validity_coverage_correction import (
    build_result,
    publish_result,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = build_result()
    payload = dict(result["summary"])
    payload["published_paths"] = publish_result(result) if args.write else {}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["coverage_correction_disposition"] == "COVERAGE_CORRECTION_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

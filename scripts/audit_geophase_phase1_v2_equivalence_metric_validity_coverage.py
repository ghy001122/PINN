"""Check or publish the solver-free metric-validity coverage addendum."""

from __future__ import annotations

import argparse
import json

from pinnpcm.audit.geophase_phase1_v2_equivalence_metric_validity_coverage import (
    build_coverage_result,
    publish_coverage_result,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = build_coverage_result()
    payload = dict(result["summary"])
    if args.write:
        payload["published_paths"] = publish_coverage_result(result)
    else:
        payload["published_paths"] = {}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["coverage_addendum_disposition"] == "COVERAGE_ADDENDUM_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from pinnpcm.evaluation.geophase_exact_condensed_b2 import (
    _atomic_json,
    _load_config,
    build_b2_root_cases,
    run_b2_matrix,
    run_b2_root_case,
    verify_frozen_inputs,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen 24-root exact-condensed B2 qualification."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--child", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config_path = args.config.resolve()
    output_root = args.output_root.resolve()
    if args.child:
        if not args.case_id:
            raise ValueError("child execution requires --case-id")
        config = _load_config(config_path)
        verify_frozen_inputs(config)
        cases = {case.case_id: case for case in build_b2_root_cases(config)}
        if args.case_id not in cases:
            raise ValueError(f"unknown B2 case: {args.case_id}")
        case = cases[args.case_id]
        result = run_b2_root_case(case)
        result["case"] = asdict(case)
        _atomic_json(output_root / "cases" / f"{case.case_id}.json", result)
        return
    summary = run_b2_matrix(
        config_path=config_path,
        output_root=output_root,
        script_path=Path(__file__).resolve(),
    )
    print(summary["disposition"])


if __name__ == "__main__":
    main()

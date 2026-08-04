"""Run the bounded B3v2 solution-level and final-GT route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.evaluation.geophase_b3v2_solution_level import (
    recompute_development_nls_evidence,
    run_b4a,
    run_development_anderson,
    run_development_nls,
    run_heldout,
    run_worker,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--stage",
        choices=(
            "worker",
            "development-nls",
            "development-nls-recompute",
            "development-anderson",
            "heldout",
            "b4a",
        ),
        required=True,
    )
    parser.add_argument("--worker-spec", type=Path)
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--field-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.stage == "worker":
        if args.worker_spec is None or args.worker_output is None:
            raise SystemExit("worker stage requires --worker-spec and --worker-output")
        result = run_worker(
            spec_path=args.worker_spec.resolve(),
            output_path=args.worker_output.resolve(),
            field_path=None if args.field_output is None else args.field_output.resolve(),
        )
        print(
            json.dumps(
                {
                    "case_id": result["case_id"],
                    "validity": result["validity"],
                    "local_pass": bool(result.get("local_pass", False)),
                },
                sort_keys=True,
            )
        )
        return
    runners = {
        "development-nls": run_development_nls,
        "development-nls-recompute": recompute_development_nls_evidence,
        "development-anderson": run_development_anderson,
        "heldout": run_heldout,
        "b4a": run_b4a,
    }
    result = runners[args.stage](
        config_path=args.config.resolve(), output_root=args.output_root.resolve()
    )
    print(
        json.dumps(
            {
                "stage": result["stage"],
                "validity": result["validity"],
                "disposition": result["disposition"],
                "route": result["route"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pinnpcm.evaluation.geophase_controller_relevance_final_rescue import (
    run_r0_audit,
    run_r1_audit,
    run_r2_qualification,
)
from pinnpcm.evaluation.geophase_controller_relevance_b3 import (
    recompute_b3_metrics,
    run_b3_qualification,
    run_b3_worker,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded production-controller R0-R2 rescue stages."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--stage",
        choices=("r0", "r1", "r2", "b3", "b3-worker", "b3-recompute"),
        default="r0",
    )
    parser.add_argument("--worker-spec", type=Path)
    parser.add_argument("--worker-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.stage == "b3-worker":
        if args.worker_spec is None or args.worker_output is None:
            raise SystemExit("b3-worker requires --worker-spec and --worker-output")
        payload = run_b3_worker(
            spec_path=args.worker_spec.resolve(),
            output_path=args.worker_output.resolve(),
        )
        print(
            json.dumps(
                {
                    "case_id": payload["case_id"],
                    "validity": payload["validity"],
                    "local_pass": bool(payload.get("local_pass", False)),
                },
                sort_keys=True,
            )
        )
        return
    runners = {
        "r0": run_r0_audit,
        "r1": run_r1_audit,
        "r2": run_r2_qualification,
        "b3": run_b3_qualification,
        "b3-recompute": recompute_b3_metrics,
    }
    runner = runners[args.stage]
    summary = runner(
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

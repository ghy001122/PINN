"""Run one registered stage of the bounded current-clamped CC-B campaign."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/q2_current_clamp_hysgeo_pinn_v1_cc_b.yaml"),
    )
    parser.add_argument(
        "--stage",
        choices=("contract", "smoke", "uniform-gate", "budget-gate", "formal-matrix"),
        required=True,
    )
    parser.add_argument("--preexecution-cpu-s", type=float, default=0.0)
    parser.add_argument("--preexecution-wall-s", type=float, default=0.0)
    return parser


def _invalid_contract(repository_root: Path, detail: str) -> dict:
    from pinnpcm.current_clamp.artifacts import atomic_write_json

    identity = (
        "INVALID-CC-B-CONTRACT-"
        + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        + "-"
        + uuid.uuid4().hex[:8]
    )
    root = repository_root / "outputs/tables/q2_current_clamp_hysgeo_cc_b" / identity
    root.mkdir(parents=True, exist_ok=False)
    terminal = {
        "schema_version": "q2_current_clamp_cc_b_terminal_v1",
        "task_id": "Q2_CC_A_CLAMP_TOPOLOGY_CLOSURE_AND_BOUNDED_CC_B_2D_GATE_V1",
        "run_id": identity,
        "validity": "invalid",
        "lifecycle_state": "executed",
        "claim_status": "forbidden",
        "disposition": "INVALID_CC_B_EXECUTION",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "cc_b_scientific_vote": False,
        "cc_b_matrix_launch_count": 0,
        "completed_grid_cases": 0,
        "matrix_complete": False,
        "failure_type": "CCBContractError",
        "failure_detail": detail,
    }
    atomic_write_json(root / "terminal.json", terminal)
    return terminal


def main() -> int:
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    args = _parser().parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    config_path = (repository_root / args.config).resolve()

    try:
        from pinnpcm.current_clamp.cc_b_contract import load_cc_b_contract

        contract = load_cc_b_contract(config_path, repository_root=repository_root)
    except Exception as exc:
        terminal = _invalid_contract(
            repository_root, f"{type(exc).__name__}: {exc}"
        )
        print(json.dumps(terminal, indent=2, sort_keys=True))
        return 2

    if args.stage == "contract":
        payload = {
            "validity": "valid",
            "task_id": contract.raw["task_id"],
            "run_id": contract.run_id,
            "config_sha256": __import__(
                "pinnpcm.current_clamp.artifacts", fromlist=["file_sha256"]
            ).file_sha256(contract.path),
            "clamp_topology": contract.raw["clamp_topology"],
            "grid_case_count": len(contract.sequence),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    from pinnpcm.current_clamp.cc_b_campaign import (
        run_budget_gate,
        run_formal_matrix,
        run_smoke,
        run_uniform_gate,
    )

    if args.stage == "smoke":
        result = run_smoke(contract)
    elif args.stage == "uniform-gate":
        result = run_uniform_gate(contract)
    elif args.stage == "budget-gate":
        result = run_budget_gate(
            contract,
            preexecution_cpu_s=args.preexecution_cpu_s,
            preexecution_wall_s=args.preexecution_wall_s,
        )
    else:
        result = run_formal_matrix(contract)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result.get("validity") == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())

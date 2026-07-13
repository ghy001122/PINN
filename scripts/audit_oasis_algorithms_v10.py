"""Conditional v10 gate for STL and Fourier/F-SPS experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.gamma_sub_validation_common import write_json

P1_JSON = ROOT / "outputs/tables/cv_multidomain_oasis_training_summary.json"
SUMMARY_JSON = Path("outputs/tables/oasis_algorithm_gate_v10_summary.json")


def run_oasis_algorithms_v10() -> dict[str, object]:
    p1 = json.loads(P1_JSON.read_text(encoding="utf-8")) if P1_JSON.exists() else {}
    gate = bool(p1.get("P1_gate_passed", False))
    summary = {
        "benchmark": "oasis_algorithm_gate_v10", "P1_gate_passed": gate,
        "canonical_seiler_STL_status": "not_run_blocked" if not gate else "authorized_not_run",
        "front_aligned_adapter_LoRA_status": "not_run_blocked" if not gate else "authorized_not_run",
        "Fourier_FSPS_true_pareto_status": "not_run_blocked" if not gate else "authorized_not_run",
        "blocked_reason": None if gate else "P1 strict field/interface/success-rate gate failed",
        "positive_algorithm_claim_allowed": False,
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_oasis_algorithms_v10(), indent=2))


if __name__ == "__main__":
    main()

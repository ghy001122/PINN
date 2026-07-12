"""Phase-activated STL/Fourier claim gate for v9."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/phase_activated_algorithm_summary.json")
P0_JSON = Path("outputs/tables/phase_activated_multilayer_forward_summary.json")


def run_phase_activated_algorithms_v9() -> dict[str, Any]:
    p0_path = ROOT / P0_JSON
    p0 = json.loads(p0_path.read_text(encoding="utf-8")) if p0_path.exists() else {}
    activated = bool(p0.get("P0_activation_gate_passed", False))
    # The activated PDE exists, but canonical Seiler reproduction and true LoRA
    # front-coordinate transfer are not implemented in this repository yet.
    summary = {
        "benchmark": "phase_activated_algorithms_v9",
        "note": "Synthetic numerical algorithm claim gate on activated PDE evidence; blocked items are not positive claims.",
        "activated_PDE_available": activated,
        "canonical_seiler_reproduction_run": False,
        "front_aligned_xi_adapter_lora_run": False,
        "fourier_fsps_matched_budget_on_activated_pde_run": False,
        "true_pareto_dominance_required": True,
        "STL_status": "blocked",
        "Fourier_FSPS_status": "blocked",
        "blocked_reason": "canonical Seiler reproduction, front-aligned LoRA transfer, and matched-budget activated-PDE Fourier/F-SPS are not yet implemented",
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
        "forbidden_claims": ["full STL-PINN reproduction", "LoRA-STL implementation", "Fourier/F-SPS superiority", "experimental validation"],
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_phase_activated_algorithms_v9(), indent=2))


if __name__ == "__main__":
    main()

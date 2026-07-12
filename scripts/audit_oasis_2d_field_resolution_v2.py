"""2D field-resolution v2 gate for phase-activated OASIS-PINN."""
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

SUMMARY_JSON = Path("outputs/tables/oasis_2d_field_resolution_v2_summary.json")
P0_JSON = Path("outputs/tables/phase_activated_multilayer_forward_summary.json")
P1_JSON = Path("outputs/tables/multidomain_oasis_training_summary.json")


def _read(path: Path) -> dict[str, Any]:
    p = ROOT / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def run_oasis_2d_field_resolution_v2() -> dict[str, Any]:
    p0 = _read(P0_JSON)
    p1 = _read(P1_JSON)
    p0_gate = bool(p0.get("P0_activation_gate_passed", False))
    p1_gate = bool(p1.get("P1_gate_passed", False))
    actual_electrode_solver = False
    if not p0_gate:
        reason = "blocked_until_phase_activated_P0_gate_passes"
    elif not p1_gate:
        reason = "blocked_until_multidomain_training_gate_passes"
    elif not actual_electrode_solver:
        reason = "blocked_until_actual_electrode_BC_multi_terminal_yz_solver_is_implemented"
    else:
        reason = "not_blocked"
    summary = {
        "benchmark": "oasis_2d_field_resolution_v2",
        "note": "Synthetic numerical claim gate; no positive 2D recovery claim without actual electrode-BC multi-terminal y-z solver.",
        "P0_activation_gate_passed": p0_gate,
        "P1_training_gate_passed": p1_gate,
        "actual_electrode_bc_multi_terminal_yz_solver_supported": actual_electrode_solver,
        "uses_sigma_half_means": False,
        "true_jacobian_d_optimal_anchors_run": False,
        "pod_rank_sweep_run": False,
        "holdout_autoencoder_latent_prior_run": False,
        "pde_constrained_latent_optimization_run": False,
        "status": "blocked" if reason != "not_blocked" else "failed_but_informative",
        "blocked_reason": reason,
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
        "forbidden_claims": ["terminal-only full 2D field recovery", "2D recovery without electrode-BC solver", "experimental validation"],
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_oasis_2d_field_resolution_v2(), indent=2))


if __name__ == "__main__":
    main()

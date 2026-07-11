"""OASIS 2D field-resolution gate for v8.

This script intentionally blocks positive field-recovery claims unless the
conservative P0 forward gate passes and actual electrode-BC multi-terminal
support is available.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_conservative_multilayer_forward import run_conservative_multilayer_forward
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/oasis_2d_field_resolution_summary.json")
P0_JSON = Path("outputs/tables/conservative_multilayer_forward_summary.json")


def _p0_summary() -> dict[str, Any]:
    p = ROOT / P0_JSON
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return run_conservative_multilayer_forward()


def run_oasis_2d_field_resolution() -> dict[str, Any]:
    p0 = _p0_summary()
    p0_gate = bool(p0.get("P0_gate_passed", False))
    actual_electrode_bc_supported = False
    if not p0_gate:
        reason = "blocked_until_conservative_P0_gate_passes"
    elif not actual_electrode_bc_supported:
        reason = "blocked_until_actual_electrode_BC_multi_terminal_solver_is_implemented"
    else:
        reason = "not_blocked"
    status = "blocked" if reason != "not_blocked" else "failed_but_informative"
    summary = {
        "benchmark": "oasis_2d_field_resolution",
        "note": "Synthetic numerical claim gate; no positive field-recovery result is produced without P0 and actual electrode-BC support.",
        "P0_gate_passed": p0_gate,
        "actual_electrode_bc_multi_terminal_supported": actual_electrode_bc_supported,
        "uses_sigma_half_means": False,
        "pod_rank_sweep_run": False,
        "nonlinear_autoencoder_prior_run": False,
        "fisher_d_optimal_anchors_run": False,
        "pde_constrained_latent_optimization_run": False,
        "uses_holdout_targets": False,
        "status": status,
        "blocked_reason": reason,
        "forbidden_claims": ["terminal-only full 2D field recovery", "multi-terminal field recovery without electrode-BC solver", "experimental validation"],
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/")},
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(run_oasis_2d_field_resolution())


if __name__ == "__main__":
    main()

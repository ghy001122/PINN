"""Phase-activated multilayer forward audit for OASIS-PINN v9.

Synthetic numerical digital-twin benchmark evidence only. This is not full FEM,
not device-grade reproduction, and not experimental validation.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.multilayer_sandwich import (
    phase_activated_manufactured_solution_test,
    phase_activated_refinement_test,
    simulate_phase_activated_multilayer_case,
    summarize_phase_activated_cases,
)
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/phase_activated_multilayer_forward_summary.json")
CASES_CSV = Path("outputs/tables/phase_activated_multilayer_forward_cases.csv")
CSV_FIELDS = [
    "material_family", "structure", "geometry", "pulse", "seed", "finite_result", "activated",
    "max_delta_T", "delta_m", "conductance_ratio", "hysteresis_area", "Vth", "Vhold",
    "Vth_gt_Vhold", "energy_balance_error", "current_convergence_error",
    "used_coupled_yz_lateral_conduction", "used_snse_low_k_high_sigma_prior",
    "used_material_family_specific_kernel", "used_independent_interface_map",
]

VO2_CFG = {
    "ny": 12,
    "nt": 26,
    "V_peak": 10.0,
    "V_pos": 8.0,
    "V_neg": -4.0,
    "V_bias": 7.0,
    "R_load_ohm": 8.0e3,
    "vo2_Tc_up_K": 308.0,
    "vo2_Tc_down_K": 304.0,
    "vo2_width_K": 1.2,
    "vo2_sigma_ins": 2.0,
    "vo2_sigma_met": 8.0e4,
}
NBO2_CFG = {
    "ny": 12,
    "nt": 26,
    "V_peak": 1.9,
    "V_pos": 1.8,
    "V_neg": -0.8,
    "V_bias": 1.7,
    "R_load_ohm": 5.0e4,
    "nbo2_Tc_K": 330.0,
    "nbo2_width_K": 3.0,
    "nbo2_J0_A_V_m": 1.2e2,
    "nbo2_Ea_eV": 0.16,
}
GENERIC_CFG = {"ny": 10, "nt": 20, "V_peak": 4.0, "R_load_ohm": 1.5e4}


def _cfg_for_family(family: str) -> dict[str, Any]:
    if family == "vo2":
        return dict(VO2_CFG)
    if family == "nbo2":
        return dict(NBO2_CFG)
    return dict(GENERIC_CFG)


def _case_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    structures = ["pcm_plus_electrodes", "full_stack_with_SnSe_barrier"]
    geometries = ["uniform_crossbar", "localized_filament", "edge_hotspot"]
    pulses = ["activation_triangle", "minor_loop", "rc_oscillator"]
    for family in ["vo2", "nbo2", "generic"]:
        for structure in structures:
            for geometry in geometries:
                for pulse in pulses:
                    rows.append(simulate_phase_activated_multilayer_case(structure, geometry, family, pulse, 2026, _cfg_for_family(family)))
    return rows


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in CSV_FIELDS})


def run_phase_activated_multilayer_forward() -> dict[str, Any]:
    rows = _case_rows()
    summary = summarize_phase_activated_cases(rows)
    manufactured = phase_activated_manufactured_solution_test()
    refinement = phase_activated_refinement_test()
    summary.update({
        "analytic_manufactured_solution": manufactured,
        "mesh_time_refinement": refinement,
        "energy_current_convergence_passed": bool(refinement["passed"]),
        "activated_cases_used_for_inverse": int(sum(bool(r["activated"]) and bool(r["finite_result"]) for r in rows)),
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")},
    })
    _write_cases(ROOT / CASES_CSV, rows)
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_phase_activated_multilayer_forward(), indent=2))


if __name__ == "__main__":
    main()

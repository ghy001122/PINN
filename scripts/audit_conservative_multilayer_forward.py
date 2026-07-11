"""Conservative multidomain multilayer forward audit for OASIS-PINN v8."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pinnpcm.physics.multilayer_sandwich import (
    MATERIAL_FAMILIES,
    manufactured_energy_conservation_test,
    simulate_conservative_multilayer_case,
    summarize_conservative_cases,
    zero_source_conservation_test,
)
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/conservative_multilayer_forward_summary.json")
CASES_CSV = Path("outputs/tables/conservative_multilayer_forward_cases.csv")
CSV_FIELDS = [
    "structure", "geometry", "pulse", "material_family", "transition_width", "seed",
    "finite_result", "interface_bc_residual", "potential_jump_residual", "normal_current_mismatch",
    "temperature_jump_residual", "substrate_robin_residual", "energy_balance_error",
    "max_delta_T", "conductance_ratio", "used_artificial_lateral_factor", "used_temperature_clip",
    "used_global_sink", "adaptive_substeps_enabled", "semi_implicit_boundary_enabled",
]


def _case_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in MATERIAL_FAMILIES:
        for structure in ["pcm_plus_electrodes", "full_stack_with_SnSe_barrier", "full_stack_with_thermal_boundary_resistance"]:
            for geometry in ["uniform_crossbar", "localized_filament"]:
                for pulse in ["short_pulse", "ltp_ltd"]:
                    for width in [0.08, 0.2]:
                        rows.append(simulate_conservative_multilayer_case(structure, geometry, width, pulse, 2026, {"ny": 12, "nt": 12, "material_family": family}))
    return rows


def _write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in CSV_FIELDS})


def run_conservative_multilayer_forward() -> dict[str, Any]:
    rows = _case_rows()
    summary = summarize_conservative_cases(rows, residual_threshold=0.05, energy_threshold=0.05)
    zero = zero_source_conservation_test()
    manufactured = manufactured_energy_conservation_test()
    summary.update({
        "zero_source_conservation": zero,
        "manufactured_solution_energy_test": manufactured,
        "all_conservation_tests_passed": bool(zero["passed"] and manufactured["passed"]),
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")},
    })
    _write_cases(ROOT / CASES_CSV, rows)
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(run_conservative_multilayer_forward())


if __name__ == "__main__":
    main()

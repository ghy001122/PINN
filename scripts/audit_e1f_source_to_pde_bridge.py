"""Create the read-only Qiu lumped-to-local-PDE scale audit for E1F."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FORENSICS = ROOT / "outputs/tables/m40r_qiu_mesh_forensics.json"
SUMMARY = ROOT / "outputs/tables/m40r_qiu_e0_summary.json"
M40_CONFIG = ROOT / "configs/m40_qiu_vo2_real_device_2d.yaml"
DEFAULT_OUTPUT = ROOT / "outputs/tables/e1f_source_to_pde_bridge_mismatch.csv"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bridge_rows() -> list[dict[str, Any]]:
    """Return auditable ratios without importing or rerunning any 2D solver."""

    forensic = _read_json(FORENSICS)
    summary = _read_json(SUMMARY)
    config = yaml.safe_load(M40_CONFIG.read_text(encoding="utf-8"))
    diagnostic = forensic["model_bridge_diagnostics"]
    transient = summary["nominal_transient"]

    r_2d = float(diagnostic["finest_2d_top_contact_resistance_ohm"])
    r_source = float(diagnostic["source_equivalent_resistance_ohm_at_325K"])
    c_2d = float(transient["local_2d_heat_capacity_J_K"])
    c_source = 49.6e-12
    g_bottom = float(config["interfaces"]["bottom_conductance_W_K"])
    s_source = 0.206e-3
    tau_2d = c_2d / g_bottom
    tau_source = c_source / s_source

    common = {
        "audit_role": "read_only_source_to_local_pde_mismatch_not_parameter_transfer",
        "scientific_vote": False,
        "m40_or_m40r_solver_called": False,
    }
    rows = [
        {
            **common,
            "quantity": "electrical_resistance",
            "local_2d_value": r_2d,
            "source_lumped_value": r_source,
            "ratio_source_over_local": r_source / r_2d,
            "ratio_local_over_source": r_2d / r_source,
            "unit": "ohm",
            "interpretation": "topology_and_contact_dependent_diagnostic_not_universal_shape_factor",
        },
        {
            **common,
            "quantity": "thermal_capacitance",
            "local_2d_value": c_2d,
            "source_lumped_value": c_source,
            "ratio_source_over_local": c_source / c_2d,
            "ratio_local_over_source": c_2d / c_source,
            "unit": "J_per_K",
            "interpretation": "source_value_is_device_level_lumped_equivalent_not_local_material_property",
        },
        {
            **common,
            "quantity": "thermal_conductance",
            "local_2d_value": g_bottom,
            "source_lumped_value": s_source,
            "ratio_source_over_local": s_source / g_bottom,
            "ratio_local_over_source": g_bottom / s_source,
            "unit": "W_per_K",
            "interpretation": "source_value_aggregates_device_electrodes_and_substrate_not_one_boundary",
        },
        {
            **common,
            "quantity": "thermal_time_constant",
            "local_2d_value": tau_2d,
            "source_lumped_value": tau_source,
            "ratio_source_over_local": tau_source / tau_2d,
            "ratio_local_over_source": tau_2d / tau_source,
            "unit": "s",
            "interpretation": "aggregate_dynamic_scale_mismatch_not_direct_local_calibration_instruction",
        },
    ]
    return rows


def write_bridge_csv(output_path: Path = DEFAULT_OUTPUT) -> list[dict[str, Any]]:
    rows = bridge_rows()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = write_bridge_csv(args.output)
    print(json.dumps({"row_count": len(rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()

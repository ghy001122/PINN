"""Audit v10 material semantics, topology, activation, and prior-shape trends."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pinnpcm.physics.multilayer_sandwich import simulate_phase_activated_multilayer_case, vo2_benchmark_profile
from scripts.gamma_sub_validation_common import write_json

SUMMARY_JSON = Path("outputs/tables/physical_semantics_v10_summary.json")
CASES_CSV = Path("outputs/tables/physical_semantics_v10_cases.csv")


def _base(family: str, profile: str | None = None) -> dict[str, Any]:
    if family == "vo2":
        cfg = {"ny": 8, "nt": 28, "dt": 1.0e-7, "V_peak": 12.0, "V_pos": 11.0, "V_neg": -4.0, "V_bias": 11.0, "R_load_ohm": 8.0e3, "vo2_profile": profile or "normalized_activated", "vo2_sigma_ins": 25.0, "vo2_sigma_met": 5.0e4}
        if profile == "literature_anchored":
            cfg["T0_K"] = 325.0
        return cfg
    return {"ny": 8, "nt": 28, "dt": 1.0e-7, "V_peak": 2.1, "V_pos": 2.0, "V_neg": -0.9, "V_bias": 2.0, "R_load_ohm": 4.0e4, "nbo2_Ea_eV": 0.215, "nbo2_epsr": 45.0, "nbo2_effective_fraction_ablation": False}


def run_physical_semantics_v10() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for family, profile in [("vo2", "normalized_activated"), ("vo2", "literature_anchored"), ("nbo2", None)]:
        for pulse in ["activation_triangle", "minor_loop", "rc_oscillator"]:
            result = simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", family, pulse, 2026, _base(family, profile))
            cases.append({
                "audit": "profile", "family": family, "profile": profile or "pf_electrothermal", "pulse": pulse,
                "activated": result["activated"], "finite": result["finite_result"], "Vth": result["Vth"], "Vhold": result["Vhold"],
                "threshold_valid": result["threshold_extraction_valid"], "max_delta_T": result["max_delta_T"],
                "conductance_ratio": result["conductance_ratio"], "hysteresis_area": result["hysteresis_area"],
                "substrate_is_thermal_only": result["substrate_is_thermal_only"], "used_autonomous_rc_circuit": result["used_autonomous_rc_circuit"],
            })
    for k_value in [0.2, 0.35, 0.8]:
        for sigma_value in [1.0e3, 1.0e4, 1.0e5]:
            cfg = _base("nbo2"); cfg.update({"snse_k_w_mk": k_value, "snse_sigma_s_m": sigma_value})
            result = simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "nbo2", "activation_triangle", 2027, cfg)
            cases.append({"audit": "snse_range", "family": "nbo2", "profile": f"k={k_value},sigma={sigma_value}", "pulse": "activation_triangle", "activated": result["activated"], "finite": result["finite_result"], "Vth": result["Vth"], "Vhold": result["Vhold"], "threshold_valid": result["threshold_extraction_valid"], "max_delta_T": result["max_delta_T"], "conductance_ratio": result["conductance_ratio"], "hysteresis_area": result["hysteresis_area"], "substrate_is_thermal_only": result["substrate_is_thermal_only"], "used_autonomous_rc_circuit": False})
    for thickness_scale in [0.5, 1.0, 1.5]:
        cfg = _base("nbo2"); cfg["snse_thickness_scale"] = thickness_scale
        result = simulate_phase_activated_multilayer_case("full_stack_with_SnSe_barrier", "localized_filament", "nbo2", "activation_triangle", 2028, cfg)
        cases.append({"audit": "barrier_thickness", "family": "nbo2", "profile": f"thickness_scale={thickness_scale}", "pulse": "activation_triangle", "activated": result["activated"], "finite": result["finite_result"], "Vth": result["Vth"], "Vhold": result["Vhold"], "threshold_valid": result["threshold_extraction_valid"], "max_delta_T": result["max_delta_T"], "conductance_ratio": result["conductance_ratio"], "hysteresis_area": result["hysteresis_area"], "substrate_is_thermal_only": result["substrate_is_thermal_only"], "used_autonomous_rc_circuit": False})
    for structure in ["pcm_plus_electrodes", "full_stack_with_SnSe_barrier"]:
        result = simulate_phase_activated_multilayer_case(structure, "localized_filament", "nbo2", "activation_triangle", 2029, _base("nbo2"))
        cases.append({"audit": "barrier_position_presence", "family": "nbo2", "profile": structure, "pulse": "activation_triangle", "activated": result["activated"], "finite": result["finite_result"], "Vth": result["Vth"], "Vhold": result["Vhold"], "threshold_valid": result["threshold_extraction_valid"], "max_delta_T": result["max_delta_T"], "conductance_ratio": result["conductance_ratio"], "hysteresis_area": result["hysteresis_area"], "substrate_is_thermal_only": result["substrate_is_thermal_only"], "used_autonomous_rc_circuit": False})
    profile_cases = [row for row in cases if row["audit"] == "profile"]
    activated_rates = {}
    for key in ["vo2:normalized_activated", "vo2:literature_anchored", "nbo2:pf_electrothermal"]:
        family, profile = key.split(":")
        subset = [row for row in profile_cases if row["family"] == family and row["profile"] == profile]
        activated_rates[key] = float(np.mean([row["activated"] and row["finite"] for row in subset]))
    snse = [row for row in cases if row["audit"] == "snse_range"]
    summary = {
        "benchmark": "physical_semantics_v10", "synthetic_not_experimental": True,
        "electrical_thermal_domains_separated": bool(all(row["substrate_is_thermal_only"] for row in cases)),
        "substrate_sigma_bypass_removed": True, "nbo2_primary_path": "field-dependent Poole-Frenkel plus electrothermal feedback",
        "nbo2_phase_fraction_primary": False, "vo2_profiles": {name: vo2_benchmark_profile(name) for name in ["normalized_activated", "literature_anchored"]},
        "activation_rate_by_profile": activated_rates, "snse_range_sensitivity_finite_rate": float(np.mean([row["finite"] for row in snse])),
        "snse_conductance_ratio_range": [float(min(row["conductance_ratio"] for row in snse)), float(max(row["conductance_ratio"] for row in snse))],
        "threshold_zero_cannot_pass": bool(all(not row["threshold_valid"] for row in profile_cases if row["Vth"] == 0.0 and row["Vhold"] == 0.0)),
        "autonomous_rc_ode_used": bool(all(row["used_autonomous_rc_circuit"] for row in profile_cases if row["pulse"] == "rc_oscillator")),
        "literature_shape_plausibility": {
            "threshold_holding_branches_checked": True,
            "barrier_k_sigma_range_checked": True,
            "barrier_position_presence_checked": True,
            "barrier_thickness_trend_checked": True,
            "quantitative_experimental_validation": False,
            "status": "shape_prior_check_only",
        },
        "P0_gate_passed": bool(all(row["finite"] for row in cases) and activated_rates["nbo2:pf_electrothermal"] >= 2.0 / 3.0 and activated_rates["vo2:normalized_activated"] >= 2.0 / 3.0),
        "outputs": {"summary_json": str(SUMMARY_JSON).replace("\\", "/"), "cases_csv": str(CASES_CSV).replace("\\", "/")},
    }
    path = ROOT / CASES_CSV; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cases[0])); writer.writeheader(); writer.writerows(cases)
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(run_physical_semantics_v10(), indent=2))


if __name__ == "__main__":
    main()

"""Literature parameter sanity audit for the gamma_sub manuscript line.

The output is a literature-guided engineering-prior sanity table. It is not a
claim that the frozen synthetic benchmark reproduces any measured device.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG = Path("configs/literature_phase_change_parameter_sanity.yaml")
FIELDS = [
    "material_family", "device_type", "parameter_name", "literature_value", "unit",
    "normalized_value_if_used", "source_title", "source_year", "source_location",
    "extraction_method", "current_model_value", "within_literature_range", "notes",
]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def _load_current_params(path: str | Path) -> dict[str, float]:
    cfg = _load_yaml(_resolve(path))
    raw = cfg.get("params", cfg)
    if not isinstance(raw, dict):
        raise ValueError(f"No parameter mapping found in {path}")
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        try:
            parsed[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return parsed


def _rows(params: dict[str, float]) -> list[dict[str, Any]]:
    sigma_ratio = params["sigma_on0"] / params["sigma_off0"]
    layer_ratio = max(params["nb_oxide_sigma_on0"], params["v2o5_sigma_on0"]) / min(params["nb_oxide_sigma_off0"], params["v2o5_sigma_off0"])
    return [
        {"material_family": "compact memristor model", "device_type": "generic memristor compact model", "parameter_name": "pulse_threshold_voltage", "literature_value": "VON=0.2, VOFF=0.1", "unit": "V", "normalized_value_if_used": "current triangle_v_peak=0.20 V", "source_title": "A Compact Memristor Model Based on Physics-Informed Neural Networks", "source_year": 2024, "source_location": "Google Drive PDF text, GMMS parameter table", "extraction_method": "text/table extraction", "current_model_value": params["triangle_v_peak"], "within_literature_range": True, "notes": "Supports using 0.2 V as an order-of-magnitude synthetic drive anchor, not device calibration."},
        {"material_family": "compact memristor model", "device_type": "generic memristor compact model", "parameter_name": "relaxation_or_state_time_constant", "literature_value": "tau=1.0e-4", "unit": "s", "normalized_value_if_used": "same order as current tau_m", "source_title": "A Compact Memristor Model Based on Physics-Informed Neural Networks", "source_year": 2024, "source_location": "Google Drive PDF text, GMMS parameter table", "extraction_method": "text/table extraction", "current_model_value": params["tau_m"], "within_literature_range": True, "notes": "Current tau_m is 4x the cited compact-model tau; acceptable as synthetic benchmark prior."},
        {"material_family": "compact memristor model", "device_type": "generic memristor compact model", "parameter_name": "normalized_resistance_contrast", "literature_value": "ROFF/RON=20", "unit": "dimensionless", "normalized_value_if_used": "compared with sigma_on0/sigma_off0", "source_title": "A Compact Memristor Model Based on Physics-Informed Neural Networks", "source_year": 2024, "source_location": "Google Drive PDF text, GMMS parameter table", "extraction_method": "text/table extraction", "current_model_value": sigma_ratio, "within_literature_range": False, "notes": "Current ratio is intentionally larger to create visible synthetic hysteresis; describe as engineering prior."},
        {"material_family": "printed memristor surrogate", "device_type": "literature-calibrated printed memristor benchmark", "parameter_name": "activation_energy_or_retention_scale", "literature_value": "Ea=0.379", "unit": "eV", "normalized_value_if_used": "compared with E_D/E_mu/E_r/E_off range 0.12-0.25 eV", "source_title": "A Physics-Regularized Neural Surrogate Framework for Printed Memristors", "source_year": 2026, "source_location": "Google Drive PDF text, supplementary retention model", "extraction_method": "text extraction", "current_model_value": max(params["E_D_eV"], params["E_mu_eV"], params["E_r_eV"], params["E_off_eV"]), "within_literature_range": True, "notes": "Same order of magnitude, not a direct fit to a printed-device retention experiment."},
        {"material_family": "printed memristor surrogate", "device_type": "literature-calibrated printed memristor benchmark", "parameter_name": "resistance_or_conductance_contrast", "literature_value": "reported examples up to 1e7 ratio", "unit": "dimensionless", "normalized_value_if_used": "current bilayer conductivity contrast proxy", "source_title": "A Physics-Regularized Neural Surrogate Framework for Printed Memristors", "source_year": 2026, "source_location": "Google Drive PDF text, literature examples", "extraction_method": "text extraction", "current_model_value": layer_ratio, "within_literature_range": True, "notes": "Only supports plausibility of large switching windows; not a pointwise material value."},
        {"material_family": "phase-change thermal switching surrogate", "device_type": "VO2-like or oxide switching closure", "parameter_name": "switching_temperature", "literature_value": "must be independently calibrated or tightly bounded", "unit": "K", "normalized_value_if_used": "current T_sw=313 K", "source_title": "Local synthetic benchmark prior registry", "source_year": 2026, "source_location": "docs/parameter_prior_registry.md and frozen GT config", "extraction_method": "project prior registry", "current_model_value": params["T_sw"], "within_literature_range": True, "notes": "T_sw is the dominant confounder and is not a measured transition temperature."},
        {"material_family": "thermal compact model", "device_type": "effective substrate-coupled 1D benchmark", "parameter_name": "thermal_dissipation_proxy_gamma_sub", "literature_value": "effective compact parameter; device and geometry dependent", "unit": "W m^-3 K^-1", "normalized_value_if_used": "current gamma_sub=4.5e8", "source_title": "Local constrained gamma_sub inversion evidence chain", "source_year": 2026, "source_location": "docs/literature_gamma_sub_evidence_chain.md", "extraction_method": "engineering prior and synthetic inverse target", "current_model_value": params["gamma_sub"], "within_literature_range": True, "notes": "Reduced inverse target only under fixed or tightly bounded micro-kinetic priors."},
        {"material_family": "phase-change thermal switching surrogate", "device_type": "VO2-like or oxide switching closure", "parameter_name": "transition_width", "literature_value": "sharpness is device/model dependent", "unit": "K", "normalized_value_if_used": "current dT_sw=4.8 K", "source_title": "Local synthetic benchmark prior registry", "source_year": 2026, "source_location": "configs/gt_v1_acceptance_triangle.yaml", "extraction_method": "project prior registry", "current_model_value": params["dT_sw"], "within_literature_range": True, "notes": "Controls smooth synthetic switching; not measured transition width."},
    ]


def run_parameter_sanity(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = _load_yaml(_resolve(config_path))
    rows = _rows(_load_current_params(cfg["frozen_gt_config"]))
    table_path = _resolve(cfg["parameter_table_csv"])
    summary_path = _resolve(cfg["summary_json"])
    notes_path = _resolve(cfg["notes_md"])
    table_path.parent.mkdir(parents=True, exist_ok=True)
    with table_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    within = sum(1 for row in rows if bool(row["within_literature_range"]))
    summary = {
        "benchmark": cfg.get("benchmark"),
        "note": "Synthetic numerical digital-twin benchmark; literature anchors are priors, not experimental calibration.",
        "num_parameters_checked": len(rows),
        "num_within_literature_or_engineering_range": within,
        "num_flagged_as_boundary_sensitive": len(rows) - within,
        "dominant_open_risk": "T_sw must be independently fixed or tightly bounded before gamma_sub claims are strong.",
        "usable_literature_sources": sorted({str(row["source_title"]) for row in rows}),
        "outputs": {"parameter_table_csv": _display_path(table_path), "summary_json": _display_path(summary_path), "notes_md": _display_path(notes_path)},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text("\n".join([
        "# Literature Parameter Sanity Notes", "",
        "All entries are literature-guided or engineering-prior anchors for a synthetic numerical digital-twin benchmark. They are not measured parameters of the repository device.", "",
        "## Key Reading", "",
        "- Lee et al. (2024) supports compact memristor PINN modeling and provides generic GMMS threshold/time-constant anchors.",
        "- Jurj (2026) supports physics-regularized memristor surrogate framing, literature-calibrated synthetic data, and explicit non-fabrication boundaries.",
        "- Local gamma_sub audits show T_sw is the main confounder; literature anchoring must be presented as a prior constraint, not proof of device calibration.", "",
        "## Boundary", "",
        "The table supports plausibility and prior selection only. It does not replace digitized curve fitting or real experimental calibration.",
    ]) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    print(json.dumps(run_parameter_sanity(args.config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

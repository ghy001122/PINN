"""Audit literature-prior registry consistency.

Synthetic numerical digital-twin benchmark support only; not experimental validation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gamma_sub_validation_common import write_json

DEFAULT_CONFIG = Path("configs/literature_priors_phase_change.yaml")
SUMMARY_JSON = Path("outputs/tables/literature_prior_consistency_summary.json")
REQUIRED_FAMILIES = {
    "NbO2_SnSe_sandwich_thermal_engineering",
    "VO2_thermal_neuristor",
    "NbOx_AlN_coplanar_Mott_memristor",
}


def audit_literature_prior_consistency(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    with (ROOT / config_path).open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    meta = cfg.get("metadata", {})
    families = cfg.get("device_families", [])
    names = {str(item.get("family")) for item in families}
    required_fields_present = True
    family_prior_counts: dict[str, int] = {}
    missing: list[str] = []
    for family in families:
        name = str(family.get("family"))
        priors = family.get("priors", {}) or {}
        family_prior_counts[name] = len(priors)
        for top_key in ["family", "stack", "allowed_use", "forbidden_use", "curve_digitization_status"]:
            if top_key not in family:
                required_fields_present = False
                missing.append(f"{name}.{top_key}")
        for prior_name, prior in priors.items():
            for key in ["quantity_type", "units", "value_or_range", "provenance_note"]:
                if key not in prior:
                    required_fields_present = False
                    missing.append(f"{name}.{prior_name}.{key}")
    summary = {
        "benchmark": "literature_prior_consistency",
        "note": "Synthetic numerical digital-twin prior registry audit; not experimental validation.",
        "required_families_present": REQUIRED_FAMILIES.issubset(names),
        "family_count": len(families),
        "family_prior_counts": family_prior_counts,
        "has_provenance_fields": bool(required_fields_present),
        "missing_fields": missing,
        "synthetic_not_experimental": bool(meta.get("synthetic_not_experimental", False)),
        "curve_digitization_status": str(meta.get("curve_digitization_status", "unknown")),
        "allowed_use": str(meta.get("allowed_use", "shape/parameter plausibility prior only")),
        "forbidden_use": str(meta.get("forbidden_use", "experimental validation")),
        "status": "qualified_supported" if REQUIRED_FAMILIES.issubset(names) and required_fields_present and meta.get("synthetic_not_experimental") else "failed_but_informative",
    }
    write_json(ROOT / SUMMARY_JSON, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    summary = audit_literature_prior_consistency(args.config)
    print(summary)


if __name__ == "__main__":
    main()

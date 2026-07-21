"""Fail-closed tests for M40R mesh-forensic evidence and source semantics."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


CONFIG = Path("configs/m40r_qiu_e0_repair.yaml")
FORENSICS = Path("outputs/tables/m40r_qiu_mesh_forensics.json")
OLD_SUMMARY = Path("outputs/tables/m40_qiu_e0_summary.json")


def test_qiu_current_direction_is_derived_not_reported_or_measured() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    parent = yaml.safe_load(
        Path(config["parent_m40_config"]).read_text(encoding="utf-8")
    )
    length = float(parent["geometry"]["device_length_m"])
    width = float(parent["geometry"]["device_width_m"])
    thickness = float(parent["geometry"]["vo2_thickness_m"])
    sigma = float(parent["materials"]["vo2"]["electrical_conductivity_S_m"])
    intrinsic_resistance = length / (sigma * width * thickness)

    assert length == 100.0e-9
    assert width == 500.0e-9
    assert intrinsic_resistance == pytest.approx(2.5, rel=1.0e-12)
    assert "literature_derived" in config["source_semantics"]["current_path_100nm_width_500nm"]
    assert config["source_semantics"]["current_path_assignment_is_measured"] is False
    assert config["source_semantics"]["contact_area_mapping"] == "engineering-prior/unresolved"


def test_non_voting_forensics_reproduces_old_m40_and_supports_only_bounded_repair() -> None:
    payload = json.loads(FORENSICS.read_text(encoding="utf-8"))
    old = json.loads(OLD_SUMMARY.read_text(encoding="utf-8"))

    assert payload["execution_class"] == "non_voting_forensic"
    assert payload["scientific_vote_generated"] is False
    assert payload["old_m40_2_4_8_csv_reproduced"] is True
    assert payload["old_m40_failure_preserved"] is True
    assert old["status"] == "failed_but_informative"
    assert old["gate_values"]["main_qoi_mesh_change"] == 0.02478775649200631
    assert old["gate_values"]["peak_field_mesh_change"] == 0.11066382246828892
    assert old["m41_conservative_reduction_authorized"] is False
    assert payload["repair_supported"] == {
        "add_corner_rounding": False,
        "change_physical_parameters": False,
        "extend_static_triplet_to_8_16_32": True,
        "keep_p99": True,
        "keep_same_exclusion_window": True,
        "map_to_common_grid_before_same_p99": True,
        "use_face_flux_J_over_sigma": True,
    }


def test_forensic_triplet_is_asymptotic_only_for_repaired_quantities() -> None:
    payload = json.loads(FORENSICS.read_text(encoding="utf-8"))
    convergence = payload["convergence"]

    assert convergence["top_contact_current"]["monotone_asymptotic_candidate"] is True
    assert convergence["repaired_common_grid_field_p99"]["monotone_asymptotic_candidate"] is True
    assert convergence["legacy_raw_field_p99"]["monotone_asymptotic_candidate"] is False
    assert convergence["legacy_raw_field_p99"]["observed_order"] is None
    assert convergence["legacy_raw_field_p99"]["fine_grid_gci"] is None
    assert convergence["top_contact_current"]["fine_pair_relative_change"] < 0.01
    assert convergence["repaired_common_grid_field_p99"]["fine_pair_relative_change"] < 0.02


def test_terminal_and_contact_areas_do_not_change_with_refinement() -> None:
    payload = json.loads(FORENSICS.read_text(encoding="utf-8"))
    source_areas = [row["terminal_source_area_m2"] for row in payload["rows"]]
    contact_areas = [row["total_vo2_ti_contact_area_m2"] for row in payload["rows"]]

    assert max(source_areas) - min(source_areas) <= 1.0e-26
    assert max(contact_areas) - min(contact_areas) <= 1.0e-26
    assert source_areas[0] == pytest.approx(1.0e-14)
    assert contact_areas[0] == pytest.approx(2.0e-14)

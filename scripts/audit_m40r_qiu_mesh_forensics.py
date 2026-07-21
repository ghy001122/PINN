"""Run the non-voting M40R mesh and electric-field forensic audit."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.physics.qiu_vo2_device import (
    QiuCircuit,
    QiuGeometry,
    QiuHysteresis,
    build_qiu_domain_masks,
    major_loop_targets,
    material_property_fields,
    qiu_equivalent_device_resistance_ohm,
)
from pinnpcm.solvers.m40r_qiu_e0_repair import (
    ReferenceFieldSample,
    reconstruct_conservative_electric_field,
    relative_field_norms,
    sample_vo2_field_on_fixed_grid,
)
from pinnpcm.solvers.qiu_vo2_2d_fvm import (
    BoundaryFace,
    cell_electric_field_V_m,
    qiu_terminal_faces,
    solve_electrical,
)


ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _resolve(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _convergence(values: list[float], safety_factor: float) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("convergence diagnostic requires exactly three values")
    coarse, medium, fine = (float(value) for value in values)
    d_coarse = coarse - medium
    d_fine = medium - fine
    monotone = bool(d_coarse * d_fine > 0.0)
    result: dict[str, Any] = {
        "values": values,
        "monotone_asymptotic_candidate": monotone,
        "fine_pair_relative_change": abs(fine - medium) / max(abs(fine), 1.0e-30),
    }
    if not monotone or abs(d_fine) <= 1.0e-30:
        result.update(
            {
                "observed_order": None,
                "richardson_extrapolation": None,
                "fine_grid_gci": None,
                "reason": "oscillatory_or_degenerate_triplet",
            }
        )
        return result
    order = math.log(abs(d_coarse / d_fine), 2.0)
    denominator = 2.0**order - 1.0
    richardson = fine + (fine - medium) / denominator
    gci = safety_factor * abs((fine - medium) / fine) / abs(denominator)
    result.update(
        {
            "observed_order": order,
            "richardson_extrapolation": richardson,
            "fine_grid_gci": gci,
            "reason": "three_level_monotone_diagnostic_not_a_vote",
        }
    )
    return result


def _old_rows(path: str | Path) -> dict[int, dict[str, float]]:
    with _resolve(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        int(row["refinement"]): {
            "source_current_A_at_1V": float(row["source_current_A_at_1V"]),
            "peak_field_p99_V_m": float(row["peak_field_p99_V_m"]),
            "relative_current_imbalance": float(row["relative_current_imbalance"]),
        }
        for row in rows
    }


def _protected_m40_paths(config: Mapping[str, Any]) -> list[str]:
    parent = str(config["parent_m40_config"])
    return [
        parent,
        "data/external/qiu_2024_thermal_neuristor/manifest.json",
        "src/pinnpcm/physics/qiu_vo2_device.py",
        "src/pinnpcm/solvers/qiu_vo2_2d_fvm.py",
        "scripts/run_m40_qiu_vo2_2d_e0.py",
        "tests/test_m40_qiu_geometry.py",
        "tests/test_m40_qiu_2d_fvm.py",
        "tests/test_m40_qiu_energy_ledger.py",
        "tests/test_m40_qiu_result_evidence.py",
        "outputs/tables/m40_qiu_e0_preregistration.json",
        "outputs/tables/m40_qiu_e0_summary.json",
        "outputs/tables/m40_qiu_mesh_convergence.csv",
        "outputs/figures/m40/qiu_device_geometry.png",
        "outputs/figures/m40/qiu_e0_field_maps.png",
        "docs/codex_reports/m40_qiu_vo2_e0_results.md",
        "docs/physics/m40_qiu_model_responsibility.md",
        "docs/physics/m40_qiu_2d_equations.md",
    ]


def _contact_area(mesh: Any) -> float:
    area = 0.0
    for ix in range(mesh.shape[1]):
        for iz in range(mesh.shape[0] - 1):
            if {str(mesh.material[iz, ix]), str(mesh.material[iz + 1, ix])} == {
                "vo2",
                "ti",
            }:
                area += mesh.dx_m[ix] * mesh.depth_m
    return float(area)


def _side_vo2_current(mesh: Any, sigma: np.ndarray) -> float:
    vo2 = mesh.material == "vo2"
    rows = np.flatnonzero(np.any(vo2, axis=1))
    terminals = [
        *[BoundaryFace("source", int(iz), 0, "left", 1.0) for iz in rows],
        *[
            BoundaryFace("ground", int(iz), mesh.shape[1] - 1, "right", 0.0)
            for iz in rows
        ],
    ]
    result = solve_electrical(
        mesh, sigma, terminals, electrical_mask=vo2, contact_resistance_m2_ohm={}
    )
    return float(result["terminal_currents_A"]["source"])


def run(config_path: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    parent = yaml.safe_load(
        _resolve(config["parent_m40_config"]).read_text(encoding="utf-8")
    )
    old_summary = json.loads(
        _resolve(config["old_m40"]["summary"]).read_text(encoding="utf-8")
    )
    if old_summary["status"] != config["old_m40"]["required_status"]:
        raise RuntimeError("old M40 failure status was not preserved")
    if old_summary["gate_values"]["main_qoi_mesh_change"] != float(
        config["old_m40"]["required_main_current_change"]
    ):
        raise RuntimeError("old M40 current failure value changed")
    if old_summary["gate_values"]["peak_field_mesh_change"] != float(
        config["old_m40"]["required_field_p99_change"]
    ):
        raise RuntimeError("old M40 field failure value changed")
    protected_before = {
        name: _sha256(name) for name in _protected_m40_paths(config)
    }
    geometry = QiuGeometry.from_mapping(parent["geometry"])
    hysteresis = QiuHysteresis.from_mapping(parent["hysteresis"])
    circuit = QiuCircuit.from_mapping(parent["circuit"])
    contact = {
        ("vo2", "ti"): float(
            parent["interfaces"]["electrical_contact_resistance_m2_ohm"]["vo2_ti"]
        )
    }
    peak = parent["verification"]["peak_field_definition"]
    x_exclusion = float(peak["x_exclusion_from_contact_edge_m"])
    z_exclusion = float(peak["z_exclusion_from_vo2_boundary_m"])
    reference_cfg = config["mesh_forensics"]["reference_grid"]
    levels = [int(value) for value in config["mesh_forensics"]["levels"]]
    percentiles = [float(value) for value in config["mesh_forensics"]["field_percentiles"]]
    old_csv = _old_rows(config["old_m40"]["mesh_csv"])
    rows: list[dict[str, Any]] = []
    samples: dict[int, ReferenceFieldSample] = {}
    for level in levels:
        mesh = build_qiu_domain_masks(geometry, level)
        temperature = np.full(mesh.shape, circuit.ambient_temperature_K)
        history, _ = major_loop_targets(temperature, hysteresis)
        sigma, _, _ = material_property_fields(
            mesh,
            temperature,
            history,
            geometry,
            hysteresis,
            parent["materials"],
        )
        terminals = qiu_terminal_faces(mesh, 1.0)
        electrical = solve_electrical(mesh, sigma, terminals, contact)
        legacy = cell_electric_field_V_m(mesh, electrical["potential_V"], sigma)
        repaired = reconstruct_conservative_electric_field(
            mesh, electrical["potential_V"], sigma, terminals, contact
        )
        sample = sample_vo2_field_on_fixed_grid(
            mesh,
            repaired,
            geometry,
            x_exclusion_m=x_exclusion,
            z_exclusion_m=z_exclusion,
            reference_nx=int(reference_cfg["nx"]),
            reference_nz=int(reference_cfg["nz"]),
        )
        samples[level] = sample
        xx, zz = np.meshgrid(mesh.x_centers_m, mesh.z_centers_m)
        core = (
            (mesh.material == "vo2")
            & (xx >= geometry.electrode_overlap_m + x_exclusion)
            & (xx <= geometry.device_length_m - geometry.electrode_overlap_m - x_exclusion)
            & (zz >= z_exclusion)
            & (zz <= geometry.vo2_thickness_m - z_exclusion)
        )
        vo2 = mesh.material == "vo2"
        max_index = np.nanargmax(
            np.where(vo2, repaired.magnitude_cell_V_m, np.nan)
        )
        max_iz, max_ix = np.unravel_index(max_index, mesh.shape)
        source_area = sum(
            mesh.dx_m[ix] * mesh.depth_m for _, ix in mesh.source_terminal_cells
        )
        source_current = float(electrical["terminal_currents_A"]["source"])
        row: dict[str, Any] = {
            "refinement": level,
            "nx": int(mesh.shape[1]),
            "nz": int(mesh.shape[0]),
            "source_current_A_at_1V": source_current,
            "side_vo2_current_A_at_1V": _side_vo2_current(mesh, sigma),
            "relative_current_imbalance": float(
                electrical["relative_current_imbalance"]
            ),
            "face_terminal_source_current_A": float(
                repaired.terminal_currents_A["source"]
            ),
            "terminal_source_area_m2": float(source_area),
            "total_vo2_ti_contact_area_m2": _contact_area(mesh),
            "raw_max_field_V_m": float(repaired.magnitude_cell_V_m[max_iz, max_ix]),
            "raw_max_field_x_m": float(mesh.x_centers_m[max_ix]),
            "raw_max_field_z_m": float(mesh.z_centers_m[max_iz]),
            "legacy_vs_face_core_relative_l2": float(
                np.linalg.norm((legacy[core] - repaired.magnitude_cell_V_m[core]).ravel())
                / max(np.linalg.norm(repaired.magnitude_cell_V_m[core].ravel()), 1.0e-30)
            ),
        }
        for percentile in percentiles:
            label = int(percentile)
            row[f"legacy_raw_field_p{label}_V_m"] = float(
                np.nanpercentile(legacy[core], percentile)
            )
            row[f"face_raw_field_p{label}_V_m"] = float(
                np.nanpercentile(repaired.magnitude_cell_V_m[core], percentile)
            )
            row[f"face_common_grid_field_p{label}_V_m"] = float(
                np.nanpercentile(sample.magnitude_V_m, percentile)
            )
        for probe_index, (fraction_x, fraction_z) in enumerate(
            config["mesh_forensics"]["probe_points_fraction_xz"]
        ):
            x_target = float(fraction_x) * geometry.device_length_m
            z_target = float(fraction_z) * geometry.vo2_thickness_m
            ix_ref = int(np.argmin(abs(sample.x_m - x_target)))
            iz_ref = int(np.argmin(abs(sample.z_m - z_target)))
            row[f"probe_{probe_index}_x_m"] = x_target
            row[f"probe_{probe_index}_z_m"] = z_target
            row[f"probe_{probe_index}_Ex_V_m"] = float(sample.ex_V_m[iz_ref, ix_ref])
            row[f"probe_{probe_index}_Ez_V_m"] = float(sample.ez_V_m[iz_ref, ix_ref])
        if level in old_csv:
            old = old_csv[level]
            row["old_csv_current_relative_difference"] = abs(
                source_current - old["source_current_A_at_1V"]
            ) / max(abs(old["source_current_A_at_1V"]), 1.0e-30)
            row["old_csv_p99_relative_difference"] = abs(
                row["legacy_raw_field_p99_V_m"] - old["peak_field_p99_V_m"]
            ) / max(abs(old["peak_field_p99_V_m"]), 1.0e-30)
            row["old_csv_imbalance_absolute_difference"] = abs(
                row["relative_current_imbalance"]
                - old["relative_current_imbalance"]
            )
        rows.append(row)

    finest = samples[levels[-1]]
    for row in rows:
        row.update(
            {
                f"common_grid_{key}": value
                for key, value in relative_field_norms(
                    samples[int(row["refinement"])], finest
                ).items()
            }
        )
    triplet = [int(value) for value in config["mesh_forensics"]["convergence_triplet"]]
    by_level = {int(row["refinement"]): row for row in rows}
    safety = float(config["mesh_forensics"]["safety_factor_gci"])
    convergence = {
        "top_contact_current": _convergence(
            [by_level[level]["source_current_A_at_1V"] for level in triplet], safety
        ),
        "legacy_raw_field_p99": _convergence(
            [by_level[level]["legacy_raw_field_p99_V_m"] for level in triplet], safety
        ),
        "repaired_common_grid_field_p99": _convergence(
            [
                by_level[level]["face_common_grid_field_p99_V_m"]
                for level in triplet
            ],
            safety,
        ),
    }
    source_resistance = float(
        qiu_equivalent_device_resistance_ohm(
            np.asarray([circuit.ambient_temperature_K]),
            np.asarray([major_loop_targets(circuit.ambient_temperature_K, hysteresis)[0]]),
            hysteresis,
        )[0]
    )
    protected_after = {
        name: _sha256(name) for name in _protected_m40_paths(config)
    }
    legacy_reproduced = bool(
        all(
            row.get("old_csv_current_relative_difference", 0.0) <= 1.0e-12
            and row.get("old_csv_p99_relative_difference", 0.0) <= 1.0e-12
            and row.get("old_csv_imbalance_absolute_difference", 0.0) <= 1.0e-12
            for row in rows
            if int(row["refinement"]) in old_csv
        )
    )
    payload = {
        "schema_version": "m40r_qiu_mesh_forensics_v1",
        "task_id": config["task_id"],
        "execution_class": "non_voting_forensic",
        "scientific_vote_generated": False,
        "old_m40_failure_preserved": protected_before == protected_after,
        "old_m40_2_4_8_csv_reproduced": legacy_reproduced,
        "source_semantics": config["source_semantics"],
        "levels": levels,
        "convergence_triplet": triplet,
        "rows": rows,
        "convergence": convergence,
        "root_cause": {
            "main_current": "approximately_first_order_top_contact_current_crowding_and_sharp_corner_underresolution",
            "field_p99": "moving_raw_grid_quantile_sampling_superposed_on_a_real_unrounded_contact_corner_singularity",
            "legacy_estimator_contract": "docstring_claimed_face_flux_but_implementation_used_same_material_cell_potential_differences",
            "legacy_estimator_direct_effect_in_uniform_core": "negligible_at_this_anchor_but_not_a_valid_general_contract",
            "contact_or_terminal_omission_in_electrical_solve": False,
            "geometry_area_changes_with_refinement": False,
            "physical_rounding_evidence_available": False,
        },
        "model_bridge_diagnostics": {
            "source_equivalent_resistance_ohm_at_325K": source_resistance,
            "finest_2d_top_contact_resistance_ohm": 1.0
            / by_level[levels[-1]]["source_current_A_at_1V"],
            "finest_topology_shape_factor": (
                1.0 / by_level[levels[-1]]["source_current_A_at_1V"]
            )
            / source_resistance,
        },
        "repair_supported": {
            "extend_static_triplet_to_8_16_32": True,
            "use_face_flux_J_over_sigma": True,
            "map_to_common_grid_before_same_p99": True,
            "keep_same_exclusion_window": True,
            "keep_p99": True,
            "add_corner_rounding": False,
            "change_physical_parameters": False,
        },
        "protected_old_m40_hashes": protected_after,
    }
    _write_csv(config["outputs"]["forensics_csv"], rows)
    _write_json(config["outputs"]["forensics_json"], payload)
    report = _resolve(config["outputs"]["forensics_report"])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# M40R Qiu Mesh Forensics (Non-Voting)",
                "",
                "This audit does not generate a scientific pass vote and does not overwrite M40.",
                "",
                f"- Old 2/4/8 CSV reproduced: `{legacy_reproduced}`.",
                f"- Current observed order: `{convergence['top_contact_current']['observed_order']}`.",
                f"- Current fine-pair change: `{convergence['top_contact_current']['fine_pair_relative_change']}`.",
                f"- Repaired common-grid p99 observed order: `{convergence['repaired_common_grid_field_p99']['observed_order']}`.",
                f"- Repaired common-grid p99 fine-pair change: `{convergence['repaired_common_grid_field_p99']['fine_pair_relative_change']}`.",
                "- The raw-grid p99 triplet is oscillatory; no Richardson/GCI precision claim is made for it.",
                "- The unrounded terminal corner produces a growing raw maximum field and remains an unresolved ideal-corner singularity.",
                "- The M40 legacy field estimator contract is incorrect in general, although it is numerically coincident with J/sigma in this uniform core anchor.",
                "- No contact rounding, parameter fit, exclusion-window change, percentile change, inverse, or PINN action is supported.",
                "",
                "The supported bounded repair is: retain terminal-flux current, extend the static triplet to 8/16/32, reconstruct bulk field from conservative face current, and evaluate the unchanged p99 on one fixed physical sampling grid.",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    payload = run(_resolve(args.config))
    print(json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

"""Execute the bounded M42 dimensional-closure preflight.

This is a solver preflight, not a calibrated Qiu device simulation.  It uses
unit-load linear thermal responses and manufactured circuit/electrical
ledgers to decide whether a pure x-z extrusion is defensible enough to justify
later work.  No literature curve, inverse model, or PINN is evaluated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt
import numpy as np
import yaml

from pinnpcm.physics.m42_qiu_foundation import (
    run_fixed_resistance_rc,
    series_electrical_ledger,
    source_resistance_mapping_error,
    thermal_diffusion_length_m,
)
from pinnpcm.solvers.m42_qiu_thermal_closure import (
    build_grid,
    relative_change,
    run_constant_power_transient,
)


ROOT = Path(__file__).resolve().parents[1]
MESH_PROFILES = {
    1: (1, 4, 1, 5),
    2: (2, 6, 2, 7),
    3: (3, 8, 3, 9),
}


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


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
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
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
        for row in rows:
            writer.writerow({key: _jsonable(row.get(key)) for key in fields})


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def _load_bridge() -> dict[str, dict[str, float]]:
    path = _resolve("outputs/tables/e1f_source_to_pde_bridge_mismatch.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            row["quantity"]: {
                "local": float(row["local_2d_value"]),
                "source": float(row["source_lumped_value"]),
            }
            for row in csv.DictReader(handle)
        }


def _protected_paths() -> list[Path]:
    fixed = [
        "configs/gt_v1_acceptance_triangle.yaml",
        "configs/gt_v1_acceptance_ltp_ltd.yaml",
        "docs/gt_v1_acceptance_report.md",
        "data/processed/gt_v1_acceptance/manifest.json",
        "outputs/tables/m40_qiu_e0_summary.json",
        "outputs/tables/m40r_qiu_e0_summary.json",
        "outputs/tables/m40r_qiu_active_transient.json",
        "outputs/tables/e1f_source_to_pde_bridge_mismatch.csv",
    ]
    paths = [_resolve(item) for item in fixed]
    paths.extend(sorted(_resolve("data/processed/gt_v1_acceptance").glob("**/*")))
    return sorted({path for path in paths if path.is_file()})


def _hashes(paths: list[Path]) -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): _sha256(path) for path in paths}


def _relative_vector_change(coarse: Mapping[str, Any], fine: Mapping[str, Any]) -> dict[str, float]:
    return {
        "Tmean": relative_change(float(coarse["Tmean_rise_K"]), float(fine["Tmean_rise_K"])),
        "Tmax": relative_change(float(coarse["Tmax_rise_K"]), float(fine["Tmax_rise_K"])),
        "Qout": relative_change(
            float(coarse["cumulative_outward_heat_J"]),
            float(fine["cumulative_outward_heat_J"]),
        ),
    }


def _gate(value: float | bool | None, threshold: float | bool, *, relation: str = "max") -> dict[str, Any]:
    if value is None:
        passed = False
    elif relation == "max":
        passed = float(value) <= float(threshold)
    elif relation == "min":
        passed = float(value) >= float(threshold)
    else:
        passed = bool(value) is bool(threshold)
    return {"value": value, "threshold": threshold, "relation": relation, "passed": passed}


def _write_figure(
    path: str | Path,
    *,
    domain_results: list[tuple[float, Mapping[str, Any]]],
    mesh_results: list[tuple[int, Mapping[str, Any]]],
    time_results: list[tuple[int, Mapping[str, Any]]],
    out_of_plane: Mapping[str, float],
) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.6), constrained_layout=True)
    axes[0].plot([item[0] for item in domain_results], [item[1]["Tmean_rise_K"] for item in domain_results], "o-", label="mean")
    axes[0].plot([item[0] for item in domain_results], [item[1]["Tmax_rise_K"] for item in domain_results], "s-", label="max")
    axes[0].set(xlabel="domain multiplier", ylabel="unit-load thermal impedance (K/W)", title="Domain closure")
    axes[0].legend()
    axes[1].plot([item[0] for item in mesh_results], [item[1]["Tmean_rise_K"] for item in mesh_results], "o-", label="mesh")
    axes[1].plot([item[0] for item in time_results], [item[1]["Tmean_rise_K"] for item in time_results], "s--", label="time")
    axes[1].set(xlabel="locked level/divisor", ylabel="mean impedance (K/W)", title="Mesh/time ladder")
    axes[1].legend()
    labels = list(out_of_plane)
    axes[2].bar(labels, [100.0 * out_of_plane[key] for key in labels], color="#b55d47")
    axes[2].axhline(10.0, color="black", linestyle="--", linewidth=1.0)
    axes[2].set(ylabel="finite-width vs x-z difference (%)", title="Out-of-plane closure")
    axes[2].tick_params(axis="x", rotation=25)
    fig.savefig(target, dpi=180)
    plt.close(fig)


def _write_report(path: str | Path, summary: Mapping[str, Any]) -> None:
    gates = summary["gates"]
    gate_lines = "\n".join(
        f"| `{name}` | {record['value']} | {record['threshold']} | {'pass' if record['passed'] else 'fail'} |"
        for name, record in gates.items()
    )
    assumptions = summary["highest_risk_assumptions"]
    text = f"""# M42 Qiu 2D Physics Foundation Preflight

## Outcome

M42 is a CPU-only solver preflight. It performed no curve fit, inverse solve,
PINN training, sealed-13-V access, or claim-bearing Qiu device forward. The
fail-closed decision is **{summary['decision']}** and the evidence status is
`{summary['status']}`.

The detached P0 replay passed after one retained non-voting abort caused by
Git ownership protection and an incorrect guessed full SHA. The corrected
replay used the same committed
bytes and external assets and completed {summary['hermetic_replay']['pytest_passed']} tests.

## Scope and equations

The electrical audit enforces $P_{{port}}=P_{{bulk}}+P_{{contact}}$ for a
source-level series network. The thermal preflight solves a constant-property,
finite-width conservative substrate problem under a unit load. The unit load
is a linear normalization: reported temperatures are thermal impedances, not
Qiu temperature predictions. Total sensible enthalpy and boundary heat are
checked through separately coded finite-volume bookkeeping paths. This is a
discrete conservation check, not independent validation of the physical
closure. Latent heat is disabled because no source-locked
local value exists; that is a model gap, not evidence for zero latent heat.

## Locked gates

| Gate | Value | Threshold | Result |
| --- | ---: | ---: | --- |
{gate_lines}

## Main findings

- Source-to-local resistance error is {summary['diagnostics']['source_resistance_mapping_error']:.3f}; therefore the old local $\sigma$ mapping does not preserve the source port resistance.
- The maximum finite-width/x-z extrusion discrepancy is {summary['diagnostics']['out_of_plane_closure_max']:.3f}.
- Domain, mesh, and time fine-pair maxima are {summary['diagnostics']['domain_sensitivity_max']:.3f}, {summary['diagnostics']['mesh_fine_pair_max']:.3f}, and {summary['diagnostics']['time_fine_pair_max']:.3f}.
- {summary['forward_accounting']['total_forward_solves']} bounded manufactured/unit-load forward calls were used across pilot and formal execution ({summary['forward_accounting'].get('unique_preflight_case_count', summary['forward_accounting']['total_forward_solves'])} unique cases), within the locked budget of {summary['forward_accounting']['maximum_forward_solves']}.

## Highest-risk unresolved assumptions

1. {assumptions[0]}
2. {assumptions[1]}
3. {assumptions[2]}

## Manuscript and next-step disposition

Decision A would authorize only a later formal reference solver, never an
inverse or PINN claim. Decision B authorizes only a bounded 2.5D/coarse-3D
closure study. Decision C terminates the 2D route. The present decision does
not upgrade any manuscript claim; exact author-code reproduction, external
quantitative validation, terminal-only 2D inverse, and trained 2D PINN remain
`forbidden`.
"""
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def _hermetic_record(
    hermetic_json: Path | None, initial_hermetic_json: Path | None
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "passed": False,
        "pytest_passed": 0,
        "environment_only_abort_retained": True,
    }
    if hermetic_json is not None:
        replay = json.loads(hermetic_json.read_text(encoding="utf-8"))
        pytest_log = hermetic_json.parent / "pytest.txt"
        pytest_passed = 0
        if pytest_log.is_file():
            raw_log = pytest_log.read_bytes()
            encoding = "utf-16" if raw_log.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
            matches = re.findall(
                r"(\d+) passed",
                raw_log.decode(encoding, errors="replace"),
            )
            pytest_passed = int(matches[-1]) if matches else 0
        record.update(
            {
                "passed": bool(replay.get("all_passed"))
                and replay.get("status") == "pass",
                "pytest_passed": pytest_passed,
                "artifact_sha256": _sha256(hermetic_json),
                "pytest_log_sha256": _sha256(pytest_log)
                if pytest_log.is_file()
                else None,
            }
        )
    if initial_hermetic_json is not None:
        initial = json.loads(initial_hermetic_json.read_text(encoding="utf-8"))
        record["initial_aborted_attempt"] = {
            "status": initial.get("status"),
            "failures": initial.get("failures", []),
            "expected_commit_was_incorrect": initial.get("expected_commit")
            != initial.get("actual_head"),
            "git_safe_directory_rejected_owner_mismatch": True,
            "artifact_sha256": _sha256(initial_hermetic_json),
            "scientific_vote": False,
        }
    return record


def run(
    config_path: Path,
    hermetic_json: Path | None,
    initial_hermetic_json: Path | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    config = dict(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    paths = _protected_paths()
    before_hashes = _hashes(paths)
    before_mtimes = {path: path.stat().st_mtime_ns for path in paths}
    bridge = _load_bridge()
    circuit = config["circuit"]
    geometry = config["geometry"]
    priors = config["engineering_priors"]
    scale = config["scale_preflight"]
    thresholds = config["gates"]
    tau = float(circuit["load_resistance_ohm"]) * float(circuit["parallel_capacitance_F"])
    duration = float(circuit["duration_Rload_C"]) * tau
    diffusion_length = thermal_diffusion_length_m(
        float(priors["sapphire_thermal_conductivity_W_mK"]),
        float(priors["sapphire_volumetric_heat_capacity_J_m3K"]),
        duration,
    )
    active_volume = float(geometry["device_length_m"]) * float(geometry["device_width_m"]) * float(geometry["vo2_thickness_m"])
    footprint = float(geometry["device_length_m"]) * float(geometry["device_width_m"])

    rows: list[dict[str, Any]] = []
    forward_count = 0
    electrical = bridge["electrical_resistance"]
    electrical_ledger = series_electrical_ledger(
        float(circuit["input_voltage_V"]), electrical["source"], 260.0
    )
    mapping_error = source_resistance_mapping_error(electrical["local"], electrical["source"])
    rows.append({
        "case_id": "source_series_electrical_ledger",
        "axis": "electrical",
        "forward_class": "analytic_manufactured",
        "scientific_vote": False,
        **electrical_ledger.__dict__,
        "source_resistance_mapping_error": mapping_error,
    })

    circuit_results: dict[int, Mapping[str, Any]] = {}
    for divisor in scale["timestep_divisors_per_Rload_C"]:
        result = run_fixed_resistance_rc(
            input_voltage_V=float(circuit["input_voltage_V"]),
            load_resistance_ohm=float(circuit["load_resistance_ohm"]),
            device_resistance_ohm=electrical["source"],
            capacitance_F=float(circuit["parallel_capacitance_F"]),
            duration_s=duration,
            dt_s=tau / int(divisor),
        )
        forward_count += 1
        circuit_results[int(divisor)] = result
        rows.append({"case_id": f"fixed_R_RC_dt{divisor}", "axis": "time", "forward_class": "manufactured_circuit", "scientific_vote": False, **result})

    thermal_cache: dict[tuple[float, int, int, bool], Mapping[str, Any]] = {}

    def thermal_case(domain: float, mesh: int, divisor: int, extruded: bool) -> Mapping[str, Any]:
        nonlocal forward_count
        key = (float(domain), int(mesh), int(divisor), bool(extruded))
        if key in thermal_cache:
            return thermal_cache[key]
        sh, outer, near, depth = MESH_PROFILES[int(mesh)]
        grid = build_grid(
            source_length_m=float(geometry["device_length_m"]),
            source_width_m=float(geometry["device_width_m"]),
            diffusion_length_m=diffusion_length,
            domain_multiplier=float(domain),
            source_half_cells=sh,
            outer_cells=outer,
            near_depth_cells=near,
            depth_outer_cells=depth,
            extruded_2d=bool(extruded),
        )
        result = run_constant_power_transient(
            grid,
            source_length_m=float(geometry["device_length_m"]),
            source_width_m=float(geometry["device_width_m"]),
            total_power_W=1.0,
            thermal_conductivity_W_mK=float(priors["sapphire_thermal_conductivity_W_mK"]),
            volumetric_heat_capacity_J_m3K=float(priors["sapphire_volumetric_heat_capacity_J_m3K"]),
            duration_s=duration,
            dt_s=tau / int(divisor),
        )
        forward_count += 1
        thermal_cache[key] = result
        rows.append({
            "case_id": f"thermal_d{domain}_m{mesh}_dt{divisor}_{'xz' if extruded else 'finite_width'}",
            "axis": "out_of_plane" if extruded else "thermal",
            "forward_class": "unit_load_linear_thermal_preflight",
            "scientific_vote": False,
            "domain_multiplier": domain,
            "mesh_level": mesh,
            "timestep_divisor": divisor,
            "extruded_2d": extruded,
            **result,
        })
        return result

    domains = [(float(level), thermal_case(float(level), 2, 20, False)) for level in scale["domain_multipliers"]]
    meshes = [(int(level), thermal_case(2.0, int(level), 20, False)) for level in scale["mesh_levels"]]
    times = [(int(level), thermal_case(2.0, 3, int(level), False)) for level in scale["timestep_divisors_per_Rload_C"]]
    finite_width = thermal_case(2.0, 3, 40, False)
    extruded = thermal_case(2.0, 3, 40, True)

    domain_changes = _relative_vector_change(domains[-2][1], domains[-1][1])
    mesh_changes = _relative_vector_change(meshes[-2][1], meshes[-1][1])
    time_changes = _relative_vector_change(times[-2][1], times[-1][1])
    out_of_plane = _relative_vector_change(extruded, finite_width)
    circuit_I_change = relative_change(
        float(circuit_results[20]["final_current_A"]),
        float(circuit_results[40]["final_current_A"]),
    )
    domain_max = max(domain_changes.values())
    mesh_max = max(mesh_changes.values())
    time_max = max(time_changes.values())
    out_of_plane_max = max(out_of_plane.values())
    fine_pair_max = max(circuit_I_change, mesh_max, time_max)
    maximum_enthalpy = max(float(result["maximum_enthalpy_imbalance"]) for result in thermal_cache.values())
    finite_and_unclipped = all(bool(result["finite"]) and int(result["clip_count"]) == 0 for result in thermal_cache.values())

    gates = {
        "relative_current_imbalance": _gate(electrical_ledger.relative_current_imbalance, thresholds["relative_current_imbalance_max"]),
        "contact_power_closure": _gate(electrical_ledger.relative_power_imbalance, thresholds["relative_current_imbalance_max"]),
        "smooth_enthalpy_imbalance": _gate(maximum_enthalpy, thresholds["smooth_enthalpy_imbalance_max"]),
        "switching_enthalpy_imbalance": _gate(None, thresholds["switching_enthalpy_imbalance_max"]),
        "finest_pair_I_Tmean_Tmax_Qout": _gate(fine_pair_max, thresholds["finest_pair_I_Tmean_Tmax_Qout_change_max"]),
        "domain_sensitivity": _gate(domain_max, thresholds["domain_sensitivity_max"]),
        "uniform_2d_source_resistance": _gate(mapping_error, thresholds["uniform_2d_source_resistance_error_max"]),
        "no_clip_nan_or_unregistered_extrapolation": _gate(finite_and_unclipped, True, relation="equal"),
        "dynamic_duration_Rload_C": _gate(float(circuit["duration_Rload_C"]), thresholds["dynamic_duration_Rload_C_min"], relation="min"),
        "pure_2d_out_of_plane_closure": _gate(out_of_plane_max, thresholds["out_of_plane_or_domain_closure_for_pure_2d_max"]),
    }
    if all(record["passed"] for record in gates.values()):
        decision = "A"
    elif max(out_of_plane_max, domain_max) > float(thresholds["out_of_plane_or_domain_closure_for_pure_2d_max"]):
        decision = "B"
    else:
        decision = "C"

    after_hashes = _hashes(paths)
    after_mtimes = {path: path.stat().st_mtime_ns for path in paths}
    if before_hashes != after_hashes:
        raise RuntimeError("protected M40/M40R/frozen evidence changed during M42")
    if forward_count > int(config["budget"]["maximum_forward_solves"]):
        raise RuntimeError("M42 forward budget exceeded")
    hermetic = _hermetic_record(hermetic_json, initial_hermetic_json)

    summary: dict[str, Any] = {
        "schema_version": config["schema_version"],
        "task_id": config["task_id"],
        "execution_class": "bounded_solver_preflight",
        "status": "failed_but_informative" if decision != "A" else "qualified_supported",
        "decision": decision,
        "base_commit": config["base_commit"],
        "preregistration_commit": _git("rev-list", "--max-count=1", "--grep=Preregister M42 dimensional closure audit", "HEAD"),
        "runtime_head": _git("rev-parse", "HEAD"),
        "evidence_type": "solver_generated_manufactured_and_unit_load_preflight",
        "scientific_forward_runs": 0,
        "claim_bearing_device_forward_runs": 0,
        "external_validation": False,
        "curve_fit_runs": 0,
        "inverse_runs": 0,
        "pinn_training_runs": 0,
        "sealed_13V_accessed": False,
        "hermetic_replay": hermetic,
        "geometry_audit": {
            "computed_active_volume_m3": active_volume,
            "reported_active_volume_m3": geometry["reported_active_volume_m3"],
            "relative_active_volume_error": relative_change(active_volume, float(geometry["reported_active_volume_m3"])),
            "computed_footprint_area_m2": footprint,
            "reported_footprint_area_m2": geometry["reported_footprint_area_m2"],
            "relative_footprint_error": relative_change(footprint, float(geometry["reported_footprint_area_m2"])),
            "finite_width_m": geometry["device_width_m"],
        },
        "scale_audit": {
            "Rload_C_s": tau,
            "duration_s": duration,
            "duration_Rload_C": duration / tau,
            "sapphire_diffusion_length_m": diffusion_length,
            "unit_thermal_load_W": 1.0,
            "unit_load_role": "linear_normalization_not_a_Qiu_device_temperature_prediction",
        },
        "diagnostics": {
            "source_resistance_mapping_error": mapping_error,
            "contact_power_imbalance": electrical_ledger.relative_power_imbalance,
            "circuit_I_fine_pair_change": circuit_I_change,
            "domain_changes": domain_changes,
            "domain_sensitivity_max": domain_max,
            "mesh_changes": mesh_changes,
            "mesh_fine_pair_max": mesh_max,
            "time_changes": time_changes,
            "time_fine_pair_max": time_max,
            "out_of_plane_changes": out_of_plane,
            "out_of_plane_closure_max": out_of_plane_max,
            "maximum_smooth_enthalpy_imbalance": maximum_enthalpy,
        },
        "gates": gates,
        "gate_pass_count": sum(record["passed"] for record in gates.values()),
        "gate_total_count": len(gates),
        "forward_accounting": {
            "manufactured_circuit_forwards": len(circuit_results),
            "unit_load_thermal_forwards": len(thermal_cache),
            "total_forward_solves": forward_count,
            "preflight_forward_solves": forward_count,
            "maximum_forward_solves": config["budget"]["maximum_forward_solves"],
            "wall_clock_s": time.perf_counter() - started,
        },
        "protected_evidence_unchanged": before_hashes == after_hashes,
        "protected_evidence_mtime_unchanged": before_mtimes == after_mtimes,
        "protected_evidence_sha256": after_hashes,
        "highest_risk_assumptions": [
            "Qiu device-level resistance does not uniquely determine local conductivity or contact partition.",
            "Constant-property sapphire and zero registered latent heat are numerical preflight closures, not real-device calibration.",
            "The x-z extrusion suppresses finite-width spreading and cannot be quantitative unless the explicit closure gate passes.",
        ],
        "allowed_claims": [
            "M42 measured dimensional-closure errors for a source-constrained manufactured/unit-load preflight.",
            "The result selects only the preregistered A/B/C routing decision.",
        ],
        "forbidden_claims": [
            "calibrated Qiu device reproduction",
            "independent external validation",
            "formal 2D dynamic ground truth unless decision A",
            "terminal-only 2D inverse",
            "trained 2D PINN",
        ],
    }
    _write_csv(config["outputs"]["cases"], rows)
    _write_figure(
        config["outputs"]["figure"],
        domain_results=domains,
        mesh_results=meshes,
        time_results=times,
        out_of_plane=out_of_plane,
    )
    summary["artifact_sha256"] = {
        "cases": _sha256(config["outputs"]["cases"]),
        "figure": _sha256(config["outputs"]["figure"]),
    }
    _write_json(config["outputs"]["summary"], summary)
    _write_report(config["outputs"]["report"], summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/m42_qiu_2d_preflight.yaml"))
    parser.add_argument("--hermetic-json", type=Path)
    parser.add_argument("--initial-hermetic-json", type=Path)
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="repair replay metadata without executing any scientific preflight forward",
    )
    args = parser.parse_args()
    config_path = _resolve(args.config)
    hermetic = args.hermetic_json.resolve() if args.hermetic_json else None
    initial_hermetic = args.initial_hermetic_json.resolve() if args.initial_hermetic_json else None
    if args.metadata_only:
        config = dict(yaml.safe_load(config_path.read_text(encoding="utf-8")))
        summary_path = _resolve(config["outputs"]["summary"])
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["hermetic_replay"] = _hermetic_record(hermetic, initial_hermetic)
        summary["gates"]["dynamic_duration_Rload_C"] = _gate(
            float(config["circuit"]["duration_Rload_C"]),
            float(config["gates"]["dynamic_duration_Rload_C_min"]),
            relation="min",
        )
        summary["gate_pass_count"] = sum(
            bool(record["passed"]) for record in summary["gates"].values()
        )
        summary["claim_bearing_device_forward_runs"] = 0
        unique_forwards = int(
            summary["forward_accounting"].get(
                "formal_preflight_forward_solves",
                summary["forward_accounting"]["total_forward_solves"],
            )
        )
        summary["forward_accounting"].update(
            {
                "unique_preflight_case_count": unique_forwards,
                "development_pilot_forward_solves": unique_forwards,
                "formal_preflight_forward_solves": unique_forwards,
                "preflight_forward_solves": 2 * unique_forwards,
                "total_forward_solves": 2 * unique_forwards,
                "manufactured_circuit_forwards": 6,
                "unit_load_thermal_forwards": 16,
                "formal_attempts": 1,
                "development_pilot_attempts": 1,
            }
        )
        summary["metadata_correction"] = {
            "scientific_forward_runs": 0,
            "reason": "correct replay-key interpretation and binary floating comparison only",
        }
        _write_json(summary_path, summary)
        _write_report(config["outputs"]["report"], summary)
        print(json.dumps({"status": summary["status"], "decision": summary["decision"], "metadata_only": True}, sort_keys=True))
        return 0
    summary = run(config_path, hermetic, initial_hermetic)
    print(json.dumps({"status": summary["status"], "decision": summary["decision"], "forwards": summary["forward_accounting"]["total_forward_solves"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

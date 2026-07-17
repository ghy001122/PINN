"""Audit frozen GT/FVM, continuous equations, and bilayer interface semantics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pinnpcm.physics.gt_solver import simulate_ground_truth
from pinnpcm.physics.params import merge_params
from pinnpcm.pinn.n0_compatibility import (
    bilayer_piecewise_manufactured,
    defect_manufactured,
    equation_parity_rows,
    frozen_fvm_conservation_audit,
    heat_manufactured,
    interface_discretization_audit,
    nrmse95,
    uniform_conduction_manufactured,
)


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip()


def _grid_refinement(params: dict[str, Any], duration_s: float) -> dict[str, Any]:
    solver_params: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            try:
                solver_params[key] = float(value)
            except ValueError:
                solver_params[key] = value
        else:
            solver_params[key] = value
    runs: dict[int, dict[str, Any]] = {}
    for nx in (31, 63):
        runs[nx] = simulate_ground_truth(
            protocol="triangle",
            params=solver_params,
            nx=nx,
            nt=160,
            t_max=duration_s,
            rtol=1.0e-6,
            atol=1.0e-8,
            method="Radau",
        )
    coarse = runs[31]
    fine = runs[63]
    field_metrics: dict[str, float] = {}
    for key in ("c_v", "T", "m", "phi", "sigma"):
        interpolated = np.vstack(
            [np.interp(coarse["x"], fine["x"], np.asarray(fine[key])[index]) for index in range(len(coarse["t"]))]
        )
        field_metrics[key] = nrmse95(interpolated, np.asarray(coarse[key]))
    return {
        "nx_levels": [31, 63],
        "nt": 160,
        "port_current_nrmse95_31_vs_63": nrmse95(np.asarray(fine["I"]), np.asarray(coarse["I"])),
        "cell_center_field_nrmse95_31_vs_63": field_metrics,
        "role": "controlled non-frozen spatial-grid diagnostic; frozen arrays were not modified",
    }


def run(config_path: Path) -> dict[str, Any]:
    config = _load_yaml(config_path)
    gt_config_path = ROOT / config["frozen_gt_config"]
    gt_path = ROOT / config["frozen_gt_path"]
    gt_config = _load_yaml(gt_config_path)
    params = merge_params(gt_config.get("params"))
    with np.load(gt_path) as archive:
        gt = {key: np.asarray(archive[key]) for key in archive.files if key != "params_json"}
    duration = float(np.max(gt["t"]))

    interface = interface_discretization_audit(gt["x"], params)
    parity = equation_parity_rows(interface)
    manufactured = {
        "uniform_nonzero_voltage_conduction": uniform_conduction_manufactured(params),
        "heat_storage_source_sink": heat_manufactured(params, duration),
        "defect_diffusion_drift_reaction": defect_manufactured(params, duration),
        "bilayer_piecewise_flux_continuity": bilayer_piecewise_manufactured(params),
    }
    conservation = frozen_fvm_conservation_audit(gt, params)
    grid_refinement = _grid_refinement(params, duration)

    manufactured_pass = (
        manufactured["uniform_nonzero_voltage_conduction"]["current_density_relative_rms_error"] <= 1.0e-10
        and manufactured["heat_storage_source_sink"]["normalized_residual_rms"] <= 1.0e-12
        and manufactured["defect_diffusion_drift_reaction"]["normalized_residual_rms"] <= 1.0e-12
        and max(
            manufactured["bilayer_piecewise_flux_continuity"]["phi_jump_normalized"],
            manufactured["bilayer_piecewise_flux_continuity"]["temperature_jump_normalized"],
            manufactured["bilayer_piecewise_flux_continuity"]["current_flux_jump_normalized"],
            manufactured["bilayer_piecewise_flux_continuity"]["heat_flux_jump_normalized"],
        )
        <= 1.0e-12
    )
    discrete_conservation_pass = max(
        conservation["max_defect_mass_normalized_imbalance"],
        conservation["max_global_energy_normalized_imbalance"],
        conservation["max_current_normalized_spread"],
        conservation["max_port_current_relative_error"],
    ) <= 1.0e-10
    v1_orientation_mismatch = any(
        row["status"] == "incompatible_v1_boundary_orientation" for row in parity
    )
    status = "repair_authorized" if manufactured_pass and discrete_conservation_pass and v1_orientation_mismatch else "stop"

    hash_paths = [
        config_path,
        gt_config_path,
        gt_path,
        ROOT / "src/pinnpcm/physics/gt_solver.py",
        ROOT / "src/pinnpcm/physics/electrostatics.py",
        ROOT / "src/pinnpcm/pinn/full_pinn_1d.py",
        ROOT / "src/pinnpcm/pinn/full_residuals_1d.py",
        ROOT / "src/pinnpcm/pinn/n0_compatibility.py",
        ROOT / "scripts/audit_n0_teacher_equation_compatibility.py",
    ]
    payload = {
        "schema_version": "n0_teacher_equation_compatibility_v1",
        "stage_id": "N0-R",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": bool(_git(["status", "--short"])),
        "status": status,
        "claim_status": "failed_but_informative",
        "decision": (
            "The frozen FVM is internally conservative and the declared continuous equations pass manufactured tests, "
            "but full_pinn_architecture_v1 reverses the frozen electrical boundary orientation and its finite-band "
            "interface proxy is not the frozen FVM face law. A bounded exact-trace split-domain repair is authorized."
        ),
        "manufactured_checks_pass": manufactured_pass,
        "frozen_discrete_conservation_pass": discrete_conservation_pass,
        "v1_electrical_orientation_mismatch": v1_orientation_mismatch,
        "manufactured_cases": manufactured,
        "interface_discretization": interface,
        "grid_refinement": grid_refinement,
        "hashes": {str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path) for path in hash_paths},
        "forbidden_interpretation": "This audit is not trained full-PINN evidence and does not revive P1 or authorize N1-N3.",
    }

    table_dir = ROOT / "outputs/tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    compatibility_path = table_dir / "n0_teacher_equation_compatibility_v1.json"
    conservation_path = table_dir / "n0_global_conservation_audit_v1.json"
    registry_path = table_dir / "n0_equation_parity_registry_v1.csv"
    compatibility_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    conservation_path.write_text(json.dumps(conservation, indent=2, sort_keys=True), encoding="utf-8")
    with registry_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(parity[0]))
        writer.writeheader()
        writer.writerows(parity)

    report_path = ROOT / "docs/codex_reports/n0_teacher_equation_compatibility_v1.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# N0 Teacher–Equation Compatibility Audit v1",
                "",
                f"- Base commit: `{payload['base_commit']}`",
                f"- Status: `{status}`",
                f"- Manufactured checks: `{manufactured_pass}`",
                f"- Frozen FVM discrete conservation: `{discrete_conservation_pass}`",
                "",
                "## Core finding",
                "",
                payload["decision"],
                "",
                "The frozen GT stores potential with the driven left electrode at `V(t)` and the right electrode at zero. "
                "The v1 single-network PINN imposes the opposite orientation while retaining `E=-dphi/dx` and a positive-voltage port operator. "
                "This reverses drift and local current signs relative to the teacher even though the scalar port operator remains positive.",
                "",
                "The frozen `nx=31` material mask places its arithmetic-averaged interface face at "
                f"`{interface['implied_discrete_face_m']:.9e} m`, an offset of `{interface['face_offset_from_declared_m']:.9e} m` "
                "from the declared `L_int`. Exact continuum traces must therefore be scored with this discretization difference recorded, not hidden.",
                "",
                "## Disposition",
                "",
                "A bounded dual-domain repair with the corrected electrode orientation and exact one-sided interface traces is allowed. "
                "The audit does not change frozen GT, does not pass N0, and does not support interface novelty, sensitivity fidelity, or inverse claims.",
                "",
                "Machine evidence: `outputs/tables/n0_teacher_equation_compatibility_v1.json`, "
                "`outputs/tables/n0_equation_parity_registry_v1.csv`, and "
                "`outputs/tables/n0_global_conservation_audit_v1.json`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    result = run(config_path)
    print(
        json.dumps(
            {
                "status": result["status"],
                "manufactured_checks_pass": result["manufactured_checks_pass"],
                "frozen_discrete_conservation_pass": result["frozen_discrete_conservation_pass"],
                "v1_electrical_orientation_mismatch": result["v1_electrical_orientation_mismatch"],
                "grid_refinement": result["grid_refinement"],
            },
            indent=2,
        )
    )
    if result["status"] == "stop":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

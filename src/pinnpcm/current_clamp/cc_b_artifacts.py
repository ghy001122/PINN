"""Atomic scientific artifacts for the bounded CC-B campaign."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from pinnpcm.branchconserve.artifacts import atomic_write_npz
from pinnpcm.current_clamp.artifacts import atomic_write_json, file_sha256
from pinnpcm.current_clamp.cc_b_solver import CCBSolveOutcome
from pinnpcm.current_clamp.cc_b_stability import CCBStabilityOutcome


def save_cc_b_equilibrium(
    processed_root: Path,
    compact_root: Path,
    *,
    identity: str,
    solve: CCBSolveOutcome,
    stability: CCBStabilityOutcome | None,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not solve.success or solve.evaluation is None or solve.temperature_K is None:
        raise ValueError("only successful CC-B equilibria can be persisted")
    if stability is not None and not stability.success:
        raise ValueError("invalid stability cannot be attached as certified")
    evaluation = solve.evaluation
    arrays: dict[str, np.ndarray] = {
        "temperature_K": evaluation.temperature_K,
        "unit_potential": evaluation.unit_potential,
        "potential_V": evaluation.potential_V,
        "conductive_state": evaluation.conductive_state,
        "conductivity_S_m": evaluation.conductivity_S_m,
        "vertical_conductance_W_m2K": evaluation.vertical_conductance_W_m2K,
        "cell_joule_power_W": evaluation.cell_joule_power_W,
        "electrical_x_face_current_A": evaluation.electrical_faces.x_face_current_A,
        "electrical_y_face_current_A": evaluation.electrical_faces.y_face_current_A,
        "electrical_source_face_current_A": evaluation.electrical_faces.source_face_current_A,
        "electrical_ground_face_current_A": evaluation.electrical_faces.ground_face_current_A,
        "thermal_x_face_flux_W": evaluation.thermal_x_face_flux_W,
        "thermal_y_face_flux_W": evaluation.thermal_y_face_flux_W,
        "thermal_net_cell_outflow_W": evaluation.thermal_net_cell_outflow_W,
        "thermal_residual_W": evaluation.thermal_residual_W,
    }
    if stability is not None:
        arrays.update(
            {
                "stability_eigenvalues_real_per_s": stability.eigenvalues_per_s.real,
                "stability_eigenvalues_imag_per_s": stability.eigenvalues_per_s.imag,
                "stability_eigenvectors_real": stability.eigenvectors_temperature.real,
                "stability_eigenvectors_imag": stability.eigenvectors_temperature.imag,
                "stability_relative_ritz_residuals": stability.relative_ritz_residuals,
                "stability_absolute_backward_errors_per_s": stability.absolute_backward_errors_per_s,
            }
        )
    npz_path = processed_root / "equilibria" / f"{identity}.npz"
    npz_hash = atomic_write_npz(npz_path, **arrays)
    manifest = {
        "schema_version": "q2_current_clamp_cc_b_equilibrium_v1",
        "identity": identity,
        "metadata": dict(metadata),
        "npz_path": npz_path.as_posix(),
        "npz_sha256": npz_hash,
        "current_set_A": evaluation.current_set_A,
        "unit_conductance_S": evaluation.unit_conductance_S,
        "device_voltage_V": evaluation.device_voltage_V,
        "source_current_A": evaluation.source_current_A,
        "ground_current_A": evaluation.ground_current_A,
        "active_area_mean_conductive_state": evaluation.active_area_mean_conductive_state,
        "effective_total_vertical_conductance_W_K": evaluation.effective_total_vertical_conductance_W_K,
        "scaled_electrical_residual_inf": evaluation.scaled_electrical_residual_inf,
        "scaled_thermal_residual_inf": evaluation.scaled_thermal_residual_inf,
        "ledger": evaluation.ledger,
        "solver": solve.telemetry,
        "last_scaled_update_inf": solve.last_scaled_update_inf,
        "stability": None
        if stability is None
        else {
            "code": stability.code,
            "stable": stability.stable,
            "eigenpair_count": stability.eigenpair_count,
            "rightmost_spectral_abscissa_per_s": stability.rightmost_spectral_abscissa_per_s,
            "alpha_tau_dimensionless": stability.alpha_tau_dimensionless,
            "maximum_relative_ritz_residual": float(
                np.max(stability.relative_ritz_residuals)
            ),
            "maximum_absolute_backward_error_per_s": float(
                np.max(stability.absolute_backward_errors_per_s)
            ),
            "h_half_operator_relative_difference": stability.h_half_operator_relative_difference,
            "telemetry": stability.telemetry,
        },
    }
    manifest_path = compact_root / "equilibria" / f"{identity}.json"
    manifest_hash = atomic_write_json(manifest_path, manifest)
    return {
        "identity": identity,
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": manifest_hash,
        "npz_path": npz_path.as_posix(),
        "npz_sha256": npz_hash,
        "npz_bytes": npz_path.stat().st_size,
    }


def artifact_manifest(root: Path, repository_root: Path, *, run_id: str) -> dict[str, Any]:
    files = [path for path in sorted(root.rglob("*")) if path.is_file() and path.name != "artifact_manifest.json"]
    return {
        "schema_version": "q2_current_clamp_cc_b_artifact_manifest_v1",
        "run_id": run_id,
        "artifacts": [
            {
                "path": path.relative_to(repository_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in files
        ],
    }

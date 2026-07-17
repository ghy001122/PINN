"""Evidence-integrity and common-scale diagnostics for N0-CV-E v3.

This module deliberately separates adjacent-state trajectory ledgers from the
older instantaneous algebraic bookkeeping audit.  Frozen GT files are read but
never regenerated or modified.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import subprocess
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import yaml
from scipy.integrate import solve_ivp

from pinnpcm.physics.conductivity import arrhenius_reference, mixed_conductivity
from pinnpcm.physics.electrostatics import solve_series_electrostatics
from pinnpcm.physics.gt_solver import _rhs_factory
from pinnpcm.physics.params import merge_params, spatial_param_profiles
from pinnpcm.physics.voltage_protocols import get_voltage_protocol


def raw_sha256(path: Path) -> str:
    """Hash binary bytes without newline or semantic normalization."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_lf_sha256(path: Path) -> str:
    """Hash UTF-8 text after canonical CRLF/CR to LF normalization."""

    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def semantic_sha256(path: Path) -> str:
    """Hash YAML/JSON by canonical parsed semantics, independent of newlines."""

    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    elif suffix == ".json":
        payload = json.loads(text)
    else:
        raise ValueError(f"Semantic hashing is only defined for YAML/JSON: {path}")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def stable_file_hash(path: Path) -> dict[str, str]:
    """Return the preregistered cross-platform hash mode and digest."""

    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml", ".json"}:
        return {"mode": "canonical_semantic_json", "sha256": semantic_sha256(path)}
    if suffix in {".py", ".md", ".txt", ".csv"}:
        return {"mode": "canonical_lf", "sha256": canonical_lf_sha256(path)}
    return {"mode": "raw_bytes", "sha256": raw_sha256(path)}


def deterministic_npz_bytes(arrays: Mapping[str, np.ndarray]) -> bytes:
    """Build a deterministic compressed NPZ with sorted members and fixed time."""

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(arrays):
            member = io.BytesIO()
            np.lib.format.write_array(member, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, member.getvalue())
    return output.getvalue()


def write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = deterministic_npz_bytes(arrays)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_frozen_gt(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    with np.load(path, allow_pickle=False) as archive:
        gt = {key: np.asarray(archive[key]) for key in archive.files if key != "params_json"}
        raw_params = json.loads(str(np.asarray(archive["params_json"])))
    return gt, merge_params(raw_params)


def nrmse95(prediction: np.ndarray, target: np.ndarray) -> float:
    target_array = np.asarray(target, dtype=float)
    scale = max(
        float(np.quantile(target_array, 0.95) - np.quantile(target_array, 0.05)),
        1.0e-30,
    )
    return float(np.sqrt(np.mean((np.asarray(prediction, dtype=float) - target_array) ** 2)) / scale)


def _safe_relative(balance: np.ndarray, terms: list[np.ndarray]) -> np.ndarray:
    denominator = np.zeros_like(np.asarray(balance, dtype=float))
    for term in terms:
        denominator = denominator + np.abs(np.asarray(term, dtype=float))
    return np.abs(np.asarray(balance, dtype=float)) / np.maximum(denominator, 1.0e-30)


def _trajectory_sources(
    gt_like: Mapping[str, np.ndarray], params: dict[str, Any]
) -> dict[str, np.ndarray]:
    t = np.asarray(gt_like["t"], dtype=float)
    x = np.asarray(gt_like["x"], dtype=float)
    c_v = np.asarray(gt_like["c_v"], dtype=float)
    temperature = np.asarray(gt_like["T"], dtype=float)
    m = np.asarray(gt_like["m"], dtype=float)
    voltage = np.asarray(gt_like["V"], dtype=float)
    nx = x.size
    dx = float(params["L_eff"]) / nx
    profiles = {**params, **spatial_param_profiles(x, params)}

    reaction_rate = arrhenius_reference(
        float(params["k_r0"]), float(params["E_r_eV"]), temperature, float(params["T0"])
    )
    reaction = np.sum(reaction_rate * (c_v - float(params["c_v0"])), axis=1) * dx
    joule = np.zeros(t.size, dtype=float)
    sink = np.sum(
        float(params["gamma_sub"]) * (temperature - float(params["T0"])), axis=1
    ) * dx
    current_density = np.zeros(t.size, dtype=float)
    for index in range(t.size):
        sigma = mixed_conductivity(c_v[index], temperature[index], m[index], profiles)
        electrical = solve_series_electrostatics(float(voltage[index]), sigma, params, dx)
        current_density[index] = float(electrical["J"])
        joule[index] = np.sum(current_density[index] * np.asarray(electrical["E"])) * dx

    return {
        "reaction_integrand_per_m_s": reaction,
        "joule_integrand_W_per_m2": joule,
        "substrate_sink_integrand_W_per_m2": sink,
        "left_defect_flux": np.zeros(t.size, dtype=float),
        "right_defect_flux": np.zeros(t.size, dtype=float),
        "left_heat_flux_W_per_m2": np.zeros(t.size, dtype=float),
        "right_heat_flux_W_per_m2": np.zeros(t.size, dtype=float),
        "current_density_A_per_m2": current_density,
    }


def trajectory_ledgers(
    gt_like: Mapping[str, np.ndarray], params: dict[str, Any]
) -> dict[str, Any]:
    """Compute independent adjacent-state mass and energy ledgers.

    Storage uses differences of saved states. Source and boundary terms are
    integrated independently over each adjacent time interval.
    """

    t = np.asarray(gt_like["t"], dtype=float)
    x = np.asarray(gt_like["x"], dtype=float)
    c_v = np.asarray(gt_like["c_v"], dtype=float)
    temperature = np.asarray(gt_like["T"], dtype=float)
    dx = float(params["L_eff"]) / x.size
    dt = np.diff(t)
    if t.ndim != 1 or t.size < 2 or np.any(dt <= 0.0):
        raise ValueError("Trajectory times must be one-dimensional and strictly increasing.")

    sources = _trajectory_sources(gt_like, params)
    mass = np.sum(c_v, axis=1) * dx
    energy = np.sum(float(params["rho"]) * float(params["Cp"]) * temperature, axis=1) * dx

    mass_storage = np.diff(mass)
    mass_boundary = 0.5 * (
        sources["right_defect_flux"][:-1]
        - sources["left_defect_flux"][:-1]
        + sources["right_defect_flux"][1:]
        - sources["left_defect_flux"][1:]
    ) * dt
    mass_reaction = 0.5 * (
        sources["reaction_integrand_per_m_s"][:-1]
        + sources["reaction_integrand_per_m_s"][1:]
    ) * dt
    mass_balance = mass_storage + mass_boundary + mass_reaction
    mass_relative = _safe_relative(mass_balance, [mass_storage, mass_boundary, mass_reaction])

    energy_storage = np.diff(energy)
    energy_boundary = 0.5 * (
        sources["right_heat_flux_W_per_m2"][:-1]
        - sources["left_heat_flux_W_per_m2"][:-1]
        + sources["right_heat_flux_W_per_m2"][1:]
        - sources["left_heat_flux_W_per_m2"][1:]
    ) * dt
    energy_joule = 0.5 * (
        sources["joule_integrand_W_per_m2"][:-1]
        + sources["joule_integrand_W_per_m2"][1:]
    ) * dt
    energy_sink = 0.5 * (
        sources["substrate_sink_integrand_W_per_m2"][:-1]
        + sources["substrate_sink_integrand_W_per_m2"][1:]
    ) * dt
    energy_balance = energy_storage + energy_boundary - energy_joule + energy_sink
    energy_relative = _safe_relative(
        energy_balance, [energy_storage, energy_boundary, energy_joule, energy_sink]
    )

    total_mass_terms = [
        mass[-1] - mass[0],
        float(np.sum(mass_boundary)),
        float(np.sum(mass_reaction)),
    ]
    total_mass_balance = sum(total_mass_terms)
    total_mass_relative = abs(total_mass_balance) / max(sum(abs(value) for value in total_mass_terms), 1.0e-30)
    total_energy_terms = [
        energy[-1] - energy[0],
        float(np.sum(energy_boundary)),
        -float(np.sum(energy_joule)),
        float(np.sum(energy_sink)),
    ]
    total_energy_balance = sum(total_energy_terms)
    total_energy_relative = abs(total_energy_balance) / max(
        sum(abs(value) for value in total_energy_terms), 1.0e-30
    )

    return {
        "semantics": "adjacent_saved_state_storage_plus_independent_trapezoidal_terms",
        "interval_count": int(dt.size),
        "defect": {
            "max_interval_normalized_imbalance": float(np.max(mass_relative)),
            "p95_interval_normalized_imbalance": float(np.quantile(mass_relative, 0.95)),
            "total_normalized_imbalance": float(total_mass_relative),
            "gate_value": float(max(np.max(mass_relative), total_mass_relative)),
            "storage_change": float(mass[-1] - mass[0]),
            "boundary_flux_integral": float(np.sum(mass_boundary)),
            "reaction_integral": float(np.sum(mass_reaction)),
        },
        "energy": {
            "max_interval_normalized_imbalance": float(np.max(energy_relative)),
            "p95_interval_normalized_imbalance": float(np.quantile(energy_relative, 0.95)),
            "total_normalized_imbalance": float(total_energy_relative),
            "gate_value": float(max(np.max(energy_relative), total_energy_relative)),
            "storage_change_J_per_m2": float(energy[-1] - energy[0]),
            "boundary_heat_integral_J_per_m2": float(np.sum(energy_boundary)),
            "joule_integral_J_per_m2": float(np.sum(energy_joule)),
            "substrate_sink_integral_J_per_m2": float(np.sum(energy_sink)),
        },
    }


def tamper_detection(gt: Mapping[str, np.ndarray], params: dict[str, Any]) -> dict[str, Any]:
    baseline = trajectory_ledgers(gt, params)
    index = max(1, min(len(np.asarray(gt["t"])) - 2, len(np.asarray(gt["t"])) // 2))

    mass_tampered = {key: np.asarray(value).copy() for key, value in gt.items()}
    mass_tampered["c_v"][index] = np.clip(mass_tampered["c_v"][index] + 0.01, 0.0, 1.0)
    mass_result = trajectory_ledgers(mass_tampered, params)

    energy_tampered = {key: np.asarray(value).copy() for key, value in gt.items()}
    energy_tampered["T"][index] = energy_tampered["T"][index] + 5.0
    energy_result = trajectory_ledgers(energy_tampered, params)
    return {
        "tampered_time_index": int(index),
        "baseline_defect_gate_value": baseline["defect"]["gate_value"],
        "tampered_defect_gate_value": mass_result["defect"]["gate_value"],
        "baseline_energy_gate_value": baseline["energy"]["gate_value"],
        "tampered_energy_gate_value": energy_result["energy"]["gate_value"],
        "defect_tamper_detected": mass_result["defect"]["gate_value"] > 0.01,
        "energy_tamper_detected": energy_result["energy"]["gate_value"] > 0.05,
    }


def radau_replay_interval(
    gt: Mapping[str, np.ndarray], params: dict[str, Any], *, rtol: float, atol: float
) -> dict[str, Any]:
    t = np.asarray(gt["t"], dtype=float)
    x = np.asarray(gt["x"], dtype=float)
    c_v = np.asarray(gt["c_v"], dtype=float)
    temperature = np.asarray(gt["T"], dtype=float)
    m = np.asarray(gt["m"], dtype=float)
    phase_increment = np.max(np.abs(np.diff(m, axis=0)), axis=1)
    index = int(np.argmax(phase_increment))
    nx = x.size
    dx = float(params["L_eff"]) / nx
    profiles = {**params, **spatial_param_profiles(x, params)}
    voltage_fn = get_voltage_protocol("triangle", float(t[-1]), params)
    rhs = _rhs_factory(voltage_fn, profiles, nx, dx)
    initial = np.concatenate([c_v[index], temperature[index], m[index]])
    target = np.concatenate([c_v[index + 1], temperature[index + 1], m[index + 1]])
    solution = solve_ivp(
        rhs,
        (float(t[index]), float(t[index + 1])),
        initial,
        method="Radau",
        t_eval=[float(t[index + 1])],
        rtol=float(rtol),
        atol=float(atol),
    )
    if not solution.success:
        return {"success": False, "message": solution.message, "selected_interval_index": index}
    prediction = solution.y[:, -1]
    blocks: dict[str, float] = {}
    for name, start, end in (("c_v", 0, nx), ("T", nx, 2 * nx), ("m", 2 * nx, 3 * nx)):
        scale = max(float(np.sqrt(np.mean(target[start:end] ** 2))), 1.0e-30)
        blocks[name] = float(np.sqrt(np.mean((prediction[start:end] - target[start:end]) ** 2)) / scale)
    return {
        "success": True,
        "selected_interval_index": index,
        "t_start_s": float(t[index]),
        "t_end_s": float(t[index + 1]),
        "relative_rms": blocks,
        "maximum_relative_rms": max(blocks.values()),
    }


def _numpy_rhs_trajectory(
    trajectory: Mapping[str, np.ndarray], params: dict[str, Any]
) -> np.ndarray:
    t = np.asarray(trajectory["t"], dtype=float)
    x = np.asarray(trajectory["x"], dtype=float)
    nx = x.size
    dx = float(params["L_eff"]) / nx
    profiles = {**params, **spatial_param_profiles(x, params)}
    voltage_fn = get_voltage_protocol("triangle", float(t[-1]), params)
    rhs = _rhs_factory(voltage_fn, profiles, nx, dx)
    values = []
    for index, time_s in enumerate(t):
        state = np.concatenate(
            [trajectory["c_v"][index], trajectory["T"][index], trajectory["m"][index]]
        )
        values.append(rhs(float(time_s), np.asarray(state, dtype=float)))
    return np.asarray(values, dtype=float)


def _common_electrical_fields(
    trajectory: Mapping[str, np.ndarray], params: dict[str, Any]
) -> dict[str, np.ndarray]:
    x = np.asarray(trajectory["x"], dtype=float)
    voltage = np.asarray(trajectory["V"], dtype=float)
    c_v = np.asarray(trajectory["c_v"], dtype=float)
    temperature = np.asarray(trajectory["T"], dtype=float)
    m = np.asarray(trajectory["m"], dtype=float)
    dx = float(params["L_eff"]) / x.size
    profiles = {**params, **spatial_param_profiles(x, params)}
    result = {
        "sigma": np.zeros_like(c_v),
        "E": np.zeros_like(c_v),
        "phi": np.zeros_like(c_v),
        "J": np.zeros(voltage.size),
        "I": np.zeros(voltage.size),
        "G": np.zeros(voltage.size),
    }
    for index, applied in enumerate(voltage):
        sigma = mixed_conductivity(c_v[index], temperature[index], m[index], profiles)
        electrical = solve_series_electrostatics(float(applied), sigma, params, dx)
        result["sigma"][index] = sigma
        result["E"][index] = electrical["E"]
        result["phi"][index] = electrical["phi"]
        for key in ("J", "I", "G"):
            result[key][index] = float(electrical[key])
    return result


def common_cv_score(
    trajectory: Mapping[str, np.ndarray],
    frozen_gt: Mapping[str, np.ndarray],
    params: dict[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    """Score any model trajectory with one frozen SI/CV convention."""

    t = np.asarray(trajectory["t"], dtype=float)
    x = np.asarray(trajectory["x"], dtype=float)
    nx = x.size
    derivative = np.concatenate(
        [
            np.gradient(np.asarray(trajectory["c_v"]), t, axis=0, edge_order=2),
            np.gradient(np.asarray(trajectory["T"]), t, axis=0, edge_order=2),
            np.gradient(np.asarray(trajectory["m"]), t, axis=0, edge_order=2),
        ],
        axis=1,
    )
    rhs = _numpy_rhs_trajectory(trajectory, params)
    residual_si = derivative - rhs
    residual_scales = registry["residual_scales"]
    residual_rms = {
        "r_c": float(np.sqrt(np.mean((residual_si[:, :nx] / float(residual_scales["r_c_per_s"])) ** 2))),
        "r_T": float(
            np.sqrt(np.mean((residual_si[:, nx : 2 * nx] / float(residual_scales["r_T_K_per_s"])) ** 2))
        ),
        "r_m": float(
            np.sqrt(np.mean((residual_si[:, 2 * nx :] / float(residual_scales["r_m_per_s"])) ** 2))
        ),
    }
    electrical = _common_electrical_fields(trajectory, params)
    field_predictions = {
        "c_v": np.asarray(trajectory["c_v"]),
        "T": np.asarray(trajectory["T"]),
        "m": np.asarray(trajectory["m"]),
        "phi": electrical["phi"],
        "sigma": electrical["sigma"],
    }
    field_scores = {key: nrmse95(value, np.asarray(frozen_gt[key])) for key, value in field_predictions.items()}

    profiles = spatial_param_profiles(x, params)
    material = np.asarray(profiles["k_th"])
    changes = np.flatnonzero(material[:-1] != material[1:])
    interface_left = int(changes[0]) if changes.size else nx // 2 - 1
    interface_right = interface_left + 1
    state_scales = {
        "phi": float(registry["voltage_scale_V"]),
        "c_v": float(registry["concentration_scale"]),
        "T": float(registry["temperature_scale_K"]),
        "m": float(registry["phase_scale"]),
    }
    # A cell-centre jump is not a dual-sided interface trace.  Reconstruct
    # one-sided face values from two cells on each side, then compare those
    # traces.  This remains score-only because the temporal CV network does
    # not learn independent subdomain interface unknowns.
    if interface_left < 1 or interface_right + 1 >= nx:
        raise ValueError("Interface trace reconstruction requires two cells on each side.")
    interface_state = {
        key: float(
            np.sqrt(
                np.mean(
                    (
                        (
                            1.5 * field_predictions[key][:, interface_right]
                            - 0.5 * field_predictions[key][:, interface_right + 1]
                            - 1.5 * field_predictions[key][:, interface_left]
                            + 0.5 * field_predictions[key][:, interface_left - 1]
                        )
                        / max(scale, 1.0e-30)
                    )
                    ** 2
                )
            )
        )
        for key, scale in state_scales.items()
    }
    interface_state["semantics"] = "score_only_one_sided_linear_face_trace_reconstruction"

    def _face_fluxes(states: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
        c_local = np.asarray(states["c_v"], dtype=float)
        t_local = np.asarray(states["T"], dtype=float)
        m_local = np.asarray(states["m"], dtype=float)
        v_local = np.asarray(states["V"], dtype=float)
        local_profiles = {**params, **spatial_param_profiles(x, params)}
        defect = np.zeros(t.size, dtype=float)
        heat = np.zeros(t.size, dtype=float)
        current = np.zeros(t.size, dtype=float)
        k_left = float(local_profiles["k_th"][interface_left])
        k_right = float(local_profiles["k_th"][interface_right])
        k_face = 2.0 * k_left * k_right / max(k_left + k_right, 1.0e-30)
        for time_index in range(t.size):
            sigma_local = mixed_conductivity(
                c_local[time_index], t_local[time_index], m_local[time_index], local_profiles
            )
            electrical_local = solve_series_electrostatics(
                float(v_local[time_index]), sigma_local, params, dx
            )
            current[time_index] = float(electrical_local["J"])
            temperature_face = 0.5 * (
                t_local[time_index, interface_left] + t_local[time_index, interface_right]
            )
            d_face = 0.5 * (
                arrhenius_reference(
                    float(local_profiles["D_v0"][interface_left]),
                    float(params["E_D_eV"]),
                    temperature_face,
                    float(params["T0"]),
                )
                + arrhenius_reference(
                    float(local_profiles["D_v0"][interface_right]),
                    float(params["E_D_eV"]),
                    temperature_face,
                    float(params["T0"]),
                )
            )
            mu_face = 0.5 * (
                arrhenius_reference(
                    float(local_profiles["mu_v0"][interface_left]),
                    float(params["E_mu_eV"]),
                    temperature_face,
                    float(params["T0"]),
                )
                + arrhenius_reference(
                    float(local_profiles["mu_v0"][interface_right]),
                    float(params["E_mu_eV"]),
                    temperature_face,
                    float(params["T0"]),
                )
            )
            c_face = 0.5 * (
                c_local[time_index, interface_left] + c_local[time_index, interface_right]
            )
            e_face = 0.5 * (
                electrical_local["E"][interface_left]
                + electrical_local["E"][interface_right]
            )
            defect[time_index] = (
                -d_face
                * (c_local[time_index, interface_right] - c_local[time_index, interface_left])
                / dx
                + mu_face * c_face * (1.0 - c_face) * e_face
            )
            heat[time_index] = -k_face * (
                t_local[time_index, interface_right] - t_local[time_index, interface_left]
            ) / dx
        return {"current": current, "heat": heat, "defect": defect}

    predicted_flux = _face_fluxes({**trajectory, "V": np.asarray(trajectory["V"])})
    target_flux = _face_fluxes({**frozen_gt, "V": np.asarray(frozen_gt["V"])})
    interface_flux_accuracy = {
        name: nrmse95(predicted_flux[name], target_flux[name])
        for name in ("current", "heat", "defect")
    }
    interface_flux_accuracy["semantics"] = "score_only_predicted_face_flux_vs_frozen_gt_face_flux"
    structural_face_conservation = {
        "current_equal_and_opposite": True,
        "heat_equal_and_opposite": True,
        "defect_equal_and_opposite": True,
        "semantics": "shared_control_volume_face_structural_invariant_not_learned_performance",
    }

    current_matrix = electrical["sigma"] * electrical["E"]
    current_scale = np.maximum(np.abs(electrical["J"]), 1.0e-30)
    current_spread = float(
        np.max((np.max(current_matrix, axis=1) - np.min(current_matrix, axis=1)) / current_scale)
    )
    ledgers = trajectory_ledgers({**trajectory, "V": np.asarray(trajectory["V"])}, params)

    t_norm = t / max(float(t[-1]), 1.0e-30)
    interface_mask = np.zeros(nx, dtype=bool)
    half_width = 2
    interface_mask[max(0, interface_left - half_width + 1) : min(nx, interface_right + half_width)] = True
    transition_mask = (t_norm >= 0.35) & (t_norm <= 0.65)
    ordinary_time = ((t_norm >= 0.05) & (t_norm <= 0.30)) | ((t_norm >= 0.70) & (t_norm <= 0.95))
    ordinary_space = ~interface_mask
    region_masks = {
        "near_interface": (np.ones(t.size, dtype=bool), interface_mask),
        "near_transition": (transition_mask, np.ones(nx, dtype=bool)),
        "ordinary": (ordinary_time, ordinary_space),
    }
    regions: dict[str, Any] = {}
    for name, (time_mask, space_mask) in region_masks.items():
        entry = {
            "time_count": int(np.sum(time_mask)),
            "cell_count": int(np.sum(space_mask)),
            "sample_count": int(np.sum(time_mask) * np.sum(space_mask)),
            "field_nrmse95": {},
        }
        for field, prediction in field_predictions.items():
            pred = prediction[np.ix_(time_mask, space_mask)]
            target = np.asarray(frozen_gt[field])[np.ix_(time_mask, space_mask)]
            entry["field_nrmse95"][field] = nrmse95(pred, target)
        regions[name] = entry

    initial_errors = {
        "c_v": float(np.max(np.abs(trajectory["c_v"][0] - frozen_gt["c_v"][0]))),
        "T": float(
            np.max(np.abs(trajectory["T"][0] - frozen_gt["T"][0]))
            / max(float(registry["temperature_scale_K"]), 1.0e-30)
        ),
        "m": float(np.max(np.abs(trajectory["m"][0] - frozen_gt["m"][0]))),
    }
    voltage_scale = max(float(registry["voltage_scale_V"]), 1.0e-30)
    dx = float(params["L_eff"]) / nx
    left_boundary = electrical["phi"][:, 0] + 0.5 * electrical["E"][:, 0] * dx
    right_boundary = electrical["phi"][:, -1] - 0.5 * electrical["E"][:, -1] * dx
    boundary_errors = {
        "phi_left": float(np.max(np.abs(left_boundary - trajectory["V"])) / voltage_scale),
        "phi_right": float(np.max(np.abs(right_boundary)) / voltage_scale),
        "defect_flux_left": 0.0,
        "defect_flux_right": 0.0,
        "heat_flux_left": 0.0,
        "heat_flux_right": 0.0,
    }
    all_values = [*field_predictions.values(), electrical["E"], electrical["I"], electrical["G"]]
    return {
        "normalization": "single_frozen_dimensionless_registry",
        "cv_residual_rms": residual_rms,
        "discrete_electrical_rms": float(
            np.sqrt(np.mean(((current_matrix - electrical["J"][:, None]) / current_scale[:, None]) ** 2))
        ),
        "port_full_trace_nrmse95": nrmse95(electrical["I"], np.asarray(frozen_gt["I"])),
        "field_score_only_nrmse95": field_scores,
        "interface_state_rms": interface_state,
        "interface_flux_accuracy_nrmse95": interface_flux_accuracy,
        "interface_flux_rms": interface_flux_accuracy,
        "structural_face_conservation": structural_face_conservation,
        "terminal_current_conservation_normalized_error": current_spread,
        "defect_mass_ledger": ledgers["defect"],
        "global_energy_ledger": ledgers["energy"],
        "initial_condition_errors": initial_errors,
        "boundary_condition_errors": boundary_errors,
        "region_diagnostics": regions,
        "finite_outputs": bool(all(bool(np.isfinite(value).all()) for value in all_values)),
        "bounded_states": bool(
            np.min(trajectory["c_v"]) >= 0.0
            and np.max(trajectory["c_v"]) <= 1.0
            and np.min(trajectory["m"]) >= 0.0
            and np.max(trajectory["m"]) <= 1.0
            and np.min(trajectory["T"]) >= 1.0
        ),
    }


def model_trajectory(model: torch.nn.Module, gt: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Evaluate legacy spatial models without using GT fields as inputs."""

    x = np.asarray(gt["x"], dtype=float)
    t = np.asarray(gt["t"], dtype=float)
    x_norm = x / float(np.max(x) + 0.5 * (x[1] - x[0]))
    t_norm = t / float(t[-1])
    xx = np.tile(x_norm, t.size)
    tt = np.repeat(t_norm, x.size)
    coords = torch.as_tensor(np.column_stack([xx, tt]), dtype=torch.float32)
    model.eval()
    with torch.no_grad():
        fields = model(coords)
    return {
        "x": x.copy(),
        "t": t.copy(),
        "V": np.asarray(gt["V"], dtype=float).copy(),
        "c_v": fields["c_v"].cpu().numpy().reshape(t.size, x.size),
        "T": fields["T"].cpu().numpy().reshape(t.size, x.size),
        "m": fields["m"].cpu().numpy().reshape(t.size, x.size),
    }


def nested_get(payload: Mapping[str, Any], dotted_path: str) -> tuple[bool, Any]:
    current: Any = payload
    for key in dotted_path.split("."):
        if not isinstance(current, Mapping) or key not in current:
            return False, None
        current = current[key]
    return True, current


def valid_gate_value(value: Any) -> bool:
    """Return True only for nonempty, recursively finite gate payloads.

    Booleans and finite real scalars are valid leaves.  Empty containers,
    strings, ``None``, non-finite numbers, and containers containing any such
    value fail closed.  This explicitly prevents ``all(empty)`` passes.
    """

    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return bool(value) and all(valid_gate_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return bool(value) and all(valid_gate_value(item) for item in value)
    return False


def gate_coverage_table(
    config: Mapping[str, Any], payload: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Map every configured v3 gate to a result path and fail closed."""

    expected = list(config["preflight_gates"].keys()) + list(config["result_gates"].keys())
    coverage = dict(config["gate_coverage"])
    rows: list[dict[str, Any]] = []
    for gate in expected:
        mapped_path = coverage.get(gate)
        executed = False
        value: Any = None
        finite = False
        if mapped_path and payload is not None:
            executed, value = nested_get(payload, mapped_path)
            if executed:
                finite = valid_gate_value(value)
        rows.append(
            {
                "gate": gate,
                "result_key": mapped_path,
                "mapped": mapped_path is not None,
                "executed": executed,
                "finite_or_boolean": finite,
                "value": value,
                "fail_closed": not (mapped_path is not None and executed and finite),
            }
        )
    extras = sorted(set(coverage) - set(expected))
    return {
        "rows": rows,
        "expected_gate_count": len(expected),
        "mapped_gate_count": sum(row["mapped"] for row in rows),
        "executed_gate_count": sum(row["executed"] for row in rows),
        "extra_mappings": extras,
        "mapping_complete": all(row["mapped"] for row in rows) and not extras,
        "execution_complete": all(not row["fail_closed"] for row in rows),
        "semantics": "missing_unexecuted_or_nonfinite_is_failure",
    }


def v2_gate_coverage_audit(v2_config: Mapping[str, Any], v2_result: Mapping[str, Any]) -> dict[str, Any]:
    """Audit historical v2 without changing its config, hashes, or outputs."""

    mappings = {
        "ic_bc_max_normalized_error": None,
        "endpoint_flux_rms_max": "result.gates.checks.endpoint_flux",
        "port_full_trace_nrmse95_max": "result.gates.checks.port",
        "residual_rms_max": "result.gates.checks.heldout_residuals",
        "field_score_only_nrmse95_max": "result.gates.checks.fields",
        "interface_state_rms_max": "result.gates.checks.interface_state",
        "interface_flux_rms_max": "result.gates.checks.interface_flux",
        "terminal_current_conservation_max": "result.gates.checks.current_conservation",
        "global_energy_account_imbalance_max": "result.gates.checks.energy_conservation",
        "finite_states_required": "result.gates.checks.finite_states",
        "positive_temperature_required": "result.gates.checks.physical_bounds",
        "bounded_c_v_and_m_required": "result.gates.checks.physical_bounds",
        "frozen_gt_hash_unchanged_required": None,
        "heldout_residual_required": "result.gates.checks.heldout_residuals",
        "minimum_passing_seeds": None,
        "total_seeds": None,
        "single_seed_success_label": "result.status",
        "defect_mass_ledger_max": None,
    }
    rows = []
    gates = dict(v2_config["gates"])
    for gate in [*gates, "defect_mass_ledger_max"]:
        path = mappings[gate]
        present, value = nested_get(v2_result, path) if path else (False, None)
        explicit = present and gate not in {"positive_temperature_required", "bounded_c_v_and_m_required"}
        rows.append(
            {
                "gate": gate,
                "configured": gate in gates,
                "result_key": path,
                "executed": present,
                "explicit_check": explicit,
                "value": value,
                "fail_closed": not (gate in gates and explicit),
            }
        )
    return {
        "rows": rows,
        "coverage_complete": all(not row["fail_closed"] for row in rows),
        "documented_gaps": [row["gate"] for row in rows if row["fail_closed"]],
        "historical_outputs_rewritten": False,
    }


def git_tracked(path: Path, root: Path) -> bool:
    relative = str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def query_remote_ci(commit: str, *, timeout_s: float = 30.0) -> dict[str, Any]:
    command = [
        "gh",
        "run",
        "list",
        "--repo",
        "ghy001122/PINN",
        "--commit",
        commit,
        "--limit",
        "20",
        "--json",
        "databaseId,name,status,conclusion,workflowName,headSha,url,createdAt,updatedAt",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"verified": False, "status": "unverified", "error": str(error), "runs": []}
    if result.returncode != 0:
        return {
            "verified": False,
            "status": "unverified",
            "error": result.stderr.strip() or result.stdout.strip(),
            "runs": [],
        }
    runs = json.loads(result.stdout or "[]")
    return {
        "verified": True,
        "status": "no_runs_for_commit" if not runs else "runs_found",
        "runs": runs,
        "command": " ".join(command),
    }


def clone_trajectory(gt: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: deepcopy(np.asarray(value)) for key, value in gt.items()}

"""Layered Qiu/LLP formula-contract audit.

This module is deliberately isolated from :mod:`pinnpcm.physics`.  It tests a
literal transcription of Qiu SI equations S3--S4 and a distinct analytic
``atanh`` inverse identity for a configured tanh limiting branch.  Neither
path is evidence of unpublished Qiu author code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class ContractParameters:
    beta_per_K: float
    hysteresis_width_K: float
    critical_temperature_K: float
    proximity_gamma_dimensionless: float


def _array64(value: float | np.ndarray) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _validate_fraction(fraction: float | np.ndarray) -> np.ndarray:
    values = _array64(fraction)
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0) or np.any(values >= 1.0):
        raise ValueError("reversal fractions must be finite and strictly inside (0, 1)")
    return values


def _validate_branch(delta: int | np.ndarray) -> np.ndarray:
    values = np.asarray(delta, dtype=np.int8)
    if np.any((values != -1) & (values != 1)):
        raise ValueError("branch delta must be -1 or +1")
    return values


def proximity_kernel(x: float | np.ndarray, gamma_dimensionless: float) -> float | np.ndarray:
    """Return Qiu SI equation S4 without normalizing ``P(0)`` by hand."""

    values = _array64(x)
    result = 0.5 * (1.0 - np.sin(float(gamma_dimensionless) * values)) * (
        1.0 + np.tanh(np.pi**2 - 2.0 * np.pi * values)
    )
    return float(result) if result.ndim == 0 else result


def qiu_literal_proximity_temperature(
    delta_new: int | np.ndarray,
    reversal_fraction: float | np.ndarray,
    reversal_temperature_K: float | np.ndarray,
    params: ContractParameters,
) -> float | np.ndarray:
    """Transcribe Qiu SI equation S3 literally, with no ``atanh`` insertion."""

    delta = _validate_branch(delta_new)
    fraction = _validate_fraction(reversal_fraction)
    temperature = _array64(reversal_temperature_K)
    result = (
        delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - (2.0 * fraction - 1.0) / params.beta_per_K
        - temperature
    )
    if not np.all(np.isfinite(result)):
        raise ValueError("literal printed-S3 proximity temperature is non-finite")
    return float(result) if result.ndim == 0 else result


def de_almeida_sena_atanh_proximity_temperature(
    delta_new: int | np.ndarray,
    reversal_fraction: float | np.ndarray,
    reversal_temperature_K: float | np.ndarray,
    params: ContractParameters,
) -> float | np.ndarray:
    """Invert the configured tanh limiting branch analytically.

    This is canonical only within the configured tanh limiting-loop inversion;
    it is not a Qiu-author-code claim and is not universal LLP.
    """

    delta = _validate_branch(delta_new)
    fraction = _validate_fraction(reversal_fraction)
    temperature = _array64(reversal_temperature_K)
    result = (
        delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - np.arctanh(2.0 * fraction - 1.0) / params.beta_per_K
        - temperature
    )
    if not np.all(np.isfinite(result)):
        raise ValueError("atanh inverse proximity temperature is non-finite")
    return float(result) if result.ndim == 0 else result


def canonical_llp_proximity_temperature(*args: Any, **kwargs: Any) -> float | np.ndarray:
    """Deprecated alias: canonical only within the configured tanh limiting-loop
    inversion; not a Qiu-author-code claim and not universal LLP.
    """

    return de_almeida_sena_atanh_proximity_temperature(*args, **kwargs)


def _major_fraction(temperature_K: np.ndarray, delta: np.ndarray, params: ContractParameters) -> np.ndarray:
    argument = params.beta_per_K * (
        delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - temperature_K
    )
    return 0.5 + 0.5 * np.tanh(argument)


def _realized_fraction(
    reversal_fraction: np.ndarray,
    proximity_temperature_K: np.ndarray,
    params: ContractParameters,
    *,
    contract: str,
) -> np.ndarray:
    p0 = float(proximity_kernel(0.0, params.proximity_gamma_dimensionless))
    if contract == "atanh":
        anchor = np.arctanh(2.0 * reversal_fraction - 1.0)
    elif contract == "literal":
        anchor = 2.0 * reversal_fraction - 1.0
    else:
        raise ValueError(f"unknown contract: {contract}")
    argument = anchor + params.beta_per_K * proximity_temperature_K * (1.0 - p0)
    return 0.5 + 0.5 * np.tanh(argument)


def _scalar_oracle_row(
    fraction: float,
    old_delta: int,
    params: ContractParameters,
) -> dict[str, float | int]:
    if not 0.0 < fraction < 1.0:
        raise ValueError("oracle fraction must be strictly inside (0, 1)")
    reversal_temperature = (
        old_delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - np.arctanh(2.0 * fraction - 1.0) / params.beta_per_K
    )
    new_delta = -old_delta
    literal_tpr = (
        new_delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - (2.0 * fraction - 1.0) / params.beta_per_K
        - reversal_temperature
    )
    atanh_tpr = (
        new_delta * params.hysteresis_width_K / 2.0
        + params.critical_temperature_K
        - np.arctanh(2.0 * fraction - 1.0) / params.beta_per_K
        - reversal_temperature
    )
    p0 = 0.5 * (1.0 + np.tanh(np.pi**2))
    literal_realized = 0.5 + 0.5 * np.tanh(
        (2.0 * fraction - 1.0) + params.beta_per_K * literal_tpr * (1.0 - p0)
    )
    atanh_realized = 0.5 + 0.5 * np.tanh(
        np.arctanh(2.0 * fraction - 1.0)
        + params.beta_per_K * atanh_tpr * (1.0 - p0)
    )
    return {
        "fraction": fraction,
        "old_delta": old_delta,
        "new_delta": new_delta,
        "reversal_temperature_K": reversal_temperature,
        "literal_tpr_K": literal_tpr,
        "atanh_tpr_K": atanh_tpr,
        "literal_realized_fraction": literal_realized,
        "atanh_realized_fraction": atanh_realized,
    }


def evaluate_contract_grid(
    fractions: np.ndarray,
    old_branches: Iterable[int],
    params: ContractParameters,
) -> tuple[list[dict[str, float | int]], dict[str, Any]]:
    """Compare independent scalar oracles with vectorized audit functions."""

    fraction_grid = _validate_fraction(fractions)
    rows: list[dict[str, float | int]] = []
    discrepancies: dict[str, list[float]] = {
        "anchor": [], "literal_tpr": [], "atanh_tpr": [], "literal_state": [], "atanh_state": []
    }
    for old_delta_raw in old_branches:
        old_delta = int(old_delta_raw)
        _validate_branch(old_delta)
        new_delta = -old_delta
        reversal_temperature = (
            old_delta * params.hysteresis_width_K / 2.0
            + params.critical_temperature_K
            - np.arctanh(2.0 * fraction_grid - 1.0) / params.beta_per_K
        )
        literal_tpr = _array64(
            qiu_literal_proximity_temperature(new_delta, fraction_grid, reversal_temperature, params)
        )
        atanh_tpr = _array64(
            de_almeida_sena_atanh_proximity_temperature(new_delta, fraction_grid, reversal_temperature, params)
        )
        literal_realized = _realized_fraction(fraction_grid, literal_tpr, params, contract="literal")
        atanh_realized = _realized_fraction(fraction_grid, atanh_tpr, params, contract="atanh")
        reconstructed_anchor = _major_fraction(
            reversal_temperature,
            np.full(fraction_grid.shape, old_delta, dtype=np.int8),
            params,
        )
        for index, fraction in enumerate(fraction_grid):
            oracle = _scalar_oracle_row(float(fraction), old_delta, params)
            discrepancies["anchor"].append(abs(float(reconstructed_anchor[index]) - float(fraction)))
            discrepancies["literal_tpr"].append(abs(float(literal_tpr[index]) - float(oracle["literal_tpr_K"])))
            discrepancies["atanh_tpr"].append(abs(float(atanh_tpr[index]) - float(oracle["atanh_tpr_K"])))
            discrepancies["literal_state"].append(abs(float(literal_realized[index]) - float(oracle["literal_realized_fraction"])))
            discrepancies["atanh_state"].append(abs(float(atanh_realized[index]) - float(oracle["atanh_realized_fraction"])))
            rows.append({
                **oracle,
                "anchor_inverse_abs_error": discrepancies["anchor"][-1],
                "literal_tpr_discrepancy_K": discrepancies["literal_tpr"][-1],
                "atanh_tpr_discrepancy_K": discrepancies["atanh_tpr"][-1],
                "literal_state_discrepancy": discrepancies["literal_state"][-1],
                "atanh_state_discrepancy": discrepancies["atanh_state"][-1],
                "literal_state_jump": float(literal_realized[index] - fraction),
                "atanh_state_jump": float(atanh_realized[index] - fraction),
                "literal_temperature_contract_K": float(literal_tpr[index] * (1.0 - proximity_kernel(0.0, params.proximity_gamma_dimensionless))),
                "atanh_temperature_contract_K": float(atanh_tpr[index] * (1.0 - proximity_kernel(0.0, params.proximity_gamma_dimensionless))),
            })
    metrics = {f"max_abs_{name}_discrepancy": float(max(values, default=0.0)) for name, values in discrepancies.items()}
    return rows, metrics


def evaluate_manufactured_protocol(
    protocol_name: str,
    params: ContractParameters,
    *,
    step_refinement: int = 1,
) -> dict[str, Any]:
    """Return non-blocking, explicitly manufactured hysteresis diagnostics.

    The protocol ledger is an equation-reimplementation comparator, not Qiu
    author code.  Reversal nodes are explicit and plateaus retain direction.
    """

    if step_refinement < 1:
        raise ValueError("step_refinement must be positive")
    anchors = {
        "major_loop_parity": [318.0, 350.0, 318.0],
        "first_reversal_continuity": [320.0, 338.0, 330.0],
        "closed_minor_loop": [320.0, 340.0, 328.0, 340.0],
        "nested_loop": [320.0, 342.0, 329.0, 336.0, 332.0, 342.0],
        "return_point_memory": [320.0, 342.0, 329.0, 336.0, 329.0, 342.0],
        "wiping_out_continuation": [320.0, 342.0, 329.0, 336.0, 346.0],
    }
    if protocol_name not in anchors:
        raise ValueError(f"unknown manufactured protocol: {protocol_name}")
    nodes = anchors[protocol_name]
    samples: list[float] = [nodes[0]]
    for left, right in zip(nodes[:-1], nodes[1:]):
        segment = np.linspace(left, right, 8 * step_refinement + 1, dtype=np.float64)[1:]
        samples.extend(float(value) for value in segment)
    temperature = np.asarray(samples, dtype=np.float64)
    direction = np.empty_like(temperature, dtype=np.int8)
    direction[0] = 1
    for index in range(1, temperature.size):
        delta_t = temperature[index] - temperature[index - 1]
        direction[index] = direction[index - 1] if delta_t == 0.0 else int(np.sign(delta_t))
    reversal_indices = [0]
    reversal_indices.extend(index for index in range(1, direction.size) if direction[index] != direction[index - 1])
    reversal_indices.append(temperature.size - 1)
    major = _major_fraction(temperature, direction, params)
    return {
        "protocol": protocol_name,
        "step_refinement": step_refinement,
        "sample_count": int(temperature.size),
        "event_count": max(0, len(reversal_indices) - 2),
        "direction_sequence": [int(direction[index]) for index in reversal_indices[:-1]],
        "anchor_temperatures_K": nodes,
        "all_finite": bool(np.all(np.isfinite(major))),
        "phase_fraction_min": float(np.min(major)),
        "phase_fraction_max": float(np.max(major)),
        "state_span": float(np.ptp(major)),
        "diagnostic_only": True,
        "return_point_memory_claim_tested": protocol_name == "return_point_memory",
        "wiping_out_claim_tested": protocol_name == "wiping_out_continuation",
    }


def build_source_contract_summary(config: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Evaluate blocking formula gates and non-blocking manufactured diagnostics."""

    params = ContractParameters(**{name: float(value) for name, value in config["parameters"].items()})
    grid_cfg = config["fraction_grid"]
    fractions = np.linspace(
        float(grid_cfg["minimum"]), float(grid_cfg["maximum"]), int(grid_cfg["points"]), dtype=np.float64
    )
    rows, fidelity = evaluate_contract_grid(fractions, grid_cfg["old_branches"], params)
    p0 = float(proximity_kernel(0.0, params.proximity_gamma_dimensionless))
    atanh_jumps = np.asarray([abs(float(row["atanh_state_jump"])) for row in rows])
    literal_jumps = np.asarray([abs(float(row["literal_state_jump"])) for row in rows])
    atanh_temp = np.asarray([abs(float(row["atanh_temperature_contract_K"])) for row in rows])
    literal_temp = np.asarray([abs(float(row["literal_temperature_contract_K"])) for row in rows])
    g1_cfg = config["gates"]["source_transcription"]
    g2_cfg = config["gates"]["realized_reversal_continuity"]
    g1_state = max(fidelity["max_abs_literal_state_discrepancy"], fidelity["max_abs_atanh_state_discrepancy"])
    g1_temperature = max(fidelity["max_abs_literal_tpr_discrepancy"], fidelity["max_abs_atanh_tpr_discrepancy"])
    g1_pass = g1_state <= float(g1_cfg["max_abs_state_discrepancy"]) and g1_temperature <= float(g1_cfg["max_abs_temperature_discrepancy_K"])
    g2_phase = float(np.max(atanh_jumps))
    g2_temperature = float(np.max(atanh_temp) / params.hysteresis_width_K)
    g2_pass = g2_phase <= float(g2_cfg["max_abs_phase_fraction_jump"]) and g2_temperature <= float(g2_cfg["max_abs_normalized_temperature_contract_residual"])
    protocols = [
        evaluate_manufactured_protocol(name, params, step_refinement=int(refinement))
        for name in config["manufactured_protocols"]["protocols"]
        for refinement in config["manufactured_protocols"]["step_refinements"]
    ]
    summary = {
        "schema_version": config["schema_version"],
        "task_id": config["task_id"],
        "new_formal_scientific_experiments": 0,
        "new_claim_bearing_device_forward_runs": 0,
        "formula_contract_evaluations": len(rows),
        "test_only_smoke_runs": 0,
        "external_validation": False,
        "qiu_author_intent_inferred": False,
        "qiu_author_code_verified": False,
        "sena_2026_author_code_verified": False,
        "contract_ids": [item["id"] for item in config["contracts"]],
        "proximity_kernel": {
            "P_at_zero": p0,
            "analytic_normalization_deficit": 1.0 - p0,
            "deficit_is_float_rounding": False,
        },
        "source_transcription_fidelity": {
            **fidelity,
            "max_abs_state_discrepancy": g1_state,
            "max_abs_temperature_discrepancy_K": g1_temperature,
            "gate_pass": g1_pass,
        },
        "anchor_inverse_identity": {
            "max_abs_fraction_error": fidelity["max_abs_anchor_discrepancy"],
            "grid_points_per_branch": int(grid_cfg["points"]),
            "branches": list(grid_cfg["old_branches"]),
            "gate_pass": fidelity["max_abs_anchor_discrepancy"] <= float(g1_cfg["max_abs_state_discrepancy"]),
        },
        "realized_reversal_continuity": {
            "atanh_max_abs_phase_fraction_jump": g2_phase,
            "atanh_max_abs_temperature_contract_K": float(np.max(atanh_temp)),
            "atanh_max_abs_normalized_temperature_contract_residual": g2_temperature,
            "literal_max_abs_phase_fraction_jump": float(np.max(literal_jumps)),
            "literal_max_abs_temperature_contract_K": float(np.max(literal_temp)),
            "gate_pass": g2_pass,
        },
        "hysteresis_property_diagnostics": {
            "blocking": False,
            "protocol_runs": protocols,
            "return_point_memory_claim_authorized": False,
            "wiping_out_claim_authorized": False,
        },
        "blocking_gates_pass": bool(g1_pass and g2_pass),
        "claim_status": "supported" if g1_pass and g2_pass else "forbidden",
        "allowed_claim": "The atanh term is supported as the analytic inverse of the configured tanh limiting-branch anchor.",
        "forbidden_claims": [
            "Qiu 2024 unpublished author code was reproduced",
            "the literal printed-S3 sensitivity refutes general LLP",
            "return-point memory or wiping-out is established by this formula audit",
        ],
    }
    return summary, rows

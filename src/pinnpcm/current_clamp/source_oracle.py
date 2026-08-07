"""Bounded S1 major-branch admission oracle for an ideal current clamp.

The branch label is protocol metadata.  The module certifies only
branch-conditioned continuation connectivity; it does not simulate branch
switching, minor loops, or the retired voltage-driven dynamics.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from scipy import optimize

from pinnpcm.current_clamp.artifacts import (
    atomic_write_csv,
    atomic_write_json,
    environment_record,
    file_sha256,
)
from pinnpcm.current_clamp.contract import load_current_clamp_contract
from pinnpcm.current_clamp.source_mapping import (
    analytic_geometry_factor_m,
    device_effective_conductivity_S_m,
    uniform_port_resistance_ohm,
)
from pinnpcm.evaluation.q2_qiu_source_oracle import (
    OracleParameters,
    insulating_fraction,
    resistance_and_derivative,
)


class CurrentClampExecutionError(RuntimeError):
    """An invalid configuration, numerical certificate, or budget breach."""


@dataclass(frozen=True)
class CurrentClampRoot:
    branch: str
    delta: int
    current_A: float
    root_index: int
    temperature_K: float
    resistance_ohm: float
    resistance_derivative_ohm_K: float
    conductive_state: float
    device_voltage_V: float
    scaled_equilibrium_residual: float
    resistance_derivative_relative_error: float
    spectral_abscissa_per_s: float
    alpha_tau_dimensionless: float
    stable: bool
    range_legal: bool
    voltage_envelope_legal: bool
    certified: bool

    def row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RootDiscovery:
    branch: str
    current_A: float
    roots: tuple[CurrentClampRoot, ...]
    coarse_root_temperatures_K: tuple[float, ...]
    fine_root_temperatures_K: tuple[float, ...]
    coarse_stationary_temperatures_K: tuple[float, ...]
    fine_stationary_temperatures_K: tuple[float, ...]
    root_hausdorff_K: float
    stationary_hausdorff_K: float


@dataclass(frozen=True)
class BranchTrace:
    branch: str
    rows: tuple[dict[str, Any], ...]
    connected_roots: tuple[CurrentClampRoot, ...]
    terminated_reason: str | None


def _branch_delta(branch: str) -> int:
    if branch == "heating":
        return 1
    if branch == "cooling":
        return -1
    raise CurrentClampExecutionError(f"unknown major branch: {branch}")


def _resistance(
    temperature_K: float | np.ndarray,
    *,
    delta: int,
    params: OracleParameters,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    return resistance_and_derivative(temperature_K, delta, 1.0, params)


def _balance(
    temperature_K: float | np.ndarray,
    *,
    current_A: float,
    delta: int,
    params: OracleParameters,
) -> float | np.ndarray:
    resistance, _ = _resistance(temperature_K, delta=delta, params=params)
    temperature = np.asarray(temperature_K, dtype=float)
    value = (
        params.thermal_conductance_W_K
        * (temperature - params.ambient_temperature_K)
        - current_A**2 * np.asarray(resistance, dtype=float)
    )
    return float(value) if value.ndim == 0 else value


def _balance_derivative(
    temperature_K: float | np.ndarray,
    *,
    current_A: float,
    delta: int,
    params: OracleParameters,
) -> float | np.ndarray:
    _, derivative = _resistance(temperature_K, delta=delta, params=params)
    value = params.thermal_conductance_W_K - current_A**2 * np.asarray(
        derivative, dtype=float
    )
    return float(value) if value.ndim == 0 else value


def _scaled_residual(
    temperature_K: float,
    *,
    current_A: float,
    delta: int,
    params: OracleParameters,
) -> float:
    resistance, _ = _resistance(temperature_K, delta=delta, params=params)
    scale = (
        params.thermal_conductance_W_K
        * max(abs(temperature_K - params.ambient_temperature_K), 1.0)
        + current_A**2 * float(resistance)
    )
    return abs(
        float(
            _balance(
                temperature_K,
                current_A=current_A,
                delta=delta,
                params=params,
            )
        )
    ) / scale


def _deduplicate(values: Sequence[float], *, tolerance_K: float = 1.0e-9) -> list[float]:
    result: list[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > tolerance_K:
            result.append(value)
    return result


def _hausdorff(left: Sequence[float], right: Sequence[float]) -> float:
    if not left and not right:
        return 0.0
    if not left or not right:
        return math.inf
    return max(
        max(min(abs(value - other) for other in right) for value in left),
        max(min(abs(value - other) for other in left) for value in right),
    )


def _partition_roots(
    function: Callable[[float | np.ndarray], float | np.ndarray],
    grid: np.ndarray,
) -> list[float]:
    values = np.asarray(function(grid), dtype=float)
    if values.shape != grid.shape or not np.isfinite(values).all():
        raise CurrentClampExecutionError("root partition evaluation was invalid")
    roots: list[float] = []
    for index in range(grid.size - 1):
        left = float(grid[index])
        right = float(grid[index + 1])
        f_left = float(values[index])
        f_right = float(values[index + 1])
        if f_left == 0.0:
            roots.append(left)
        if f_left * f_right < 0.0:
            roots.append(
                float(
                    optimize.brentq(
                        lambda value: float(function(value)),
                        left,
                        right,
                        xtol=5.0e-14,
                        rtol=1.0e-14,
                        maxiter=200,
                    )
                )
            )
    if float(values[-1]) == 0.0:
        roots.append(float(grid[-1]))
    return _deduplicate(roots)


def _discover_at_partition(
    *,
    count: int,
    lower_K: float,
    upper_K: float,
    current_A: float,
    delta: int,
    params: OracleParameters,
    tangent_scaled_tolerance: float,
) -> tuple[list[float], list[float]]:
    grid = np.linspace(lower_K, upper_K, count)
    balance = lambda value: _balance(
        value, current_A=current_A, delta=delta, params=params
    )
    derivative = lambda value: _balance_derivative(
        value, current_A=current_A, delta=delta, params=params
    )
    roots = _partition_roots(balance, grid)
    stationary = _partition_roots(derivative, grid)
    candidates = list(roots)
    for temperature_K in (lower_K, upper_K, *stationary):
        if (
            _scaled_residual(
                float(temperature_K),
                current_A=current_A,
                delta=delta,
                params=params,
            )
            <= tangent_scaled_tolerance
        ):
            candidates.append(float(temperature_K))
    return _deduplicate(candidates), _deduplicate(stationary)


def _certify_root(
    *,
    branch: str,
    current_A: float,
    root_index: int,
    temperature_K: float,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> CurrentClampRoot:
    delta = _branch_delta(branch)
    resistance, derivative = _resistance(
        temperature_K, delta=delta, params=params
    )
    resistance = float(resistance)
    derivative = float(derivative)
    eps = np.finfo(float).eps
    step_K = eps ** (1.0 / 3.0) * max(1.0, abs(temperature_K))
    plus, _ = _resistance(temperature_K + step_K, delta=delta, params=params)
    minus, _ = _resistance(temperature_K - step_K, delta=delta, params=params)
    fd_derivative = (float(plus) - float(minus)) / (2.0 * step_K)
    derivative_relative_error = abs(fd_derivative - derivative) / max(
        abs(derivative), resistance / 1.0
    )
    conductive_state = 1.0 - float(
        insulating_fraction(temperature_K, delta, params)
    )
    device_voltage_V = current_A * resistance
    spectral_abscissa = (
        current_A**2 * derivative - params.thermal_conductance_W_K
    ) / params.thermal_capacitance_J_K
    alpha_tau = (
        spectral_abscissa
        * params.thermal_capacitance_J_K
        / params.thermal_conductance_W_K
    )
    temperature_range = config["admissibility"]["temperature_K"]
    range_legal = (
        float(temperature_range["minimum"])
        <= temperature_K
        <= float(temperature_range["maximum"])
        and 0.0 <= conductive_state <= 1.0
        and math.isfinite(resistance)
        and resistance > 0.0
    )
    voltage_legal = device_voltage_V <= float(
        config["admissibility"]["device_voltage_operating_envelope_max_V"]
    )
    residual = _scaled_residual(
        temperature_K,
        current_A=current_A,
        delta=delta,
        params=params,
    )
    stable = alpha_tau <= float(
        config["stability"]["stable_alpha_tau_max"]
    )
    certified = (
        residual <= float(config["root_discovery"]["scaled_residual_max"])
        and derivative_relative_error
        <= float(config["root_discovery"]["resistance_derivative_relative_error_max"])
        and range_legal
        and voltage_legal
        and stable
    )
    return CurrentClampRoot(
        branch=branch,
        delta=delta,
        current_A=current_A,
        root_index=root_index,
        temperature_K=temperature_K,
        resistance_ohm=resistance,
        resistance_derivative_ohm_K=derivative,
        conductive_state=conductive_state,
        device_voltage_V=device_voltage_V,
        scaled_equilibrium_residual=residual,
        resistance_derivative_relative_error=derivative_relative_error,
        spectral_abscissa_per_s=spectral_abscissa,
        alpha_tau_dimensionless=alpha_tau,
        stable=stable,
        range_legal=range_legal,
        voltage_envelope_legal=voltage_legal,
        certified=certified,
    )


def discover_roots(
    *,
    branch: str,
    current_A: float,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> RootDiscovery:
    """Enumerate and numerically resolve all scalar fixed points in the domain."""

    lower_K = float(config["admissibility"]["temperature_K"]["minimum"])
    upper_K = float(config["admissibility"]["temperature_K"]["maximum"])
    counts = tuple(int(value) for value in config["root_discovery"]["nested_partition_counts"])
    if len(counts) != 2 or counts[1] <= counts[0]:
        raise CurrentClampExecutionError("root partitions must be nested coarse/fine counts")
    delta = _branch_delta(branch)
    tolerance = float(config["root_discovery"]["tangent_scaled_residual_max"])
    coarse_roots, coarse_stationary = _discover_at_partition(
        count=counts[0],
        lower_K=lower_K,
        upper_K=upper_K,
        current_A=current_A,
        delta=delta,
        params=params,
        tangent_scaled_tolerance=tolerance,
    )
    fine_roots, fine_stationary = _discover_at_partition(
        count=counts[1],
        lower_K=lower_K,
        upper_K=upper_K,
        current_A=current_A,
        delta=delta,
        params=params,
        tangent_scaled_tolerance=tolerance,
    )
    root_hausdorff = _hausdorff(coarse_roots, fine_roots)
    stationary_hausdorff = _hausdorff(coarse_stationary, fine_stationary)
    maximum = float(config["root_discovery"]["root_set_hausdorff_max_K"])
    if len(coarse_roots) != len(fine_roots) or root_hausdorff > maximum:
        raise CurrentClampExecutionError(
            f"unresolved root set for {branch} at {current_A:.12g} A"
        )
    if len(coarse_stationary) != len(fine_stationary) or stationary_hausdorff > maximum:
        raise CurrentClampExecutionError(
            f"unresolved stationary set for {branch} at {current_A:.12g} A"
        )
    roots = tuple(
        _certify_root(
            branch=branch,
            current_A=current_A,
            root_index=index,
            temperature_K=temperature_K,
            params=params,
            config=config,
        )
        for index, temperature_K in enumerate(fine_roots)
    )
    return RootDiscovery(
        branch=branch,
        current_A=current_A,
        roots=roots,
        coarse_root_temperatures_K=tuple(coarse_roots),
        fine_root_temperatures_K=tuple(fine_roots),
        coarse_stationary_temperatures_K=tuple(coarse_stationary),
        fine_stationary_temperatures_K=tuple(fine_stationary),
        root_hausdorff_K=root_hausdorff,
        stationary_hausdorff_K=stationary_hausdorff,
    )


def _correct_connected_temperature(
    *,
    branch: str,
    current_A: float,
    predictor_temperature_K: float,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> tuple[float | None, int, str]:
    delta = _branch_delta(branch)
    lower = float(config["admissibility"]["temperature_K"]["minimum"])
    upper = float(config["admissibility"]["temperature_K"]["maximum"])
    temperature = min(max(float(predictor_temperature_K), lower), upper)
    tolerance = float(config["root_discovery"]["scaled_residual_max"])
    for iteration in range(1, 31):
        residual = float(
            _balance(
                temperature,
                current_A=current_A,
                delta=delta,
                params=params,
            )
        )
        if _scaled_residual(
            temperature,
            current_A=current_A,
            delta=delta,
            params=params,
        ) <= tolerance:
            return temperature, iteration - 1, "CONVERGED"
        derivative = float(
            _balance_derivative(
                temperature,
                current_A=current_A,
                delta=delta,
                params=params,
            )
        )
        if not math.isfinite(derivative) or derivative == 0.0:
            return None, iteration, "ZERO_OR_NONFINITE_DERIVATIVE"
        direction = -residual / derivative
        accepted = False
        for backtrack in range(8):
            candidate = temperature + direction / (2**backtrack)
            if not lower <= candidate <= upper:
                continue
            candidate_residual = abs(
                float(
                    _balance(
                        candidate,
                        current_A=current_A,
                        delta=delta,
                        params=params,
                    )
                )
            )
            if candidate_residual <= (1.0 - 1.0e-4 / (2**backtrack)) * abs(residual):
                temperature = candidate
                accepted = True
                break
        if not accepted:
            return None, iteration, "LINE_SEARCH_NO_DESCENT"
    return None, 30, "MAX_ITERATIONS"


def _predict_temperature(
    connected: Sequence[CurrentClampRoot], *, next_current_A: float
) -> float:
    if len(connected) < 2:
        return connected[-1].temperature_K
    previous = connected[-1]
    before = connected[-2]
    delta_current = previous.current_A - before.current_A
    if delta_current == 0.0:
        return previous.temperature_K
    slope = (previous.temperature_K - before.temperature_K) / delta_current
    return previous.temperature_K + slope * (next_current_A - previous.current_A)


def _trace_branch(
    *,
    branch: str,
    currents_A: Sequence[float],
    discoveries: Mapping[tuple[str, float], RootDiscovery],
    anchor: CurrentClampRoot,
    params: OracleParameters,
    config: Mapping[str, Any],
) -> BranchTrace:
    connected: list[CurrentClampRoot] = [anchor]
    rows: list[dict[str, Any]] = []
    terminal_reason: str | None = None
    match_tolerance = float(config["branch_admission"]["root_match_temperature_tolerance_K"])
    for current_A in currents_A:
        discovery = discoveries[(branch, float(current_A))]
        predictor = _predict_temperature(connected, next_current_A=float(current_A))
        corrected, iterations, code = _correct_connected_temperature(
            branch=branch,
            current_A=float(current_A),
            predictor_temperature_K=predictor,
            params=params,
            config=config,
        )
        matched: CurrentClampRoot | None = None
        if corrected is not None:
            matches = [
                root
                for root in discovery.roots
                if abs(root.temperature_K - corrected) <= match_tolerance
            ]
            if len(matches) == 1:
                matched = matches[0]
            else:
                code = "ROOT_MATCH_AMBIGUOUS_OR_ABSENT"
        connected_ok = bool(
            matched is not None
            and matched.certified
            and len(discovery.roots) == 1
        )
        rows.append(
            {
                "branch": branch,
                "current_A": float(current_A),
                "predictor_temperature_K": predictor,
                "corrected_temperature_K": corrected,
                "corrector_iterations": iterations,
                "corrector_code": code,
                "enumerated_root_count": len(discovery.roots),
                "matched_root_index": None if matched is None else matched.root_index,
                "temperature_K": None if matched is None else matched.temperature_K,
                "conductive_state": None if matched is None else matched.conductive_state,
                "device_voltage_V": None if matched is None else matched.device_voltage_V,
                "stable": False if matched is None else matched.stable,
                "certified": False if matched is None else matched.certified,
                "continuation_connected": connected_ok,
            }
        )
        if not connected_ok:
            terminal_reason = code if matched is None else "ROOT_NOT_UNIQUE_OR_CERTIFIED"
            break
        connected.append(matched)
    return BranchTrace(
        branch=branch,
        rows=tuple(rows),
        connected_roots=tuple(connected[1:]),
        terminated_reason=terminal_reason,
    )


def evaluate_admission(
    config: Mapping[str, Any],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Evaluate all preregistered CC-A cases and return gate plus long tables."""

    params = OracleParameters.from_config(config)
    currents = tuple(float(value) for value in config["current_clamp"]["official_currents_A"])
    discoveries: dict[tuple[str, float], RootDiscovery] = {}
    root_rows: list[dict[str, Any]] = []
    stationary_rows: list[dict[str, Any]] = []
    for branch in ("heating", "cooling"):
        for current_A in currents:
            discovery = discover_roots(
                branch=branch,
                current_A=current_A,
                params=params,
                config=config,
            )
            discoveries[(branch, current_A)] = discovery
            root_rows.extend(root.row() for root in discovery.roots)
            for resolution, temperatures in (
                ("coarse", discovery.coarse_stationary_temperatures_K),
                ("fine", discovery.fine_stationary_temperatures_K),
            ):
                stationary_rows.extend(
                    {
                        "branch": branch,
                        "current_A": current_A,
                        "resolution": resolution,
                        "stationary_index": index,
                        "temperature_K": temperature_K,
                    }
                    for index, temperature_K in enumerate(temperatures)
                )

    heating_anchor_discovery = discover_roots(
        branch="heating",
        current_A=float(config["current_clamp"]["heating_anchor_current_A"]),
        params=params,
        config=config,
    )
    heating_anchor_candidates = [
        root
        for root in heating_anchor_discovery.roots
        if root.certified
        and root.conductive_state
        <= float(config["branch_admission"]["heating_anchor_state_max"])
    ]
    heating_anchor_valid = len(heating_anchor_candidates) == 1
    if heating_anchor_valid:
        heating_trace = _trace_branch(
            branch="heating",
            currents_A=currents,
            discoveries=discoveries,
            anchor=heating_anchor_candidates[0],
            params=params,
            config=config,
        )
    else:
        heating_trace = BranchTrace(
            branch="heating",
            rows=(),
            connected_roots=(),
            terminated_reason="HEATING_ANCHOR_NOT_UNIQUE_OR_LOW_STATE",
        )

    endpoint_current = float(config["current_clamp"]["cooling_endpoint_current_A"])
    cooling_endpoint_discovery = discoveries[("cooling", endpoint_current)]
    cooling_endpoint_candidates = [
        root
        for root in cooling_endpoint_discovery.roots
        if root.certified
        and root.conductive_state
        >= float(config["branch_admission"]["cooling_endpoint_state_min"])
    ]
    cooling_endpoint_valid = len(cooling_endpoint_candidates) == 1
    if cooling_endpoint_valid:
        endpoint = cooling_endpoint_candidates[0]
        remaining = tuple(reversed(currents[:-1]))
        partial = _trace_branch(
            branch="cooling",
            currents_A=remaining,
            discoveries=discoveries,
            anchor=endpoint,
            params=params,
            config=config,
        )
        endpoint_row = {
            "branch": "cooling",
            "current_A": endpoint_current,
            "predictor_temperature_K": endpoint.temperature_K,
            "corrected_temperature_K": endpoint.temperature_K,
            "corrector_iterations": 0,
            "corrector_code": "FROZEN_HIGH_STATE_ENDPOINT",
            "enumerated_root_count": len(cooling_endpoint_discovery.roots),
            "matched_root_index": endpoint.root_index,
            "temperature_K": endpoint.temperature_K,
            "conductive_state": endpoint.conductive_state,
            "device_voltage_V": endpoint.device_voltage_V,
            "stable": endpoint.stable,
            "certified": endpoint.certified,
            "continuation_connected": True,
        }
        cooling_trace = BranchTrace(
            branch="cooling",
            rows=(endpoint_row, *partial.rows),
            connected_roots=(endpoint, *partial.connected_roots),
            terminated_reason=partial.terminated_reason,
        )
    else:
        cooling_trace = BranchTrace(
            branch="cooling",
            rows=(),
            connected_roots=(),
            terminated_reason="COOLING_ENDPOINT_NOT_UNIQUE_OR_HIGH_STATE",
        )

    trace_rows = [*heating_trace.rows, *cooling_trace.rows]
    gate_cfg = config["branch_admission"]
    branch_summaries: dict[str, Any] = {}
    for trace in (heating_trace, cooling_trace):
        states = [root.conductive_state for root in trace.connected_roots]
        intermediate_count = sum(
            float(gate_cfg["transition_state_min"])
            <= state
            <= float(gate_cfg["transition_state_max"])
            for state in states
        )
        state_span = max(states) - min(states) if states else 0.0
        branch_summaries[trace.branch] = {
            "connected_point_count": len(trace.connected_roots),
            "conductive_state_span": state_span,
            "intermediate_transition_point_count": intermediate_count,
            "terminated_reason": trace.terminated_reason,
            "pass": (
                len(trace.connected_roots)
                >= int(gate_cfg["minimum_connected_points_per_branch"])
                and state_span >= float(gate_cfg["conductive_state_span_min"])
                and intermediate_count
                >= int(gate_cfg["minimum_intermediate_points_per_branch"])
                and trace.terminated_reason is None
            ),
        }

    heating_by_current = {root.current_A: root for root in heating_trace.connected_roots}
    cooling_by_current = {root.current_A: root for root in cooling_trace.connected_roots}
    common = sorted(set(heating_by_current) & set(cooling_by_current))
    separation_rows = [
        {
            "current_A": current_A,
            "heating_state": heating_by_current[current_A].conductive_state,
            "cooling_state": cooling_by_current[current_A].conductive_state,
            "absolute_branch_state_difference": abs(
                heating_by_current[current_A].conductive_state
                - cooling_by_current[current_A].conductive_state
            ),
        }
        for current_A in common
    ]
    separated = [
        row
        for row in separation_rows
        if row["absolute_branch_state_difference"]
        >= float(gate_cfg["common_current_state_separation_min"])
    ]
    root_uniqueness = all(
        len(discovery.roots) == 1
        for discovery in discoveries.values()
    )
    dual_branch_pass = (
        len(common) >= int(gate_cfg["minimum_common_current_points"])
        and len(separated) >= int(gate_cfg["minimum_separated_common_points"])
    )
    pass_all = (
        heating_anchor_valid
        and cooling_endpoint_valid
        and root_uniqueness
        and branch_summaries["heating"]["pass"]
        and branch_summaries["cooling"]["pass"]
        and dual_branch_pass
    )
    failures: list[str] = []
    if not heating_anchor_valid:
        failures.append("HEATING_ANCHOR_GATE")
    if not cooling_endpoint_valid:
        failures.append("COOLING_ENDPOINT_GATE")
    if not root_uniqueness:
        failures.append("FORMAL_ROOT_UNIQUENESS_GATE")
    for branch in ("heating", "cooling"):
        if not branch_summaries[branch]["pass"]:
            failures.append(f"{branch.upper()}_CONTINUATION_DOMAIN_GATE")
    if not dual_branch_pass:
        failures.append("COMMON_BRANCH_SEPARATION_GATE")
    gate = {
        "pass": pass_all,
        "disposition": (
            "PASS_CC_A_CURRENT_CLAMP_ADMISSION"
            if pass_all
            else "STOP_CC_CURRENT_CLAMP_ADMISSION"
        ),
        "heating_anchor_valid": heating_anchor_valid,
        "cooling_endpoint_valid": cooling_endpoint_valid,
        "formal_root_uniqueness_pass": root_uniqueness,
        "branches": branch_summaries,
        "common_current_count": len(common),
        "separated_common_current_count": len(separated),
        "common_branch_separation": separation_rows,
        "failure_reasons": failures,
        "semantic_boundary": (
            "branch-conditioned continuation connectivity; not dynamic branch-switching reachability"
        ),
    }
    return gate, root_rows, stationary_rows, trace_rows


def _source_mapping_contract(config: Mapping[str, Any], params: OracleParameters) -> dict[str, Any]:
    mapping = config["source_mapping"]
    geometry_factor = analytic_geometry_factor_m(
        length_m=float(mapping["length_m"]),
        width_m=float(mapping["width_m"]),
        thickness_m=float(mapping["thickness_m"]),
    )
    expected = float(mapping["expected_geometry_factor_m"])
    if not math.isclose(geometry_factor, expected, rel_tol=0.0, abs_tol=1.0e-18):
        raise CurrentClampExecutionError("analytic source geometry factor drifted")
    roundtrip_errors: list[float] = []
    samples: list[dict[str, Any]] = []
    for branch, delta in (("heating", 1), ("cooling", -1)):
        resistance, _ = _resistance(
            params.ambient_temperature_K, delta=delta, params=params
        )
        conductivity = device_effective_conductivity_S_m(
            device_resistance_ohm=float(resistance),
            geometry_factor_m=geometry_factor,
        )
        recovered = uniform_port_resistance_ohm(
            conductivity_S_m=conductivity,
            geometry_factor_m=geometry_factor,
        )
        relative_error = abs(recovered - float(resistance)) / float(resistance)
        roundtrip_errors.append(relative_error)
        samples.append(
            {
                "branch": branch,
                "temperature_K": params.ambient_temperature_K,
                "source_device_effective_resistance_ohm": float(resistance),
                "mapped_device_effective_conductivity_S_m": conductivity,
                "recovered_uniform_port_resistance_ohm": recovered,
                "relative_error": relative_error,
            }
        )
    return {
        "status": "ALGEBRAIC_CONTRACT_ONLY_NOT_2D_EXECUTED",
        "geometry_factor_m": geometry_factor,
        "mapping_rule": "sigma_eff_equals_one_over_g_geom_times_R_S1",
        "maximum_roundtrip_relative_error": max(roundtrip_errors),
        "samples": samples,
        "electrical_contact_overlap_role": "thermal_only",
        "additional_series_resistance": "forbidden",
        "local_semantics": "device-effective distributed proxy",
        "allowed_claim": "uniform-limit port-equivalent source-scale mapping",
        "forbidden_claims": [
            "intrinsic local VO2 conductivity",
            "real contact-current-crowding reconstruction",
            "two-dimensional validation",
        ],
    }


ROOT_FIELDS = [field.name for field in CurrentClampRoot.__dataclass_fields__.values()]
STATIONARY_FIELDS = [
    "branch",
    "current_A",
    "resolution",
    "stationary_index",
    "temperature_K",
]
TRACE_FIELDS = [
    "branch",
    "current_A",
    "predictor_temperature_K",
    "corrected_temperature_K",
    "corrector_iterations",
    "corrector_code",
    "enumerated_root_count",
    "matched_root_index",
    "temperature_K",
    "conductive_state",
    "device_voltage_V",
    "stable",
    "certified",
    "continuation_connected",
]


def run_cc_a(
    *,
    config_path: Path,
    repository_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Execute one bounded, non-Phase-1-voting CC-A admission invocation."""

    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        config = load_current_clamp_contract(config_path)
    except Exception as exc:
        execution_id = (
            "INVALID-CC-A-CONTRACT-"
            + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            + "-"
            + uuid.uuid4().hex[:8]
        )
        output_dir = output_root / execution_id
        output_dir.mkdir(parents=True, exist_ok=False)
        summary = {
            "schema_version": "q2_current_clamp_cc_a_summary_v1",
            "task_id": "Q2_CURRENT_CLAMP_HYSGEO_PINN_V1",
            "run_id": execution_id,
            "execution_id": execution_id,
            "validity": "invalid",
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": "INVALID_CC_A_EXECUTION",
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "cc_b_eligible_to_request": False,
            "cc_b_authorized": False,
            "cc_b_executed": False,
            "aggregate_cpu_s": time.process_time() - cpu_started,
            "calendar_wall_s": time.perf_counter() - wall_started,
        }
        atomic_write_json(output_dir / "summary.json", summary)
        atomic_write_json(output_dir / "terminal.json", summary)
        atomic_write_json(
            output_dir / "artifact_manifest.json",
            {
                "schema_version": "q2_current_clamp_cc_a_artifact_manifest_v1",
                "run_id": execution_id,
                "artifacts": [
                    {
                        "path": (
                            path.relative_to(repository_root).as_posix()
                            if path.is_relative_to(repository_root)
                            else path.as_posix()
                        ),
                        "sha256": file_sha256(path),
                    }
                    for path in sorted(output_dir.iterdir())
                    if path.is_file() and path.name != "artifact_manifest.json"
                ],
            },
        )
        return summary

    run_id = str(config["run_id"])
    execution_id = (
        run_id
        + "-"
        + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        + "-"
        + uuid.uuid4().hex[:8]
    )
    output_dir = output_root / execution_id
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        params = OracleParameters.from_config(config)
        source_mapping = _source_mapping_contract(config, params)
        gate, root_rows, stationary_rows, trace_rows = evaluate_admission(config)
        cpu_elapsed = time.process_time() - cpu_started
        wall_elapsed = time.perf_counter() - wall_started
        if cpu_elapsed > float(config["budget"]["aggregate_cpu_cap_s"]):
            raise CurrentClampExecutionError("CC-A aggregate CPU budget exceeded")
        if wall_elapsed > float(config["budget"]["calendar_wall_cap_s"]):
            raise CurrentClampExecutionError("CC-A calendar wall budget exceeded")
        atomic_write_csv(
            output_dir / "all_roots.csv", root_rows, fieldnames=ROOT_FIELDS
        )
        atomic_write_csv(
            output_dir / "stationary_points.csv",
            stationary_rows,
            fieldnames=STATIONARY_FIELDS,
        )
        atomic_write_csv(
            output_dir / "continuation.csv",
            trace_rows,
            fieldnames=TRACE_FIELDS,
        )
        atomic_write_json(output_dir / "gate_summary.json", gate)
        atomic_write_json(
            output_dir / "source_mapping_contract.json", source_mapping
        )
        summary = {
            "schema_version": "q2_current_clamp_cc_a_summary_v1",
            "task_id": config["task_id"],
            "run_id": run_id,
            "execution_id": execution_id,
            "validity": "valid",
            "lifecycle_state": "executed",
            "claim_status": (
                "qualified_supported" if gate["pass"] else "failed_but_informative"
            ),
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": gate["disposition"],
            "gate": gate,
            "source_mapping": source_mapping,
            "cc_b_eligible_to_request": bool(gate["pass"]),
            "cc_b_authorized": False,
            "cc_b_executed": False,
            "implementation_started": True,
            "experiment_started": True,
            "environment": environment_record(repository_root, run_id=run_id),
            "config_path": config_path.relative_to(repository_root).as_posix(),
            "config_sha256": file_sha256(config_path),
            "aggregate_cpu_s": cpu_elapsed,
            "calendar_wall_s": wall_elapsed,
            "evidence_type": config["evidence_type"],
            "claim_boundary": config["claim_boundary"],
        }
    except Exception as exc:
        cpu_elapsed = time.process_time() - cpu_started
        wall_elapsed = time.perf_counter() - wall_started
        summary = {
            "schema_version": "q2_current_clamp_cc_a_summary_v1",
            "task_id": config["task_id"],
            "run_id": run_id,
            "execution_id": execution_id,
            "validity": "invalid",
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "disposition": "INVALID_CC_A_EXECUTION",
            "failure_type": type(exc).__name__,
            "failure_detail": str(exc),
            "cc_b_eligible_to_request": False,
            "cc_b_authorized": False,
            "cc_b_executed": False,
            "aggregate_cpu_s": cpu_elapsed,
            "calendar_wall_s": wall_elapsed,
            "evidence_type": config["evidence_type"],
            "claim_boundary": config["claim_boundary"],
        }
    atomic_write_json(output_dir / "summary.json", summary)
    terminal = {
        key: summary[key]
        for key in (
            "schema_version",
            "task_id",
            "run_id",
            "validity",
            "lifecycle_state",
            "claim_status",
            "scientific_vote",
            "formal_execution_count",
            "disposition",
            "cc_b_eligible_to_request",
            "cc_b_authorized",
            "cc_b_executed",
            "aggregate_cpu_s",
            "calendar_wall_s",
        )
    }
    if summary["validity"] == "invalid":
        terminal["failure_type"] = summary["failure_type"]
        terminal["failure_detail"] = summary["failure_detail"]
    atomic_write_json(output_dir / "terminal.json", terminal)
    artifacts = [
        path
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    atomic_write_json(
        output_dir / "artifact_manifest.json",
        {
            "schema_version": "q2_current_clamp_cc_a_artifact_manifest_v1",
            "run_id": run_id,
            "artifacts": [
                {
                    "path": path.relative_to(repository_root).as_posix(),
                    "sha256": file_sha256(path),
                }
                for path in artifacts
            ],
        },
    )
    return summary

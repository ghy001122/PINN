"""Fixed-source load line and stable-reachable branch continuation."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, process_time
from typing import Callable

import numpy as np
from scipy.optimize import brentq
from scipy.sparse.linalg import LinearOperator, lgmres, splu
from scipy import sparse

from pinnpcm.branchconserve.solver import (
    SteadySolveOutcome,
    SteadySolverTelemetry,
    scaled_secant_predictor,
    solve_steady_equilibrium,
)
from pinnpcm.branchconserve.stability import (
    StabilityOutcome,
    certify_branch_conditioned_stability,
)
from pinnpcm.branchconserve.steady_model import BranchConserveModel, SteadyEvaluation


@dataclass(frozen=True)
class FixedSourceOutcome:
    success: bool
    code: str
    source_voltage_V: float
    branch_memory: float
    device_voltage_V: float | None
    solve: SteadySolveOutcome | None
    certified_evaluation: SteadyEvaluation | None
    stability: StabilityOutcome | None
    outer_equilibrium_count: int
    bracket_device_voltages_V: tuple[float, ...]
    wall_time_s: float
    failure_detail: str | None = None


@dataclass(frozen=True)
class BranchPoint:
    index: int
    branch_name: str
    branch_memory: float
    device_voltage_V: float
    source_voltage_V: float
    source_current_A: float
    active_area_mean_conductive_state: float
    stable: bool
    reachable: bool
    atlas_only_reason: str | None
    solve: SteadySolveOutcome
    stability: StabilityOutcome


@dataclass(frozen=True)
class BranchAtlasOutcome:
    success: bool
    code: str
    branch_name: str
    points: tuple[BranchPoint, ...]
    wall_time_s: float
    cpu_time_s: float
    failure_detail: str | None = None


@dataclass(frozen=True)
class CommonReachableDomain:
    exists: bool
    lower_source_voltage_V: float | None
    upper_source_voltage_V: float | None
    candidate_source_voltages_V: tuple[float, ...]


def _nearest_temperature(
    cached: dict[float, SteadySolveOutcome], device_voltage_V: float
) -> np.ndarray | None:
    valid = [
        (abs(key - device_voltage_V), value)
        for key, value in cached.items()
        if value.success and value.temperature_K is not None
    ]
    if not valid:
        return None
    return min(valid, key=lambda item: item[0])[1].temperature_K


def fixed_source_bracket_points(
    *, source_voltage_V: float, branch_memory: float, count: int
) -> np.ndarray:
    """Return the frozen load-line scan order for one major branch.

    Cooling must start at the high-voltage/high-temperature endpoint so that
    the temperature-primary corrector remains on the conductive major branch.
    Heating starts from the ambient/zero-voltage endpoint.  This ordering is
    part of the single registered solver identity, not a fallback portfolio.
    """

    if count < 2:
        raise ValueError("the fixed-source bracket requires at least two points")
    source_voltage = float(source_voltage_V)
    start, stop = (
        (source_voltage, 0.0) if branch_memory == -1.0 else (0.0, source_voltage)
    )
    return np.linspace(start, stop, count, dtype=float)


def is_inside_physical_atlas_domain(
    *, device_voltage_V: float, source_voltage_V: float, source_voltage_max_V: float
) -> bool:
    """Enforce the positive-source load-line domain for persisted atlas points."""

    tolerance = 1.0e-10
    device_voltage = float(device_voltage_V)
    source_voltage = float(source_voltage_V)
    maximum = float(source_voltage_max_V)
    return bool(
        -tolerance <= device_voltage
        and device_voltage <= source_voltage + tolerance
        and source_voltage <= maximum + tolerance
    )


def first_contiguous_load_line_bracket(
    points: np.ndarray,
    value_at: Callable[[float], float | None],
) -> tuple[float, float] | None:
    """Find the first sign change without bridging an invalid inner solve.

    A high-voltage scan point may have no range-legal equilibrium even though
    a conductive load-line root exists farther along the deterministic 33-point
    scan.  Such a point is skipped, but it breaks contiguity: Brent is never
    allowed to cross an unresolved inner-equilibrium gap.
    """

    previous_point: float | None = None
    previous_value: float | None = None
    for raw_point in points:
        point = float(raw_point)
        value = value_at(point)
        if value is None:
            previous_point = None
            previous_value = None
            continue
        value = float(value)
        if value == 0.0:
            return point, point
        if previous_value is not None and previous_value * value < 0.0:
            return float(previous_point), point
        previous_point = point
        previous_value = value
    return None


def solve_fixed_source_equilibrium(
    model: BranchConserveModel,
    *,
    source_voltage_V: float,
    branch_memory: float,
    initial_temperature_K: np.ndarray | None = None,
    include_stability: bool = True,
    minimum_conductive_state: float | None = None,
    equilibrium_callback: Callable[[int, float, SteadySolveOutcome], None]
    | None = None,
) -> FixedSourceOutcome:
    """Solve the full load line, recomputing equilibrium at every outer point."""

    started = perf_counter()
    load = model.contract.raw["load_line"]
    source_voltage = float(source_voltage_V)
    if not np.isfinite(source_voltage) or not (
        0.0 <= source_voltage <= float(load["source_voltage_max_V"])
    ):
        return FixedSourceOutcome(
            success=False,
            code="STEADY_LOAD_LINE_FAIL",
            source_voltage_V=source_voltage,
            branch_memory=branch_memory,
            device_voltage_V=None,
            solve=None,
            certified_evaluation=None,
            stability=None,
            outer_equilibrium_count=0,
            bracket_device_voltages_V=(),
            wall_time_s=perf_counter() - started,
            failure_detail="source voltage is outside the frozen load-line interval",
        )

    cache: dict[float, SteadySolveOutcome] = {}
    queried: list[float] = []

    def equilibrium_at(device_voltage: float) -> SteadySolveOutcome:
        key = round(float(device_voltage), 14)
        if key in cache:
            return cache[key]
        guess = _nearest_temperature(cache, device_voltage)
        if guess is None:
            guess = initial_temperature_K
        outcome = solve_steady_equilibrium(
            model,
            device_voltage_V=float(device_voltage),
            branch_memory=branch_memory,
            initial_temperature_K=guess,
        )
        cache[key] = outcome
        queried.append(float(device_voltage))
        if equilibrium_callback is not None:
            equilibrium_callback(len(queried) - 1, float(device_voltage), outcome)
        return outcome

    def load_function(device_voltage: float) -> float:
        outcome = equilibrium_at(device_voltage)
        if not outcome.success or outcome.evaluation is None:
            raise RuntimeError(
                f"inner equilibrium failed at Vd={device_voltage:.12g}: {outcome.code}"
            )
        if (
            minimum_conductive_state is not None
            and outcome.evaluation.active_area_mean_conductive_state
            < minimum_conductive_state
        ):
            raise RuntimeError(
                "inner equilibrium left the certified conductive endpoint component "
                f"at Vd={device_voltage:.12g}"
            )
        return (
            device_voltage
            + model.contract.series_resistance_ohm
            * outcome.evaluation.source_current_A
            - source_voltage
        )

    bracket_points = fixed_source_bracket_points(
        source_voltage_V=source_voltage,
        branch_memory=branch_memory,
        count=int(load["bracket_points"]),
    )
    failed_scan_points: list[str] = []

    def bracket_value(device_voltage: float) -> float | None:
        outcome = equilibrium_at(device_voltage)
        if not outcome.success or outcome.evaluation is None:
            failed_scan_points.append(
                f"Vd={device_voltage:.12g}:{outcome.code}"
            )
            return None
        if (
            minimum_conductive_state is not None
            and outcome.evaluation.active_area_mean_conductive_state
            < minimum_conductive_state
        ):
            failed_scan_points.append(
                f"Vd={device_voltage:.12g}:outside_conductive_endpoint_component"
            )
            return None
        return (
            device_voltage
            + model.contract.series_resistance_ohm
            * outcome.evaluation.source_current_A
            - source_voltage
        )

    try:
        bracket = first_contiguous_load_line_bracket(bracket_points, bracket_value)
    except Exception as exc:
        return FixedSourceOutcome(
            success=False,
            code="STEADY_LOAD_LINE_FAIL",
            source_voltage_V=source_voltage,
            branch_memory=branch_memory,
            device_voltage_V=None,
            solve=None,
            certified_evaluation=None,
            stability=None,
            outer_equilibrium_count=len(cache),
            bracket_device_voltages_V=tuple(queried),
            wall_time_s=perf_counter() - started,
            failure_detail=str(exc),
        )
    if bracket is None:
        return FixedSourceOutcome(
            success=False,
            code="STEADY_LOAD_LINE_FAIL",
            source_voltage_V=source_voltage,
            branch_memory=branch_memory,
            device_voltage_V=None,
            solve=None,
            certified_evaluation=None,
            stability=None,
            outer_equilibrium_count=len(cache),
            bracket_device_voltages_V=tuple(queried),
            wall_time_s=perf_counter() - started,
            failure_detail=(
                "33-point fixed bracket contained no contiguous load-line sign change"
                + (
                    "; invalid inner points=" + ",".join(failed_scan_points)
                    if failed_scan_points
                    else ""
                )
            ),
        )
    try:
        if bracket[0] == bracket[1]:
            root = bracket[0]
        else:
            root = float(
                brentq(
                    load_function,
                    bracket[0],
                    bracket[1],
                    xtol=float(load["brent_xtol_V"]),
                    rtol=float(load["brent_rtol"]),
                    maxiter=int(load["brent_maxiter"]),
                )
            )
        root_outcome = equilibrium_at(root)
        if not root_outcome.success or root_outcome.temperature_K is None:
            raise RuntimeError(f"root equilibrium failed: {root_outcome.code}")
        certified = model.evaluate_temperature(
            root_outcome.temperature_K,
            root,
            branch_memory,
            source_voltage_V=source_voltage,
        )
        if (
            certified.load_line_residual
            > model.contract.scales.load_line_residual_max
            or certified.scaled_electrical_residual_inf
            > model.contract.scales.electrical_residual_max
            or certified.scaled_thermal_residual_inf
            > model.contract.scales.thermal_residual_max
            or not certified.ledger.pass_all
        ):
            raise RuntimeError("fixed-source equilibrium failed final certification")
        stability = (
            certify_branch_conditioned_stability(
                model,
                temperature_K=root_outcome.temperature_K,
                device_voltage_V=root,
                source_voltage_V=source_voltage,
                branch_memory=branch_memory,
            )
            if include_stability
            else None
        )
        if include_stability and (stability is None or not stability.success):
            raise RuntimeError(
                "fixed-source equilibrium failed sparse stability certification"
            )
        return FixedSourceOutcome(
            success=True,
            code="PASS",
            source_voltage_V=source_voltage,
            branch_memory=branch_memory,
            device_voltage_V=root,
            solve=root_outcome,
            certified_evaluation=certified,
            stability=stability,
            outer_equilibrium_count=len(cache),
            bracket_device_voltages_V=tuple(queried),
            wall_time_s=perf_counter() - started,
        )
    except Exception as exc:
        return FixedSourceOutcome(
            success=False,
            code="STEADY_LOAD_LINE_FAIL",
            source_voltage_V=source_voltage,
            branch_memory=branch_memory,
            device_voltage_V=None,
            solve=None,
            certified_evaluation=None,
            stability=None,
            outer_equilibrium_count=len(cache),
            bracket_device_voltages_V=tuple(queried),
            wall_time_s=perf_counter() - started,
            failure_detail=str(exc),
        )


def should_start_pseudo_arclength(
    *,
    fixed_device_voltage_failed_at_minimum_step: bool,
    current_tangent_device_voltage: float,
    previous_tangent_device_voltage: float | None,
) -> bool:
    """Apply only the registered device-voltage parameterization triggers."""

    if not fixed_device_voltage_failed_at_minimum_step:
        return False
    small_component = abs(float(current_tangent_device_voltage)) <= 0.1
    reversed_component = bool(
        previous_tangent_device_voltage is not None
        and current_tangent_device_voltage * previous_tangent_device_voltage < 0.0
    )
    return small_component or reversed_component


def _scaled_point(
    model: BranchConserveModel,
    temperature_K: np.ndarray,
    device_voltage_V: float,
) -> np.ndarray:
    return np.concatenate(
        (
            model.scaled_from_temperature(temperature_K),
            np.asarray([device_voltage_V / model.contract.scales.voltage_V]),
        )
    )


def solve_scaled_pseudo_arclength_corrector(
    model: BranchConserveModel,
    *,
    branch_memory: float,
    previous_temperature_K: np.ndarray,
    previous_device_voltage_V: float,
    current_temperature_K: np.ndarray,
    current_device_voltage_V: float,
    step_size: float,
) -> tuple[SteadySolveOutcome, float]:
    """Use the same scaled residual, Jv, Armijo and thermal preconditioner."""

    y_previous = _scaled_point(
        model, previous_temperature_K, previous_device_voltage_V
    )
    y_current = _scaled_point(model, current_temperature_K, current_device_voltage_V)
    tangent = y_current - y_previous
    tangent_norm = float(np.linalg.norm(tangent))
    if not np.isfinite(tangent_norm) or tangent_norm <= 0.0:
        telemetry = SteadySolverTelemetry(failure_detail="zero pseudo-arclength secant")
        return (
            SteadySolveOutcome(
                False,
                "STEADY_ARCLENGTH_FAIL",
                branch_memory,
                current_device_voltage_V,
                None,
                None,
                float("inf"),
                telemetry,
            ),
            float(step_size),
        )
    tangent /= tangent_norm
    config = model.contract.solver
    arc = config["pseudo_arclength"]
    thermal_matrix = model.thermal_matrix.tocsc() + sparse.diags(
        model.sink_cell_W_K, format="csc"
    )
    try:
        thermal_factor = splu(thermal_matrix, permc_spec="COLAMD")
    except Exception as exc:
        telemetry = SteadySolverTelemetry(failure_detail=str(exc))
        return (
            SteadySolveOutcome(
                False,
                "STEADY_PRECONDITIONER_FAIL",
                branch_memory,
                current_device_voltage_V,
                None,
                None,
                float("inf"),
                telemetry,
            ),
            float(step_size),
        )

    for halving in range(int(arc["step_halvings_max"]) + 1):
        ds = float(step_size) / (2**halving)
        predictor = y_current + ds * tangent
        y = predictor.copy()
        telemetry = SteadySolverTelemetry()
        wall_started = perf_counter()
        cpu_started = process_time()
        last_update = float("inf")
        evaluation: SteadyEvaluation | None = None

        def augmented(values: np.ndarray) -> np.ndarray:
            telemetry.full_residual_evaluations += 1
            if telemetry.full_residual_evaluations > int(
                config["full_residual_evaluations_max"]
            ):
                raise RuntimeError("pseudo-arclength residual budget exhausted")
            z = values[:-1]
            vd = values[-1] * model.contract.scales.voltage_V
            item = model.evaluate_scaled_temperature(z, vd, branch_memory)
            return np.concatenate(
                (
                    item.scaled_thermal_residual,
                    np.asarray([float(np.dot(tangent, values - predictor))]),
                )
            )

        try:
            residual = augmented(y)
            for iteration in range(int(config["nonlinear_iterations_max"]) + 1):
                residual_inf = float(np.max(np.abs(residual)))
                telemetry.residual_inf_history.append(residual_inf)
                if (
                    residual_inf <= float(config["residual_inf_max"])
                    and last_update <= float(config["last_scaled_update_inf_max"])
                ):
                    temperature = model.temperature_from_scaled(y[:-1])
                    vd = y[-1] * model.contract.scales.voltage_V
                    evaluation = model.evaluate_temperature(
                        temperature, vd, branch_memory
                    )
                    telemetry.wall_time_s = perf_counter() - wall_started
                    telemetry.cpu_time_s = process_time() - cpu_started
                    if not evaluation.postcertified:
                        raise RuntimeError("pseudo-arclength post-certification failed")
                    return (
                        SteadySolveOutcome(
                            True,
                            "PASS",
                            branch_memory,
                            float(vd),
                            temperature,
                            evaluation,
                            float(last_update),
                            telemetry,
                        ),
                        ds,
                    )
                if iteration == int(config["nonlinear_iterations_max"]):
                    break
                telemetry.nonlinear_iterations += 1
                base = y.copy()
                base_residual = residual.copy()

                def jv(vector: np.ndarray) -> np.ndarray:
                    telemetry.jv_evaluations += 1
                    if telemetry.jv_evaluations > int(config["jv_evaluations_max"]):
                        raise RuntimeError("pseudo-arclength Jv budget exhausted")
                    direction = np.asarray(vector, dtype=float)
                    magnitude = float(np.linalg.norm(direction, ord=np.inf))
                    if magnitude == 0.0:
                        return np.zeros_like(direction)
                    unit_direction = direction / magnitude
                    h = np.finfo(float).eps ** (1.0 / 3.0) * max(
                        1.0, float(np.linalg.norm(base, ord=np.inf))
                    ) / max(1.0, float(np.linalg.norm(unit_direction, ord=np.inf)))
                    plus_y = base + h * unit_direction
                    minus_y = base - h * unit_direction
                    # Count and evaluate the same complete conservative pair
                    # used by the frozen central-difference contract.
                    telemetry.full_residual_evaluations += 2
                    if telemetry.full_residual_evaluations > int(
                        config["full_residual_evaluations_max"]
                    ):
                        raise RuntimeError("pseudo-arclength residual budget exhausted")
                    plus = model.evaluate_scaled_temperature(
                        plus_y[:-1],
                        plus_y[-1] * model.contract.scales.voltage_V,
                        branch_memory,
                    )
                    minus = model.evaluate_scaled_temperature(
                        minus_y[:-1],
                        minus_y[-1] * model.contract.scales.voltage_V,
                        branch_memory,
                    )
                    thermal = model.conservative_thermal_jv_from_pair(
                        unit_direction[:-1], h, plus, minus
                    )
                    return magnitude * np.concatenate(
                        (
                            thermal,
                            np.asarray([float(np.dot(tangent, unit_direction))]),
                        )
                    )

                operator = LinearOperator((y.size, y.size), matvec=jv, dtype=float)

                def precondition(vector: np.ndarray) -> np.ndarray:
                    thermal = np.asarray(vector[:-1], dtype=float)
                    thermal_physical = thermal * (
                        model.contract.scales.power_W / model.grid.nx / model.grid.ny
                    )
                    z_part = (
                        np.asarray(thermal_factor.solve(thermal_physical), dtype=float)
                        / model.temperature_reference_K
                    )
                    return np.concatenate((z_part, np.asarray([vector[-1]])))

                preconditioner = LinearOperator(
                    (y.size, y.size), matvec=precondition, dtype=float
                )
                delta, info = lgmres(
                    operator,
                    -base_residual,
                    x0=preconditioner.matvec(-base_residual),
                    M=preconditioner,
                    rtol=float(config["lgmres"]["rtol"]),
                    atol=float(config["lgmres"]["atol"]),
                    # Jv itself enforces the exact matvec ceiling.  LGMRES
                    # maxiter counts outer cycles and therefore must not divide
                    # the remaining matvec allowance by ``inner_m``.
                    maxiter=max(
                        1,
                        int(config["jv_evaluations_max"])
                        - telemetry.jv_evaluations,
                    ),
                    inner_m=int(config["lgmres"]["inner_m"]),
                    outer_k=int(config["lgmres"]["outer_k"]),
                )
                if info != 0 or not np.isfinite(delta).all():
                    raise RuntimeError(f"pseudo-arclength LGMRES info={info}")
                phi0 = 0.5 * float(np.dot(base_residual, base_residual))
                accepted = False
                for damping in map(float, config["armijo"]["damping_values"]):
                    candidate = base + damping * delta
                    candidate_residual = augmented(candidate)
                    phi = 0.5 * float(np.dot(candidate_residual, candidate_residual))
                    if phi <= (
                        1.0 - 2.0 * float(config["armijo"]["c1"]) * damping
                    ) * phi0:
                        y = candidate
                        residual = candidate_residual
                        last_update = float(np.max(np.abs(damping * delta)))
                        telemetry.damping_history.append(damping)
                        telemetry.update_inf_history.append(last_update)
                        accepted = True
                        break
                if not accepted:
                    raise RuntimeError("pseudo-arclength line search found no descent")
        except Exception as exc:
            telemetry.failure_detail = str(exc)
            telemetry.wall_time_s = perf_counter() - wall_started
            telemetry.cpu_time_s = process_time() - cpu_started
            continue
    return (
        SteadySolveOutcome(
            False,
            "STEADY_ARCLENGTH_FAIL",
            branch_memory,
            current_device_voltage_V,
            None,
            None,
            float("inf"),
            telemetry,
        ),
        float(step_size) / (2 ** int(arc["step_halvings_max"])),
    )


def _point_from_solve(
    model: BranchConserveModel,
    *,
    index: int,
    branch_name: str,
    solve: SteadySolveOutcome,
    stability: StabilityOutcome,
    previous: BranchPoint | None,
) -> BranchPoint:
    if solve.evaluation is None:
        raise ValueError("successful branch point requires an evaluation")
    evaluation = solve.evaluation
    stable = bool(stability.success and stability.stable)
    if previous is None:
        monotonic = True
        previous_reachable = True
    else:
        tolerance = 1.0e-10
        monotonic = (
            evaluation.source_voltage_V >= previous.source_voltage_V - tolerance
            if branch_name == "up"
            else evaluation.source_voltage_V <= previous.source_voltage_V + tolerance
        )
        previous_reachable = previous.reachable
    reachable = bool(previous_reachable and stable and monotonic)
    reason = None
    if not stable:
        reason = "marginal_or_unstable"
    elif not monotonic:
        reason = "source_direction_reversal"
    elif not previous_reachable:
        reason = "beyond_reachability_gap"
    return BranchPoint(
        index=index,
        branch_name=branch_name,
        branch_memory=solve.branch_memory,
        device_voltage_V=solve.device_voltage_V,
        source_voltage_V=evaluation.source_voltage_V,
        source_current_A=evaluation.source_current_A,
        active_area_mean_conductive_state=evaluation.active_area_mean_conductive_state,
        stable=stable,
        reachable=reachable,
        atlas_only_reason=reason,
        solve=solve,
        stability=stability,
    )


def trace_nominal_branch_atlas(
    model: BranchConserveModel,
    *,
    branch_name: str,
    point_callback: Callable[[BranchPoint], None] | None = None,
    inner_equilibrium_callback: Callable[[int, float, SteadySolveOutcome], None]
    | None = None,
) -> BranchAtlasOutcome:
    """Trace one nominal fixed-Vd atlas and apply the stable-reachable label."""

    if branch_name not in {"up", "down"}:
        raise ValueError("branch_name must be 'up' or 'down'")
    wall_started = perf_counter()
    cpu_started = process_time()
    branch_memory = 1.0 if branch_name == "up" else -1.0
    atlas_config = model.contract.batch1["atlas"]
    points: list[BranchPoint] = []
    failure_detail: str | None = None

    if branch_name == "up":
        endpoint = solve_steady_equilibrium(
            model,
            device_voltage_V=0.0,
            branch_memory=branch_memory,
            initial_temperature_K=np.full(
                model.grid.shape, model.ambient_temperature_K
            ),
        )
        if not endpoint.success or endpoint.temperature_K is None or endpoint.evaluation is None:
            return BranchAtlasOutcome(
                False,
                endpoint.code,
                branch_name,
                (),
                perf_counter() - wall_started,
                process_time() - cpu_started,
                endpoint.telemetry.failure_detail,
            )
        endpoint_stability = certify_branch_conditioned_stability(
            model,
            temperature_K=endpoint.temperature_K,
            device_voltage_V=0.0,
            source_voltage_V=0.0,
            branch_memory=branch_memory,
        )
        if not endpoint_stability.success:
            return BranchAtlasOutcome(
                False,
                endpoint_stability.code,
                branch_name,
                (),
                perf_counter() - wall_started,
                process_time() - cpu_started,
                endpoint_stability.telemetry.failure_detail,
            )
        current = endpoint
        direction = 1.0
        step = float(atlas_config["initial_device_voltage_step_V"])
    else:
        source_endpoint = solve_fixed_source_equilibrium(
            model,
            source_voltage_V=float(
                model.contract.raw["branch_contract"]["cooling"][
                    "endpoint_source_voltage_V"
                ]
            ),
            branch_memory=branch_memory,
            initial_temperature_K=np.full(
                model.grid.shape,
                float(model.contract.solver["initialization"]["high_endpoint_temperature_K"]),
            ),
            include_stability=True,
            minimum_conductive_state=float(
                model.contract.raw["branch_contract"]["cooling"][
                    "endpoint_conductive_state_mean_min"
                ]
            ),
            equilibrium_callback=inner_equilibrium_callback,
        )
        if (
            not source_endpoint.success
            or source_endpoint.solve is None
            or source_endpoint.stability is None
            or source_endpoint.certified_evaluation is None
        ):
            return BranchAtlasOutcome(
                False,
                source_endpoint.code,
                branch_name,
                (),
                perf_counter() - wall_started,
                process_time() - cpu_started,
                source_endpoint.failure_detail,
            )
        if (
            not source_endpoint.stability.stable
            or source_endpoint.certified_evaluation.active_area_mean_conductive_state
            < float(
                model.contract.raw["branch_contract"]["cooling"][
                    "endpoint_conductive_state_mean_min"
                ]
            )
        ):
            return BranchAtlasOutcome(
                False,
                "STEADY_POSTCERTIFICATION_FAIL",
                branch_name,
                (),
                perf_counter() - wall_started,
                process_time() - cpu_started,
                "cooling endpoint is not stable and high-conductive",
            )
        current = source_endpoint.solve
        endpoint_stability = source_endpoint.stability
        direction = -1.0
        step = min(
            float(atlas_config["initial_device_voltage_step_V"]),
            max(
                current.device_voltage_V / 4.0,
                float(atlas_config["minimum_device_voltage_step_V"]),
            ),
        )

    first = _point_from_solve(
        model,
        index=0,
        branch_name=branch_name,
        solve=current,
        stability=endpoint_stability,
        previous=None,
    )
    points.append(first)
    if point_callback is not None:
        point_callback(first)
    if not first.reachable:
        return BranchAtlasOutcome(
            False,
            "STABILITY_NOT_STABLE",
            branch_name,
            tuple(points),
            perf_counter() - wall_started,
            process_time() - cpu_started,
            "branch endpoint is not stable",
        )

    previous_solve: SteadySolveOutcome | None = None
    minimum_step = float(atlas_config["minimum_device_voltage_step_V"])
    maximum_points = int(atlas_config["maximum_points_per_branch"])
    maximum_halvings = int(atlas_config["maximum_step_halvings"])
    source_max = float(model.contract.raw["load_line"]["source_voltage_max_V"])
    arclength_mode = False
    arclength_step: float | None = None

    while len(points) < maximum_points:
        if arclength_mode:
            if previous_solve is None or previous_solve.temperature_K is None:
                failure_detail = "pseudo-arclength lacks two valid predecessor states"
                break
            arc_outcome, used_step = solve_scaled_pseudo_arclength_corrector(
                model,
                branch_memory=branch_memory,
                previous_temperature_K=previous_solve.temperature_K,
                previous_device_voltage_V=previous_solve.device_voltage_V,
                current_temperature_K=current.temperature_K,
                current_device_voltage_V=current.device_voltage_V,
                step_size=float(arclength_step),
            )
            if (
                not arc_outcome.success
                or arc_outcome.temperature_K is None
                or arc_outcome.evaluation is None
            ):
                failure_detail = arc_outcome.telemetry.failure_detail
                break
            if not is_inside_physical_atlas_domain(
                device_voltage_V=arc_outcome.device_voltage_V,
                source_voltage_V=arc_outcome.evaluation.source_voltage_V,
                source_voltage_max_V=source_max,
            ):
                # The equilibrium manifold may continue mathematically beyond
                # the frozen positive-source operating envelope.  Reaching
                # that envelope is a clean atlas boundary, not a new solver
                # failure and not a point eligible for persistence or voting.
                break
            stability = certify_branch_conditioned_stability(
                model,
                temperature_K=arc_outcome.temperature_K,
                device_voltage_V=arc_outcome.device_voltage_V,
                source_voltage_V=arc_outcome.evaluation.source_voltage_V,
                branch_memory=branch_memory,
            )
            if not stability.success:
                failure_detail = stability.telemetry.failure_detail
                break
            point = _point_from_solve(
                model,
                index=len(points),
                branch_name=branch_name,
                solve=arc_outcome,
                stability=stability,
                previous=points[-1],
            )
            points.append(point)
            if point_callback is not None:
                point_callback(point)
            previous_solve, current = current, arc_outcome
            arclength_step = used_step
            if branch_name == "up" and point.source_voltage_V >= source_max:
                break
            if branch_name == "down" and point.source_voltage_V <= 0.0:
                break
            continue
        target_vd = current.device_voltage_V + direction * step
        if target_vd < 0.0:
            target_vd = 0.0
        if target_vd > source_max:
            target_vd = source_max
        if np.isclose(target_vd, current.device_voltage_V, rtol=0.0, atol=1.0e-14):
            break
        if previous_solve is not None and previous_solve.temperature_K is not None:
            guess = scaled_secant_predictor(
                model,
                previous_solve.temperature_K,
                previous_solve.device_voltage_V,
                current.temperature_K,
                current.device_voltage_V,
                target_vd,
            )
        else:
            guess = current.temperature_K
        trial_step = abs(target_vd - current.device_voltage_V)
        trial: SteadySolveOutcome | None = None
        for _ in range(maximum_halvings + 1):
            trial_vd = current.device_voltage_V + direction * trial_step
            trial_vd = min(max(trial_vd, 0.0), source_max)
            trial = solve_steady_equilibrium(
                model,
                device_voltage_V=trial_vd,
                branch_memory=branch_memory,
                initial_temperature_K=guess,
            )
            if trial.success:
                break
            if trial_step <= minimum_step + 1.0e-15:
                break
            trial_step = max(0.5 * trial_step, minimum_step)
        if trial is None or not trial.success or trial.temperature_K is None or trial.evaluation is None:
            if previous_solve is not None and previous_solve.temperature_K is not None:
                y_previous = _scaled_point(
                    model,
                    previous_solve.temperature_K,
                    previous_solve.device_voltage_V,
                )
                y_current = _scaled_point(
                    model, current.temperature_K, current.device_voltage_V
                )
                tangent = y_current - y_previous
                tangent /= max(float(np.linalg.norm(tangent)), 1.0e-300)
                if should_start_pseudo_arclength(
                    fixed_device_voltage_failed_at_minimum_step=trial_step <= minimum_step + 1.0e-15,
                    current_tangent_device_voltage=float(tangent[-1]),
                    previous_tangent_device_voltage=None,
                ):
                    arclength_mode = True
                    arclength_step = float(np.linalg.norm(y_current - y_previous))
                    continue
            failure_detail = (
                "fixed-device-voltage corrector failed at minimum step without an eligible arclength trigger: "
                + ("unknown" if trial is None else trial.code)
            )
            break
        source_voltage = trial.evaluation.source_voltage_V
        stability = certify_branch_conditioned_stability(
            model,
            temperature_K=trial.temperature_K,
            device_voltage_V=trial.device_voltage_V,
            source_voltage_V=source_voltage,
            branch_memory=branch_memory,
        )
        if not stability.success:
            failure_detail = stability.telemetry.failure_detail
            break
        point = _point_from_solve(
            model,
            index=len(points),
            branch_name=branch_name,
            solve=trial,
            stability=stability,
            previous=points[-1],
        )
        points.append(point)
        if point_callback is not None:
            point_callback(point)
        previous_solve, current = current, trial
        step = min(
            float(atlas_config["initial_device_voltage_step_V"]),
            max(trial_step, minimum_step),
        )
        if branch_name == "up" and source_voltage >= source_max:
            break
        if branch_name == "down" and trial.device_voltage_V <= 0.0:
            break

    success = bool(
        failure_detail is None
        and len(points) >= 2
        and any(point.reachable for point in points)
    )
    return BranchAtlasOutcome(
        success=success,
        code="PASS" if success else "STEADY_ARCLENGTH_FAIL",
        branch_name=branch_name,
        points=tuple(points),
        wall_time_s=perf_counter() - wall_started,
        cpu_time_s=process_time() - cpu_started,
        failure_detail=failure_detail,
    )


def common_reachable_domain(
    contract_candidates_V: tuple[float, ...],
    heating: BranchAtlasOutcome,
    cooling: BranchAtlasOutcome,
) -> CommonReachableDomain:
    """Intersect nominal reachable source ranges without interpolating fields."""

    up_values = [point.source_voltage_V for point in heating.points if point.reachable]
    down_values = [point.source_voltage_V for point in cooling.points if point.reachable]
    if not up_values or not down_values:
        return CommonReachableDomain(False, None, None, ())
    lower = max(min(up_values), min(down_values))
    upper = min(max(up_values), max(down_values))
    if upper < lower:
        return CommonReachableDomain(False, lower, upper, ())
    candidates = tuple(
        value
        for value in contract_candidates_V
        if lower - 1.0e-10 <= value <= upper + 1.0e-10
    )
    return CommonReachableDomain(bool(candidates), lower, upper, candidates)

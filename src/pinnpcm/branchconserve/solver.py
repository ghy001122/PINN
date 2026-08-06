"""Unique temperature-primary steady Newton--Krylov solver."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, process_time
from typing import Callable

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, lgmres, splu

from pinnpcm.branchconserve.steady_model import (
    BranchConserveModel,
    SteadyEvaluation,
    SteadyModelError,
)


class _RootBudgetExceeded(RuntimeError):
    pass


@dataclass
class SteadySolverTelemetry:
    nonlinear_iterations: int = 0
    lgmres_iterations: int = 0
    jv_evaluations: int = 0
    full_residual_evaluations: int = 0
    line_search_backtracks: int = 0
    electrical_subsolves: int = 0
    residual_inf_history: list[float] = field(default_factory=list)
    update_inf_history: list[float] = field(default_factory=list)
    damping_history: list[float] = field(default_factory=list)
    wall_time_s: float = 0.0
    cpu_time_s: float = 0.0
    failure_detail: str | None = None


@dataclass(frozen=True)
class SteadySolveOutcome:
    success: bool
    code: str
    branch_memory: float
    device_voltage_V: float
    temperature_K: np.ndarray | None
    evaluation: SteadyEvaluation | None
    last_scaled_update_inf: float
    telemetry: SteadySolverTelemetry


class _CountedResidual:
    def __init__(self, model: BranchConserveModel, telemetry: SteadySolverTelemetry):
        self.model = model
        self.telemetry = telemetry
        self.maximum = int(model.contract.solver["full_residual_evaluations_max"])

    def evaluate(
        self, z: np.ndarray, device_voltage_V: float, branch_memory: float
    ) -> SteadyEvaluation:
        if self.telemetry.full_residual_evaluations >= self.maximum:
            raise _RootBudgetExceeded("full thermal residual evaluation budget exhausted")
        self.telemetry.full_residual_evaluations += 1
        self.telemetry.electrical_subsolves += 1
        return self.model.evaluate_scaled_temperature(
            z, device_voltage_V, branch_memory
        )


def _thermal_factorization(model: BranchConserveModel):
    matrix = model.thermal_matrix.tocsc() + sparse.diags(
        model.sink_cell_W_K, format="csc"
    )
    try:
        return splu(matrix, permc_spec="COLAMD")
    except Exception as exc:
        raise SteadyModelError("STEADY_PRECONDITIONER_FAIL", str(exc)) from exc


def _initial_temperature(
    model: BranchConserveModel,
    branch_memory: float,
    initial_temperature_K: np.ndarray | None,
) -> np.ndarray:
    if initial_temperature_K is not None:
        values = np.asarray(initial_temperature_K, dtype=float)
        if values.shape != model.grid.shape:
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "initial temperature shape is invalid"
            )
        return values.copy()
    initialization = model.contract.solver["initialization"]
    value = (
        float(initialization["low_endpoint_temperature_K"])
        if branch_memory == 1.0
        else float(initialization["high_endpoint_temperature_K"])
    )
    return np.full(model.grid.shape, value, dtype=float)


def solve_steady_equilibrium(
    model: BranchConserveModel,
    *,
    device_voltage_V: float,
    branch_memory: float,
    initial_temperature_K: np.ndarray | None = None,
) -> SteadySolveOutcome:
    """Solve one fixed-device-voltage equilibrium with the frozen strategy."""

    telemetry = SteadySolverTelemetry()
    wall_started = perf_counter()
    cpu_started = process_time()
    evaluation: SteadyEvaluation | None = None
    temperature: np.ndarray | None = None
    last_update = float("inf")
    code = "STEADY_NONLINEAR_MAX_ITER"
    success = False

    def finish() -> SteadySolveOutcome:
        telemetry.wall_time_s = perf_counter() - wall_started
        telemetry.cpu_time_s = process_time() - cpu_started
        return SteadySolveOutcome(
            success=success,
            code=code,
            branch_memory=float(branch_memory),
            device_voltage_V=float(device_voltage_V),
            temperature_K=None if temperature is None else temperature.copy(),
            evaluation=evaluation,
            last_scaled_update_inf=float(last_update),
            telemetry=telemetry,
        )

    try:
        if branch_memory not in (-1.0, 1.0):
            raise SteadyModelError(
                "STEADY_NONFINITE_OR_RANGE", "branch metadata must be +1 or -1"
            )
        factorization = _thermal_factorization(model)
        counted = _CountedResidual(model, telemetry)
        guess = _initial_temperature(model, branch_memory, initial_temperature_K)
        z_guess = model.scaled_from_temperature(guess)
        predictor_evaluation = counted.evaluate(
            z_guess, device_voltage_V, branch_memory
        )
        predictor_rhs = predictor_evaluation.cell_joule_power_W.reshape(-1) + (
            model.sink_cell_W_K * model.ambient_temperature_K
        )
        try:
            corrected = np.asarray(
                factorization.solve(predictor_rhs), dtype=float
            ).reshape(model.grid.shape)
        except Exception as exc:
            raise SteadyModelError("STEADY_PRECONDITIONER_FAIL", str(exc)) from exc
        model._validate_temperature(corrected)
        z = model.scaled_from_temperature(corrected)
        evaluation = counted.evaluate(z, device_voltage_V, branch_memory)
        residual = np.asarray(evaluation.scaled_thermal_residual, dtype=float)
        residual_inf = float(np.max(np.abs(residual)))
        telemetry.residual_inf_history.append(residual_inf)
        last_update = 0.0

        solver = model.contract.solver
        residual_gate = float(solver["residual_inf_max"])
        update_gate = float(solver["last_scaled_update_inf_max"])
        maximum_newton = int(solver["nonlinear_iterations_max"])
        maximum_jv = int(solver["jv_evaluations_max"])
        damping_values = tuple(float(x) for x in solver["armijo"]["damping_values"])
        if len(damping_values) != int(solver["line_search_backtracks_max"]) + 1:
            raise ValueError("line-search damping count differs from the frozen budget")

        preconditioner = LinearOperator(
            (z.size, z.size),
            matvec=lambda vector: np.asarray(
                factorization.solve(
                    np.asarray(vector, dtype=float)
                    * (model.contract.scales.power_W / z.size)
                ),
                dtype=float,
            )
            / model.temperature_reference_K,
            dtype=float,
        )

        for iteration in range(maximum_newton + 1):
            if residual_inf <= residual_gate and last_update <= update_gate:
                temperature = model.temperature_from_scaled(z)
                if (
                    evaluation.scaled_electrical_residual_inf
                    > model.contract.scales.electrical_residual_max
                    or not evaluation.ledger.pass_all
                    or not evaluation.finite_and_range_legal
                ):
                    code = "STEADY_POSTCERTIFICATION_FAIL"
                    telemetry.failure_detail = "root met nonlinear gates but failed post-certification"
                    return finish()
                success = True
                code = "PASS"
                return finish()
            if iteration == maximum_newton:
                break
            telemetry.nonlinear_iterations += 1
            base_z = z.copy()
            base_residual = residual.copy()
            epsilon = np.finfo(float).eps

            def jv(vector: np.ndarray) -> np.ndarray:
                if telemetry.jv_evaluations >= maximum_jv:
                    raise _RootBudgetExceeded("Jv budget exhausted")
                telemetry.jv_evaluations += 1
                direction = np.asarray(vector, dtype=float)
                magnitude = float(np.linalg.norm(direction, ord=np.inf))
                if magnitude == 0.0:
                    return np.zeros_like(direction)
                unit_direction = direction / magnitude
                h = epsilon ** (1.0 / 3.0) * max(
                    1.0, float(np.linalg.norm(base_z, ord=np.inf))
                ) / max(1.0, float(np.linalg.norm(unit_direction, ord=np.inf)))
                plus = counted.evaluate(
                    base_z + h * unit_direction, device_voltage_V, branch_memory
                )
                minus = counted.evaluate(
                    base_z - h * unit_direction, device_voltage_V, branch_memory
                )
                return magnitude * model.conservative_thermal_jv_from_pair(
                    unit_direction, h, plus, minus
                )

            jacobian = LinearOperator((z.size, z.size), matvec=jv, dtype=float)
            remaining = maximum_jv - telemetry.jv_evaluations
            inner_m = int(solver["lgmres"]["inner_m"])
            # SciPy's ``maxiter`` counts outer iterations, not matvecs.  An
            # outer iteration may terminate its inner cycle early, so dividing
            # by ``inner_m`` can reject a convergent solve after only a small
            # fraction of the registered matvec budget.  The Jv wrapper is the
            # authoritative hard stop and fails before evaluation 513.
            maximum_outer = max(1, remaining)

            def callback(_: np.ndarray) -> None:
                telemetry.lgmres_iterations += 1

            try:
                krylov_initial = preconditioner.matvec(-base_residual)
                delta, info = lgmres(
                    jacobian,
                    -base_residual,
                    x0=krylov_initial,
                    M=preconditioner,
                    rtol=float(solver["lgmres"]["rtol"]),
                    atol=float(solver["lgmres"]["atol"]),
                    maxiter=maximum_outer,
                    inner_m=inner_m,
                    outer_k=int(solver["lgmres"]["outer_k"]),
                    callback=callback,
                )
            except _RootBudgetExceeded:
                raise
            except SteadyModelError:
                raise
            except Exception as exc:
                telemetry.failure_detail = f"LGMRES failed: {exc}"
                code = "STEADY_KRYLOV_BUDGET"
                return finish()
            if info != 0 or not np.isfinite(delta).all():
                telemetry.failure_detail = f"LGMRES returned info={info}"
                code = "STEADY_KRYLOV_BUDGET"
                return finish()

            phi0 = 0.5 * float(np.dot(base_residual, base_residual))
            accepted = False
            for backtrack, damping in enumerate(damping_values):
                candidate_z = base_z + damping * np.asarray(delta, dtype=float)
                try:
                    candidate = counted.evaluate(
                        candidate_z, device_voltage_V, branch_memory
                    )
                except SteadyModelError as exc:
                    if exc.code != "STEADY_NONFINITE_OR_RANGE":
                        raise
                    candidate = None
                if candidate is not None:
                    candidate_residual = np.asarray(
                        candidate.scaled_thermal_residual, dtype=float
                    )
                    phi = 0.5 * float(np.dot(candidate_residual, candidate_residual))
                    sufficient = phi <= (
                        1.0 - 2.0 * float(solver["armijo"]["c1"]) * damping
                    ) * phi0
                    certified = (
                        float(np.max(np.abs(candidate_residual))) <= residual_gate
                        and float(np.max(np.abs(damping * delta))) <= update_gate
                    )
                    if sufficient or certified:
                        z = candidate_z
                        evaluation = candidate
                        residual = candidate_residual
                        residual_inf = float(np.max(np.abs(residual)))
                        last_update = float(np.max(np.abs(damping * delta)))
                        telemetry.residual_inf_history.append(residual_inf)
                        telemetry.update_inf_history.append(last_update)
                        telemetry.damping_history.append(damping)
                        telemetry.line_search_backtracks += backtrack
                        accepted = True
                        break
                if backtrack == len(damping_values) - 1:
                    telemetry.line_search_backtracks += backtrack
            if not accepted:
                telemetry.failure_detail = "no frozen damping value met Armijo descent"
                code = "STEADY_LINE_SEARCH_NO_DESCENT"
                return finish()

        temperature = model.temperature_from_scaled(z)
        code = "STEADY_NONLINEAR_MAX_ITER"
        telemetry.failure_detail = "maximum nonlinear iterations reached"
        return finish()
    except _RootBudgetExceeded as exc:
        code = "STEADY_KRYLOV_BUDGET"
        telemetry.failure_detail = str(exc)
        return finish()
    except SteadyModelError as exc:
        code = exc.code
        telemetry.failure_detail = str(exc)
        return finish()
    except Exception as exc:
        code = "STEADY_POSTCERTIFICATION_FAIL"
        telemetry.failure_detail = f"unexpected solver error: {type(exc).__name__}: {exc}"
        return finish()


def scaled_secant_predictor(
    model: BranchConserveModel,
    previous_temperature_K: np.ndarray,
    previous_device_voltage_V: float,
    current_temperature_K: np.ndarray,
    current_device_voltage_V: float,
    target_device_voltage_V: float,
) -> np.ndarray:
    """Return the frozen two-point scaled secant predictor."""

    denominator = current_device_voltage_V - previous_device_voltage_V
    if not np.isfinite(denominator) or abs(denominator) <= 1.0e-15:
        return np.asarray(current_temperature_K, dtype=float).copy()
    fraction = (target_device_voltage_V - current_device_voltage_V) / denominator
    z_previous = model.scaled_from_temperature(previous_temperature_K)
    z_current = model.scaled_from_temperature(current_temperature_K)
    predicted = z_current + fraction * (z_current - z_previous)
    return model.temperature_from_scaled(predicted)

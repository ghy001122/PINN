"""Unique no-fallback temperature-primary Newton--Krylov solver for CC-B."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, process_time

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, lgmres, splu

from pinnpcm.current_clamp.cc_b_model import (
    CCBEvaluation,
    CCBModelError,
    CurrentClamp2DModel,
)


class _BudgetExceeded(RuntimeError):
    pass


@dataclass
class CCBSolverTelemetry:
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
class CCBSolveOutcome:
    success: bool
    code: str
    current_set_A: float
    branch: str
    defect: str
    spatial_level: int
    temperature_K: np.ndarray | None
    evaluation: CCBEvaluation | None
    last_scaled_update_inf: float
    telemetry: CCBSolverTelemetry


class _CountedResidual:
    def __init__(self, model: CurrentClamp2DModel, telemetry: CCBSolverTelemetry):
        self.model = model
        self.telemetry = telemetry
        self.maximum = int(model.contract.solver["full_residual_evaluations_max"])

    def evaluate(self, z: np.ndarray) -> CCBEvaluation:
        if self.telemetry.full_residual_evaluations >= self.maximum:
            raise _BudgetExceeded("full thermal residual evaluation budget exhausted")
        self.telemetry.full_residual_evaluations += 1
        self.telemetry.electrical_subsolves += 1
        return self.model.evaluate_scaled_temperature(z)


def _factorization(model: CurrentClamp2DModel):
    matrix = model.thermal_matrix.tocsc() + sparse.diags(
        model.sink_cell_W_K, format="csc"
    )
    try:
        return splu(matrix, permc_spec="COLAMD")
    except Exception as exc:
        raise CCBModelError("CCB_PRECONDITIONER_FAIL", str(exc)) from exc


def solve_cc_b_equilibrium(
    model: CurrentClamp2DModel,
    *,
    initial_temperature_K: np.ndarray | None = None,
) -> CCBSolveOutcome:
    """Solve one fixed-current, fixed-branch, fixed-defect equilibrium."""

    telemetry = CCBSolverTelemetry()
    wall_started = perf_counter()
    cpu_started = process_time()
    evaluation: CCBEvaluation | None = None
    temperature: np.ndarray | None = None
    last_update = float("inf")
    code = "CCB_NONLINEAR_MAX_ITER"
    success = False

    def finish() -> CCBSolveOutcome:
        telemetry.wall_time_s = perf_counter() - wall_started
        telemetry.cpu_time_s = process_time() - cpu_started
        return CCBSolveOutcome(
            success=success,
            code=code,
            current_set_A=model.current_set_A,
            branch=model.branch,
            defect=model.defect,
            spatial_level=model.spatial_level,
            temperature_K=None if temperature is None else temperature.copy(),
            evaluation=evaluation,
            last_scaled_update_inf=float(last_update),
            telemetry=telemetry,
        )

    try:
        factorization = _factorization(model)
        counted = _CountedResidual(model, telemetry)
        if initial_temperature_K is None:
            default = model.ambient_temperature_K if model.branch == "heating" else 370.0
            guess = np.full(model.grid.shape, default, dtype=float)
        else:
            guess = np.asarray(initial_temperature_K, dtype=float).copy()
        model.validate_temperature(guess)
        z_guess = model.scaled_from_temperature(guess)
        predictor = counted.evaluate(z_guess)
        predictor_rhs = predictor.cell_joule_power_W.reshape(-1) + (
            model.sink_cell_W_K * model.ambient_temperature_K
        )
        try:
            corrected = np.asarray(
                factorization.solve(predictor_rhs), dtype=float
            ).reshape(model.grid.shape)
        except Exception as exc:
            raise CCBModelError("CCB_PRECONDITIONER_FAIL", str(exc)) from exc
        model.validate_temperature(corrected)
        z = model.scaled_from_temperature(corrected)
        evaluation = counted.evaluate(z)
        residual = np.asarray(evaluation.scaled_thermal_residual, dtype=float)
        residual_inf = float(np.max(np.abs(residual)))
        telemetry.residual_inf_history.append(residual_inf)
        last_update = 0.0

        solver = model.contract.solver
        residual_gate = float(solver["residual_inf_max"])
        update_gate = float(solver["last_scaled_update_inf_max"])
        maximum_newton = int(solver["nonlinear_iterations_max"])
        maximum_jv = int(solver["jv_evaluations_max"])
        damping_values = tuple(float(value) for value in solver["armijo"]["damping_values"])
        if len(damping_values) != int(solver["line_search_backtracks_max"]) + 1:
            raise CCBModelError("CCB_CONTRACT_DRIFT", "line-search budget drifted")

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
                gates = model.contract.raw["equilibrium_gates"]
                if (
                    evaluation.scaled_electrical_residual_inf
                    > float(gates["electrical_scaled_cv_residual_max"])
                    or not evaluation.ledger.pass_all
                    or not evaluation.finite_and_range_legal
                ):
                    code = "CCB_POSTCERTIFICATION_FAIL"
                    telemetry.failure_detail = "nonlinear root failed a residual, ledger, or range gate"
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
                    raise _BudgetExceeded("Jv budget exhausted")
                telemetry.jv_evaluations += 1
                direction = np.asarray(vector, dtype=float)
                magnitude = float(np.linalg.norm(direction, ord=np.inf))
                if magnitude == 0.0:
                    return np.zeros_like(direction)
                unit = direction / magnitude
                h = epsilon ** (1.0 / 3.0) * max(
                    1.0, float(np.linalg.norm(base_z, ord=np.inf))
                ) / max(1.0, float(np.linalg.norm(unit, ord=np.inf)))
                plus = counted.evaluate(base_z + h * unit)
                minus = counted.evaluate(base_z - h * unit)
                return magnitude * model.conservative_thermal_jv_from_pair(
                    unit, h, plus, minus
                )

            operator = LinearOperator((z.size, z.size), matvec=jv, dtype=float)

            def callback(_: np.ndarray) -> None:
                telemetry.lgmres_iterations += 1

            try:
                delta, info = lgmres(
                    operator,
                    -base_residual,
                    x0=preconditioner.matvec(-base_residual),
                    M=preconditioner,
                    rtol=float(solver["lgmres"]["rtol"]),
                    atol=float(solver["lgmres"]["atol"]),
                    maxiter=max(1, maximum_jv - telemetry.jv_evaluations),
                    inner_m=int(solver["lgmres"]["inner_m"]),
                    outer_k=int(solver["lgmres"]["outer_k"]),
                    callback=callback,
                )
            except _BudgetExceeded:
                raise
            except CCBModelError:
                raise
            except Exception as exc:
                code = "CCB_KRYLOV_FAIL"
                telemetry.failure_detail = f"LGMRES failed: {exc}"
                return finish()
            if info != 0 or not np.isfinite(delta).all():
                code = "CCB_KRYLOV_FAIL"
                telemetry.failure_detail = f"LGMRES returned info={info}"
                return finish()

            phi0 = 0.5 * float(np.dot(base_residual, base_residual))
            accepted = False
            for backtrack, damping in enumerate(damping_values):
                candidate_z = base_z + damping * np.asarray(delta, dtype=float)
                try:
                    candidate = counted.evaluate(candidate_z)
                except CCBModelError as exc:
                    if exc.code != "CCB_NONFINITE_OR_RANGE":
                        raise
                    candidate = None
                if candidate is not None:
                    candidate_residual = np.asarray(candidate.scaled_thermal_residual, dtype=float)
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
                code = "CCB_LINE_SEARCH_NO_DESCENT"
                telemetry.failure_detail = "no frozen damping value met Armijo descent"
                return finish()
        temperature = model.temperature_from_scaled(z)
        code = "CCB_NONLINEAR_MAX_ITER"
        telemetry.failure_detail = "maximum nonlinear iterations reached"
        return finish()
    except _BudgetExceeded as exc:
        code = "CCB_KRYLOV_BUDGET"
        telemetry.failure_detail = str(exc)
        return finish()
    except CCBModelError as exc:
        code = exc.code
        telemetry.failure_detail = str(exc)
        return finish()
    except Exception as exc:
        code = "CCB_POSTCERTIFICATION_FAIL"
        telemetry.failure_detail = f"unexpected solver error: {type(exc).__name__}: {exc}"
        return finish()


def prolong_temperature(coarse: np.ndarray, fine_shape: tuple[int, int]) -> np.ndarray:
    """Piecewise-constant conservative L1-to-L2 prolongation."""

    values = np.asarray(coarse, dtype=float)
    fy, fx = fine_shape
    cy, cx = values.shape
    if fy % cy or fx % cx:
        raise ValueError("fine grid is not nested over the coarse grid")
    return np.repeat(np.repeat(values, fy // cy, axis=0), fx // cx, axis=1)


def restrict_area_average(fine: np.ndarray, coarse_shape: tuple[int, int]) -> np.ndarray:
    """Conservative area average from a nested uniform fine grid."""

    values = np.asarray(fine, dtype=float)
    cy, cx = coarse_shape
    fy, fx = values.shape
    if fy % cy or fx % cx:
        raise ValueError("fine grid is not nested over the coarse grid")
    ry, rx = fy // cy, fx // cx
    return values.reshape(cy, ry, cx, rx).mean(axis=(1, 3))

"""Constrained temperature-only local stability for the algebraic current clamp."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, process_time
from typing import Any

import numpy as np
from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigs

from pinnpcm.current_clamp.cc_b_model import CCBModelError, CurrentClamp2DModel


@dataclass
class CCBStabilityTelemetry:
    matrix_vector_products: int = 0
    dynamic_rhs_evaluations: int = 0
    wall_time_s: float = 0.0
    cpu_time_s: float = 0.0
    failure_detail: str | None = None


@dataclass(frozen=True)
class CCBStabilityOutcome:
    success: bool
    code: str
    stable: bool
    eigenpair_count: int
    rightmost_spectral_abscissa_per_s: float
    alpha_tau_dimensionless: float
    eigenvalues_per_s: np.ndarray
    eigenvectors_temperature: np.ndarray
    relative_ritz_residuals: np.ndarray
    absolute_backward_errors_per_s: np.ndarray
    h_half_operator_relative_difference: float
    telemetry: CCBStabilityTelemetry


def _failure(
    telemetry: CCBStabilityTelemetry, code: str, detail: str, k: int
) -> CCBStabilityOutcome:
    telemetry.failure_detail = detail
    return CCBStabilityOutcome(
        success=False,
        code=code,
        stable=False,
        eigenpair_count=k,
        rightmost_spectral_abscissa_per_s=float("nan"),
        alpha_tau_dimensionless=float("nan"),
        eigenvalues_per_s=np.asarray([], dtype=complex),
        eigenvectors_temperature=np.empty((0, 0), dtype=complex),
        relative_ritz_residuals=np.asarray([], dtype=float),
        absolute_backward_errors_per_s=np.asarray([], dtype=float),
        h_half_operator_relative_difference=float("nan"),
        telemetry=telemetry,
    )


def _deterministic_vector(model: CurrentClamp2DModel) -> np.ndarray:
    x, y = np.meshgrid(model.grid.x_centers_m, model.grid.y_centers_m)
    xr = (x - float(np.mean(x))) / max(float(np.ptp(x)), 1.0e-30)
    yr = (y - float(np.mean(y))) / max(float(np.ptp(y)), 1.0e-30)
    vector = (1.0 + 0.25 * xr - 0.125 * yr).reshape(-1)
    return vector / max(float(np.linalg.norm(vector)), 1.0e-300)


def _mass_norm(vector: np.ndarray, mass: np.ndarray) -> float:
    values = np.asarray(vector)
    return float(np.sqrt(np.sum(mass * np.abs(values) ** 2)))


def _apply_operator(
    model: CurrentClamp2DModel,
    base_temperature_K: np.ndarray,
    vector: np.ndarray,
    telemetry: CCBStabilityTelemetry,
    *,
    step_multiplier: float = 1.0,
    recorder: Any | None = None,
    call_role: str = "operator",
) -> np.ndarray:
    wall_started = perf_counter()
    cpu_started = process_time()
    telemetry.matrix_vector_products += 1
    direction = np.asarray(vector, dtype=float)
    magnitude = float(np.linalg.norm(direction, ord=np.inf))
    if magnitude == 0.0:
        result = np.zeros_like(direction)
        if recorder is not None:
            recorder.record_jv(
                call_role=call_role,
                step_multiplier=float(step_multiplier),
                step_size_K=0.0,
                direction=direction,
                result=result,
                electrical_evaluations=[],
                wall_time_s=perf_counter() - wall_started,
                cpu_time_s=process_time() - cpu_started,
                exception=None,
            )
        return result
    unit = direction / magnitude
    epsilon = np.finfo(float).eps
    h = (
        step_multiplier
        * epsilon ** (1.0 / 3.0)
        * max(1.0, float(np.linalg.norm(base_temperature_K, ord=np.inf)))
        / max(1.0, float(np.linalg.norm(unit, ord=np.inf)))
    )
    telemetry.dynamic_rhs_evaluations += 2
    electrical_evaluations: list[dict[str, Any]] = []
    callback = electrical_evaluations.append if recorder is not None else None
    try:
        plus = model.dynamic_rhs(
            base_temperature_K + h * unit.reshape(model.grid.shape),
            telemetry_callback=callback,
        )
        minus = model.dynamic_rhs(
            base_temperature_K - h * unit.reshape(model.grid.shape),
            telemetry_callback=callback,
        )
        result = magnitude * (plus - minus) / (2.0 * h)
        if recorder is not None:
            recorder.record_jv(
                call_role=call_role,
                step_multiplier=float(step_multiplier),
                step_size_K=float(h),
                direction=direction,
                result=result,
                electrical_evaluations=electrical_evaluations,
                wall_time_s=perf_counter() - wall_started,
                cpu_time_s=process_time() - cpu_started,
                exception=None,
            )
        return result
    except Exception as exc:
        if recorder is not None:
            recorder.record_jv(
                call_role=call_role,
                step_multiplier=float(step_multiplier),
                step_size_K=float(h),
                direction=direction,
                result=None,
                electrical_evaluations=electrical_evaluations,
                wall_time_s=perf_counter() - wall_started,
                cpu_time_s=process_time() - cpu_started,
                exception=exc,
            )
        raise


def certify_current_clamp_stability(
    model: CurrentClamp2DModel,
    *,
    temperature_K: np.ndarray,
    eigenpairs: int | None = None,
    recorder: Any | None = None,
) -> CCBStabilityOutcome:
    """Certify the rightmost spectrum of the constrained thermal DAE reduction."""

    telemetry = CCBStabilityTelemetry()
    wall_started = perf_counter()
    cpu_started = process_time()
    config = model.contract.stability
    k = int(config["eigenpairs"] if eigenpairs is None else eigenpairs)
    temperature = np.asarray(temperature_K, dtype=float)
    n = temperature.size
    stage = "PRE_OPERATOR"
    if recorder is not None:
        recorder.start_stability(
            requested_pair_count=k,
            state_dimension=n,
            temperature_K=temperature,
        )

    def fail(code: str, detail: str) -> CCBStabilityOutcome:
        if recorder is not None:
            recorder.record_failure(stage=stage, code=code, detail=detail)
        return _failure(telemetry, code, detail, k)

    if n <= k + 1:
        return fail("INVALID_STABILITY", "state dimension is too small")
    try:
        model.validate_temperature(temperature)
        probe = _deterministic_vector(model)
        stage = "JV_EVALUATION"
        jv_h = _apply_operator(
            model,
            temperature,
            probe,
            telemetry,
            recorder=recorder,
            call_role="parent_h_probe",
        )
        jv_h2 = _apply_operator(
            model,
            temperature,
            probe,
            telemetry,
            step_multiplier=0.5,
            recorder=recorder,
            call_role="parent_h_half_probe",
        )
        h_half_difference = float(
            np.linalg.norm(jv_h - jv_h2)
            / max(np.linalg.norm(jv_h), np.linalg.norm(jv_h2), 1.0 / model.tau0_s)
        )
        if recorder is not None:
            recorder.record_h_half_consistency(h_half_difference)
        if h_half_difference > float(config["h_half_operator_relative_difference_max"]):
            return fail(
                "INVALID_STABILITY",
                "central-difference h/h2 operator consistency failed",
            )

        stage = "OPERATOR_BUILD"
        operator = LinearOperator(
            (n, n),
            matvec=lambda vector: _apply_operator(
                model,
                temperature,
                np.asarray(vector, dtype=float),
                telemetry,
                recorder=recorder,
                call_role="arpack_matvec",
            ),
            dtype=float,
        )
        stage = "EIGENSOLVER"
        try:
            values, vectors = eigs(
                operator,
                k=k,
                which=str(config["which"]),
                tol=float(config["tolerance"]),
                maxiter=int(config["maxiter"]),
                ncv=min(max(int(config["ncv"]), 2 * k + 1), n - 1),
                v0=probe,
            )
        except ArpackNoConvergence as exc:
            if recorder is not None:
                recorder.record_eigensolver_return(
                    eigenvalues=getattr(exc, "eigenvalues", None),
                    eigenvectors=getattr(exc, "eigenvectors", None),
                    converged=False,
                    exception=exc,
                    eligible_for_certification=False,
                )
            return fail("INVALID_STABILITY", f"ARPACK did not converge: {exc}")
        if recorder is not None:
            recorder.record_eigensolver_return(
                eigenvalues=values,
                eigenvectors=vectors,
                converged=True,
                exception=None,
                eligible_for_certification=True,
            )
        if values.size != k or vectors.shape != (n, k):
            return fail("INVALID_STABILITY", "incomplete eigenspectrum")

        stage = "RITZ_CERTIFICATION"
        mass = model.cell_capacity_J_K
        relative: list[float] = []
        absolute: list[float] = []
        for index in range(k):
            vector = vectors[:, index]
            applied = _apply_operator(
                model,
                temperature,
                vector.real,
                telemetry,
                recorder=recorder,
                call_role=f"ritz_{index}_real",
            )
            if np.any(vector.imag):
                applied = applied + 1j * _apply_operator(
                    model,
                    temperature,
                    vector.imag,
                    telemetry,
                    recorder=recorder,
                    call_role=f"ritz_{index}_imag",
                )
            residual = applied - values[index] * vector
            rho = _mass_norm(residual, mass) / max(_mass_norm(vector, mass), 1.0e-300)
            eta = rho / max(abs(values[index]), 1.0 / model.tau0_s)
            absolute.append(rho)
            relative.append(eta)
        relative_values = np.asarray(relative, dtype=float)
        backward = np.asarray(absolute, dtype=float)
        if recorder is not None:
            recorder.record_ritz_certification(
                eigenvalues=values,
                eigenvectors=vectors,
                absolute_residual_rates_per_s=backward,
                relative_residuals=relative_values,
            )
        if (
            not np.isfinite(relative_values).all()
            or not np.isfinite(backward).all()
            or float(np.max(relative_values)) > float(config["relative_ritz_residual_max"])
        ):
            return fail("INVALID_STABILITY", "Ritz residual certification failed")
        alpha = float(np.max(values.real))
        alpha_tau = alpha * model.tau0_s
        stable = bool(
            alpha_tau <= float(config["stable_alpha_tau_max"])
            and alpha <= -float(config["backward_error_multiplier"]) * float(np.max(backward))
        )
        outcome = CCBStabilityOutcome(
            success=True,
            code="PASS" if stable else "CCB_PHYSICALLY_UNSTABLE",
            stable=stable,
            eigenpair_count=k,
            rightmost_spectral_abscissa_per_s=alpha,
            alpha_tau_dimensionless=alpha_tau,
            eigenvalues_per_s=np.asarray(values, dtype=complex),
            eigenvectors_temperature=np.asarray(vectors, dtype=complex),
            relative_ritz_residuals=relative_values,
            absolute_backward_errors_per_s=backward,
            h_half_operator_relative_difference=h_half_difference,
            telemetry=telemetry,
        )
        if recorder is not None:
            recorder.record_outcome(outcome)
        return outcome
    except CCBModelError as exc:
        return fail("INVALID_STABILITY", f"{exc.code}: {exc}")
    except Exception as exc:
        return fail(
            "INVALID_STABILITY",
            f"stability evaluation failed: {type(exc).__name__}: {exc}",
        )
    finally:
        telemetry.wall_time_s = perf_counter() - wall_started
        telemetry.cpu_time_s = process_time() - cpu_started
        if recorder is not None:
            recorder.finish_stability(telemetry)


def uniform_mode_operator_regression(
    model: CurrentClamp2DModel,
    *,
    equilibrium_temperature_K: float,
    analytic_lambda_per_s: float,
) -> dict[str, float | bool]:
    """Recover the CC-A scalar thermal rate from the 2D constrained operator."""

    if not model.uniform_coefficients:
        raise ValueError("uniform-mode regression requires uniform coefficients")
    temperature = np.full(model.grid.shape, equilibrium_temperature_K, dtype=float)
    telemetry = CCBStabilityTelemetry()
    mode = np.ones(temperature.size, dtype=float)
    applied_h = _apply_operator(model, temperature, mode, telemetry)
    applied_h2 = _apply_operator(
        model, temperature, mode, telemetry, step_multiplier=0.5
    )
    # Central differences are second order.  The manufactured uniform-mode
    # gate uses deterministic Richardson cancellation so that its 1e-6 source
    # identity threshold tests the topology rather than finite-difference
    # truncation.  Production spectra retain the preregistered central Jv.
    applied = (4.0 * applied_h2 - applied_h) / 3.0
    mass = model.cell_capacity_J_K
    rayleigh = float(np.sum(mass * mode * applied) / np.sum(mass * mode * mode))
    residual = applied - rayleigh * mode
    mass_residual = _mass_norm(residual, mass) / max(
        _mass_norm(mode, mass) / model.tau0_s, 1.0e-300
    )
    dimensionless_error = abs(rayleigh - analytic_lambda_per_s) * model.tau0_s / max(
        abs(analytic_lambda_per_s * model.tau0_s), 1.0
    )
    sign_floor = float(model.contract.raw["uniform_gate"]["sign_guard_dimensionless_floor"])
    sign_match = bool(
        abs(analytic_lambda_per_s * model.tau0_s) <= sign_floor
        or np.sign(rayleigh) == np.sign(analytic_lambda_per_s)
    )
    gate = model.contract.raw["uniform_gate"]
    passed = bool(
        dimensionless_error <= float(gate["topology_operator_dimensionless_error_max"])
        and mass_residual <= float(gate["topology_operator_mass_residual_max"])
        and sign_match
    )
    return {
        "passed": passed,
        "analytic_lambda_per_s": analytic_lambda_per_s,
        "two_dimensional_rayleigh_lambda_per_s": rayleigh,
        "dimensionless_error": dimensionless_error,
        "mass_norm_uniform_mode_residual": mass_residual,
        "sign_match": sign_match,
        "operator_evaluations": telemetry.dynamic_rhs_evaluations,
    }

"""Sparse branch-conditioned electrothermal local-stability certification."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter, process_time

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigs

from pinnpcm.branchconserve.steady_model import BranchConserveModel, SteadyModelError


@dataclass
class StabilityTelemetry:
    matrix_vector_products: int = 0
    dynamic_rhs_evaluations: int = 0
    repeat_wall_time_s: list[float] = field(default_factory=list)
    wall_time_s: float = 0.0
    cpu_time_s: float = 0.0
    failure_detail: str | None = None


@dataclass(frozen=True)
class StabilityOutcome:
    success: bool
    code: str
    stable: bool
    rightmost_spectral_abscissa_per_s: float
    tau_lambda_per_s: float
    eigenvalues_per_s: np.ndarray
    eigenvectors_scaled: np.ndarray
    relative_residuals: np.ndarray
    backward_errors_per_s: np.ndarray
    spectral_abscissa_repeats_per_s: np.ndarray
    matched_repeat_spread_per_s: float
    telemetry: StabilityTelemetry


def _deterministic_initial_vectors(model: BranchConserveModel) -> tuple[np.ndarray, ...]:
    grid = model.grid
    x, y = np.meshgrid(grid.x_centers_m, grid.y_centers_m)
    x_ramp = (x - float(np.mean(x))) / max(float(np.ptp(x)), 1.0e-30)
    y_ramp = (y - float(np.mean(y))) / max(float(np.ptp(y)), 1.0e-30)
    thermal_modes = (
        np.ones(grid.shape, dtype=float),
        x_ramp,
        y_ramp,
    )
    voltage_signs = (1.0, -1.0, 1.0)
    vectors: list[np.ndarray] = []
    for thermal, voltage in zip(thermal_modes, voltage_signs, strict=True):
        vector = np.concatenate((thermal.reshape(-1), np.asarray([voltage])))
        vector /= max(float(np.linalg.norm(vector)), 1.0e-30)
        vectors.append(vector)
    return tuple(vectors)


def _match_eigenvalues(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    cost = np.abs(reference[:, None] - candidate[None, :])
    rows, columns = linear_sum_assignment(cost)
    ordered = np.empty_like(reference)
    ordered[rows] = candidate[columns]
    return ordered


def _failure(
    telemetry: StabilityTelemetry,
    code: str,
    detail: str,
) -> StabilityOutcome:
    telemetry.failure_detail = detail
    return StabilityOutcome(
        success=False,
        code=code,
        stable=False,
        rightmost_spectral_abscissa_per_s=float("nan"),
        tau_lambda_per_s=float("nan"),
        eigenvalues_per_s=np.asarray([], dtype=complex),
        eigenvectors_scaled=np.empty((0, 0), dtype=complex),
        relative_residuals=np.asarray([], dtype=float),
        backward_errors_per_s=np.asarray([], dtype=float),
        spectral_abscissa_repeats_per_s=np.asarray([], dtype=float),
        matched_repeat_spread_per_s=float("nan"),
        telemetry=telemetry,
    )


def certify_branch_conditioned_stability(
    model: BranchConserveModel,
    *,
    temperature_K: np.ndarray,
    device_voltage_V: float,
    source_voltage_V: float,
    branch_memory: float,
) -> StabilityOutcome:
    """Compute and certify the matrix-free rightmost spectrum three times."""

    config = model.contract.stability
    telemetry = StabilityTelemetry()
    wall_started = perf_counter()
    cpu_started = process_time()
    temperature = np.asarray(temperature_K, dtype=float)
    n_temperature = temperature.size
    dimension = n_temperature + 1
    k = int(config["eigenpairs"])
    if dimension <= k + 1:
        return _failure(
            telemetry,
            "STABILITY_SPECTRUM_INCONSISTENT",
            "state dimension is too small for the frozen sparse spectrum contract",
        )

    scaled_state = np.concatenate(
        (
            model.scaled_from_temperature(temperature),
            np.asarray([device_voltage_V / model.contract.scales.voltage_V]),
        )
    )
    state_scales = np.concatenate(
        (
            np.full(n_temperature, model.temperature_reference_K),
            np.asarray([model.contract.scales.voltage_V]),
        )
    )
    mass = np.concatenate(
        (
            model.cell_capacity_J_K,
            np.asarray([model.contract.external_capacitance_F]),
        )
    )
    epsilon = np.finfo(float).eps

    def matvec(vector: np.ndarray) -> np.ndarray:
        telemetry.matrix_vector_products += 1
        direction = np.asarray(vector, dtype=float)
        magnitude = float(np.linalg.norm(direction, ord=np.inf))
        if magnitude == 0.0:
            return np.zeros_like(direction)
        unit_direction = direction / magnitude
        h = epsilon ** (1.0 / 3.0) * max(
            1.0, float(np.linalg.norm(scaled_state, ord=np.inf))
        ) / max(1.0, float(np.linalg.norm(unit_direction, ord=np.inf)))
        plus_state = scaled_state + h * unit_direction
        minus_state = scaled_state - h * unit_direction

        def evaluate(state: np.ndarray):
            telemetry.dynamic_rhs_evaluations += 1
            t_values = model.temperature_from_scaled(state[:n_temperature])
            vd_value = float(state[-1] * model.contract.scales.voltage_V)
            return model.evaluate_temperature(
                t_values,
                vd_value,
                branch_memory,
                source_voltage_V=source_voltage_V,
            )

        plus = evaluate(plus_state)
        minus = evaluate(minus_state)
        thermal_scaled_residual_jv = model.conservative_thermal_jv_from_pair(
            unit_direction[:n_temperature], h, plus, minus
        )
        thermal_physical_rhs_jv = -thermal_scaled_residual_jv * (
            model.contract.scales.power_W / n_temperature
        )
        circuit_plus = plus.source_load_current_A - plus.source_current_A
        circuit_minus = minus.source_load_current_A - minus.source_current_A
        circuit_physical_rhs_jv = (circuit_plus - circuit_minus) / (2.0 * h)
        derivative_physical = np.concatenate(
            (thermal_physical_rhs_jv, np.asarray([circuit_physical_rhs_jv]))
        )
        return magnitude * derivative_physical / mass / state_scales

    operator = LinearOperator((dimension, dimension), matvec=matvec, dtype=float)
    repeat_values: list[np.ndarray] = []
    repeat_vectors: list[np.ndarray] = []
    try:
        for initial in _deterministic_initial_vectors(model):
            started = perf_counter()
            try:
                values, vectors = eigs(
                    operator,
                    k=k,
                    which=str(config["which"]),
                    tol=float(config["tolerance"]),
                    maxiter=int(config["maxiter"]),
                    ncv=min(int(config["ncv"]), dimension - 1),
                    v0=initial,
                )
            except ArpackNoConvergence as exc:
                return _failure(
                    telemetry,
                    "STABILITY_SPECTRUM_INCONSISTENT",
                    f"ARPACK failed to converge: {exc}",
                )
            finally:
                telemetry.repeat_wall_time_s.append(perf_counter() - started)
            if values.size != k or vectors.shape != (dimension, k):
                return _failure(
                    telemetry,
                    "STABILITY_SPECTRUM_INCONSISTENT",
                    "sparse eigensolver returned an incomplete spectrum",
                )
            repeat_values.append(np.asarray(values, dtype=complex))
            repeat_vectors.append(np.asarray(vectors, dtype=complex))
    except SteadyModelError as exc:
        return _failure(telemetry, exc.code, str(exc))
    except Exception as exc:
        return _failure(
            telemetry,
            "STABILITY_SPECTRUM_INCONSISTENT",
            f"spectrum evaluation failed: {type(exc).__name__}: {exc}",
        )
    finally:
        telemetry.wall_time_s = perf_counter() - wall_started
        telemetry.cpu_time_s = process_time() - cpu_started

    reference = repeat_values[0]
    matched = [reference]
    for values in repeat_values[1:]:
        matched.append(_match_eigenvalues(reference, values))
    matched_matrix = np.vstack(matched)
    spectral_abscissae = np.asarray(
        [float(np.max(values.real)) for values in repeat_values], dtype=float
    )

    selected_values = repeat_values[0]
    selected_vectors = repeat_vectors[0]
    relative_residuals: list[float] = []
    backward_errors: list[float] = []
    try:
        for index in range(k):
            vector = selected_vectors[:, index]
            # The operator is real but accepts a complex eigenvector by linearity.
            applied = matvec(vector.real) + 1j * matvec(vector.imag)
            residual = applied - selected_values[index] * vector
            residual_norm = float(np.linalg.norm(residual))
            vector_norm = max(float(np.linalg.norm(vector)), 1.0e-300)
            applied_norm = float(np.linalg.norm(applied))
            eigen_norm = abs(selected_values[index]) * vector_norm
            relative_residuals.append(
                residual_norm / max(applied_norm, eigen_norm, 1.0e-300)
            )
            backward_errors.append(residual_norm / vector_norm)
    except Exception as exc:
        return _failure(
            telemetry,
            "STABILITY_SPECTRUM_INCONSISTENT",
            f"eigenpair certification failed: {exc}",
        )

    relative = np.asarray(relative_residuals, dtype=float)
    backward = np.asarray(backward_errors, dtype=float)
    tau_theta = (
        model.thermal_fields.target_uniform_capacity_J_K
        / model.thermal_fields.target_uniform_conductance_W_K
    )
    tau_lambda = max(
        float(config["zero_band_timescale_fraction"]) / tau_theta,
        float(config["backward_error_multiplier"])
        * float(np.max(backward)),
    )
    matched_spread = float(
        np.max(np.abs(matched_matrix - matched_matrix[0:1, :]))
    )
    abscissa_span = float(np.ptp(spectral_abscissae))
    consistency = bool(
        np.isfinite(relative).all()
        and np.isfinite(backward).all()
        and np.max(relative) <= float(config["eigenpair_relative_residual_max"])
        and abscissa_span
        <= float(config["spectral_abscissa_span_tau_fraction_max"]) * tau_lambda
        and matched_spread
        <= float(config["matched_eigenvalue_span_tau_fraction_max"]) * tau_lambda
    )
    if not consistency:
        return _failure(
            telemetry,
            "STABILITY_SPECTRUM_INCONSISTENT",
            "eigenpair residual or three-start spectrum consistency gate failed",
        )
    rightmost = float(np.max(selected_values.real))
    stable = bool(rightmost <= -tau_lambda)
    return StabilityOutcome(
        success=True,
        code="PASS" if stable else "STABILITY_NOT_STABLE",
        stable=stable,
        rightmost_spectral_abscissa_per_s=rightmost,
        tau_lambda_per_s=tau_lambda,
        eigenvalues_per_s=selected_values,
        eigenvectors_scaled=selected_vectors,
        relative_residuals=relative,
        backward_errors_per_s=backward,
        spectral_abscissa_repeats_per_s=spectral_abscissae,
        matched_repeat_spread_per_s=matched_spread,
        telemetry=telemetry,
    )


def certify_dense_test_operator(
    matrix: np.ndarray,
    *,
    eigenpairs: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """Test-only sparse-spectrum helper; production model never uses dense full spectra."""

    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("test matrix must be square")
    operator = LinearOperator(values.shape, matvec=lambda x: values @ x, dtype=float)
    return eigs(operator, k=eigenpairs, which="LR", tol=1.0e-10, maxiter=1000)

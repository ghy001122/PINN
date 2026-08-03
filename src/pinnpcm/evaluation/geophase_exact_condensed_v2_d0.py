"""One-replay D0 mechanism audit for exact-condensed solver v2.

This module is diagnostic-only.  It replays the single frozen PR #24 failure
without changing the v1 solver, constructs explicit L1 Jacobians, freezes one
finite-difference Jv rule for a prospective v2 identity, and records a
non-voting dyadic root map.  It never casts a physics or formal-campaign vote.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping

import numpy as np
from scipy.linalg import lstsq as scipy_lstsq
from scipy.sparse.linalg import LinearOperator, lgmres
import yaml

from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as production
from pinnpcm.solvers.geophase_exact_condensed import (
    DEFAULT_EXACT_CONDENSED_SETTINGS,
    ExactAuxiliaryState,
    ExactCondensedRootFailure,
    _predict_temperature,
    _thermal_terms,
    reconstruct_exact_auxiliary_state,
    solve_exact_condensed_step,
)


SCHEMA_VERSION = "geophase_exact_condensed_v2_d0_v1"


@dataclass(frozen=True)
class D0Context:
    scientific: dict[str, Any]
    grid: Any
    fields: Any
    closure: Any
    cache: production.S2SolverCache
    old_state: production.S2State
    input_voltage_V: float
    dt_s: float


@dataclass(frozen=True)
class V1Replay:
    predictor_temperature_K: np.ndarray
    accepted_iterates_K: tuple[np.ndarray, ...]
    residual_history_inf: tuple[float, ...]
    accepted_damping_history: tuple[float, ...]
    final_temperature_K: np.ndarray
    final_original_residual: np.ndarray
    final_failed_correction_K: np.ndarray
    final_line_search_trials: tuple[dict[str, Any], ...]
    failure_code: str
    krylov_matvecs: int
    residual_evaluations: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_builtin(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return _to_builtin(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        if not np.isfinite(result):
            raise ValueError("D0 artifact contains a nonfinite numeric value")
        return result
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or isinstance(value, str):
        return value
    raise TypeError(f"unsupported D0 artifact value: {type(value).__name__}")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            _to_builtin(payload), indent=2, sort_keys=True, allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle, **{name: np.asarray(value) for name, value in arrays.items()}
        )
    temporary.replace(path)


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_to_builtin(row))


def _load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("D0 config must contain a mapping")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected D0 config schema")
    identity = payload["identity"]
    if int(identity["diagnostic_replay_count"]) != 1:
        raise ValueError("D0 permits exactly one diagnostic replay")
    if bool(identity["scientific_vote"]):
        raise ValueError("D0 cannot cast a scientific vote")
    if int(identity["formal_execution_count"]) != 0:
        raise ValueError("D0 formal execution count must remain zero")
    return payload


def verify_frozen_inputs(config: Mapping[str, Any]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in config["frozen_inputs"]:
        relative = Path(str(item["path"]))
        observed = _sha256(ROOT / relative)
        expected = str(item["sha256"])
        if observed != expected:
            raise ValueError(
                f"frozen D0 input drifted: {relative}: {observed} != {expected}"
            )
        verified.append({"path": relative.as_posix(), "sha256": observed})
    return verified


def _build_context(config: Mapping[str, Any]) -> D0Context:
    diagnostic = config["diagnostic"]
    scientific = resolved_s2_config()
    level = int(diagnostic["spatial_level"])
    grid = build_geophase_grid(scientific, spatial_level=level)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    replay_path = ROOT / str(diagnostic["source_replay_path"])
    replay = json.loads(replay_path.read_text(encoding="utf-8"))["replay"]
    old_state = _state_from_replay(replay["previous_state"])
    production.validate_s2_state(old_state, grid, closure)
    voltage = float(diagnostic["input_voltage_V"])
    if voltage != float(replay["full_input_voltage_V"]):
        raise ValueError("D0 voltage does not match the frozen replay")
    return D0Context(
        scientific=scientific,
        grid=grid,
        fields=fields,
        closure=closure,
        cache=cache,
        old_state=old_state,
        input_voltage_V=voltage,
        dt_s=float(diagnostic["dt_s"]),
    )


def _auxiliary(context: D0Context, temperature: np.ndarray) -> ExactAuxiliaryState:
    return reconstruct_exact_auxiliary_state(
        np.asarray(temperature, dtype=float).reshape(context.grid.shape),
        context.old_state,
        context.dt_s,
        context.input_voltage_V,
        grid=context.grid,
        closure=context.closure,
        fields=context.fields,
        config=context.scientific,
        cache=context.cache,
    )


def _original_residual(context: D0Context, temperature: np.ndarray) -> np.ndarray:
    return _auxiliary(context, temperature).temperature_scaled_residual.reshape(-1)


def _fixed_point_residual(
    context: D0Context, temperature: np.ndarray
) -> np.ndarray:
    candidate = np.asarray(temperature, dtype=float).reshape(context.grid.shape)
    auxiliary = _auxiliary(context, candidate)
    load, capacitance = production._circuit_parameters(context.scientific)
    mapped = production._fixed_point_map(
        auxiliary.full_vector,
        old_state=context.old_state,
        input_voltage_V=context.input_voltage_V,
        dt_s=context.dt_s,
        grid=context.grid,
        closure=context.closure,
        fields=context.fields,
        lateral_matrix=context.cache.lateral_matrix,
        thermal_linear_solver=context.cache.thermal_solver(context.dt_s),
        electrical_topology=context.cache.electrical_topology,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
        performance_timings=None,
        load_resistance_ohm=load,
        capacitance_F=capacitance,
    )
    mapped_temperature = np.asarray(mapped[: candidate.size], dtype=float)
    flat = candidate.reshape(-1)
    return (flat - mapped_temperature) / np.maximum(np.abs(flat), 1.0)


def finite_difference_base_step(vector: np.ndarray, residual: np.ndarray) -> float:
    values = np.asarray(vector, dtype=float)
    function = np.asarray(residual, dtype=float)
    return float(
        np.sqrt(np.finfo(float).eps)
        * max(1.0, float(np.max(np.abs(values))))
        / max(1.0, float(np.max(np.abs(function))))
    )


def explicit_central_jacobian(
    function: Callable[[np.ndarray], np.ndarray],
    point: np.ndarray,
    step: float,
) -> np.ndarray:
    values = np.asarray(point, dtype=float).reshape(-1)
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("explicit Jacobian step must be finite and positive")
    baseline = np.asarray(function(values), dtype=float).reshape(-1)
    jacobian = np.empty((baseline.size, values.size), dtype=float)
    for column in range(values.size):
        direction = np.zeros_like(values)
        direction[column] = step
        forward = np.asarray(function(values + direction), dtype=float).reshape(-1)
        backward = np.asarray(function(values - direction), dtype=float).reshape(-1)
        jacobian[:, column] = (forward - backward) / (2.0 * step)
    if not np.isfinite(jacobian).all():
        raise FloatingPointError("explicit central Jacobian is nonfinite")
    return jacobian


def _rank_diagnostics(jacobian: np.ndarray) -> dict[str, Any]:
    matrix = np.asarray(jacobian, dtype=float)
    left, singular, right_t = np.linalg.svd(matrix, full_matrices=False)
    tolerance = float(matrix.shape[1] * np.finfo(float).eps * singular[0])
    rank = int(np.count_nonzero(singular > tolerance))
    condition = (
        float(singular[0] / singular[-1]) if singular[-1] > 0.0 else None
    )
    return {
        "left_singular_vectors": left,
        "singular_values": singular,
        "right_singular_vectors_t": right_t,
        "smallest_right_singular_vector": right_t[-1],
        "rank_tolerance": tolerance,
        "numerical_rank": rank,
        "condition_2": condition,
    }


def _direct_corrections(
    jacobian: np.ndarray, residual: np.ndarray
) -> dict[str, Any]:
    matrix = np.asarray(jacobian, dtype=float)
    function = np.asarray(residual, dtype=float).reshape(-1)
    left, singular, right_t = np.linalg.svd(matrix, full_matrices=False)
    tolerance = float(matrix.shape[1] * np.finfo(float).eps * singular[0])
    inverse = np.where(singular > tolerance, 1.0 / singular, 0.0)
    svd_correction = right_t.T @ (inverse * (left.T @ (-function)))
    qr_correction = np.asarray(
        scipy_lstsq(matrix, -function, lapack_driver="gelsy")[0], dtype=float
    )

    def backward(correction: np.ndarray) -> float:
        return float(
            np.linalg.norm(matrix @ correction + function, ord=np.inf)
            / max(np.linalg.norm(function, ord=np.inf), np.finfo(float).tiny)
        )

    return {
        "svd_correction": svd_correction,
        "qr_correction": qr_correction,
        "svd_linear_backward_error": backward(svd_correction),
        "qr_linear_backward_error": backward(qr_correction),
        "svd_qr_relative_difference": float(
            np.linalg.norm(svd_correction - qr_correction)
            / max(np.linalg.norm(svd_correction), np.finfo(float).tiny)
        ),
    }


def _trial_metrics(
    context: D0Context,
    base_temperature: np.ndarray,
    correction: np.ndarray,
    alpha: float,
) -> dict[str, Any]:
    trial = np.asarray(base_temperature, dtype=float).reshape(-1) + float(alpha) * np.asarray(
        correction, dtype=float
    ).reshape(-1)
    row: dict[str, Any] = {
        "alpha": float(alpha),
        "finite": bool(np.isfinite(trial).all()),
        "range": False,
        "original_residual_inf": None,
        "original_merit_l2": None,
        "fp_defect_inf": None,
        "raw_thermal_residual_inf_W_per_cell": None,
        "temperature_min_K": None,
        "temperature_max_K": None,
    }
    if not row["finite"]:
        return row
    row["temperature_min_K"] = float(np.min(trial))
    row["temperature_max_K"] = float(np.max(trial))
    try:
        context.closure.validate_temperature(trial.reshape(context.grid.shape))
        auxiliary = _auxiliary(context, trial)
        original = auxiliary.temperature_scaled_residual.reshape(-1)
        fixed_point = _fixed_point_residual(context, trial)
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
        return row
    row.update(
        {
            "range": True,
            "original_residual_inf": float(np.max(np.abs(original))),
            "original_merit_l2": 0.5 * float(np.dot(original, original)),
            "fp_defect_inf": float(np.max(np.abs(fixed_point))),
            "raw_thermal_residual_inf_W_per_cell": float(
                np.max(np.abs(auxiliary.raw_thermal_residual_W_per_cell))
            ),
        }
    )
    return row


def _replay_v1_failure(context: D0Context) -> V1Replay:
    settings = DEFAULT_EXACT_CONDENSED_SETTINGS
    predictor = _predict_temperature(
        old_state=context.old_state,
        input_voltage_V=context.input_voltage_V,
        dt_s=context.dt_s,
        grid=context.grid,
        closure=context.closure,
        fields=context.fields,
        config=context.scientific,
        cache=context.cache,
        performance_timings=None,
    )
    temperature = predictor.copy()
    accepted: list[np.ndarray] = [temperature.copy()]
    residual_history: list[float] = []
    damping_history: list[float] = []
    residual_evaluations = 0
    krylov_matvecs = 0
    final_correction: np.ndarray | None = None
    final_trials: list[dict[str, Any]] = []

    def evaluate(candidate: np.ndarray) -> ExactAuxiliaryState:
        nonlocal residual_evaluations
        residual_evaluations += 1
        if residual_evaluations > settings.maximum_reduced_residual_evaluations:
            raise RuntimeError("D0 replay exceeded the frozen residual budget")
        return _auxiliary(context, candidate)

    for _iteration in range(settings.maximum_newton_iterations + 1):
        auxiliary = evaluate(temperature)
        residual = auxiliary.temperature_scaled_residual.reshape(-1)
        residual_inf = float(np.max(np.abs(residual)))
        merit = 0.5 * float(np.dot(residual, residual))
        residual_history.append(residual_inf)
        if residual_inf <= settings.reduced_residual_tolerance:
            raise RuntimeError("frozen v1 replay unexpectedly converged")
        flat = temperature.reshape(-1).copy()
        _, thermal_scale = _thermal_terms(
            temperature,
            old_state=context.old_state,
            electrical=auxiliary.electrical,
            dt_s=context.dt_s,
            grid=context.grid,
            fields=context.fields,
            lateral_matrix=context.cache.lateral_matrix,
        )

        def precondition(vector: np.ndarray) -> np.ndarray:
            return context.cache.thermal_solver(context.dt_s)(
                thermal_scale * np.asarray(vector, dtype=float)
            )

        preconditioner = LinearOperator(
            (flat.size, flat.size), matvec=precondition, dtype=float
        )
        omega = (
            np.sqrt(np.finfo(float).eps)
            * max(1.0, float(np.max(np.abs(flat))))
            / max(1.0, residual_inf)
        )

        def jacobian_vector(vector: np.ndarray) -> np.ndarray:
            nonlocal krylov_matvecs
            values = np.asarray(vector, dtype=float)
            norm = float(np.linalg.norm(values))
            if norm == 0.0:
                return np.zeros_like(values)
            if krylov_matvecs >= settings.maximum_krylov_matvecs:
                raise RuntimeError("D0 replay exceeded the frozen Krylov budget")
            krylov_matvecs += 1
            scale = omega / norm
            shifted = evaluate(flat + scale * values)
            return (
                shifted.temperature_scaled_residual.reshape(-1) - residual
            ) / scale

        remaining = settings.maximum_krylov_matvecs - krylov_matvecs
        inner_m = min(settings.lgmres_inner_m, max(1, remaining - 1))
        dynamic_maxiter = max(1, remaining // (inner_m + 1))
        correction, info = lgmres(
            LinearOperator(
                (flat.size, flat.size), matvec=jacobian_vector, dtype=float
            ),
            -residual,
            M=preconditioner,
            inner_m=inner_m,
            outer_k=settings.lgmres_outer_k,
            maxiter=dynamic_maxiter,
            rtol=settings.lgmres_rtol,
            atol=settings.lgmres_atol,
        )
        correction = np.asarray(correction, dtype=float)
        if info != 0 or not np.isfinite(correction).all():
            raise RuntimeError(f"frozen v1 replay LGMRES returned info={info}")
        final_correction = correction.copy()
        accepted_temperature: np.ndarray | None = None
        final_trials = []
        for backtrack in range(settings.maximum_line_search_backtracks + 1):
            damping = 0.5**backtrack
            if damping < settings.minimum_damping:
                break
            trial = flat + damping * correction
            try:
                trial_auxiliary = evaluate(trial)
                trial_original = (
                    trial_auxiliary.temperature_scaled_residual.reshape(-1)
                )
                trial_fixed_point = _fixed_point_residual(context, trial)
                row = {
                    "alpha": float(damping),
                    "finite": True,
                    "range": True,
                    "original_residual_inf": float(
                        np.max(np.abs(trial_original))
                    ),
                    "original_merit_l2": 0.5
                    * float(np.dot(trial_original, trial_original)),
                    "fp_defect_inf": float(
                        np.max(np.abs(trial_fixed_point))
                    ),
                    "raw_thermal_residual_inf_W_per_cell": float(
                        np.max(
                            np.abs(
                                trial_auxiliary.raw_thermal_residual_W_per_cell
                            )
                        )
                    ),
                    "temperature_min_K": float(np.min(trial)),
                    "temperature_max_K": float(np.max(trial)),
                }
            except (
                RuntimeError,
                ValueError,
                FloatingPointError,
                np.linalg.LinAlgError,
            ):
                row = {
                    "alpha": float(damping),
                    "finite": bool(np.isfinite(trial).all()),
                    "range": False,
                    "original_residual_inf": None,
                    "original_merit_l2": None,
                    "fp_defect_inf": None,
                    "raw_thermal_residual_inf_W_per_cell": None,
                    "temperature_min_K": (
                        float(np.min(trial)) if np.isfinite(trial).all() else None
                    ),
                    "temperature_max_K": (
                        float(np.max(trial)) if np.isfinite(trial).all() else None
                    ),
                }
            final_trials.append(row)
            trial_merit = row["original_merit_l2"]
            if trial_merit is not None and trial_merit <= (
                1.0 - settings.armijo_c1 * damping
            ) * merit:
                accepted_temperature = (
                    flat + damping * correction
                ).reshape(context.grid.shape)
                damping_history.append(float(damping))
                break
        if accepted_temperature is None:
            assert final_correction is not None
            return V1Replay(
                predictor_temperature_K=predictor,
                accepted_iterates_K=tuple(accepted),
                residual_history_inf=tuple(residual_history),
                accepted_damping_history=tuple(damping_history),
                final_temperature_K=temperature.copy(),
                final_original_residual=residual.copy(),
                final_failed_correction_K=final_correction,
                final_line_search_trials=tuple(final_trials),
                failure_code="ARMIJO_LINE_SEARCH_FAILURE",
                krylov_matvecs=krylov_matvecs,
                residual_evaluations=residual_evaluations,
            )
        temperature = accepted_temperature
        accepted.append(temperature.copy())
    raise RuntimeError("frozen v1 replay did not reach its expected line-search failure")


def _directional_approximation(
    function: Callable[[np.ndarray], np.ndarray],
    point: np.ndarray,
    baseline: np.ndarray,
    direction: np.ndarray,
    *,
    base_step: float,
    multiplier: float,
    scheme: str,
) -> np.ndarray:
    values = np.asarray(direction, dtype=float)
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        return np.zeros_like(np.asarray(baseline, dtype=float))
    scale = float(multiplier) * float(base_step) / norm
    if scheme == "forward":
        return (
            np.asarray(function(point + scale * values), dtype=float) - baseline
        ) / scale
    if scheme == "central":
        forward = np.asarray(function(point + scale * values), dtype=float)
        backward = np.asarray(function(point - scale * values), dtype=float)
        return (forward - backward) / (2.0 * scale)
    raise ValueError(f"unsupported Jv scheme: {scheme}")


def _jv_candidate(
    function: Callable[[np.ndarray], np.ndarray],
    point: np.ndarray,
    baseline: np.ndarray,
    explicit_jacobian: np.ndarray,
    directions: list[tuple[str, np.ndarray]],
    *,
    base_step: float,
    multiplier: float,
    scheme: str,
    gates: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[float] = []
    direction_rows: list[dict[str, Any]] = []
    for label, direction in directions:
        reference = explicit_jacobian @ direction
        approximation = _directional_approximation(
            function,
            point,
            baseline,
            direction,
            base_step=base_step,
            multiplier=multiplier,
            scheme=scheme,
        )
        error = float(
            np.linalg.norm(approximation - reference)
            / max(np.linalg.norm(reference), np.finfo(float).tiny)
        )
        errors.append(error)
        direction_rows.append(
            {"direction": label, "relative_error": error}
        )

    matvecs = 0

    def matvec(vector: np.ndarray) -> np.ndarray:
        nonlocal matvecs
        values = np.asarray(vector, dtype=float)
        if np.linalg.norm(values) == 0.0:
            return np.zeros_like(values)
        if matvecs >= 512:
            raise RuntimeError("D0 Jv correction exceeded 512 matvecs")
        matvecs += 1
        return _directional_approximation(
            function,
            point,
            baseline,
            values,
            base_step=base_step,
            multiplier=multiplier,
            scheme=scheme,
        )

    correction: np.ndarray | None = None
    info: int | None = None
    correction_error: float | None = None
    try:
        correction_raw, info_raw = lgmres(
            LinearOperator(
                (point.size, point.size), matvec=matvec, dtype=float
            ),
            -baseline,
            M=None,
            inner_m=30,
            outer_k=10,
            maxiter=max(1, 512 // 31),
            rtol=1.0e-4,
            atol=0.0,
        )
        correction = np.asarray(correction_raw, dtype=float)
        info = int(info_raw)
        if info == 0 and np.isfinite(correction).all():
            correction_error = float(
                np.linalg.norm(
                    explicit_jacobian @ correction + baseline, ord=np.inf
                )
                / max(np.linalg.norm(baseline, ord=np.inf), np.finfo(float).tiny)
            )
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
        correction = None

    median_error = float(np.median(errors))
    maximum_error = float(np.max(errors))
    passed = bool(
        median_error <= float(gates["jv_median_relative_error_max"])
        and maximum_error <= float(gates["jv_maximum_relative_error_max"])
        and correction_error is not None
        and correction_error
        <= float(gates["correction_linear_backward_error_max"])
    )
    return {
        "scheme": scheme,
        "multiplier": float(multiplier),
        "median_relative_error": median_error,
        "maximum_relative_error": maximum_error,
        "correction_linear_backward_error": correction_error,
        "lgmres_info": info,
        "matvecs": matvecs,
        "passed": passed,
        "direction_rows": direction_rows,
        "correction": correction,
    }


def select_jv_candidate(candidates: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    passing_forward = [
        item for item in candidates if item["scheme"] == "forward" and item["passed"]
    ]
    pool = passing_forward or [
        item for item in candidates if item["scheme"] == "central" and item["passed"]
    ]
    if not pool:
        return None
    selected = min(
        pool,
        key=lambda item: (
            float(item["median_relative_error"]),
            float(item["maximum_relative_error"]),
            float(item["multiplier"]),
        ),
    )
    return dict(selected)


def _dyadic_root_map(
    context: D0Context,
    dt_values_ns: list[float],
    frozen_ten_ns_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dt_ns in dt_values_ns:
        if float(dt_ns) == 10.0:
            rows.append(dict(frozen_ten_ns_result))
            continue
        started = perf_counter()
        try:
            outcome = solve_exact_condensed_step(
                context.old_state,
                input_voltage_V=context.input_voltage_V,
                dt_s=float(dt_ns) * 1.0e-9,
                grid=context.grid,
                closure=context.closure,
                fields=context.fields,
                config=context.scientific,
                cache=context.cache,
            )
        except ExactCondensedRootFailure as error:
            rows.append(
                {
                    "dt_ns": float(dt_ns),
                    "status": "VALID_FAIL",
                    "failure_code": error.code,
                    "reduced_residual_inf": error.telemetry.reduced_residual_inf,
                    "full_scaled_residual_inf": error.telemetry.full_scaled_residual_inf,
                    "full_fixed_point_defect_inf": error.telemetry.full_fixed_point_defect_inf,
                    "wall_time_s": float(perf_counter() - started),
                    "scientific_vote": False,
                }
            )
            continue
        telemetry = outcome.telemetry
        rows.append(
            {
                "dt_ns": float(dt_ns),
                "status": "PASS",
                "failure_code": None,
                "reduced_residual_inf": telemetry.reduced_residual_inf,
                "full_scaled_residual_inf": telemetry.full_scaled_residual_inf,
                "full_fixed_point_defect_inf": telemetry.full_fixed_point_defect_inf,
                "wall_time_s": float(perf_counter() - started),
                "scientific_vote": False,
            }
        )
    return rows


def run_d0_diagnostic(
    *, config_path: Path, output_root: Path
) -> dict[str, Any]:
    started = perf_counter()
    config = _load_config(config_path)
    verified = verify_frozen_inputs(config)
    context = _build_context(config)
    diagnostic = config["diagnostic"]
    gates = config["gates"]
    source_case = json.loads(
        (ROOT / str(diagnostic["source_case_path"])).read_text(encoding="utf-8")
    )

    replay = _replay_v1_failure(context)
    frozen_history = source_case["telemetry"]["reduced_residual_history_inf"]
    frozen_damping = source_case["telemetry"]["accepted_damping_history"]
    replay_match = bool(
        replay.failure_code == source_case["failure_code"]
        and np.allclose(
            replay.residual_history_inf, frozen_history, rtol=1.0e-12, atol=1.0e-15
        )
        and np.allclose(
            replay.accepted_damping_history,
            frozen_damping,
            rtol=0.0,
            atol=0.0,
        )
    )
    if not replay_match:
        raise RuntimeError("D0 replay did not reproduce the frozen PR #24 failure")

    point = replay.final_temperature_K.reshape(-1)
    original = replay.final_original_residual.reshape(-1)
    fixed_point = _fixed_point_residual(context, point)
    original_step = finite_difference_base_step(point, original)
    fixed_point_step = finite_difference_base_step(point, fixed_point)
    original_jacobian = explicit_central_jacobian(
        lambda values: _original_residual(context, values), point, original_step
    )
    fixed_point_jacobian = explicit_central_jacobian(
        lambda values: _fixed_point_residual(context, values),
        point,
        fixed_point_step,
    )
    original_rank = _rank_diagnostics(original_jacobian)
    fixed_point_rank = _rank_diagnostics(fixed_point_jacobian)
    original_direct = _direct_corrections(original_jacobian, original)
    fixed_point_direct = _direct_corrections(fixed_point_jacobian, fixed_point)
    v1_linear_backward = float(
        np.linalg.norm(
            original_jacobian @ replay.final_failed_correction_K + original,
            ord=np.inf,
        )
        / max(np.linalg.norm(original, ord=np.inf), np.finfo(float).tiny)
    )

    line_rows: list[dict[str, Any]] = []
    for name, correction in (
        ("v1_last_failed_lgmres", replay.final_failed_correction_K),
        ("fixed_point_svd_direct", fixed_point_direct["svd_correction"]),
    ):
        for exponent in diagnostic["line_profile_exponents"]:
            row = _trial_metrics(
                context, point, correction, 2.0 ** (-int(exponent))
            )
            row.update({"correction": name, "exponent": int(exponent)})
            line_rows.append(row)

    base_fp_inf = float(np.max(np.abs(fixed_point)))
    fixed_point_decrease = any(
        row["correction"] == "fixed_point_svd_direct"
        and int(row["exponent"]) <= 7
        and row["fp_defect_inf"] is not None
        and float(row["fp_defect_inf"]) < base_fp_inf
        for row in line_rows
    )
    full_rank = bool(
        fixed_point_rank["numerical_rank"] == fixed_point_jacobian.shape[1]
    )
    direct_finite = bool(
        np.isfinite(fixed_point_direct["svd_correction"]).all()
        and np.isfinite(fixed_point_direct["qr_correction"]).all()
    )

    rng = np.random.default_rng(int(diagnostic["rademacher_seed"]))
    directions: list[tuple[str, np.ndarray]] = []
    for index in range(int(diagnostic["rademacher_direction_count"])):
        direction = rng.choice((-1.0, 1.0), size=point.size)
        directions.append((f"rademacher_{index + 1}", direction))
    directions.append(("v1_failed_correction", replay.final_failed_correction_K))
    candidates: list[dict[str, Any]] = []
    if full_rank and direct_finite and fixed_point_decrease:
        function = lambda values: _fixed_point_residual(context, values)
        for scheme in ("forward", "central"):
            for multiplier in diagnostic["jv_multipliers"]:
                candidates.append(
                    _jv_candidate(
                        function,
                        point,
                        fixed_point,
                        fixed_point_jacobian,
                        directions,
                        base_step=fixed_point_step,
                        multiplier=float(multiplier),
                        scheme=scheme,
                        gates=gates,
                    )
                )
    selected = select_jv_candidate(candidates)

    root_rows: list[dict[str, Any]] = []
    if selected is not None:
        root_rows = _dyadic_root_map(
            context,
            [float(value) for value in diagnostic["dyadic_root_dt_ns"]],
            {
                "dt_ns": 10.0,
                "status": "VALID_FAIL",
                "failure_code": replay.failure_code,
                "reduced_residual_inf": float(np.max(np.abs(original))),
                "full_scaled_residual_inf": float(
                    np.max(np.abs(_auxiliary(context, point).full_scaled_residual))
                ),
                "full_fixed_point_defect_inf": None,
                "wall_time_s": 0.0,
                "scientific_vote": False,
            },
        )

    wall_time = float(perf_counter() - started)
    wall_pass = wall_time <= float(diagnostic["wall_time_s_max"])
    passed = bool(
        replay_match
        and full_rank
        and direct_finite
        and fixed_point_decrease
        and selected is not None
        and wall_pass
    )
    disposition = (
        "GO_D0_FIXED_POINT_JV_FREEZE"
        if passed
        else "D0_MECHANISM_VALID_FAIL"
    )

    jacobian_path = output_root / "d0_jacobians_and_corrections.npz"
    _atomic_npz(
        jacobian_path,
        original_jacobian=original_jacobian,
        fixed_point_jacobian=fixed_point_jacobian,
        original_singular_values=original_rank["singular_values"],
        fixed_point_singular_values=fixed_point_rank["singular_values"],
        original_smallest_right_singular_vector=original_rank[
            "smallest_right_singular_vector"
        ],
        fixed_point_smallest_right_singular_vector=fixed_point_rank[
            "smallest_right_singular_vector"
        ],
        original_svd_correction=original_direct["svd_correction"],
        original_qr_correction=original_direct["qr_correction"],
        fixed_point_svd_correction=fixed_point_direct["svd_correction"],
        fixed_point_qr_correction=fixed_point_direct["qr_correction"],
        v1_failed_correction=replay.final_failed_correction_K,
    )
    replay_path = output_root / "d0_replay_trace.json"
    _atomic_json(
        replay_path,
        {
            "schema_version": SCHEMA_VERSION,
            "source_case_id": diagnostic["source_case_id"],
            "diagnostic_replay_count": 1,
            "predictor_temperature_K": replay.predictor_temperature_K,
            "accepted_iterates_K": replay.accepted_iterates_K,
            "residual_history_inf": replay.residual_history_inf,
            "accepted_damping_history": replay.accepted_damping_history,
            "final_failed_correction_K": replay.final_failed_correction_K,
            "final_line_search_trials": replay.final_line_search_trials,
            "failure_code": replay.failure_code,
            "krylov_matvecs": replay.krylov_matvecs,
            "residual_evaluations": replay.residual_evaluations,
            "frozen_replay_match": replay_match,
        },
    )
    line_path = output_root / "d0_line_profiles.csv"
    _write_csv(line_path, line_rows)
    candidate_path = output_root / "d0_jv_candidates.csv"
    candidate_rows: list[dict[str, Any]] = []
    direction_path = output_root / "d0_jv_direction_errors.csv"
    direction_rows: list[dict[str, Any]] = []
    for item in candidates:
        candidate_rows.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"direction_rows", "correction"}
            }
        )
        for direction in item["direction_rows"]:
            direction_rows.append(
                {
                    "scheme": item["scheme"],
                    "multiplier": item["multiplier"],
                    **direction,
                }
            )
    _write_csv(candidate_path, candidate_rows)
    _write_csv(direction_path, direction_rows)
    root_path = output_root / "d0_v1_dyadic_root_map.csv"
    _write_csv(root_path, root_rows)

    selected_public = None
    if selected is not None:
        selected_public = {
            key: value
            for key, value in selected.items()
            if key not in {"direction_rows", "correction"}
        }
    largest_solvable = max(
        (float(row["dt_ns"]) for row in root_rows if row["status"] == "PASS"),
        default=None,
    )
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_id": config["identity"]["diagnostic_id"],
        "disposition": disposition,
        "validity": "valid",
        "lifecycle_state": "executed",
        "claim_status": "qualified_supported" if passed else "failed_but_informative",
        "evidence_type": config["evidence_type"],
        "scientific_vote": False,
        "formal_execution_count": 0,
        "diagnostic_replay_count": 1,
        "source_case_id": diagnostic["source_case_id"],
        "frozen_replay_match": replay_match,
        "original_residual_inf": float(np.max(np.abs(original))),
        "fixed_point_defect_inf": base_fp_inf,
        "original_jacobian": {
            "finite_difference_step_K": original_step,
            "singular_values": original_rank["singular_values"],
            "condition_2": original_rank["condition_2"],
            "numerical_rank": original_rank["numerical_rank"],
            "rank_tolerance": original_rank["rank_tolerance"],
            "smallest_right_singular_vector": original_rank[
                "smallest_right_singular_vector"
            ],
            "svd_linear_backward_error": original_direct[
                "svd_linear_backward_error"
            ],
            "qr_linear_backward_error": original_direct[
                "qr_linear_backward_error"
            ],
            "v1_lgmres_linear_backward_error": v1_linear_backward,
        },
        "fixed_point_jacobian": {
            "finite_difference_step_K": fixed_point_step,
            "singular_values": fixed_point_rank["singular_values"],
            "condition_2": fixed_point_rank["condition_2"],
            "numerical_rank": fixed_point_rank["numerical_rank"],
            "rank_tolerance": fixed_point_rank["rank_tolerance"],
            "smallest_right_singular_vector": fixed_point_rank[
                "smallest_right_singular_vector"
            ],
            "svd_linear_backward_error": fixed_point_direct[
                "svd_linear_backward_error"
            ],
            "qr_linear_backward_error": fixed_point_direct[
                "qr_linear_backward_error"
            ],
            "svd_qr_relative_difference": fixed_point_direct[
                "svd_qr_relative_difference"
            ],
        },
        "selected_jv": selected_public,
        "dyadic_root_map": {
            "executed": bool(root_rows),
            "largest_solvable_dt_ns": largest_solvable,
            "rows": root_rows,
        },
        "gates": {
            "replay_matches_frozen_failure": replay_match,
            "fixed_point_jacobian_full_rank": full_rank,
            "direct_correction_finite": direct_finite,
            "fixed_point_strict_decrease_at_or_above_1_over_128": fixed_point_decrease,
            "jv_candidate_selected": selected is not None,
            "wall_time": wall_pass,
            "all_required": passed,
        },
        "wall_time_s": wall_time,
        "verified_frozen_inputs": verified,
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha256(config_path),
        "artifacts": {
            "replay_trace": replay_path.relative_to(ROOT).as_posix(),
            "replay_trace_sha256": _sha256(replay_path),
            "jacobians_and_corrections": jacobian_path.relative_to(ROOT).as_posix(),
            "jacobians_and_corrections_sha256": _sha256(jacobian_path),
            "line_profiles": line_path.relative_to(ROOT).as_posix(),
            "line_profiles_sha256": _sha256(line_path),
            "jv_candidates": candidate_path.relative_to(ROOT).as_posix(),
            "jv_candidates_sha256": _sha256(candidate_path),
            "jv_direction_errors": direction_path.relative_to(ROOT).as_posix(),
            "jv_direction_errors_sha256": _sha256(direction_path),
            "dyadic_root_map": root_path.relative_to(ROOT).as_posix(),
            "dyadic_root_map_sha256": _sha256(root_path),
        },
    }
    _atomic_json(output_root / "d0_summary.json", summary)
    return summary


__all__ = [
    "SCHEMA_VERSION",
    "explicit_central_jacobian",
    "finite_difference_base_step",
    "run_d0_diagnostic",
    "select_jv_candidate",
    "verify_frozen_inputs",
]

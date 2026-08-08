"""Bounded nonlinear patterned-branch MVE for the frozen CC-B proxy.

This module deliberately reuses the certified CC-B equilibrium and constrained
stability implementations.  It adds only orchestration, branch switching,
pseudo-arclength continuation, and evidence recording for the preregistered
MVE identity.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile
from time import perf_counter, process_time
from typing import Any, Callable, Iterable, Mapping

import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import LinearOperator, lgmres, splu
import yaml

import pinnpcm.current_clamp.cc_b_solver as cc_b_solver_module

from pinnpcm.branchconserve.artifacts import atomic_write_npz
from pinnpcm.current_clamp.artifacts import (
    atomic_write_json,
    environment_record,
    file_sha256,
    to_builtin,
)
from pinnpcm.current_clamp.cc_b_branch_stability_transition_bracket import (
    cc_a_temperature_predictor,
    mode_metrics,
)
from pinnpcm.current_clamp.cc_b_contract import CCBContract, load_cc_b_contract
from pinnpcm.current_clamp.cc_b_model import (
    CCBEvaluation,
    CurrentClamp2DModel,
    build_cc_b_model,
)
from pinnpcm.current_clamp.cc_b_solver import (
    CCBSolveOutcome,
    prolong_temperature,
    restrict_area_average,
    solve_cc_b_equilibrium,
)
from pinnpcm.current_clamp.cc_b_stability import (
    CCBStabilityOutcome,
    CCBStabilityTelemetry,
    _apply_operator,
    centered_jv_step_size_K,
)
from pinnpcm.current_clamp.cc_b_stability_requalification import (
    RequalificationContract,
    _equilibrium_metrics,
    _run_spectrum,
    _run_step_diagnostics,
)
from pinnpcm.current_clamp.cc_b_stability_telemetry import TelemetryContract


SCHEMA_VERSION = "q2_cc_b_patterned_branch_decision_mve_v1"
TASK_ID = "Q2_CC_B_PATTERNED_BRANCH_DECISION_MVE_V1"
DUAL_PASS = "PASS_CC_B_DUAL_BRANCH_PATTERNED_MVE"
SINGLE_PASS = "PASS_CC_B_SINGLE_BRANCH_PATTERNED_MVE"
VALID_NO_GO = "NO_GO_CC_B_STABLE_PATTERNED_TRANSITION_SPAN"
NUMERIC_STOP = "STOP_CC_B_PATTERNED_MVE_NUMERICALLY_INCONCLUSIVE"
TERMINALS = frozenset({DUAL_PASS, SINGLE_PASS, VALID_NO_GO, NUMERIC_STOP})
BRANCHES = ("heating", "cooling")


class PatternedContractError(RuntimeError):
    pass


class PatternedExecutionError(RuntimeError):
    pass


class PatternedNumericalStop(RuntimeError):
    pass


@dataclass(frozen=True)
class PatternedContract:
    path: Path
    repository_root: Path
    raw: dict[str, Any]
    parent: CCBContract
    requalification: RequalificationContract
    parent_bracket_raw: dict[str, Any]

    @property
    def run_id(self) -> str:
        return str(self.raw["run_id"])

    @property
    def compact_root(self) -> Path:
        return (
            self.repository_root
            / str(self.raw["outputs"]["compact_root"])
            / self.run_id
        )

    @property
    def processed_root(self) -> Path:
        return (
            self.repository_root
            / str(self.raw["outputs"]["processed_root"])
            / self.run_id
        )


@dataclass
class EquilibriumTrace:
    rows: list[dict[str, Any]]
    best_residual: float = float("inf")
    best_scaled_temperature: np.ndarray | None = None
    last_scaled_temperature: np.ndarray | None = None

    def __call__(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        scaled = payload.pop("scaled_temperature", None)
        if scaled is not None:
            values = np.asarray(scaled, dtype=float).copy()
            self.last_scaled_temperature = values
            residual = payload.get("scaled_thermal_residual_inf")
            if residual is not None and float(residual) < self.best_residual:
                self.best_residual = float(residual)
                self.best_scaled_temperature = values.copy()
        self.rows.append(payload)


@dataclass(frozen=True)
class EquilibriumRecord:
    identity: str
    branch: str
    current_A: float
    grid: str
    temperature_K: np.ndarray
    evaluation: CCBEvaluation
    last_scaled_update_inf: float
    metrics: dict[str, Any]
    compact_manifest: Path
    processed_npz: Path


@dataclass(frozen=True)
class SpectrumRecord:
    outcome: CCBStabilityOutcome
    summary: dict[str, Any]
    root: Path


@dataclass(frozen=True)
class CriticalRecord:
    branch: str
    current_A: float
    equilibrium: EquilibriumRecord
    spectrum_k6: SpectrumRecord
    spectrum_k10: SpectrumRecord
    mode: np.ndarray
    checks: dict[str, Any]
    lower_current_A: float
    upper_current_A: float
    lower_alpha_tau: float
    upper_alpha_tau: float


@dataclass(frozen=True)
class CorrectorOutcome:
    success: bool
    code: str
    temperature_K: np.ndarray | None
    current_A: float | None
    evaluation: CCBEvaluation | None
    residual_inf: float
    update_inf: float
    nonlinear_iterations: int
    jv_evaluations: int
    full_residual_evaluations: int
    wall_time_s: float
    cpu_time_s: float
    failure_detail: str | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatternedContractError(f"{path} is not a YAML mapping")
    return payload


def _authority_path(root: Path, spec: Mapping[str, Any]) -> Path:
    path = (root / str(spec["path"])).resolve()
    if not path.is_file():
        raise PatternedContractError(f"authority file is missing: {path}")
    if file_sha256(path) != str(spec["sha256"]).lower():
        raise PatternedContractError(f"authority hash drifted: {path}")
    return path


def _assert_ancestor(root: Path, commit: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PatternedContractError(f"required merge is not an ancestor: {commit}")


def _manual_requalification_contract(
    root: Path, parent: CCBContract, path: Path
) -> RequalificationContract:
    raw = _load_yaml(path)
    telemetry_path = root / str(raw["authority"]["parent_telemetry_config"]["path"])
    telemetry_raw = _load_yaml(telemetry_path)
    telemetry = TelemetryContract(telemetry_path, root, telemetry_raw, parent)
    return RequalificationContract(path, root, raw, telemetry)


def load_patterned_contract(
    path: Path | str = Path("configs/q2_cc_b_patterned_branch_decision_mve_v1.yaml"),
    *,
    repository_root: Path | str | None = None,
) -> PatternedContract:
    root = (Path.cwd() if repository_root is None else Path(repository_root)).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    raw = _load_yaml(config_path)
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("task_id") != TASK_ID:
        raise PatternedContractError("unexpected patterned-MVE task/schema")
    authority = raw["authority"]
    _assert_ancestor(root, str(authority["pr_35_merge_sha"]))
    for name in (
        "parent_bracket_config",
        "requalification_config",
        "parent_cc_b_config",
        "pr_35_terminal",
        "pr_35_fixed_lattice",
        "pr_35_mode_metrics",
        "frozen_model",
        "frozen_stability",
    ):
        _authority_path(root, authority[name])
    terminal = json.loads(
        _authority_path(root, authority["pr_35_terminal"]).read_text(encoding="utf-8")
    )
    if (
        terminal.get("disposition")
        != authority["pr_35_terminal"]["required_disposition"]
        or terminal.get("validity") != "invalid"
        or terminal.get("scientific_vote") is not False
        or int(terminal.get("formal_execution_count", -1)) != 0
        or int(terminal.get("cc_b_matrix_launch_count", -1)) != 0
    ):
        raise PatternedContractError("PR #35 terminal identity is ineligible")
    parent_path = _authority_path(root, authority["parent_cc_b_config"])
    parent = load_cc_b_contract(parent_path, repository_root=root)
    requal_path = _authority_path(root, authority["requalification_config"])
    requalification = _manual_requalification_contract(root, parent, requal_path)
    bracket_raw = _load_yaml(_authority_path(root, authority["parent_bracket_config"]))
    if set(raw["terminal_dispositions"]) != TERMINALS:
        raise PatternedContractError("terminal vocabulary drifted")
    if (
        raw.get("scientific_vote") is not False
        or int(raw.get("formal_execution_count", -1)) != 0
        or int(raw.get("cc_b_matrix_launch_count", -1)) != 0
        or int(raw.get("patterned_mve_execution_count", -1)) != 0
    ):
        raise PatternedContractError("initial counters must be zero")
    beta = float(parent.cc_a_config["source_parameters"]["beta_per_K"])
    expected_width = 1.0 / (2.0 * beta)
    if not math.isclose(
        float(raw["branch_switch"]["transition_scale_K"]),
        expected_width,
        rel_tol=0.0,
        abs_tol=1.0e-15,
    ):
        raise PatternedContractError("transition amplitude scale drifted from beta")
    frozen = raw["stability_gates"]
    parent_stability = parent.stability
    exact = {
        "relative_ritz_residual_max": parent_stability["relative_ritz_residual_max"],
        "stable_alpha_tau_max": parent_stability["stable_alpha_tau_max"],
        "backward_error_multiplier": parent_stability["backward_error_multiplier"],
        "k6_k10_alpha_tau_difference_max": parent_stability[
            "comparison_alpha_tau_difference_max"
        ],
    }
    for key, value in exact.items():
        if float(frozen[key]) != float(value):
            raise PatternedContractError(f"frozen stability gate drifted: {key}")
    if int(raw["budget"]["workers"]) != 1 or int(raw["budget"]["blas_threads"]) != 1:
        raise PatternedContractError("patterned MVE must remain single worker/thread")
    return PatternedContract(
        config_path, root, raw, parent, requalification, bracket_raw
    )


def _current_token(current_A: float) -> str:
    text = f"{current_A * 1.0e3:.9f}".rstrip("0").rstrip(".")
    return text.replace(".", "p") + "mA"


def _relative_path(contract: PatternedContract, path: Path) -> str:
    return path.resolve().relative_to(contract.repository_root).as_posix()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_cc_a_roots(contract: PatternedContract) -> dict[str, list[dict[str, Any]]]:
    spec = contract.parent_bracket_raw["authority"]["cc_a_all_roots"]
    path = _authority_path(contract.repository_root, spec)
    rows: dict[str, list[dict[str, Any]]] = {branch: [] for branch in BRANCHES}
    for raw in _read_csv(path):
        branch = str(raw["branch"])
        if branch in rows and str(raw["certified"]).lower() == "true":
            rows[branch].append(
                {
                    "current_A": float(raw["current_A"]),
                    "temperature_K": float(raw["temperature_K"]),
                }
            )
    for branch in BRANCHES:
        rows[branch].sort(key=lambda item: item["current_A"])
        if len(rows[branch]) != 7:
            raise PatternedContractError(f"CC-A root count drifted: {branch}")
    return rows


def build_model(
    contract: PatternedContract,
    *,
    branch: str,
    current_A: float,
    spatial_level: int,
) -> CurrentClamp2DModel:
    low, high = map(float, contract.raw["scope"]["current_domain_A"])
    if branch not in BRANCHES or not low <= float(current_A) <= high:
        raise ValueError("patterned-MVE branch/current lies outside the frozen domain")
    template = build_cc_b_model(
        contract.parent,
        spatial_level=spatial_level,
        current_set_A=2.0e-4,
        branch=branch,
        defect="NOM",
    )
    return replace(template, current_set_A=float(current_A))


def reflect_y(values: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    array = np.asarray(values)
    if array.size != shape[0] * shape[1]:
        raise ValueError("reflection input has the wrong size")
    reflected = np.flip(array.reshape(shape), axis=0)
    return reflected.reshape(array.shape)


def mass_rms(vector: np.ndarray, mass: np.ndarray) -> float:
    values = np.asarray(vector)
    weights = np.asarray(mass, dtype=float).reshape(-1)
    return float(np.sqrt(np.sum(weights * np.abs(values.reshape(-1)) ** 2) / np.sum(weights)))


def normalized_mass_inner(left: np.ndarray, right: np.ndarray, mass: np.ndarray) -> complex:
    weights = np.asarray(mass, dtype=float).reshape(-1)
    return complex(
        np.sum(weights * np.conjugate(np.asarray(left).reshape(-1)) * np.asarray(right).reshape(-1))
        / np.sum(weights)
    )


def orient_transverse_mode(
    model: CurrentClamp2DModel, eigenvector: np.ndarray
) -> tuple[np.ndarray, dict[str, float]]:
    vector = np.asarray(eigenvector, dtype=complex).reshape(-1)
    mass = model.cell_capacity_J_K
    y = np.repeat(model.grid.y_centers_m, model.grid.nx)
    y_centered = y - float(np.sum(mass * y) / np.sum(mass))
    moment = np.sum(mass * y_centered * vector)
    if abs(moment) <= 1.0e-30:
        pivot = vector[int(np.argmax(np.abs(vector)))]
        phase_reference = pivot
    else:
        phase_reference = moment
    vector = vector * np.exp(-1j * np.angle(phase_reference))
    scale = mass_rms(vector, mass)
    if scale <= 0.0 or not math.isfinite(scale):
        raise ValueError("critical mode has invalid mass norm")
    vector = vector / scale
    imaginary_fraction = mass_rms(vector.imag, mass) / max(mass_rms(vector.real, mass), 1.0e-300)
    real = np.asarray(vector.real, dtype=float)
    if np.sum(mass * y_centered * real) < 0.0:
        real = -real
    real /= mass_rms(real, mass)
    reflected = reflect_y(real, model.grid.shape)
    odd_residual = mass_rms(reflected + real, mass) / max(mass_rms(real, mass), 1.0e-300)
    even_residual = mass_rms(reflected - real, mass) / max(mass_rms(real, mass), 1.0e-300)
    return real, {
        "complex_to_real_mass_ratio": imaginary_fraction,
        "reflection_odd_residual": odd_residual,
        "reflection_even_residual": even_residual,
        "transverse_first_moment": float(np.sum(mass * y_centered * real)),
    }


def patterned_amplitude_K(model: CurrentClamp2DModel, temperature_K: np.ndarray) -> float:
    temperature = np.asarray(temperature_K, dtype=float)
    difference = temperature - reflect_y(temperature, model.grid.shape)
    return 0.5 * mass_rms(difference, model.cell_capacity_J_K)


def _transition_metrics(
    contract: PatternedContract, evaluation: CCBEvaluation
) -> tuple[float, float, bool]:
    lower, upper = map(float, contract.raw["transition_gate"]["conductive_state_interval"])
    state = np.asarray(evaluation.conductive_state, dtype=float)
    mean = float(np.mean(state))
    fraction = float(np.mean((state >= lower) & (state <= upper)))
    intersects = bool(float(np.min(state)) <= upper and float(np.max(state)) >= lower)
    return mean, fraction, bool(
        intersects and fraction >= float(contract.raw["transition_gate"]["area_fraction_min"])
    )


def _equilibrium_valid(
    contract: PatternedContract,
    model: CurrentClamp2DModel,
    temperature_K: np.ndarray,
    *,
    last_update: float,
) -> tuple[bool, dict[str, Any], CCBEvaluation]:
    evaluation = model.evaluate_temperature(temperature_K)
    metrics = _equilibrium_metrics(
        model, temperature_K, last_scaled_update_inf=float(last_update)
    )
    gates = contract.raw["equilibrium_gates"]
    valid = bool(
        evaluation.finite_and_range_legal
        and evaluation.ledger.pass_all
        and metrics["scaled_thermal_residual_inf"]
        <= float(gates["thermal_scaled_cv_residual_max"])
        and metrics["last_scaled_update_inf"]
        <= float(gates["last_scaled_update_inf_max"])
        and metrics["scaled_electrical_residual_inf"]
        <= float(gates["electrical_scaled_cv_residual_max"])
        and metrics["maximum_ledger_error"]
        <= float(gates["ledger_symmetric_relative_max"])
        and float(np.min(temperature_K)) >= float(gates["temperature_K"][0])
        and float(np.max(temperature_K)) <= float(gates["temperature_K"][1])
        and evaluation.device_voltage_V
        <= float(gates["voltage_operating_envelope_max_V"])
    )
    return valid, metrics, evaluation


def _save_equilibrium(
    contract: PatternedContract,
    *,
    identity: str,
    model: CurrentClamp2DModel,
    temperature_K: np.ndarray,
    last_update: float,
    source: str,
    stage: str,
) -> EquilibriumRecord:
    valid, metrics, evaluation = _equilibrium_valid(
        contract, model, temperature_K, last_update=last_update
    )
    if not valid:
        raise PatternedExecutionError(f"equilibrium postcertification failed: {identity}")
    npz_path = contract.processed_root / "equilibria" / f"{identity}.npz"
    npz_sha = atomic_write_npz(
        npz_path,
        temperature_K=evaluation.temperature_K,
        unit_potential=evaluation.unit_potential,
        potential_V=evaluation.potential_V,
        conductive_state=evaluation.conductive_state,
        conductivity_S_m=evaluation.conductivity_S_m,
        vertical_conductance_W_m2K=evaluation.vertical_conductance_W_m2K,
        cell_joule_power_W=evaluation.cell_joule_power_W,
        thermal_residual_W=evaluation.thermal_residual_W,
        thermal_x_face_flux_W=evaluation.thermal_x_face_flux_W,
        thermal_y_face_flux_W=evaluation.thermal_y_face_flux_W,
    )
    manifest_path = contract.compact_root / "equilibria" / f"{identity}.json"
    payload = {
        "schema_version": "q2_cc_b_patterned_equilibrium_v1",
        "identity": identity,
        "task_id": TASK_ID,
        "run_id": contract.run_id,
        "stage": stage,
        "source": source,
        "branch": model.branch,
        "current_A": model.current_set_A,
        "grid": f"L{model.spatial_level}",
        "metrics": metrics,
        "npz_path": _relative_path(contract, npz_path),
        "npz_sha256": npz_sha,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "cc_b_matrix_launch_count": 0,
    }
    atomic_write_json(manifest_path, payload)
    return EquilibriumRecord(
        identity=identity,
        branch=model.branch,
        current_A=model.current_set_A,
        grid=f"L{model.spatial_level}",
        temperature_K=np.asarray(temperature_K, dtype=float).copy(),
        evaluation=evaluation,
        last_scaled_update_inf=float(last_update),
        metrics=metrics,
        compact_manifest=manifest_path,
        processed_npz=npz_path,
    )


def _solve_and_save(
    contract: PatternedContract,
    *,
    branch: str,
    current_A: float,
    spatial_level: int,
    initial_temperature_K: np.ndarray,
    identity: str,
    source: str,
    stage: str,
) -> tuple[CCBSolveOutcome, EquilibriumRecord | None]:
    model = build_model(
        contract, branch=branch, current_A=current_A, spatial_level=spatial_level
    )
    solve = solve_cc_b_equilibrium(
        model,
        initial_temperature_K=np.asarray(initial_temperature_K, dtype=float),
    )
    if not solve.success or solve.temperature_K is None:
        return solve, None
    record = _save_equilibrium(
        contract,
        identity=identity,
        model=model,
        temperature_K=solve.temperature_K,
        last_update=solve.last_scaled_update_inf,
        source=source,
        stage=stage,
    )
    return solve, record


def solve_equilibrium_with_trace(
    model: CurrentClamp2DModel,
    initial_temperature_K: np.ndarray,
    trace: EquilibriumTrace,
) -> CCBSolveOutcome:
    """Replay the unchanged production solver while observing internal calls.

    The temporary wrappers delegate every numerical operation to the original
    `_CountedResidual` and SciPy LGMRES objects.  They are restored in `finally`,
    so historical code identity and all non-diagnostic calls remain untouched.
    """

    original_counted = cc_b_solver_module._CountedResidual
    original_lgmres = cc_b_solver_module.lgmres

    class RecordedResidual(original_counted):
        def evaluate(self, z: np.ndarray) -> CCBEvaluation:
            started_wall = perf_counter()
            started_cpu = process_time()
            try:
                evaluation = super().evaluate(z)
            except Exception as exc:
                trace(
                    {
                        "event": "full_residual_evaluation",
                        "evaluation_index": self.telemetry.full_residual_evaluations,
                        "success": False,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "wall_time_s": perf_counter() - started_wall,
                        "cpu_time_s": process_time() - started_cpu,
                    }
                )
                raise
            index = self.telemetry.full_residual_evaluations
            trace(
                {
                    "event": "full_residual_evaluation",
                    "evaluation_role": (
                        "CC_A_or_base_predictor" if index == 1 else "linear_thermal_correction" if index == 2 else "Newton_Jv_or_line_search"
                    ),
                    "evaluation_index": index,
                    "success": True,
                    "scaled_temperature": np.asarray(z, dtype=float).copy(),
                    "scaled_thermal_residual_inf": evaluation.scaled_thermal_residual_inf,
                    "temperature_min_K": float(np.min(evaluation.temperature_K)),
                    "temperature_max_K": float(np.max(evaluation.temperature_K)),
                    "unit_conductance_S": evaluation.unit_conductance_S,
                    "device_voltage_V": evaluation.device_voltage_V,
                    "field_joule_power_W": evaluation.field_joule_power_W,
                    "maximum_ledger_error": max(
                        evaluation.ledger.current_error,
                        evaluation.ledger.terminal_field_power_error,
                        evaluation.ledger.field_thermal_error,
                    ),
                    "wall_time_s": perf_counter() - started_wall,
                    "cpu_time_s": process_time() - started_cpu,
                }
            )
            return evaluation

    def recorded_lgmres(*args: Any, **kwargs: Any):
        original_callback = kwargs.get("callback")

        def callback(value: np.ndarray) -> None:
            trace(
                {
                    "event": "lgmres_callback",
                    "callback_input_inf": float(np.max(np.abs(value))),
                }
            )
            if original_callback is not None:
                original_callback(value)

        kwargs["callback"] = callback
        result = original_lgmres(*args, **kwargs)
        trace(
            {
                "event": "lgmres_return",
                "info": int(result[1]),
                "update_inf": float(np.max(np.abs(result[0]))),
            }
        )
        return result

    trace(
        {
            "event": "start",
            "current_set_A": model.current_set_A,
            "branch": model.branch,
            "spatial_level": model.spatial_level,
        }
    )
    cc_b_solver_module._CountedResidual = RecordedResidual
    cc_b_solver_module.lgmres = recorded_lgmres
    try:
        outcome = cc_b_solver_module.solve_cc_b_equilibrium(
            model, initial_temperature_K=initial_temperature_K
        )
    finally:
        cc_b_solver_module._CountedResidual = original_counted
        cc_b_solver_module.lgmres = original_lgmres
    for index, residual in enumerate(outcome.telemetry.residual_inf_history):
        trace(
            {
                "event": "accepted_newton_history",
                "accepted_index": index,
                "scaled_thermal_residual_inf": residual,
                "scaled_update_inf": (
                    outcome.telemetry.update_inf_history[index - 1]
                    if index > 0 and index - 1 < len(outcome.telemetry.update_inf_history)
                    else 0.0
                ),
                "damping": (
                    outcome.telemetry.damping_history[index - 1]
                    if index > 0 and index - 1 < len(outcome.telemetry.damping_history)
                    else None
                ),
            }
        )
    trace(
        {
            "event": "finish",
            "success": outcome.success,
            "code": outcome.code,
            "failure_detail": outcome.telemetry.failure_detail,
            "nonlinear_iterations": outcome.telemetry.nonlinear_iterations,
            "lgmres_iterations": outcome.telemetry.lgmres_iterations,
            "jv_evaluations": outcome.telemetry.jv_evaluations,
            "full_residual_evaluations": outcome.telemetry.full_residual_evaluations,
        }
    )
    return outcome


def _run_certified_spectrum(
    contract: PatternedContract,
    record: EquilibriumRecord,
    *,
    eigenpairs: int,
    stage: str,
    role: str,
) -> SpectrumRecord:
    model = build_model(
        contract,
        branch=record.branch,
        current_A=record.current_A,
        spatial_level=int(record.grid[1:]),
    )
    root = (
        contract.compact_root
        / stage
        / "spectra"
        / record.identity
        / f"{role}_k{eigenpairs}"
    )
    step = _run_step_diagnostics(
        contract.requalification,
        model,
        record.temperature_K,
        root / "operator_diagnostics",
    )
    if not step["passed"]:
        raise PatternedNumericalStop(
            f"frozen operator diagnostics failed: {record.identity}"
        )
    outcome, summary = _run_spectrum(
        contract.requalification,
        model,
        record.temperature_K,
        eigenpairs=eigenpairs,
        root=root / "spectrum",
    )
    if not summary["valid"]:
        raise PatternedNumericalStop(
            f"Ritz certification failed: {record.identity}/k{eigenpairs}"
        )
    return SpectrumRecord(outcome=outcome, summary=summary, root=root)


def _spectrum_classification(outcome: CCBStabilityOutcome) -> str:
    if outcome.stable:
        return "STABLE_MARGIN_PASS"
    rho = float(np.max(outcome.absolute_backward_errors_per_s))
    alpha = float(outcome.rightmost_spectral_abscissa_per_s)
    if abs(alpha) <= 10.0 * rho:
        return "SIGN_INDETERMINATE_WITHIN_RITZ_UNCERTAINTY"
    if alpha > 0.0:
        return "POSITIVE_UNSTABLE"
    return "NEGATIVE_MARGIN_INSUFFICIENT"


def _rightmost_mode(outcome: CCBStabilityOutcome) -> tuple[complex, np.ndarray]:
    values = np.asarray(outcome.eigenvalues_per_s, dtype=complex)
    vectors = np.asarray(outcome.eigenvectors_temperature, dtype=complex)
    index = int(np.argmax(values.real))
    return complex(values[index]), vectors[:, index]


def _reflection_and_operator_checks(
    contract: PatternedContract,
    record: EquilibriumRecord,
    spectrum: SpectrumRecord,
    *,
    lower_alpha_tau: float,
    upper_alpha_tau: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    model = build_model(
        contract,
        branch=record.branch,
        current_A=record.current_A,
        spatial_level=int(record.grid[1:]),
    )
    eigenvalue, raw_mode = _rightmost_mode(spectrum.outcome)
    mode, orientation = orient_transverse_mode(model, raw_mode)
    telemetry = CCBStabilityTelemetry()
    applied = _apply_operator(
        model, record.temperature_K, mode, telemetry, call_role="critical_mode"
    )
    reflected_mode = reflect_y(mode, model.grid.shape)
    applied_reflected = _apply_operator(
        model,
        record.temperature_K,
        reflected_mode,
        telemetry,
        call_role="critical_reflected_mode",
    )
    equivariance = mass_rms(
        applied_reflected - reflect_y(applied, model.grid.shape),
        model.cell_capacity_J_K,
    ) / max(
        mass_rms(applied, model.cell_capacity_J_K),
        mass_rms(mode, model.cell_capacity_J_K) / model.tau0_s,
    )

    magnitude = float(np.max(np.abs(mode)))
    unit = mode / magnitude
    h = centered_jv_step_size_K(record.temperature_K, mode)
    plus = model.evaluate_temperature(
        record.temperature_K + h * unit.reshape(model.grid.shape)
    )
    minus = model.evaluate_temperature(
        record.temperature_K - h * unit.reshape(model.grid.shape)
    )
    static_action = magnitude * (
        plus.thermal_residual_W.reshape(-1)
        - minus.thermal_residual_W.reshape(-1)
    ) / (2.0 * h)
    dynamic_implied_static = -model.cell_capacity_J_K * applied
    action_difference = float(np.linalg.norm(static_action - dynamic_implied_static))
    action_scale = max(
        float(np.linalg.norm(static_action)),
        float(np.linalg.norm(dynamic_implied_static)),
        1.0e-300,
    )
    static_dynamic_error = action_difference / action_scale
    near_null = (
        mass_rms(applied, model.cell_capacity_J_K)
        * model.tau0_s
        / max(mass_rms(mode, model.cell_capacity_J_K), 1.0e-300)
    )

    evaluation = model.evaluate_temperature(record.temperature_K)
    power_scale = model.contract.scales.power_W / record.temperature_K.size
    analytic_fi = -2.0 * evaluation.cell_joule_power_W.reshape(-1) / (
        model.current_set_A * power_scale
    )
    epsilon = np.finfo(float).eps
    current_step = epsilon ** (1.0 / 3.0) * max(
        abs(model.current_set_A),
        float(contract.raw["branch_switch"]["current_scale_A"]),
    )
    plus_model = replace(model, current_set_A=model.current_set_A + current_step)
    minus_model = replace(model, current_set_A=model.current_set_A - current_step)
    fi_fd = (
        plus_model.evaluate_temperature(record.temperature_K).scaled_thermal_residual
        - minus_model.evaluate_temperature(record.temperature_K).scaled_thermal_residual
    ) / (2.0 * current_step)
    fi_error = float(np.linalg.norm(analytic_fi - fi_fd)) / max(
        float(np.linalg.norm(analytic_fi)),
        float(np.linalg.norm(fi_fd)),
        1.0e-300,
    )
    sorted_real = np.sort(np.asarray(spectrum.outcome.eigenvalues_per_s).real)[::-1]
    gap_tau = float((sorted_real[0] - sorted_real[1]) * model.tau0_s)
    delta_alpha = float(upper_alpha_tau - lower_alpha_tau)
    gates = contract.raw["stability_gates"]
    metrics = mode_metrics(model, eigenvalue, mode)
    checks = {
        "branch": record.branch,
        "current_A": record.current_A,
        "alpha_tau": spectrum.outcome.alpha_tau_dimensionless,
        "absolute_alpha_tau": abs(spectrum.outcome.alpha_tau_dimensionless),
        "leading_spectral_gap_tau": gap_tau,
        "operator_reflection_equivariance": equivariance,
        "static_dynamic_action_relative_error": static_dynamic_error,
        "dynamic_near_null_tau": near_null,
        "fi_analytic_fd_relative_error": fi_error,
        "bracket_delta_alpha_tau": delta_alpha,
        **orientation,
        **metrics,
    }
    checks["passed"] = bool(
        abs(spectrum.outcome.alpha_tau_dimensionless)
        <= float(gates["critical_abs_alpha_tau_max"])
        and gap_tau >= float(gates["simple_leading_gap_tau_min"])
        and equivariance <= float(gates["operator_reflection_equivariance_max"])
        and orientation["reflection_odd_residual"]
        <= float(gates["eigenmode_reflection_parity_residual_max"])
        and orientation["complex_to_real_mass_ratio"] <= 1.0e-6
        and static_dynamic_error
        <= float(gates["static_dynamic_action_relative_error_max"])
        and near_null <= float(gates["critical_abs_alpha_tau_max"])
        and fi_error
        <= float(
            contract.raw["branch_switch"]["fi_analytic_fd_relative_error_max"]
        )
        and abs(delta_alpha)
        >= float(gates["transversality_delta_alpha_tau_min"])
        and lower_alpha_tau * upper_alpha_tau < 0.0
    )
    return mode, checks


def _static_residual(
    model: CurrentClamp2DModel, scaled_temperature: np.ndarray
) -> tuple[np.ndarray, CCBEvaluation]:
    evaluation = model.evaluate_scaled_temperature(scaled_temperature)
    return np.asarray(evaluation.scaled_thermal_residual, dtype=float), evaluation


def _analytic_fi_scaled_per_A(
    model: CurrentClamp2DModel, evaluation: CCBEvaluation
) -> np.ndarray:
    power_scale = model.contract.scales.power_W / evaluation.temperature_K.size
    return -2.0 * evaluation.cell_joule_power_W.reshape(-1) / (
        model.current_set_A * power_scale
    )


def augmented_operator_jv_from_state(
    model: CurrentClamp2DModel,
    scaled_temperature: np.ndarray,
    direction_zq: np.ndarray,
    *,
    current_scale_A: float,
    oriented_mode: np.ndarray,
    transition_scale_K: float,
) -> np.ndarray:
    """Apply the frozen bordered-Newton Jacobian at one augmented state.

    The final direction component is for the dimensionless coordinate
    ``q=(I-Ic)/current_scale_A``. Budget accounting deliberately stays with
    the caller so this mathematical kernel is shared by production and its
    centered-difference regression.
    """

    z = np.asarray(scaled_temperature, dtype=float).reshape(-1)
    direction = np.asarray(direction_zq, dtype=float).reshape(-1)
    if direction.size != z.size + 1:
        raise ValueError("augmented direction has the wrong size")
    dz = direction[:-1]
    dq = float(direction[-1])
    magnitude = float(np.max(np.abs(dz)))
    if magnitude == 0.0:
        top = np.zeros_like(dz)
    else:
        unit = dz / magnitude
        h = np.finfo(float).eps ** (1.0 / 3.0) * max(
            1.0, float(np.max(np.abs(z)))
        )
        plus = model.evaluate_scaled_temperature(z + h * unit)
        minus = model.evaluate_scaled_temperature(z - h * unit)
        top = magnitude * model.conservative_thermal_jv_from_pair(
            unit, h, plus, minus
        )
    base_evaluation = model.evaluate_scaled_temperature(z)
    top = top + (
        _analytic_fi_scaled_per_A(model, base_evaluation)
        * float(current_scale_A)
        * dq
    )
    bottom = (
        normalized_mass_inner(
            oriented_mode,
            model.temperature_reference_K * dz,
            model.cell_capacity_J_K,
        ).real
        / float(transition_scale_K)
    )
    return np.concatenate([top, [bottom]])


def _thermal_preconditioner(model: CurrentClamp2DModel) -> Callable[[np.ndarray], np.ndarray]:
    factor = splu(
        (model.thermal_matrix.tocsc() + diags(model.sink_cell_W_K, format="csc")),
        permc_spec="COLAMD",
    )
    scale = model.contract.scales.power_W / (model.grid.nx * model.grid.ny)

    def apply(vector: np.ndarray) -> np.ndarray:
        return np.asarray(factor.solve(np.asarray(vector, dtype=float) * scale), dtype=float) / model.temperature_reference_K

    return apply


def solve_augmented_amplitude(
    contract: PatternedContract,
    critical: CriticalRecord,
    *,
    target_amplitude_K: float,
    orientation: int,
    initial_temperature_K: np.ndarray | None = None,
    initial_current_A: float | None = None,
) -> CorrectorOutcome:
    started_wall = perf_counter()
    started_cpu = process_time()
    cfg = contract.raw["branch_switch"]
    base_model = build_model(
        contract,
        branch=critical.branch,
        current_A=critical.current_A,
        spatial_level=1,
    )
    current_scale = float(cfg["current_scale_A"])
    width = float(cfg["transition_scale_K"])
    signed_amplitude = float(orientation) * float(target_amplitude_K)
    mode = critical.mode
    if initial_temperature_K is None:
        temperature0 = critical.equilibrium.temperature_K + signed_amplitude * mode.reshape(base_model.grid.shape)
    else:
        temperature0 = np.asarray(initial_temperature_K, dtype=float).copy()
        present = float(
            normalized_mass_inner(
                mode,
                temperature0.reshape(-1) - critical.equilibrium.temperature_K.reshape(-1),
                base_model.cell_capacity_J_K,
            ).real
        )
        temperature0 += (signed_amplitude - present) * mode.reshape(base_model.grid.shape)
    if initial_current_A is None:
        slope = critical.upper_alpha_tau - critical.lower_alpha_tau
        unstable_direction = 1.0 if slope > 0.0 else -1.0
        bracket_width = critical.upper_current_A - critical.lower_current_A
        current0 = critical.current_A + unstable_direction * bracket_width * (
            target_amplitude_K / width
        ) ** 2
    else:
        current0 = float(initial_current_A)
    z0 = base_model.scaled_from_temperature(temperature0)
    x = np.concatenate([z0, [(current0 - critical.current_A) / current_scale]])
    residual_count = 0
    jv_count = 0
    last_update = float("inf")
    last_evaluation: CCBEvaluation | None = None
    last_model: CurrentClamp2DModel | None = None

    def unpack(values: np.ndarray) -> tuple[np.ndarray, float, CurrentClamp2DModel]:
        z = np.asarray(values[:-1], dtype=float)
        current = critical.current_A + current_scale * float(values[-1])
        domain = tuple(map(float, contract.raw["scope"]["current_domain_A"]))
        if not (domain[0] <= current <= domain[1]):
            raise PatternedExecutionError("augmented current left the preregistered domain")
        return z, current, replace(base_model, current_set_A=current)

    def residual(values: np.ndarray) -> np.ndarray:
        nonlocal residual_count, last_evaluation, last_model
        if residual_count >= int(cfg["full_residual_evaluations_max"]):
            raise PatternedExecutionError("augmented full residual budget exhausted")
        residual_count += 1
        z, _current, model = unpack(values)
        top, evaluation = _static_residual(model, z)
        displacement = evaluation.temperature_K.reshape(-1) - critical.equilibrium.temperature_K.reshape(-1)
        constraint = (
            normalized_mass_inner(mode, displacement, model.cell_capacity_J_K).real
            - signed_amplitude
        ) / width
        last_evaluation = evaluation
        last_model = model
        return np.concatenate([top, [constraint]])

    try:
        current_residual = residual(x)
        residual_inf = float(np.max(np.abs(current_residual)))
        preconditioner_apply = _thermal_preconditioner(base_model)
        for iteration in range(int(cfg["nonlinear_iterations_max"]) + 1):
            if residual_inf <= float(cfg["augmented_residual_inf_max"]) and last_update <= float(cfg["augmented_update_inf_max"]):
                z, current, model = unpack(x)
                temperature = model.temperature_from_scaled(z)
                valid, _metrics, evaluation = _equilibrium_valid(
                    contract, model, temperature, last_update=last_update
                )
                if not valid:
                    raise PatternedExecutionError("augmented root failed equilibrium gates")
                amplitude_observed = normalized_mass_inner(
                    mode,
                    temperature.reshape(-1) - critical.equilibrium.temperature_K.reshape(-1),
                    model.cell_capacity_J_K,
                ).real
                if abs(amplitude_observed - signed_amplitude) / width > float(cfg["augmented_residual_inf_max"]):
                    raise PatternedExecutionError("augmented amplitude constraint failed")
                return CorrectorOutcome(
                    True,
                    "PASS",
                    temperature,
                    current,
                    evaluation,
                    residual_inf,
                    last_update,
                    iteration,
                    jv_count,
                    residual_count,
                    perf_counter() - started_wall,
                    process_time() - started_cpu,
                    None,
                )
            if iteration == int(cfg["nonlinear_iterations_max"]):
                break
            base_x = x.copy()
            base_residual = current_residual.copy()
            z, _current, model = unpack(base_x)

            def jv(vector: np.ndarray) -> np.ndarray:
                nonlocal jv_count, residual_count
                if jv_count >= int(cfg["jv_evaluations_max"]):
                    raise PatternedExecutionError("augmented Jv budget exhausted")
                jv_count += 1
                direction = np.asarray(vector, dtype=float)
                dz = direction[:-1]
                magnitude = float(np.max(np.abs(dz)))
                added_residuals = 3 if magnitude != 0.0 else 1
                if residual_count + added_residuals > int(
                    cfg["full_residual_evaluations_max"]
                ):
                    raise PatternedExecutionError(
                        "augmented full residual budget exhausted"
                    )
                residual_count += added_residuals
                return augmented_operator_jv_from_state(
                    model,
                    z,
                    direction,
                    current_scale_A=current_scale,
                    oriented_mode=mode,
                    transition_scale_K=width,
                )

            operator = LinearOperator((x.size, x.size), matvec=jv, dtype=float)
            preconditioner = LinearOperator(
                (x.size, x.size),
                matvec=lambda vector: np.concatenate(
                    [preconditioner_apply(np.asarray(vector[:-1], dtype=float)), [float(vector[-1])]]
                ),
                dtype=float,
            )
            delta, info = lgmres(
                operator,
                -base_residual,
                M=preconditioner,
                rtol=float(cfg["lgmres"]["rtol"]),
                atol=float(cfg["lgmres"]["atol"]),
                maxiter=max(1, int(cfg["jv_evaluations_max"]) - jv_count),
                inner_m=int(cfg["lgmres"]["inner_m"]),
                outer_k=int(cfg["lgmres"]["outer_k"]),
            )
            if info != 0 or not np.isfinite(delta).all():
                raise PatternedExecutionError(f"augmented LGMRES returned info={info}")
            merit0 = 0.5 * float(np.dot(base_residual, base_residual))
            accepted = False
            for damping in tuple(float(v) for v in cfg["damping_values"]):
                candidate_x = base_x + damping * delta
                try:
                    candidate_residual = residual(candidate_x)
                except Exception:
                    continue
                merit = 0.5 * float(np.dot(candidate_residual, candidate_residual))
                if merit <= (1.0 - 2.0 * float(cfg["armijo_c1"]) * damping) * merit0:
                    x = candidate_x
                    current_residual = candidate_residual
                    residual_inf = float(np.max(np.abs(candidate_residual)))
                    last_update = float(np.max(np.abs(damping * delta)))
                    accepted = True
                    break
            if not accepted:
                raise PatternedExecutionError("augmented line search found no descent")
        raise PatternedExecutionError("augmented nonlinear iteration limit reached")
    except Exception as exc:
        return CorrectorOutcome(
            False,
            "AUGMENTED_CORRECTOR_FAIL",
            None,
            None,
            last_evaluation,
            float(np.max(np.abs(current_residual))) if "current_residual" in locals() else float("inf"),
            last_update,
            int(cfg["nonlinear_iterations_max"]),
            jv_count,
            residual_count,
            perf_counter() - started_wall,
            process_time() - started_cpu,
            f"{type(exc).__name__}: {exc}",
        )


def _weighted_dot(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    return float(np.dot(a[:-1], b[:-1]) / (a.size - 1) + a[-1] * b[-1])


def _weighted_norm(vector: np.ndarray) -> float:
    return math.sqrt(max(_weighted_dot(vector, vector), 0.0))


def solve_pitchfork_toy_amplitude(amplitude: float) -> tuple[float, float]:
    """Bordered Newton sanity problem: mu*x-x**3=0, x=amplitude."""

    target = float(amplitude)
    values = np.asarray([target, target * target], dtype=float)
    for _ in range(8):
        x, mu = map(float, values)
        residual = np.asarray([mu * x - x**3, x - target], dtype=float)
        if float(np.max(np.abs(residual))) <= 1.0e-13:
            return x, mu
        jacobian = np.asarray([[mu - 3.0 * x * x, x], [1.0, 0.0]])
        values += np.linalg.solve(jacobian, -residual)
    raise RuntimeError("toy pitchfork bordered corrector did not converge")


def solve_fold_toy_arclength(
    previous: tuple[float, float],
    current: tuple[float, float],
    step: float,
) -> tuple[float, float]:
    """Pseudo-arclength sanity problem: x**2 + mu - 1 = 0."""

    y0 = np.asarray(previous, dtype=float)
    y1 = np.asarray(current, dtype=float)
    tangent = y1 - y0
    tangent /= np.linalg.norm(tangent)
    predictor = y1 + float(step) * tangent
    values = predictor.copy()
    for _ in range(12):
        x, mu = map(float, values)
        residual = np.asarray(
            [x * x + mu - 1.0, float(np.dot(values - predictor, tangent))]
        )
        if float(np.max(np.abs(residual))) <= 1.0e-13:
            return x, mu
        jacobian = np.asarray([[2.0 * x, 1.0], tangent], dtype=float)
        values += np.linalg.solve(jacobian, -residual)
    raise RuntimeError("toy fold arclength corrector did not converge")


def solve_arclength_corrector(
    contract: PatternedContract,
    *,
    branch: str,
    spatial_level: int,
    predictor: np.ndarray,
    tangent: np.ndarray,
) -> CorrectorOutcome:
    started_wall = perf_counter()
    started_cpu = process_time()
    cfg = contract.raw["branch_switch"]
    arc_cfg = contract.raw["pseudo_arclength"]
    current_scale = float(cfg["current_scale_A"])
    x = np.asarray(predictor, dtype=float).copy()
    tangent_values = np.asarray(tangent, dtype=float).copy()
    tangent_values /= max(_weighted_norm(tangent_values), 1.0e-300)
    template = build_model(
        contract,
        branch=branch,
        current_A=float(np.clip(x[-1] * current_scale, *contract.raw["scope"]["current_domain_A"])),
        spatial_level=spatial_level,
    )
    residual_count = 0
    jv_count = 0
    last_update = float("inf")
    last_evaluation: CCBEvaluation | None = None

    def unpack(values: np.ndarray) -> tuple[np.ndarray, float, CurrentClamp2DModel]:
        z = np.asarray(values[:-1], dtype=float)
        current = current_scale * float(values[-1])
        low, high = map(float, contract.raw["scope"]["current_domain_A"])
        if not low <= current <= high:
            raise PatternedExecutionError("arclength current left the preregistered domain")
        return z, current, replace(template, current_set_A=current)

    def residual(values: np.ndarray) -> np.ndarray:
        nonlocal residual_count, last_evaluation
        if residual_count >= int(cfg["full_residual_evaluations_max"]):
            raise PatternedExecutionError("arclength full residual budget exhausted")
        residual_count += 1
        z, _current, model = unpack(values)
        top, evaluation = _static_residual(model, z)
        last_evaluation = evaluation
        return np.concatenate([top, [_weighted_dot(values - predictor, tangent_values)]])

    try:
        current_residual = residual(x)
        residual_inf = float(np.max(np.abs(current_residual)))
        preconditioner_apply = _thermal_preconditioner(template)
        for iteration in range(int(cfg["nonlinear_iterations_max"]) + 1):
            if residual_inf <= float(cfg["augmented_residual_inf_max"]) and last_update <= float(cfg["augmented_update_inf_max"]):
                z, current, model = unpack(x)
                temperature = model.temperature_from_scaled(z)
                valid, _metrics, evaluation = _equilibrium_valid(
                    contract, model, temperature, last_update=last_update
                )
                if not valid:
                    raise PatternedExecutionError("arclength root failed equilibrium gates")
                return CorrectorOutcome(
                    True,
                    "PASS",
                    temperature,
                    current,
                    evaluation,
                    residual_inf,
                    last_update,
                    iteration,
                    jv_count,
                    residual_count,
                    perf_counter() - started_wall,
                    process_time() - started_cpu,
                    None,
                )
            if iteration == int(cfg["nonlinear_iterations_max"]):
                break
            base_x = x.copy()
            base_residual = current_residual.copy()
            z, _current, model = unpack(base_x)
            evaluation = model.evaluate_scaled_temperature(z)
            fi = _analytic_fi_scaled_per_A(model, evaluation) * current_scale

            def jv(vector: np.ndarray) -> np.ndarray:
                nonlocal jv_count, residual_count
                if jv_count >= int(cfg["jv_evaluations_max"]):
                    raise PatternedExecutionError("arclength Jv budget exhausted")
                jv_count += 1
                direction = np.asarray(vector, dtype=float)
                dz = direction[:-1]
                dq = float(direction[-1])
                magnitude = float(np.max(np.abs(dz)))
                if magnitude == 0.0:
                    top = np.zeros_like(dz)
                else:
                    unit = dz / magnitude
                    h = np.finfo(float).eps ** (1.0 / 3.0) * max(1.0, float(np.max(np.abs(z))))
                    if residual_count + 2 > int(cfg["full_residual_evaluations_max"]):
                        raise PatternedExecutionError("arclength full residual budget exhausted")
                    residual_count += 2
                    plus = model.evaluate_scaled_temperature(z + h * unit)
                    minus = model.evaluate_scaled_temperature(z - h * unit)
                    top = magnitude * model.conservative_thermal_jv_from_pair(unit, h, plus, minus)
                return np.concatenate([top + fi * dq, [_weighted_dot(tangent_values, direction)]])

            operator = LinearOperator((x.size, x.size), matvec=jv, dtype=float)
            preconditioner = LinearOperator(
                (x.size, x.size),
                matvec=lambda vector: np.concatenate(
                    [preconditioner_apply(np.asarray(vector[:-1], dtype=float)), [float(vector[-1])]]
                ),
                dtype=float,
            )
            delta, info = lgmres(
                operator,
                -base_residual,
                M=preconditioner,
                rtol=float(cfg["lgmres"]["rtol"]),
                atol=float(cfg["lgmres"]["atol"]),
                maxiter=max(1, int(cfg["jv_evaluations_max"]) - jv_count),
                inner_m=int(cfg["lgmres"]["inner_m"]),
                outer_k=int(cfg["lgmres"]["outer_k"]),
            )
            if info != 0 or not np.isfinite(delta).all():
                raise PatternedExecutionError(f"arclength LGMRES returned info={info}")
            merit0 = 0.5 * float(np.dot(base_residual, base_residual))
            accepted = False
            for damping in tuple(float(v) for v in cfg["damping_values"]):
                candidate = base_x + damping * delta
                try:
                    candidate_residual = residual(candidate)
                except Exception:
                    continue
                merit = 0.5 * float(np.dot(candidate_residual, candidate_residual))
                if merit <= (1.0 - 2.0 * float(cfg["armijo_c1"]) * damping) * merit0:
                    x = candidate
                    current_residual = candidate_residual
                    residual_inf = float(np.max(np.abs(candidate_residual)))
                    last_update = float(np.max(np.abs(damping * delta)))
                    accepted = True
                    break
            if not accepted:
                raise PatternedExecutionError("arclength line search found no descent")
        raise PatternedExecutionError("arclength nonlinear iteration limit reached")
    except Exception as exc:
        return CorrectorOutcome(
            False,
            "ARCLENGTH_CORRECTOR_FAIL",
            None,
            None,
            last_evaluation,
            float(np.max(np.abs(current_residual))) if "current_residual" in locals() else float("inf"),
            last_update,
            int(cfg["nonlinear_iterations_max"]),
            jv_count,
            residual_count,
            perf_counter() - started_wall,
            process_time() - started_cpu,
            f"{type(exc).__name__}: {exc}",
        )


def _corrector_to_record(
    contract: PatternedContract,
    outcome: CorrectorOutcome,
    *,
    branch: str,
    spatial_level: int,
    identity: str,
    source: str,
    stage: str,
) -> EquilibriumRecord:
    if (
        not outcome.success
        or outcome.temperature_K is None
        or outcome.current_A is None
    ):
        raise PatternedExecutionError(outcome.failure_detail or outcome.code)
    model = build_model(
        contract,
        branch=branch,
        current_A=outcome.current_A,
        spatial_level=spatial_level,
    )
    return _save_equilibrium(
        contract,
        identity=identity,
        model=model,
        temperature_K=outcome.temperature_K,
        last_update=outcome.update_inf,
        source=source,
        stage=stage,
    )


def _point_row(
    contract: PatternedContract,
    record: EquilibriumRecord,
    spectrum: SpectrumRecord,
    *,
    stage: str,
    component: str,
    sequence_index: int,
) -> dict[str, Any]:
    model = build_model(
        contract,
        branch=record.branch,
        current_A=record.current_A,
        spatial_level=int(record.grid[1:]),
    )
    state_mean, transition_fraction, transition = _transition_metrics(
        contract, record.evaluation
    )
    eigenvalue, eigenvector = _rightmost_mode(spectrum.outcome)
    spatial = mode_metrics(model, eigenvalue, eigenvector)
    return {
        "branch": record.branch,
        "component": component,
        "sequence_index": sequence_index,
        "stage": stage,
        "grid": record.grid,
        "current_A": record.current_A,
        "current_mA": record.current_A * 1.0e3,
        "temperature_mean_K": float(np.mean(record.temperature_K)),
        "temperature_min_K": float(np.min(record.temperature_K)),
        "temperature_max_K": float(np.max(record.temperature_K)),
        "device_voltage_V": record.evaluation.device_voltage_V,
        "active_area_mean_conductive_state": state_mean,
        "transition_area_fraction": transition_fraction,
        "transition_bearing": transition,
        "pattern_amplitude_K": patterned_amplitude_K(model, record.temperature_K),
        "alpha_tau": spectrum.outcome.alpha_tau_dimensionless,
        "classification": _spectrum_classification(spectrum.outcome),
        "stable": bool(spectrum.outcome.stable),
        "maximum_eta": float(np.max(spectrum.outcome.relative_ritz_residuals)),
        "maximum_ritz_residual_rate_per_s": float(
            np.max(spectrum.outcome.absolute_backward_errors_per_s)
        ),
        "uniform_mass_overlap": spatial["uniform_mass_overlap"],
        "x_gradient_energy_fraction": spatial["x_gradient_energy_fraction"],
        "y_gradient_energy_fraction": spatial["y_gradient_energy_fraction"],
        "equilibrium_manifest": _relative_path(contract, record.compact_manifest),
        "equilibrium_npz": _relative_path(contract, record.processed_npz),
        "spectrum_root": _relative_path(contract, spectrum.root),
    }


def _atomic_write_csv_lf(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    fieldnames: Iterable[str],
) -> str:
    """Write deterministic UTF-8/LF CSV bytes, then hash the final file."""

    names = list(fieldnames)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=names,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: to_builtin(row.get(name)) for name in names})
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return file_sha256(path)


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return _atomic_write_csv_lf(path, [], fieldnames=("status",))
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    normalized = [{key: row.get(key) for key in fields} for row in rows]
    return _atomic_write_csv_lf(path, normalized, fieldnames=fields)


def _initialize_run(contract: PatternedContract) -> None:
    if contract.compact_root.exists() or contract.processed_root.exists():
        raise PatternedExecutionError("patterned MVE output root is not initially empty")
    contract.compact_root.mkdir(parents=True, exist_ok=False)
    contract.processed_root.mkdir(parents=True, exist_ok=False)
    atomic_write_json(contract.compact_root / "config_snapshot.json", contract.raw)
    identity = environment_record(contract.repository_root, run_id=contract.run_id)
    identity.update(
        {
            "task_id": TASK_ID,
            "base_merge_sha": contract.raw["authority"]["pr_35_merge_sha"],
            "scientific_vote": False,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
            "ground_truth_generated": False,
            "pinn_executed": False,
        }
    )
    atomic_write_json(contract.compact_root / "identity.json", identity)


def run_stage_t(contract: PatternedContract) -> dict[str, Any]:
    started_wall = perf_counter()
    started_cpu = process_time()
    roots = _load_cc_a_roots(contract)
    initial_scalar = cc_a_temperature_predictor(roots, "heating", 3.5e-4)
    model = build_model(
        contract, branch="heating", current_A=3.5e-4, spatial_level=1
    )
    initial = np.full(model.grid.shape, initial_scalar, dtype=float)
    trace = EquilibriumTrace(rows=[])
    solve = solve_equilibrium_with_trace(model, initial, trace)
    compact_rows = []
    for index, row in enumerate(trace.rows):
        compact_rows.append({"event_index": index, **row})
    _write_rows(contract.compact_root / "telemetry_0p35.csv", compact_rows)
    summary_rows = [
        row
        for row in compact_rows
        if row.get("event")
        in {
            "start",
            "initial_guess",
            "predictor",
            "linear_thermal_correction",
            "newton_iteration",
            "lgmres_return",
            "line_search_accept",
            "finish",
        }
    ]
    atomic_write_json(contract.compact_root / "telemetry_0p35.json", summary_rows)
    arrays: dict[str, np.ndarray] = {"initial_temperature_K": initial}
    if trace.best_scaled_temperature is not None:
        arrays["best_temperature_K"] = model.temperature_from_scaled(
            trace.best_scaled_temperature
        )
    if trace.last_scaled_temperature is not None:
        arrays["last_accepted_or_evaluated_temperature_K"] = model.temperature_from_scaled(
            trace.last_scaled_temperature
        )
    atomic_write_npz(contract.processed_root / "telemetry_0p35.npz", **arrays)
    if solve.success:
        closure = "CLOSED_NONREPRODUCIBLE_OR_PRIOR_INSTRUMENTATION_EFFECT"
        if solve.temperature_K is None:
            raise PatternedExecutionError("successful telemetry replay lacks a state")
        _save_equilibrium(
            contract,
            identity="NOM_heating_0p35mA_L1_T",
            model=model,
            temperature_K=solve.temperature_K,
            last_update=solve.last_scaled_update_inf,
            source="frozen_solver_telemetry_replay",
            stage="T",
        )
    elif solve.code == "CCB_KRYLOV_BUDGET" and solve.telemetry.full_residual_evaluations == int(
        model.contract.solver["full_residual_evaluations_max"]
    ):
        closure = "CLOSED_TRUE_LOCAL_STAGNATION"
    else:
        closure = "SHARED_SOLVER_SEMANTICS_CONTAMINATED"
    payload = {
        "schema_version": "q2_cc_b_patterned_mve_stage_t_v1",
        "stage": "T",
        "closure": closure,
        "solver_success": solve.success,
        "solver_code": solve.code,
        "failure_detail": solve.telemetry.failure_detail,
        "initial_temperature_K": initial_scalar,
        "best_scaled_residual_inf": (
            trace.best_residual if math.isfinite(trace.best_residual) else None
        ),
        "nonlinear_iterations": solve.telemetry.nonlinear_iterations,
        "lgmres_iterations": solve.telemetry.lgmres_iterations,
        "jv_evaluations": solve.telemetry.jv_evaluations,
        "full_residual_evaluations": solve.telemetry.full_residual_evaluations,
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(contract.compact_root / "stage_T.json", payload)
    return payload


def _pr35_initial_temperature(
    contract: PatternedContract, branch: str, current_A: float
) -> tuple[np.ndarray, dict[str, Any]]:
    fixed = _read_csv(
        _authority_path(
            contract.repository_root,
            contract.raw["authority"]["pr_35_fixed_lattice"],
        )
    )
    for row in fixed:
        if row["branch"] == branch and math.isclose(
            float(row["current_A"]), current_A, rel_tol=0.0, abs_tol=1.0e-15
        ):
            filename = f"NOM_{branch}_{_current_token(current_A)}_L1_R1.npz"
            root = (
                contract.repository_root
                / "data/processed/q2_current_clamp_cc_b_branch_stability_transition_bracket"
                / "Q2-CC-B-BRANCH-STABILITY-TRANSITION-BRACKET-20260808-V1"
                / "equilibria"
                / filename
            )
            if not root.is_file():
                raise PatternedContractError(f"PR #35 initial field is missing: {filename}")
            observed = file_sha256(root)
            expected = str(row["equilibrium_npz_sha256"])
            if observed != expected:
                raise PatternedContractError(f"PR #35 initial field hash drifted: {filename}")
            with np.load(root, allow_pickle=False) as payload:
                temperature = np.asarray(payload["temperature_K"], dtype=float)
            return temperature, {
                "path": _relative_path(contract, root),
                "sha256": observed,
                "vote_role": "initial_guess_only",
            }
    raise PatternedContractError("PR #35 initial field row was not found")


def _recompute_boundary_point(
    contract: PatternedContract,
    *,
    branch: str,
    current_A: float,
    initial_temperature_K: np.ndarray,
    stage_role: str,
) -> tuple[EquilibriumRecord, SpectrumRecord, dict[str, Any]]:
    identity = f"NOM_{branch}_{_current_token(current_A)}_L1_B_{stage_role}"
    solve, record = _solve_and_save(
        contract,
        branch=branch,
        current_A=current_A,
        spatial_level=1,
        initial_temperature_K=initial_temperature_K,
        identity=identity,
        source="independent_recompute_pr35_initial_guess_only",
        stage="B",
    )
    if record is None:
        raise PatternedNumericalStop(
            f"boundary equilibrium failed: {branch}/{current_A}: {solve.code}"
        )
    spectrum = _run_certified_spectrum(
        contract, record, eigenpairs=6, stage="B", role=stage_role
    )
    row = _point_row(
        contract,
        record,
        spectrum,
        stage="B",
        component="uniform_boundary",
        sequence_index=0,
    )
    return record, spectrum, row


def run_stage_b(contract: PatternedContract) -> tuple[dict[str, Any], dict[str, CriticalRecord]]:
    started_wall = perf_counter()
    started_cpu = process_time()
    endpoint_rows: list[dict[str, Any]] = []
    refinement_rows: list[dict[str, Any]] = []
    critical_rows: list[dict[str, Any]] = []
    critical: dict[str, CriticalRecord] = {}
    endpoints_by_branch: dict[str, list[tuple[EquilibriumRecord, SpectrumRecord]]] = {
        branch: [] for branch in BRANCHES
    }
    for branch, current_A in contract.raw["scope"]["endpoint_execution_order"]:
        initial, source = _pr35_initial_temperature(contract, str(branch), float(current_A))
        record, spectrum, row = _recompute_boundary_point(
            contract,
            branch=str(branch),
            current_A=float(current_A),
            initial_temperature_K=initial,
            stage_role="endpoint",
        )
        row["initial_source_path"] = source["path"]
        row["initial_source_sha256"] = source["sha256"]
        endpoint_rows.append(row)
        endpoints_by_branch[str(branch)].append((record, spectrum))

    for branch in BRANCHES:
        points = sorted(endpoints_by_branch[branch], key=lambda pair: pair[0].current_A)
        low_record, low_spectrum = points[0]
        high_record, high_spectrum = points[1]
        low_alpha = float(low_spectrum.outcome.alpha_tau_dimensionless)
        high_alpha = float(high_spectrum.outcome.alpha_tau_dimensionless)
        if low_alpha * high_alpha >= 0.0:
            raise PatternedNumericalStop(f"{branch} endpoint alpha_tau does not bracket zero")
        all_points = points.copy()
        for iteration in range(1, int(contract.raw["scope"]["bisections_per_branch"]) + 1):
            midpoint = 0.5 * (low_record.current_A + high_record.current_A)
            initial = 0.5 * (low_record.temperature_K + high_record.temperature_K)
            mid_record, mid_spectrum, row = _recompute_boundary_point(
                contract,
                branch=branch,
                current_A=midpoint,
                initial_temperature_K=initial,
                stage_role=f"bisect_{iteration}",
            )
            alpha = float(mid_spectrum.outcome.alpha_tau_dimensionless)
            row.update(
                {
                    "iteration": iteration,
                    "input_lower_current_A": low_record.current_A,
                    "input_upper_current_A": high_record.current_A,
                    "alpha_zero_bracketed": True,
                    "wording": "candidate linear-stability boundary",
                }
            )
            refinement_rows.append(row)
            all_points.append((mid_record, mid_spectrum))
            if low_alpha * alpha <= 0.0:
                high_record, high_spectrum, high_alpha = mid_record, mid_spectrum, alpha
            else:
                low_record, low_spectrum, low_alpha = mid_record, mid_spectrum, alpha
        chosen_record, chosen_spectrum = min(
            all_points,
            key=lambda pair: abs(float(pair[1].outcome.alpha_tau_dimensionless)),
        )
        k10 = _run_certified_spectrum(
            contract, chosen_record, eigenpairs=10, stage="B", role="critical"
        )
        difference = abs(
            chosen_spectrum.outcome.alpha_tau_dimensionless
            - k10.outcome.alpha_tau_dimensionless
        )
        if difference > float(
            contract.raw["stability_gates"]["k6_k10_alpha_tau_difference_max"]
        ):
            raise PatternedNumericalStop(f"{branch} critical k6/k10 mismatch")
        mode, checks = _reflection_and_operator_checks(
            contract,
            chosen_record,
            chosen_spectrum,
            lower_alpha_tau=low_alpha,
            upper_alpha_tau=high_alpha,
        )
        checks["k6_k10_alpha_tau_difference"] = difference
        checks["lower_current_A"] = low_record.current_A
        checks["upper_current_A"] = high_record.current_A
        checks["wording"] = "candidate linear-stability boundary"
        critical_rows.append(checks)
        atomic_write_npz(
            contract.processed_root / "critical_modes" / f"{branch}.npz",
            temperature_K=chosen_record.temperature_K,
            critical_mode=mode,
            eigenvalues_k6_real=chosen_spectrum.outcome.eigenvalues_per_s.real,
            eigenvalues_k6_imag=chosen_spectrum.outcome.eigenvalues_per_s.imag,
        )
        if not checks["passed"]:
            raise PatternedNumericalStop(
                f"{branch} static/dynamic critical-mode semantics did not close"
            )
        critical[branch] = CriticalRecord(
            branch=branch,
            current_A=chosen_record.current_A,
            equilibrium=chosen_record,
            spectrum_k6=chosen_spectrum,
            spectrum_k10=k10,
            mode=mode,
            checks=checks,
            lower_current_A=low_record.current_A,
            upper_current_A=high_record.current_A,
            lower_alpha_tau=low_alpha,
            upper_alpha_tau=high_alpha,
        )
    _write_rows(contract.compact_root / "critical_endpoints.csv", endpoint_rows)
    _write_rows(contract.compact_root / "critical_boundaries.csv", refinement_rows)
    _write_rows(contract.compact_root / "static_dynamic_mode_checks.csv", critical_rows)
    payload = {
        "schema_version": "q2_cc_b_patterned_mve_stage_b_v1",
        "stage": "B",
        "passed": len(critical) == 2,
        "critical_currents_A": {branch: critical[branch].current_A for branch in critical},
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(contract.compact_root / "stage_B.json", payload)
    return payload, critical


def run_stage_s(
    contract: PatternedContract, critical: Mapping[str, CriticalRecord]
) -> tuple[
    dict[str, Any],
    dict[str, list[tuple[EquilibriumRecord, SpectrumRecord]]],
]:
    started_wall = perf_counter()
    started_cpu = process_time()
    width = float(contract.raw["branch_switch"]["transition_scale_K"])
    fractions = tuple(float(v) for v in contract.raw["branch_switch"]["amplitude_fractions"])
    rows: list[dict[str, Any]] = []
    seeds: dict[str, list[tuple[EquilibriumRecord, SpectrumRecord]]] = {}
    for branch in BRANCHES:
        branch_critical = critical[branch]
        previous: dict[int, CorrectorOutcome | None] = {1: None, -1: None}
        valid_pairs: list[
            tuple[
                int,
                EquilibriumRecord,
                EquilibriumRecord,
                SpectrumRecord,
                SpectrumRecord,
            ]
        ] = []
        for level, fraction in enumerate(fractions, start=1):
            amplitude = fraction * width
            records: dict[int, EquilibriumRecord] = {}
            outcomes: dict[int, CorrectorOutcome] = {}
            spectra: dict[int, SpectrumRecord] = {}
            for orientation in (1, -1):
                prior = previous[orientation]
                outcome = solve_augmented_amplitude(
                    contract,
                    branch_critical,
                    target_amplitude_K=amplitude,
                    orientation=orientation,
                    initial_temperature_K=(prior.temperature_K if prior and prior.success else None),
                    initial_current_A=(prior.current_A if prior and prior.success else None),
                )
                outcomes[orientation] = outcome
                previous[orientation] = outcome
                row = {
                    "branch": branch,
                    "amplitude_level": level,
                    "amplitude_fraction": fraction,
                    "target_amplitude_K": amplitude,
                    "orientation": orientation,
                    "corrector_success": outcome.success,
                    "current_A": outcome.current_A,
                    "residual_inf": outcome.residual_inf,
                    "update_inf": outcome.update_inf,
                    "nonlinear_iterations": outcome.nonlinear_iterations,
                    "jv_evaluations": outcome.jv_evaluations,
                    "full_residual_evaluations": outcome.full_residual_evaluations,
                    "failure_detail": outcome.failure_detail,
                    "mirror_pair_error_K": None,
                    "mirror_pair_pass": False,
                }
                rows.append(row)
                if outcome.success:
                    identity = f"{branch}_a{level}_p{'plus' if orientation > 0 else 'minus'}_L1"
                    record = _corrector_to_record(
                        contract,
                        outcome,
                        branch=branch,
                        spatial_level=1,
                        identity=identity,
                        source="augmented_amplitude_corrector",
                        stage="S",
                    )
                    records[orientation] = record
                    spectra[orientation] = _run_certified_spectrum(
                        contract, record, eigenpairs=6, stage="S", role=f"a{level}_p{orientation}"
                    )
                    row["classification"] = _spectrum_classification(
                        spectra[orientation].outcome
                    )
                    row["alpha_tau"] = spectra[orientation].outcome.alpha_tau_dimensionless
                    row["pattern_amplitude_K"] = patterned_amplitude_K(
                        build_model(contract, branch=branch, current_A=record.current_A, spatial_level=1),
                        record.temperature_K,
                    )
            if 1 in records and -1 in records:
                plus = records[1]
                minus = records[-1]
                plus_model = build_model(
                    contract, branch=branch, current_A=plus.current_A, spatial_level=1
                )
                current_match = abs(plus.current_A - minus.current_A)
                mirror_error = mass_rms(
                    minus.temperature_K.reshape(-1)
                    - reflect_y(plus.temperature_K, plus_model.grid.shape),
                    plus_model.cell_capacity_J_K,
                )
                tolerance = max(1.0e-6, 0.05 * amplitude)
                pair_pass = bool(current_match <= 1.0e-10 and mirror_error <= tolerance)
                for row in rows[-2:]:
                    row["mirror_pair_error_K"] = mirror_error
                    row["mirror_pair_pass"] = pair_pass
                if pair_pass:
                    valid_pairs.append(
                        (level, plus, minus, spectra[1], spectra[-1])
                    )
            if (
                len(valid_pairs) >= 2
                and valid_pairs[-1][0] == valid_pairs[-2][0] + 1
            ):
                break
        if len(valid_pairs) < 2 or valid_pairs[-1][0] != valid_pairs[-2][0] + 1:
            raise PatternedNumericalStop(
                f"{branch} augmented branch switching did not yield two adjacent mirror pairs"
            )
        seeds[branch] = [
            (valid_pairs[-2][1], valid_pairs[-2][3]),
            (valid_pairs[-1][1], valid_pairs[-1][3]),
        ]
    _write_rows(contract.compact_root / "augmented_branch_switch.csv", rows)
    payload = {
        "schema_version": "q2_cc_b_patterned_mve_stage_s_v1",
        "stage": "S",
        "passed": len(seeds) == 2,
        "seed_currents_A": {
            branch: [record.current_A for record, _spectrum in records]
            for branch, records in seeds.items()
        },
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(contract.compact_root / "stage_S.json", payload)
    return payload, seeds


def _state_vector(
    contract: PatternedContract, model: CurrentClamp2DModel, record: EquilibriumRecord
) -> np.ndarray:
    current_scale = float(contract.raw["branch_switch"]["current_scale_A"])
    return np.concatenate(
        [model.scaled_from_temperature(record.temperature_K), [record.current_A / current_scale]]
    )


def _candidate_pattern_row(contract: PatternedContract, row: Mapping[str, Any]) -> bool:
    width = float(contract.raw["branch_switch"]["transition_scale_K"])
    gates = contract.raw["pattern_gates"]
    return bool(
        row["stable"]
        and row["transition_bearing"]
        and float(row["pattern_amplitude_K"])
        >= float(gates["amplitude_min_fraction_of_transition_scale"]) * width
        and float(row["y_gradient_energy_fraction"])
        >= float(gates["y_gradient_energy_fraction_min"])
    )


def run_stage_c(
    contract: PatternedContract,
    seeds: Mapping[str, list[tuple[EquilibriumRecord, SpectrumRecord]]],
) -> tuple[
    dict[str, Any],
    dict[str, list[tuple[EquilibriumRecord, SpectrumRecord, dict[str, Any]]]],
]:
    started_wall = perf_counter()
    started_cpu = process_time()
    cfg = contract.raw["pseudo_arclength"]
    current_scale = float(contract.raw["branch_switch"]["current_scale_A"])
    rows: list[dict[str, Any]] = []
    all_points: dict[
        str, list[tuple[EquilibriumRecord, SpectrumRecord, dict[str, Any]]]
    ] = {}
    for branch in BRANCHES:
        seed_pairs = list(seeds[branch])
        seed_pairs.sort(key=lambda pair: patterned_amplitude_K(
            build_model(contract, branch=branch, current_A=pair[0].current_A, spatial_level=1),
            pair[0].temperature_K,
        ))
        branch_points: list[tuple[EquilibriumRecord, SpectrumRecord, dict[str, Any]]] = []
        for index, (record, spectrum) in enumerate(seed_pairs):
            row = _point_row(
                contract,
                record,
                spectrum,
                stage="C",
                component="canonical_plus_seed",
                sequence_index=index,
            )
            rows.append(row)
            branch_points.append((record, spectrum, row))
        low_record = seed_pairs[0][0]
        high_record = seed_pairs[1][0]
        low_model = build_model(
            contract, branch=branch, current_A=low_record.current_A, spatial_level=1
        )
        high_model = build_model(
            contract, branch=branch, current_A=high_record.current_A, spatial_level=1
        )
        y_low = _state_vector(contract, low_model, low_record)
        y_high = _state_vector(contract, high_model, high_record)
        directions: dict[str, dict[str, Any]] = {
            "lower_current": {
                "history": [y_high, y_low],
                "step": float(cfg["initial_step"]),
                "accepted": 0,
                "active": True,
            },
            "higher_current": {
                "history": [y_low, y_high],
                "step": float(cfg["initial_step"]),
                "accepted": 0,
                "active": True,
            },
        }
        accepted_total = len(branch_points)
        round_index = 0
        while accepted_total < int(cfg["maximum_accepted_points_per_branch"]):
            progressed = False
            for direction_name in tuple(str(v) for v in cfg["direction_order"]):
                state = directions[direction_name]
                if not state["active"]:
                    continue
                history = state["history"]
                tangent = np.asarray(history[-1]) - np.asarray(history[-2])
                tangent /= max(_weighted_norm(tangent), 1.0e-300)
                reductions = 0
                outcome: CorrectorOutcome | None = None
                step = float(state["step"])
                while reductions <= int(cfg["maximum_reductions_per_point"]):
                    predictor = np.asarray(history[-1]) + step * tangent
                    outcome = solve_arclength_corrector(
                        contract,
                        branch=branch,
                        spatial_level=1,
                        predictor=predictor,
                        tangent=tangent,
                    )
                    if outcome.success:
                        break
                    step *= float(cfg["failure_reduction_factor"])
                    reductions += 1
                    if step < float(cfg["minimum_step"]):
                        break
                if outcome is None or not outcome.success:
                    state["active"] = False
                    rows.append(
                        {
                            "branch": branch,
                            "component": direction_name,
                            "sequence_index": accepted_total,
                            "stage": "C",
                            "grid": "L1",
                            "current_A": None,
                            "current_mA": None,
                            "classification": "NOT_APPLICABLE",
                            "stable": False,
                            "transition_bearing": False,
                            "pattern_amplitude_K": None,
                            "failure_detail": (
                                outcome.failure_detail if outcome is not None else "no outcome"
                            ),
                        }
                    )
                    continue
                identity = f"{branch}_{direction_name}_arc_{state['accepted'] + 1}_L1"
                record = _corrector_to_record(
                    contract,
                    outcome,
                    branch=branch,
                    spatial_level=1,
                    identity=identity,
                    source="bounded_pseudo_arclength",
                    stage="C",
                )
                spectrum = _run_certified_spectrum(
                    contract,
                    record,
                    eigenpairs=6,
                    stage="C",
                    role=f"{direction_name}_{state['accepted'] + 1}",
                )
                row = _point_row(
                    contract,
                    record,
                    spectrum,
                    stage="C",
                    component=direction_name,
                    sequence_index=accepted_total,
                )
                row["arclength_step"] = step
                row["step_reductions"] = reductions
                row["corrector_newton_iterations"] = outcome.nonlinear_iterations
                rows.append(row)
                branch_points.append((record, spectrum, row))
                new_model = build_model(
                    contract,
                    branch=branch,
                    current_A=record.current_A,
                    spatial_level=1,
                )
                history.append(_state_vector(contract, new_model, record))
                if len(history) > 2:
                    history.pop(0)
                state["accepted"] += 1
                if outcome.nonlinear_iterations <= int(cfg["growth_newton_iteration_max"]):
                    step = min(
                        step * float(cfg["growth_factor"]),
                        float(cfg["maximum_step"]),
                    )
                state["step"] = step
                accepted_total += 1
                progressed = True
            round_index += 1
            if round_index == 1 and not all(
                int(state["accepted"]) >= 1 for state in directions.values()
            ):
                raise PatternedNumericalStop(
                    f"{branch} could not take one valid arclength step on both sides"
                )
            eligible = [row for _record, _spectrum, row in branch_points if _candidate_pattern_row(contract, row)]
            currents = sorted({float(row["current_A"]) for row in eligible})
            if (
                len(currents) >= int(cfg["required_distinct_anchor_count"])
                and currents[-1] - currents[0]
                >= float(cfg["discovery_anchor_span_A"])
            ):
                break
            all_currents = [record.current_A for record, _spectrum, _row in branch_points]
            if max(all_currents) - min(all_currents) >= float(cfg["maximum_current_span_A"]):
                break
            if not progressed or not any(bool(state["active"]) for state in directions.values()):
                break
        all_points[branch] = branch_points
    _write_rows(contract.compact_root / "patterned_branch_points.csv", rows)
    payload = {
        "schema_version": "q2_cc_b_patterned_mve_stage_c_v1",
        "stage": "C",
        "passed": True,
        "accepted_point_count_by_branch": {
            branch: len(points) for branch, points in all_points.items()
        },
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(contract.compact_root / "stage_C.json", payload)
    return payload, all_points


def field_gradient_fractions(model: CurrentClamp2DModel, field: np.ndarray) -> tuple[float, float]:
    values = np.asarray(field, dtype=float).reshape(model.grid.shape)
    dx = float(np.mean(np.diff(model.grid.x_centers_m)))
    dy = float(np.mean(np.diff(model.grid.y_centers_m)))
    ex = float(np.sum((np.diff(values, axis=1) / dx) ** 2))
    ey = float(np.sum((np.diff(values, axis=0) / dy) ** 2))
    total = ex + ey
    return (ex / total, ey / total) if total > 0.0 else (0.0, 0.0)


def _select_anchor_sources(
    contract: PatternedContract,
    points: list[tuple[EquilibriumRecord, SpectrumRecord, dict[str, Any]]],
) -> tuple[list[tuple[EquilibriumRecord, SpectrumRecord]], dict[str, Any]] | None:
    eligible = [item for item in points if _candidate_pattern_row(contract, item[2])]
    if not eligible:
        return None
    eligible.sort(key=lambda item: item[0].current_A)
    low = eligible[0]
    high = eligible[-1]
    span = high[0].current_A - low[0].current_A
    if span < float(contract.raw["pattern_gates"]["sampled_span_A_min"]):
        return None
    midpoint = 0.5 * (low[0].current_A + high[0].current_A)
    exact = [item for item in eligible if math.isclose(item[0].current_A, midpoint, rel_tol=0.0, abs_tol=1.0e-15)]
    if exact:
        mid = exact[0]
    else:
        below = max(
            (item for item in eligible if item[0].current_A < midpoint),
            key=lambda item: item[0].current_A,
        )
        above = min(
            (item for item in eligible if item[0].current_A > midpoint),
            key=lambda item: item[0].current_A,
        )
        weight = (midpoint - below[0].current_A) / (
            above[0].current_A - below[0].current_A
        )
        initial = (1.0 - weight) * below[0].temperature_K + weight * above[0].temperature_K
        solve, record = _solve_and_save(
            contract,
            branch=low[0].branch,
            current_A=midpoint,
            spatial_level=1,
            initial_temperature_K=initial,
            identity=f"{low[0].branch}_exact_mid_L1_Q",
            source="frozen_anchor_midpoint_interpolation_then_resolve",
            stage="Q",
        )
        if record is None:
            raise PatternedNumericalStop(
                f"{low[0].branch} exact midpoint equilibrium failed: {solve.code}"
            )
        spectrum = _run_certified_spectrum(
            contract, record, eigenpairs=6, stage="Q", role="exact_mid"
        )
        row = _point_row(
            contract,
            record,
            spectrum,
            stage="Q",
            component="exact_midpoint",
            sequence_index=-1,
        )
        mid = (record, spectrum, row)
    selected = [(low[0], low[1]), (mid[0], mid[1]), (high[0], high[1])]
    if len({item[0].current_A for item in selected}) != 3:
        return None
    return selected, {
        "branch": low[0].branch,
        "low_current_A": low[0].current_A,
        "mid_current_A": mid[0].current_A,
        "high_current_A": high[0].current_A,
        "sampled_span_A": span,
    }


def run_stage_q(
    contract: PatternedContract,
    points: Mapping[str, list[tuple[EquilibriumRecord, SpectrumRecord, dict[str, Any]]]],
) -> tuple[dict[str, Any], dict[str, bool], bool]:
    started_wall = perf_counter()
    started_cpu = process_time()
    selections: dict[str, list[tuple[EquilibriumRecord, SpectrumRecord]]] = {}
    selection_rows: list[dict[str, Any]] = []
    for branch in BRANCHES:
        selected = _select_anchor_sources(contract, points[branch])
        if selected is not None:
            selections[branch], summary = selected
            selection_rows.append(summary)
    atomic_write_json(
        contract.compact_root / "selected_l2_anchors.json",
        {
            "schema_version": "q2_cc_b_patterned_selected_anchors_v1",
            "frozen_before_l2": True,
            "selections": selection_rows,
        },
    )
    rows: list[dict[str, Any]] = []
    reflection_rows: list[dict[str, Any]] = []
    branch_pass = {branch: False for branch in BRANCHES}
    numerical_invalid = False
    roots = _load_cc_a_roots(contract)
    width = float(contract.raw["branch_switch"]["transition_scale_K"])
    pattern_gate = contract.raw["pattern_gates"]
    for branch in BRANCHES:
        selected = selections.get(branch)
        if selected is None:
            continue
        branch_rows: list[dict[str, Any]] = []
        for role, (l1_record, l1_k6) in zip(("low", "mid", "high"), selected, strict=True):
            try:
                l1_k10 = _run_certified_spectrum(
                    contract, l1_record, eigenpairs=10, stage="Q", role=f"{role}_L1"
                )
                l1_diff = abs(
                    l1_k6.outcome.alpha_tau_dimensionless
                    - l1_k10.outcome.alpha_tau_dimensionless
                )
                l1_model = build_model(
                    contract,
                    branch=branch,
                    current_A=l1_record.current_A,
                    spatial_level=1,
                )
                l2_model = build_model(
                    contract,
                    branch=branch,
                    current_A=l1_record.current_A,
                    spatial_level=2,
                )
                l2_initial = prolong_temperature(l1_record.temperature_K, l2_model.grid.shape)
                l2_solve, l2_record = _solve_and_save(
                    contract,
                    branch=branch,
                    current_A=l1_record.current_A,
                    spatial_level=2,
                    initial_temperature_K=l2_initial,
                    identity=f"{branch}_{role}_patterned_L2_Q",
                    source="L1_patterned_prolongation_then_resolve",
                    stage="Q",
                )
                if l2_record is None:
                    raise PatternedNumericalStop(f"{branch}/{role} L2 equilibrium failed: {l2_solve.code}")
                l2_k6 = _run_certified_spectrum(
                    contract, l2_record, eigenpairs=6, stage="Q", role=f"{role}_L2"
                )
                l2_k10 = _run_certified_spectrum(
                    contract, l2_record, eigenpairs=10, stage="Q", role=f"{role}_L2"
                )
                l2_diff = abs(
                    l2_k6.outcome.alpha_tau_dimensionless
                    - l2_k10.outcome.alpha_tau_dimensionless
                )

                l1_minus_solve, l1_minus = _solve_and_save(
                    contract,
                    branch=branch,
                    current_A=l1_record.current_A,
                    spatial_level=1,
                    initial_temperature_K=reflect_y(l1_record.temperature_K, l1_model.grid.shape),
                    identity=f"{branch}_{role}_mirror_L1_Q",
                    source="reflected_canonical_anchor_then_independent_resolve",
                    stage="Q",
                )
                l2_minus_solve, l2_minus = _solve_and_save(
                    contract,
                    branch=branch,
                    current_A=l1_record.current_A,
                    spatial_level=2,
                    initial_temperature_K=reflect_y(l2_record.temperature_K, l2_model.grid.shape),
                    identity=f"{branch}_{role}_mirror_L2_Q",
                    source="reflected_canonical_anchor_then_independent_resolve",
                    stage="Q",
                )
                if l1_minus is None or l2_minus is None:
                    raise PatternedNumericalStop(
                        f"{branch}/{role} independent reflected solve failed: "
                        f"{l1_minus_solve.code}/{l2_minus_solve.code}"
                    )

                uniform_scalar = cc_a_temperature_predictor(roots, branch, l1_record.current_A)
                uniform_solve, uniform_record = _solve_and_save(
                    contract,
                    branch=branch,
                    current_A=l1_record.current_A,
                    spatial_level=2,
                    initial_temperature_K=np.full(l2_model.grid.shape, uniform_scalar),
                    identity=f"{branch}_{role}_uniform_L2_Q",
                    source="independent_CC_A_uniform_predictor",
                    stage="Q",
                )
                if uniform_record is None:
                    raise PatternedNumericalStop(
                        f"{branch}/{role} independent uniform comparator failed: {uniform_solve.code}"
                    )
                restricted_l2 = restrict_area_average(l2_record.temperature_K, l1_model.grid.shape)
                field_discrepancy = mass_rms(
                    restricted_l2 - l1_record.temperature_K,
                    l1_model.cell_capacity_J_K,
                )
                amp_l1 = patterned_amplitude_K(l1_model, l1_record.temperature_K)
                amp_l2 = patterned_amplitude_K(l2_model, l2_record.temperature_K)
                amp_discrepancy = abs(amp_l2 - amp_l1)
                antisymmetric_l2 = l2_record.temperature_K - reflect_y(
                    l2_record.temperature_K, l2_model.grid.shape
                )
                x_fraction, y_fraction = field_gradient_fractions(
                    l2_model, antisymmetric_l2
                )
                mirror_l1 = mass_rms(
                    l1_minus.temperature_K.reshape(-1)
                    - reflect_y(l1_record.temperature_K, l1_model.grid.shape),
                    l1_model.cell_capacity_J_K,
                )
                mirror_l2 = mass_rms(
                    l2_minus.temperature_K.reshape(-1)
                    - reflect_y(l2_record.temperature_K, l2_model.grid.shape),
                    l2_model.cell_capacity_J_K,
                )
                mirror_tolerance = max(
                    field_discrepancy,
                    float(pattern_gate["mirror_relative_amplitude_tolerance"]) * amp_l2,
                )
                pattern_uniform_difference = mass_rms(
                    l2_record.temperature_K - uniform_record.temperature_K,
                    l2_model.cell_capacity_J_K,
                )
                state_mean, transition_fraction, transition = _transition_metrics(
                    contract, l2_record.evaluation
                )
                classification_equal = (
                    _spectrum_classification(l1_k6.outcome)
                    == _spectrum_classification(l2_k6.outcome)
                )
                anchor_pass = bool(
                    l1_k6.outcome.stable
                    and l2_k6.outcome.stable
                    and classification_equal
                    and l1_diff
                    <= float(contract.raw["stability_gates"]["k6_k10_alpha_tau_difference_max"])
                    and l2_diff
                    <= float(contract.raw["stability_gates"]["k6_k10_alpha_tau_difference_max"])
                    and transition
                    and amp_l2
                    >= float(pattern_gate["amplitude_min_fraction_of_transition_scale"]) * width
                    and amp_l2
                    >= float(pattern_gate["amplitude_over_grid_discrepancy_min"]) * amp_discrepancy
                    and y_fraction >= float(pattern_gate["y_gradient_energy_fraction_min"])
                    and mirror_l1 <= mirror_tolerance
                    and mirror_l2 <= mirror_tolerance
                    and pattern_uniform_difference
                    >= float(pattern_gate["amplitude_min_fraction_of_transition_scale"]) * width
                )
                row = {
                    "branch": branch,
                    "anchor_role": role,
                    "current_A": l1_record.current_A,
                    "sampled_span_A": selected[-1][0].current_A - selected[0][0].current_A,
                    "l1_k6_k10_alpha_tau_difference": l1_diff,
                    "l2_k6_k10_alpha_tau_difference": l2_diff,
                    "l1_alpha_tau": l1_k6.outcome.alpha_tau_dimensionless,
                    "l2_alpha_tau": l2_k6.outcome.alpha_tau_dimensionless,
                    "l1_l2_classification_identical": classification_equal,
                    "l2_active_area_mean_conductive_state": state_mean,
                    "l2_transition_area_fraction": transition_fraction,
                    "l2_transition_bearing": transition,
                    "l1_pattern_amplitude_K": amp_l1,
                    "l2_pattern_amplitude_K": amp_l2,
                    "amplitude_discrepancy_K": amp_discrepancy,
                    "field_discrepancy_K": field_discrepancy,
                    "x_gradient_energy_fraction": x_fraction,
                    "y_gradient_energy_fraction": y_fraction,
                    "l1_mirror_error_K": mirror_l1,
                    "l2_mirror_error_K": mirror_l2,
                    "mirror_tolerance_K": mirror_tolerance,
                    "pattern_uniform_difference_K": pattern_uniform_difference,
                    "anchor_pass": anchor_pass,
                    "failure_detail": None,
                }
                rows.append(row)
                branch_rows.append(row)
                reflection_rows.append(
                    {
                        "branch": branch,
                        "anchor_role": role,
                        "current_A": l1_record.current_A,
                        "l1_mirror_error_K": mirror_l1,
                        "l2_mirror_error_K": mirror_l2,
                        "mirror_tolerance_K": mirror_tolerance,
                        "passed": mirror_l1 <= mirror_tolerance and mirror_l2 <= mirror_tolerance,
                    }
                )
            except PatternedNumericalStop as exc:
                numerical_invalid = True
                rows.append(
                    {
                        "branch": branch,
                        "anchor_role": role,
                        "current_A": l1_record.current_A,
                        "anchor_pass": False,
                        "failure_detail": str(exc),
                    }
                )
                break
        branch_pass[branch] = bool(
            len(branch_rows) == 3
            and len({float(row["current_A"]) for row in branch_rows}) == 3
            and all(bool(row["anchor_pass"]) for row in branch_rows)
        )
    _write_rows(contract.compact_root / "l2_anchor_qualification.csv", rows)
    _write_rows(contract.compact_root / "reflection_pair_metrics.csv", reflection_rows)
    payload = {
        "schema_version": "q2_cc_b_patterned_mve_stage_q_v1",
        "stage": "Q",
        "branch_pass": branch_pass,
        "numerical_invalid": numerical_invalid,
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(contract.compact_root / "stage_Q.json", payload)
    return payload, branch_pass, numerical_invalid


def _budget_check(contract: PatternedContract, stage: str, payload: Mapping[str, Any]) -> None:
    key = {
        "T": "stage_T_wall_cap_s",
        "B": "stage_B_wall_cap_s",
        "SC": "stage_SC_wall_cap_s",
        "Q": "stage_Q_wall_cap_s",
    }[stage]
    if float(payload.get("wall_time_s", 0.0)) > float(contract.raw["budget"][key]):
        raise PatternedNumericalStop(f"{stage} exceeded its preregistered wall budget")


def _plot_bifurcation(contract: PatternedContract) -> str | None:
    source = contract.compact_root / "patterned_branch_points.csv"
    if not source.is_file():
        return None
    rows = _read_csv(source)
    usable = [row for row in rows if row.get("current_A") not in (None, "")]
    if not usable:
        return None
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 2, figsize=(10.0, 7.0), sharex=True)
    metrics = (
        ("temperature_max_K", "Tmax (K)"),
        ("temperature_mean_K", "Tmean (K)"),
        ("device_voltage_V", "Vd (V)"),
        ("pattern_amplitude_K", "A_perp (K)"),
    )
    colors = {"heating": "#c23b22", "cooling": "#2563a5"}
    for axis, (field, label) in zip(axes.reshape(-1), metrics, strict=True):
        for branch in BRANCHES:
            selected = [row for row in usable if row["branch"] == branch and row.get(field) not in (None, "")]
            selected.sort(key=lambda row: float(row["current_A"]))
            if not selected:
                continue
            x = [float(row["current_A"]) * 1.0e3 for row in selected]
            y = [float(row[field]) for row in selected]
            stable = [str(row.get("stable", "")).lower() == "true" for row in selected]
            axis.plot(x, y, color=colors[branch], linewidth=1.0, alpha=0.7)
            axis.scatter(
                x,
                y,
                c=[colors[branch] if value else "white" for value in stable],
                edgecolors=colors[branch],
                s=32,
                label=branch,
            )
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[1, 0].set_xlabel("Iset (mA)")
    axes[1, 1].set_xlabel("Iset (mA)")
    axes[0, 0].legend(frameon=False)
    figure.suptitle("Frozen current-clamp uniform/patterned MVE atlas")
    figure.tight_layout()
    path = contract.compact_root / "bifurcation_atlas.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return _relative_path(contract, path)


def _plot_critical_modes(contract: PatternedContract) -> list[str]:
    import matplotlib.pyplot as plt

    outputs: list[str] = []
    for branch in BRANCHES:
        path = contract.processed_root / "critical_modes" / f"{branch}.npz"
        if not path.is_file():
            continue
        with np.load(path, allow_pickle=False) as payload:
            temperature = np.asarray(payload["temperature_K"], dtype=float)
            mode = np.asarray(payload["critical_mode"], dtype=float).reshape(temperature.shape)
        figure, axes = plt.subplots(1, 2, figsize=(8.5, 3.6))
        im0 = axes[0].imshow(temperature, origin="lower", aspect="auto", cmap="inferno")
        axes[0].set_title(f"{branch} critical uniform T")
        figure.colorbar(im0, ax=axes[0], label="K")
        vmax = float(np.max(np.abs(mode)))
        im1 = axes[1].imshow(mode, origin="lower", aspect="auto", cmap="coolwarm", vmin=-vmax, vmax=vmax)
        axes[1].set_title("rightmost transverse mode")
        figure.colorbar(im1, ax=axes[1], label="mass-RMS normalized")
        for axis in axes:
            axis.set_xlabel("x cell (current path)")
            axis.set_ylabel("y cell (transverse)")
        figure.tight_layout()
        output = contract.compact_root / f"critical_mode_{branch}.png"
        figure.savefig(output, dpi=180)
        plt.close(figure)
        outputs.append(_relative_path(contract, output))
    return outputs


def _write_combined_manifest(contract: PatternedContract) -> None:
    artifacts: list[dict[str, Any]] = []
    for root in (contract.compact_root, contract.processed_root):
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != "artifact_manifest.json":
                artifacts.append(
                    {
                        "path": _relative_path(contract, path),
                        "bytes": path.stat().st_size,
                        "sha256": file_sha256(path),
                    }
                )
    atomic_write_json(
        contract.compact_root / "artifact_manifest.json",
        {
            "schema_version": "q2_cc_b_patterned_mve_artifact_manifest_v1",
            "run_id": contract.run_id,
            "paths_are_repository_relative": True,
            "git_stable_bytes_policy": "JSON LF and deterministic keys; CSV writer newline contract; NPZ content hash",
            "artifacts": artifacts,
        },
    )


def _write_terminal(
    contract: PatternedContract,
    *,
    disposition: str,
    detail: str,
    summary: Mapping[str, Any],
    total_wall_s: float,
    total_cpu_s: float,
) -> dict[str, Any]:
    if disposition not in TERMINALS:
        raise ValueError("unknown patterned-MVE terminal")
    valid = disposition != NUMERIC_STOP
    claim_status = (
        "qualified_supported"
        if disposition in (DUAL_PASS, SINGLE_PASS)
        else "failed_but_informative"
        if disposition == VALID_NO_GO
        else "forbidden"
    )
    payload = {
        "schema_version": "q2_cc_b_patterned_branch_decision_mve_terminal_v1",
        "task_id": TASK_ID,
        "run_id": contract.run_id,
        "disposition": disposition,
        "validity": "valid" if valid else "invalid",
        "lifecycle_state": "executed",
        "claim_status": claim_status,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "cc_b_matrix_launch_count": 0,
        "ground_truth_generated": False,
        "pinn_executed": False,
        "patterned_mve_execution_count": 1 if valid else 0,
        "detail": detail,
        "evidence_type": "literature-guided synthetic numerical digital-twin evidence",
        "allowed_claim": (
            "a locally stable transition-bearing symmetry-broken patterned branch exists within the frozen proxy"
            if disposition in (DUAL_PASS, SINGLE_PASS)
            else "the preregistered frozen search did not yield a qualifying stable patterned span"
            if disposition == VALID_NO_GO
            else "no physical interpretation; numerical semantics were not closed"
        ),
        "forbidden_claims": [
            "conductive filament formation",
            "nonlinear dynamic attractor or real ramp accessibility",
            "equivalence to the source-voltage external-RC experiment",
            "PINN, defect diagnosis, or ground-truth success",
        ],
        "summary": dict(summary),
        "runtime": {"wall_time_s": total_wall_s, "cpu_time_s": total_cpu_s},
        "finished_at_utc": _utc_now(),
    }
    atomic_write_json(contract.compact_root / "terminal.json", payload)
    atomic_write_json(contract.compact_root / "summary.json", payload)
    _write_combined_manifest(contract)
    return payload


def run_all(
    config_path: Path | str,
    *,
    repository_root: Path | str | None = None,
) -> dict[str, Any]:
    contract = load_patterned_contract(config_path, repository_root=repository_root)
    total_wall_started = perf_counter()
    total_cpu_started = process_time()
    _initialize_run(contract)
    stage_payloads: dict[str, Any] = {}
    try:
        stage_t = run_stage_t(contract)
        stage_payloads["T"] = stage_t
        _budget_check(contract, "T", stage_t)
        if stage_t["closure"] == "SHARED_SOLVER_SEMANTICS_CONTAMINATED":
            raise PatternedNumericalStop("STOP_SHARED_SOLVER_SEMANTICS_CONTAMINATED")
        stage_b, critical = run_stage_b(contract)
        stage_payloads["B"] = stage_b
        _budget_check(contract, "B", stage_b)
        stage_s, seeds = run_stage_s(contract, critical)
        stage_payloads["S"] = stage_s
        stage_c, points = run_stage_c(contract, seeds)
        stage_payloads["C"] = stage_c
        sc_wall = float(stage_s["wall_time_s"]) + float(stage_c["wall_time_s"])
        if sc_wall > float(contract.raw["budget"]["stage_SC_wall_cap_s"]):
            raise PatternedNumericalStop("S/C exceeded its preregistered wall budget")
        any_candidate = any(
            any(_candidate_pattern_row(contract, row) for _record, _spectrum, row in branch_points)
            for branch_points in points.values()
        )
        if any_candidate:
            stage_q, branch_pass, numerical_invalid = run_stage_q(contract, points)
            stage_payloads["Q"] = stage_q
            _budget_check(contract, "Q", stage_q)
            if numerical_invalid:
                raise PatternedNumericalStop("one or more L2 qualification paths were numerically invalid")
        else:
            branch_pass = {branch: False for branch in BRANCHES}
            stage_payloads["Q"] = {"stage": "Q", "status": "SKIPPED_NO_L1_CANDIDATE"}
        if all(branch_pass.values()):
            disposition = DUAL_PASS
            detail = "both frozen major branches have three L2-qualified stable patterned transition anchors"
        elif any(branch_pass.values()):
            disposition = SINGLE_PASS
            detail = "only one frozen major branch has a qualified stable patterned transition span"
        else:
            disposition = VALID_NO_GO
            detail = "the bounded valid nonlinear search did not produce a qualifying stable patterned transition span"
        figure = _plot_bifurcation(contract)
        modes = _plot_critical_modes(contract)
        total_wall = perf_counter() - total_wall_started
        total_cpu = process_time() - total_cpu_started
        summary = {
            "stage_payloads": stage_payloads,
            "branch_pass": branch_pass,
            "bifurcation_figure": figure,
            "critical_mode_figures": modes,
        }
        return _write_terminal(
            contract,
            disposition=disposition,
            detail=detail,
            summary=summary,
            total_wall_s=total_wall,
            total_cpu_s=total_cpu,
        )
    except PatternedNumericalStop as exc:
        total_wall = perf_counter() - total_wall_started
        total_cpu = process_time() - total_cpu_started
        return _write_terminal(
            contract,
            disposition=NUMERIC_STOP,
            detail=str(exc),
            summary={"stage_payloads": stage_payloads, "failure_type": type(exc).__name__},
            total_wall_s=total_wall,
            total_cpu_s=total_cpu,
        )
    except Exception as exc:
        total_wall = perf_counter() - total_wall_started
        total_cpu = process_time() - total_cpu_started
        return _write_terminal(
            contract,
            disposition=NUMERIC_STOP,
            detail=f"artifact/runner execution failed: {type(exc).__name__}: {exc}",
            summary={"stage_payloads": stage_payloads, "failure_type": type(exc).__name__},
            total_wall_s=total_wall,
            total_cpu_s=total_cpu,
        )

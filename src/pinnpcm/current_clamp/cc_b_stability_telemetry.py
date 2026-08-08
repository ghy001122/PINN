"""Versioned, non-voting telemetry closure for the invalid CC-B L1/k6 pilot."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.branchconserve.artifacts import atomic_write_npz
from pinnpcm.current_clamp.artifacts import (
    atomic_write_csv,
    atomic_write_json,
    environment_record,
    file_sha256,
)
from pinnpcm.current_clamp.cc_b_artifacts import save_cc_b_equilibrium
from pinnpcm.current_clamp.cc_b_contract import CCBContract, load_cc_b_contract
from pinnpcm.current_clamp.cc_b_model import CurrentClamp2DModel, build_cc_b_model
from pinnpcm.current_clamp.cc_b_solver import CCBSolveOutcome, solve_cc_b_equilibrium
from pinnpcm.current_clamp.cc_b_stability import (
    CCBStabilityOutcome,
    CCBStabilityTelemetry,
    _apply_operator,
    _deterministic_vector,
    certify_current_clamp_stability,
)
from pinnpcm.current_clamp.source_oracle import discover_roots
from pinnpcm.evaluation.q2_qiu_source_oracle import OracleParameters


SCHEMA_VERSION = "q2_cc_b_stability_telemetry_closure_v1"
TASK_ID = "Q2_CC_B_STABILITY_TELEMETRY_CLOSURE_V1"
REVIEW_REVISION = "20260808-R1"
TERMINAL_DISPOSITIONS = frozenset(
    {
        "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE",
        "STOP_CC_B_STABILITY_BUDGET_NOT_ADMISSIBLE",
        "STOP_CC_B_STABILITY_SEMANTICS_NOT_CLOSED",
        "INVALID_CC_B_STABILITY_TELEMETRY_EXECUTION",
    }
)
GATE_STATUSES = frozenset({"PASS", "FAIL", "INVALID", "SKIPPED_NOT_ELIGIBLE"})
SPECTRUM_CLASSES = frozenset(
    {
        "STABLE_MARGIN_PASS",
        "NEGATIVE_MARGIN_INSUFFICIENT",
        "POSITIVE_UNSTABLE",
        "SIGN_INDETERMINATE_WITHIN_RITZ_UNCERTAINTY",
        "NOT_APPLICABLE",
    }
)

GATE_METADATA: dict[str, tuple[str, str]] = {
    "INPUT_IDENTITY": ("telemetry_v1_preregistered", "execution_validity"),
    "EQUILIBRIUM_INPUT_INTEGRITY": (
        "parent_cc_b_contract",
        "execution_validity",
    ),
    "MASS_MATRIX_VALIDITY": ("parent_cc_b_contract", "execution_validity"),
    "ELECTRICAL_SUBSOLVE": ("parent_cc_b_contract", "execution_validity"),
    "FIXED_CURRENT_CONSTRAINT": ("parent_cc_b_contract", "execution_validity"),
    "JV_FINITE": ("parent_cc_b_contract", "execution_validity"),
    "JV_REPEATABILITY": ("telemetry_v1_preregistered", "execution_validity"),
    "JV_HOMOGENEITY": ("telemetry_v1_preregistered", "nonvoting_diagnostic"),
    "JV_ADDITIVITY": ("telemetry_v1_preregistered", "nonvoting_diagnostic"),
    "JV_STEP_SIZE_CONSISTENCY": (
        "parent_cc_b_contract",
        "execution_validity",
    ),
    "OPERATOR_UNIT_AND_SIGN": (
        "telemetry_v1_preregistered",
        "execution_validity",
    ),
    "EIGENSOLVER_RETURN": ("parent_cc_b_contract", "execution_validity"),
    "RITZ_COUNT": ("parent_cc_b_contract", "execution_validity"),
    "RITZ_FINITE": ("parent_cc_b_contract", "execution_validity"),
    "RITZ_RELATIVE_RESIDUAL": (
        "parent_cc_b_contract",
        "physical_stability",
    ),
    "RIGHTMOST_ORDERING": ("parent_cc_b_contract", "execution_validity"),
    "K6_K10_CONSISTENCY": (
        "telemetry_v1_preregistered",
        "nonvoting_diagnostic",
    ),
    "ARTIFACT_CANONICALIZATION": (
        "telemetry_v1_preregistered",
        "execution_validity",
    ),
    "TERMINAL_AGGREGATION": (
        "telemetry_v1_preregistered",
        "execution_validity",
    ),
}

JVCALL_FIELDS = (
    "call_index",
    "call_role",
    "perturbation_method",
    "step_multiplier",
    "step_size_K",
    "input_inf_norm",
    "output_inf_norm_per_s",
    "plus_temperature_min_K",
    "plus_temperature_max_K",
    "minus_temperature_min_K",
    "minus_temperature_max_K",
    "unit_bias_electrical_solve_count",
    "electrical_solver_type",
    "electrical_iterations",
    "plus_electrical_residual",
    "minus_electrical_residual",
    "plus_electrical_wall_s",
    "minus_electrical_wall_s",
    "plus_electrical_cpu_s",
    "minus_electrical_cpu_s",
    "plus_G_hat_S",
    "minus_G_hat_S",
    "plus_Vd_V",
    "minus_Vd_V",
    "delta_Vd_V",
    "plus_normalized_current_error",
    "minus_normalized_current_error",
    "normalized_delta_I_cond",
    "finite",
    "operator_wall_s",
    "operator_cpu_s",
    "exception_type",
    "exception_message",
)


class TelemetryContractError(RuntimeError):
    pass


class TelemetryArtifactError(RuntimeError):
    pass


class TelemetryBudgetStop(RuntimeError):
    pass


class TelemetrySemanticsStop(RuntimeError):
    pass


@dataclass(frozen=True)
class TelemetryContract:
    path: Path
    repository_root: Path
    raw: dict[str, Any]
    parent: CCBContract

    @property
    def campaign(self) -> str:
        return str(self.raw["campaign"])

    @property
    def target(self) -> dict[str, Any]:
        return self.raw["target"]

    @property
    def compact_root(self) -> Path:
        return self.repository_root / str(self.raw["outputs"]["compact_root"])

    @property
    def processed_root(self) -> Path:
        return self.repository_root / str(self.raw["outputs"]["processed_root"])


class GateBook:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        for name, (origin, role) in GATE_METADATA.items():
            self._records[name] = {
                "name": name,
                "status": "SKIPPED_NOT_ELIGIBLE",
                "gate_origin": origin,
                "vote_role": role,
                "detail": "not reached",
                "metrics": {},
            }

    def set(
        self,
        name: str,
        status: str,
        detail: str,
        *,
        metrics: Mapping[str, Any] | None = None,
    ) -> None:
        if name not in self._records:
            raise KeyError(f"unregistered telemetry gate: {name}")
        if status not in GATE_STATUSES:
            raise ValueError(f"invalid telemetry gate status: {status}")
        record = self._records[name]
        record["status"] = status
        record["detail"] = str(detail)
        record["metrics"] = dict(metrics or {})

    def get(self, name: str) -> dict[str, Any]:
        return dict(self._records[name])

    def rows(self) -> list[dict[str, Any]]:
        return [dict(self._records[name]) for name in GATE_METADATA]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TelemetryContractError(f"cannot read telemetry YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise TelemetryContractError("telemetry config must contain a mapping")
    return payload


def _authority_file(root: Path, spec: Mapping[str, Any], *, optional: bool = False) -> Path | None:
    path = (root / str(spec["path"])).resolve()
    if not path.is_file():
        if optional:
            return None
        raise TelemetryContractError(f"authority file is missing: {path}")
    if file_sha256(path) != str(spec["sha256"]).lower():
        raise TelemetryContractError(f"authority hash drift: {path}")
    return path


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _assert_base_ancestor(root: Path, expected: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", expected, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TelemetryContractError(
            "the verified PR #32 merge is not an ancestor of the execution code"
        )


def load_telemetry_contract(
    path: Path | str = Path("configs/q2_cc_b_stability_telemetry_closure_v1.yaml"),
    *,
    repository_root: Path | str | None = None,
) -> TelemetryContract:
    root = (Path.cwd() if repository_root is None else Path(repository_root)).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    raw = _load_yaml(config_path)
    if (
        raw.get("schema_version") != SCHEMA_VERSION
        or raw.get("task_id") != TASK_ID
        or raw.get("review_revision") != REVIEW_REVISION
    ):
        raise TelemetryContractError("unexpected telemetry task/schema/review identity")
    if raw.get("reproduction_semantics") != "merged-PR32_numerical-contract_reproduction":
        raise TelemetryContractError("reproduction semantics drifted")
    target = raw.get("target", {})
    expected_target = {
        "defect": "NOM",
        "branch": "heating",
        "current_A": 4.0e-4,
        "grid": "L1",
        "spatial_level": 1,
        "eigenpairs": 6,
        "only_case": True,
    }
    if target != expected_target:
        raise TelemetryContractError("the sole L1/k6 replay target drifted")
    if set(raw.get("terminal_dispositions", ())) != TERMINAL_DISPOSITIONS:
        raise TelemetryContractError("terminal disposition vocabulary drifted")
    forbidden = set(raw.get("forbidden_execution", ()))
    required_forbidden = {
        "L2_k6",
        "L2_k10",
        "k6_k10_consistency",
        "uniform_gate",
        "36_case_matrix",
        "CC_C",
        "PINN",
        "inverse",
    }
    if not required_forbidden.issubset(forbidden):
        raise TelemetryContractError("a prohibited downstream execution disappeared")
    authority = raw["authority"]
    parent_config = _authority_file(root, authority["parent_config"])
    terminal_path = _authority_file(root, authority["parent_terminal"])
    smoke_path = _authority_file(root, authority["parent_smoke_summary"])
    _authority_file(root, authority["parent_l1_compact"])
    _authority_file(root, authority["parent_l1_npz"], optional=True)
    assert parent_config is not None and terminal_path is not None and smoke_path is not None
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    if (
        terminal.get("disposition") != "INVALID_CC_B_EXECUTION"
        or terminal.get("claim_status") != "forbidden"
        or terminal.get("scientific_vote") is not False
        or int(terminal.get("formal_execution_count", -1)) != 0
        or int(terminal.get("cc_b_matrix_launch_count", -1)) != 0
        or smoke.get("validity") != "invalid"
    ):
        raise TelemetryContractError("parent invalid terminal boundary drifted")
    parent = load_cc_b_contract(parent_config, repository_root=root)
    stability = raw["frozen_stability"]
    parent_stability = parent.stability
    exact_pairs = {
        "which": "which",
        "eigenpairs": "eigenpairs",
        "tolerance": "tolerance",
        "maxiter": "maxiter",
        "ncv": "ncv",
        "relative_ritz_residual_max": "relative_ritz_residual_max",
        "h_half_operator_relative_difference_max": "h_half_operator_relative_difference_max",
        "stable_alpha_tau_max": "stable_alpha_tau_max",
        "backward_error_multiplier": "backward_error_multiplier",
    }
    for local_key, parent_key in exact_pairs.items():
        if stability[local_key] != parent_stability[parent_key]:
            raise TelemetryContractError(f"frozen stability field drifted: {local_key}")
    if int(raw["budget"]["campaign_attempt_count_max"]) != 2:
        raise TelemetryContractError("campaign attempt budget drifted")
    if int(raw["budget"]["implementation_repair_count_max"]) != 1:
        raise TelemetryContractError("implementation repair budget drifted")
    if float(raw["budget"]["aggregate_cpu_cap_s"]) != 7200.0:
        raise TelemetryContractError("CPU budget drifted")
    if float(raw["budget"]["calendar_wall_cap_s"]) != 7200.0:
        raise TelemetryContractError("wall budget drifted")
    _assert_base_ancestor(root, str(authority["expected_origin_main_sha"]))
    return TelemetryContract(path=config_path, repository_root=root, raw=raw, parent=parent)


def _finite_or_none(value: Any) -> Any:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    return numeric if np.isfinite(numeric) else None


class StabilityTelemetryRecorder:
    """Observer-only recorder. It never changes an operator input or result."""

    def __init__(
        self,
        root: Path,
        *,
        model: CurrentClamp2DModel,
        checkpoint_interval: int,
    ) -> None:
        self.root = Path(root)
        self.model = model
        self.checkpoint_interval = int(checkpoint_interval)
        self.jv_rows: list[dict[str, Any]] = []
        self.detail_arrays: dict[str, np.ndarray] = {}
        self.requested_pair_count = 0
        self.returned_pair_count = 0
        self.finite_pair_count = 0
        self.certified_pair_count = 0
        self.eigensolver_converged = False
        self.partial_pairs_eligible_for_certification = False
        self.failure_stage: str | None = None
        self.failure_code: str | None = None
        self.failure_detail: str | None = None
        self.h_half_operator_relative_difference: float | None = None
        self.artifact_error: str | None = None
        self._last_success: tuple[np.ndarray, np.ndarray] | None = None
        self._stability_summary: dict[str, Any] = {}

    def start_stability(
        self,
        *,
        requested_pair_count: int,
        state_dimension: int,
        temperature_K: np.ndarray,
    ) -> None:
        self.requested_pair_count = int(requested_pair_count)
        self._stability_summary.update(
            {
                "state_dimension": int(state_dimension),
                "temperature_min_K": float(np.min(temperature_K)),
                "temperature_max_K": float(np.max(temperature_K)),
            }
        )

    def record_jv(
        self,
        *,
        call_role: str,
        step_multiplier: float,
        step_size_K: float,
        direction: np.ndarray,
        result: np.ndarray | None,
        electrical_evaluations: list[dict[str, Any]],
        wall_time_s: float,
        cpu_time_s: float,
        exception: Exception | None,
    ) -> None:
        plus = electrical_evaluations[0] if len(electrical_evaluations) >= 1 else {}
        minus = electrical_evaluations[1] if len(electrical_evaluations) >= 2 else {}
        output = None if result is None else np.asarray(result)
        plus_current = plus.get("source_current_A")
        minus_current = minus.get("source_current_A")
        delta_current = None
        if plus_current is not None and minus_current is not None:
            delta_current = abs(float(plus_current) - float(minus_current)) / self.model.contract.scales.current_A
        finite = bool(
            exception is None
            and output is not None
            and np.isfinite(output).all()
            and len(electrical_evaluations) == 2
            and all(item.get("success") is True for item in electrical_evaluations)
        )
        row = {
            "call_index": len(self.jv_rows) + 1,
            "call_role": call_role,
            "perturbation_method": "central_difference",
            "step_multiplier": float(step_multiplier),
            "step_size_K": float(step_size_K),
            "input_inf_norm": float(np.linalg.norm(direction, ord=np.inf)),
            "output_inf_norm_per_s": None
            if output is None
            else _finite_or_none(np.linalg.norm(output, ord=np.inf)),
            "plus_temperature_min_K": _finite_or_none(plus.get("temperature_min_K")),
            "plus_temperature_max_K": _finite_or_none(plus.get("temperature_max_K")),
            "minus_temperature_min_K": _finite_or_none(minus.get("temperature_min_K")),
            "minus_temperature_max_K": _finite_or_none(minus.get("temperature_max_K")),
            "unit_bias_electrical_solve_count": len(electrical_evaluations),
            "electrical_solver_type": plus.get("solver_type", minus.get("solver_type", "not_reached")),
            "electrical_iterations": plus.get("iterations", minus.get("iterations", "not_reached")),
            "plus_electrical_residual": _finite_or_none(plus.get("scaled_electrical_residual_inf")),
            "minus_electrical_residual": _finite_or_none(minus.get("scaled_electrical_residual_inf")),
            "plus_electrical_wall_s": _finite_or_none(plus.get("wall_time_s")),
            "minus_electrical_wall_s": _finite_or_none(minus.get("wall_time_s")),
            "plus_electrical_cpu_s": _finite_or_none(plus.get("cpu_time_s")),
            "minus_electrical_cpu_s": _finite_or_none(minus.get("cpu_time_s")),
            "plus_G_hat_S": _finite_or_none(plus.get("unit_conductance_S")),
            "minus_G_hat_S": _finite_or_none(minus.get("unit_conductance_S")),
            "plus_Vd_V": _finite_or_none(plus.get("device_voltage_V")),
            "minus_Vd_V": _finite_or_none(minus.get("device_voltage_V")),
            "delta_Vd_V": None
            if plus.get("device_voltage_V") is None or minus.get("device_voltage_V") is None
            else abs(float(plus["device_voltage_V"]) - float(minus["device_voltage_V"])),
            "plus_normalized_current_error": _finite_or_none(plus.get("normalized_current_error")),
            "minus_normalized_current_error": _finite_or_none(minus.get("normalized_current_error")),
            "normalized_delta_I_cond": _finite_or_none(delta_current),
            "finite": finite,
            "operator_wall_s": float(wall_time_s),
            "operator_cpu_s": float(cpu_time_s),
            "exception_type": None if exception is None else type(exception).__name__,
            "exception_message": None if exception is None else str(exception),
        }
        self.jv_rows.append(row)
        if output is not None and finite:
            self._last_success = (np.asarray(direction, dtype=float).copy(), np.asarray(output).copy())
        if call_role.startswith("fixed_probe_"):
            safe = call_role.replace("-", "_")
            self.detail_arrays[f"{safe}_input"] = np.asarray(direction, dtype=float).copy()
            if output is not None:
                self.detail_arrays[f"{safe}_output"] = np.asarray(output).copy()
        if exception is not None and "first_failure_input" not in self.detail_arrays:
            self.detail_arrays["first_failure_input"] = np.asarray(direction, dtype=float).copy()
            if output is not None:
                self.detail_arrays["first_failure_output"] = np.asarray(output).copy()
        if self.checkpoint_interval > 0 and len(self.jv_rows) % self.checkpoint_interval == 0:
            self.checkpoint()

    def record_h_half_consistency(self, value: float) -> None:
        self.h_half_operator_relative_difference = float(value)

    def record_eigensolver_return(
        self,
        *,
        eigenvalues: np.ndarray | None,
        eigenvectors: np.ndarray | None,
        converged: bool,
        exception: Exception | None,
        eligible_for_certification: bool,
    ) -> None:
        values = np.asarray([] if eigenvalues is None else eigenvalues, dtype=complex)
        vectors = np.asarray(
            np.empty((0, 0), dtype=complex) if eigenvectors is None else eigenvectors,
            dtype=complex,
        )
        self.returned_pair_count = int(values.size)
        finite_values = np.isfinite(values.real) & np.isfinite(values.imag)
        finite_vectors = np.ones(values.size, dtype=bool)
        if vectors.ndim == 2 and vectors.shape[1] == values.size:
            finite_vectors = np.asarray(
                [np.isfinite(vectors[:, index].real).all() and np.isfinite(vectors[:, index].imag).all() for index in range(values.size)],
                dtype=bool,
            )
        else:
            finite_vectors[:] = False
        self.finite_pair_count = int(np.sum(finite_values & finite_vectors))
        self.eigensolver_converged = bool(converged)
        self.partial_pairs_eligible_for_certification = bool(eligible_for_certification)
        self._stability_summary.update(
            {
                "eigensolver_exception_type": None if exception is None else type(exception).__name__,
                "eigensolver_exception_message": None if exception is None else str(exception),
                "partial_pairs_eligible_for_certification": bool(eligible_for_certification),
            }
        )
        self._write_npz(
            self.root / "eigensolver_pairs.npz",
            eigenvalues_real_per_s=values.real,
            eigenvalues_imag_per_s=values.imag,
            eigenvectors_real=vectors.real,
            eigenvectors_imag=vectors.imag,
            eligible_for_certification=np.asarray([bool(eligible_for_certification)]),
        )

    def record_ritz_certification(
        self,
        *,
        eigenvalues: np.ndarray,
        eigenvectors: np.ndarray,
        absolute_residual_rates_per_s: np.ndarray,
        relative_residuals: np.ndarray,
    ) -> None:
        values = np.asarray(eigenvalues, dtype=complex)
        vectors = np.asarray(eigenvectors, dtype=complex)
        absolute = np.asarray(absolute_residual_rates_per_s, dtype=float)
        relative = np.asarray(relative_residuals, dtype=float)
        threshold = float(self.model.contract.stability["relative_ritz_residual_max"])
        certified = (
            np.isfinite(values.real)
            & np.isfinite(values.imag)
            & np.isfinite(absolute)
            & np.isfinite(relative)
            & (relative <= threshold)
        )
        self.certified_pair_count = int(np.sum(certified))
        order = np.argsort(values.real)[::-1]
        self._write_npz(
            self.root / "ritz_pairs.npz",
            eigenvalues_real_per_s=values.real,
            eigenvalues_imag_per_s=values.imag,
            eigenvectors_real=vectors.real,
            eigenvectors_imag=vectors.imag,
            absolute_ritz_residual_rates_per_s=absolute,
            relative_ritz_residuals=relative,
            certified=certified,
            rightmost_order=order,
        )

    def record_failure(self, *, stage: str, code: str, detail: str) -> None:
        if self.failure_stage is None:
            self.failure_stage = str(stage)
            self.failure_code = str(code)
            self.failure_detail = str(detail)

    def record_outcome(self, outcome: CCBStabilityOutcome) -> None:
        self._stability_summary.update(
            {
                "outcome_success": bool(outcome.success),
                "outcome_code": outcome.code,
                "outcome_stable": bool(outcome.stable),
                "rightmost_spectral_abscissa_per_s": outcome.rightmost_spectral_abscissa_per_s,
                "alpha_tau_dimensionless": outcome.alpha_tau_dimensionless,
            }
        )

    def finish_stability(self, telemetry: CCBStabilityTelemetry) -> None:
        self._stability_summary.update(
            {
                "matrix_vector_products": int(telemetry.matrix_vector_products),
                "dynamic_rhs_evaluations": int(telemetry.dynamic_rhs_evaluations),
                "wall_time_s": float(telemetry.wall_time_s),
                "cpu_time_s": float(telemetry.cpu_time_s),
                "failure_detail": telemetry.failure_detail,
            }
        )
        self.checkpoint()

    def _write_npz(self, path: Path, **arrays: np.ndarray) -> None:
        try:
            atomic_write_npz(path, **arrays)
        except Exception as exc:
            self.artifact_error = f"{type(exc).__name__}: {exc}"
            raise TelemetryArtifactError(self.artifact_error) from exc

    def checkpoint(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            atomic_write_csv(
                self.root / "jv_calls.csv",
                self.jv_rows,
                fieldnames=JVCALL_FIELDS,
            )
            numeric = {
                "call_index": np.asarray([row["call_index"] for row in self.jv_rows], dtype=int),
                "step_multiplier": np.asarray([row["step_multiplier"] for row in self.jv_rows], dtype=float),
                "step_size_K": np.asarray([row["step_size_K"] for row in self.jv_rows], dtype=float),
                "input_inf_norm": np.asarray([row["input_inf_norm"] for row in self.jv_rows], dtype=float),
                "output_inf_norm_per_s": np.asarray([np.nan if row["output_inf_norm_per_s"] is None else row["output_inf_norm_per_s"] for row in self.jv_rows], dtype=float),
                "normalized_delta_I_cond": np.asarray([np.nan if row["normalized_delta_I_cond"] is None else row["normalized_delta_I_cond"] for row in self.jv_rows], dtype=float),
                "finite": np.asarray([row["finite"] for row in self.jv_rows], dtype=bool),
                "operator_wall_s": np.asarray([row["operator_wall_s"] for row in self.jv_rows], dtype=float),
                "operator_cpu_s": np.asarray([row["operator_cpu_s"] for row in self.jv_rows], dtype=float),
            }
            atomic_write_npz(self.root / "jv_calls.npz", **numeric)
            details = dict(self.detail_arrays)
            if self._last_success is not None:
                details["last_success_input"] = self._last_success[0]
                details["last_success_output"] = self._last_success[1]
            if details:
                atomic_write_npz(self.root / "jv_details.npz", **details)
            summary = {
                "schema_version": "q2_cc_b_stability_telemetry_recorder_v1",
                "requested_pair_count": int(self.requested_pair_count),
                "returned_pair_count": int(self.returned_pair_count),
                "finite_pair_count": int(self.finite_pair_count),
                "certified_pair_count": int(self.certified_pair_count),
                "eigensolver_converged": bool(self.eigensolver_converged),
                "partial_pairs_eligible_for_certification": bool(
                    self.partial_pairs_eligible_for_certification
                ),
                "h_half_operator_relative_difference": _finite_or_none(
                    self.h_half_operator_relative_difference
                ),
                "failure_stage": self.failure_stage,
                "failure_code": self.failure_code,
                "failure_detail": self.failure_detail,
                "jv_call_count": len(self.jv_rows),
                "stability": self._stability_summary,
            }
            atomic_write_json(self.root / "telemetry_summary.json", summary)
        except TelemetryArtifactError:
            raise
        except Exception as exc:
            self.artifact_error = f"{type(exc).__name__}: {exc}"
            raise TelemetryArtifactError(self.artifact_error) from exc


def deterministic_jv_probes(model: CurrentClamp2DModel) -> tuple[np.ndarray, np.ndarray]:
    first = _deterministic_vector(model)
    x, y = np.meshgrid(model.grid.x_centers_m, model.grid.y_centers_m)
    xr = (x - float(np.mean(x))) / max(float(np.ptp(x)), 1.0e-30)
    yr = (y - float(np.mean(y))) / max(float(np.ptp(y)), 1.0e-30)
    second = (0.75 - 0.3 * xr + 0.4 * yr).reshape(-1)
    second -= float(np.dot(second, first)) * first
    second /= max(float(np.linalg.norm(second)), 1.0e-300)
    return first, second


def _relative_difference(left: np.ndarray, right: np.ndarray, floor: float) -> float:
    return float(
        np.linalg.norm(np.asarray(left) - np.asarray(right))
        / max(np.linalg.norm(left), np.linalg.norm(right), float(floor))
    )


def run_operator_prechecks(
    contract: TelemetryContract,
    model: CurrentClamp2DModel,
    temperature_K: np.ndarray,
    recorder: StabilityTelemetryRecorder,
    gates: GateBook,
) -> bool:
    gate = contract.raw["diagnostic_gates"]
    mass = np.asarray(model.cell_capacity_J_K, dtype=float)
    expected_mass = float(model.source_parameters.thermal_capacitance_J_K)
    mass_relative = abs(float(np.sum(mass)) - expected_mass) / expected_mass
    mass_pass = bool(
        mass.shape == (temperature_K.size,)
        and mass.dtype.kind == "f"
        and np.isfinite(mass).all()
        and np.all(mass > 0.0)
        and mass_relative <= float(gate["mass_sum_relative_max"])
    )
    gates.set(
        "MASS_MATRIX_VALIDITY",
        "PASS" if mass_pass else "INVALID",
        "temperature mass matrix is finite, positive, and closes to Cth"
        if mass_pass
        else "temperature mass matrix validation failed",
        metrics={
            "shape": list(mass.shape),
            "dtype": str(mass.dtype),
            "sum_J_K": float(np.sum(mass)),
            "expected_Cth_J_K": expected_mass,
            "relative_sum_error": mass_relative,
            "condition_proxy": float(np.max(mass) / np.min(mass)),
        },
    )
    if not mass_pass:
        return False

    probe_a, probe_b = deterministic_jv_probes(model)
    telemetry = CCBStabilityTelemetry()
    try:
        a1 = _apply_operator(
            model,
            temperature_K,
            probe_a,
            telemetry,
            recorder=recorder,
            call_role="fixed_probe_a_repeat_1",
        )
        a2 = _apply_operator(
            model,
            temperature_K,
            probe_a,
            telemetry,
            recorder=recorder,
            call_role="fixed_probe_a_repeat_2",
        )
        a_half = _apply_operator(
            model,
            temperature_K,
            probe_a,
            telemetry,
            step_multiplier=0.5,
            recorder=recorder,
            call_role="fixed_probe_a_h_half",
        )
        a_two = _apply_operator(
            model,
            temperature_K,
            probe_a,
            telemetry,
            step_multiplier=2.0,
            recorder=recorder,
            call_role="fixed_probe_a_two_h",
        )
        a_scaled = _apply_operator(
            model,
            temperature_K,
            -0.5 * probe_a,
            telemetry,
            recorder=recorder,
            call_role="fixed_probe_a_scaled",
        )
        b = _apply_operator(
            model,
            temperature_K,
            probe_b,
            telemetry,
            recorder=recorder,
            call_role="fixed_probe_b",
        )
        added = _apply_operator(
            model,
            temperature_K,
            probe_a + probe_b,
            telemetry,
            recorder=recorder,
            call_role="fixed_probe_a_plus_b",
        )
    except Exception as exc:
        recorder.record_failure(
            stage="JV_EVALUATION",
            code="INVALID_STABILITY",
            detail=f"operator precheck failed: {type(exc).__name__}: {exc}",
        )
        gates.set("JV_FINITE", "INVALID", str(exc))
        return False

    rhs_evaluation = model.evaluate_temperature(temperature_K)
    rhs = model.dynamic_rhs(temperature_K)
    sign_error = _relative_difference(
        rhs,
        -rhs_evaluation.thermal_residual_W.reshape(-1) / mass,
        1.0 / model.tau0_s,
    )
    sign_pass = bool(rhs.shape == (temperature_K.size,) and np.isfinite(rhs).all() and sign_error <= 1.0e-12)
    gates.set(
        "OPERATOR_UNIT_AND_SIGN",
        "PASS" if sign_pass else "INVALID",
        "F(T)=-M_C^-1 R_T has the frozen temperature-rate shape and sign"
        if sign_pass
        else "dynamic RHS unit/sign closure failed",
        metrics={"relative_identity_error": sign_error, "output_unit": "K_per_s"},
    )

    repeatability = _relative_difference(a1, a2, 1.0 / model.tau0_s)
    homogeneity = _relative_difference(a_scaled, -0.5 * a1, 1.0 / model.tau0_s)
    additivity = _relative_difference(added, a1 + b, 1.0 / model.tau0_s)
    h_half = _relative_difference(a1, a_half, 1.0 / model.tau0_s)
    two_h = _relative_difference(a_two, a1, 1.0 / model.tau0_s)
    finite_pass = bool(
        all(np.isfinite(value).all() for value in (a1, a2, a_half, a_two, a_scaled, b, added))
        and all(bool(row["finite"]) for row in recorder.jv_rows)
    )
    gates.set(
        "JV_FINITE",
        "PASS" if finite_pass else "INVALID",
        "all preregistered operator probes are finite" if finite_pass else "a Jv probe is nonfinite",
    )
    repeat_pass = repeatability <= float(gate["jv_repeatability_relative_max"])
    gates.set(
        "JV_REPEATABILITY",
        "PASS" if repeat_pass else "INVALID",
        "deterministic repeated Jv agrees" if repeat_pass else "deterministic repeated Jv differs",
        metrics={"relative_difference": repeatability},
    )
    homogeneity_pass = homogeneity <= float(gate["jv_homogeneity_relative_max"])
    gates.set(
        "JV_HOMOGENEITY",
        "PASS" if homogeneity_pass else "FAIL",
        "nonvoting homogeneity diagnostic",
        metrics={"relative_difference": homogeneity, "scale": -0.5},
    )
    additivity_pass = additivity <= float(gate["jv_additivity_relative_max"])
    gates.set(
        "JV_ADDITIVITY",
        "PASS" if additivity_pass else "FAIL",
        "nonvoting additivity diagnostic",
        metrics={"relative_difference": additivity},
    )
    h_half_pass = h_half <= float(gate["jv_h_half_relative_max"])
    gates.set(
        "JV_STEP_SIZE_CONSISTENCY",
        "PASS" if h_half_pass else "INVALID",
        "parent h/h2 operator gate",
        metrics={
            "h_vs_h_half_relative_difference": h_half,
            "two_h_vs_h_relative_difference_nonvoting": two_h,
            "two_h_nonvoting_pass": two_h <= float(gate["jv_two_h_relative_max"]),
        },
    )
    current_rows = [row for row in recorder.jv_rows if row["unit_bias_electrical_solve_count"] == 2]
    electrical_max = max(
        [
            float(value)
            for row in current_rows
            for value in (row["plus_electrical_residual"], row["minus_electrical_residual"])
            if value is not None
        ],
        default=float("inf"),
    )
    current_error_max = max(
        [
            float(value)
            for row in current_rows
            for value in (
                row["plus_normalized_current_error"],
                row["minus_normalized_current_error"],
                row["normalized_delta_I_cond"],
            )
            if value is not None
        ],
        default=float("inf"),
    )
    electrical_pass = electrical_max <= float(gate["electrical_scaled_residual_max"])
    current_pass = current_error_max <= float(gate["fixed_current_relative_max"])
    gates.set(
        "ELECTRICAL_SUBSOLVE",
        "PASS" if electrical_pass else "INVALID",
        "all plus/minus unit-bias solves pass the parent residual gate"
        if electrical_pass
        else "a plus/minus electrical solve failed its residual gate",
        metrics={"maximum_scaled_electrical_residual": electrical_max},
    )
    gates.set(
        "FIXED_CURRENT_CONSTRAINT",
        "PASS" if current_pass else "INVALID",
        "all plus/minus projections preserve conductive-sheet current"
        if current_pass
        else "a plus/minus projection violated fixed current",
        metrics={"maximum_normalized_current_error": current_error_max},
    )
    return bool(
        mass_pass
        and sign_pass
        and finite_pass
        and repeat_pass
        and h_half_pass
        and electrical_pass
        and current_pass
    )


def classify_spectrum(
    *,
    alpha_per_s: float,
    maximum_ritz_residual_rate_per_s: float,
    tau0_s: float,
    stable: bool,
    backward_error_multiplier: float = 10.0,
) -> str:
    if stable:
        return "STABLE_MARGIN_PASS"
    uncertainty = backward_error_multiplier * maximum_ritz_residual_rate_per_s
    if abs(alpha_per_s) <= uncertainty:
        return "SIGN_INDETERMINATE_WITHIN_RITZ_UNCERTAINTY"
    if alpha_per_s > 0.0:
        return "POSITIVE_UNSTABLE"
    return "NEGATIVE_MARGIN_INSUFFICIENT"


def _exclusive_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TelemetryArtifactError(f"{path} is not a JSON object")
    return payload


def increment_campaign_counter(path: Path, *, attempt: str, repair_count: int) -> dict[str, Any]:
    if path.exists():
        payload = _read_json(path)
    else:
        payload = {
            "schema_version": "q2_cc_b_stability_telemetry_counters_v1",
            "campaign_attempt_count": 0,
            "implementation_repair_count": 0,
            "attempts": [],
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
        }
    payload["campaign_attempt_count"] = int(payload["campaign_attempt_count"]) + 1
    payload["implementation_repair_count"] = int(repair_count)
    payload["attempts"] = [*payload["attempts"], attempt]
    atomic_write_json(path, payload)
    return payload


def _parent_initial_temperature(contract: TelemetryContract) -> tuple[np.ndarray, dict[str, Any]]:
    authority = contract.raw["authority"]
    compact_path = contract.repository_root / str(authority["parent_l1_compact"]["path"])
    compact = _read_json(compact_path)
    npz_path = contract.repository_root / str(authority["parent_l1_npz"]["path"])
    model = build_cc_b_model(
        contract.parent,
        spatial_level=1,
        current_set_A=2.0e-4,
        branch="heating",
        defect="NOM",
    )
    if npz_path.is_file() and file_sha256(npz_path) == str(authority["parent_l1_npz"]["sha256"]):
        with np.load(npz_path, allow_pickle=False) as payload:
            temperature = np.asarray(payload["temperature_K"], dtype=float)
        evaluation = model.evaluate_temperature(temperature)
        if not np.isclose(
            evaluation.device_voltage_V,
            float(compact["device_voltage_V"]),
            rtol=1.0e-12,
            atol=1.0e-12,
        ):
            raise TelemetryContractError("parent L1 NPZ does not reproduce compact voltage")
        return temperature, {
            "source": "verified_parent_0p2mA_L1_npz",
            "parent_npz_sha256": file_sha256(npz_path),
            "parent_compact_sha256": file_sha256(compact_path),
        }

    params = OracleParameters.from_config(contract.parent.cc_a_config)
    roots = discover_roots(
        branch="heating",
        current_A=2.0e-4,
        params=params,
        config=contract.parent.cc_a_config,
    ).roots
    certified = [root for root in roots if root.certified]
    if len(certified) != 1:
        raise TelemetrySemanticsStop("diagnostic fallback lacks one certified scalar initializer")
    fallback = solve_cc_b_equilibrium(
        model,
        initial_temperature_K=np.full(model.grid.shape, certified[0].temperature_K),
    )
    if not fallback.success or fallback.temperature_K is None or fallback.evaluation is None:
        raise TelemetrySemanticsStop("diagnostic 0.2 mA initialization cannot be regenerated")
    if not np.isclose(
        fallback.evaluation.device_voltage_V,
        float(compact["device_voltage_V"]),
        rtol=1.0e-10,
        atol=1.0e-10,
    ):
        raise TelemetrySemanticsStop("diagnostic fallback disagrees with parent compact scalars")
    return fallback.temperature_K, {
        "source": "non_voting_diagnostic_parent_initialization_regeneration",
        "parent_npz_sha256": None,
        "parent_compact_sha256": file_sha256(compact_path),
    }


def regenerate_diagnostic_equilibrium(
    contract: TelemetryContract,
    *,
    attempt_compact: Path,
    attempt_processed: Path,
    gates: GateBook,
) -> tuple[CCBSolveOutcome | None, CurrentClamp2DModel | None, dict[str, Any]]:
    initial, parent_identity = _parent_initial_temperature(contract)
    model = build_cc_b_model(
        contract.parent,
        spatial_level=1,
        current_set_A=4.0e-4,
        branch="heating",
        defect="NOM",
    )
    solve = solve_cc_b_equilibrium(model, initial_temperature_K=initial)
    if not solve.success or solve.temperature_K is None or solve.evaluation is None:
        payload = {
            "schema_version": "q2_cc_b_stability_diagnostic_equilibrium_failure_v1",
            "input_identity": "non_voting_diagnostic_equilibrium_regeneration",
            "parent_initialization": parent_identity,
            "solve": solve,
        }
        atomic_write_json(attempt_compact / "equilibrium_failure.json", payload)
        gates.set(
            "EQUILIBRIUM_INPUT_INTEGRITY",
            "FAIL",
            f"diagnostic equilibrium failed: {solve.code}",
            metrics={"failure_detail": solve.telemetry.failure_detail},
        )
        return None, model, payload
    actual_head = _git_head(contract.repository_root)
    artifact = save_cc_b_equilibrium(
        attempt_processed / "diagnostic_input",
        attempt_compact / "diagnostic_input",
        identity="diagnostic_NOM_heating_0p4mA_L1",
        solve=solve,
        stability=None,
        metadata={
            "input_identity": "non_voting_diagnostic_equilibrium_regeneration",
            "reproduction_semantics": contract.raw["reproduction_semantics"],
            "parent_initialization": parent_identity,
            "config_sha256": file_sha256(contract.path),
            "code_identity": actual_head,
            "scientific_vote": False,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
        },
    )
    npz_path = Path(str(artifact["npz_path"]))
    manifest_path = Path(str(artifact["manifest_path"]))
    if file_sha256(npz_path) != str(artifact["npz_sha256"]):
        raise TelemetryArtifactError("diagnostic equilibrium NPZ hash changed after save")
    with np.load(npz_path, allow_pickle=False) as payload:
        reloaded_temperature = np.asarray(payload["temperature_K"], dtype=float)
    reloaded = model.evaluate_temperature(reloaded_temperature)
    ledger_max = max(
        reloaded.ledger.current_error,
        reloaded.ledger.terminal_field_power_error,
        reloaded.ledger.field_thermal_error,
    )
    gate = contract.raw["equilibrium_input_gates"]
    lower, upper = map(float, gate["temperature_K"])
    passed = bool(
        reloaded_temperature.shape == model.grid.shape
        and reloaded_temperature.dtype.kind == "f"
        and np.isfinite(reloaded_temperature).all()
        and np.min(reloaded_temperature) >= lower
        and np.max(reloaded_temperature) <= upper
        and reloaded.scaled_thermal_residual_inf <= float(gate["thermal_scaled_cv_residual_max"])
        and solve.last_scaled_update_inf <= float(gate["last_scaled_update_inf_max"])
        and reloaded.scaled_electrical_residual_inf <= float(gate["electrical_scaled_cv_residual_max"])
        and ledger_max <= float(gate["ledger_symmetric_relative_max"])
        and reloaded.device_voltage_V <= float(gate["voltage_operating_envelope_max_V"])
        and manifest_path.is_file()
        and file_sha256(manifest_path) == str(artifact["manifest_sha256"])
    )
    metrics = {
        "thermal_scaled_cv_residual_inf": reloaded.scaled_thermal_residual_inf,
        "last_scaled_update_inf": solve.last_scaled_update_inf,
        "electrical_scaled_cv_residual_inf": reloaded.scaled_electrical_residual_inf,
        "ledger_max": ledger_max,
        "temperature_min_K": float(np.min(reloaded_temperature)),
        "temperature_max_K": float(np.max(reloaded_temperature)),
        "device_voltage_V": reloaded.device_voltage_V,
        "npz_sha256": artifact["npz_sha256"],
        "manifest_sha256": artifact["manifest_sha256"],
        "code_identity": actual_head,
        "config_sha256": file_sha256(contract.path),
    }
    gates.set(
        "EQUILIBRIUM_INPUT_INTEGRITY",
        "PASS" if passed else "INVALID",
        "the regenerated L1 equilibrium was saved before stability and re-certified"
        if passed
        else "the regenerated L1 equilibrium failed readback certification",
        metrics=metrics,
    )
    atomic_write_json(
        attempt_compact / "diagnostic_input" / "readback_certification.json",
        {
            "schema_version": "q2_cc_b_stability_diagnostic_input_certification_v1",
            "passed": passed,
            "input_identity": "non_voting_diagnostic_equilibrium_regeneration",
            "parent_initialization": parent_identity,
            "metrics": metrics,
            "artifact": artifact,
        },
    )
    return (solve if passed else None), model, {"artifact": artifact, "metrics": metrics}


def _apply_stability_gates(
    contract: TelemetryContract,
    recorder: StabilityTelemetryRecorder,
    outcome: CCBStabilityOutcome,
    gates: GateBook,
) -> None:
    requested = int(contract.target["eigenpairs"])
    gates.set(
        "EIGENSOLVER_RETURN",
        "PASS" if recorder.eigensolver_converged else "INVALID",
        "ARPACK returned normally" if recorder.eigensolver_converged else "ARPACK did not return a complete converged result",
        metrics={
            "requested_pair_count": requested,
            "returned_pair_count": recorder.returned_pair_count,
            "partial_pairs_eligible_for_certification": recorder.partial_pairs_eligible_for_certification,
        },
    )
    count_pass = recorder.returned_pair_count == requested
    gates.set(
        "RITZ_COUNT",
        "PASS" if count_pass else "INVALID",
        "requested and returned pair counts agree" if count_pass else "returned pair count is incomplete",
        metrics={
            "requested_pair_count": requested,
            "returned_pair_count": recorder.returned_pair_count,
            "finite_pair_count": recorder.finite_pair_count,
            "certified_pair_count": recorder.certified_pair_count,
        },
    )
    finite_pass = recorder.finite_pair_count == requested
    gates.set(
        "RITZ_FINITE",
        "PASS" if finite_pass else "INVALID",
        "all returned pairs are finite" if finite_pass else "one or more returned pairs are nonfinite",
    )
    residual_pass = recorder.certified_pair_count == requested and outcome.success
    gates.set(
        "RITZ_RELATIVE_RESIDUAL",
        "PASS" if residual_pass else "INVALID",
        "all Ritz pairs satisfy the frozen relative residual gate"
        if residual_pass
        else "Ritz certification did not produce six eligible pairs",
        metrics={
            "maximum_relative_ritz_residual": None
            if outcome.relative_ritz_residuals.size == 0
            else float(np.max(outcome.relative_ritz_residuals)),
        },
    )
    ordering_pass = bool(
        outcome.success
        and outcome.eigenvalues_per_s.size == requested
        and np.isclose(
            outcome.rightmost_spectral_abscissa_per_s,
            float(np.max(outcome.eigenvalues_per_s.real)),
            rtol=0.0,
            atol=0.0,
        )
    )
    gates.set(
        "RIGHTMOST_ORDERING",
        "PASS" if ordering_pass else "INVALID",
        "reported spectral abscissa is the rightmost returned Ritz value"
        if ordering_pass
        else "rightmost ordering was not certifiable",
    )
    gates.set(
        "K6_K10_CONSISTENCY",
        "SKIPPED_NOT_ELIGIBLE",
        "review_revision=20260808-R1 prohibits k=10 and all L2 execution",
    )


def _verify_artifacts(root: Path) -> tuple[bool, dict[str, Any]]:
    json_files = sorted(root.rglob("*.json"))
    csv_files = sorted(root.rglob("*.csv"))
    npz_files = sorted(root.rglob("*.npz"))
    try:
        for path in json_files:
            json.loads(path.read_text(encoding="utf-8"))
        for path in npz_files:
            with np.load(path, allow_pickle=False) as payload:
                for name in payload.files:
                    np.asarray(payload[name])
        hashes = {path.relative_to(root).as_posix(): file_sha256(path) for path in [*json_files, *csv_files, *npz_files]}
        return True, {
            "json_count": len(json_files),
            "csv_count": len(csv_files),
            "npz_count": len(npz_files),
            "hashes": hashes,
        }
    except Exception as exc:
        return False, {"failure_type": type(exc).__name__, "failure_detail": str(exc)}


def _write_terminal(
    root: Path,
    *,
    contract: TelemetryContract,
    disposition: str,
    validity: str,
    telemetry_closure_status: str,
    closure_class: str,
    stability_certification_status: str,
    physical_spectrum_classification: str,
    stable: bool | None,
    attempt: str,
    counters: Mapping[str, Any],
    gates: GateBook,
    budget: Mapping[str, Any],
    detail: str,
) -> dict[str, Any]:
    if disposition not in TERMINAL_DISPOSITIONS:
        raise ValueError("unregistered telemetry terminal disposition")
    if physical_spectrum_classification not in SPECTRUM_CLASSES:
        raise ValueError("unregistered physical spectrum classification")
    payload = {
        "schema_version": "q2_cc_b_stability_telemetry_terminal_v1",
        "task_id": TASK_ID,
        "review_revision": REVIEW_REVISION,
        "campaign": contract.campaign,
        "attempt": attempt,
        "reproduction_semantics": contract.raw["reproduction_semantics"],
        "disposition": disposition,
        "validity": validity,
        "lifecycle_state": "executed",
        "claim_status": "forbidden",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "cc_b_matrix_launch_count": 0,
        "telemetry_closure_status": telemetry_closure_status,
        "closure_class": closure_class,
        "stability_certification_status": stability_certification_status,
        "physical_spectrum_classification": physical_spectrum_classification,
        "stable": stable,
        "requested_case": contract.target,
        "counters": dict(counters),
        "gates": gates.rows(),
        "budget": dict(budget),
        "detail": detail,
        "cc_b_scientific_pass": False,
        "uniform_gate_executed": False,
        "formal_matrix_executed": False,
        "cc_c_authorized": False,
        "pinn_executed": False,
    }
    atomic_write_json(root / "terminal.json", payload)
    reloaded = _read_json(root / "terminal.json")
    if reloaded.get("disposition") != disposition:
        raise TelemetryArtifactError("terminal readback changed disposition")
    gates.set(
        "TERMINAL_AGGREGATION",
        "PASS",
        "terminal was written atomically and read back with mutually exclusive state",
    )
    payload["gates"] = gates.rows()
    atomic_write_json(root / "terminal.json", payload)
    return payload


def run_telemetry_closure(
    config_path: Path | str = Path("configs/q2_cc_b_stability_telemetry_closure_v1.yaml"),
    *,
    repository_root: Path | str | None = None,
    attempt: str = "T1",
    repair_count: int = 0,
    preexecution_cpu_s: float = 0.0,
    preexecution_wall_s: float = 0.0,
    compact_root_override: Path | None = None,
    processed_root_override: Path | None = None,
) -> dict[str, Any]:
    contract = load_telemetry_contract(config_path, repository_root=repository_root)
    if attempt not in ("T1", "T2"):
        raise TelemetryContractError("attempt must be T1 or T2")
    if attempt == "T1" and repair_count != 0:
        raise TelemetryContractError("T1 cannot consume a repair")
    if attempt == "T2" and repair_count != 1:
        raise TelemetryContractError("T2 requires the sole registered repair")
    compact_base = contract.compact_root if compact_root_override is None else Path(compact_root_override)
    processed_base = contract.processed_root if processed_root_override is None else Path(processed_root_override)
    compact = compact_base / contract.campaign
    processed = processed_base / contract.campaign
    if attempt == "T1":
        _exclusive_directory(compact)
        _exclusive_directory(processed)
        atomic_write_json(
            compact / "identity.json",
            {
                "schema_version": "q2_cc_b_stability_telemetry_identity_v1",
                "task_id": TASK_ID,
                "review_revision": REVIEW_REVISION,
                "campaign": contract.campaign,
                "config_path": contract.path.relative_to(contract.repository_root).as_posix(),
                "config_sha256": file_sha256(contract.path),
                "authority": contract.raw["authority"],
                "environment": environment_record(contract.repository_root, run_id=contract.campaign),
                "reproduction_semantics": contract.raw["reproduction_semantics"],
            },
        )
    elif not compact.is_dir() or not processed.is_dir():
        raise TelemetryContractError("T2 requires the existing T1 campaign root")
    attempt_compact = compact / "attempts" / attempt
    attempt_processed = processed / "attempts" / attempt
    _exclusive_directory(attempt_compact)
    _exclusive_directory(attempt_processed)
    gates = GateBook()
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    gates.set(
        "INPUT_IDENTITY",
        "PASS",
        "PR #32 merge ancestry and all parent hashes were authenticated",
        metrics={
            "execution_git_sha": _git_head(contract.repository_root),
            "expected_origin_main_sha": contract.raw["authority"]["expected_origin_main_sha"],
            "config_sha256": file_sha256(contract.path),
        },
    )
    disposition = "INVALID_CC_B_STABILITY_TELEMETRY_EXECUTION"
    validity = "invalid"
    closure_status = "INVALID"
    closure_class = "unlocalized_execution_invalidity"
    certification_status = "NOT_RUN"
    spectrum_class = "NOT_APPLICABLE"
    stable: bool | None = None
    detail = "telemetry task did not reach a classifiable terminal"
    counters: dict[str, Any] = {
        "campaign_attempt_count": 0,
        "implementation_repair_count": repair_count,
        "formal_execution_count": 0,
        "cc_b_matrix_launch_count": 0,
    }
    outcome: CCBStabilityOutcome | None = None
    recorder: StabilityTelemetryRecorder | None = None
    try:
        if preexecution_cpu_s >= float(contract.raw["budget"]["aggregate_cpu_cap_s"]):
            raise TelemetryBudgetStop("preexecution CPU already exhausted the task budget")
        if preexecution_wall_s >= float(contract.raw["budget"]["calendar_wall_cap_s"]):
            raise TelemetryBudgetStop("preexecution wall time already exhausted the task budget")
        solve, model, input_record = regenerate_diagnostic_equilibrium(
            contract,
            attempt_compact=attempt_compact,
            attempt_processed=attempt_processed,
            gates=gates,
        )
        if solve is None or model is None or solve.temperature_K is None:
            disposition = "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
            validity = "valid"
            closure_status = "PASS"
            closure_class = "input_invalidity_localized"
            certification_status = "NOT_RUN"
            detail = "the diagnostic equilibrium input failed a recorded prerequisite gate"
        else:
            counters = increment_campaign_counter(
                compact / "counters.json", attempt=attempt, repair_count=repair_count
            )
            if int(counters["campaign_attempt_count"]) > int(
                contract.raw["budget"]["campaign_attempt_count_max"]
            ):
                raise TelemetryBudgetStop("campaign replay counter exceeded its hard maximum")
            recorder = StabilityTelemetryRecorder(
                attempt_compact / "telemetry",
                model=model,
                checkpoint_interval=int(
                    contract.raw["diagnostic_gates"]["checkpoint_matvec_interval"]
                ),
            )
            prechecks_pass = run_operator_prechecks(
                contract,
                model,
                solve.temperature_K,
                recorder,
                gates,
            )
            if not prechecks_pass:
                recorder.checkpoint()
                disposition = "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
                validity = "valid"
                closure_status = "PASS"
                closure_class = "implementation_invalidity_localized"
                certification_status = "INVALID"
                detail = "operator/Jv prechecks localized the parent stability invalidity"
            else:
                replay_started = time.perf_counter()
                outcome = certify_current_clamp_stability(
                    model,
                    temperature_K=solve.temperature_K,
                    eigenpairs=6,
                    recorder=recorder,
                )
                replay_wall = time.perf_counter() - replay_started
                if replay_wall > float(contract.raw["budget"]["l1_k6_replay_cap_s"]):
                    raise TelemetryBudgetStop("L1/k6 replay exceeded its preregistered wall cap")
                _apply_stability_gates(contract, recorder, outcome, gates)
                if outcome.success:
                    rho_max = float(np.max(outcome.absolute_backward_errors_per_s))
                    spectrum_class = classify_spectrum(
                        alpha_per_s=outcome.rightmost_spectral_abscissa_per_s,
                        maximum_ritz_residual_rate_per_s=rho_max,
                        tau0_s=model.tau0_s,
                        stable=outcome.stable,
                        backward_error_multiplier=float(
                            contract.parent.stability["backward_error_multiplier"]
                        ),
                    )
                    disposition = "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
                    validity = "valid"
                    closure_status = "PASS"
                    closure_class = "valid_spectrum"
                    certification_status = "CERTIFIED"
                    stable = bool(outcome.stable)
                    detail = "L1/k6 returned a complete finite Ritz-certified spectrum"
                else:
                    disposition = "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
                    validity = "valid"
                    closure_status = "PASS"
                    closure_class = "implementation_invalidity_localized"
                    certification_status = "INVALID"
                    detail = (
                        f"stability invalidity localized at {recorder.failure_stage}: "
                        f"{recorder.failure_detail}"
                    )

        artifact_pass, artifact_metrics = _verify_artifacts(attempt_compact)
        gates.set(
            "ARTIFACT_CANONICALIZATION",
            "PASS" if artifact_pass else "INVALID",
            "all diagnostic artifacts round-trip and hash"
            if artifact_pass
            else "a diagnostic artifact failed round-trip validation",
            metrics=artifact_metrics,
        )
        if not artifact_pass:
            disposition = "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
            validity = "valid"
            closure_status = "PASS"
            closure_class = "artifact_path_invalidity_localized"
            certification_status = "INVALID"
            spectrum_class = "NOT_APPLICABLE"
            stable = None
            detail = "artifact invalidity was localized while the terminal path remained writable"
    except TelemetryBudgetStop as exc:
        disposition = "STOP_CC_B_STABILITY_BUDGET_NOT_ADMISSIBLE"
        validity = "valid"
        closure_status = "STOPPED"
        closure_class = "budget_not_admissible"
        certification_status = "NOT_APPLICABLE"
        detail = str(exc)
    except TelemetrySemanticsStop as exc:
        disposition = "STOP_CC_B_STABILITY_SEMANTICS_NOT_CLOSED"
        validity = "valid"
        closure_status = "STOPPED"
        closure_class = "frozen_semantics_change_required"
        certification_status = "NOT_APPLICABLE"
        detail = str(exc)
    except TelemetryArtifactError as exc:
        disposition = "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
        validity = "valid"
        closure_status = "PASS"
        closure_class = "artifact_path_invalidity_localized"
        certification_status = "INVALID"
        detail = str(exc)
        gates.set("ARTIFACT_CANONICALIZATION", "INVALID", str(exc))
    except Exception as exc:
        disposition = "INVALID_CC_B_STABILITY_TELEMETRY_EXECUTION"
        validity = "invalid"
        closure_status = "INVALID"
        closure_class = "unlocalized_execution_invalidity"
        certification_status = "INVALID"
        detail = f"{type(exc).__name__}: {exc}"

    elapsed_wall = preexecution_wall_s + (time.perf_counter() - wall_started)
    elapsed_cpu = preexecution_cpu_s + (time.process_time() - cpu_started)
    if (
        disposition == "PASS_CC_B_STABILITY_TELEMETRY_CLOSURE"
        and (
            elapsed_wall > float(contract.raw["budget"]["calendar_wall_cap_s"])
            or elapsed_cpu > float(contract.raw["budget"]["aggregate_cpu_cap_s"])
        )
    ):
        disposition = "STOP_CC_B_STABILITY_BUDGET_NOT_ADMISSIBLE"
        validity = "valid"
        closure_status = "STOPPED"
        closure_class = "budget_not_admissible"
        certification_status = "NOT_APPLICABLE"
        spectrum_class = "NOT_APPLICABLE"
        stable = None
        detail = "the telemetry task exceeded its aggregate CPU or wall budget"
    budget = {
        "aggregate_cpu_s": elapsed_cpu,
        "calendar_wall_s": elapsed_wall,
        "aggregate_cpu_cap_s": float(contract.raw["budget"]["aggregate_cpu_cap_s"]),
        "calendar_wall_cap_s": float(contract.raw["budget"]["calendar_wall_cap_s"]),
        "l1_k6_wall_cap_s": float(contract.raw["budget"]["l1_k6_replay_cap_s"]),
    }
    try:
        terminal = _write_terminal(
            compact,
            contract=contract,
            disposition=disposition,
            validity=validity,
            telemetry_closure_status=closure_status,
            closure_class=closure_class,
            stability_certification_status=certification_status,
            physical_spectrum_classification=spectrum_class,
            stable=stable,
            attempt=attempt,
            counters=counters,
            gates=gates,
            budget=budget,
            detail=detail,
        )
    except Exception as exc:
        fallback = {
            "schema_version": "q2_cc_b_stability_telemetry_terminal_v1",
            "task_id": TASK_ID,
            "review_revision": REVIEW_REVISION,
            "campaign": contract.campaign,
            "attempt": attempt,
            "disposition": "INVALID_CC_B_STABILITY_TELEMETRY_EXECUTION",
            "validity": "invalid",
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
            "telemetry_closure_status": "INVALID",
            "closure_class": "terminal_aggregation_invalidity",
            "stability_certification_status": "INVALID",
            "physical_spectrum_classification": "NOT_APPLICABLE",
            "stable": None,
            "detail": f"terminal aggregation failed: {type(exc).__name__}: {exc}",
            "budget": budget,
            "counters": counters,
        }
        atomic_write_json(compact / "terminal.json", fallback)
        terminal = fallback
    return terminal

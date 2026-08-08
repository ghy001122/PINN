"""Bounded L1/L2 stability requalification after the PR #33 Jv-scale defect."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import perf_counter, process_time
from typing import Any, Mapping

import numpy as np
import yaml

from pinnpcm.branchconserve.artifacts import atomic_write_npz
from pinnpcm.current_clamp.artifacts import atomic_write_json, file_sha256
from pinnpcm.current_clamp.cc_b_artifacts import save_cc_b_equilibrium
from pinnpcm.current_clamp.cc_b_model import CurrentClamp2DModel, build_cc_b_model
from pinnpcm.current_clamp.cc_b_solver import solve_cc_b_equilibrium
from pinnpcm.current_clamp.cc_b_stability import (
    CCBStabilityOutcome,
    CCBStabilityTelemetry,
    _apply_operator,
    _mass_norm,
    centered_jv_step_size_K,
    certify_current_clamp_stability,
)
from pinnpcm.current_clamp.cc_b_stability_telemetry import (
    GateBook,
    StabilityTelemetryRecorder,
    TelemetryContract,
    classify_spectrum,
    deterministic_jv_probes,
    load_telemetry_contract,
    run_operator_prechecks,
)


SCHEMA_VERSION = "q2_cc_b_stability_requalification_v1"
TASK_ID = "Q2_CC_B_STABILITY_REQUALIFICATION_V1"
PASS_DISPOSITION = "PASS_CC_B_STABILITY_REQUALIFICATION"
STOP_DISPOSITION = "STOP_NUMERICAL_SEMANTICS_NOT_CLOSED"
INVALID_DISPOSITION = "INVALID_CC_B_STABILITY_REQUALIFICATION_EXECUTION"


class RequalificationContractError(RuntimeError):
    """The requalification identity or frozen numerical contract is invalid."""


class NumericalSemanticsStop(RuntimeError):
    """A preregistered numerical certification gate did not close."""


@dataclass(frozen=True)
class RequalificationContract:
    path: Path
    repository_root: Path
    raw: dict[str, Any]
    telemetry_contract: TelemetryContract

    @property
    def parent(self):
        return self.telemetry_contract.parent

    @property
    def run_id(self) -> str:
        return str(self.raw["run_id"])


@dataclass(frozen=True)
class DenseSpectrum:
    eigenvalues_per_s: np.ndarray
    eigenvectors: np.ndarray
    absolute_residual_rates_per_s: np.ndarray
    relative_residuals: np.ndarray
    rightmost_order: np.ndarray
    alpha_per_s: float
    alpha_tau: float
    stable: bool
    classification: str


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RequalificationContractError(f"{path} is not a YAML mapping")
    return payload


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _assert_ancestor(root: Path, ancestor: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RequalificationContractError(
            f"PR #33 merge {ancestor} is not an ancestor of HEAD"
        )


def _authority_path(root: Path, spec: Mapping[str, Any]) -> Path:
    path = (root / str(spec["path"])).resolve()
    if not path.is_file():
        raise RequalificationContractError(f"authority file is missing: {path}")
    expected = str(spec["sha256"])
    if file_sha256(path) != expected:
        raise RequalificationContractError(f"authority hash drifted: {path}")
    return path


def load_requalification_contract(
    path: Path | str = Path("configs/q2_cc_b_stability_requalification_v1.yaml"),
    *,
    repository_root: Path | str | None = None,
) -> RequalificationContract:
    root = (Path.cwd() if repository_root is None else Path(repository_root)).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    raw = _load_yaml(config_path)
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("task_id") != TASK_ID:
        raise RequalificationContractError("unexpected requalification task/schema")
    authority = raw["authority"]
    _assert_ancestor(root, str(authority["pr_33_merge_sha"]))
    for name in (
        "parent_cc_b_config",
        "parent_telemetry_config",
        "pr_33_terminal",
        "parent_l1_input_manifest",
        "parent_l1_input_npz",
        "parent_l2_0p2_manifest",
        "parent_l2_0p2_npz",
    ):
        _authority_path(root, authority[name])
    terminal_path = root / str(authority["pr_33_terminal"]["path"])
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    if (
        terminal.get("disposition")
        != authority["pr_33_terminal"]["required_disposition"]
        or terminal.get("closure_class")
        != authority["pr_33_terminal"]["required_closure_class"]
        or terminal.get("scientific_vote") is not False
        or int(terminal.get("formal_execution_count", -1)) != 0
        or int(terminal.get("cc_b_matrix_launch_count", -1)) != 0
    ):
        raise RequalificationContractError("PR #33 terminal identity is not eligible")
    telemetry_path = root / str(authority["parent_telemetry_config"]["path"])
    telemetry = load_telemetry_contract(telemetry_path, repository_root=root)
    stability = telemetry.parent.stability
    frozen = raw["frozen_stability"]
    expected = {
        "which": stability["which"],
        "tolerance": float(stability["tolerance"]),
        "maxiter": int(stability["maxiter"]),
        "ncv": int(stability["ncv"]),
        "relative_ritz_residual_max": float(stability["relative_ritz_residual_max"]),
        "h_half_operator_relative_difference_max": float(
            stability["h_half_operator_relative_difference_max"]
        ),
        "stable_alpha_tau_max": float(stability["stable_alpha_tau_max"]),
        "backward_error_multiplier": float(stability["backward_error_multiplier"]),
    }
    for name, value in expected.items():
        if frozen[name] != value:
            raise RequalificationContractError(f"frozen stability field drifted: {name}")
    if raw.get("scientific_vote") is not False:
        raise RequalificationContractError("requalification must remain nonvoting")
    if int(raw.get("formal_execution_count", -1)) != 0 or int(
        raw.get("cc_b_matrix_launch_count", -1)
    ) != 0:
        raise RequalificationContractError("legacy counters must remain zero")
    return RequalificationContract(config_path, root, raw, telemetry)


def analyze_dense_operator(
    matrix: np.ndarray,
    mass: np.ndarray,
    *,
    tau0_s: float,
    stable_alpha_tau_max: float,
    backward_error_multiplier: float,
) -> DenseSpectrum:
    operator = np.asarray(matrix, dtype=float)
    weights = np.asarray(mass, dtype=float)
    if operator.ndim != 2 or operator.shape[0] != operator.shape[1]:
        raise ValueError("dense operator must be square")
    if weights.shape != (operator.shape[0],) or np.any(weights <= 0.0):
        raise ValueError("mass vector is incompatible with dense operator")
    values, vectors = np.linalg.eig(operator)
    absolute: list[float] = []
    relative: list[float] = []
    for index, value in enumerate(values):
        vector = vectors[:, index]
        residual = operator @ vector - value * vector
        rho = _mass_norm(residual, weights) / max(
            _mass_norm(vector, weights), 1.0e-300
        )
        absolute.append(rho)
        relative.append(rho / max(abs(value), 1.0 / tau0_s))
    absolute_array = np.asarray(absolute, dtype=float)
    relative_array = np.asarray(relative, dtype=float)
    order = np.argsort(values.real)[::-1]
    rightmost = order[: min(6, values.size)]
    alpha = float(values[order[0]].real)
    alpha_tau = alpha * tau0_s
    rho_max = float(np.max(absolute_array[rightmost]))
    stable = bool(
        alpha_tau <= stable_alpha_tau_max
        and alpha <= -backward_error_multiplier * rho_max
    )
    classification = classify_spectrum(
        alpha_per_s=alpha,
        maximum_ritz_residual_rate_per_s=rho_max,
        tau0_s=tau0_s,
        stable=stable,
        backward_error_multiplier=backward_error_multiplier,
    )
    return DenseSpectrum(
        eigenvalues_per_s=np.asarray(values, dtype=complex),
        eigenvectors=np.asarray(vectors, dtype=complex),
        absolute_residual_rates_per_s=absolute_array,
        relative_residuals=relative_array,
        rightmost_order=order,
        alpha_per_s=alpha,
        alpha_tau=alpha_tau,
        stable=stable,
        classification=classification,
    )


def _relative_difference(left: np.ndarray, right: np.ndarray, floor: float) -> float:
    return float(
        np.linalg.norm(np.asarray(left) - np.asarray(right))
        / max(np.linalg.norm(left), np.linalg.norm(right), floor)
    )


def _temperature_sha256(temperature: np.ndarray) -> str:
    values = np.ascontiguousarray(np.asarray(temperature, dtype=np.float64))
    return sha256(values.tobytes(order="C")).hexdigest()


def _equilibrium_metrics(
    model: CurrentClamp2DModel,
    temperature: np.ndarray,
    *,
    last_scaled_update_inf: float,
) -> dict[str, Any]:
    evaluation = model.evaluate_temperature(temperature)
    ledger_max = max(
        evaluation.ledger.current_error,
        evaluation.ledger.terminal_field_power_error,
        evaluation.ledger.field_thermal_error,
    )
    return {
        "shape": list(np.asarray(temperature).shape),
        "dtype": str(np.asarray(temperature).dtype),
        "finite": bool(np.isfinite(temperature).all()),
        "temperature_min_K": float(np.min(temperature)),
        "temperature_max_K": float(np.max(temperature)),
        "temperature_sha256": _temperature_sha256(temperature),
        "device_voltage_V": float(evaluation.device_voltage_V),
        "scaled_thermal_residual_inf": float(evaluation.scaled_thermal_residual_inf),
        "last_scaled_update_inf": float(last_scaled_update_inf),
        "scaled_electrical_residual_inf": float(
            evaluation.scaled_electrical_residual_inf
        ),
        "maximum_ledger_error": float(ledger_max),
        "finite_and_range_legal": bool(evaluation.finite_and_range_legal),
    }


def _equilibrium_passes(contract: RequalificationContract, metrics: Mapping[str, Any]) -> bool:
    gates = contract.raw["equilibrium_input_gates"]
    lower, upper = map(float, gates["temperature_K"])
    return bool(
        metrics["finite"]
        and metrics["finite_and_range_legal"]
        and metrics["scaled_thermal_residual_inf"]
        <= float(gates["thermal_scaled_cv_residual_max"])
        and metrics["last_scaled_update_inf"]
        <= float(gates["last_scaled_update_inf_max"])
        and metrics["scaled_electrical_residual_inf"]
        <= float(gates["electrical_scaled_cv_residual_max"])
        and metrics["maximum_ledger_error"]
        <= float(gates["ledger_symmetric_relative_max"])
        and metrics["temperature_min_K"] >= lower
        and metrics["temperature_max_K"] <= upper
        and metrics["device_voltage_V"]
        <= float(gates["voltage_operating_envelope_max_V"])
    )


def _load_verified_temperature(
    contract: RequalificationContract,
    *,
    manifest_key: str,
    npz_key: str,
    model: CurrentClamp2DModel,
) -> tuple[np.ndarray, dict[str, Any]]:
    authority = contract.raw["authority"]
    manifest_path = _authority_path(contract.repository_root, authority[manifest_key])
    npz_path = _authority_path(contract.repository_root, authority[npz_key])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("npz_sha256") != authority[npz_key]["sha256"]:
        raise RequalificationContractError("manifest and frozen NPZ identity disagree")
    with np.load(npz_path, allow_pickle=False) as payload:
        temperature = np.asarray(payload["temperature_K"], dtype=float)
    metrics = _equilibrium_metrics(
        model,
        temperature,
        last_scaled_update_inf=float(manifest["last_scaled_update_inf"]),
    )
    if temperature.shape != model.grid.shape or not _equilibrium_passes(contract, metrics):
        raise RequalificationContractError("authenticated equilibrium input failed gates")
    metrics.update(
        {
            "manifest_path": manifest_path.as_posix(),
            "manifest_sha256": file_sha256(manifest_path),
            "npz_path": npz_path.as_posix(),
            "npz_sha256": file_sha256(npz_path),
        }
    )
    return temperature, metrics


def _run_step_diagnostics(
    contract: RequalificationContract,
    model: CurrentClamp2DModel,
    temperature: np.ndarray,
    root: Path,
) -> dict[str, Any]:
    recorder = StabilityTelemetryRecorder(root / "telemetry", model=model, checkpoint_interval=64)
    gates = GateBook()
    parent_prechecks = run_operator_prechecks(
        contract.telemetry_contract, model, temperature, recorder, gates
    )
    probe, _ = deterministic_jv_probes(model)
    outputs: dict[float, np.ndarray] = {}
    steps: dict[str, float] = {}
    for multiplier in tuple(float(value) for value in contract.raw["frozen_stability"]["step_multipliers"]):
        role = f"requalification_step_{multiplier:g}h"
        outputs[multiplier] = _apply_operator(
            model,
            temperature,
            probe,
            CCBStabilityTelemetry(),
            step_multiplier=multiplier,
            recorder=recorder,
            call_role=role,
        )
        steps[f"{multiplier:g}"] = centered_jv_step_size_K(
            temperature, probe, step_multiplier=multiplier
        )
    recorder.checkpoint()
    floor = 1.0 / model.tau0_s
    h_half = _relative_difference(outputs[1.0], outputs[0.5], floor)
    two_h = _relative_difference(outputs[2.0], outputs[1.0], floor)
    h_quarter = _relative_difference(outputs[0.5], outputs[0.25], floor)
    frozen = contract.raw["frozen_stability"]
    passed = bool(
        parent_prechecks
        and h_half <= float(frozen["h_half_operator_relative_difference_max"])
        and two_h <= float(frozen["two_h_operator_relative_difference_max"])
    )
    payload = {
        "schema_version": "q2_cc_b_stability_requalification_steps_v1",
        "passed": passed,
        "step_size_K_by_multiplier": steps,
        "h_vs_h_half_relative_difference": h_half,
        "two_h_vs_h_relative_difference": two_h,
        "h_half_vs_h_quarter_nonvoting_relative_difference": h_quarter,
        "parent_prechecks": gates.rows(),
        "h_quarter_vote_role": "nonvoting_roundoff_observation",
    }
    atomic_write_json(root / "summary.json", payload)
    atomic_write_npz(
        root / "jv_step_outputs.npz",
        probe=probe,
        jv_two_h=outputs[2.0],
        jv_h=outputs[1.0],
        jv_h_half=outputs[0.5],
        jv_h_quarter=outputs[0.25],
    )
    return payload


def _run_spectrum(
    contract: RequalificationContract,
    model: CurrentClamp2DModel,
    temperature: np.ndarray,
    *,
    eigenpairs: int,
    root: Path,
) -> tuple[CCBStabilityOutcome, dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=False)
    recorder = StabilityTelemetryRecorder(root / "telemetry", model=model, checkpoint_interval=64)
    outcome = certify_current_clamp_stability(
        model,
        temperature_K=temperature,
        eigenpairs=eigenpairs,
        recorder=recorder,
    )
    counts_pass = bool(
        recorder.requested_pair_count == eigenpairs
        and recorder.returned_pair_count == eigenpairs
        and recorder.finite_pair_count == eigenpairs
        and recorder.certified_pair_count == eigenpairs
    )
    valid = bool(outcome.success and counts_pass)
    maximum_eta = recorder.maximum_relative_ritz_residual
    maximum_rho = recorder.maximum_absolute_ritz_residual_rate_per_s
    classification = "NOT_APPLICABLE"
    if valid and maximum_rho is not None:
        classification = classify_spectrum(
            alpha_per_s=outcome.rightmost_spectral_abscissa_per_s,
            maximum_ritz_residual_rate_per_s=maximum_rho,
            tau0_s=model.tau0_s,
            stable=outcome.stable,
            backward_error_multiplier=float(
                contract.parent.stability["backward_error_multiplier"]
            ),
        )
    summary = {
        "schema_version": "q2_cc_b_stability_requalification_spectrum_v1",
        "grid": f"L{model.spatial_level}",
        "eigenpairs_requested": int(eigenpairs),
        "valid": valid,
        "outcome_code": outcome.code,
        "failure_detail": outcome.telemetry.failure_detail,
        "requested_pair_count": recorder.requested_pair_count,
        "returned_pair_count": recorder.returned_pair_count,
        "finite_pair_count": recorder.finite_pair_count,
        "certified_pair_count": recorder.certified_pair_count,
        "maximum_relative_ritz_residual": maximum_eta,
        "maximum_absolute_ritz_residual_rate_per_s": maximum_rho,
        "h_half_operator_relative_difference": (
            recorder.h_half_operator_relative_difference
        ),
        "rightmost_spectral_abscissa_per_s": (
            float(outcome.rightmost_spectral_abscissa_per_s) if valid else None
        ),
        "alpha_tau_dimensionless": (
            float(outcome.alpha_tau_dimensionless) if valid else None
        ),
        "physical_spectrum_classification": classification,
        "stable": bool(outcome.stable) if valid else None,
        "wall_time_s": float(outcome.telemetry.wall_time_s),
        "cpu_time_s": float(outcome.telemetry.cpu_time_s),
    }
    atomic_write_json(root / "summary.json", summary)
    return outcome, summary


def _build_dense_reference(
    contract: RequalificationContract,
    model: CurrentClamp2DModel,
    temperature: np.ndarray,
    arpack_summary: Mapping[str, Any],
    root: Path,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=False)
    n = temperature.size
    matrix = np.empty((n, n), dtype=float)
    recorder = StabilityTelemetryRecorder(root / "telemetry", model=model, checkpoint_interval=64)
    telemetry = CCBStabilityTelemetry()
    for index in range(n):
        direction = np.zeros(n, dtype=float)
        direction[index] = 1.0
        matrix[:, index] = _apply_operator(
            model,
            temperature,
            direction,
            telemetry,
            recorder=recorder,
            call_role=f"dense_basis_{index}",
        )
    recorder.checkpoint()
    dense = analyze_dense_operator(
        matrix,
        model.cell_capacity_J_K,
        tau0_s=model.tau0_s,
        stable_alpha_tau_max=float(contract.parent.stability["stable_alpha_tau_max"]),
        backward_error_multiplier=float(
            contract.parent.stability["backward_error_multiplier"]
        ),
    )
    maximum_eta = float(np.max(dense.relative_residuals))
    alpha_difference = abs(
        dense.alpha_tau - float(arpack_summary["alpha_tau_dimensionless"])
    )
    passed = bool(
        maximum_eta
        <= float(contract.raw["frozen_stability"]["dense_relative_residual_max"])
        and dense.classification
        == str(arpack_summary["physical_spectrum_classification"])
        and alpha_difference
        <= float(
            contract.raw["frozen_stability"][
                "dense_arpack_alpha_tau_difference_max"
            ]
        )
    )
    atomic_write_npz(
        root / "dense_operator_and_spectrum.npz",
        operator_per_s=matrix,
        eigenvalues_real_per_s=dense.eigenvalues_per_s.real,
        eigenvalues_imag_per_s=dense.eigenvalues_per_s.imag,
        eigenvectors_real=dense.eigenvectors.real,
        eigenvectors_imag=dense.eigenvectors.imag,
        absolute_ritz_residual_rates_per_s=dense.absolute_residual_rates_per_s,
        relative_ritz_residuals=dense.relative_residuals,
        rightmost_order=dense.rightmost_order,
    )
    summary = {
        "schema_version": "q2_cc_b_stability_dense_reference_v1",
        "representation": "independent_eigensolver_same_centered_jv_operator",
        "state_dimension": n,
        "passed": passed,
        "maximum_relative_eigenpair_residual": maximum_eta,
        "rightmost_spectral_abscissa_per_s": dense.alpha_per_s,
        "alpha_tau_dimensionless": dense.alpha_tau,
        "physical_spectrum_classification": dense.classification,
        "stable": dense.stable,
        "arpack_alpha_tau_absolute_difference": alpha_difference,
        "arpack_classification": arpack_summary["physical_spectrum_classification"],
        "matrix_vector_products": telemetry.matrix_vector_products,
        "dynamic_rhs_evaluations": telemetry.dynamic_rhs_evaluations,
    }
    atomic_write_json(root / "summary.json", summary)
    return summary


def _write_manifest(root: Path, repository_root: Path, *, run_id: str) -> dict[str, Any]:
    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    payload = {
        "schema_version": "q2_cc_b_stability_requalification_manifest_v1",
        "run_id": run_id,
        "artifacts": [
            {
                "path": path.relative_to(repository_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in files
        ],
    }
    atomic_write_json(root / "artifact_manifest.json", payload)
    return payload


def _stable_value(classification: str) -> bool | None:
    if classification == "STABLE_MARGIN_PASS":
        return True
    if classification in ("POSITIVE_UNSTABLE", "NEGATIVE_MARGIN_INSUFFICIENT"):
        return False
    return None


def run_requalification(
    config_path: Path | str,
    *,
    repository_root: Path | str | None = None,
) -> dict[str, Any]:
    contract = load_requalification_contract(
        config_path, repository_root=repository_root
    )
    root = contract.repository_root
    compact_root = root / str(contract.raw["outputs"]["compact_root"]) / contract.run_id
    processed_root = root / str(contract.raw["outputs"]["processed_root"]) / contract.run_id
    compact_root.mkdir(parents=True, exist_ok=False)
    processed_root.mkdir(parents=True, exist_ok=False)
    wall_started = perf_counter()
    cpu_started = process_time()
    phase_results: dict[str, Any] = {}
    disposition = INVALID_DISPOSITION
    validity = "invalid"
    certification = "INVALID"
    classification = "NOT_APPLICABLE"
    detail = "execution did not reach a registered terminal"
    terminal_written = False
    try:
        head = _git_head(root)
        identity = {
            "schema_version": "q2_cc_b_stability_requalification_identity_v1",
            "task_id": TASK_ID,
            "run_id": contract.run_id,
            "git_sha": head,
            "pr_33_merge_sha": contract.raw["authority"]["pr_33_merge_sha"],
            "config_path": contract.path.relative_to(root).as_posix(),
            "config_sha256": file_sha256(contract.path),
            "scientific_vote": False,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
            "workers": 1,
            "blas_threads": 1,
        }
        atomic_write_json(compact_root / "identity.json", identity)

        l1_model = build_cc_b_model(
            contract.parent,
            spatial_level=1,
            current_set_A=4.0e-4,
            branch="heating",
            defect="NOM",
        )
        l1_temperature, l1_metrics = _load_verified_temperature(
            contract,
            manifest_key="parent_l1_input_manifest",
            npz_key="parent_l1_input_npz",
            model=l1_model,
        )
        atomic_write_json(compact_root / "inputs" / "l1_parent_reference.json", l1_metrics)
        phase_results["l1_input"] = l1_metrics

        r1_started = perf_counter()
        step_summary = _run_step_diagnostics(
            contract,
            l1_model,
            l1_temperature,
            compact_root / "R1" / "step_diagnostics",
        )
        phase_results["step_diagnostics"] = step_summary
        if not step_summary["passed"]:
            raise NumericalSemanticsStop("L1 componentwise Jv step diagnostics failed")
        _, l1_k6 = _run_spectrum(
            contract,
            l1_model,
            l1_temperature,
            eigenpairs=6,
            root=compact_root / "R1" / "L1_k6",
        )
        phase_results["L1_k6"] = l1_k6
        if not l1_k6["valid"]:
            raise NumericalSemanticsStop("corrected L1/k6 did not pass Ritz certification")
        dense = _build_dense_reference(
            contract,
            l1_model,
            l1_temperature,
            l1_k6,
            processed_root / "R1" / "L1_dense_reference",
        )
        phase_results["L1_dense_reference"] = dense
        if not dense["passed"]:
            raise NumericalSemanticsStop("L1 dense/ARPACK reference gate failed")
        r1_wall = perf_counter() - r1_started
        if r1_wall > float(contract.raw["budget"]["r1_wall_cap_s"]):
            raise NumericalSemanticsStop("R1 wall budget was exceeded")

        r2_started = perf_counter()
        _, l1_k10 = _run_spectrum(
            contract,
            l1_model,
            l1_temperature,
            eigenpairs=10,
            root=compact_root / "R2" / "L1_k10",
        )
        phase_results["L1_k10"] = l1_k10
        if not l1_k10["valid"]:
            raise NumericalSemanticsStop("L1/k10 did not pass Ritz certification")
        if abs(
            float(l1_k6["alpha_tau_dimensionless"])
            - float(l1_k10["alpha_tau_dimensionless"])
        ) > float(contract.raw["frozen_stability"]["k6_k10_alpha_tau_difference_max"]):
            raise NumericalSemanticsStop("L1 k6/k10 rightmost spectrum is inconsistent")

        l2_parent_model = build_cc_b_model(
            contract.parent,
            spatial_level=2,
            current_set_A=2.0e-4,
            branch="heating",
            defect="NOM",
        )
        l2_initial, l2_parent_metrics = _load_verified_temperature(
            contract,
            manifest_key="parent_l2_0p2_manifest",
            npz_key="parent_l2_0p2_npz",
            model=l2_parent_model,
        )
        atomic_write_json(
            compact_root / "inputs" / "l2_parent_0p2mA_reference.json",
            l2_parent_metrics,
        )
        l2_model = build_cc_b_model(
            contract.parent,
            spatial_level=2,
            current_set_A=4.0e-4,
            branch="heating",
            defect="NOM",
        )
        l2_solve = solve_cc_b_equilibrium(
            l2_model, initial_temperature_K=l2_initial
        )
        if (
            not l2_solve.success
            or l2_solve.temperature_K is None
            or l2_solve.evaluation is None
        ):
            raise NumericalSemanticsStop(
                f"L2 0.4 mA equilibrium failed: {l2_solve.code}"
            )
        l2_metrics = _equilibrium_metrics(
            l2_model,
            l2_solve.temperature_K,
            last_scaled_update_inf=l2_solve.last_scaled_update_inf,
        )
        if not _equilibrium_passes(contract, l2_metrics):
            raise NumericalSemanticsStop("L2 0.4 mA equilibrium failed input gates")
        l2_artifact = save_cc_b_equilibrium(
            processed_root,
            compact_root,
            identity="NOM_heating_0p4mA_L2",
            solve=l2_solve,
            stability=None,
            metadata={
                "run_id": contract.run_id,
                "input_role": "requalification_L2_equilibrium",
                "scientific_vote": False,
                "formal_execution_count": 0,
                "cc_b_matrix_launch_count": 0,
            },
        )
        l2_metrics["artifact"] = l2_artifact
        phase_results["l2_input"] = l2_metrics
        _, l2_k6 = _run_spectrum(
            contract,
            l2_model,
            l2_solve.temperature_K,
            eigenpairs=6,
            root=compact_root / "R2" / "L2_k6",
        )
        phase_results["L2_k6"] = l2_k6
        if not l2_k6["valid"]:
            raise NumericalSemanticsStop("L2/k6 did not pass Ritz certification")
        _, l2_k10 = _run_spectrum(
            contract,
            l2_model,
            l2_solve.temperature_K,
            eigenpairs=10,
            root=compact_root / "R2" / "L2_k10",
        )
        phase_results["L2_k10"] = l2_k10
        if not l2_k10["valid"]:
            raise NumericalSemanticsStop("L2/k10 did not pass Ritz certification")
        if abs(
            float(l2_k6["alpha_tau_dimensionless"])
            - float(l2_k10["alpha_tau_dimensionless"])
        ) > float(contract.raw["frozen_stability"]["k6_k10_alpha_tau_difference_max"]):
            raise NumericalSemanticsStop("L2 k6/k10 rightmost spectrum is inconsistent")
        classes = {
            str(item["physical_spectrum_classification"])
            for item in (l1_k6, l1_k10, l2_k6, l2_k10)
        }
        if len(classes) != 1:
            raise NumericalSemanticsStop("L1/L2 physical spectrum classifications disagree")
        r2_wall = perf_counter() - r2_started
        if r2_wall > float(contract.raw["budget"]["r2_wall_cap_s"]):
            raise NumericalSemanticsStop("R2 wall budget was exceeded")
        classification = classes.pop()
        disposition = PASS_DISPOSITION
        validity = "valid"
        certification = "VALID"
        detail = "all preregistered L1/L2 k6/k10 and dense-reference gates passed"
    except NumericalSemanticsStop as exc:
        disposition = STOP_DISPOSITION
        validity = "valid"
        certification = "INVALID"
        classification = "NOT_APPLICABLE"
        detail = str(exc)
    except Exception as exc:
        disposition = INVALID_DISPOSITION
        validity = "invalid"
        certification = "INVALID"
        classification = "NOT_APPLICABLE"
        detail = f"{type(exc).__name__}: {exc}"
    finally:
        wall_time = perf_counter() - wall_started
        cpu_time = process_time() - cpu_started
        if (
            wall_time > float(contract.raw["budget"]["total_calendar_wall_cap_s"])
            or cpu_time > float(contract.raw["budget"]["aggregate_cpu_cap_s"])
        ):
            disposition = STOP_DISPOSITION
            validity = "valid"
            certification = "INVALID"
            classification = "NOT_APPLICABLE"
            detail = "global requalification budget was exceeded"
        terminal = {
            "schema_version": "q2_cc_b_stability_requalification_terminal_v1",
            "task_id": TASK_ID,
            "run_id": contract.run_id,
            "disposition": disposition,
            "validity": validity,
            "lifecycle_state": "executed",
            "claim_status": "forbidden",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
            "stability_certification_status": certification,
            "physical_spectrum_classification": classification,
            "stable": _stable_value(classification) if certification == "VALID" else None,
            "phase_results": phase_results,
            "wall_time_s": wall_time,
            "cpu_time_s": cpu_time,
            "detail": detail,
            "cc_b_scientific_pass": False,
            "uniform_gate_executed": False,
            "formal_matrix_executed": False,
            "pinn_executed": False,
        }
        atomic_write_json(compact_root / "summary.json", phase_results)
        atomic_write_json(compact_root / "terminal.json", terminal)
        reloaded = json.loads((compact_root / "terminal.json").read_text(encoding="utf-8"))
        if reloaded.get("disposition") != disposition:
            raise RuntimeError("terminal readback changed disposition")
        _write_manifest(processed_root, root, run_id=contract.run_id)
        _write_manifest(compact_root, root, run_id=contract.run_id)
        terminal_written = True
    if not terminal_written:
        raise RuntimeError("terminal was not written")
    return terminal


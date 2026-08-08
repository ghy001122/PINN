"""Bounded branch-stability and transition bracket for the frozen CC-B model."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
from time import perf_counter, process_time, time
from typing import Any, Iterable, Mapping

import numpy as np
import yaml

from pinnpcm.current_clamp.artifacts import (
    atomic_write_csv,
    atomic_write_json,
    environment_record,
    file_sha256,
)
from pinnpcm.current_clamp.cc_b_artifacts import save_cc_b_equilibrium
from pinnpcm.current_clamp.cc_b_model import CurrentClamp2DModel, build_cc_b_model
from pinnpcm.current_clamp.cc_b_solver import (
    prolong_temperature,
    solve_cc_b_equilibrium,
)
from pinnpcm.current_clamp.cc_b_stability_requalification import (
    RequalificationContract,
    _equilibrium_metrics,
    _equilibrium_passes,
    _run_spectrum,
    _run_step_diagnostics,
    load_requalification_contract,
)


SCHEMA_VERSION = "q2_cc_b_branch_stability_transition_bracket_v1"
TASK_ID = "Q2_CC_B_BRANCH_STABILITY_TRANSITION_BRACKET_V1"
PASS_DISPOSITION = "PASS_CC_B_BRANCH_STABILITY_TRANSITION_BRACKET"
COVERAGE_DISPOSITION = "STOP_CC_B_BRANCH_COVERAGE_INCOMPLETE"
PATTERN_DISPOSITION = "STOP_CC_B_PATTERNED_BRANCH_REQUIRED"
NO_GO_DISPOSITION = "NO_GO_CC_B_NOMINAL_TRANSITION_DOMAIN"
SEMANTICS_DISPOSITION = "STOP_NUMERICAL_SEMANTICS_NOT_CLOSED"
INVALID_DISPOSITION = "INVALID_CC_B_BRANCH_STABILITY_TRANSITION_BRACKET_EXECUTION"
TERMINAL_DISPOSITIONS = frozenset(
    {
        PASS_DISPOSITION,
        COVERAGE_DISPOSITION,
        PATTERN_DISPOSITION,
        NO_GO_DISPOSITION,
        SEMANTICS_DISPOSITION,
        INVALID_DISPOSITION,
    }
)
BRANCHES = ("heating", "cooling")


class BracketContractError(RuntimeError):
    """A frozen authority or preregistered bracket field is invalid."""


class BracketExecutionError(RuntimeError):
    """The artifact/runner path failed independently of the physics result."""


@dataclass(frozen=True)
class BracketContract:
    path: Path
    repository_root: Path
    raw: dict[str, Any]
    requalification: RequalificationContract

    @property
    def run_id(self) -> str:
        return str(self.raw["run_id"])

    @property
    def parent(self):
        return self.requalification.parent

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


POINT_FIELDS = (
    "branch",
    "current_A",
    "current_mA",
    "stage",
    "grid",
    "execution_role",
    "equilibrium_valid",
    "equilibrium_code",
    "spectrum_valid",
    "spectrum_code",
    "physical_spectrum_classification",
    "stable",
    "stable_continuation_connected",
    "continuation_role",
    "active_area_mean_conductive_state",
    "transition_area_fraction",
    "transition_bearing",
    "temperature_mean_K",
    "temperature_min_K",
    "temperature_max_K",
    "device_voltage_V",
    "scaled_thermal_residual_inf",
    "last_scaled_update_inf",
    "scaled_electrical_residual_inf",
    "maximum_ledger_error",
    "requested_pair_count",
    "returned_pair_count",
    "finite_pair_count",
    "certified_pair_count",
    "maximum_relative_ritz_residual",
    "maximum_absolute_ritz_residual_rate_per_s",
    "rightmost_spectral_abscissa_per_s",
    "alpha_tau_dimensionless",
    "h_vs_h_half_relative_difference",
    "two_h_vs_h_relative_difference",
    "equilibrium_manifest_path",
    "equilibrium_manifest_sha256",
    "equilibrium_npz_path",
    "equilibrium_npz_sha256",
    "spectrum_summary_path",
    "spectrum_ritz_path",
    "failure_detail",
)

MODE_FIELDS = (
    "branch",
    "current_A",
    "current_mA",
    "stage",
    "grid",
    "physical_spectrum_classification",
    "eigenvalue_real_per_s",
    "eigenvalue_imag_per_s",
    "uniform_mass_overlap",
    "x_gradient_energy_fraction",
    "y_gradient_energy_fraction",
    "participation_ratio",
    "dominant_spatial_axis",
    "dominant_transverse_mode_index",
    "mode_classification",
    "vote_role",
)

BOUNDARY_FIELDS = (
    "branch",
    "bracket_index",
    "iteration",
    "lower_current_A",
    "upper_current_A",
    "midpoint_current_A",
    "lower_stable",
    "upper_stable",
    "midpoint_stable",
    "midpoint_spectrum_valid",
    "midpoint_alpha_tau",
    "midpoint_ritz_uncertainty_tau",
    "alpha_zero_bracketed",
    "status",
    "wording",
)

ANCHOR_FIELDS = (
    "branch",
    "anchor_role",
    "current_A",
    "current_mA",
    "source_component_low_A",
    "source_component_high_A",
    "sampled_span_A",
    "l1_k6_valid",
    "l1_k10_valid",
    "l1_k6_k10_alpha_tau_difference",
    "l1_classification",
    "l2_equilibrium_valid",
    "l2_k6_valid",
    "l2_k10_valid",
    "l2_k6_k10_alpha_tau_difference",
    "l2_classification",
    "l1_l2_classification_equal",
    "l2_active_area_mean_conductive_state",
    "l2_transition_area_fraction",
    "l2_transition_bearing",
    "anchor_pass",
    "failure_detail",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BracketContractError(f"{path} must contain a YAML mapping")
    return payload


def _authority_path(root: Path, spec: Mapping[str, Any]) -> Path:
    path = (root / str(spec["path"])).resolve()
    if not path.is_file():
        raise BracketContractError(f"authority file is missing: {path}")
    if file_sha256(path) != str(spec["sha256"]).lower():
        raise BracketContractError(f"authority hash drifted: {path}")
    return path


def _assert_ancestor(root: Path, ancestor: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BracketContractError(f"required merge is not an ancestor: {ancestor}")


def _exact_float(observed: Any, expected: float, name: str) -> None:
    value = float(observed)
    if not math.isfinite(value) or not math.isclose(
        value, expected, rel_tol=0.0, abs_tol=0.0
    ):
        raise BracketContractError(f"frozen field drifted: {name}")


def load_bracket_contract(
    path: Path | str = Path(
        "configs/q2_cc_b_branch_stability_transition_bracket_v1.yaml"
    ),
    *,
    repository_root: Path | str | None = None,
) -> BracketContract:
    root = (Path.cwd() if repository_root is None else Path(repository_root)).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    raw = _load_yaml(config_path)
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("task_id") != TASK_ID:
        raise BracketContractError("unexpected bracket task/schema identity")
    authority = raw["authority"]
    _assert_ancestor(root, str(authority["pr_34_merge_sha"]))
    for name in (
        "cc_a_config",
        "cc_a_all_roots",
        "parent_cc_b_config",
        "requalification_config",
        "pr_34_terminal",
        "pr_34_summary",
        "pr_34_manifest",
        "pr_34_l1_input_manifest",
        "pr_34_l1_input_npz",
        "pr_34_l1_step_summary",
        "pr_34_l1_k6_summary",
        "pr_34_l1_k6_ritz",
    ):
        _authority_path(root, authority[name])
    for spec in authority["frozen_core_files"]:
        _authority_path(root, spec)
    terminal_path = _authority_path(root, authority["pr_34_terminal"])
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    if (
        terminal.get("disposition")
        != authority["pr_34_terminal"]["required_disposition"]
        or terminal.get("physical_spectrum_classification")
        != authority["pr_34_terminal"]["required_classification"]
        or terminal.get("stability_certification_status") != "VALID"
        or terminal.get("scientific_vote") is not False
        or int(terminal.get("formal_execution_count", -1)) != 0
        or int(terminal.get("cc_b_matrix_launch_count", -1)) != 0
    ):
        raise BracketContractError("PR #34 terminal is not eligible for reuse")
    requalification = load_requalification_contract(
        _authority_path(root, authority["requalification_config"]),
        repository_root=root,
    )
    parent = requalification.parent
    frozen = raw["frozen_stability"]
    exact = {
        "tolerance": float(parent.stability["tolerance"]),
        "relative_ritz_residual_max": float(
            parent.stability["relative_ritz_residual_max"]
        ),
        "h_half_operator_relative_difference_max": float(
            parent.stability["h_half_operator_relative_difference_max"]
        ),
        "stable_alpha_tau_max": float(parent.stability["stable_alpha_tau_max"]),
        "backward_error_multiplier": float(
            parent.stability["backward_error_multiplier"]
        ),
        "k6_k10_alpha_tau_difference_max": float(
            parent.stability["comparison_alpha_tau_difference_max"]
        ),
    }
    for name, expected in exact.items():
        _exact_float(frozen[name], expected, f"frozen_stability.{name}")
    if (
        frozen["which"] != parent.stability["which"]
        or int(frozen["maxiter"]) != int(parent.stability["maxiter"])
        or int(frozen["ncv"]) != int(parent.stability["ncv"])
    ):
        raise BracketContractError("ARPACK identity drifted")
    currents = tuple(float(value) for value in raw["scope"]["fixed_currents_A"])
    expected = tuple(index * 5.0e-5 for index in range(2, 15))
    if (
        len(currents) != len(expected)
        or any(
            not math.isclose(actual, reference, rel_tol=0.0, abs_tol=1.0e-15)
            for actual, reference in zip(currents, expected, strict=True)
        )
        or len(set(currents)) != 13
    ):
        raise BracketContractError("fixed current lattice drifted")
    if set(raw["terminal_dispositions"]) != TERMINAL_DISPOSITIONS:
        raise BracketContractError("terminal disposition vocabulary drifted")
    if (
        raw.get("scientific_vote") is not False
        or int(raw.get("formal_execution_count", -1)) != 0
        or int(raw.get("cc_b_matrix_launch_count", -1)) != 0
    ):
        raise BracketContractError("global counters must remain zero")
    if int(raw["budget"]["workers"]) != 1 or int(
        raw["budget"]["blas_threads"]
    ) != 1:
        raise BracketContractError("execution must remain single worker/thread")
    return BracketContract(config_path, root, raw, requalification)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_token(current_A: float) -> str:
    text = f"{current_A * 1.0e3:.8f}".rstrip("0").rstrip(".")
    return text.replace(".", "p") + "mA"


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _optional_bool(value: Any) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    return _bool(value)


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_cc_a_roots(contract: BracketContract) -> dict[str, list[dict[str, Any]]]:
    path = _authority_path(
        contract.repository_root, contract.raw["authority"]["cc_a_all_roots"]
    )
    result: dict[str, list[dict[str, Any]]] = {branch: [] for branch in BRANCHES}
    for raw in _read_csv(path):
        if raw["branch"] not in result or not _bool(raw["certified"]):
            raise BracketContractError("CC-A all_roots contains an ineligible row")
        result[raw["branch"]].append(
            {
                "current_A": float(raw["current_A"]),
                "temperature_K": float(raw["temperature_K"]),
                "conductive_state": float(raw["conductive_state"]),
                "device_voltage_V": float(raw["device_voltage_V"]),
                "alpha_tau_dimensionless": float(raw["alpha_tau_dimensionless"]),
                "stable": _bool(raw["stable"]),
            }
        )
    for branch in BRANCHES:
        result[branch].sort(key=lambda row: row["current_A"])
        if len(result[branch]) != 7:
            raise BracketContractError(f"CC-A branch cardinality drifted: {branch}")
    return result


def cc_a_temperature_predictor(
    roots: Mapping[str, list[dict[str, Any]]], branch: str, current_A: float
) -> float:
    rows = roots[branch]
    currents = np.asarray([row["current_A"] for row in rows], dtype=float)
    temperatures = np.asarray([row["temperature_K"] for row in rows], dtype=float)
    if current_A < currents[0] or current_A > currents[-1]:
        raise ValueError("predictor current lies outside the frozen CC-A range")
    return float(np.interp(current_A, currents, temperatures))


def build_registered_nominal_model(
    contract: BracketContract,
    *,
    spatial_level: int,
    current_set_A: float,
    branch: str,
) -> CurrentClamp2DModel:
    lower = float(contract.raw["scope"]["current_min_A"])
    upper = float(contract.raw["scope"]["current_max_A"])
    if branch not in BRANCHES or not (lower <= current_set_A <= upper):
        raise ValueError("branch/current is outside the bracket contract")
    template = build_cc_b_model(
        contract.parent,
        spatial_level=spatial_level,
        current_set_A=2.0e-4,
        branch=branch,
        defect="NOM",
    )
    return replace(template, current_set_A=float(current_set_A))


def _transition_metrics(
    contract: BracketContract, conductive_state: np.ndarray
) -> tuple[float, float, bool]:
    state = np.asarray(conductive_state, dtype=float)
    lower, upper = map(
        float, contract.raw["transition_gate"]["conductive_state_interval"]
    )
    mean = float(np.mean(state))
    fraction = float(np.mean((state >= lower) & (state <= upper)))
    passed = bool(
        lower <= mean <= upper
        and fraction >= float(contract.raw["transition_gate"]["area_fraction_min"])
    )
    return mean, fraction, passed


def mode_metrics(
    model: CurrentClamp2DModel,
    eigenvalue: complex,
    eigenvector: np.ndarray,
) -> dict[str, Any]:
    vector = np.asarray(eigenvector, dtype=complex).reshape(-1)
    if vector.size != model.grid.nx * model.grid.ny or not np.isfinite(vector).all():
        raise ValueError("rightmost eigenmode is incompatible with the grid")
    mass = np.asarray(model.cell_capacity_J_K, dtype=float)
    energy = float(np.sum(mass * np.abs(vector) ** 2))
    if not math.isfinite(energy) or energy <= 0.0:
        raise ValueError("rightmost eigenmode has zero/invalid mass energy")
    ones_energy = float(np.sum(mass))
    overlap = float(abs(np.sum(mass * vector)) ** 2 / (ones_energy * energy))
    participation = float(
        energy**2
        / max(ones_energy * float(np.sum(mass * np.abs(vector) ** 4)), 1.0e-300)
    )
    field = vector.reshape(model.grid.shape)
    dx = float(np.mean(np.diff(model.grid.x_centers_m)))
    dy = float(np.mean(np.diff(model.grid.y_centers_m)))
    ex = float(np.sum(np.abs(np.diff(field, axis=1) / dx) ** 2))
    ey = float(np.sum(np.abs(np.diff(field, axis=0) / dy) ** 2))
    total_gradient = ex + ey
    x_fraction = ex / total_gradient if total_gradient > 0.0 else 0.0
    y_fraction = ey / total_gradient if total_gradient > 0.0 else 0.0
    profile = np.mean(field, axis=1)
    indices = np.arange(model.grid.ny, dtype=float)
    basis = np.asarray(
        [
            np.cos(math.pi * mode * (indices + 0.5) / model.grid.ny)
            for mode in range(model.grid.ny)
        ],
        dtype=float,
    )
    coefficients = basis @ profile
    transverse_index = int(np.argmax(np.abs(coefficients) ** 2))
    return {
        "eigenvalue_real_per_s": float(eigenvalue.real),
        "eigenvalue_imag_per_s": float(eigenvalue.imag),
        "uniform_mass_overlap": overlap,
        "x_gradient_energy_fraction": x_fraction,
        "y_gradient_energy_fraction": y_fraction,
        "participation_ratio": participation,
        "dominant_spatial_axis": (
            "y_transverse" if y_fraction > x_fraction else "x_current_path"
        ),
        "dominant_transverse_mode_index": transverse_index,
    }


def classify_mode(contract: BracketContract, metrics: Mapping[str, Any]) -> str:
    gate = contract.raw["mode_diagnostics"]
    overlap = float(metrics["uniform_mass_overlap"])
    x_fraction = float(metrics["x_gradient_energy_fraction"])
    y_fraction = float(metrics["y_gradient_energy_fraction"])
    if overlap >= float(gate["uniform_mass_overlap_min"]):
        return "uniform-like"
    if (
        overlap <= float(gate["localized_uniform_overlap_max"])
        and y_fraction >= float(gate["dominant_gradient_fraction_min"])
    ):
        return "transverse-dominated"
    if (
        overlap <= float(gate["localized_uniform_overlap_max"])
        and x_fraction >= float(gate["dominant_gradient_fraction_min"])
    ):
        return "longitudinal-dominated"
    return "mixed"


def continuation_connected(
    *,
    chain_active: bool,
    equilibrium_valid: bool,
    spectrum_valid: bool,
    stable: bool | None,
) -> bool:
    """A broken discrete stable-continuation chain can never be restored."""

    return bool(chain_active and equilibrium_valid and spectrum_valid and stable is True)


def select_terminal_disposition(
    *, branch_pass: Mapping[str, bool], patterned: bool, numeric_invalid: bool
) -> str:
    if numeric_invalid:
        return SEMANTICS_DISPOSITION
    heating = bool(branch_pass.get("heating", False))
    cooling = bool(branch_pass.get("cooling", False))
    if heating and cooling:
        return PASS_DISPOSITION
    if heating != cooling:
        return COVERAGE_DISPOSITION
    if patterned:
        return PATTERN_DISPOSITION
    return NO_GO_DISPOSITION


def refine_bracket_side(
    lower_A: float,
    upper_A: float,
    *,
    lower_stable: bool,
    midpoint_stable: bool,
) -> tuple[float, float]:
    """Return the next deterministic qualification-change bracket."""

    if not lower_A < upper_A:
        raise ValueError("boundary bracket must be strictly ordered")
    midpoint = 0.5 * (lower_A + upper_A)
    return (
        (midpoint, upper_A)
        if midpoint_stable == lower_stable
        else (lower_A, midpoint)
    )


def _load_temperature(path_value: str) -> np.ndarray:
    path = Path(path_value)
    with np.load(path, allow_pickle=False) as payload:
        return np.asarray(payload["temperature_K"], dtype=float)


def _rightmost_pair(values: np.ndarray, vectors: np.ndarray) -> tuple[complex, np.ndarray]:
    eigenvalues = np.asarray(values, dtype=complex)
    eigenvectors = np.asarray(vectors, dtype=complex)
    if eigenvectors.shape[1] != eigenvalues.size:
        raise ValueError("eigenpair arrays are inconsistent")
    index = int(np.argmax(eigenvalues.real))
    return complex(eigenvalues[index]), eigenvectors[:, index]


def _ritz_arrays(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        values = np.asarray(payload["eigenvalues_real_per_s"], dtype=float) + 1j * np.asarray(
            payload["eigenvalues_imag_per_s"], dtype=float
        )
        vectors = np.asarray(payload["eigenvectors_real"], dtype=float) + 1j * np.asarray(
            payload["eigenvectors_imag"], dtype=float
        )
    return values, vectors


def _stage_marker(contract: BracketContract, stage: str) -> Path:
    return contract.compact_root / "stages" / f"{stage}.json"


def _terminal_path(contract: BracketContract) -> Path:
    return contract.compact_root / "terminal.json"


def _write_manifest(root: Path, repository_root: Path, run_id: str) -> None:
    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    atomic_write_json(
        root / "artifact_manifest.json",
        {
            "schema_version": "q2_cc_b_branch_stability_transition_bracket_manifest_v1",
            "run_id": run_id,
            "artifacts": [
                {
                    "path": path.relative_to(repository_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
                for path in files
            ],
        },
    )


def _write_terminal(
    contract: BracketContract,
    *,
    disposition: str,
    detail: str,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if disposition not in TERMINAL_DISPOSITIONS:
        raise ValueError(f"unknown terminal disposition: {disposition}")
    if disposition == PASS_DISPOSITION:
        validity = "valid"
        claim_status = "qualified_supported"
        local_evidence_status = "QUALIFIED_SUPPORTED"
    elif disposition in (COVERAGE_DISPOSITION, PATTERN_DISPOSITION, NO_GO_DISPOSITION):
        validity = "valid"
        claim_status = "failed_but_informative"
        local_evidence_status = "FAILED_BUT_INFORMATIVE"
    else:
        validity = "invalid"
        claim_status = "forbidden"
        local_evidence_status = "FORBIDDEN"
    identity_path = contract.compact_root / "identity.json"
    identity = (
        json.loads(identity_path.read_text(encoding="utf-8"))
        if identity_path.is_file()
        else {}
    )
    payload = {
        "schema_version": "q2_cc_b_branch_stability_transition_bracket_terminal_v1",
        "task_id": TASK_ID,
        "run_id": contract.run_id,
        "disposition": disposition,
        "detail": detail,
        "validity": validity,
        "lifecycle_state": "executed",
        "claim_status": claim_status,
        "local_evidence_status": local_evidence_status,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "cc_b_matrix_launch_count": 0,
        "ground_truth_generated": False,
        "pinn_executed": False,
        "candidate_boundary_wording": "candidate linear-stability boundary",
        "stable_continuation_wording": (
            "discrete continuation connectivity under frozen major-branch metadata; "
            "not dynamic switching reachability"
        ),
        "git_sha": identity.get("git_sha"),
        "finished_at_utc": _utc_now(),
        "summary": dict(summary or {}),
    }
    atomic_write_json(_terminal_path(contract), payload)
    _write_manifest(contract.compact_root, contract.repository_root, contract.run_id)
    if contract.processed_root.exists():
        _write_manifest(contract.processed_root, contract.repository_root, contract.run_id)
    return payload


def _budget_status(contract: BracketContract, next_stage: str) -> tuple[bool, dict[str, float]]:
    identity = json.loads(
        (contract.compact_root / "identity.json").read_text(encoding="utf-8")
    )
    elapsed = time() - float(identity["started_epoch_s"])
    stage_cap = float(contract.raw["budget"][f"{next_stage.lower()}_wall_cap_s"])
    total_cap = float(contract.raw["budget"]["total_calendar_wall_cap_s"])
    return elapsed + stage_cap <= total_cap, {
        "elapsed_wall_s": elapsed,
        "next_stage_cap_s": stage_cap,
        "total_wall_cap_s": total_cap,
    }


def _empty_point_row(
    *,
    branch: str,
    current_A: float,
    stage: str,
    grid: str,
    execution_role: str,
) -> dict[str, Any]:
    row = {name: None for name in POINT_FIELDS}
    row.update(
        {
            "branch": branch,
            "current_A": float(current_A),
            "current_mA": float(current_A * 1.0e3),
            "stage": stage,
            "grid": grid,
            "execution_role": execution_role,
            "equilibrium_valid": False,
            "spectrum_valid": False,
            "stable_continuation_connected": False,
            "transition_bearing": False,
        }
    )
    return row


def _mode_row(
    contract: BracketContract,
    model: CurrentClamp2DModel,
    *,
    branch: str,
    current_A: float,
    stage: str,
    classification: str,
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
) -> dict[str, Any]:
    value, vector = _rightmost_pair(eigenvalues, eigenvectors)
    metrics = mode_metrics(model, value, vector)
    return {
        "branch": branch,
        "current_A": float(current_A),
        "current_mA": float(current_A * 1.0e3),
        "stage": stage,
        "grid": f"L{model.spatial_level}",
        "physical_spectrum_classification": classification,
        **metrics,
        "mode_classification": classify_mode(contract, metrics),
        "vote_role": "nonvoting_diagnostic",
    }


def _execute_new_point(
    contract: BracketContract,
    *,
    branch: str,
    current_A: float,
    spatial_level: int,
    eigenpairs: int,
    stage: str,
    initial_temperature_K: np.ndarray,
    continuation_candidate: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    grid = f"L{spatial_level}"
    identity = f"NOM_{branch}_{_current_token(current_A)}_{grid}_{stage}"
    row = _empty_point_row(
        branch=branch,
        current_A=current_A,
        stage=stage,
        grid=grid,
        execution_role="new_preregistered_execution",
    )
    model = build_registered_nominal_model(
        contract,
        spatial_level=spatial_level,
        current_set_A=current_A,
        branch=branch,
    )
    solve = solve_cc_b_equilibrium(
        model, initial_temperature_K=np.asarray(initial_temperature_K, dtype=float)
    )
    row["equilibrium_code"] = solve.code
    row["failure_detail"] = solve.telemetry.failure_detail
    if (
        not solve.success
        or solve.temperature_K is None
        or solve.evaluation is None
    ):
        row["continuation_role"] = "equilibrium_invalid_breaks_chain"
        return row, None
    metrics = _equilibrium_metrics(
        model,
        solve.temperature_K,
        last_scaled_update_inf=solve.last_scaled_update_inf,
    )
    equilibrium_valid = _equilibrium_passes(contract.requalification, metrics)
    mean_state, transition_fraction, transition = _transition_metrics(
        contract, solve.evaluation.conductive_state
    )
    artifact = save_cc_b_equilibrium(
        contract.processed_root,
        contract.compact_root,
        identity=identity,
        solve=solve,
        stability=None,
        metadata={
            "run_id": contract.run_id,
            "task_id": TASK_ID,
            "stage": stage,
            "execution_role": "new_preregistered_execution",
            "scientific_vote": False,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
        },
    )
    row.update(
        {
            "equilibrium_valid": equilibrium_valid,
            "active_area_mean_conductive_state": mean_state,
            "transition_area_fraction": transition_fraction,
            "transition_bearing": transition,
            "temperature_mean_K": float(np.mean(solve.temperature_K)),
            "temperature_min_K": metrics["temperature_min_K"],
            "temperature_max_K": metrics["temperature_max_K"],
            "device_voltage_V": metrics["device_voltage_V"],
            "scaled_thermal_residual_inf": metrics[
                "scaled_thermal_residual_inf"
            ],
            "last_scaled_update_inf": metrics["last_scaled_update_inf"],
            "scaled_electrical_residual_inf": metrics[
                "scaled_electrical_residual_inf"
            ],
            "maximum_ledger_error": metrics["maximum_ledger_error"],
            "equilibrium_manifest_path": artifact["manifest_path"],
            "equilibrium_manifest_sha256": artifact["manifest_sha256"],
            "equilibrium_npz_path": artifact["npz_path"],
            "equilibrium_npz_sha256": artifact["npz_sha256"],
        }
    )
    if not equilibrium_valid:
        row["continuation_role"] = "postcertification_invalid_breaks_chain"
        row["failure_detail"] = "equilibrium input gates failed"
        return row, None
    case_root = (
        contract.compact_root
        / stage
        / "cases"
        / f"NOM_{branch}_{_current_token(current_A)}_{grid}"
    )
    step = _run_step_diagnostics(
        contract.requalification,
        model,
        solve.temperature_K,
        case_root / "operator_diagnostics",
    )
    row["h_vs_h_half_relative_difference"] = step[
        "h_vs_h_half_relative_difference"
    ]
    row["two_h_vs_h_relative_difference"] = step[
        "two_h_vs_h_relative_difference"
    ]
    if not step["passed"]:
        row["spectrum_code"] = "INVALID_OPERATOR_DIAGNOSTICS"
        row["continuation_role"] = "operator_invalid_breaks_chain"
        row["failure_detail"] = "frozen operator diagnostics failed"
        return row, None
    outcome, spectrum = _run_spectrum(
        contract.requalification,
        model,
        solve.temperature_K,
        eigenpairs=eigenpairs,
        root=case_root / f"k{eigenpairs}",
    )
    spectrum_valid = bool(spectrum["valid"])
    stable = bool(spectrum["stable"]) if spectrum_valid else None
    row.update(
        {
            "spectrum_valid": spectrum_valid,
            "spectrum_code": spectrum["outcome_code"],
            "physical_spectrum_classification": spectrum[
                "physical_spectrum_classification"
            ],
            "stable": stable,
            "stable_continuation_connected": continuation_connected(
                chain_active=continuation_candidate,
                equilibrium_valid=equilibrium_valid,
                spectrum_valid=spectrum_valid,
                stable=stable,
            ),
            "continuation_role": (
                "stable_discrete_continuation_chain"
                if continuation_candidate and spectrum_valid and stable
                else "equilibrium_only_not_continuation_certified"
            ),
            "requested_pair_count": spectrum["requested_pair_count"],
            "returned_pair_count": spectrum["returned_pair_count"],
            "finite_pair_count": spectrum["finite_pair_count"],
            "certified_pair_count": spectrum["certified_pair_count"],
            "maximum_relative_ritz_residual": spectrum[
                "maximum_relative_ritz_residual"
            ],
            "maximum_absolute_ritz_residual_rate_per_s": spectrum[
                "maximum_absolute_ritz_residual_rate_per_s"
            ],
            "rightmost_spectral_abscissa_per_s": spectrum[
                "rightmost_spectral_abscissa_per_s"
            ],
            "alpha_tau_dimensionless": spectrum["alpha_tau_dimensionless"],
            "spectrum_summary_path": (case_root / f"k{eigenpairs}" / "summary.json").as_posix(),
            "spectrum_ritz_path": (
                case_root / f"k{eigenpairs}" / "telemetry" / "ritz_pairs.npz"
            ).as_posix(),
            "failure_detail": spectrum["failure_detail"],
        }
    )
    mode = None
    if spectrum_valid and transition and stable is False:
        mode = _mode_row(
            contract,
            model,
            branch=branch,
            current_A=current_A,
            stage=stage,
            classification=str(spectrum["physical_spectrum_classification"]),
            eigenvalues=outcome.eigenvalues_per_s,
            eigenvectors=outcome.eigenvectors_temperature,
        )
    return row, mode


def _pr34_reuse_point(
    contract: BracketContract, *, continuation_candidate: bool
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    authority = contract.raw["authority"]
    branch = "heating"
    current_A = 4.0e-4
    model = build_registered_nominal_model(
        contract, spatial_level=1, current_set_A=current_A, branch=branch
    )
    manifest_path = _authority_path(
        contract.repository_root, authority["pr_34_l1_input_manifest"]
    )
    npz_path = _authority_path(
        contract.repository_root, authority["pr_34_l1_input_npz"]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with np.load(npz_path, allow_pickle=False) as payload:
        temperature = np.asarray(payload["temperature_K"], dtype=float)
        state = np.asarray(payload["conductive_state"], dtype=float)
    metrics = _equilibrium_metrics(
        model,
        temperature,
        last_scaled_update_inf=float(manifest["last_scaled_update_inf"]),
    )
    if temperature.shape != model.grid.shape or not _equilibrium_passes(
        contract.requalification, metrics
    ):
        raise BracketContractError("PR #34 L1 equilibrium failed current gates")
    step_path = _authority_path(
        contract.repository_root, authority["pr_34_l1_step_summary"]
    )
    spectrum_path = _authority_path(
        contract.repository_root, authority["pr_34_l1_k6_summary"]
    )
    ritz_path = _authority_path(
        contract.repository_root, authority["pr_34_l1_k6_ritz"]
    )
    step = json.loads(step_path.read_text(encoding="utf-8"))
    spectrum = json.loads(spectrum_path.read_text(encoding="utf-8"))
    if not step.get("passed") or not spectrum.get("valid"):
        raise BracketContractError("PR #34 reuse spectra are not certified")
    mean_state, transition_fraction, transition = _transition_metrics(contract, state)
    stable = bool(spectrum["stable"])
    row = _empty_point_row(
        branch=branch,
        current_A=current_A,
        stage="R1",
        grid="L1",
        execution_role="authenticated_pr34_reuse_no_replay",
    )
    row.update(
        {
            "equilibrium_valid": True,
            "equilibrium_code": "PASS_REUSED_PR34",
            "spectrum_valid": True,
            "spectrum_code": spectrum["outcome_code"],
            "physical_spectrum_classification": spectrum[
                "physical_spectrum_classification"
            ],
            "stable": stable,
            "stable_continuation_connected": continuation_connected(
                chain_active=continuation_candidate,
                equilibrium_valid=True,
                spectrum_valid=True,
                stable=stable,
            ),
            "continuation_role": (
                "stable_discrete_continuation_chain"
                if continuation_candidate and stable
                else "equilibrium_only_not_continuation_certified"
            ),
            "active_area_mean_conductive_state": mean_state,
            "transition_area_fraction": transition_fraction,
            "transition_bearing": transition,
            "temperature_mean_K": float(np.mean(temperature)),
            "temperature_min_K": metrics["temperature_min_K"],
            "temperature_max_K": metrics["temperature_max_K"],
            "device_voltage_V": metrics["device_voltage_V"],
            "scaled_thermal_residual_inf": metrics[
                "scaled_thermal_residual_inf"
            ],
            "last_scaled_update_inf": metrics["last_scaled_update_inf"],
            "scaled_electrical_residual_inf": metrics[
                "scaled_electrical_residual_inf"
            ],
            "maximum_ledger_error": metrics["maximum_ledger_error"],
            "requested_pair_count": spectrum["requested_pair_count"],
            "returned_pair_count": spectrum["returned_pair_count"],
            "finite_pair_count": spectrum["finite_pair_count"],
            "certified_pair_count": spectrum["certified_pair_count"],
            "maximum_relative_ritz_residual": spectrum[
                "maximum_relative_ritz_residual"
            ],
            "maximum_absolute_ritz_residual_rate_per_s": spectrum[
                "maximum_absolute_ritz_residual_rate_per_s"
            ],
            "rightmost_spectral_abscissa_per_s": spectrum[
                "rightmost_spectral_abscissa_per_s"
            ],
            "alpha_tau_dimensionless": spectrum["alpha_tau_dimensionless"],
            "h_vs_h_half_relative_difference": step[
                "h_vs_h_half_relative_difference"
            ],
            "two_h_vs_h_relative_difference": step[
                "two_h_vs_h_relative_difference"
            ],
            "equilibrium_manifest_path": manifest_path.as_posix(),
            "equilibrium_manifest_sha256": file_sha256(manifest_path),
            "equilibrium_npz_path": npz_path.as_posix(),
            "equilibrium_npz_sha256": file_sha256(npz_path),
            "spectrum_summary_path": spectrum_path.as_posix(),
            "spectrum_ritz_path": ritz_path.as_posix(),
        }
    )
    mode = None
    if transition and not stable:
        values, vectors = _ritz_arrays(ritz_path)
        mode = _mode_row(
            contract,
            model,
            branch=branch,
            current_A=current_A,
            stage="R1",
            classification=str(spectrum["physical_spectrum_classification"]),
            eigenvalues=values,
            eigenvectors=vectors,
        )
    return row, mode


def run_r0(contract: BracketContract) -> dict[str, Any]:
    if contract.compact_root.exists() or contract.processed_root.exists():
        raise BracketExecutionError("R0 output roots must be new and empty")
    tracked_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=contract.repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tracked_status:
        raise BracketExecutionError("R0 requires a committed clean tracked worktree")
    contract.compact_root.mkdir(parents=True, exist_ok=False)
    contract.processed_root.mkdir(parents=True, exist_ok=False)
    started_wall = perf_counter()
    started_cpu = process_time()
    env = environment_record(contract.repository_root, run_id=contract.run_id)
    identity = {
        "schema_version": "q2_cc_b_branch_stability_transition_bracket_identity_v1",
        "task_id": TASK_ID,
        "run_id": contract.run_id,
        "git_sha": env["git_sha"],
        "pr_34_merge_sha": contract.raw["authority"]["pr_34_merge_sha"],
        "pr_34_code_anchor_sha": contract.raw["authority"][
            "pr_34_code_anchor_sha"
        ],
        "pr_34_result_commit_sha": contract.raw["authority"][
            "pr_34_result_commit_sha"
        ],
        "config_path": contract.path.relative_to(contract.repository_root).as_posix(),
        "config_sha256": file_sha256(contract.path),
        "started_at_utc": _utc_now(),
        "started_epoch_s": time(),
        "workers": 1,
        "blas_threads": 1,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "cc_b_matrix_launch_count": 0,
        "environment": env,
    }
    atomic_write_json(contract.compact_root / "identity.json", identity)
    roots = _load_cc_a_roots(contract)
    r0 = {
        "schema_version": "q2_cc_b_branch_stability_transition_bracket_r0_v1",
        "passed": True,
        "authority_file_count": 15 + len(
            contract.raw["authority"]["frozen_core_files"]
        ),
        "cc_a_root_count": sum(len(rows) for rows in roots.values()),
        "fixed_lattice_point_count": 26,
        "pr_34_reuse_identity": "NOM/heating/0.4mA/L1/k6",
        "pr_34_replay_forbidden": True,
        "frozen_core_files": contract.raw["authority"]["frozen_core_files"],
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(contract.compact_root / "R0" / "authority.json", r0)
    atomic_write_json(_stage_marker(contract, "R0"), r0)
    _write_manifest(contract.compact_root, contract.repository_root, contract.run_id)
    return r0


def _point_numeric_invalid(row: Mapping[str, Any]) -> bool:
    return not _bool(row.get("equilibrium_valid")) or not _bool(
        row.get("spectrum_valid")
    )


def _load_row_temperature(row: Mapping[str, Any]) -> np.ndarray:
    path = str(row.get("equilibrium_npz_path") or "")
    if not path:
        raise BracketExecutionError("point row has no persisted equilibrium input")
    return _load_temperature(path)


def _write_point_tables(
    contract: BracketContract,
    rows: Iterable[Mapping[str, Any]],
    modes: Iterable[Mapping[str, Any]],
) -> None:
    atomic_write_csv(
        contract.compact_root / "fixed_lattice.csv",
        rows,
        fieldnames=POINT_FIELDS,
    )
    atomic_write_csv(
        contract.compact_root / "mode_metrics.csv",
        modes,
        fieldnames=MODE_FIELDS,
    )


def _write_cc_a_comparison(
    contract: BracketContract,
    roots: Mapping[str, list[dict[str, Any]]],
    point_rows: list[dict[str, Any]],
) -> None:
    lookup = {
        (str(row["branch"]), round(float(row["current_A"]), 12)): row
        for row in point_rows
    }
    fields = (
        "branch",
        "current_A",
        "current_mA",
        "cc_a_alpha_tau",
        "cc_b_alpha_tau",
        "cc_a_stable",
        "cc_b_classification",
        "cc_a_conductive_state",
        "cc_b_mean_conductive_state",
        "cc_a_temperature_K",
        "cc_b_temperature_mean_K",
        "cc_a_device_voltage_V",
        "cc_b_device_voltage_V",
        "claim_boundary",
    )
    rows: list[dict[str, Any]] = []
    for branch in BRANCHES:
        for source in roots[branch]:
            point = lookup[(branch, round(float(source["current_A"]), 12))]
            rows.append(
                {
                    "branch": branch,
                    "current_A": source["current_A"],
                    "current_mA": source["current_A"] * 1.0e3,
                    "cc_a_alpha_tau": source["alpha_tau_dimensionless"],
                    "cc_b_alpha_tau": point["alpha_tau_dimensionless"],
                    "cc_a_stable": source["stable"],
                    "cc_b_classification": point[
                        "physical_spectrum_classification"
                    ],
                    "cc_a_conductive_state": source["conductive_state"],
                    "cc_b_mean_conductive_state": point[
                        "active_area_mean_conductive_state"
                    ],
                    "cc_a_temperature_K": source["temperature_K"],
                    "cc_b_temperature_mean_K": point["temperature_mean_K"],
                    "cc_a_device_voltage_V": source["device_voltage_V"],
                    "cc_b_device_voltage_V": point["device_voltage_V"],
                    "claim_boundary": (
                        "lumped local stability does not imply distributed "
                        "constrained thermal stability"
                    ),
                }
            )
    atomic_write_csv(
        contract.compact_root / "cc_a_vs_cc_b_stability.csv",
        rows,
        fieldnames=fields,
    )


def run_r1(contract: BracketContract) -> dict[str, Any]:
    if not _stage_marker(contract, "R0").is_file():
        raise BracketExecutionError("R1 requires a completed R0")
    if _stage_marker(contract, "R1").exists():
        raise BracketExecutionError("R1 is single-execution and already exists")
    admissible, budget = _budget_status(contract, "R1")
    if not admissible:
        return _write_terminal(
            contract,
            disposition=INVALID_DISPOSITION,
            detail="R1 was not launched because the preregistered wall budget was unavailable",
            summary={"resource_status": "budget_exhausted_before_R1", **budget},
        )
    started_wall = perf_counter()
    started_cpu = process_time()
    roots = _load_cc_a_roots(contract)
    fixed = tuple(float(value) for value in contract.raw["scope"]["fixed_currents_A"])
    rows: list[dict[str, Any]] = []
    modes: list[dict[str, Any]] = []
    for branch in BRANCHES:
        order = fixed if branch == "heating" else tuple(reversed(fixed))
        chain_active = True
        previous_temperature: np.ndarray | None = None
        for current_A in order:
            if branch == "heating" and math.isclose(
                current_A, 4.0e-4, rel_tol=0.0, abs_tol=1.0e-15
            ):
                row, mode = _pr34_reuse_point(
                    contract, continuation_candidate=chain_active
                )
            else:
                if chain_active and previous_temperature is not None:
                    initial = previous_temperature
                    predictor_role = "previous_stable_l1_equilibrium"
                else:
                    predictor = cc_a_temperature_predictor(roots, branch, current_A)
                    model = build_registered_nominal_model(
                        contract,
                        spatial_level=1,
                        current_set_A=current_A,
                        branch=branch,
                    )
                    initial = np.full(model.grid.shape, predictor, dtype=float)
                    predictor_role = "piecewise_linear_cc_a_temperature_predictor"
                row, mode = _execute_new_point(
                    contract,
                    branch=branch,
                    current_A=current_A,
                    spatial_level=1,
                    eigenpairs=6,
                    stage="R1",
                    initial_temperature_K=initial,
                    continuation_candidate=chain_active,
                )
                row["execution_role"] = (
                    str(row["execution_role"]) + ":" + predictor_role
                )
            rows.append(row)
            if mode is not None:
                modes.append(mode)
            if _bool(row["stable_continuation_connected"]):
                previous_temperature = _load_row_temperature(row)
            else:
                chain_active = False
                previous_temperature = None
            _write_point_tables(contract, rows, modes)
    _write_cc_a_comparison(contract, roots, rows)
    numeric_invalid = any(_point_numeric_invalid(row) for row in rows)
    payload = {
        "schema_version": "q2_cc_b_branch_stability_transition_bracket_r1_v1",
        "passed": not numeric_invalid,
        "fixed_point_count": len(rows),
        "new_scientific_point_count": sum(
            row["execution_role"] != "authenticated_pr34_reuse_no_replay"
            for row in rows
        ),
        "pr_34_reuse_count": sum(
            row["execution_role"] == "authenticated_pr34_reuse_no_replay"
            for row in rows
        ),
        "mode_diagnostic_count": len(modes),
        "numeric_invalid_point_count": sum(_point_numeric_invalid(row) for row in rows),
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(_stage_marker(contract, "R1"), payload)
    _write_manifest(contract.compact_root, contract.repository_root, contract.run_id)
    _write_manifest(contract.processed_root, contract.repository_root, contract.run_id)
    if numeric_invalid:
        return _write_terminal(
            contract,
            disposition=SEMANTICS_DISPOSITION,
            detail="one or more fixed-lattice equilibrium or spectrum gates were invalid",
            summary=payload,
        )
    return payload


def _row_stable(row: Mapping[str, Any]) -> bool:
    return bool(_bool(row.get("spectrum_valid")) and _bool(row.get("stable")))


def _row_alpha_tau(row: Mapping[str, Any]) -> float:
    value = _optional_float(row.get("alpha_tau_dimensionless"))
    if value is None:
        raise BracketExecutionError("spectrum-valid row is missing alpha_tau")
    return value


def _ritz_uncertainty_tau(contract: BracketContract, row: Mapping[str, Any]) -> float:
    rho = _optional_float(row.get("maximum_absolute_ritz_residual_rate_per_s"))
    if rho is None:
        raise BracketExecutionError("spectrum-valid row is missing Ritz residual rate")
    model = build_registered_nominal_model(
        contract,
        spatial_level=int(str(row["grid"])[1:]),
        current_set_A=float(row["current_A"]),
        branch=str(row["branch"]),
    )
    return rho * model.tau0_s


def _append_mode_table(contract: BracketContract, rows: list[dict[str, Any]]) -> None:
    path = contract.compact_root / "mode_metrics.csv"
    existing: list[dict[str, Any]] = _read_csv(path) if path.is_file() else []
    atomic_write_csv(path, [*existing, *rows], fieldnames=MODE_FIELDS)


def run_r2(contract: BracketContract) -> dict[str, Any]:
    if _terminal_path(contract).is_file():
        return json.loads(_terminal_path(contract).read_text(encoding="utf-8"))
    if not _stage_marker(contract, "R1").is_file():
        raise BracketExecutionError("R2 requires a completed R1")
    if _stage_marker(contract, "R2").exists():
        raise BracketExecutionError("R2 is single-execution and already exists")
    admissible, budget = _budget_status(contract, "R2")
    if not admissible:
        return _write_terminal(
            contract,
            disposition=INVALID_DISPOSITION,
            detail="R2 was not launched because the preregistered wall budget was unavailable",
            summary={"resource_status": "budget_exhausted_before_R2", **budget},
        )
    started_wall = perf_counter()
    started_cpu = process_time()
    fixed = _read_csv(contract.compact_root / "fixed_lattice.csv")
    boundary_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    new_modes: list[dict[str, Any]] = []
    new_point_count = 0
    complex_branches: list[str] = []
    unresolved = False
    max_brackets = int(
        contract.raw["boundary_refinement"]["maximum_brackets_per_branch"]
    )
    max_iterations = int(
        contract.raw["boundary_refinement"]["maximum_bisections_per_bracket"]
    )
    max_points = int(contract.raw["boundary_refinement"]["maximum_new_points_total"])
    for branch in BRANCHES:
        branch_rows = sorted(
            [row for row in fixed if row["branch"] == branch],
            key=lambda row: float(row["current_A"]),
        )
        changes = [
            (left, right)
            for left, right in zip(branch_rows, branch_rows[1:])
            if _bool(left["spectrum_valid"])
            and _bool(right["spectrum_valid"])
            and _row_stable(left) != _row_stable(right)
        ]
        if len(changes) > max_brackets:
            complex_branches.append(branch)
            boundary_rows.append(
                {
                    "branch": branch,
                    "bracket_index": None,
                    "iteration": None,
                    "lower_current_A": None,
                    "upper_current_A": None,
                    "midpoint_current_A": None,
                    "lower_stable": None,
                    "upper_stable": None,
                    "midpoint_stable": None,
                    "midpoint_spectrum_valid": None,
                    "midpoint_alpha_tau": None,
                    "midpoint_ritz_uncertainty_tau": None,
                    "alpha_zero_bracketed": None,
                    "status": "COMPLEX_STABILITY_TOPOLOGY",
                    "wording": "branch refinement stopped without manual selection",
                }
            )
            continue
        for bracket_index, (left_initial, right_initial) in enumerate(changes, start=1):
            left = dict(left_initial)
            right = dict(right_initial)
            for iteration in range(1, max_iterations + 1):
                if new_point_count >= max_points:
                    raise BracketExecutionError("boundary point cardinality exceeded")
                midpoint = 0.5 * (
                    float(left["current_A"]) + float(right["current_A"])
                )
                initial = 0.5 * (
                    _load_row_temperature(left) + _load_row_temperature(right)
                )
                point, mode = _execute_new_point(
                    contract,
                    branch=branch,
                    current_A=midpoint,
                    spatial_level=1,
                    eigenpairs=6,
                    stage="R2",
                    initial_temperature_K=initial,
                    continuation_candidate=False,
                )
                point["execution_role"] = (
                    "new_preregistered_execution:deterministic_boundary_midpoint"
                )
                point_rows.append(point)
                if mode is not None:
                    new_modes.append(mode)
                new_point_count += 1
                spectrum_valid = _bool(point["spectrum_valid"])
                if not _bool(point["equilibrium_valid"]) or not spectrum_valid:
                    unresolved = True
                    status = "BOUNDARY_NUMERICALLY_UNRESOLVED"
                    midpoint_stable = None
                    alpha = None
                    uncertainty = None
                    alpha_zero = None
                else:
                    status = "REFINED"
                    midpoint_stable = _row_stable(point)
                    alpha = _row_alpha_tau(point)
                    uncertainty = _ritz_uncertainty_tau(contract, point)
                    left_alpha = _row_alpha_tau(left)
                    right_alpha = _row_alpha_tau(right)
                    left_uncertainty = _ritz_uncertainty_tau(contract, left)
                    right_uncertainty = _ritz_uncertainty_tau(contract, right)
                    alpha_zero = bool(
                        min(
                            left_alpha - left_uncertainty,
                            right_alpha - right_uncertainty,
                        )
                        <= 0.0
                        <= max(
                            left_alpha + left_uncertainty,
                            right_alpha + right_uncertainty,
                        )
                    )
                boundary_rows.append(
                    {
                        "branch": branch,
                        "bracket_index": bracket_index,
                        "iteration": iteration,
                        "lower_current_A": float(left["current_A"]),
                        "upper_current_A": float(right["current_A"]),
                        "midpoint_current_A": midpoint,
                        "lower_stable": _row_stable(left),
                        "upper_stable": _row_stable(right),
                        "midpoint_stable": midpoint_stable,
                        "midpoint_spectrum_valid": spectrum_valid,
                        "midpoint_alpha_tau": alpha,
                        "midpoint_ritz_uncertainty_tau": uncertainty,
                        "alpha_zero_bracketed": alpha_zero,
                        "status": status,
                        "wording": "candidate linear-stability boundary",
                    }
                )
                atomic_write_csv(
                    contract.compact_root / "boundary_refinement.csv",
                    boundary_rows,
                    fieldnames=BOUNDARY_FIELDS,
                )
                atomic_write_csv(
                    contract.compact_root / "R2" / "boundary_points.csv",
                    point_rows,
                    fieldnames=POINT_FIELDS,
                )
                if unresolved:
                    break
                next_lower, next_upper = refine_bracket_side(
                    float(left["current_A"]),
                    float(right["current_A"]),
                    lower_stable=_row_stable(left),
                    midpoint_stable=bool(midpoint_stable),
                )
                if math.isclose(next_lower, midpoint, rel_tol=0.0, abs_tol=1.0e-15):
                    left = point
                else:
                    right = point
            if unresolved:
                break
        if unresolved:
            break
    if not boundary_rows:
        atomic_write_csv(
            contract.compact_root / "boundary_refinement.csv",
            [],
            fieldnames=BOUNDARY_FIELDS,
        )
    if not point_rows:
        atomic_write_csv(
            contract.compact_root / "R2" / "boundary_points.csv",
            [],
            fieldnames=POINT_FIELDS,
        )
    _append_mode_table(contract, new_modes)
    payload = {
        "schema_version": "q2_cc_b_branch_stability_transition_bracket_r2_v1",
        "passed": not unresolved,
        "candidate_bracket_count": sum(
            row["status"] == "REFINED" and row["iteration"] == 1
            for row in boundary_rows
        ),
        "new_point_count": new_point_count,
        "complex_stability_topology_branches": complex_branches,
        "boundary_numerically_unresolved": unresolved,
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(_stage_marker(contract, "R2"), payload)
    _write_manifest(contract.compact_root, contract.repository_root, contract.run_id)
    _write_manifest(contract.processed_root, contract.repository_root, contract.run_id)
    if unresolved:
        return _write_terminal(
            contract,
            disposition=SEMANTICS_DISPOSITION,
            detail="a preregistered boundary midpoint failed equilibrium or Ritz certification",
            summary=payload,
        )
    return payload


def _eligible_anchor_source(row: Mapping[str, Any]) -> bool:
    return bool(
        _bool(row.get("equilibrium_valid"))
        and _bool(row.get("spectrum_valid"))
        and _bool(row.get("stable"))
        and _bool(row.get("transition_bearing"))
        and _bool(row.get("stable_continuation_connected"))
    )


def _eligible_components(
    rows: list[dict[str, str]], *, lattice_step_A: float = 5.0e-5
) -> list[list[dict[str, str]]]:
    eligible = sorted(
        [row for row in rows if _eligible_anchor_source(row)],
        key=lambda row: float(row["current_A"]),
    )
    components: list[list[dict[str, str]]] = []
    for row in eligible:
        if not components or not math.isclose(
            float(row["current_A"]) - float(components[-1][-1]["current_A"]),
            lattice_step_A,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        ):
            components.append([row])
        else:
            components[-1].append(row)
    return components


def _select_component(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    components = _eligible_components(rows)
    if not components:
        return []
    return sorted(
        components,
        key=lambda component: (
            -(
                float(component[-1]["current_A"])
                - float(component[0]["current_A"])
            ),
            float(component[0]["current_A"]),
        ),
    )[0]


def _find_point(
    rows: Iterable[Mapping[str, Any]], branch: str, current_A: float
) -> dict[str, Any] | None:
    for row in rows:
        if row["branch"] == branch and math.isclose(
            float(row["current_A"]), current_A, rel_tol=0.0, abs_tol=1.0e-15
        ):
            return dict(row)
    return None


def _spectrum_from_existing_point(
    contract: BracketContract,
    row: Mapping[str, Any],
    *,
    eigenpairs: int,
    stage: str,
) -> dict[str, Any]:
    model = build_registered_nominal_model(
        contract,
        spatial_level=int(str(row["grid"])[1:]),
        current_set_A=float(row["current_A"]),
        branch=str(row["branch"]),
    )
    temperature = _load_row_temperature(row)
    case_root = (
        contract.compact_root
        / stage
        / "anchors"
        / f"NOM_{row['branch']}_{_current_token(float(row['current_A']))}_{row['grid']}"
    )
    _, summary = _run_spectrum(
        contract.requalification,
        model,
        temperature,
        eigenpairs=eigenpairs,
        root=case_root / f"k{eigenpairs}",
    )
    return summary


def _anchor_failure_row(
    branch: str,
    *,
    detail: str,
    low_A: float | None = None,
    high_A: float | None = None,
) -> dict[str, Any]:
    row = {name: None for name in ANCHOR_FIELDS}
    row.update(
        {
            "branch": branch,
            "anchor_role": "NOT_ELIGIBLE",
            "source_component_low_A": low_A,
            "source_component_high_A": high_A,
            "sampled_span_A": (
                high_A - low_A
                if low_A is not None and high_A is not None
                else None
            ),
            "anchor_pass": False,
            "failure_detail": detail,
        }
    )
    return row


def _plot_lattice(contract: BracketContract, rows: list[dict[str, str]]) -> str:
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    colors = {"heating": "#c23b22", "cooling": "#2563a5"}
    for branch in BRANCHES:
        selected = sorted(
            [row for row in rows if row["branch"] == branch],
            key=lambda row: float(row["current_A"]),
        )
        x = np.asarray([float(row["current_A"]) * 1.0e3 for row in selected])
        y = np.asarray([float(row["alpha_tau_dimensionless"]) for row in selected])
        axis.plot(x, y, marker="o", color=colors[branch], label=branch)
        for row, x_value, y_value in zip(selected, x, y):
            if _bool(row["transition_bearing"]):
                axis.scatter(
                    [x_value],
                    [y_value],
                    s=70,
                    facecolors="none",
                    edgecolors=colors[branch],
                    linewidths=1.5,
                )
    axis.axhline(0.0, color="black", linewidth=0.8, linestyle="--")
    axis.axhline(-1.0e-3, color="gray", linewidth=0.8, linestyle=":")
    axis.set_xlabel("conductive-sheet current (mA)")
    axis.set_ylabel(r"rightmost $\alpha\tau_0$")
    axis.set_title("CC-A lumped stability is not a CC-B distributed stability vote")
    axis.legend(frameon=False)
    figure.tight_layout()
    path = contract.compact_root / "alpha_tau_vs_current.png"
    figure.savefig(path, dpi=180)
    plt.close(figure)
    return path.as_posix()


def _patterned_trigger(contract: BracketContract) -> tuple[bool, dict[str, Any]]:
    path = contract.compact_root / "mode_metrics.csv"
    modes = _read_csv(path) if path.is_file() else []
    detail: dict[str, Any] = {}
    passed = True
    for branch in BRANCHES:
        relevant = [
            row
            for row in modes
            if row["branch"] == branch
            and row["stage"] == "R1"
            and row["physical_spectrum_classification"] == "POSITIVE_UNSTABLE"
        ]
        transverse = sum(
            row["mode_classification"] == "transverse-dominated"
            for row in relevant
        )
        fraction = transverse / len(relevant) if relevant else 0.0
        branch_pass = bool(
            len(relevant)
            >= int(
                contract.raw["mode_diagnostics"][
                    "patterned_route_minimum_points_per_branch"
                ]
            )
            and fraction
            > float(
                contract.raw["mode_diagnostics"][
                    "patterned_route_fraction_strictly_greater_than"
                ]
            )
        )
        detail[branch] = {
            "valid_transition_positive_unstable_count": len(relevant),
            "transverse_dominated_count": transverse,
            "transverse_fraction": fraction,
            "passed": branch_pass,
        }
        passed = passed and branch_pass
    return passed, detail


def run_r3(contract: BracketContract) -> dict[str, Any]:
    if _terminal_path(contract).is_file():
        return json.loads(_terminal_path(contract).read_text(encoding="utf-8"))
    if not _stage_marker(contract, "R2").is_file():
        raise BracketExecutionError("R3 requires a completed R2")
    if _stage_marker(contract, "R3").exists():
        raise BracketExecutionError("R3 is single-execution and already exists")
    admissible, budget = _budget_status(contract, "R3")
    if not admissible:
        return _write_terminal(
            contract,
            disposition=INVALID_DISPOSITION,
            detail="R3 was not launched because the preregistered wall budget was unavailable",
            summary={"resource_status": "budget_exhausted_before_R3", **budget},
        )
    started_wall = perf_counter()
    started_cpu = process_time()
    fixed = _read_csv(contract.compact_root / "fixed_lattice.csv")
    boundary_point_path = contract.compact_root / "R2" / "boundary_points.csv"
    boundary_points = _read_csv(boundary_point_path) if boundary_point_path.is_file() else []
    anchor_rows: list[dict[str, Any]] = []
    branch_pass: dict[str, bool] = {}
    branch_spans: dict[str, dict[str, Any]] = {}
    numeric_invalid = False
    for branch in BRANCHES:
        branch_fixed = [row for row in fixed if row["branch"] == branch]
        component = _select_component(branch_fixed)
        if not component:
            branch_pass[branch] = False
            anchor_rows.append(
                _anchor_failure_row(branch, detail="no eligible fixed-lattice component")
            )
            branch_spans[branch] = {"passed": False, "reason": "no_component"}
            continue
        low_A = float(component[0]["current_A"])
        high_A = float(component[-1]["current_A"])
        span = high_A - low_A
        minimum_span = float(
            contract.raw["l2_anchor_qualification"]["minimum_sampled_span_A"]
        )
        midpoint_A = 0.5 * (low_A + high_A)
        if span + 1.0e-15 < minimum_span or not (
            low_A < midpoint_A < high_A
        ):
            branch_pass[branch] = False
            anchor_rows.append(
                _anchor_failure_row(
                    branch,
                    detail="eligible component lacks the frozen nonzero three-anchor span",
                    low_A=low_A,
                    high_A=high_A,
                )
            )
            branch_spans[branch] = {
                "passed": False,
                "low_A": low_A,
                "high_A": high_A,
                "span_A": span,
                "reason": "insufficient_span_or_distinct_anchors",
            }
            continue
        anchor_map = {"low": low_A, "mid": midpoint_A, "high": high_A}
        execution_roles = (
            ("low", "mid", "high")
            if branch == "heating"
            else ("high", "mid", "low")
        )
        previous_l2: np.ndarray | None = None
        branch_anchor_rows: list[dict[str, Any]] = []
        for role in execution_roles:
            current_A = anchor_map[role]
            l1_row = _find_point(fixed, branch, current_A)
            if l1_row is None:
                l1_row = _find_point(boundary_points, branch, current_A)
            if l1_row is None:
                endpoint = component[0] if branch == "heating" else component[-1]
                l1_row, mode = _execute_new_point(
                    contract,
                    branch=branch,
                    current_A=current_A,
                    spatial_level=1,
                    eigenpairs=6,
                    stage="R3",
                    initial_temperature_K=_load_row_temperature(endpoint),
                    continuation_candidate=True,
                )
                if mode is not None:
                    _append_mode_table(contract, [mode])
            if not _eligible_anchor_source(l1_row):
                failed = _anchor_failure_row(
                    branch,
                    detail=f"{role} L1 anchor lost eligibility",
                    low_A=low_A,
                    high_A=high_A,
                )
                failed.update(
                    {
                        "anchor_role": role,
                        "current_A": current_A,
                        "current_mA": current_A * 1.0e3,
                    }
                )
                branch_anchor_rows.append(failed)
                continue
            l1_k10 = _spectrum_from_existing_point(
                contract, l1_row, eigenpairs=10, stage="R3"
            )
            l1_k6_alpha = _row_alpha_tau(l1_row)
            l1_difference = (
                abs(l1_k6_alpha - float(l1_k10["alpha_tau_dimensionless"]))
                if l1_k10["valid"]
                else None
            )
            l1_comparison_pass = bool(
                l1_k10["valid"]
                and l1_difference is not None
                and l1_difference
                <= float(
                    contract.raw["frozen_stability"][
                        "k6_k10_alpha_tau_difference_max"
                    ]
                )
            )
            l1_temperature = _load_row_temperature(l1_row)
            l2_model = build_registered_nominal_model(
                contract,
                spatial_level=2,
                current_set_A=current_A,
                branch=branch,
            )
            initial_l2 = (
                previous_l2
                if previous_l2 is not None
                else prolong_temperature(l1_temperature, l2_model.grid.shape)
            )
            l2_solve = solve_cc_b_equilibrium(
                l2_model, initial_temperature_K=initial_l2
            )
            l2_valid = False
            l2_transition = False
            l2_mean = None
            l2_fraction = None
            l2_k6: dict[str, Any] = {"valid": False}
            l2_k10: dict[str, Any] = {"valid": False}
            l2_difference = None
            l2_classification = "NOT_APPLICABLE"
            failure_detail = l2_solve.telemetry.failure_detail
            if (
                l2_solve.success
                and l2_solve.temperature_K is not None
                and l2_solve.evaluation is not None
            ):
                l2_metrics = _equilibrium_metrics(
                    l2_model,
                    l2_solve.temperature_K,
                    last_scaled_update_inf=l2_solve.last_scaled_update_inf,
                )
                l2_valid = _equilibrium_passes(contract.requalification, l2_metrics)
                l2_mean, l2_fraction, l2_transition = _transition_metrics(
                    contract, l2_solve.evaluation.conductive_state
                )
                save_cc_b_equilibrium(
                    contract.processed_root,
                    contract.compact_root,
                    identity=f"NOM_{branch}_{_current_token(current_A)}_L2_R3_{role}",
                    solve=l2_solve,
                    stability=None,
                    metadata={
                        "run_id": contract.run_id,
                        "task_id": TASK_ID,
                        "stage": "R3",
                        "anchor_role": role,
                        "scientific_vote": False,
                        "formal_execution_count": 0,
                        "cc_b_matrix_launch_count": 0,
                    },
                )
                if l2_valid:
                    previous_l2 = l2_solve.temperature_K.copy()
                    case_root = (
                        contract.compact_root
                        / "R3"
                        / "anchors"
                        / f"NOM_{branch}_{_current_token(current_A)}_L2"
                    )
                    step = _run_step_diagnostics(
                        contract.requalification,
                        l2_model,
                        l2_solve.temperature_K,
                        case_root / "operator_diagnostics",
                    )
                    if step["passed"]:
                        _, l2_k6 = _run_spectrum(
                            contract.requalification,
                            l2_model,
                            l2_solve.temperature_K,
                            eigenpairs=6,
                            root=case_root / "k6",
                        )
                        _, l2_k10 = _run_spectrum(
                            contract.requalification,
                            l2_model,
                            l2_solve.temperature_K,
                            eigenpairs=10,
                            root=case_root / "k10",
                        )
                        if l2_k6["valid"] and l2_k10["valid"]:
                            l2_difference = abs(
                                float(l2_k6["alpha_tau_dimensionless"])
                                - float(l2_k10["alpha_tau_dimensionless"])
                            )
                            l2_classification = str(
                                l2_k6["physical_spectrum_classification"]
                            )
                    else:
                        failure_detail = "L2 frozen operator diagnostics failed"
            l1_classification = str(l1_row["physical_spectrum_classification"])
            classifications_equal = bool(
                l2_k6.get("valid")
                and l1_classification == l2_classification
            )
            l2_comparison_pass = bool(
                l2_k6.get("valid")
                and l2_k10.get("valid")
                and l2_difference is not None
                and l2_difference
                <= float(
                    contract.raw["frozen_stability"][
                        "k6_k10_alpha_tau_difference_max"
                    ]
                )
            )
            anchor_pass = bool(
                l1_comparison_pass
                and l2_valid
                and l2_comparison_pass
                and classifications_equal
                and l2_classification == "STABLE_MARGIN_PASS"
                and l2_transition
            )
            if not l1_k10["valid"] or (l2_valid and not l2_comparison_pass):
                numeric_invalid = True
            branch_anchor_rows.append(
                {
                    "branch": branch,
                    "anchor_role": role,
                    "current_A": current_A,
                    "current_mA": current_A * 1.0e3,
                    "source_component_low_A": low_A,
                    "source_component_high_A": high_A,
                    "sampled_span_A": span,
                    "l1_k6_valid": _bool(l1_row["spectrum_valid"]),
                    "l1_k10_valid": l1_k10["valid"],
                    "l1_k6_k10_alpha_tau_difference": l1_difference,
                    "l1_classification": l1_classification,
                    "l2_equilibrium_valid": l2_valid,
                    "l2_k6_valid": l2_k6.get("valid", False),
                    "l2_k10_valid": l2_k10.get("valid", False),
                    "l2_k6_k10_alpha_tau_difference": l2_difference,
                    "l2_classification": l2_classification,
                    "l1_l2_classification_equal": classifications_equal,
                    "l2_active_area_mean_conductive_state": l2_mean,
                    "l2_transition_area_fraction": l2_fraction,
                    "l2_transition_bearing": l2_transition,
                    "anchor_pass": anchor_pass,
                    "failure_detail": failure_detail,
                }
            )
        anchor_rows.extend(branch_anchor_rows)
        branch_ok = bool(
            len(branch_anchor_rows) == 3
            and len({float(row["current_A"]) for row in branch_anchor_rows}) == 3
            and all(_bool(row["anchor_pass"]) for row in branch_anchor_rows)
        )
        branch_pass[branch] = branch_ok
        branch_spans[branch] = {
            "passed": branch_ok,
            "low_A": low_A,
            "high_A": high_A,
            "span_A": span,
            "anchor_currents_A": [
                float(row["current_A"]) for row in branch_anchor_rows
            ],
        }
    atomic_write_csv(
        contract.compact_root / "l2_anchor_qualification.csv",
        anchor_rows,
        fieldnames=ANCHOR_FIELDS,
    )
    figure_path = _plot_lattice(contract, fixed)
    patterned, patterned_detail = _patterned_trigger(contract)
    disposition = select_terminal_disposition(
        branch_pass=branch_pass,
        patterned=patterned,
        numeric_invalid=numeric_invalid,
    )
    detail_by_disposition = {
        SEMANTICS_DISPOSITION: "an R3 k6/k10 numerical certification gate did not close",
        PASS_DISPOSITION: "both branches have three L2-certified stable transition anchors and nonzero sampled spans",
        COVERAGE_DISPOSITION: "only one branch passed the frozen sampled-span qualification",
        PATTERN_DISPOSITION: "both branches are dominated by certified transverse positive-instability modes in transition-bearing fixed points",
        NO_GO_DISPOSITION: "no two-branch stable transition span and no preregistered patterned-branch trigger",
    }
    detail = detail_by_disposition[disposition]
    payload = {
        "schema_version": "q2_cc_b_branch_stability_transition_bracket_r3_v1",
        "passed": disposition == PASS_DISPOSITION,
        "branch_sampled_spans": branch_spans,
        "branch_pass": branch_pass,
        "patterned_branch_trigger": patterned,
        "patterned_branch_detail": patterned_detail,
        "figure_path": figure_path,
        "anchor_row_count": len(anchor_rows),
        "wall_time_s": perf_counter() - started_wall,
        "cpu_time_s": process_time() - started_cpu,
    }
    atomic_write_json(_stage_marker(contract, "R3"), payload)
    atomic_write_json(contract.compact_root / "machine_readable_summary.json", payload)
    return _write_terminal(
        contract,
        disposition=disposition,
        detail=detail,
        summary=payload,
    )


def run_stage(
    config_path: Path | str,
    *,
    stage: str,
    repository_root: Path | str | None = None,
) -> dict[str, Any]:
    contract = load_bracket_contract(config_path, repository_root=repository_root)
    normalized = stage.upper()
    if normalized not in ("R0", "R1", "R2", "R3"):
        raise ValueError("stage must be one of R0, R1, R2, R3")
    try:
        if normalized == "R0":
            return run_r0(contract)
        if normalized == "R1":
            return run_r1(contract)
        if normalized == "R2":
            return run_r2(contract)
        return run_r3(contract)
    except BracketContractError:
        raise
    except Exception as exc:
        if contract.compact_root.exists() and not _terminal_path(contract).exists():
            return _write_terminal(
                contract,
                disposition=INVALID_DISPOSITION,
                detail=f"{normalized} runner/artifact failure: {type(exc).__name__}: {exc}",
                summary={"failure_stage": normalized},
            )
        raise

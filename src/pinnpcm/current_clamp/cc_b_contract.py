"""Fail-closed contract for the bounded current-clamped 2.5D CC-B gate."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from pinnpcm.current_clamp.artifacts import file_sha256


SCHEMA_VERSION = "q2_current_clamp_hysgeo_pinn_v1_cc_b_v1"
TASK_ID = "Q2_CC_A_CLAMP_TOPOLOGY_CLOSURE_AND_BOUNDED_CC_B_2D_GATE_V1"
TERMINAL_DISPOSITIONS = frozenset(
    {
        "PASS_CC_B_2D_GATE",
        "STOP_CC_B_PHYSICS_DEGENERATE",
        "STOP_CC_B_UNSTABLE",
        "STOP_CC_B_BUDGET_NOT_ADMISSIBLE",
        "INVALID_CC_B_EXECUTION",
    }
)
OFFICIAL_CURRENTS_A = (2.0e-4, 4.0e-4, 6.0e-4)
EXPECTED_COMPARISON_CASES = (
    ("NOM", "heating", 4.0e-4),
    ("NOM", "cooling", 4.0e-4),
    ("LU", "heating", 4.0e-4),
    ("RD", "cooling", 4.0e-4),
)
EXPECTED_SEQUENCE = (
    ("NOM", "heating", 2.0e-4, "L1"),
    ("NOM", "heating", 2.0e-4, "L2"),
    ("NOM", "heating", 4.0e-4, "L1"),
    ("NOM", "heating", 4.0e-4, "L2"),
    ("NOM", "cooling", 6.0e-4, "L1"),
    ("NOM", "cooling", 6.0e-4, "L2"),
    ("NOM", "cooling", 4.0e-4, "L1"),
    ("NOM", "cooling", 4.0e-4, "L2"),
    ("LU", "heating", 2.0e-4, "L1"),
    ("LU", "heating", 2.0e-4, "L2"),
    ("LU", "heating", 4.0e-4, "L1"),
    ("LU", "heating", 4.0e-4, "L2"),
    ("RD", "cooling", 6.0e-4, "L1"),
    ("RD", "cooling", 6.0e-4, "L2"),
    ("RD", "cooling", 4.0e-4, "L1"),
    ("RD", "cooling", 4.0e-4, "L2"),
    ("NOM", "heating", 6.0e-4, "L1"),
    ("NOM", "heating", 6.0e-4, "L2"),
    ("NOM", "cooling", 2.0e-4, "L1"),
    ("NOM", "cooling", 2.0e-4, "L2"),
    ("LU", "heating", 6.0e-4, "L1"),
    ("LU", "heating", 6.0e-4, "L2"),
    ("LU", "cooling", 6.0e-4, "L1"),
    ("LU", "cooling", 6.0e-4, "L2"),
    ("LU", "cooling", 4.0e-4, "L1"),
    ("LU", "cooling", 4.0e-4, "L2"),
    ("LU", "cooling", 2.0e-4, "L1"),
    ("LU", "cooling", 2.0e-4, "L2"),
    ("RD", "heating", 2.0e-4, "L1"),
    ("RD", "heating", 2.0e-4, "L2"),
    ("RD", "heating", 4.0e-4, "L1"),
    ("RD", "heating", 4.0e-4, "L2"),
    ("RD", "heating", 6.0e-4, "L1"),
    ("RD", "heating", 6.0e-4, "L2"),
    ("RD", "cooling", 2.0e-4, "L1"),
    ("RD", "cooling", 2.0e-4, "L2"),
)


class CCBContractError(RuntimeError):
    """The claim-bearing CC-B identity is incomplete or has drifted."""


@dataclass(frozen=True)
class CCBScales:
    temperature_K: float
    current_A: float
    voltage_V: float
    power_W: float
    current_floor_A: float
    power_floor_W: float


@dataclass(frozen=True)
class CCBContract:
    path: Path
    repository_root: Path
    raw: dict[str, Any]
    cc_a_config: dict[str, Any]
    parent_config: dict[str, Any]
    scales: CCBScales

    @property
    def solver(self) -> dict[str, Any]:
        return self.raw["steady_solver"]

    @property
    def stability(self) -> dict[str, Any]:
        return self.raw["stability"]

    @property
    def run_id(self) -> str:
        return str(self.raw["run_id"])

    @property
    def sequence(self) -> tuple[tuple[str, str, float, str], ...]:
        return tuple(
            (str(item[0]), str(item[1]), float(item[2]), str(item[3]))
            for item in self.raw["matrix"]["sequence"]
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CCBContractError(f"cannot read YAML contract: {exc}") from exc
    if not isinstance(payload, dict):
        raise CCBContractError(f"{path} must contain a mapping")
    return payload


def _resolved(root: Path, spec: Mapping[str, Any]) -> Path:
    path = (root / str(spec["path"])).resolve()
    if not path.is_file():
        raise CCBContractError(f"authority file is missing: {path}")
    observed = file_sha256(path)
    expected = str(spec["sha256"]).lower()
    if observed != expected:
        raise CCBContractError(f"authority hash drift: {path}")
    return path


def _exact_float(value: Any, expected: float, name: str) -> None:
    try:
        observed = float(value)
    except Exception as exc:
        raise CCBContractError(f"{name} is not numeric") from exc
    if not math.isfinite(observed) or not math.isclose(
        observed, expected, rel_tol=0.0, abs_tol=0.0
    ):
        raise CCBContractError(f"claim-bearing value drifted: {name}")


def _assert_frozen_contract(raw: Mapping[str, Any]) -> None:
    topology = raw["clamp_topology"]
    expected_topology = {
        "clamp_target": "conductive_sheet_current",
        "electrical_response": "algebraic",
        "dynamic_state": "temperature_cells_only",
        "parallel_capacitance_role": "inactive_external_source_metadata",
        "terminal_total_current_clamp": "forbidden",
        "external_RC_state": "forbidden",
    }
    for key, expected in expected_topology.items():
        if topology.get(key) != expected:
            raise CCBContractError(f"current-clamp topology drifted: {key}")
    source = raw["source_mapping"]
    if source.get("resistance_variant") != "S1_QS":
        raise CCBContractError("only the audited S1_QS source mapping is eligible")
    if source.get("additional_series_or_contact_resistance") != "forbidden":
        raise CCBContractError("duplicate electrical series/contact semantics are forbidden")
    _exact_float(source.get("geometry_factor_m"), 5.0e-7, "geometry_factor_m")

    matrix = raw["matrix"]
    currents = tuple(float(value) for value in matrix["official_currents_A"])
    if currents != OFFICIAL_CURRENTS_A:
        raise CCBContractError("formal current set drifted")
    sequence = tuple(
        (str(item[0]), str(item[1]), float(item[2]), str(item[3]))
        for item in matrix["sequence"]
    )
    if sequence != EXPECTED_SEQUENCE:
        raise CCBContractError("36-solution execution sequence drifted")
    if int(matrix["physical_case_count"]) != 18 or int(matrix["grid_case_count"]) != 36:
        raise CCBContractError("formal matrix cardinality drifted")
    if len(set(sequence)) != 36:
        raise CCBContractError("formal sequence contains duplicates")

    comparison = tuple(
        (str(item[0]), str(item[1]), float(item[2]))
        for item in raw["stability"]["comparison_cases"]
    )
    if comparison != EXPECTED_COMPARISON_CASES:
        raise CCBContractError("k=6/k=10 comparison cases drifted")

    exact = {
        ("steady_solver", "residual_inf_max"): 1.0e-8,
        ("steady_solver", "last_scaled_update_inf_max"): 1.0e-8,
        ("equilibrium_gates", "thermal_scaled_cv_residual_max"): 1.0e-8,
        ("equilibrium_gates", "electrical_scaled_cv_residual_max"): 1.0e-10,
        ("equilibrium_gates", "ledger_symmetric_relative_max"): 5.0e-3,
        ("uniform_gate", "electrical_geometry_relative_error_max"): 5.0e-3,
        ("uniform_gate", "topology_operator_dimensionless_error_max"): 1.0e-6,
        ("uniform_gate", "topology_operator_mass_residual_max"): 1.0e-8,
        ("stability", "relative_ritz_residual_max"): 1.0e-6,
        ("stability", "stable_alpha_tau_max"): -1.0e-3,
        ("stability", "comparison_alpha_tau_difference_max"): 1.0e-4,
        ("transition_gate", "nominal_l2_area_fraction_min"): 0.10,
        ("two_dimensional_gate", "response_rms_K_min"): 0.25,
        ("two_dimensional_gate", "r2d_min"): 0.15,
        ("two_dimensional_gate", "grid_uncertainty_multiplier_min"): 5.0,
        ("budget", "aggregate_cpu_cap_s"): 14400.0,
        ("budget", "calendar_wall_cap_s"): 14400.0,
        ("budget", "safety_multiplier"): 1.5,
    }
    for (section, key), expected in exact.items():
        _exact_float(raw[section][key], expected, f"{section}.{key}")
    if int(raw["budget"]["formal_matrix_launches_max"]) != 1:
        raise CCBContractError("formal matrix must remain one-shot")
    if set(raw["terminal_dispositions"]) != TERMINAL_DISPOSITIONS:
        raise CCBContractError("terminal disposition vocabulary drifted")


def load_cc_b_contract(
    path: Path | str = Path("configs/q2_current_clamp_hysgeo_pinn_v1_cc_b.yaml"),
    *,
    repository_root: Path | str | None = None,
) -> CCBContract:
    """Load the CC-B contract and authenticate every upstream scientific identity."""

    root = (Path.cwd() if repository_root is None else Path(repository_root)).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    raw = _read_yaml(config_path)
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("task_id") != TASK_ID:
        raise CCBContractError("unexpected CC-B task/schema identity")
    _assert_frozen_contract(raw)

    authority = raw["authority"]
    cc_a_path = _resolved(root, authority["cc_a_config"])
    terminal_path = _resolved(root, authority["cc_a_terminal"])
    parent_path = _resolved(root, authority["parent_physics_config"])
    cc_a = _read_yaml(cc_a_path)
    parent = _read_yaml(parent_path)
    try:
        terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CCBContractError(f"cannot read CC-A terminal: {exc}") from exc
    required = authority["cc_a_terminal"]["required_disposition"]
    if (
        terminal.get("disposition") != required
        or terminal.get("validity") != "valid"
        or terminal.get("cc_b_eligible_to_request") is not True
        or terminal.get("scientific_vote") is not False
        or int(terminal.get("formal_execution_count", -1)) != 0
    ):
        raise CCBContractError("CC-A terminal does not authorize the bounded CC-B request")
    if cc_a["source_parameters"].get("parallel_capacitance_F") is None:
        raise CCBContractError("CC-A external capacitance metadata unexpectedly disappeared")

    scales = CCBScales(**{key: float(value) for key, value in raw["reference_scales"].items()})
    if any(not math.isfinite(value) or value <= 0.0 for value in scales.__dict__.values()):
        raise CCBContractError("reference scales must be finite and positive")
    if not math.isclose(
        scales.current_A * scales.voltage_V,
        scales.power_W,
        rel_tol=8.0 * float.fromhex("0x1.0000000000000p-52"),
        abs_tol=0.0,
    ):
        raise CCBContractError("power reference is inconsistent")
    return CCBContract(
        path=config_path,
        repository_root=root,
        raw=raw,
        cc_a_config=cc_a,
        parent_config=parent,
        scales=scales,
    )

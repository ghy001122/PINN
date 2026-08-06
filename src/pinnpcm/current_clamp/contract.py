"""Frozen contract validation for CurrentClamp-HysGeo-PINN Batch 1."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

import yaml


SCHEMA_VERSION = "q2_current_clamp_hysgeo_pinn_v1_cc_a_v1"
TERMINAL_DISPOSITIONS = {
    "PASS_CC_A_CURRENT_CLAMP_ADMISSION",
    "STOP_CC_CURRENT_CLAMP_ADMISSION",
    "INVALID_CC_A_EXECUTION",
}
OFFICIAL_CURRENTS_A = tuple(index * 1.0e-4 for index in range(1, 8))


class CurrentClampContractError(RuntimeError):
    """Fail-closed configuration or source-semantics error."""


def _require_positive_finite(mapping: Mapping[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        value = float(mapping[name])
        if not math.isfinite(value) or value <= 0.0:
            raise CurrentClampContractError(
                f"{name} must be finite and positive"
            )


def load_current_clamp_contract(path: Path) -> dict[str, Any]:
    """Load and fail closed on any drift in the approved CC-A contract."""

    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CurrentClampContractError("CC-A config must be a mapping")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise CurrentClampContractError("unexpected CC-A schema version")
    if set(payload.get("terminal_dispositions", ())) != TERMINAL_DISPOSITIONS:
        raise CurrentClampContractError("terminal disposition vocabulary drifted")
    if bool(payload.get("scientific_vote")):
        raise CurrentClampContractError(
            "CC-A cannot cast a global Phase-1 scientific vote"
        )
    if int(payload.get("formal_execution_count", -1)) != 0:
        raise CurrentClampContractError("CC-A cannot consume a formal execution")

    parameters = payload["source_parameters"]
    _require_positive_finite(
        parameters,
        (
            "resistance_prefactor_ohm",
            "metallic_resistance_ohm",
            "activation_temperature_K",
            "beta_per_K",
            "loop_width_K",
            "critical_temperature_K",
            "thermal_conductance_W_K",
            "thermal_capacitance_J_K",
            "ambient_temperature_K",
        ),
    )
    if not math.isclose(float(payload["production_source"]["metallic_multiplier"]), 1.0):
        raise CurrentClampContractError("CC-A production source must be S1_QS")
    if payload["production_source"]["resistance_variant"] != "S1_QS":
        raise CurrentClampContractError("only S1_QS is production eligible")

    current_cfg = payload["current_clamp"]
    currents = tuple(float(value) for value in current_cfg["official_currents_A"])
    if len(currents) != len(OFFICIAL_CURRENTS_A) or any(
        not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1.0e-15)
        for actual, expected in zip(currents, OFFICIAL_CURRENTS_A, strict=True)
    ):
        raise CurrentClampContractError(
            "official currents must remain 0.1 through 0.7 mA"
        )
    if not math.isclose(float(current_cfg["heating_anchor_current_A"]), 0.0):
        raise CurrentClampContractError("heating anchor must remain I=0")
    if not math.isclose(
        float(current_cfg["cooling_endpoint_current_A"]), currents[-1]
    ):
        raise CurrentClampContractError(
            "cooling endpoint must remain the 0.7 mA formal point"
        )

    temperature = payload["admissibility"]["temperature_K"]
    lower = float(temperature["minimum"])
    upper = float(temperature["maximum"])
    ambient = float(parameters["ambient_temperature_K"])
    if not (0.0 < lower <= ambient <= upper):
        raise CurrentClampContractError(
            "ambient temperature must lie inside the frozen source domain"
        )

    source_mapping = payload["source_mapping"]
    if not bool(source_mapping["additional_series_resistance_forbidden"]):
        raise CurrentClampContractError(
            "S1 device-effective resistance cannot be counted twice"
        )
    if source_mapping["contact_overlap_role"] != "thermal_only":
        raise CurrentClampContractError(
            "contact overlap cannot alter electrical resistance in this contract"
        )
    if bool(source_mapping["per_grid_or_overlap_refit_allowed"]):
        raise CurrentClampContractError("geometry-factor refitting is forbidden")

    budget = payload["budget"]
    _require_positive_finite(
        budget, ("aggregate_cpu_cap_s", "calendar_wall_cap_s")
    )
    if float(budget["aggregate_cpu_cap_s"]) > 1800.0 or float(
        budget["calendar_wall_cap_s"]
    ) > 1800.0:
        raise CurrentClampContractError("CC-A budget cannot exceed 30 minutes")
    return payload

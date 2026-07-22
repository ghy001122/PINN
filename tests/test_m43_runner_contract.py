from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable

import pytest
import yaml

from scripts.run_m43_finite_width_thermal_spreading import (
    EXPECTED_CASE_IDS,
    EXPECTED_GATE_NAMES,
    _validate_config_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m43_finite_width_thermal_spreading.yaml"


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _set_wrong_area(config: dict) -> None:
    config["geometry"]["source_area_m2"] *= 2.0


def _set_wrong_diffusivity(config: dict) -> None:
    config["material"]["thermal_diffusivity_m2_s"] *= 1.1


def _set_wrong_fourier_time(config: dict) -> None:
    config["time"]["fvm_comparison_times_s"][3] *= 1.01


def _set_wrong_case_mode(config: dict) -> None:
    config["forward_matrix"][8]["mode"] = "steady"


def _set_wrong_gate(config: dict) -> None:
    config["gates"]["steady_rho5_reference_error_max"] = 0.5


def _set_wrong_boundary(config: dict) -> None:
    config["boundary_contract"]["top_source"] = "first_layer_volumetric_source"


def _set_wrong_square_depth(config: dict) -> None:
    config["grid"]["mesh_profiles"]["M1"]["square_source_depth_cells"] = 2


def _set_wrong_decision(config: dict) -> None:
    config["decision"]["any_mandatory_gate_fails"] = "M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY"


TAMPERS: tuple[tuple[str, Callable[[dict], None]], ...] = (
    ("source_area", _set_wrong_area),
    ("diffusivity", _set_wrong_diffusivity),
    ("fourier_time", _set_wrong_fourier_time),
    ("case_mode", _set_wrong_case_mode),
    ("gate_threshold", _set_wrong_gate),
    ("boundary_source", _set_wrong_boundary),
    ("square_isotropy", _set_wrong_square_depth),
    ("terminal_decision", _set_wrong_decision),
)


def test_m43_locked_config_contract_is_complete_and_passes() -> None:
    config = _config()
    contract = _validate_config_contract(config)
    assert contract["passed"] is True
    assert contract["failed_checks"] == []
    assert contract["checks"]
    assert all(isinstance(value, bool) and value for value in contract["checks"].values())
    assert tuple(case["case_id"] for case in config["forward_matrix"]) == EXPECTED_CASE_IDS
    assert len(EXPECTED_CASE_IDS) == 15
    assert len(EXPECTED_GATE_NAMES) == 21


@pytest.mark.parametrize(("tamper_name", "mutate"), TAMPERS, ids=[name for name, _ in TAMPERS])
def test_m43_config_contract_fails_closed_on_registered_tamper(
    tamper_name: str,
    mutate: Callable[[dict], None],
) -> None:
    del tamper_name
    config = deepcopy(_config())
    mutate(config)
    contract = _validate_config_contract(config)
    assert contract["passed"] is False
    assert contract["failed_checks"]
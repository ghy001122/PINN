from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pinnpcm.evaluation.geophase_s0_direct_physics import S0ExecutionError
from pinnpcm.evaluation import geophase_s0_formal
from pinnpcm.evaluation.geophase_s0_formal import execute_unit


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_s0_formal.py"


def _unit(group: str, **values: object) -> dict[str, object]:
    return {
        "execution_unit_id": f"TRJ-TEST-{group}",
        "execution_group": group,
        "consumer_evaluation_ids": [f"TEST-{group}"],
        "primary_evaluation_id": f"P1V2-{group}-test",
        "fixture_id": None,
        "protocol_id": None,
        "spatial_level": None,
        "time_divisor": None,
        "contact_overlap_m": None,
        **values,
    }


def test_formal_module_has_no_historical_runner_imports() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any("geophase_phase1_e0" in name for name in imported)
    assert not any("equivalence" in name for name in imported)
    assert not any("readiness" in name for name in imported)


@pytest.mark.parametrize(
    "fixture",
    [
        "negative_effective_capacity",
        "negative_vertical_conductance",
        "nonfinite_newton",
        "ledger_tamper",
        "coordinate_swap",
    ],
)
def test_real_fail_closed_fixtures_are_detected(fixture: str) -> None:
    payload = execute_unit(
        _unit("FAIL", fixture_id=fixture),
        remaining_s=60.0,
    )
    assert payload["status"] == "PASS"
    assert payload["local_metrics"]["expected_failure_detected"] is True


@pytest.mark.parametrize(
    "evaluation_id",
    [
        "P1V2-MMS-electrical_linear_field-L1",
        "P1V2-MMS-thermal_diffusion_with_source_and_sink-L1",
        "P1V2-MMS-S2_forced_uniform_temperature_response-L1",
    ],
)
def test_real_l1_manufactured_fixtures_pass(evaluation_id: str) -> None:
    payload = execute_unit(
        _unit(
            "MMS",
            primary_evaluation_id=evaluation_id,
            spatial_level=1,
        ),
        remaining_s=60.0,
    )
    assert payload["status"] == "PASS"


@pytest.mark.parametrize(
    "fixture",
    [
        "uniform_conductivity_linear_potential",
        "zero_joule_cooling",
        "steady_thermal_resistance",
        "local_single_cell_backward_euler",
        "rc_open_device",
    ],
)
def test_real_nontrajectory_limit_fixtures_pass(fixture: str) -> None:
    payload = execute_unit(
        _unit("LIM", fixture_id=fixture),
        remaining_s=60.0,
    )
    assert payload["status"] == "PASS"


def test_unknown_group_fails_closed() -> None:
    with pytest.raises(S0ExecutionError, match="unsupported"):
        execute_unit(_unit("UNKNOWN"), remaining_s=1.0)


def test_zero_drive_limit_resolves_nullable_dag_axes_from_frozen_addendum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_trajectory(
        unit: dict[str, object], *, remaining_s: float, overlap_m: float | None = None
    ) -> dict[str, object]:
        observed.update(unit)
        return {
            "execution_unit_id": unit["execution_unit_id"],
            "execution_group": "LIM",
            "validity": "valid",
            "status": "PASS",
            "scientific_vote": True,
            "local_metrics": {},
            "raw": {},
        }

    monkeypatch.setattr(geophase_s0_formal, "_run_trajectory", fake_trajectory)
    execute_unit(
        _unit(
            "LIM",
            fixture_id="zero_drive_equilibrium",
            spatial_level=None,
            time_divisor=None,
            protocol_id=None,
        ),
        remaining_s=60.0,
    )
    assert observed["spatial_level"] == 1
    assert observed["time_divisor"] == 1
    assert observed["protocol_id"] == "zero_drive"

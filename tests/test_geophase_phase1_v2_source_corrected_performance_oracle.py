from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
import yaml

from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    effective_vo2_closure_from_v2_config,
)


ROOT = Path(__file__).resolve().parents[1]
ORACLE_PATH = ROOT / "tests" / "oracles" / "pr8_geophase_2p5d_fvm.py"
CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
PR8_COMMIT = "85e4257fc01af2e0bf706ef9001f263b1420ecaa"
PR8_SOURCE_PATH = "src/pinnpcm/solvers/geophase_2p5d_fvm.py"
EXPECTED_SHA256 = "e1a349ca0275021508cd07da02576adafbbcdae81e122659274769f329016a37"
EXPECTED_GIT_BLOB = "fd0e0773255181b037c4d6b6be4e482b735d1eff"

pytestmark = [pytest.mark.phase1, pytest.mark.current]


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _load_oracle() -> ModuleType:
    module_name = "_phase1_v2_pr8_test_only_electrical_oracle"
    spec = importlib.util.spec_from_file_location(module_name, ORACLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _source_corrected_config() -> dict:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_oracle_is_the_exact_PR8_blob_and_not_a_reimplementation() -> None:
    payload = ORACLE_PATH.read_bytes()
    historical = subprocess.check_output(
        ["git", "show", f"{PR8_COMMIT}:{PR8_SOURCE_PATH}"],
        cwd=ROOT,
    )

    assert payload == historical
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_SHA256
    assert _git_blob_sha1(payload) == EXPECTED_GIT_BLOB


def test_oracle_loads_dynamically_without_a_production_legacy_mode() -> None:
    production_name = "pinnpcm.solvers.geophase_2p5d_fvm"
    production_before = sys.modules.get(production_name)
    oracle = _load_oracle()

    assert callable(oracle.solve_sheet_electrical)
    assert sys.modules.get(production_name) is production_before
    assert "_phase1_v2_pr8_test_only_electrical_oracle" not in sys.modules
    for path in (ROOT / "src" / "pinnpcm").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "tests.oracles" not in text
        assert "pr8_geophase_2p5d_fvm" not in text


def test_oracle_accepts_the_source_corrected_15p8V_high_state_input() -> None:
    config = _source_corrected_config()
    protocols = config["formal_protocols"]["protocols"]
    assert "high_bias_15V" not in protocols
    protocol = protocols["high_bias_lock_15p8V"]
    assert protocol["input_voltage_V"] == pytest.approx(15.8)

    grid = build_geophase_grid(config, spatial_level=1)
    closure = effective_vo2_closure_from_v2_config(config)
    temperature = np.full(grid.shape, 380.0, dtype=float)
    branch = np.ones(grid.shape, dtype=float)
    conductive = closure.equilibrium_state(temperature, branch)
    conductivity = closure.conductivity_S_m(temperature, conductive)

    oracle = _load_oracle()
    solution = oracle.solve_sheet_electrical(
        grid,
        conductivity,
        float(protocol["input_voltage_V"]),
    )

    assert solution.potential_V.shape == grid.shape
    assert solution.cell_joule_power_W.shape == grid.shape
    assert np.isfinite(solution.potential_V).all()
    assert np.isfinite(solution.cell_joule_power_W).all()
    assert solution.source_current_A > 0.0
    assert solution.joule_power_W > 0.0
    assert solution.terminal_device_power_W > 0.0
    assert solution.relative_current_imbalance <= 1.0e-12
    assert solution.relative_power_imbalance <= 1.0e-12

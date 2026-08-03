from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import yaml

from pinnpcm.evaluation.geophase_exact_block_condensation_stage_a import (
    evaluate_exact_condensation,
)
from pinnpcm.evaluation.geophase_nls_v1_qualification import _state_from_replay
from pinnpcm.evaluation.geophase_s0_direct_physics import ROOT, resolved_s2_config
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    effective_vo2_closure_from_v2_config,
)
from pinnpcm.solvers import geophase_phase1_v2_implicit as production


CONFIG = ROOT / "configs/geophase_exact_block_condensation_stage_a.yaml"
REPLAY = ROOT / (
    "outputs/tables/geophase_controller_v3/qualification/"
    "CTRLV3-QUAL-20260801-V2/failures/CTRLV3-QUAL-QUIESCENT-9V-T1.json"
)


def _context():
    scientific = resolved_s2_config()
    grid = build_geophase_grid(scientific, spatial_level=1)
    fields = build_s2_thermal_fields(grid, scientific)
    closure = effective_vo2_closure_from_v2_config(scientific)
    cache = production.build_s2_solver_cache(grid, fields)
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))["replay"]
    return scientific, grid, fields, closure, cache, replay


def test_auxiliary_blocks_are_exactly_condensed_in_production_residual() -> None:
    scientific, grid, fields, closure, cache, replay = _context()
    old_state = _state_from_replay(replay["previous_state"])
    for dt_ns in (10.0, 0.3125, 0.15625):
        result = evaluate_exact_condensation(
            candidate_temperature_K=old_state.temperature_K,
            old_state=old_state,
            input_voltage_V=float(replay["full_input_voltage_V"]),
            dt_s=dt_ns * 1.0e-9,
            grid=grid,
            closure=closure,
            fields=fields,
            scientific_config=scientific,
            cache=cache,
        )
        assert result["auxiliary"] <= 1.0e-12
        assert result["branch"] <= np.finfo(float).eps
        assert result["full"] == result["temperature"]


def test_stage_a_keeps_full_future_nonlinear_gates_at_one_e_minus_eight() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["gates"]["future_full_scaled_residual_inf_max"] == 1.0e-8
    assert config["gates"]["future_full_fixed_point_defect_inf_max"] == 1.0e-8
    assert config["gates"]["relaxed_1e_minus_6_gate"] == "forbidden"
    assert config["scope"]["nonlinear_or_trajectory_execution"] == "forbidden"
    assert config["scope"]["new_12p5V_trace_generation"] == "forbidden"


def test_stage_a_module_has_no_nonlinear_or_trajectory_entrypoint() -> None:
    source_path = ROOT / (
        "src/pinnpcm/evaluation/geophase_exact_block_condensation_stage_a.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    forbidden = {
        "advance_s2_backward_euler_nls_v1",
        "run_s2_streaming_protocol_nls_v1",
        "simulate_s2_protocol",
    }
    assert called_names.isdisjoint(forbidden)

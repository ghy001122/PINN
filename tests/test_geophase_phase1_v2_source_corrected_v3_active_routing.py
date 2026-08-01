from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE_PATH = ROOT / "configs" / "geo2p5d_stage_source_corrected_v3.yaml"
LEGACY_STAGE_PATH = ROOT / "configs" / "geo2p5d_stage.yaml"
RUNNER_PATH = (
    ROOT
    / "scripts"
    / "run_geophase_phase1_v2_source_corrected_performance_readiness.py"
)
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "read_only_validation.yml"


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _runner_module():
    specification = importlib.util.spec_from_file_location("source_corrected_route", RUNNER_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_v3_stage_is_the_only_active_runtime_bundle_and_formal_count_is_zero() -> None:
    stage = _yaml(STAGE_PATH)
    active = stage["active_bundle"]
    historical = stage["historical_bundle"]

    assert stage["current_checkpoint"] == (
        "PHASE1_V2_SOURCE_CORRECTED_V3_PERFORMANCE_REPAIR_PREREGISTERED_PENDING_IMPLEMENTATION"
    )
    assert stage["formal_execution_count"] == 0
    assert stage["formal_artifact_count"] == 0
    assert active["source_correction_preregistration_commit"] == (
        "0ebe037ef707a56750c5db0c52f7a312ee251b6c"
    )
    assert active["active_high_bias_protocol"] == "high_bias_lock_15p8V"
    assert active["active_high_bias_voltage_V"] == 15.8
    assert active["high_bias_role"] == "qualitative_source_trend_probe"
    assert active["high_bias_15V_compatibility_alias"] == "forbidden"
    assert active["source_contract"] == "configs/qiu_vo2_phase1_source_contract_v3.yaml"
    assert active["phase1_config"].endswith("_source_corrected_v3.yaml")
    assert active["phase1_manifest"].endswith("_source_corrected_v3.yaml")
    assert active["phase1_execution_addendum"].endswith("_source_corrected_v3.yaml")
    assert active["phase1_active_time_controller"].endswith(
        "_source_corrected_v3.yaml"
    )
    assert "geophase_phase1_v2_source_corrected_v3" in active[
        "resolved_runtime_identity"
    ]
    assert "geophase_phase1_v2_source_corrected_v3" in active["execution_DAG"]
    assert active["output_namespace"].endswith(
        "geophase_phase1_v2_source_corrected_v3"
    )
    assert historical["stage_router"] == LEGACY_STAGE_PATH.relative_to(ROOT).as_posix()
    assert historical["active_runtime_selection"] == "forbidden"
    assert historical["old_high_bias_protocol"] == "high_bias_15V"


def test_route_only_runner_validates_v3_and_cannot_execute_before_preregistration() -> None:
    module = _runner_module()
    route = module.validate_active_route()

    assert route["active_high_bias_protocol"] == "high_bias_lock_15p8V"
    assert route["formal_execution_count"] == 0
    assert route["formal_artifact_count"] == 0
    assert len(route["resolved_runtime_identity_sha256"]) == 64
    assert route["performance_repair_preregistration_sha256"] == (
        "84e1ecb298cfa6264646cc5e74df602b3e9e790e3eecfdc1abea62c087e87db4"
    )
    assert module.IMPLEMENTATION_READY is False
    runner_source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "from pinnpcm.solvers.geophase_phase1_v2_implicit import" not in runner_source
    assert "import pinnpcm.solvers.geophase_phase1_v2_implicit" not in runner_source
    assert "run_C1" not in runner_source


def test_authority_chain_records_terminal_s0_and_preserves_old_route_tests() -> None:
    checkpoint = "Q2_CONTROLLER_V3_EXHAUSTED_NO_S0"
    for path in (
        ROOT / "CODEX_CONTEXT.md",
        ROOT / "PROJECT_STATE.md",
        ROOT / "NEXT_ACTIONS.md",
        ROOT / "docs" / "research_strategy" / "active_phase.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert checkpoint in text
        assert "formal_execution_count=0" in text

    active = (ROOT / "docs" / "research_strategy" / "active_phase.md").read_text(
        encoding="utf-8"
    )
    assert "Equivalence-v4/v5 is forbidden" in active
    assert "Equivalence-v2 remains" in active
    assert "Equivalence-v3 remains" in active

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "tests/test_geophase_phase1_v2_source_corrected_v3_preregistration.py" in workflow
    assert "tests/test_geophase_phase1_v2_source_corrected_v3_active_routing.py" in workflow
    assert "tests/test_phase1_e0_single_implementation_activation.py" in workflow
    assert (
        "tests/test_geophase_phase1_v2_equivalence_v2_comparator_closure_v3.py"
        in workflow
    )
    assert (
        "tests/test_geophase_phase1_v2_equivalence_v2_one_shot_control_plane.py"
        in workflow
    )
    assert (
        "tests/test_geophase_phase1_v2_equivalence_v2_one_shot_execution_preregistration.py"
        in workflow
    )

    identity = json.loads(
        (
            ROOT
            / "outputs"
            / "tables"
            / "geophase_phase1_v2_source_corrected_v3"
            / "resolved_runtime_identity.json"
        ).read_text(encoding="utf-8")
    )
    assert identity["formal_execution_count"] == 0
    assert identity["formal_artifact_count"] == 0

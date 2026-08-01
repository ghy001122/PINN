from __future__ import annotations

import ast
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import yaml

from pinnpcm.evaluation.geophase_s0_formal_v3 import execute_unit_v3


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/pinnpcm/evaluation/geophase_s0_formal_v3.py"


def _unit(group: str, **values: object) -> dict[str, object]:
    return {
        "execution_unit_id": f"TRJ-TEST-V3-{group}",
        "execution_group": group,
        "execution_stage": 2,
        "consumer_evaluation_ids": [f"TEST-V3-{group}"],
        "primary_evaluation_id": f"P1V2-{group}-test",
        "fixture_id": None,
        "protocol_id": None,
        "spatial_level": None,
        "time_divisor": None,
        "contact_overlap_m": None,
        **values,
    }


def test_s0_v3_control_plane_has_no_old_trajectory_or_campaign_call() -> None:
    text = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "run_formal_campaign" not in imported_names
    assert "run_s2_streaming_protocol_v2" not in text
    assert "run_s2_streaming_protocol_v3" in imported_names


def test_s0_v3_real_foundation_fixture_uses_frozen_science(tmp_path: Path) -> None:
    payload = execute_unit_v3(
        _unit("FAIL", fixture_id="coordinate_swap"),
        remaining_s=60.0,
        failure_root=tmp_path,
    )
    assert payload["status"] == "PASS"
    assert payload["scientific_vote"] is True
    assert payload["controller_id"] == "controller-v3"


def test_s0_v3_worker_is_spawn_safe_for_real_foundation_fixture(
    tmp_path: Path,
) -> None:
    units = [
        _unit(
            "FAIL",
            execution_unit_id=f"TRJ-TEST-V3-FAIL-{index}",
            fixture_id=fixture,
        )
        for index, fixture in enumerate(
            ("coordinate_swap", "negative_effective_capacity")
        )
    ]
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                execute_unit_v3,
                unit,
                remaining_s=60.0,
                failure_root=tmp_path,
            )
            for unit in units
        ]
        payloads = [future.result(timeout=60.0) for future in futures]

    assert [payload["status"] for payload in payloads] == ["PASS", "PASS"]
    assert all(payload["controller_id"] == "controller-v3" for payload in payloads)


def test_s0_v3_config_freezes_campaign_budget_and_identity() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/geophase_controller_v3_s0_c01_c06_r1.yaml").read_text(
            encoding="utf-8"
        )
    )
    formal = config["formal_s0"]
    assert formal["evaluation_items"] == 63
    assert formal["unique_execution_units"] == 60
    assert formal["legal_reuses"] == 3
    assert formal["worker_count"] == 4
    assert formal["maximum_wall_clock_s"] == 86400
    assert formal["maximum_cpu_time_s"] == 345600
    assert formal["formal_execution_count"] == 0

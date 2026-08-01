from __future__ import annotations

import ast
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation.geophase_s0_direct_physics import (
    S0ExecutionError,
    atomic_json,
    canonical_bytes,
    formal_plan,
    read_canonical_json,
    to_builtin,
    validate_authority,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "geophase_s0_direct_physics_qualification_v1.yaml"
RUNNER = ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_s0_direct_physics.py"
CLI = ROOT / "scripts" / "run_geophase_s0_direct_physics.py"


@dataclass(frozen=True)
class _Payload:
    flag: np.bool_
    integer: np.int64
    floating: np.float64
    array: np.ndarray
    path: Path


def test_recursive_builtin_canonicalization_covers_real_payload_types() -> None:
    payload = _Payload(
        flag=np.bool_(True),
        integer=np.int64(7),
        floating=np.float64(1.25),
        array=np.asarray([[1.0, 2.0], [3.0, 4.0]]),
        path=Path("outputs") / "case.json",
    )
    converted = to_builtin({"nested": [payload, (np.int32(3),)]})
    assert converted == {
        "nested": [
            {
                "flag": True,
                "integer": 7,
                "floating": 1.25,
                "array": [[1.0, 2.0], [3.0, 4.0]],
                "path": "outputs/case.json",
            },
            [3],
        ]
    }
    assert json.loads(canonical_bytes(converted)) == converted


@pytest.mark.parametrize("value", [float("nan"), float("inf"), np.float64("-inf")])
def test_canonicalization_rejects_nonfinite(value: object) -> None:
    with pytest.raises(S0ExecutionError, match="nonfinite"):
        canonical_bytes({"value": value})


def test_atomic_publication_is_canonical_and_hash_verified(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    digest = atomic_json(path, {"z": np.bool_(True), "a": np.asarray([1, 2])})
    assert read_canonical_json(path, digest) == {"a": [1, 2], "z": True}
    path.write_text('{"a":[1,2],"z":false}\n', encoding="utf-8")
    with pytest.raises(S0ExecutionError, match="hash mismatch"):
        read_canonical_json(path, digest)


def test_fresh_runner_has_no_old_e0_equivalence_or_readiness_import() -> None:
    for path in (RUNNER, CLI):
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
        assert not any("geophase_phase1_e0" in item for item in imported)
        assert not any("equivalence" in item for item in imported)
        assert not any("readiness" in item for item in imported)


def test_cli_freezes_threads_before_scientific_imports() -> None:
    source = CLI.read_text(encoding="utf-8")
    environment_guard = source.index('os.environ[_name] = "1"')
    scientific_import = source.index(
        "from pinnpcm.evaluation.geophase_s0_direct_physics import"
    )
    assert environment_guard < scientific_import


def test_goal2_config_freezes_fresh_identity_budgets_ood_and_seeds() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["identity"]["base_commit"] == "d1dd6921beb5614da7dedfe1e4e481b149309ed4"
    assert config["identity"]["old_e0_reuse"] == "forbidden"
    assert config["budgets"]["smoke_wall_clock_s"] == 1800
    assert config["budgets"]["formal_campaign_wall_clock_s"] == 14400
    assert config["budgets"]["training_aggregate_gpu_hours_max"] == 72
    assert config["phase2"]["geometry_ood_contact_overlap_nm"] == [10, 30]
    assert config["phase2"]["protocol_ood"] == "pulse_12p5V"
    assert config["training"]["paired_seeds"] == [
        20260801,
        20260802,
        20260803,
        20260804,
        20260805,
    ]
    assert config["training"]["only_planned_upgrade"] == "C06_dual_axis_homotopy"


def test_authority_and_formal_plan_are_exact() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert len(validate_authority(ROOT, config)) == 14
    plan = formal_plan()
    assert plan["evaluation_items"] == 63
    assert plan["execution_units"] == 60
    assert plan["legal_reuses"] == 3
    assert len(set(plan["unit_ids"])) == 60

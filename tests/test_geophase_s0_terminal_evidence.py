from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from pinnpcm.evaluation.geophase_s0_direct_physics import canonical_bytes


ROOT = Path(__file__).resolve().parents[1]
FORMAL_ROOT = ROOT / "outputs" / "tables" / "geophase_s0_direct_physics" / "formal"


def _registry(campaign_id: str) -> dict[str, object]:
    path = FORMAL_ROOT / campaign_id / "campaign_registry.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_units(campaign_id: str, registry: dict[str, object]) -> None:
    completed = list(registry["completed_unit_ids"])
    expected = dict(registry["unit_sha256"])
    assert len(completed) == len(set(completed))
    assert set(expected) == set(completed)

    unit_root = FORMAL_ROOT / campaign_id / "units"
    paths = sorted(unit_root.glob("*.json.gz"))
    assert {path.name.removesuffix(".json.gz") for path in paths} == set(completed)
    for path in paths:
        unit_id = path.name.removesuffix(".json.gz")
        compressed = path.read_bytes()
        canonical = gzip.decompress(compressed)
        assert hashlib.sha256(compressed).hexdigest() == expected[unit_id][
            "artifact_sha256"
        ]
        assert hashlib.sha256(canonical).hexdigest() == expected[unit_id][
            "canonical_sha256"
        ]
        payload = json.loads(canonical)
        assert canonical_bytes(payload) == canonical
        assert payload["execution_unit_id"] == unit_id
        assert payload["status"] == "PASS"


def test_s0_v1_invalid_attempt_is_immutable_and_nonvoting() -> None:
    registry = _registry("S0-FORMAL-20260801-V1")
    assert registry["state"] == "INVALID_S0_EXECUTION"
    assert registry["validity"] == "invalid"
    assert registry["scientific_vote"] is False
    assert registry["formal_execution_count"] == 0
    assert len(registry["completed_unit_ids"]) == 14
    assert registry["error_type"] == "TypeError"
    assert "int() argument" in registry["error_message"]
    _verify_units("S0-FORMAL-20260801-V1", registry)


def test_s0_v2_terminal_attempt_is_immutable_and_nonvoting() -> None:
    registry = _registry("S0-FORMAL-20260801-V2")
    assert registry["state"] == "INVALID_S0_EXECUTION"
    assert registry["validity"] == "invalid"
    assert registry["scientific_vote"] is False
    assert registry["formal_execution_count"] == 0
    assert len(registry["completed_unit_ids"]) == 25
    assert registry["completed_unit_ids"][-1] == "TRJ-P1V2-REF-zero_drive-S4T4"
    assert registry["error_type"] == "RuntimeError"
    assert registry["error_message"] == "controller-v2 forced remainder failed closed"
    _verify_units("S0-FORMAL-20260801-V2", registry)


def test_s0_terminal_boundary_does_not_publish_scientific_or_c01_results() -> None:
    v2_root = FORMAL_ROOT / "S0-FORMAL-20260801-V2"
    assert not (v2_root / "s0_summary.json").exists()
    assert not (v2_root / "evaluation_verdicts.csv").exists()
    output_root = FORMAL_ROOT.parent
    assert not (output_root / "phase2").exists()
    assert not (output_root / "training").exists()

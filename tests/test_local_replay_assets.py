from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.build_local_replay_asset_manifest import build_manifest
from scripts.verify_local_replay_assets import _validate_ceba, load_manifest, verify_assets


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs/local_replay_asset_manifest_v1.json"
QIU_MAIN = (
    ROOT
    / "data/external/qiu_2024_thermal_neuristor/raw/qiu_2024_main.pdf"
)


def test_local_replay_manifest_has_exact_closed_inventory() -> None:
    payload = load_manifest(MANIFEST)
    records = payload["records"]
    assert len(records) == payload["required_asset_count"] == 50
    assert payload["class_counts"] == {
        "ceba_solver_generated_trajectory": 36,
        "frozen_gt_v1_1": 6,
        "qiu_third_party_pdf": 2,
        "zhang_open_public_input": 6,
    }
    assert len({record["path"] for record in records}) == 50
    assert all(record["identity"] == "exact_raw_bytes" for record in records)
    assert all(len(record["sha256"]) == 64 for record in records)
    assert payload["sealed_metadata_record_count"] == 1
    sealed = payload["sealed_metadata_only_records"][0]
    assert sealed["scientific_access_authorized"] is False
    assert all(member["content_read_prelock"] is False for member in sealed["members"])


@pytest.mark.skipif(not QIU_MAIN.is_file(), reason="local replay assets are not installed")
def test_local_replay_manifest_rebuild_is_deterministic() -> None:
    assert build_manifest(ROOT) == load_manifest(MANIFEST)


def test_ceba_validation_rejects_wrong_cache_key(tmp_path: Path) -> None:
    path = tmp_path / "trajectory.npz"
    np.savez(
        path,
        cache_key=np.asarray("wrong"),
        t=np.asarray([0.0, 1.0]),
        G=np.asarray([1.0, 2.0]),
        I=np.asarray([0.1, 0.2]),
    )
    assert "ceba_cache_key" in _validate_ceba(path, {"cache_key": "expected"})


@pytest.mark.skipif(not QIU_MAIN.is_file(), reason="local replay assets are not installed")
def test_local_replay_assets_and_sealed_metadata_verify() -> None:
    result = verify_assets(root=ROOT, manifest_path=MANIFEST)
    assert result["all_passed"] is True
    assert result["verified_asset_count"] == result["required_asset_count"] == 50
    assert result["failures"] == []
    assert result["sealed_member_payload_accessed"] is False
    assert len(result["sealed_metadata_checks"]) == 2
    assert all(item["passed"] for item in result["sealed_metadata_checks"])


def test_manifest_is_strict_json_without_nonfinite_values() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, allow_nan=False, sort_keys=True)
    assert "NaN" not in serialized

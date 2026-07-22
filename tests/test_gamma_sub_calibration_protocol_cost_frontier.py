from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from pinnpcm.audit.evidence_identity import assert_evidence_lock
from scripts.audit_gamma_sub_calibration_protocol_cost_frontier import (
    DEFAULT_CONFIG,
    _evaluate_case,
    _full_specs,
    _load_config,
    _pilot_specs,
    _resource_components,
    _resource_index,
    _sha256,
    _strict_value,
)


def _portable_input_hashes(config: dict) -> dict[str, str]:
    """Verify exact assets or newline-equivalent tracked historical locks."""

    missing = [str(item["path"]) for item in config["inputs"] if not Path(item["path"]).is_file()]
    if missing:
        manifest = json.loads(
            Path("configs/local_replay_asset_manifest_v1.json").read_text(encoding="utf-8")
        )
        declared = {
            str(record["path"]): str(record["sha256"]).upper()
            for record in manifest["records"]
            if record.get("required_for_local_replay") is True
        }
        expected = {str(item["path"]): str(item["sha256"]).upper() for item in config["inputs"]}
        unexpected = [
            path for path in missing if declared.get(path) != expected.get(path)
        ]
        if unexpected:
            raise AssertionError(f"Undeclared missing CPCF inputs: {unexpected}")
        if os.environ.get("PINN_PUBLIC_CHECKOUT") == "1":
            pytest.skip(
                "public checkout intentionally excludes exact local replay assets: "
                + ", ".join(missing)
            )
        raise AssertionError(f"Required local replay assets are missing: {missing}")

    result: dict[str, str] = {}
    for item in config["inputs"]:
        path = str(item["path"])
        expected = str(item["sha256"])
        assert_evidence_lock(path, expected, root=Path.cwd())
        result[path] = expected
    return result


def test_cpcf_preregistered_pilot_scope_and_strategies() -> None:
    config = _load_config(DEFAULT_CONFIG)
    specs = _pilot_specs(config)
    assert len(specs) == 48
    assert len({spec["id"] for spec in specs}) == 12
    assert all(spec["case_id"].startswith(f"{spec['id']}__") for spec in specs)
    assert sum(bool(spec["fresh_solver_anchor"]) for spec in specs) == 8
    assert {spec["strategy"] for spec in specs} == {
        "calibration_only",
        "protocol_only",
        "sequential_calibration_then_protocol",
        "joint_calibration_protocol_design",
    }
    assert {float(spec["noise"]) for spec in specs} == {0.0, 0.01, 0.02, 0.05}
    assert len(_full_specs(config)) <= int(config["full_sweep_gate"]["full_case_cap"])


def test_cpcf_locked_inputs_and_thresholds_are_unchanged() -> None:
    config = _load_config(DEFAULT_CONFIG)
    hashes = _portable_input_hashes(config)
    assert hashes["data/processed/gt_v1_acceptance/gt_triangle.npz"] == "4e4814d9c66a79cbe86417296b0a797e53ffff2cee2bd881548fbcd35e05c9f8"
    assert float(config["risk"]["success_relative_error_threshold"]) == 0.15
    tolerance = config["solver_anchor"]["historical_tolerance"]
    assert float(tolerance["mean_absolute_discrepancy_max"]) == 0.05373609469259508
    assert int(tolerance["disagreement_count_max"]) == 0


def test_cpcf_resource_index_is_nonmonetary_and_monotone() -> None:
    config = _load_config(DEFAULT_CONFIG)
    weights = config["resource_index"]["weight_sets"]["balanced"]
    loose = {"T_sw_prior_width_K": 1.0, "protocol": "ltp_ltd", "observation_count": 8}
    tight = {"T_sw_prior_width_K": 0.02, "protocol": "multi_pulse_to_ltp_ltd", "observation_count": 64}
    loose_components = _resource_components(loose, config)
    tight_components = _resource_components(tight, config)
    assert _resource_index(loose_components, weights) == 0.0
    assert _resource_index(tight_components, weights) == 1.0
    assert "monetary" in config["forbidden_claims"][0]


def test_cpcf_case_cache_resume_and_strict_json(tmp_path: Path) -> None:
    config = _load_config(DEFAULT_CONFIG)
    config["pilot"]["cache_dir"] = str(tmp_path / "cache")
    spec = next(spec for spec in _pilot_specs(config) if not spec["fresh_solver_anchor"])
    input_hashes = _portable_input_hashes(config)
    config_hash = _sha256(DEFAULT_CONFIG)
    script_hash = _sha256(Path("scripts/audit_gamma_sub_calibration_protocol_cost_frontier.py"))
    first = _evaluate_case(spec, config, config_hash=config_hash, input_hashes=input_hashes, script_hash=script_hash, resume=True)
    second = _evaluate_case(spec, config, config_hash=config_hash, input_hashes=input_hashes, script_hash=script_hash, resume=True)
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    cache_files = list((tmp_path / "cache").glob("*.json"))
    assert len(cache_files) == 1
    json.loads(cache_files[0].read_text(encoding="utf-8"))
    try:
        _strict_value(float("nan"))
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("strict serialization accepted NaN")
    assert np.isfinite(float(first["predicted_relative_error"]))

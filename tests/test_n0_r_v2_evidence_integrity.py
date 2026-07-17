"""Evidence-integrity tests for the N0-R v2 audit and v3 lock policy."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from pinnpcm.pinn.n0_cv_evidence import (
    canonical_lf_sha256,
    deterministic_npz_bytes,
    load_frozen_gt,
    semantic_sha256,
    tamper_detection,
    trajectory_ledgers,
    v2_gate_coverage_audit,
)


def test_cross_platform_text_and_semantic_hashes_ignore_newline_and_key_order(tmp_path: Path) -> None:
    left = tmp_path / "left.yaml"
    right = tmp_path / "right.yaml"
    left.write_bytes(b"a: 1\r\nb: 2\r\n")
    right.write_bytes(b"b: 2\na: 1\n")
    assert semantic_sha256(left) == semantic_sha256(right)

    text_lf = tmp_path / "lf.txt"
    text_crlf = tmp_path / "crlf.txt"
    text_lf.write_bytes(b"alpha\nbeta\n")
    text_crlf.write_bytes(b"alpha\r\nbeta\r\n")
    assert canonical_lf_sha256(text_lf) == canonical_lf_sha256(text_crlf)


def test_deterministic_npz_bytes_are_stable_and_loadable(tmp_path: Path) -> None:
    arrays = {"z": np.arange(4, dtype=np.float64), "a": np.eye(2, dtype=np.float64)}
    first = deterministic_npz_bytes(arrays)
    second = deterministic_npz_bytes(dict(reversed(list(arrays.items()))))
    assert first == second
    path = tmp_path / "stable.npz"
    path.write_bytes(first)
    with np.load(path, allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive["z"], arrays["z"])
        np.testing.assert_array_equal(archive["a"], arrays["a"])


def test_independent_adjacent_state_ledgers_pass_and_tampering_fails() -> None:
    gt, params = load_frozen_gt(Path("data/processed/gt_v1_acceptance/gt_triangle.npz"))
    ledger = trajectory_ledgers(gt, params)
    assert ledger["defect"]["gate_value"] <= 0.01
    assert ledger["energy"]["gate_value"] <= 0.05
    tamper = tamper_detection(gt, params)
    assert tamper["defect_tamper_detected"] is True
    assert tamper["energy_tamper_detected"] is True


def test_v2_gate_coverage_fails_closed_without_rewriting_history() -> None:
    v2_config = yaml.safe_load(Path("configs/full_pinn_n0_repair_v2.yaml").read_text(encoding="utf-8"))
    v2_result = json.loads(
        Path("outputs/tables/full_pinn_n0_repair_data_free_seed_20260715_v2.json").read_text(
            encoding="utf-8"
        )
    )
    audit = v2_gate_coverage_audit(v2_config, v2_result)
    assert audit["coverage_complete"] is False
    assert "ic_bc_max_normalized_error" in audit["documented_gaps"]
    assert "frozen_gt_hash_unchanged_required" in audit["documented_gaps"]
    assert "defect_mass_ledger_max" in audit["documented_gaps"]
    assert audit["historical_outputs_rewritten"] is False

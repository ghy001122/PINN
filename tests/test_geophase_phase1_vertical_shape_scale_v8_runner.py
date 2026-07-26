from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_geophase_phase1_vertical_shape_scale_v8.py"
FORMAL_PATH = ROOT / "configs" / "geophase_phase1_2p5d_reference.yaml"
REPAIR_PATH = ROOT / "configs" / "geophase_phase1_vertical_shape_scale_v8.yaml"
V7_REPAIR_PATH = ROOT / "configs" / "geophase_phase1_vertical_repair_v7.yaml"

SPEC = importlib.util.spec_from_file_location("phase1_vertical_v8_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _pair_result(
    pair_id: str,
    pair: dict[str, Any],
    raws: dict[tuple[float, str], object],
    *,
    foundation_pass: bool,
    depth_pass: bool,
) -> dict[str, object]:
    return {
        "pair_id": pair_id,
        "production_depth_m": float(pair["production_depth_m"]),
        "comparator_depth_m": float(pair["comparator_depth_m"]),
        "temporary_ratio_r": 1.0,
        "raw_device_G_W_K": 2.0,
        "raw_device_C_J_K": 3.0,
        "foundation_pass": foundation_pass,
        "depth_pass": depth_pass,
        "pair_pass": foundation_pass and depth_pass,
        "failure_metric_ids": [] if foundation_pass and depth_pass else ["fixture"],
        "candidate_rows": [],
        "pointwise_rows": [],
        "passivity_rows": [],
        "raws": raws,
    }


def _patch_lightweight_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    foundation_pass: bool,
    depth_pass: bool,
    postscale_pass: bool | None,
) -> list[str]:
    monkeypatch.setattr(
        RUNNER,
        "_verify_entry",
        lambda *_args, **_kwargs: {
            "preregistration_sha": "a" * 40,
            "repair_yaml_sha256": "b" * 64,
            "head_at_screening": "c" * 40,
            "branch_at_screening": "codex/phase1-vertical-shape-scale-v8",
            "origin_branch_head_at_screening": "c" * 40,
        },
    )
    monkeypatch.setattr(
        RUNNER,
        "build_repair_overlay_branch",
        lambda *_args, **_kwargs: (object(), np.asarray([1.0e-9])),
    )
    monkeypatch.setattr(
        RUNNER,
        "build_repair_substrate_branch",
        lambda *_args, substrate_depth_m, **_kwargs: (
            object(),
            np.asarray([float(substrate_depth_m)]),
        ),
    )
    evaluated_pair_ids: list[str] = []

    def evaluate(
        pair_id: str,
        pair: dict[str, Any],
        raws: dict[tuple[float, str], object],
        *_args: object,
    ) -> dict[str, object]:
        evaluated_pair_ids.append(pair_id)
        return _pair_result(
            pair_id,
            pair,
            raws,
            foundation_pass=foundation_pass,
            depth_pass=depth_pass,
        )

    monkeypatch.setattr(RUNNER, "_evaluate_pair", evaluate)
    monkeypatch.setattr(RUNNER, "_write_evidence", lambda *_args, **_kwargs: None)
    if postscale_pass is not None:
        monkeypatch.setattr(
            RUNNER,
            "_postscale_checks",
            lambda *_args, **_kwargs: (
                {"postscale_pass": postscale_pass},
                [],
                object(),
            ),
        )
    return evaluated_pair_ids


def test_response_pass_uses_separate_mesh_and_depth_gates_and_ignores_impulse() -> None:
    repair = _yaml(REPAIR_PATH)
    metrics = {
        "step_response_nrmse": 9.0e-3,
        "impulse_response_nrmse": 1.0e9,
        "frequency_log_magnitude_rmse": 9.0e-3,
    }
    assert RUNNER._response_pass(metrics, repair, "mesh_D") is True
    assert RUNNER._response_pass(metrics, repair, "mesh_2D") is True
    assert RUNNER._response_pass(metrics, repair, "depth") is True

    mesh_failure = {**metrics, "step_response_nrmse": 1.01e-2}
    assert RUNNER._response_pass(mesh_failure, repair, "mesh_D") is False
    assert RUNNER._response_pass(mesh_failure, repair, "depth") is True

    depth_only = {
        **metrics,
        "step_response_nrmse": 4.9e-2,
        "frequency_log_magnitude_rmse": 4.9e-2,
    }
    assert RUNNER._response_pass(depth_only, repair, "depth") is True
    assert RUNNER._response_pass(depth_only, repair, "mesh_D") is False
    assert (
        RUNNER._response_pass(
            {**depth_only, "frequency_log_magnitude_rmse": 5.01e-2},
            repair,
            "depth",
        )
        is False
    )


def test_temporary_ratio_is_exactly_aC_over_aG_without_mutating_raw_coefficients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formal = _yaml(FORMAL_PATH)
    repair_v7 = _yaml(V7_REPAIR_PATH)
    overlay, overlay_widths = RUNNER.build_repair_overlay_branch(
        formal, repair_v7, grid_level="fine"
    )
    raw = RUNNER.RawVerticalComponents(
        substrate=RUNNER.build_repair_substrate_branch(
            formal,
            repair_v7,
            substrate_depth_m=4.0e-7,
            grid_level="fine",
        )[0],
        overlay=overlay,
        region_areas_m2=RUNNER._areas(formal),
        substrate_depth_m=4.0e-7,
        grid_level="fine",
        substrate_cell_widths_m=RUNNER.build_repair_substrate_branch(
            formal,
            repair_v7,
            substrate_depth_m=4.0e-7,
            grid_level="fine",
        )[1],
        overlay_cell_widths_m=overlay_widths,
    )
    substrate_capacity = raw.substrate.capacities_J_m2K.copy()
    substrate_matrix = raw.substrate.conductance_matrix_W_m2K.copy()
    overlay_capacity = raw.overlay.capacities_J_m2K.copy()
    overlay_matrix = raw.overlay.conductance_matrix_W_m2K.copy()
    monkeypatch.setattr(
        RUNNER,
        "apply_repair_normalization",
        lambda *_args, **_kwargs: pytest.fail(
            "temporary coordinate mapping must not normalize raw coefficients"
        ),
    )

    ratio, raw_G, raw_C = RUNNER._temporary_coordinate_ratio(raw, formal)
    target_G, target_C = RUNNER._targets(formal)
    assert ratio == pytest.approx((target_C / raw_C) / (target_G / raw_G))
    assert np.array_equal(raw.substrate.capacities_J_m2K, substrate_capacity)
    assert np.array_equal(raw.substrate.conductance_matrix_W_m2K, substrate_matrix)
    assert np.array_equal(raw.overlay.capacities_J_m2K, overlay_capacity)
    assert np.array_equal(raw.overlay.conductance_matrix_W_m2K, overlay_matrix)


def test_primary_foundation_failure_never_triggers_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated = _patch_lightweight_run(
        monkeypatch,
        foundation_pass=False,
        depth_pass=False,
        postscale_pass=None,
    )
    summary = RUNNER.run(
        FORMAL_PATH,
        REPAIR_PATH,
        preregistration_sha="a" * 40,
        repair_yaml_sha256="b" * 64,
    )

    assert evaluated == ["primary_51p2um_vs_102p4um"]
    assert summary["conditional_second_pair_triggered"] is False
    assert summary["evaluated_pair_ids"] == ["primary_51p2um_vs_102p4um"]
    assert summary["stop_reason"] == "primary_foundation_failure"
    assert summary["final_disposition"] == "NO_GO_VERTICAL_REFERENCE"
    assert summary["final_disposition_reached"] is True


def test_vertical_pass_leaves_final_disposition_open_for_k_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated = _patch_lightweight_run(
        monkeypatch,
        foundation_pass=True,
        depth_pass=True,
        postscale_pass=True,
    )
    summary = RUNNER.run(
        FORMAL_PATH,
        REPAIR_PATH,
        preregistration_sha="a" * 40,
        repair_yaml_sha256="b" * 64,
    )

    assert evaluated == ["primary_51p2um_vs_102p4um"]
    assert summary["vertical_status"] == "PASS_VERTICAL_REFERENCE"
    assert summary["selected_production_depth_m"] == pytest.approx(5.12e-5)
    assert summary["final_disposition"] is None
    assert summary["final_disposition_reached"] is False
    assert summary["stage_disposition"] == "VERTICAL_PASS_PENDING_K_STATE"


def test_pure_primary_depth_failure_alone_triggers_the_fallback_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated = _patch_lightweight_run(
        monkeypatch,
        foundation_pass=True,
        depth_pass=False,
        postscale_pass=True,
    )
    repair = _yaml(REPAIR_PATH)
    pairs = repair["candidate_protocol"]["pairs"]

    def evaluate(
        pair_id: str,
        pair: dict[str, Any],
        raws: dict[tuple[float, str], object],
        *_args: object,
    ) -> dict[str, object]:
        evaluated.append(pair_id)
        is_fallback = pair_id == "conditional_maximum_102p4um_vs_204p8um"
        return _pair_result(
            pair_id,
            pair,
            raws,
            foundation_pass=True,
            depth_pass=is_fallback,
        )

    monkeypatch.setattr(RUNNER, "_evaluate_pair", evaluate)
    summary = RUNNER.run(
        FORMAL_PATH,
        REPAIR_PATH,
        preregistration_sha="a" * 40,
        repair_yaml_sha256="b" * 64,
    )

    assert list(pairs) == [
        "primary_51p2um_vs_102p4um",
        "conditional_maximum_102p4um_vs_204p8um",
    ]
    assert evaluated == list(pairs)
    assert summary["conditional_second_pair_triggered"] is True
    assert summary["actual_unique_raw_build_count"] == 8
    assert summary["selected_production_depth_m"] == pytest.approx(1.024e-4)
    assert summary["final_disposition"] is None


def test_entry_rejects_wrong_branch_before_screening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repair = _yaml(REPAIR_PATH)
    monkeypatch.setattr(RUNNER, "_verify_commit_exists", lambda _commit: None)

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return "c" * 40
        if args == ("branch", "--show-current"):
            return "main"
        raise AssertionError(f"unexpected Git query: {args}")

    monkeypatch.setattr(RUNNER, "_git", fake_git)
    with pytest.raises(RuntimeError, match="requires branch"):
        RUNNER._verify_entry(
            REPAIR_PATH,
            repair,
            preregistration_sha="a" * 40,
            repair_yaml_sha256=hashlib.sha256(REPAIR_PATH.read_bytes()).hexdigest(),
        )


def test_entry_rejects_wrong_repair_yaml_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repair = _yaml(REPAIR_PATH)
    required_branch = repair["authority"]["required_branch"]
    monkeypatch.setattr(RUNNER, "_verify_commit_exists", lambda _commit: None)
    monkeypatch.setattr(RUNNER, "_require_ancestor", lambda *_args: None)

    def fake_git(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return "c" * 40
        if args == ("branch", "--show-current"):
            return str(required_branch)
        if args == ("show", "-s", "--format=%s", "a" * 40):
            return repair["execution_boundary"][
                "required_repair_protocol_commit_message"
            ]
        if args == ("rev-parse", "--verify", f"origin/{required_branch}"):
            return "c" * 40
        raise AssertionError(f"unexpected Git query: {args}")

    monkeypatch.setattr(RUNNER, "_git", fake_git)
    with pytest.raises(RuntimeError, match="YAML hash"):
        RUNNER._verify_entry(
            REPAIR_PATH,
            repair,
            preregistration_sha="a" * 40,
            repair_yaml_sha256="0" * 64,
        )

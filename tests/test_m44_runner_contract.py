from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest
import yaml

from scripts import run_m44_qiu_heterogeneous_3d_thermal as runner


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m44_qiu_heterogeneous_3d_thermal.yaml"


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_m44_locked_config_expands_exactly_31_unique_thermal_cases() -> None:
    config = _config()
    contract = runner._validate_config_contract(config)
    cases = runner._expand_case_matrix(config)
    assert contract["passed"] is True
    assert contract["failed_checks"] == []
    assert len(cases) == 31
    assert len({case["id"] for case in cases}) == 31
    assert sum(case["mode"] == "homogeneous" for case in cases) == 2
    assert sum(case["mode"] == "layered1d" for case in cases) == 2
    assert sum(case["mode"] == "heterogeneous_3d" for case in cases) == 18
    assert sum(case["mode"] == "xz" for case in cases) == 9


@pytest.mark.parametrize(
    "tamper",
    [
        lambda cfg: cfg["budget"].update(maximum_unique_thermal_forwards=64),
        lambda cfg: cfg["budget"].update(no_rescue_round=False),
        lambda cfg: cfg["geometry"].update(quarter_power_W=1.0e-6),
        lambda cfg: cfg["interfaces"].update(
            voting_thermal_boundary_resistance_m2K_W=1.0e-8
        ),
        lambda cfg: cfg["decision"].update(
            any_gate_fails="M44_HET3D_GO_ROBUST"
        ),
        lambda cfg: cfg["evidence_boundary"].update(inverse_runs=1),
        lambda cfg: cfg["outputs"].update(summary="somewhere/else.json"),
    ],
)
def test_m44_config_tampering_fails_closed(tamper) -> None:
    config = deepcopy(_config())
    tamper(config)
    contract = runner._validate_config_contract(config)
    assert contract["passed"] is False
    assert contract["failed_checks"]


def test_m44_one_shot_receipt_is_exclusive_and_prohibits_nonthermal_work(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "receipt.json"
    summary_path = tmp_path / "summary.json"
    receipt = runner._create_execution_receipt(
        receipt_path,
        summary_path,
        "A" * 40,
        "B" * 64,
        {runner.CANONICAL_CONFIG: "C" * 64},
    )
    assert receipt["formal_runner_invocations"] == 1
    assert receipt["terminal_rerun_forbidden"] is True
    assert receipt["prohibited_run_accounting"] == runner.EXPECTED_PROHIBITED_RUN_ACCOUNTING
    assert all(
        value in (0, False)
        for value in receipt["prohibited_run_accounting"].values()
    )
    with pytest.raises(RuntimeError, match="rerun is forbidden"):
        runner._create_execution_receipt(
            receipt_path,
            summary_path,
            "A" * 40,
            "B" * 64,
            {},
        )


def test_protected_paths_resolve_under_direct_script_style_sys_path(
    monkeypatch,
) -> None:
    """The formal CLI must resolve its M43 protection import before receipt."""

    root_text = str(ROOT)
    monkeypatch.setattr(sys, "path", [item for item in sys.path if item != root_text])
    paths = runner._protected_paths()
    assert root_text in sys.path
    assert any(path.name == "m43_final_validation.json" for path in paths)


def test_m44_terminal_decision_cannot_hide_one_failed_gate() -> None:
    config = _config()
    gates = runner._fail_closed_gate_records(config)
    for record in gates.values():
        record["value"] = record["threshold"]
        record["passed"] = True
    assert runner._terminal_decision(config, gates, 0.01) == (
        "M44_HET3D_GO_ROBUST",
        "qualified_supported",
    )
    gates["steady_normalized_power_imbalance"]["passed"] = False
    assert runner._terminal_decision(config, gates, 0.0) == (
        "M44_STOP_REAL_GEOMETRY_UPGRADE",
        "failed_but_informative",
    )
    del gates["steady_normalized_power_imbalance"]
    assert runner._terminal_decision(config, gates, 0.0)[0] == (
        "M44_STOP_REAL_GEOMETRY_UPGRADE"
    )


def _synthetic_result(config: dict, case: dict, R: float) -> dict:
    times = np.asarray(config["time"]["output_times_s"], dtype=float)
    curve = R * np.linspace(0.2, 0.9, times.size)
    kind = case["kind"]
    mode = case["mode"]
    source_id = case.get("source_id", "S_surface_anchor")
    fraction = 0.25 if mode in {"homogeneous", "heterogeneous_3d"} else 0.5
    audit = {
        "source_id": source_id,
        "source_power_integration_relative_error": 0.0,
        "source_geometry_integration_relative_error": 0.0,
        "integrated_model_power_W": config["geometry"]["full_power_W"] * fraction,
        "expected_model_power_W": config["geometry"]["full_power_W"] * fraction,
    }
    if mode == "homogeneous":
        audit["surface_source_area_m2"] = config["time"]["source_area_m2"] / 4.0
    elif mode in {"heterogeneous_3d", "xz"}:
        volume = (
            config["geometry"]["vo2_full_x_m"]
            * config["geometry"]["vo2_full_y_m"]
            * config["geometry"]["vo2_thickness_m"]
            * fraction
        )
        if source_id == "S_contact":
            volume *= config["geometry"]["contact_support_fraction_of_half_x"]
        audit["vo2_source_support_volume_m3"] = volume
        audit["source_cell_count"] = 4
        audit["contact_support_face_aligned"] = True
    if mode == "layered1d":
        reference_times = np.asarray(
            config["layered_reference"]["comparison_times_s"], dtype=float
        )
        curve = R * np.linspace(0.1, 0.8, reference_times.size)
        times = reference_times
    metrics = {
        "source_mean_Zth_K_W": (100.0 * curve).tolist(),
        "source_surface_face_Zth_K_W": curve.tolist() if kind == "transient" else R,
        "vo2_mean_Zth_K_W": curve.tolist() if kind == "transient" else R,
        "vo2_tmax_rise_K": (curve * config["geometry"]["full_power_W"]).tolist()
        if kind == "transient"
        else R * config["geometry"]["full_power_W"],
    }
    if kind == "transient":
        metrics["time_s"] = times.tolist()
    ledger = (
        {"normalized_power_imbalance": 0.0}
        if kind == "steady"
        else {"maximum_normalized_sensible_energy_imbalance": 0.0}
    )
    return {
        "case_id": case["id"],
        "mode": mode,
        "kind": kind,
        "mesh": case.get("mesh"),
        "domain": case.get("domain"),
        "time_profile": case.get("time"),
        "source_id": source_id,
        "source_audit": audit,
        "finite": True,
        "positive": True,
        "active_cell_count": 10,
        "metrics": metrics,
        "ledger": ledger,
    }


def test_m44_recovery_gates_use_neumann_source_face_not_cell_center() -> None:
    config = _config()
    R = float(config["reference"]["m43_steady_R_ref_K_W"])
    cases = runner._expand_case_matrix(config)
    results = {case["id"]: _synthetic_result(config, case, R) for case in cases}
    m43_curve = np.asarray(
        results["homogeneous_transient_M3D3"]["metrics"][
            "source_surface_face_Zth_K_W"
        ],
        dtype=float,
    )
    layered_curve = np.asarray(
        results["layered1d_transient"]["metrics"][
            "source_surface_face_Zth_K_W"
        ],
        dtype=float,
    )
    layered = {
        "steady_R_K_W": R,
        "fine_Zth_K_W": layered_curve,
        "self_refinement_change": 0.0,
        "single_slab_error": 0.0,
    }
    gates, diagnostics = runner._aggregate_gates(
        config,
        results,
        {"steady_R_K_W": R, "Zth_K_W": m43_curve},
        layered,
        forward_count=31,
        cpu_time_s=0.1,
    )
    assert diagnostics["homogeneous_steady_error"] == pytest.approx(0.0)
    assert diagnostics["homogeneous_transient_error"] == pytest.approx(0.0)
    assert diagnostics["layered_steady_error"] == pytest.approx(0.0)
    assert diagnostics["layered_transient_error"] == pytest.approx(0.0)
    assert all(gates[name]["passed"] for name in (
        "homogeneous_steady_recovery_error",
        "homogeneous_transient_recovery_error",
        "layered_1d_steady_reference_error",
        "layered_1d_transient_reference_error",
    ))
    # The cell-center values are intentionally wrong by two orders of magnitude.
    assert results["homogeneous_steady_M3D3"]["metrics"]["source_mean_Zth_K_W"] != R
    assert diagnostics["maximum_heterogeneity_departure"] == pytest.approx(0.0)
    assert diagnostics["heterogeneity_normalized_rmse_by_source"]
    assert diagnostics["non_voting_steady_source_envelope"] == pytest.approx(0.0)


def test_m44_attestation_identity_verifies_all_seven_raw_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    artifacts = {}
    for index in range(7):
        path = tmp_path / f"artifact_{index}.bin"
        path.write_bytes(f"artifact-{index}".encode())
        artifacts[path.name] = runner.hashlib.sha256(path.read_bytes()).hexdigest().upper()
    attestation = tmp_path / "outputs" / "tables" / "m43_postcommit_attestation.json"
    attestation.parent.mkdir(parents=True)
    attestation.write_text(
        runner.json.dumps({"artifact_sha256": artifacts}), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    identity = runner._verify_m43_postcommit_attestation()
    assert identity["passed"] is True
    assert identity["artifact_count"] == 7
    (tmp_path / "artifact_3.bin").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="attested artifact identity failed"):
        runner._verify_m43_postcommit_attestation()


def test_layered_fixed_cases_use_locked_fine_fvm_resolution(monkeypatch) -> None:
    config = _config()
    case = next(
        item for item in runner._expand_case_matrix(config) if item["id"] == "layered1d_steady"
    )
    calls: dict[str, object] = {}
    system = object()
    monkeypatch.setattr(
        runner.thermal_solver,
        "build_layered_1d_grid",
        lambda _config, *, resolution: calls.setdefault("resolution", resolution),
    )
    monkeypatch.setattr(
        runner.thermal_solver,
        "assemble_heterogeneous_system",
        lambda _config, grid: system,
    )
    monkeypatch.setattr(
        runner.thermal_solver,
        "build_layered_top_source",
        lambda _config, _system: (
            np.asarray([1.0]),
            {
                "source_id": "S_layered_top_isoflux",
                "source_power_integration_relative_error": 0.0,
                "source_geometry_integration_relative_error": 0.0,
            },
        ),
    )
    monkeypatch.setattr(
        runner.thermal_solver,
        "solve_steady",
        lambda _system, _source, *, full_power_W: {
            "finite": True,
            "positive": True,
            "active_cell_count": 1,
            "metrics": {
                "source_surface_face_Zth_K_W": 1.0,
                "source_mean_Zth_K_W": 0.5,
            },
            "ledger": {"normalized_power_imbalance": 0.0},
        },
    )
    runner._execute_case(config, case)
    assert calls["resolution"] == "fine"

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m43_finite_width_thermal_spreading.yaml"
SUMMARY = ROOT / "outputs" / "tables" / "m43_finite_width_thermal_spreading_summary.json"
CASES = ROOT / "outputs" / "tables" / "m43_finite_width_thermal_spreading_cases.csv"
REFERENCE = ROOT / "outputs" / "tables" / "m43_transient_green_reference.csv"
RECEIPT = ROOT / "outputs" / "tables" / "m43_execution_receipt.json"
POSTPROCESSING = ROOT / "outputs" / "tables" / "m43_figure_postprocessing_manifest.json"
FIGURE = ROOT / "outputs" / "figures" / "m43" / "m43_thermal_spreading_closure.png"
REPORT = ROOT / "docs" / "codex_reports" / "m43_finite_width_thermal_spreading_closure.md"

EXPECTED_CASE_IDS = (
    "square_steady_M1D3",
    "square_steady_M2D3",
    "square_steady_M3D3",
    "square_steady_M3D1",
    "square_steady_M3D2",
    "rho5_steady_M2D3",
    "rho5_steady_M3D3",
    "rho5_steady_M3D2",
    "rho5_transient_M2D3_base",
    "rho5_transient_M3D3_base",
    "rho5_transient_M3D2_base",
    "rho5_transient_M3D3_fine",
    "rho5_xz_M2D3_base",
    "rho5_xz_M3D3_base",
    "rho5_xz_M3D2_base",
)
EXPECTED_GATE_TO_CONFIG = {
    "eq21_rho1_relative_error": ("gates", "eq21_rho1_relative_error_max"),
    "eq21_rho5_relative_error": ("gates", "eq21_rho5_relative_error_max"),
    "green_early_limit_error": ("gates", "green_early_limit_error_max"),
    "green_long_limit_error": ("gates", "green_long_limit_error_max"),
    "green_quadrature_refinement_change": ("gates", "green_quadrature_refinement_change_max"),
    "steady_rho1_reference_error": ("gates", "steady_rho1_reference_error_max"),
    "steady_rho5_reference_error": ("gates", "steady_rho5_reference_error_max"),
    "rho5_mesh_pair_change": ("gates", "rho5_mesh_pair_change_max"),
    "rho5_domain_pair_change": ("gates", "rho5_domain_pair_change_max"),
    "steady_normalized_power_imbalance": ("gates", "steady_normalized_power_imbalance_max"),
    "transient_3d_green_normalized_max_error": ("gates", "transient_3d_green_normalized_max_error_max"),
    "transient_time_pair_change": ("gates", "transient_time_pair_change_max"),
    "transient_normalized_sensible_energy_imbalance": ("gates", "transient_normalized_sensible_energy_imbalance_max"),
    "finite_width_bias_mesh_pair_absolute_change": ("gates", "finite_width_bias_mesh_pair_absolute_change_max"),
    "finite_width_bias_domain_pair_absolute_change": ("gates", "finite_width_bias_domain_pair_absolute_change_max"),
    "source_area_integral_error": ("gates", "source_area_integral_error_max"),
    "source_power_integral_error": ("gates", "source_power_integral_error_max"),
    "near_zero_outflow_normalized_change": ("gates", "near_zero_outflow_normalized_change_max"),
    "finite_nan_clip_source_smearing_unit_error": ("gates", "finite_nan_clip_source_smearing_unit_error"),
    "wall_clock_budget": ("budget", "maximum_wall_clock_s"),
    "cpu_time_budget": ("budget", "maximum_cpu_time_s"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_m43_result_locks_exact_gates_thresholds_and_terminal_decision() -> None:
    summary = _summary()
    config = _config()
    gates = summary["gates"]
    assert set(gates) == set(EXPECTED_GATE_TO_CONFIG)
    assert len(gates) == summary["gate_total_count"] == 21

    for name, (section, key) in EXPECTED_GATE_TO_CONFIG.items():
        record = gates[name]
        assert set(record) >= {"value", "threshold", "relation", "passed"}
        assert isinstance(record["passed"], bool)
        assert record["threshold"] == config[section][key]
        expected_relation = "equal" if name == "finite_nan_clip_source_smearing_unit_error" else "max"
        assert record["relation"] == expected_relation
        value = record["value"]
        if value is None:
            assert record["passed"] is False
        elif expected_relation == "equal":
            assert isinstance(value, bool)
            assert record["passed"] is (value is bool(record["threshold"]))
        else:
            assert math.isfinite(float(value))
            assert record["passed"] is (float(value) <= float(record["threshold"]))

    pass_count = sum(record["passed"] for record in gates.values())
    failed = [name for name, record in gates.items() if not record["passed"]]
    assert summary["gate_pass_count"] == pass_count
    assert summary["failed_gates"] == failed

    accounting = summary["forward_accounting"]
    forwards = int(accounting["unique_thermal_pde_forwards"])
    completed = bool(accounting["confirmatory_completed"])
    assert 0 <= forwards <= int(accounting["maximum_unique_pde_forwards"]) == 16
    assert completed is (forwards == int(accounting["preregistered_pde_forwards"]) == 15)
    all_pass = all(record["passed"] for record in gates.values())
    if all_pass and completed:
        assert summary["decision"] == "M43_THERMAL_CLOSURE_GO_COMPONENT_ONLY"
        assert summary["status"] == "qualified_supported"
    else:
        assert summary["decision"] == "M43_STOP_C_FREEZE_1D"
        assert summary["status"] == "failed_but_informative"


def test_m43_result_receipt_cases_and_hashes_are_consistent() -> None:
    summary = _summary()
    config = _config()
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    rows = _csv_rows(CASES)
    accounting = summary["forward_accounting"]
    forwards = int(accounting["unique_thermal_pde_forwards"])
    attempted = int(receipt["forward_invocations_attempted"])
    completed = int(receipt["forward_invocations_completed"])

    assert receipt["schema_version"] == "m43_one_shot_execution_receipt_v1"
    assert receipt["formal_runner_invocations"] == 1
    assert receipt["terminal_rerun_forbidden"] is True
    assert receipt["preregistration_commit"] == summary["preregistration_commit"]
    assert receipt["config_sha256"] == summary["config_sha256"] == _sha256(CONFIG)
    assert completed == forwards <= attempted <= 16
    assert len(receipt["cases"]) == attempted
    assert tuple(case["case_id"] for case in receipt["cases"]) == EXPECTED_CASE_IDS[:attempted]
    assert tuple(row["case_id"] for row in rows) == EXPECTED_CASE_IDS[:forwards]
    assert sum(case["status"] == "completed" for case in receipt["cases"]) == completed
    assert set(accounting["canonical_case_sha256"]) == {
        row["canonical_case_sha256"] for row in rows
    }
    assert len(set(accounting["canonical_case_sha256"])) == forwards
    for row in rows:
        digest = row["canonical_case_sha256"]
        assert len(digest) == 64
        int(digest, 16)

    if forwards == 15:
        assert tuple(row["case_id"] for row in rows) == EXPECTED_CASE_IDS
        assert receipt["status"] == "completed"
        assert receipt["confirmatory_completed"] is True
    else:
        assert receipt["status"] == "terminal_stopped"
        assert receipt["confirmatory_completed"] is False

    output_paths = {
        "cases": CASES,
        "transient_reference": REFERENCE,
        "figure": FIGURE,
    }
    assert set(summary["artifact_sha256"]) == set(output_paths)
    for key, path in output_paths.items():
        assert path.is_file() and path.stat().st_size > 0
        assert summary["artifact_sha256"][key] == _sha256(path)

    postprocessing = json.loads(POSTPROCESSING.read_text(encoding="utf-8"))
    amendment = summary["visualization_only_amendment"]
    assert postprocessing["schema_version"] == "m43_figure_postprocessing_manifest_v1"
    assert postprocessing["evidence_role"] == "visualization_only_non_voting_amendment"
    assert postprocessing["final_figure_sha256"] == amendment["final_figure_sha256"] == _sha256(FIGURE)
    assert postprocessing["builder_sha256"] == summary["postprocessing_code_sha256"]["figure_builder"]
    assert postprocessing["pde_forwards"] == amendment["pde_forwards"] == 0
    for key in ("gate_values_changed", "cases_csv_changed", "transient_reference_csv_changed"):
        assert postprocessing[key] is amendment[key] is False

    code_paths = {
        "runner": ROOT / "scripts" / "run_m43_finite_width_thermal_spreading.py",
        "reference": ROOT / "src" / "pinnpcm" / "physics" / "m43_thermal_spreading_reference.py",
        "solver": ROOT / "src" / "pinnpcm" / "solvers" / "m43_finite_width_thermal.py",
    }
    assert set(summary["runtime_code_sha256"]) == set(code_paths)
    for key, path in code_paths.items():
        assert summary["runtime_code_sha256"][key] == _sha256(path)

    for relative, digest in summary["preregistration_file_sha256"].items():
        assert _sha256(ROOT / relative) == digest
    assert summary["protected_baseline_identity"]["verified"] is True
    assert summary["protected_baseline_identity"]["record_count"] > 0
    assert summary["protected_baseline_identity"]["failures"] == []
    for relative, record in summary["protected_evidence"].items():
        path = ROOT / relative
        assert path.is_file()
        assert _sha256(path) == record["sha256"]
        assert path.stat().st_size == record["bytes"]

    assert REPORT.is_file() and REPORT.stat().st_size > 0
    report = REPORT.read_text(encoding="utf-8")
    assert summary["decision"] in report
    assert summary["status"] in report
    assert str(summary["preregistration_commit"]) in report
    assert config["outputs"]["execution_receipt"] == RECEIPT.relative_to(ROOT).as_posix()


def test_m43_green_reference_artifact_has_nine_locked_monotone_times() -> None:
    config = _config()
    rows = _csv_rows(REFERENCE)
    assert len(rows) == 9
    Fo = np.asarray([float(row["Fo_A"]) for row in rows])
    times = np.asarray([float(row["time_s"]) for row in rows])
    theta_base = np.asarray([float(row["Theta_base"]) for row in rows])
    theta_fine = np.asarray([float(row["Theta_fine"]) for row in rows])
    z_base = np.asarray([float(row["Z_green_K_W"]) for row in rows])
    z_fine = np.asarray([float(row["Z_green_fine_K_W"]) for row in rows])
    steady = np.asarray([float(row["steady_Rs_K_W"]) for row in rows])

    assert np.array_equal(Fo, np.asarray(config["time"]["fvm_comparison_Fo_A"], dtype=float))
    assert np.allclose(
        times,
        np.asarray(config["time"]["fvm_comparison_times_s"], dtype=float),
        rtol=1.0e-14,
        atol=0.0,
    )
    for values in (theta_base, theta_fine, z_base, z_fine, steady):
        assert np.all(np.isfinite(values))
        assert np.all(values > 0.0)
    assert np.all(np.diff(times) > 0.0)
    assert np.all(np.diff(theta_base) >= 0.0)
    assert np.all(np.diff(theta_fine) >= 0.0)
    assert np.all(np.diff(z_base) >= 0.0)
    assert np.all(np.diff(z_fine) >= 0.0)
    assert np.allclose(steady, steady[0], rtol=0.0, atol=0.0)
    assert np.all(z_base <= steady * (1.0 + 1.0e-12))
    assert np.all(z_fine <= steady * (1.0 + 1.0e-12))


def test_m43_result_has_no_prohibited_scientific_runs() -> None:
    summary = _summary()
    accounting = summary["prohibited_run_accounting"]
    assert accounting["sealed_13V_accessed"] is False
    assert all(value == 0 for key, value in accounting.items() if key != "sealed_13V_accessed")
    assert summary["evidence_type"] == "solver_generated_manufactured_component_closure"
    assert summary["protected_evidence_unchanged"] is True
    assert summary["protected_evidence_mtime_unchanged"] is True
    assert summary["upstream_blockers"]["resolved_by_m43"] is False
    assert summary["upstream_blockers"]["m42_source_local_resistance_error"] == pytest.approx(
        1.330233207545514
    )
    assert summary["upstream_blockers"]["latent_heat"] == "unresolved_and_unassessed"

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.sparse.linalg import ArpackNoConvergence

import pinnpcm.current_clamp.cc_b_stability as stability_module
from pinnpcm.current_clamp.artifacts import file_sha256
from pinnpcm.current_clamp.cc_b_model import build_cc_b_model
from pinnpcm.current_clamp.cc_b_stability import (
    CCBStabilityTelemetry,
    _apply_operator,
    certify_current_clamp_stability,
)
from pinnpcm.current_clamp.cc_b_stability_telemetry import (
    GATE_METADATA,
    TERMINAL_DISPOSITIONS,
    GateBook,
    StabilityTelemetryRecorder,
    _exclusive_directory,
    _write_terminal,
    classify_spectrum,
    deterministic_jv_probes,
    increment_campaign_counter,
    load_telemetry_contract,
    run_operator_prechecks,
)
from pinnpcm.current_clamp.source_oracle import discover_roots
from pinnpcm.evaluation.q2_qiu_source_oracle import OracleParameters


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_cc_b_stability_telemetry_closure_v1.yaml"


@pytest.fixture(scope="module")
def contract():
    return load_telemetry_contract(CONFIG, repository_root=ROOT)


def _equilibrium_temperature(contract, current_A: float = 4.0e-4) -> float:
    params = OracleParameters.from_config(contract.parent.cc_a_config)
    roots = discover_roots(
        branch="heating",
        current_A=current_A,
        params=params,
        config=contract.parent.cc_a_config,
    ).roots
    certified = [root for root in roots if root.certified]
    assert len(certified) == 1
    return float(certified[0].temperature_K)


def test_contract_authenticates_parent_and_only_l1_k6_target(contract) -> None:
    assert contract.target == {
        "defect": "NOM",
        "branch": "heating",
        "current_A": 4.0e-4,
        "grid": "L1",
        "spatial_level": 1,
        "eigenpairs": 6,
        "only_case": True,
    }
    forbidden = set(contract.raw["forbidden_execution"])
    assert {"L2_k6", "L2_k10", "36_case_matrix", "PINN"} <= forbidden
    authority = contract.raw["authority"]
    for key in ("parent_config", "parent_terminal", "parent_smoke_summary", "parent_l1_compact"):
        path = ROOT / authority[key]["path"]
        assert file_sha256(path) == authority[key]["sha256"]


def test_parent_artifacts_remain_immutable(contract) -> None:
    authority = contract.raw["authority"]
    assert file_sha256(ROOT / authority["parent_config"]["path"]) == (
        "56384a56893c1f9752e00e1dcece242a788805df2148b5022903adc6c314de8d"
    )
    assert file_sha256(ROOT / authority["parent_terminal"]["path"]) == (
        "4fd2e2c0ca090788e38b8e96b19a0543285149cfe899c3febd84fae57a95f6d3"
    )
    assert file_sha256(ROOT / authority["parent_smoke_summary"]["path"]) == (
        "817f301f3f03ea03e7ef57b095c89ce12829b90d531aae3b55c5da54a0d3c183"
    )


def test_recorder_enabled_and_disabled_operator_are_numerically_identical(
    contract, tmp_path: Path
) -> None:
    model = build_cc_b_model(
        contract.parent,
        spatial_level=1,
        current_set_A=4.0e-4,
        branch="heating",
        defect="NOM",
    )
    temperature = np.full(model.grid.shape, _equilibrium_temperature(contract))
    probe, _ = deterministic_jv_probes(model)
    without = _apply_operator(
        model, temperature, probe, CCBStabilityTelemetry()
    )
    recorder = StabilityTelemetryRecorder(tmp_path, model=model, checkpoint_interval=64)
    with_recorder = _apply_operator(
        model,
        temperature,
        probe,
        CCBStabilityTelemetry(),
        recorder=recorder,
        call_role="fixed_probe_parity",
    )
    recorder.checkpoint()
    assert np.array_equal(without, with_recorder)
    assert recorder.jv_rows[0]["electrical_iterations"] == "not_applicable"
    assert (tmp_path / "jv_calls.csv").is_file()
    assert (tmp_path / "jv_calls.npz").is_file()


def test_mass_fixed_current_and_deterministic_jv_prechecks(contract, tmp_path: Path) -> None:
    model = build_cc_b_model(
        contract.parent,
        spatial_level=1,
        current_set_A=4.0e-4,
        branch="heating",
        defect="NOM",
    )
    temperature = np.full(model.grid.shape, _equilibrium_temperature(contract))
    recorder = StabilityTelemetryRecorder(tmp_path, model=model, checkpoint_interval=64)
    gates = GateBook()
    assert run_operator_prechecks(contract, model, temperature, recorder, gates)
    for name in (
        "MASS_MATRIX_VALIDITY",
        "ELECTRICAL_SUBSOLVE",
        "FIXED_CURRENT_CONSTRAINT",
        "JV_FINITE",
        "JV_REPEATABILITY",
        "JV_STEP_SIZE_CONSISTENCY",
        "OPERATOR_UNIT_AND_SIGN",
    ):
        assert gates.get(name)["status"] == "PASS"
    first = deterministic_jv_probes(model)
    second = deterministic_jv_probes(model)
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])


@pytest.mark.parametrize(
    ("alpha", "rho", "stable", "expected"),
    [
        (-2.0, 1.0e-4, True, "STABLE_MARGIN_PASS"),
        (-2.0, 0.25, False, "SIGN_INDETERMINATE_WITHIN_RITZ_UNCERTAINTY"),
        (2.0, 1.0e-4, False, "POSITIVE_UNSTABLE"),
        (-2.0, 1.0e-4, False, "NEGATIVE_MARGIN_INSUFFICIENT"),
    ],
)
def test_spectrum_classification(alpha: float, rho: float, stable: bool, expected: str) -> None:
    assert classify_spectrum(
        alpha_per_s=alpha,
        maximum_ritz_residual_rate_per_s=rho,
        tau0_s=1.0,
        stable=stable,
    ) == expected


class _FakeGrid:
    shape = (4, 4)
    x_centers_m = np.linspace(0.0, 1.0, 4)
    y_centers_m = np.linspace(0.0, 1.0, 4)


class _FakeModel:
    def __init__(self) -> None:
        self.grid = _FakeGrid()
        self.current_set_A = 4.0e-4
        self.tau0_s = 1.0
        self.cell_capacity_J_K = np.ones(16)
        self.contract = SimpleNamespace(
            stability={
                "eigenpairs": 6,
                "which": "LR",
                "tolerance": 1.0e-8,
                "maxiter": 2000,
                "ncv": 14,
                "h_half_operator_relative_difference_max": 1.0e-4,
                "relative_ritz_residual_max": 1.0e-6,
                "stable_alpha_tau_max": -1.0e-3,
                "backward_error_multiplier": 10.0,
            },
            scales=SimpleNamespace(current_A=7.0e-4),
        )

    def validate_temperature(self, temperature_K: np.ndarray) -> None:
        assert np.asarray(temperature_K).shape == self.grid.shape

    def dynamic_rhs(self, temperature_K: np.ndarray, *, telemetry_callback=None) -> np.ndarray:
        temperature = np.asarray(temperature_K, dtype=float)
        if telemetry_callback is not None:
            telemetry_callback(
                {
                    "success": True,
                    "solver_type": "sparse_direct",
                    "iterations": "not_applicable",
                    "wall_time_s": 0.0,
                    "cpu_time_s": 0.0,
                    "unit_conductance_S": 1.0,
                    "device_voltage_V": 4.0e-4,
                    "source_current_A": 4.0e-4,
                    "ground_current_A": -4.0e-4,
                    "normalized_current_error": 0.0,
                    "scaled_electrical_residual_inf": 0.0,
                    "temperature_min_K": float(np.min(temperature)),
                    "temperature_max_K": float(np.max(temperature)),
                }
            )
        return -temperature.reshape(-1)


def test_arpack_no_convergence_persists_partial_pairs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = _FakeModel()
    partial_values = np.asarray([-1.0 + 2.0j, -1.0 - 2.0j])
    partial_vectors = np.ones((16, 2), dtype=complex)

    def fail_eigs(*args, **kwargs):
        raise ArpackNoConvergence("partial", partial_values, partial_vectors)

    monkeypatch.setattr(stability_module, "eigs", fail_eigs)
    recorder = StabilityTelemetryRecorder(tmp_path, model=model, checkpoint_interval=64)
    outcome = certify_current_clamp_stability(
        model,
        temperature_K=np.full(model.grid.shape, 330.0),
        recorder=recorder,
    )
    assert not outcome.success
    assert recorder.requested_pair_count == 6
    assert recorder.returned_pair_count == 2
    assert recorder.finite_pair_count == 2
    assert recorder.certified_pair_count == 0
    assert not recorder.partial_pairs_eligible_for_certification
    with np.load(tmp_path / "eigensolver_pairs.npz", allow_pickle=False) as payload:
        assert np.array_equal(payload["eigenvalues_real_per_s"], partial_values.real)
        assert not bool(payload["eligible_for_certification"][0])


def test_complex_numpy_canonicalization_and_pair_counts(tmp_path: Path) -> None:
    model = _FakeModel()
    recorder = StabilityTelemetryRecorder(tmp_path, model=model, checkpoint_interval=64)
    values = np.asarray([-1.0 + 3.0j, -1.0 - 3.0j])
    vectors = np.ones((16, 2), dtype=complex)
    recorder.start_stability(
        requested_pair_count=6,
        state_dimension=16,
        temperature_K=np.full((4, 4), 330.0),
    )
    recorder.record_eigensolver_return(
        eigenvalues=values,
        eigenvectors=vectors,
        converged=False,
        exception=RuntimeError("partial"),
        eligible_for_certification=False,
    )
    recorder.checkpoint()
    summary = json.loads((tmp_path / "telemetry_summary.json").read_text(encoding="utf-8"))
    assert summary["requested_pair_count"] == 6
    assert summary["returned_pair_count"] == 2


def test_attempt_directories_and_counters_are_exclusive_and_monotone(tmp_path: Path) -> None:
    t1 = tmp_path / "attempts" / "T1"
    _exclusive_directory(t1)
    with pytest.raises(FileExistsError):
        _exclusive_directory(t1)
    counter = tmp_path / "counters.json"
    first = increment_campaign_counter(counter, attempt="T1", repair_count=0)
    assert first["campaign_attempt_count"] == 1
    # A crash cannot roll this back; the next atomic update starts from one.
    second = increment_campaign_counter(counter, attempt="T2", repair_count=1)
    assert second["campaign_attempt_count"] == 2
    assert second["implementation_repair_count"] == 1
    assert second["formal_execution_count"] == 0
    assert second["cc_b_matrix_launch_count"] == 0


@pytest.mark.parametrize("disposition", sorted(TERMINAL_DISPOSITIONS))
def test_terminal_states_are_mutually_registered_and_keep_legacy_counters_zero(
    contract, tmp_path: Path, disposition: str
) -> None:
    root = tmp_path / disposition
    root.mkdir()
    gates = GateBook()
    terminal = _write_terminal(
        root,
        contract=contract,
        disposition=disposition,
        validity="invalid" if disposition.startswith("INVALID") else "valid",
        telemetry_closure_status="INVALID" if disposition.startswith("INVALID") else "PASS",
        closure_class="unit_test",
        stability_certification_status="INVALID",
        physical_spectrum_classification="NOT_APPLICABLE",
        stable=None,
        attempt="T1",
        counters={
            "campaign_attempt_count": 1,
            "implementation_repair_count": 0,
            "formal_execution_count": 0,
            "cc_b_matrix_launch_count": 0,
        },
        gates=gates,
        budget={"aggregate_cpu_s": 0.0, "calendar_wall_s": 0.0},
        detail="unit test",
    )
    assert terminal["disposition"] == disposition
    assert terminal["formal_execution_count"] == 0
    assert terminal["cc_b_matrix_launch_count"] == 0
    assert terminal["scientific_vote"] is False
    assert terminal["stable"] is None
    gate_names = {row["name"] for row in terminal["gates"]}
    assert gate_names == set(GATE_METADATA)


def test_telemetry_module_does_not_import_retired_or_downstream_paths() -> None:
    import pinnpcm.current_clamp.cc_b_stability_telemetry as module

    syntax = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = ("controller", "geophase_nls", "pinnpcm.pinn", "inverse")
    assert not any(any(token in name for token in forbidden) for name in imports)

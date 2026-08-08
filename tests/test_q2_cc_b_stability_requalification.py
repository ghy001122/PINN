from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pinnpcm.current_clamp.cc_b_model import build_cc_b_model
from pinnpcm.current_clamp.cc_b_stability import (
    CCBStabilityTelemetry,
    _failure,
    centered_jv_step_size_K,
    temperature_componentwise_inf_norm,
)
from pinnpcm.current_clamp.cc_b_stability_requalification import (
    analyze_dense_operator,
    load_requalification_contract,
)
from pinnpcm.current_clamp.cc_b_stability_telemetry import (
    GateBook,
    StabilityTelemetryRecorder,
    _apply_stability_gates,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q2_cc_b_stability_requalification_v1.yaml"


@pytest.fixture(scope="module")
def contract():
    return load_requalification_contract(CONFIG, repository_root=ROOT)


def test_contract_authenticates_pr33_and_freezes_scope(contract) -> None:
    assert contract.run_id == "Q2-CC-B-STABILITY-REQUALIFICATION-20260808-V1"
    assert contract.raw["target"] == {
        "defect": "NOM",
        "branch": "heating",
        "current_A": 4.0e-4,
        "l1_spatial_level": 1,
        "l2_spatial_level": 2,
        "r1_eigenpairs": 6,
        "r2_eigenpairs": [10, 6, 10],
    }
    assert {"36_case_matrix", "PINN", "inverse"} <= set(
        contract.raw["forbidden_execution"]
    )
    assert contract.raw["scientific_vote"] is False
    assert contract.raw["formal_execution_count"] == 0
    assert contract.raw["cc_b_matrix_launch_count"] == 0


def test_temperature_componentwise_norm_is_layout_invariant() -> None:
    values = np.asarray([300.0, -331.25, 320.0, 315.0, 305.0, 310.0])
    matrix = values.reshape(2, 3)
    assert temperature_componentwise_inf_norm(values) == 331.25
    assert temperature_componentwise_inf_norm(matrix) == 331.25
    assert temperature_componentwise_inf_norm(matrix.T) == 331.25
    with pytest.raises(ValueError):
        temperature_componentwise_inf_norm(np.asarray([]))


def test_uniform_l1_l2_step_is_grid_independent(contract) -> None:
    l1 = build_cc_b_model(
        contract.parent,
        spatial_level=1,
        current_set_A=4.0e-4,
        branch="heating",
        defect="NOM",
    )
    l2 = build_cc_b_model(
        contract.parent,
        spatial_level=2,
        current_set_A=4.0e-4,
        branch="heating",
        defect="NOM",
    )
    temperature_l1 = np.full(l1.grid.shape, 336.4)
    temperature_l2 = np.full(l2.grid.shape, 336.4)
    assert centered_jv_step_size_K(
        temperature_l1, np.ones(temperature_l1.size)
    ) == centered_jv_step_size_K(temperature_l2, np.ones(temperature_l2.size))


def test_pr33_l1_input_uses_corrected_step(contract) -> None:
    spec = contract.raw["authority"]["parent_l1_input_npz"]
    with np.load(ROOT / spec["path"], allow_pickle=False) as payload:
        temperature = np.asarray(payload["temperature_K"], dtype=float)
    step = centered_jv_step_size_K(temperature, np.ones(temperature.size))
    assert step == pytest.approx(2.0373e-3, rel=5.0e-4)
    assert step < 3.0e-3


class _RecorderModel:
    def __init__(self) -> None:
        self.contract = SimpleNamespace(
            stability={"relative_ritz_residual_max": 1.0e-6},
            scales=SimpleNamespace(current_A=7.0e-4),
        )


def test_failed_ritz_outcome_keeps_recorder_maxima(contract, tmp_path: Path) -> None:
    recorder = StabilityTelemetryRecorder(
        tmp_path, model=_RecorderModel(), checkpoint_interval=64
    )
    values = np.asarray([1.0, 0.5, -1.0, -2.0, -3.0, -4.0], dtype=complex)
    vectors = np.eye(6, dtype=complex)
    relative = np.linspace(1.0e-5, 3.0e-5, 6)
    absolute = np.linspace(0.1, 0.6, 6)
    recorder.start_stability(
        requested_pair_count=6,
        state_dimension=6,
        temperature_K=np.full(6, 330.0),
    )
    recorder.record_eigensolver_return(
        eigenvalues=values,
        eigenvectors=vectors,
        converged=True,
        exception=None,
        eligible_for_certification=True,
    )
    recorder.record_ritz_certification(
        eigenvalues=values,
        eigenvectors=vectors,
        absolute_residual_rates_per_s=absolute,
        relative_residuals=relative,
    )
    outcome = _failure(
        CCBStabilityTelemetry(),
        "INVALID_STABILITY",
        "Ritz residual certification failed",
        6,
    )
    gates = GateBook()
    _apply_stability_gates(contract.telemetry_contract, recorder, outcome, gates)
    metrics = gates.get("RITZ_RELATIVE_RESIDUAL")["metrics"]
    assert metrics["maximum_relative_ritz_residual"] == pytest.approx(3.0e-5)
    assert metrics["maximum_absolute_ritz_residual_rate_per_s"] == pytest.approx(0.6)
    assert metrics["returned_pair_count"] == 6
    assert metrics["finite_pair_count"] == 6
    assert metrics["certified_pair_count"] == 0
    recorder.checkpoint()
    summary = __import__("json").loads(
        (tmp_path / "telemetry_summary.json").read_text(encoding="utf-8")
    )
    assert summary["maximum_relative_ritz_residual"] == pytest.approx(3.0e-5)


@pytest.mark.parametrize(
    ("matrix", "expected"),
    [
        (np.diag([-1.0, -2.0, -3.0, -4.0]), "STABLE_MARGIN_PASS"),
        (np.diag([1.0, -2.0, -3.0, -4.0]), "POSITIVE_UNSTABLE"),
        (np.diag([-1.0e-5, -2.0, -3.0, -4.0]), "NEGATIVE_MARGIN_INSUFFICIENT"),
        (
            np.asarray(
                [[-1.0, -5.0, 0.0, 0.0], [5.0, -1.0, 0.0, 0.0], [0.0, 0.0, -2.0, 20.0], [0.0, 0.0, 0.0, -3.0]]
            ),
            "STABLE_MARGIN_PASS",
        ),
    ],
)
def test_dense_spectrum_classification(matrix: np.ndarray, expected: str) -> None:
    result = analyze_dense_operator(
        matrix,
        np.ones(matrix.shape[0]),
        tau0_s=1.0,
        stable_alpha_tau_max=-1.0e-3,
        backward_error_multiplier=10.0,
    )
    assert result.classification == expected
    assert float(np.max(result.relative_residuals)) <= 1.0e-10
    assert np.array_equal(
        result.rightmost_order, np.argsort(result.eigenvalues_per_s.real)[::-1]
    )


def test_requalification_module_does_not_import_retired_or_downstream_paths() -> None:
    import pinnpcm.current_clamp.cc_b_stability_requalification as module

    syntax = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(syntax):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    forbidden = ("controller", "geophase_nls", "pinnpcm.pinn", "inverse")
    assert not any(any(token in name for token in forbidden) for name in imports)

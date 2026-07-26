from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.evaluation.geophase_phase1_gates import (
    held_out_vertical_response_grid,
    vertical_passivity_and_identity_metrics,
    vertical_passivity_and_identity_metrics_on_grid,
    vertical_response_comparison,
    vertical_response_comparison_on_grid,
)
from pinnpcm.solvers.vertical_multilayer_reference import (
    build_normalized_vertical_references,
    build_repair_overlay_branch,
    build_repair_raw_components,
)


ROOT = Path(__file__).resolve().parents[1]


def _yaml(relative_path: str) -> dict:
    return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))


class _FrequencyTiltModel:
    """Small analytic response used to expose grid-specific aggregation."""

    def __init__(self, frequency_log_slope: float) -> None:
        self.frequency_log_slope = float(frequency_log_slope)

    def step_heat_flux_W_m2(self, times_s: np.ndarray) -> np.ndarray:
        times = np.asarray(times_s, dtype=float)
        return 1.0 + np.exp(-times / 1.0e-6)

    def impulse_tail_W_m2K_s(self, times_s: np.ndarray) -> np.ndarray:
        times = np.asarray(times_s, dtype=float)
        return -np.exp(-times / 1.0e-6)

    def driving_admittance_W_m2K(
        self, angular_frequency_rad_s: np.ndarray
    ) -> np.ndarray:
        omega = np.asarray(angular_frequency_rad_s, dtype=float)
        return np.exp(self.frequency_log_slope * np.log1p(omega)).astype(complex)


def test_inherited_and_pullback_grid_families_are_evaluated_separately() -> None:
    effective_times = np.asarray([1.0e-10, 1.0e-8, 1.0e-6])
    effective_frequencies = np.asarray([1.0e3, 1.0e5, 1.0e7])
    ratio = 2.5e-3
    pullback_times = effective_times / ratio
    pullback_frequencies = ratio * effective_frequencies
    candidate = _FrequencyTiltModel(0.02)
    reference = _FrequencyTiltModel(0.0)

    inherited = vertical_response_comparison_on_grid(
        candidate,
        reference,
        times_s=effective_times,
        frequencies_Hz=effective_frequencies,
    )
    pullback = vertical_response_comparison_on_grid(
        candidate,
        reference,
        times_s=pullback_times,
        frequencies_Hz=pullback_frequencies,
    )

    assert np.array_equal(inherited["time_s"], effective_times)
    assert np.array_equal(inherited["frequency_Hz"], effective_frequencies)
    assert np.array_equal(pullback["time_s"], effective_times / ratio)
    assert np.array_equal(
        pullback["frequency_Hz"], ratio * effective_frequencies
    )
    inherited_error = np.asarray(
        inherited["frequency_log_magnitude_error"], dtype=float
    )
    pullback_error = np.asarray(
        pullback["frequency_log_magnitude_error"], dtype=float
    )
    assert inherited["metrics"]["frequency_log_magnitude_rmse"] == pytest.approx(
        np.sqrt(np.mean(inherited_error**2))
    )
    assert pullback["metrics"]["frequency_log_magnitude_rmse"] == pytest.approx(
        np.sqrt(np.mean(pullback_error**2))
    )
    concatenated_rmse = float(
        np.sqrt(np.mean(np.concatenate([inherited_error, pullback_error]) ** 2))
    )
    assert concatenated_rmse != pytest.approx(
        inherited["metrics"]["frequency_log_magnitude_rmse"]
    )
    assert concatenated_rmse != pytest.approx(
        pullback["metrics"]["frequency_log_magnitude_rmse"]
    )


def test_explicit_grid_helpers_are_backward_compatible_with_locked_grid() -> None:
    formal = _yaml("configs/geophase_phase1_2p5d_reference.yaml")
    fit_contract = formal["vertical_reference"]["reduction_fit_contract"]
    times, frequencies = held_out_vertical_response_grid(fit_contract)
    reference = build_normalized_vertical_references(
        formal, substrate_depth_m=4.0e-7, cells_per_layer=3
    ).references["bare_vo2"]

    legacy_comparison = vertical_response_comparison(
        reference, reference, fit_contract
    )
    explicit_comparison = vertical_response_comparison_on_grid(
        reference,
        reference,
        times_s=times,
        frequencies_Hz=frequencies,
    )
    assert explicit_comparison["metrics"] == legacy_comparison["metrics"]
    assert np.array_equal(explicit_comparison["time_s"], times)
    assert np.array_equal(explicit_comparison["frequency_Hz"], frequencies)

    legacy_identity = vertical_passivity_and_identity_metrics(
        reference, fit_contract
    )
    explicit_identity = vertical_passivity_and_identity_metrics_on_grid(
        reference,
        times_s=times,
        frequencies_Hz=frequencies,
    )
    assert explicit_identity == legacy_identity


def test_raw_region_topology_is_substrate_plus_parallel_no_flux_overlay() -> None:
    formal = _yaml("configs/geophase_phase1_2p5d_reference.yaml")
    repair = _yaml("configs/geophase_phase1_vertical_repair_v7.yaml")
    overlay, overlay_widths = build_repair_overlay_branch(
        formal, repair, grid_level="coarse"
    )
    raw = build_repair_raw_components(
        formal,
        repair,
        substrate_depth_m=4.0e-7,
        grid_level="coarse",
        overlay_branch=overlay,
        overlay_cell_widths_m=overlay_widths,
    )
    regions = raw.raw_region_references()
    bare = regions["bare_vo2"]
    contact = regions["electrode_covered_vo2"]

    assert bare.order == raw.substrate.order
    assert contact.order == raw.substrate.order + raw.overlay.order
    assert bare.total_capacity_J_m2K == pytest.approx(
        raw.substrate.total_capacity_J_m2K
    )
    assert contact.total_capacity_J_m2K == pytest.approx(
        raw.substrate.total_capacity_J_m2K + raw.overlay.total_capacity_J_m2K
    )
    assert contact.dc_conductance_W_m2K == pytest.approx(
        raw.substrate.dc_conductance_W_m2K
        + raw.overlay.dc_conductance_W_m2K
    )
    substrate_order = raw.substrate.order
    assert np.count_nonzero(
        contact.conductance_matrix_W_m2K[:substrate_order, substrate_order:]
    ) == 0
    assert np.count_nonzero(
        contact.conductance_matrix_W_m2K[substrate_order:, :substrate_order]
    ) == 0


@pytest.mark.parametrize(
    ("times_s", "frequencies_Hz", "message"),
    [
        (np.asarray([]), np.asarray([1.0]), "nonempty"),
        (np.asarray([[1.0e-9]]), np.asarray([1.0]), "one-dimensional"),
        (np.asarray([np.nan]), np.asarray([1.0]), "finite"),
        (np.asarray([-1.0e-9]), np.asarray([1.0]), "nonnegative"),
        (np.asarray([1.0e-9]), np.asarray([]), "nonempty"),
        (np.asarray([1.0e-9]), np.asarray([[1.0]]), "one-dimensional"),
        (np.asarray([1.0e-9]), np.asarray([np.inf]), "finite"),
        (np.asarray([1.0e-9]), np.asarray([-1.0]), "nonnegative"),
    ],
)
def test_explicit_comparison_grid_rejects_invalid_coordinates(
    times_s: np.ndarray,
    frequencies_Hz: np.ndarray,
    message: str,
) -> None:
    model = _FrequencyTiltModel(0.0)
    with pytest.raises(ValueError, match=message):
        vertical_response_comparison_on_grid(
            model,
            model,
            times_s=times_s,
            frequencies_Hz=frequencies_Hz,
        )


def test_explicit_identity_grid_rejects_nonfinite_coordinates() -> None:
    formal = _yaml("configs/geophase_phase1_2p5d_reference.yaml")
    reference = build_normalized_vertical_references(
        formal, substrate_depth_m=4.0e-7, cells_per_layer=2
    ).references["bare_vo2"]
    with pytest.raises(ValueError, match="finite"):
        vertical_passivity_and_identity_metrics_on_grid(
            reference,
            times_s=np.asarray([1.0e-9]),
            frequencies_Hz=np.asarray([np.nan]),
        )

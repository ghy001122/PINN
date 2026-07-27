from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

import pinnpcm.physics.geophase_s1_diffusive as s1
from pinnpcm.physics.geophase_s1_diffusive import (
    DiffusiveThermalImpedance,
    FosterThermalImpedance,
    candidate_eligible,
    fit_grids,
    foster_to_cauer_ii,
    pulse_event_times,
    select_training_candidate,
    validation_grids,
)
from pinnpcm.physics.geophase_s2_thermal import derive_nominal_s2_source_scale


ROOT = Path(__file__).resolve().parents[1]
V1_CONFIG = ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve.yaml"
V2_CONFIG = ROOT / "configs" / "geophase_phase1_s1_diffusive_sensitivity_mve_v2.yaml"
S2_CONFIG = ROOT / "configs" / "geophase_phase1_v2_s2_reference.yaml"
PREREGISTRATION = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "s1_diffusive_mve_v2_preregistration.json"
)
SUMMARY = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "s1_diffusive_mve_v2_summary.json"
)
INTERRUPTION_DISPOSITION = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2"
    / "s1_diffusive_mve_v2_interruption_disposition.json"
)
INTERRUPTION_REPORT = (
    ROOT
    / "docs"
    / "codex_reports"
    / "geophase_phase1_v2_s1_diffusive_mve_v2_interruption.md"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _eligible_metadata(start_id: str, objective: float) -> dict[str, object]:
    return {
        "start_id": start_id,
        "fit_objective": objective,
        "optimizer_success": True,
        "finite_objective": True,
        "finite_parameters": True,
        "equality_constraints_feasible": True,
        "no_optimizer_exception": True,
        "no_parameter_bound_hit": True,
        "positive_foster_elements": True,
    }


def _legacy_chunked_step(
    kernel: DiffusiveThermalImpedance, time: np.ndarray
) -> np.ndarray:
    weights, times = kernel._modal_weights_and_times()
    response = np.zeros(time.size, dtype=float)
    for start in range(0, weights.size, kernel.modal_chunk_terms):
        stop = min(start + kernel.modal_chunk_terms, weights.size)
        exponent = -time[:, None] / times[None, start:stop]
        response += np.sum(
            weights[None, start:stop] * (-np.expm1(exponent)), axis=1
        )
    return kernel.resistance_m2K_W * response


def _legacy_chunked_pulse(
    kernel: DiffusiveThermalImpedance,
    time: np.ndarray,
    *,
    pulse_width_s: float,
    pulse_amplitude_W_m2: float,
) -> np.ndarray:
    weights, times = kernel._modal_weights_and_times()
    response = np.zeros(time.size, dtype=float)
    before = time <= pulse_width_s
    after = ~before
    for start in range(0, weights.size, kernel.modal_chunk_terms):
        stop = min(start + kernel.modal_chunk_terms, weights.size)
        local_times = times[start:stop]
        local_weights = weights[start:stop]
        if np.any(before):
            response[before] += np.sum(
                local_weights[None, :]
                * (-np.expm1(-time[before, None] / local_times[None, :])),
                axis=1,
            )
        if np.any(after):
            charged = -np.expm1(-pulse_width_s / local_times)
            response[after] += np.sum(
                local_weights[None, :]
                * charged[None, :]
                * np.exp(
                    -(time[after, None] - pulse_width_s)
                    / local_times[None, :]
                ),
                axis=1,
            )
    return pulse_amplitude_W_m2 * kernel.resistance_m2K_W * response


@pytest.mark.phase1
def test_v2_preregistration_hashes_and_nonformal_boundary_are_locked() -> None:
    amendment = _yaml(V2_CONFIG)
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert _sha256(V2_CONFIG) == preregistration["amendment_config_sha256"]
    assert _sha256(S2_CONFIG) == preregistration["s2_config_sha256"]
    assert preregistration["formal_execution_count"] == 0
    assert preregistration["production_selection_authorized"] is False
    assert amendment["runner_contract"]["formal_ID_prefix"] == "forbidden"
    assert amendment["runner_contract"]["result_may_change_nominal_S2"] is False


@pytest.mark.phase1
def test_diffusive_kernel_matches_locked_low_frequency_moments() -> None:
    kernel = DiffusiveThermalImpedance(
        4.0, 2.0, modal_terms=1024, modal_chunk_terms=1024
    )
    assert kernel.tau_s == pytest.approx(1.5)
    assert kernel.impedance(np.asarray([0.0j]))[0].real == pytest.approx(0.25)
    small_s = 1.0e-7 / kernel.tau_s
    admittance_slope = (
        kernel.admittance(np.asarray([small_s]))[0].real - kernel.gtheta_A_W_m2K
    ) / small_s
    assert admittance_slope == pytest.approx(kernel.cm_A_J_m2K, rel=1.0e-6)
    weights, times = kernel._modal_weights_and_times()
    assert np.sum(weights) == pytest.approx(1.0, rel=0.0, abs=2.0e-4)
    assert np.dot(weights, times) == pytest.approx(
        kernel.mean_time_s, rel=2.0e-4
    )


@pytest.mark.phase1
def test_source_scale_is_derived_once_from_s2_and_mirror_matches() -> None:
    v1 = _yaml(V1_CONFIG)
    s2_config = _yaml(S2_CONFIG)
    scale = derive_nominal_s2_source_scale(s2_config)
    mirrored = v1["shared_source_moments"]
    assert scale["nominal_memory_coefficient_J_K"] > 0.0
    assert scale["target_uniform_conductance_W_K"] == float(
        mirrored["Gtheta_W_K"]
    )
    assert scale["target_uniform_capacity_J_K"] == float(
        mirrored["Ctheta_low_frequency_coefficient_J_K"]
    )


@pytest.mark.phase1
def test_candidate_eligibility_cannot_be_bypassed() -> None:
    metadata = _eligible_metadata("S0", 1.0)
    assert candidate_eligible(metadata)
    for key in (
        "optimizer_success",
        "finite_objective",
        "finite_parameters",
        "equality_constraints_feasible",
        "no_optimizer_exception",
        "no_parameter_bound_hit",
        "positive_foster_elements",
    ):
        failed = dict(metadata)
        failed[key] = False
        assert not candidate_eligible(failed), key


@pytest.mark.phase1
def test_training_selection_has_no_validation_reselection_surface() -> None:
    first = FosterThermalImpedance(np.asarray([0.8, 0.2]), np.asarray([0.25, 4.0]))
    second = FosterThermalImpedance(np.asarray([0.5, 0.5]), np.asarray([0.5, 1.5]))
    selected = select_training_candidate(
        [
            (first, _eligible_metadata("S0", 0.2)),
            (second, _eligible_metadata("S1", 0.1)),
        ]
    )
    assert selected is not None
    assert selected[1]["start_id"] == "S1"
    failed = _eligible_metadata("S2", 0.01)
    failed["optimizer_success"] = False
    selected = select_training_candidate([(first, failed)])
    assert selected is None


@pytest.mark.phase1
def test_optimizer_exception_is_isolated_and_ineligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        s1,
        "minimum_l2_start_weights",
        lambda multipliers, lower_bound: np.asarray([0.8, 0.2]),
    )

    def _raise(*args: object, **kwargs: object) -> object:
        raise FloatingPointError("synthetic optimizer failure")

    monkeypatch.setattr(s1, "minimize", _raise)
    model, metadata = s1.fit_foster_candidate(
        start_id="S0",
        multipliers=np.asarray([0.25, 4.0]),
        analytic=DiffusiveThermalImpedance(
            4.0, 2.0, modal_terms=1024, modal_chunk_terms=1024
        ),
        fit_frequency_Hz=np.asarray([1.0, 10.0]),
        fit_time_s=np.asarray([0.0, 0.1]),
        pulse_width_s=0.01,
        pulse_amplitude_W_m2=100.0,
        weights={
            "frequency_log_magnitude": 0.4,
            "unit_heat_flux_step_temperature": 0.3,
            "unit_area_pulse_temperature": 0.3,
        },
        maximum_iterations=2,
        ftol=1.0e-12,
        equality_tolerance=1.0e-12,
        log_weight_bounds=(-27.0, 0.0),
        log_multiplier_bounds=(-18.0, 18.0),
        finite_penalty=1.0e100,
        boundary_hit_tolerance=1.0e-7,
    )
    assert model is None
    assert metadata["no_optimizer_exception"] is False
    assert metadata["candidate_eligible"] is False


@pytest.mark.phase1
def test_foster_cauer_transfer_topology_and_independent_ledger() -> None:
    gtheta = 4.0
    cm = 2.0
    resistance_scale = 1.0 / gtheta
    time_scale = cm / gtheta
    foster = FosterThermalImpedance(
        resistance_scale * np.asarray([0.8, 0.2]),
        time_scale * np.asarray([0.25, 4.0]),
    )
    cauer = foster_to_cauer_ii(
        foster, gtheta_A_W_m2K=gtheta, cm_A_J_m2K=cm
    )
    assert cauer.order == 2
    assert cauer.independent_vertical_state_count == 1
    assert cauer.port_capacity_J_m2K > 0.0
    frequency = 1j * 2.0 * np.pi * np.geomspace(1.0e-3, 1.0e3, 31)
    np.testing.assert_allclose(
        cauer.impedance(frequency), foster.impedance(frequency), rtol=1.0e-11
    )
    np.testing.assert_allclose(
        cauer.state_space_impedance(frequency),
        cauer.impedance(frequency),
        rtol=1.0e-11,
    )
    assert cauer.dc_resistance_m2K_W == pytest.approx(
        foster.dc_resistance_m2K_W, rel=1.0e-12
    )
    assert cauer.first_impedance_moment_m2K_s_W == pytest.approx(
        foster.first_moment_m2K_s_W, rel=1.0e-12
    )

    ledger = cauer.backward_euler_ledger(
        time_step_s=1.0e-3, steps=8, port_heat_flux_W_m2=1.0
    )
    storage_tamper = cauer.backward_euler_ledger(
        time_step_s=1.0e-3,
        steps=8,
        port_heat_flux_W_m2=1.0,
        storage_tamper_W_m2=0.01,
    )
    sink_tamper = cauer.backward_euler_ledger(
        time_step_s=1.0e-3,
        steps=8,
        port_heat_flux_W_m2=1.0,
        sink_tamper_W_m2=0.01,
    )
    assert ledger["maximum_relative_residual"] <= 1.0e-12
    assert storage_tamper["maximum_relative_residual"] > 1.0e-4
    assert sink_tamper["maximum_relative_residual"] > 1.0e-4


@pytest.mark.phase1
def test_registered_pulse_event_points_include_the_input_corner() -> None:
    amendment = _yaml(V2_CONFIG)
    width = 1.0e-10
    times = pulse_event_times(
        width,
        amendment["analytic_reference_control"][
            "pulse_event_audit_times_relative_to_width"
        ],
    )
    np.testing.assert_allclose(times / width, [0.999, 1.0, 1.001])


@pytest.mark.phase1
def test_active_prefix_modal_evaluation_matches_original_finite_sum() -> None:
    base = _yaml(V1_CONFIG)
    response = base["response_contract"]
    _, fit_time = fit_grids(response)
    _, validation_time = validation_grids(response)
    width = float(response["regularized_impulse_response"]["pulse_width_s"])
    amplitude = float(
        response["regularized_impulse_response"]["pulse_amplitude_W_m2"]
    )
    event_time = pulse_event_times(width, [0.999, 1.0, 1.001])
    exact_registered_coordinates = np.unique(
        np.concatenate((fit_time, validation_time, event_time))
    )
    real_scale = derive_nominal_s2_source_scale(_yaml(S2_CONFIG))

    # Exercise every registered time coordinate with the original chunked
    # expression while keeping the unit test bounded.
    bounded = DiffusiveThermalImpedance(
        real_scale["vertical_conductance_W_m2K"],
        real_scale["memory_areal_coefficient_J_m2K"],
        modal_terms=1024,
        modal_chunk_terms=256,
    )
    np.testing.assert_allclose(
        bounded.step_temperature_K(exact_registered_coordinates),
        _legacy_chunked_step(bounded, exact_registered_coordinates),
        rtol=2.0e-15,
        atol=0.0,
    )
    np.testing.assert_allclose(
        bounded.rectangular_pulse_temperature_K(
            exact_registered_coordinates,
            pulse_width_s=width,
            pulse_amplitude_W_m2=amplitude,
        ),
        _legacy_chunked_pulse(
            bounded,
            exact_registered_coordinates,
            pulse_width_s=width,
            pulse_amplitude_W_m2=amplitude,
        ),
        rtol=2.0e-15,
        atol=0.0,
    )

    # Also exercise the locked 16k/32k truncations at the registered temporal
    # edges and pulse corner, where a tail/off-by-one error is most visible.
    edge_time = np.unique(
        np.concatenate(
            (
                [fit_time[0], fit_time[1], fit_time[-1]],
                [validation_time[0], validation_time[1], validation_time[-1]],
                event_time,
            )
        )
    )
    for terms in (16384, 32768):
        locked = DiffusiveThermalImpedance(
            real_scale["vertical_conductance_W_m2K"],
            real_scale["memory_areal_coefficient_J_m2K"],
            modal_terms=terms,
            modal_chunk_terms=2048,
        )
        np.testing.assert_allclose(
            locked.step_temperature_K(edge_time),
            _legacy_chunked_step(locked, edge_time),
            rtol=2.0e-15,
            atol=0.0,
        )
        np.testing.assert_allclose(
            locked.rectangular_pulse_temperature_K(
                edge_time,
                pulse_width_s=width,
                pulse_amplitude_W_m2=amplitude,
            ),
            _legacy_chunked_pulse(
                locked,
                edge_time,
                pulse_width_s=width,
                pulse_amplitude_W_m2=amplitude,
            ),
            rtol=2.0e-15,
            atol=0.0,
        )


@pytest.mark.phase1
def test_generated_mve_evidence_remains_nonformal_if_present() -> None:
    if not SUMMARY.exists():
        pytest.skip("nonformal S1 MVE has not executed yet")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["formal_execution_count"] == 0
    assert summary["formal_artifacts_created"] is False
    assert summary["production_selected"] is False
    assert summary["S2_remains_nominal"] is True
    assert summary["eligible_same_device_holdout_used"] is False
    assert summary["evidence_type"] == "nonformal_synthetic_model_form_sensitivity"


@pytest.mark.phase1
def test_interruption_disposition_is_nonvoting_and_does_not_fabricate_mve() -> None:
    payload = json.loads(INTERRUPTION_DISPOSITION.read_text(encoding="utf-8"))
    assert payload["disposition"] == (
        "STOP_S1_REFERENCE_EVALUATION_"
        "INFRASTRUCTURE_BLOCKED_BEFORE_ATOMIC_EVIDENCE"
    )
    assert payload["evidence_type"] == (
        "nonvoting_infrastructure_interruption_disposition"
    )
    assert payload["formal_execution_count"] == 0
    assert payload["formal_artifacts_created"] is False
    assert payload["production_selected"] is False
    assert payload["s2_remains_nominal"] is True
    assert payload["k_fit_started"] is False
    assert payload["eligible_same_device_holdout_used"] is False
    assert payload["configured_atomic_outputs_created"] is False
    assert payload["s1_mve_closed_without_further_numerical_work"] is True
    assert len(payload["infrastructure_interruptions"]) == 3
    assert sum(
        item["modal_reference_stdout"] == "S1-MVE: modal reference failed"
        for item in payload["infrastructure_interruptions"]
    ) == 2
    assert all(
        item["scientific_vote"] is False
        for item in payload["infrastructure_interruptions"]
    )
    assert INTERRUPTION_REPORT.exists()

    configured = payload["configured_outputs_intentionally_not_fabricated"]
    for relative in configured:
        assert not (ROOT / relative).exists(), relative


@pytest.mark.phase1
def test_interruption_artifact_has_an_exact_gitignore_exception() -> None:
    expected = (
        "!outputs/tables/geophase_phase1_v2/"
        "s1_diffusive_mve_v2_interruption_disposition.json"
    )
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines.count(expected) == 1

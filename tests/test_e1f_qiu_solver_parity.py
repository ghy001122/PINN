"""Independent-solver and event-ledger tests for the E1F compact model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from pinnpcm.physics.qiu_author_compact_model import load_parameters
from pinnpcm.solvers.qiu_author_ode import QiuAuthorSimulation, simulate


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "e1f_qiu_author_external_anchor.yaml"


def _config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _range_normalized_rmse(first: np.ndarray, second: np.ndarray) -> float:
    scale = max(
        float(np.percentile(second, 95.0) - np.percentile(second, 5.0)),
        float(np.max(np.abs(second))) * 1.0e-12,
        np.finfo(np.float64).tiny,
    )
    return float(np.sqrt(np.mean((first - second) ** 2)) / scale)


@pytest.fixture(scope="module")
def solver_pair() -> tuple[QiuAuthorSimulation, QiuAuthorSimulation]:
    config = _config()
    params = load_parameters(config)
    times = np.linspace(0.0, 6.0e-6, int(config["solvers"]["comparison_points"]))
    primary = simulate(params, 12.0, times, "DOP853", config)
    independent = simulate(params, 12.0, times, "Radau", config)
    return primary, independent


def test_dop853_and_radau_waveforms_and_event_topology_agree(
    solver_pair: tuple[QiuAuthorSimulation, QiuAuthorSimulation],
) -> None:
    primary, independent = solver_pair

    assert _range_normalized_rmse(primary.current_A, independent.current_A) <= 1.0e-3
    assert _range_normalized_rmse(primary.voltage_V, independent.voltage_V) <= 1.0e-3
    assert (
        _range_normalized_rmse(primary.temperature_K, independent.temperature_K)
        <= 1.0e-3
    )
    assert primary.metrics["activity_class"] == independent.metrics["activity_class"]
    assert primary.metrics["event_count"] == independent.metrics["event_count"]
    assert primary.metrics["event_count"] > 0
    assert np.isfinite(primary.current_A).all()
    assert np.isfinite(independent.current_A).all()


def test_event_records_are_localized_ordered_and_alternating(
    solver_pair: tuple[QiuAuthorSimulation, QiuAuthorSimulation],
) -> None:
    primary, _ = solver_pair
    records = primary.event_records

    assert records
    assert np.all(np.diff([record["time_s"] for record in records]) > 0.0)
    for index, record in enumerate(records):
        assert record["event_index"] == index
        assert record["delta_after"] == -record["delta_before"]
        assert record["delta_before"] == (1 if index % 2 == 0 else -1)
        assert np.isfinite(record["proximity_temperature_K"])
        assert 0.0 < record["reversal_fraction"] < 1.0


def test_simulation_exposes_charge_energy_and_json_ready_evidence(
    solver_pair: tuple[QiuAuthorSimulation, QiuAuthorSimulation],
) -> None:
    primary, _ = solver_pair
    metrics = primary.metrics
    payload = primary.to_dict()

    assert metrics["charge_C"] > 0.0
    assert metrics["joule_energy_J"] > 0.0
    assert metrics["minimum_joule_power_W"] >= 0.0
    assert metrics["peak_temperature_K"] > metrics["minimum_temperature_K"]
    assert metrics["energy_ledger_relative_imbalance"] < 2.0e-3
    assert isinstance(payload["time_s"], list)
    assert isinstance(payload["event_records"], list)
    assert payload["method"] == "DOP853"
    assert len(payload["time_s"]) == len(primary.time_s)


@pytest.mark.parametrize("variant", ["no_hysteresis", "fixed_heating"])
def test_preregistered_baseline_variants_do_not_mutate_an_event_ledger(
    variant: str,
) -> None:
    config = _config()
    params = load_parameters(config)
    times = np.linspace(0.0, 2.0e-7, 51)
    result = simulate(params, 12.0, times, "DOP853", config, variant=variant)

    assert result.event_records == ()
    assert result.solver_statistics["segments"] == 1
    assert np.unique(result.branch_delta).tolist() == [1]
    assert np.isfinite(result.resistance_ohm).all()

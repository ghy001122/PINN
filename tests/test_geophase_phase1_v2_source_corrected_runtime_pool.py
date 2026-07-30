from __future__ import annotations

import math

import pytest

from pinnpcm.solvers.geophase_phase1_v2_runtime import (
    C3_RAM_FRACTION,
    C3WorkerMemoryLimitError,
    select_c3_worker_count,
)


pytestmark = [pytest.mark.phase1, pytest.mark.current]


@pytest.mark.parametrize(
    ("physical", "available", "peak_rss", "samples", "expected"),
    [
        (4, 10_000, 100, 26, 4),
        (64, 1_000, 300, 26, 2),
        (64, 10_000, 100, 5, 5),
        (64, 1_000, 700, 26, 1),
        (64, 3_000, 700, 26, 3),
    ],
)
def test_select_c3_worker_count_uses_the_exact_locked_minimum(
    physical: int,
    available: int,
    peak_rss: int,
    samples: int,
    expected: int,
) -> None:
    assert (
        select_c3_worker_count(
            physical,
            available,
            peak_rss,
            independent_sample_count=samples,
        )
        == expected
    )


def test_zero_memory_worker_limit_is_a_classifiable_no_go_not_one_worker() -> None:
    with pytest.raises(C3WorkerMemoryLimitError) as captured:
        select_c3_worker_count(
            physical_core_count=64,
            launch_available_RAM_bytes=1_000,
            measured_peak_worker_RSS_bytes=701,
        )

    error = captured.value
    assert error.disposition == "NO_GO_RUNTIME"
    assert error.failure_class == "memory"
    assert error.memory_worker_limit == 0
    assert "zero C3 workers" in str(error)


def test_c3_RAM_fraction_is_fixed_and_not_an_API_override() -> None:
    import inspect

    assert C3_RAM_FRACTION == pytest.approx(0.70)
    assert "memory_fraction" not in inspect.signature(
        select_c3_worker_count
    ).parameters


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("physical_core_count", 0),
        ("physical_core_count", -1),
        ("physical_core_count", 1.5),
        ("physical_core_count", math.inf),
        ("physical_core_count", True),
        ("launch_available_RAM_bytes", 0),
        ("launch_available_RAM_bytes", -1),
        ("launch_available_RAM_bytes", math.nan),
        ("measured_peak_worker_RSS_bytes", 0),
        ("measured_peak_worker_RSS_bytes", -1),
        ("measured_peak_worker_RSS_bytes", math.inf),
        ("independent_sample_count", 0),
        ("independent_sample_count", -1),
        ("independent_sample_count", math.nan),
    ],
)
def test_select_c3_worker_count_rejects_nonpositive_nonfinite_or_noninteger_inputs(
    argument: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "physical_core_count": 8,
        "launch_available_RAM_bytes": 16_000,
        "measured_peak_worker_RSS_bytes": 1_000,
        "independent_sample_count": 26,
    }
    arguments[argument] = value
    with pytest.raises(ValueError):
        select_c3_worker_count(**arguments)  # type: ignore[arg-type]

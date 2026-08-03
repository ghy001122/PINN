"""Bind the sole safeguarded-AA root into the frozen exact controller flow.

The wrapper changes no controller source or state-machine logic.  It binds one
step solver for the duration of a serial call, verifies the historical binding
before entry, and restores it in ``finally``.  A process-wide lock prevents a
mixed solver identity.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from threading import RLock
from typing import Any, Iterator

from pinnpcm.solvers import geophase_exact_condensed as exact_v1
from pinnpcm.solvers import geophase_exact_condensed_controller_v2 as controller
from pinnpcm.solvers.geophase_exact_condensed_anderson import (
    DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS,
    SafeguardedAndersonSettings,
    solve_exact_condensed_safeguarded_anderson_step,
)


_BIND_LOCK = RLock()


def _bound_step(
    *args: Any,
    anderson_settings: SafeguardedAndersonSettings,
    settings: exact_v1.ExactCondensedSettings = (
        exact_v1.DEFAULT_EXACT_CONDENSED_SETTINGS
    ),
    **kwargs: Any,
) -> exact_v1.ExactCondensedStepOutcome:
    if settings != exact_v1.DEFAULT_EXACT_CONDENSED_SETTINGS:
        raise ValueError(
            "the Anderson controller binding rejects v1 setting overrides"
        )
    return solve_exact_condensed_safeguarded_anderson_step(
        *args,
        anderson_settings=anderson_settings,
        **kwargs,
    )


@contextmanager
def _bind_solver(
    settings: SafeguardedAndersonSettings,
) -> Iterator[None]:
    settings.validate()
    with _BIND_LOCK:
        original = controller.solve_exact_condensed_step
        if original is not exact_v1.solve_exact_condensed_step:
            raise RuntimeError(
                "exact controller already has a nonhistorical solver binding"
            )
        bound = partial(_bound_step, anderson_settings=settings)
        controller.solve_exact_condensed_step = bound  # type: ignore[assignment]
        try:
            yield
        finally:
            if controller.solve_exact_condensed_step is not bound:
                controller.solve_exact_condensed_step = original
                raise RuntimeError(
                    "exact controller solver binding changed during execution"
                )
            controller.solve_exact_condensed_step = original


def attempt_exact_condensed_anderson_embedded_interval(
    *args: Any,
    anderson_settings: SafeguardedAndersonSettings = (
        DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    ),
    **kwargs: Any,
) -> controller.ExactCondensedEmbeddedAttemptObservation:
    with _bind_solver(anderson_settings):
        return controller.attempt_exact_condensed_embedded_interval(*args, **kwargs)


def simulate_exact_condensed_anderson_protocol_v2(
    *args: Any,
    anderson_settings: SafeguardedAndersonSettings = (
        DEFAULT_SAFEGUARDED_ANDERSON_SETTINGS
    ),
    **kwargs: Any,
) -> controller.ExactCondensedProtocolResult:
    with _bind_solver(anderson_settings):
        return controller.simulate_exact_condensed_protocol_v2(*args, **kwargs)


__all__ = [
    "attempt_exact_condensed_anderson_embedded_interval",
    "simulate_exact_condensed_anderson_protocol_v2",
]

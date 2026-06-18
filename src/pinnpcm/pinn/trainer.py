"""Training entry points for the PINN workflow.

The first engineering version intentionally keeps this module as a minimal
skeleton. It should not be used to report inverse-identification performance.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainerState:
    """Minimal training state placeholder."""

    epoch: int = 0
    best_loss: float = float("inf")


class PINNTrainer:
    """Placeholder trainer for the v1 inverse-identification workflow."""

    def __init__(self) -> None:
        self.state = TrainerState()

    def fit(self) -> TrainerState:
        """Return the initial state until the full training loop is implemented."""

        return self.state

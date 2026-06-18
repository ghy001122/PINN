"""Least-squares fitting baseline skeleton."""

from __future__ import annotations

import numpy as np


def fit_linear_least_squares(features: np.ndarray, targets: np.ndarray) -> dict[str, np.ndarray]:
    """Fit a linear least-squares model as a placeholder baseline."""

    x = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    coef, residuals, rank, singular_values = np.linalg.lstsq(x, y, rcond=None)
    return {
        "coef": coef,
        "residuals": residuals,
        "rank": np.asarray(rank),
        "singular_values": singular_values,
    }

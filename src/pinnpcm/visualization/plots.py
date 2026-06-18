"""Reusable plotting helpers."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from pinnpcm.utils.io import ensure_dir


def save_figure(fig: plt.Figure, path: str | Path, dpi: int = 300) -> Path:
    """Save a matplotlib figure and close it."""

    target = Path(path)
    ensure_dir(target.parent)
    fig.savefig(target, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return target

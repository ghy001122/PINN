"""Provenance and access controls for Zhang et al. public VO2 data.

Pre-fit code may inspect ZIP central-directory metadata to identify the
repository-withheld 13 V member, but it must not decompress that member.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


REQUIRED_FIT_LOCK_KEYS = {
    "fit_lock_sha256",
    "git_commit",
    "config_sha256",
    "fit_data_sha256",
    "preprocessing",
    "metrics",
    "thresholds",
    "all_start_results",
}


def compute_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return an uppercase SHA-256 digest without changing the input."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and minimally validate a VO2 provenance manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "vo2_d0_provenance_v2":
        raise ValueError("Unsupported VO2 provenance manifest schema.")
    if not isinstance(payload.get("artifacts"), list):
        raise ValueError("Manifest artifacts must be a list.")
    return payload


def require_fit_lock_for_sealed_access(fit_lock_path: Path) -> dict[str, Any]:
    """Validate that a fit-lock artifact exists before 13 V access."""

    if not fit_lock_path.exists():
        raise PermissionError(
            "13 V is repository-withheld and cannot be read before fit_lock.json exists."
        )
    payload = json.loads(fit_lock_path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_FIT_LOCK_KEYS.difference(payload))
    if missing:
        raise PermissionError(f"Fit lock is incomplete: {missing}")
    recorded = str(payload["fit_lock_sha256"])
    unlocked = dict(payload)
    unlocked.pop("fit_lock_sha256", None)
    canonical = json.dumps(unlocked, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual = hashlib.sha256(canonical).hexdigest().upper()
    if actual != recorded.upper():
        raise PermissionError("Fit lock SHA-256 does not match its canonical payload.")
    return payload


def _guard_path(path: Path, fit_lock_path: Path | None = None) -> None:
    normalized = path.name.casefold().replace("_", "").replace(" ", "")
    if "13v" not in normalized:
        return
    if fit_lock_path is None:
        raise PermissionError("13 V numeric content is sealed before the fit lock.")
    require_fit_lock_for_sealed_access(fit_lock_path)


def load_rt_curve(path: Path) -> dict[str, Any]:
    """Load the public Fig. 1b temperature-resistance curve."""

    values = np.loadtxt(path, delimiter=",", comments="#", dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("Expected a two-column R-T curve.")
    return {
        "temperature_K": values[:, 0],
        "resistance_ohm": values[:, 1] * 1000.0,
        "source_kind": "public_external_raw",
        "curve_id": "zhang_2024_fig1b_rt",
    }


def load_theory_trace(path: Path, *, fit_lock_path: Path | None = None) -> dict[str, Any]:
    """Load a publisher-provided theory trace without relabeling it as data."""

    _guard_path(path, fit_lock_path)
    values = np.loadtxt(path, delimiter=",", comments="#", dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("Expected a two-column theory trace.")
    return {
        "time_s": values[:, 0] * 1.0e-6,
        "current_A": values[:, 1] * 1.0e-3,
        "source_kind": "source_paper_model_prediction",
        "curve_id": f"zhang_2024_{path.stem.casefold()}",
    }


def load_tektronix_trace(
    path: Path,
    *,
    current_sense_ohm: float,
    fit_lock_path: Path | None = None,
) -> dict[str, Any]:
    """Load a Tektronix CH3/CH4 trace using the declared 50-ohm current channel."""

    _guard_path(path, fit_lock_path)
    if current_sense_ohm <= 0.0:
        raise ValueError("current_sense_ohm must be positive.")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.strip().upper() == "TIME,CH3,CH4"),
        None,
    )
    if header_index is None:
        raise ValueError("Tektronix TIME,CH3,CH4 header was not found.")
    values = np.loadtxt(
        lines[header_index + 1 :],
        delimiter=",",
        dtype=np.float64,
    )
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("Expected TIME, CH3, and CH4 columns.")
    return {
        "time_s": values[:, 0],
        "current_A": values[:, 1] / current_sense_ohm,
        "device_voltage_V": values[:, 2],
        "source_kind": "public_external_raw",
        "curve_id": f"zhang_2024_{path.stem.casefold()}",
        "baseline_subtracted": False,
    }

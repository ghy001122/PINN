"""Data loading utilities for PINN inverse v0."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pinnpcm.utils.config import load_yaml
from pinnpcm.utils.io import read_json


@dataclass(frozen=True)
class InverseV0Data:
    """Frozen Ground Truth and sparse observation bundle for inverse v0."""

    train_data_path: Path
    sparse_obs_path: Path
    manifest_path: Path
    output_dir: Path
    gt: dict[str, np.ndarray | str | float | int]
    obs: dict[str, np.ndarray | str | float | int]
    manifest: dict[str, Any]
    params: dict[str, float]
    gt_keys: list[str]
    obs_keys: list[str]

    @property
    def x(self) -> np.ndarray:
        return np.asarray(self.gt["x"], dtype=float)

    @property
    def t(self) -> np.ndarray:
        return np.asarray(self.gt["t"], dtype=float)

    @property
    def nx(self) -> int:
        return int(self.x.size)

    @property
    def nt(self) -> int:
        return int(self.t.size)

    @property
    def dx(self) -> float:
        return float(self.params["L_eff"]) / float(self.nx)

    @property
    def x_norm(self) -> np.ndarray:
        length = float(self.params["L_eff"])
        if length <= 0.0:
            raise ValueError("L_eff must be positive.")
        return self.x / length

    @property
    def t_norm(self) -> np.ndarray:
        t = self.t
        span = float(t[-1] - t[0])
        if span <= 0.0:
            raise ValueError("Time vector must be strictly increasing.")
        return (t - t[0]) / span


def _resolve_path(path: str | Path, root: Path | None = None) -> Path:
    """Resolve a config path relative to the project root."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (root or Path.cwd()) / candidate


def _read_npz(path: Path) -> tuple[dict[str, np.ndarray | str | float | int], list[str]]:
    """Read an npz file and return scalar arrays as Python scalars."""

    with np.load(path, allow_pickle=False) as payload:
        keys = list(payload.keys())
        data: dict[str, np.ndarray | str | float | int] = {}
        for key in keys:
            value = payload[key]
            data[key] = value.item() if value.shape == () else np.asarray(value)
    return data, keys


def load_inverse_v0_data(
    config: str | Path | dict[str, Any],
    *,
    root: str | Path | None = None,
    verbose: bool = False,
) -> InverseV0Data:
    """Load frozen Ground Truth, sparse observations, and manifest for PINN v0."""

    cfg = load_yaml(config) if isinstance(config, (str, Path)) else dict(config)
    project_root = Path(root) if root is not None else Path.cwd()

    train_data_path = _resolve_path(cfg["train_data"], project_root)
    sparse_obs_path = _resolve_path(cfg["sparse_obs"], project_root)
    manifest_path = _resolve_path(cfg["manifest"], project_root)
    output_dir = _resolve_path(cfg["output_dir"], project_root)

    gt, gt_keys = _read_npz(train_data_path)
    obs, obs_keys = _read_npz(sparse_obs_path)
    manifest = read_json(manifest_path)
    params = json.loads(str(gt["params_json"]))

    if verbose:
        print(f"Loaded Ground Truth npz: {train_data_path}")
        print(f"Ground Truth keys: {gt_keys}")
        print(f"Loaded sparse observation npz: {sparse_obs_path}")
        print(f"Sparse observation keys: {obs_keys}")

    required_gt = {"x", "t", "V", "I", "G", "c_v", "T", "m", "sigma", "params_json"}
    required_obs = {"t_idx", "t", "V", "I", "G"}
    missing_gt = sorted(required_gt.difference(gt_keys))
    missing_obs = sorted(required_obs.difference(obs_keys))
    if missing_gt:
        raise KeyError(f"Ground Truth npz is missing keys: {missing_gt}")
    if missing_obs:
        raise KeyError(f"Sparse observation npz is missing keys: {missing_obs}")

    return InverseV0Data(
        train_data_path=train_data_path,
        sparse_obs_path=sparse_obs_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        gt=gt,
        obs=obs,
        manifest=manifest,
        params=params,
        gt_keys=gt_keys,
        obs_keys=obs_keys,
    )

"""Versioned contract loader for the BranchConserve steady route."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml


ALLOWED_BATCH1_STAGES = frozenset(
    {
        "contract",
        "focused_tests",
        "nominal_l1_smoke",
        "nominal_l1_atlas",
        "nominal_l2_cost_sentinel",
    }
)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_keys(mapping: Mapping[str, Any], keys: set[str], *, name: str) -> None:
    missing = sorted(keys.difference(mapping))
    if missing:
        raise ValueError(f"{name} is missing required keys: {missing}")


@dataclass(frozen=True)
class ReferenceScales:
    voltage_V: float
    current_A: float
    power_W: float
    temperature_K: float
    electrical_residual_max: float
    thermal_residual_max: float
    load_line_residual_max: float
    ledger_relative_max: float
    current_floor_A: float
    power_floor_W: float


@dataclass(frozen=True)
class BranchConserveContract:
    """Resolved, hash-checked BranchConserve configuration."""

    path: Path
    repository_root: Path
    raw: dict[str, Any]
    parent_path: Path
    parent_config: dict[str, Any]
    parent_sha256: str
    scales: ReferenceScales

    @property
    def solver(self) -> dict[str, Any]:
        return self.raw["steady_solver"]

    @property
    def stability(self) -> dict[str, Any]:
        return self.raw["stability"]

    @property
    def batch1(self) -> dict[str, Any]:
        return self.raw["batch1"]

    @property
    def series_resistance_ohm(self) -> float:
        return float(self.raw["load_line"]["series_resistance_ohm"])

    @property
    def external_capacitance_F(self) -> float:
        return float(
            self.parent_config["physics_contract"]["circuit"][
                "parallel_capacitance_F"
            ]
        )

    @property
    def candidate_source_voltages_V(self) -> tuple[float, ...]:
        spec = self.raw["bias_selection"]["candidate_source_voltages_V"]
        start = float(spec["start"])
        stop = float(spec["stop"])
        step = float(spec["step"])
        count = int(round((stop - start) / step)) + 1
        values = [start + index * step for index in range(count)]
        values.extend(float(value) for value in spec.get("append", ()))
        excluded = {float(value) for value in spec.get("excluded", ())}
        return tuple(
            sorted({round(value, 12) for value in values if value not in excluded})
        )

    def assert_batch1_stage_authorized(self, stage: str) -> None:
        configured = set(self.batch1["allowed_stages"])
        if configured != ALLOWED_BATCH1_STAGES:
            raise ValueError("Batch 1 stage allowlist differs from the approved contract")
        if stage not in configured:
            raise PermissionError(f"stage {stage!r} is not authorized in Batch 1")


def load_branchconserve_contract(
    path: Path | str = Path("configs/q2_branchconserve_2d_steady_mve_v1.yaml"),
    *,
    repository_root: Path | str | None = None,
) -> BranchConserveContract:
    """Load and validate the independent steady-route contract."""

    config_path = Path(path)
    root = Path.cwd() if repository_root is None else Path(repository_root)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    root = root.resolve()
    raw = _read_yaml(config_path)
    _require_keys(
        raw,
        {
            "task_id",
            "schema_version",
            "authority",
            "branch_contract",
            "reference_scales",
            "steady_solver",
            "load_line",
            "stability",
            "patches",
            "bias_selection",
            "batch1",
            "batch2",
            "outputs",
            "claim_boundary",
        },
        name="BranchConserve contract",
    )
    if raw["task_id"] != "Q2_BRANCHCONSERVE_2D_STEADY_MVE_V1":
        raise ValueError("unexpected BranchConserve task identity")
    if raw["schema_version"] != "q2_branchconserve_2d_steady_mve_v1":
        raise ValueError("unexpected BranchConserve schema version")
    if raw["batch2"].get("authorized") is not False:
        raise ValueError("Batch 2 must remain unauthorized")

    authority = raw["authority"]
    parent_spec = authority["parent_physics_config"]
    parent_path = (root / str(parent_spec["path"])).resolve()
    expected_parent_hash = str(parent_spec["sha256"]).lower()
    observed_parent_hash = sha256_file(parent_path)
    if observed_parent_hash != expected_parent_hash:
        raise ValueError("parent physics config hash drift detected")
    parent = _read_yaml(parent_path)

    load_resistance = float(
        parent["physics_contract"]["circuit"]["load_resistance_ohm"]
    )
    if not np.isclose(
        load_resistance,
        float(raw["load_line"]["series_resistance_ohm"]),
        rtol=0.0,
        atol=0.0,
    ):
        raise ValueError("load resistance differs from the parent physics contract")
    ambient = float(parent["parameter_contract"]["ambient_temperature_K"])
    tmin, tmax = map(
        float, parent["parameter_contract"]["validity"]["temperature_K"]
    )
    reference = raw["reference_scales"]
    voltage = float(reference["voltage_V"])
    current = voltage / load_resistance
    power = voltage * current
    temperature = max(tmax - ambient, ambient - tmin, 1.0)
    scales = ReferenceScales(
        voltage_V=voltage,
        current_A=current,
        power_W=power,
        temperature_K=temperature,
        electrical_residual_max=float(
            reference["electrical_integrated_residual_max"]
        ),
        thermal_residual_max=float(reference["thermal_integrated_residual_max"]),
        load_line_residual_max=float(
            reference["load_line_integrated_residual_max"]
        ),
        ledger_relative_max=float(reference["ledger_symmetric_relative_max"]),
        current_floor_A=float(reference["current_floor_fraction"]) * current,
        power_floor_W=float(reference["power_floor_fraction"]) * power,
    )
    if not np.isfinite(tuple(scales.__dict__.values())).all():
        raise ValueError("reference scales must be finite")
    if min(scales.__dict__.values()) <= 0.0:
        raise ValueError("reference scales and gates must be positive")

    allowed = set(raw["batch1"]["allowed_stages"])
    forbidden = set(raw["batch1"]["forbidden_stages"])
    if allowed != ALLOWED_BATCH1_STAGES or allowed & forbidden:
        raise ValueError("Batch 1 authorization boundary is inconsistent")
    if raw["claim_boundary"]["batch1_scientific_vote"] is not False:
        raise ValueError("Batch 1 must remain non-voting")
    return BranchConserveContract(
        path=config_path,
        repository_root=root,
        raw=raw,
        parent_path=parent_path,
        parent_config=parent,
        parent_sha256=observed_parent_hash,
        scales=scales,
    )

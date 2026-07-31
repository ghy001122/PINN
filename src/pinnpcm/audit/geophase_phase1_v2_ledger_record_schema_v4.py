"""Solver-free ledger record schema closure for Phase 1-v2 equivalence-v3.

The module has two deliberately separate responsibilities:

* derive the ledger grouping manifest from the frozen field contract, real S2
  ledger constructors, and the production observation extractors; and
* turn one production observation into a content-addressable record which
  preserves both the producer balance name and the structural scale group.

No candidate, oracle, controller, numerical solver, audit scheduler, or audit
row is invoked here.
"""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator as _core
from pinnpcm.audit import geophase_phase1_v2_equivalence_v2_comparator_v3 as _v3
from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_metric_validity_coverage_correction as _coverage,
)
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_ledgers import (
    S2LedgerBundle,
    build_s2_ledgers,
    build_s2_two_half_interval_ledgers,
)
from pinnpcm.physics.geophase_s2_thermal import build_s2_thermal_fields
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as _production


ROOT = Path(__file__).resolve().parents[3]
RECORD_SCHEMA_VERSION = "geophase_phase1_v2_ledger_record_v4"
LEDGER_MANIFEST_SCHEMA_VERSION = "geophase_phase1_v2_ledger_group_manifest_v1"
DEFAULT_SOURCE_CONFIG = ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
DEFAULT_LEDGER_MANIFEST = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_v2_source_corrected_v3"
    / "ledger_record_schema_closure_v4"
    / "ledger_group_manifest.csv"
)

LEDGER_MANIFEST_COLUMNS = (
    "family",
    "profile",
    "field_pattern",
    "producer_balance_name",
    "normalized_scale_group_id",
    "required_when",
    "source_constructor",
    "source_extractor",
)

_LEDGER_CONSTRUCTOR = (
    "pinnpcm.physics.geophase_s2_ledgers.build_s2_ledgers"
)
_AGGREGATE_CONSTRUCTOR = (
    "pinnpcm.physics.geophase_s2_ledgers.build_s2_two_half_interval_ledgers"
)
_ATTEMPT_EXTRACTOR = (
    "pinnpcm.solvers.geophase_phase1_v2_performance_equivalence._attempt_observation"
)
_PROGRESSION_EXTRACTOR = (
    "pinnpcm.solvers.geophase_phase1_v2_performance_equivalence._progression_observation"
)


class LedgerSchemaError(RuntimeError):
    """An explicit pre-record producer/schema/normalization failure."""

    def __init__(self, stage: str, code: str, detail: str):
        super().__init__(detail)
        self.stage = str(stage)
        self.code = str(code)
        self.detail = str(detail)

    def as_record(self) -> dict[str, str]:
        return {"stage": self.stage, "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class LedgerManifestEntry:
    family: str
    profile: str
    field_pattern: str
    producer_balance_name: str
    normalized_scale_group_id: str
    required_when: str
    source_constructor: str
    source_extractor: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.field_pattern)

    def as_row(self) -> dict[str, str]:
        return {name: str(getattr(self, name)) for name in LEDGER_MANIFEST_COLUMNS}


@dataclass(frozen=True)
class LedgerManifest:
    entries: Mapping[tuple[str, str], LedgerManifestEntry]
    csv_sha256: str
    template_identity_sha256: str


@dataclass(frozen=True)
class _Scenario:
    family: str
    profile: str
    extractor: str
    observation: Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_source_config(path: Path = DEFAULT_SOURCE_CONFIG) -> Mapping[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise LedgerSchemaError("producer", "SOURCE_CONFIG_INVALID", "source config is not a mapping")
    return payload


def _grid_shape(config: Mapping[str, Any], grid_id: str) -> tuple[int, int]:
    level = {"L1": 1, "L2": 2, "L4": 4}.get(grid_id)
    if level is None:
        raise LedgerSchemaError("producer", "GRID_ID_INVALID", f"unknown grid: {grid_id}")
    base = config["reference_solver"]["base_grid"]
    return int(base["nx"]) * level, int(base["ny"]) * level


def _real_ledger_fixture(grid_id: str = "L1") -> tuple[Any, S2LedgerBundle]:
    """Construct regular and aggregate production ledgers without a solver."""

    config = _load_source_config()
    nx, ny = _grid_shape(config, grid_id)
    grid = build_geophase_grid(config, nx_override=nx, ny_override=ny)
    fields = build_s2_thermal_fields(grid, config)
    ambient = float(fields.ambient_temperature_K)
    temperature = np.full(grid.shape, ambient, dtype=float)
    zeros = np.zeros(grid.shape, dtype=float)
    electrical = SimpleNamespace(
        potential_V=zeros.copy(),
        source_current_A=0.0,
        ground_current_A=0.0,
        cell_joule_power_W=zeros.copy(),
        joule_power_W=0.0,
        terminal_device_power_W=0.0,
        relative_current_imbalance=0.0,
        relative_power_imbalance=0.0,
    )
    circuit = config["physics_contract"]["circuit"]
    dt_s = 1.0e-9
    regular = build_s2_ledgers(
        grid=grid,
        fields=fields,
        old_temperature_K=temperature,
        new_temperature_K=temperature,
        old_device_voltage_V=0.0,
        new_device_voltage_V=0.0,
        input_voltage_V=0.0,
        load_resistance_ohm=float(circuit["load_resistance_ohm"]),
        capacitance_F=float(circuit["parallel_capacitance_F"]),
        dt_s=dt_s,
        electrical=electrical,
        lateral_boundary_outflow_W=0.0,
    )
    step = SimpleNamespace(
        state=SimpleNamespace(
            time_s=dt_s,
            temperature_K=temperature.copy(),
            conductive_state=zeros.copy(),
            branch_memory=zeros.copy(),
            device_voltage_V=0.0,
        ),
        electrical=electrical,
        lateral_flux=SimpleNamespace(
            net_cell_outflow_W=zeros.copy(),
            x_face_flux_W=np.zeros((grid.ny, grid.nx - 1), dtype=float),
            y_face_flux_W=np.zeros((grid.ny - 1, grid.nx), dtype=float),
            boundary_face_flux_W=np.zeros(2 * grid.ny + 2 * grid.nx, dtype=float),
            boundary_outflow_W=0.0,
            internal_pair_cancellation_W=0.0,
            face_to_cell_global_residual_W=0.0,
            matrix_face_relative_mismatch=0.0,
            matrix_face_roundoff_ratio=0.0,
        ),
        nonlinear=SimpleNamespace(
            method="damped_newton_krylov",
            converged=True,
            iterations=1,
            krylov_matvecs=1,
            armijo_backtracks=0,
            predictor_picard_iterations=0,
            fallback_picard_iterations=0,
            scaled_residual_inf=0.0,
            scaled_update_inf=0.0,
        ),
        ledgers=regular,
    )
    aggregate, _energy = build_s2_two_half_interval_ledgers(
        grid=grid,
        fields=fields,
        outer_initial_temperature_K=temperature,
        outer_initial_device_voltage_V=0.0,
        first_half=step,
        second_half=step,
        half_dt_s=dt_s / 2.0,
        capacitance_F=float(circuit["parallel_capacitance_F"]),
    )
    return step, aggregate


def _real_attempt(
    *,
    grid_id: str = "L1",
    accepted: bool = True,
    failing_path: str | None = None,
) -> Any:
    step, aggregate = _real_ledger_fixture(grid_id)
    paths = ("full_step", "first_half_step", "second_half_step")
    failure_index = None if failing_path is None else paths.index(failing_path)
    steps = {name: copy.deepcopy(step) for name in paths}
    integrities = {
        name: SimpleNamespace(overall_pass=failure_index is None or index < failure_index)
        for index, name in enumerate(paths)
    }
    return SimpleNamespace(
        full_candidate=steps["full_step"],
        first_half_candidate=steps["first_half_step"],
        second_half_candidate=steps["second_half_step"],
        step=steps["second_half_step"] if accepted else None,
        aggregate_ledgers=aggregate,
        diagnostics=SimpleNamespace(
            full_step=integrities["full_step"],
            first_half_step=integrities["first_half_step"],
            second_half_step=integrities["second_half_step"],
            outer_interval_s=1.0e-9,
            half_interval_s=5.0e-10,
            legacy_conductive_increment=0.0,
            legacy_branch_increment=0.0,
            embedded_error=SimpleNamespace(e_T=0.0, e_s=0.0, e_b=0.0, e_V=0.0, e_max=0.0),
        ),
        error_class=("RuntimeError" if failing_path is not None else None),
        error_message=(f"{failing_path} synthetic failure" if failing_path is not None else None),
    )


def _replace_attempt_ledgers(raw: Any, *, grid_id: str = "L1") -> None:
    step, aggregate = _real_ledger_fixture(grid_id)
    for name in ("full_candidate", "first_half_candidate", "second_half_candidate"):
        if getattr(raw, name) is not None:
            setattr(raw, name, copy.deepcopy(step))
    raw.step = None if raw.step is None else copy.deepcopy(step)
    if raw.aggregate_ledgers is not None:
        raw.aggregate_ledgers = copy.deepcopy(aggregate)


def build_production_real_scenarios(grid_id: str = "L1") -> tuple[_Scenario, ...]:
    """Return raw-constructor-backed observations through production extractors."""

    scenarios: list[_Scenario] = []
    interval_raw = _real_attempt(grid_id=grid_id, accepted=True)
    scenarios.append(
        _Scenario(
            "interval",
            "interval_full_accepted",
            _ATTEMPT_EXTRACTOR,
            _production._attempt_observation(interval_raw),
        )
    )
    for path in ("full_step", "first_half_step", "second_half_step"):
        raw = _real_attempt(grid_id=grid_id, accepted=False, failing_path=path)
        observation = _production._attempt_observation(
            raw,
            include_only_integrity_passed_steps=True,
            declared_failure=f"{path}:nonfinite",
        )
        scenarios.append(
            _Scenario("failure", f"failure_at_{path}", _ATTEMPT_EXTRACTOR, observation)
        )

    streaming_schema = _coverage.derive_streaming_schema_from_source()
    progression_raw, attempts = _coverage._raw_progression(streaming_schema)
    real_step, _aggregate = _real_ledger_fixture(grid_id)
    for accepted_step in progression_raw.protocol_result.steps:
        accepted_step.state = copy.deepcopy(real_step.state)
        accepted_step.electrical = copy.deepcopy(real_step.electrical)
        accepted_step.lateral_flux = copy.deepcopy(real_step.lateral_flux)
        accepted_step.nonlinear = copy.deepcopy(real_step.nonlinear)
        accepted_step.ledgers = copy.deepcopy(real_step.ledgers)
        accepted_step.accepted_first_half = copy.deepcopy(real_step)
    progression_raw.final_state = copy.deepcopy(real_step.state)
    for raw in attempts:
        _replace_attempt_ledgers(raw, grid_id=grid_id)
    scenarios.append(
        _Scenario(
            "progression",
            "progression_full",
            _PROGRESSION_EXTRACTOR,
            _production._progression_observation(progression_raw, attempts),
        )
    )
    return tuple(scenarios)


def _canonical_group(name: str) -> str:
    value = _core._canonical_ledger_scale_group(name)
    if value is None:
        raise LedgerSchemaError("normalization", "LEDGER_SLOT_UNKNOWN", f"no structural ledger slot for {name}")
    return value


def _producer_name(field_name: str, producer_group: str) -> str:
    structural = _canonical_group(field_name)
    prefix = structural.rsplit(":", 1)[0]
    expected_prefix = prefix + ":"
    if not producer_group.startswith(expected_prefix):
        raise LedgerSchemaError(
            "normalization",
            "PRODUCER_GROUP_PREFIX_MISMATCH",
            f"producer group for {field_name} does not preserve its structural container",
        )
    value = producer_group[len(expected_prefix) :]
    if not value or ":" in value:
        raise LedgerSchemaError("normalization", "PRODUCER_BALANCE_NAME_INVALID", field_name)
    return value


def build_ledger_group_manifest(
    contract: _core.LoadedContract | _v3.V3LoadedContract,
) -> list[LedgerManifestEntry]:
    """Mechanically derive every ledger-power row and cross-check the 638 source."""

    core_contract = contract.core if isinstance(contract, _v3.V3LoadedContract) else contract
    frozen = {
        key: template
        for key, template in core_contract.templates.items()
        if template.value_kind == "numeric" and template.denominator_key == "ledger_power_terms"
    }
    discovered: dict[tuple[str, str], dict[str, set[str]]] = {}
    for scenario in build_production_real_scenarios("L1"):
        for raw_name, field in scenario.observation.numeric.items():
            if field.denominator_key != "ledger_power_terms":
                continue
            pattern = _core._normalise_field(str(raw_name))
            key = (scenario.family, pattern)
            if (scenario.family, "numeric", pattern) not in frozen:
                raise LedgerSchemaError("schema_loading", "UNFROZEN_LEDGER_TEMPLATE", str(key))
            if not isinstance(field.scale_group, str):
                raise LedgerSchemaError("normalization", "PRODUCER_GROUP_ABSENT", str(key))
            record = discovered.setdefault(
                key,
                {"profiles": set(), "producers": set(), "groups": set(), "extractors": set()},
            )
            record["profiles"].add(scenario.profile)
            record["producers"].add(_producer_name(str(raw_name), field.scale_group))
            record["groups"].add(_canonical_group(pattern))
            record["extractors"].add(scenario.extractor)

    expected = {(family, pattern) for family, _kind, pattern in frozen}
    if set(discovered) != expected:
        missing = sorted(expected - set(discovered))
        extra = sorted(set(discovered) - expected)
        raise LedgerSchemaError(
            "schema_loading",
            "LEDGER_TEMPLATE_COVERAGE_MISMATCH",
            f"missing={missing},extra={extra}",
        )
    output: list[LedgerManifestEntry] = []
    for family, pattern in sorted(discovered):
        facts = discovered[(family, pattern)]
        if any(len(facts[key]) != 1 for key in ("producers", "groups", "extractors")):
            raise LedgerSchemaError("normalization", "LEDGER_IDENTITY_NOT_UNIQUE", f"{family}:{pattern}")
        template = frozen[(family, "numeric", pattern)]
        constructor = _AGGREGATE_CONSTRUCTOR if "aggregate_ledgers" in pattern else _LEDGER_CONSTRUCTOR
        output.append(
            LedgerManifestEntry(
                family=family,
                profile="|".join(sorted(facts["profiles"])),
                field_pattern=pattern,
                producer_balance_name=next(iter(facts["producers"])),
                normalized_scale_group_id=next(iter(facts["groups"])),
                required_when=template.required_when,
                source_constructor=constructor,
                source_extractor=next(iter(facts["extractors"])),
            )
        )
    return output


def ledger_manifest_csv_bytes(entries: Sequence[LedgerManifestEntry]) -> bytes:
    handle = StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=LEDGER_MANIFEST_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for entry in sorted(entries, key=lambda item: item.key):
        writer.writerow(entry.as_row())
    return handle.getvalue().encode("utf-8")


def load_ledger_group_manifest(
    path: Path = DEFAULT_LEDGER_MANIFEST,
    *,
    expected_sha256: str | None = None,
) -> LedgerManifest:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise LedgerSchemaError("schema_loading", "LEDGER_MANIFEST_HASH_MISMATCH", str(path))
    reader = csv.DictReader(raw.decode("utf-8").splitlines())
    if tuple(reader.fieldnames or ()) != LEDGER_MANIFEST_COLUMNS:
        raise LedgerSchemaError("schema_loading", "LEDGER_MANIFEST_COLUMNS_INVALID", str(path))
    entries: dict[tuple[str, str], LedgerManifestEntry] = {}
    for row in reader:
        entry = LedgerManifestEntry(**{name: str(row[name]) for name in LEDGER_MANIFEST_COLUMNS})
        if entry.key in entries:
            raise LedgerSchemaError("schema_loading", "LEDGER_MANIFEST_DUPLICATE", str(entry.key))
        entries[entry.key] = entry
    identities = [entry.as_row() for entry in sorted(entries.values(), key=lambda value: value.key)]
    return LedgerManifest(entries=entries, csv_sha256=digest, template_identity_sha256=canonical_sha256(identities))


def _expand_group_pattern(pattern: str, field_name: str) -> str:
    raw_pattern = re.escape(pattern)
    raw_pattern = raw_pattern.replace(r"\{interval_index\}", r"(?P<interval_index>\d+)")
    raw_pattern = raw_pattern.replace(r"\{record_index\}", r"(?P<record_index>\d+)")
    raw_pattern = raw_pattern.replace(r"\{snapshot_index\}", r"(?P<snapshot_index>\d+)")
    match = re.fullmatch(raw_pattern, _core._normalise_field(field_name))
    # Normalisation deliberately keeps placeholders, so group expansion is
    # obtained from the concrete structural path, not the normalized pattern.
    if match is None and _core._normalise_field(field_name) != pattern:
        raise LedgerSchemaError("normalization", "FIELD_PATTERN_MISMATCH", field_name)
    return _canonical_group(field_name)


def observation_to_record(
    observation: Any,
    *,
    plan_index: int,
    input_sha256: str,
    contract: _v3.V3LoadedContract,
    ledger_manifest: LedgerManifest,
    runtime_input_sha256: str | None = None,
    validation_errors: Sequence[str] = (),
) -> dict[str, Any]:
    """Create a v4 record while preserving producer and normalized identities."""

    base = _v3.observation_to_record(
        observation,
        plan_index=plan_index,
        input_sha256=input_sha256,
        contract=contract,
        validation_errors=validation_errors,
    )
    errors: list[dict[str, str]] = []
    payload = base.get("observation")
    if isinstance(payload, Mapping):
        payload = copy.deepcopy(payload)
        numeric = payload.get("numeric")
        if isinstance(numeric, Mapping):
            for name, value in numeric.items():
                if not isinstance(value, dict):
                    errors.append(LedgerSchemaError("normalization", "NUMERIC_FIELD_INVALID", str(name)).as_record())
                    continue
                old_group = value.pop("scale_group", None)
                value["ledger_balance_name"] = None
                value["scale_group_id"] = old_group
                if value.get("denominator_key") != "ledger_power_terms":
                    continue
                key = (str(payload.get("family")), _core._normalise_field(str(name)))
                entry = ledger_manifest.entries.get(key)
                if entry is None:
                    errors.append(LedgerSchemaError("schema_loading", "LEDGER_TEMPLATE_ABSENT", str(key)).as_record())
                    continue
                try:
                    if not isinstance(old_group, str):
                        raise LedgerSchemaError("normalization", "PRODUCER_GROUP_ABSENT", str(name))
                    producer_name = _producer_name(str(name), old_group)
                    structural_group = _expand_group_pattern(entry.field_pattern, str(name))
                    if producer_name != entry.producer_balance_name:
                        raise LedgerSchemaError("normalization", "PRODUCER_BALANCE_NAME_MISMATCH", str(name))
                    expected_pattern = _core._normalise_field(structural_group.rsplit(":", 1)[0]) + ":" + structural_group.rsplit(":", 1)[1]
                    if expected_pattern != entry.normalized_scale_group_id:
                        raise LedgerSchemaError("normalization", "STRUCTURAL_SCALE_GROUP_MISMATCH", str(name))
                    value["ledger_balance_name"] = producer_name
                    value["scale_group_id"] = structural_group
                except LedgerSchemaError as exc:
                    errors.append(exc.as_record())
        base["observation"] = payload
    for item in base.get("construction_errors", ()):
        if isinstance(item, Mapping):
            errors.append({str(k): str(v) for k, v in item.items()})
        else:
            errors.append({"stage": "canonical_record_formation", "code": "PREDECESSOR_RECORD_ERROR", "detail": str(item)})
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "plan_identity": copy.deepcopy(base.get("plan_identity")),
        "runtime_input_sha256": runtime_input_sha256,
        "failure_contract": copy.deepcopy(base.get("failure_contract")),
        "observation": copy.deepcopy(base.get("observation")),
        "construction_errors": errors,
    }


def validate_normalized_record(
    record: Mapping[str, Any], ledger_manifest: LedgerManifest
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    expected = {
        "schema_version",
        "plan_identity",
        "runtime_input_sha256",
        "failure_contract",
        "observation",
        "construction_errors",
    }
    if set(record) != expected or record.get("schema_version") != RECORD_SCHEMA_VERSION:
        return [LedgerSchemaError("canonical_record_formation", "RECORD_ENVELOPE_INVALID", "v4 record envelope differs").as_record()]
    for item in record.get("construction_errors", ()):
        if isinstance(item, Mapping):
            issues.append({str(k): str(v) for k, v in item.items()})
        else:
            issues.append(LedgerSchemaError("canonical_record_formation", "CONSTRUCTION_ERROR_INVALID", str(item)).as_record())
    payload = record.get("observation")
    numeric = payload.get("numeric") if isinstance(payload, Mapping) else None
    family = payload.get("family") if isinstance(payload, Mapping) else None
    if not isinstance(numeric, Mapping) or not isinstance(family, str):
        issues.append(LedgerSchemaError("canonical_record_formation", "OBSERVATION_INVALID", "observation numeric/family absent").as_record())
        return issues
    actual_groups: dict[str, set[str]] = {}
    expected_groups: dict[str, set[str]] = {}
    for name, value in numeric.items():
        if not isinstance(value, Mapping):
            issues.append(LedgerSchemaError("normalization", "NUMERIC_FIELD_INVALID", str(name)).as_record())
            continue
        if value.get("denominator_key") != "ledger_power_terms":
            if value.get("ledger_balance_name") is not None:
                issues.append(LedgerSchemaError("normalization", "NON_LEDGER_BALANCE_NAME_PRESENT", str(name)).as_record())
            continue
        key = (family, _core._normalise_field(str(name)))
        entry = ledger_manifest.entries.get(key)
        if entry is None:
            issues.append(LedgerSchemaError("schema_loading", "LEDGER_TEMPLATE_ABSENT", str(key)).as_record())
            continue
        try:
            expected_group = _canonical_group(str(name))
        except LedgerSchemaError as exc:
            issues.append(exc.as_record())
            continue
        if value.get("ledger_balance_name") != entry.producer_balance_name:
            issues.append(LedgerSchemaError("normalization", "PRODUCER_BALANCE_NAME_MISMATCH", str(name)).as_record())
        if value.get("scale_group_id") != expected_group:
            issues.append(LedgerSchemaError("normalization", "STRUCTURAL_SCALE_GROUP_MISMATCH", str(name)).as_record())
        actual_groups.setdefault(str(value.get("scale_group_id")), set()).add(str(name))
        expected_groups.setdefault(expected_group, set()).add(str(name))
    if actual_groups != expected_groups:
        issues.append(LedgerSchemaError("normalization", "LEDGER_GROUP_MEMBERSHIP_MISMATCH", "ledger split, merge, collision, missing, or extra group").as_record())
    return issues


def project_to_predecessor_record(record: Mapping[str, Any]) -> dict[str, Any]:
    projected = {
        "schema_version": _v3.RECORD_SCHEMA_VERSION,
        "plan_identity": copy.deepcopy(record.get("plan_identity")),
        "failure_contract": copy.deepcopy(record.get("failure_contract")),
        "observation": copy.deepcopy(record.get("observation")),
        "construction_errors": [],
    }
    payload = projected.get("observation")
    numeric = payload.get("numeric") if isinstance(payload, Mapping) else None
    if isinstance(numeric, Mapping):
        for value in numeric.values():
            if not isinstance(value, dict):
                continue
            value["scale_group"] = value.pop("scale_group_id", None)
            value.pop("ledger_balance_name", None)
    return projected


def group_denominators(record: Mapping[str, Any]) -> dict[str, float]:
    payload = record["observation"]
    grouped: dict[str, list[float]] = {}
    for field in payload["numeric"].values():
        if field["denominator_key"] != "ledger_power_terms":
            continue
        array = np.asarray(field["value"], dtype=float)
        grouped.setdefault(str(field["scale_group_id"]), []).extend(np.ravel(np.abs(array)).tolist())
    return {group: max(values + [1.0e-30]) for group, values in grouped.items()}


def publish_normalized_record(
    record: Mapping[str, Any], directory: Path, *, side: str
) -> tuple[Path, str]:
    if side not in {"candidate", "oracle"}:
        raise LedgerSchemaError("IO", "RECORD_SIDE_INVALID", side)
    payload = canonical_json_bytes(record)
    digest = hashlib.sha256(payload).hexdigest()
    target_dir = directory / side
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{digest}.json"
    if target.exists():
        if target.read_bytes() != payload:
            raise LedgerSchemaError("IO", "CONTENT_ADDRESS_COLLISION", str(target))
        return target, digest
    temporary = target_dir / f".{digest}.{os.getpid()}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
            raise LedgerSchemaError("serialization", "RECORD_HASH_VERIFY_FAILED", str(temporary))
        os.replace(temporary, target)
        if hasattr(os, "O_DIRECTORY"):
            descriptor = os.open(target_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target, digest


def load_normalized_record(path: Path, *, expected_sha256: str | None = None) -> dict[str, Any]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise LedgerSchemaError("IO", "RECORD_HASH_MISMATCH", str(path))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != raw:
        raise LedgerSchemaError("serialization", "RECORD_NOT_CANONICAL", str(path))
    return payload


__all__ = [
    "DEFAULT_LEDGER_MANIFEST",
    "LEDGER_MANIFEST_COLUMNS",
    "LEDGER_MANIFEST_SCHEMA_VERSION",
    "LedgerManifest",
    "LedgerManifestEntry",
    "LedgerSchemaError",
    "RECORD_SCHEMA_VERSION",
    "build_ledger_group_manifest",
    "build_production_real_scenarios",
    "canonical_json_bytes",
    "canonical_sha256",
    "group_denominators",
    "ledger_manifest_csv_bytes",
    "load_ledger_group_manifest",
    "load_normalized_record",
    "observation_to_record",
    "project_to_predecessor_record",
    "publish_normalized_record",
    "sha256_path",
    "validate_normalized_record",
]

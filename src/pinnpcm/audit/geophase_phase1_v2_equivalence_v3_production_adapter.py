"""Frozen production adapter for the independent equivalence-v3 audit.

The module has no audit loop and performs no comparison.  It exposes the
already frozen candidate/oracle production execution chain one row at a time,
then returns the two raw observations to the schema-corrected v3 control
plane.  In particular, it never imports or calls either historical audit
runner or either historical comparison function.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, Protocol

from pinnpcm.audit import geophase_phase1_v2_equivalence_v3_comparator as _v3
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as _production
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    resolve_controller_v2,
)
from scripts import run_geophase_phase1_v2_source_corrected_performance_readiness as _identity


class PlanRowLike(Protocol):
    plan_index: int
    sample_id: str
    family: str
    grid_id: str
    input_sha256: str


@dataclass(frozen=True)
class ProductionAuditContext:
    contract: _v3.LoadedContract
    production_contract: _production.EquivalenceContract
    production_plan: tuple[_production.EquivalencePlanRow, ...]
    resolved_config: Mapping[str, Any]
    cases: Mapping[tuple[str, str], _production.DeterministicAuditCase]
    candidate_solver: Callable[..., Any]
    oracle_solver: Callable[..., Any]
    candidate_identity: Mapping[str, Any]


@dataclass(frozen=True)
class ProductionObservationPair:
    plan_index: int
    sample_id: str
    family: str
    candidate_observation: Any
    oracle_observation: Any
    runtime_input_sha256: str
    candidate_validation_errors: tuple[str, ...]
    oracle_validation_errors: tuple[str, ...]


def _normalise_optional(value: Any) -> str:
    return "" if value is None else str(value)


def _assert_plan_alignment(
    production_plan: tuple[_production.EquivalencePlanRow, ...],
    contract: _v3.LoadedContract,
) -> None:
    frozen = contract.core.plan_rows
    if tuple(sorted(frozen)) != tuple(range(57)) or len(production_plan) != 57:
        raise RuntimeError("production/v3 plan is not the frozen ordered 57 rows")
    for position, row in enumerate(production_plan):
        manifest = frozen.get(position)
        if row.plan_index != position or manifest is None:
            raise RuntimeError("production plan order differs from the frozen manifest")
        expected = {
            "sample_id": row.sample_id,
            "family": row.family,
            "state": _normalise_optional(row.state),
            "grid": _normalise_optional(row.grid),
            "candidate_paths": "|".join(row.candidate_paths),
            "failure_class": _normalise_optional(row.failure_class),
            "maximum_accepted_intervals": _normalise_optional(
                row.maximum_accepted_intervals
            ),
        }
        if {key: str(manifest[key]) for key in expected} != expected:
            raise RuntimeError(f"production row {position} differs from frozen manifest")


@contextmanager
def open_frozen_production_context(
    contract: _v3.LoadedContract | None = None,
) -> Iterator[ProductionAuditContext]:
    """Resolve frozen callables without executing a numerical plan row."""

    loaded = contract or _v3.load_preregistered_contract_bundle()
    production_contract = _production.load_equivalence_contract()
    production_plan = _production.build_equivalence_plan(production_contract)
    _assert_plan_alignment(production_plan, loaded)
    candidate_identity = _identity.validate_frozen_candidate_identity_for_harness(
        expected_file_sha256=_identity.FROZEN_CANDIDATE_IDENTITY_SHA256
    )
    _identity._validate_loaded_candidate_module_origins()
    controller = resolve_controller_v2(
        _identity.SOURCE_CORRECTED_CONFIG_PATH,
        _identity.SOURCE_CORRECTED_CONTROLLER_OVERLAY_PATH,
    )
    resolved_config = _production._resolved_source_corrected_config(
        controller.base_config, controller
    )
    cases = _production.build_deterministic_audit_cases(
        controller.base_config, controller
    )
    from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical

    with _identity._loaded_pr8_test_only_oracle_solver() as oracle_solver:
        if solve_sheet_electrical is oracle_solver:
            raise RuntimeError("candidate and oracle callables are not independent")
        yield ProductionAuditContext(
            contract=loaded,
            production_contract=production_contract,
            production_plan=production_plan,
            resolved_config=resolved_config,
            cases=cases,
            candidate_solver=solve_sheet_electrical,
            oracle_solver=oracle_solver,
            candidate_identity=candidate_identity,
        )


def _case_for_row(
    context: ProductionAuditContext,
    row: _production.EquivalencePlanRow,
) -> _production.DeterministicAuditCase:
    if row.family in {"electrical", "interval", "progression"}:
        if row.grid is None or row.state is None:
            raise ValueError(f"{row.family} row lacks grid/state identity")
        return context.cases[(row.grid, row.state)]
    if row.family == "failure":
        return context.cases[("L1", "legal_critical")]
    raise ValueError(f"unknown equivalence family: {row.family}")


def _execute_electrical_row(
    context: ProductionAuditContext,
    case: _production.DeterministicAuditCase,
) -> _production.PairExecution:
    from pinnpcm.solvers.geophase_phase1_v2_implicit import protocol_voltage

    conductivity = case.closure.conductivity_S_m(
        case.initial_state.temperature_K, case.initial_state.conductive_state
    )
    voltage = float(protocol_voltage(dict(case.protocol), case.initial_state.time_s))
    candidate = context.candidate_solver(case.grid, conductivity, voltage, 0.0)
    oracle = context.oracle_solver(case.grid, conductivity, voltage, 0.0)
    return _production.PairExecution(
        candidate_observation=_production.electrical_observation(candidate),
        oracle_observation=_production.electrical_observation(oracle),
        candidate_raw=candidate,
        oracle_raw=oracle,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
    )


def _execute_observations(
    context: ProductionAuditContext,
    row: _production.EquivalencePlanRow,
    case: _production.DeterministicAuditCase,
) -> _production.PairExecution:
    if row.family == "electrical":
        return _execute_electrical_row(context, case)
    config = dict(context.resolved_config)
    if row.family == "interval":
        return _production._execute_interval_row(row, case, config, context.oracle_solver)
    if row.family == "progression":
        return _production._execute_progression_row(row, case, config, context.oracle_solver)
    if row.family == "failure":
        return _production._execute_failure_row(row, case, config, context.oracle_solver)
    raise ValueError(f"unknown equivalence family: {row.family}")


def execute_production_row(
    context: ProductionAuditContext, row: PlanRowLike
) -> ProductionObservationPair:
    """Execute exactly one frozen row and return un-compared observations."""

    index = row.plan_index
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 57:
        raise ValueError("plan_index is outside the frozen 0..56 range")
    production_row = context.production_plan[index]
    manifest = context.contract.core.plan_rows.get(index)
    expected = {
        "plan_index": index,
        "sample_id": str(manifest["sample_id"]) if manifest else None,
        "family": str(manifest["family"]) if manifest else None,
        "grid_id": str(manifest["grid"] or "L1") if manifest else None,
        "input_sha256": str(manifest["plan_sha256"]) if manifest else None,
    }
    observed = {
        "plan_index": row.plan_index,
        "sample_id": row.sample_id,
        "family": row.family,
        "grid_id": row.grid_id,
        "input_sha256": row.input_sha256,
    }
    if manifest is None or observed != expected:
        raise RuntimeError("control-plane row identity differs from frozen manifest")
    if production_row.plan_index != index:
        raise RuntimeError("production plan ordering changed")
    case = _case_for_row(context, production_row)
    runtime_sha = _production.hash_equivalence_input(
        production_row,
        _production._runtime_input_payload(
            production_row, case, context.resolved_config
        ),
        context.production_contract,
    )
    if not isinstance(runtime_sha, str) or len(runtime_sha) != 64:
        raise RuntimeError("runtime input identity is invalid")
    pair = _execute_observations(context, production_row, case)
    errors = tuple(str(value) for value in pair.validation_errors)
    return ProductionObservationPair(
        plan_index=index,
        sample_id=row.sample_id,
        family=row.family,
        candidate_observation=pair.candidate_observation,
        oracle_observation=pair.oracle_observation,
        runtime_input_sha256=runtime_sha,
        candidate_validation_errors=errors,
        oracle_validation_errors=errors,
    )


__all__ = [
    "PlanRowLike",
    "ProductionAuditContext",
    "ProductionObservationPair",
    "execute_production_row",
    "open_frozen_production_context",
]

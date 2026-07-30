"""Frozen production-record adapter for the one-shot equivalence-v2 audit.

This module is deliberately narrower than an audit runner.  It resolves the
already-frozen candidate/oracle execution chain, executes exactly one supplied
plan row, and converts the resulting production observations into closure-v3
records.  It contains no loop, retry, journal, terminal reducer, or publication
logic and never calls either historical equivalence comparator.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping

from pinnpcm.audit import (
    geophase_phase1_v2_equivalence_v2_comparator_v3 as _v3,
)
from pinnpcm.audit.geophase_phase1_v2_equivalence_v2_one_shot import (
    PlanRow,
)
from pinnpcm.solvers import geophase_phase1_v2_performance_equivalence as _production
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_controller_overlay import (
    resolve_controller_v2,
)
from scripts import run_geophase_phase1_v2_source_corrected_performance_readiness as _identity


@dataclass(frozen=True)
class ProductionAuditContext:
    """Validated production objects held for one non-retryable audit attempt."""

    contract: _v3.V3LoadedContract
    production_contract: _production.EquivalenceContract
    production_plan: tuple[_production.EquivalencePlanRow, ...]
    resolved_config: Mapping[str, Any]
    cases: Mapping[tuple[str, str], _production.DeterministicAuditCase]
    candidate_solver: Callable[..., Any]
    oracle_solver: Callable[..., Any]
    candidate_identity: Mapping[str, Any]


@dataclass(frozen=True)
class ProductionObservationPair:
    """Raw production observations and their non-voting input provenance."""

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
    contract: _v3.V3LoadedContract,
) -> None:
    """Prove the production row order matches the frozen v3 plan manifest."""

    frozen_indices = tuple(sorted(contract.plan_rows))
    if frozen_indices != tuple(range(57)) or len(production_plan) != 57:
        raise RuntimeError("production/v3 plan cardinality is not the frozen 57 rows")
    for production_row in production_plan:
        frozen = contract.plan_rows.get(production_row.plan_index)
        if frozen is None:
            raise RuntimeError("production plan index is absent from the v3 manifest")
        expected = {
            "sample_id": production_row.sample_id,
            "family": production_row.family,
            "state": _normalise_optional(production_row.state),
            "grid": _normalise_optional(production_row.grid),
            "candidate_paths": "|".join(production_row.candidate_paths),
            "failure_class": _normalise_optional(production_row.failure_class),
            "maximum_accepted_intervals": _normalise_optional(
                production_row.maximum_accepted_intervals
            ),
        }
        observed = {key: str(frozen[key]) for key in expected}
        if observed != expected:
            raise RuntimeError(
                f"production row {production_row.plan_index} differs from the "
                "frozen v3 plan manifest"
            )


@contextmanager
def open_frozen_production_context() -> Iterator[ProductionAuditContext]:
    """Validate all frozen identities and expose the production row adapter.

    Entering this context performs no numerical solve.  The PR8 oracle remains
    registered only for the lifetime of the context so every executed row uses
    the same byte-locked callable.
    """

    contract = _v3.load_preregistered_contract_bundle()
    production_contract = _production.load_equivalence_contract()
    production_plan = _production.build_equivalence_plan(production_contract)
    _assert_plan_alignment(production_plan, contract)
    candidate_identity = _identity.validate_frozen_candidate_identity_for_harness(
        expected_file_sha256=_identity.FROZEN_CANDIDATE_IDENTITY_SHA256
    )
    _identity._validate_loaded_candidate_module_origins()
    resolved_controller = resolve_controller_v2(
        _identity.SOURCE_CORRECTED_CONFIG_PATH,
        _identity.SOURCE_CORRECTED_CONTROLLER_OVERLAY_PATH,
    )
    resolved_config = _production._resolved_source_corrected_config(
        resolved_controller.base_config, resolved_controller
    )
    cases = _production.build_deterministic_audit_cases(
        resolved_controller.base_config, resolved_controller
    )
    from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical

    with _identity._loaded_pr8_test_only_oracle_solver() as oracle_solver:
        if solve_sheet_electrical is oracle_solver:
            raise RuntimeError("candidate and oracle electrical callables are not independent")
        yield ProductionAuditContext(
            contract=contract,
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
            raise ValueError(f"{row.family} row lacks state/grid identity")
        return context.cases[(row.grid, row.state)]
    if row.family == "failure":
        return context.cases[("L1", "legal_critical")]
    raise ValueError(f"unknown equivalence family: {row.family}")


def _execute_electrical_row_direct(
    context: ProductionAuditContext,
    case: _production.DeterministicAuditCase,
) -> _production.PairExecution:
    """Execute both frozen electrical callables without the v1 pair/comparator."""

    from pinnpcm.solvers.geophase_phase1_v2_implicit import protocol_voltage

    conductivity = case.closure.conductivity_S_m(
        case.initial_state.temperature_K, case.initial_state.conductive_state
    )
    voltage = float(protocol_voltage(dict(case.protocol), case.initial_state.time_s))
    candidate = context.candidate_solver(
        case.grid, conductivity, voltage, 0.0
    )
    oracle = context.oracle_solver(case.grid, conductivity, voltage, 0.0)
    return _production.PairExecution(
        candidate_observation=_production.electrical_observation(candidate),
        oracle_observation=_production.electrical_observation(oracle),
        candidate_raw=candidate,
        oracle_raw=oracle,
        protocol_voltage_scale_V=case.protocol_voltage_scale_V,
    )


def _execute_production_observations(
    context: ProductionAuditContext,
    row: _production.EquivalencePlanRow,
    case: _production.DeterministicAuditCase,
) -> _production.PairExecution:
    if row.family == "electrical":
        return _execute_electrical_row_direct(context, case)
    config = dict(context.resolved_config)
    if row.family == "interval":
        return _production._execute_interval_row(
            row, case, config, context.oracle_solver
        )
    if row.family == "progression":
        return _production._execute_progression_row(
            row, case, config, context.oracle_solver
        )
    if row.family == "failure":
        return _production._execute_failure_row(
            row, case, config, context.oracle_solver
        )
    raise ValueError(f"unknown equivalence family: {row.family}")


def execute_production_row(
    context: ProductionAuditContext, row: PlanRow
) -> ProductionObservationPair:
    """Execute one frozen row and return observations for the v3 control plane."""

    if not isinstance(row, PlanRow):
        raise TypeError("row must be the one-shot control plane PlanRow")
    plan_index = row.plan_index
    if not isinstance(plan_index, int) or not 0 <= plan_index < 57:
        raise ValueError("plan_index must be an integer in the frozen range 0..56")
    production_row = context.production_plan[plan_index]
    if production_row.plan_index != plan_index:
        raise RuntimeError("production plan ordering changed")
    frozen_row = context.contract.plan_rows.get(plan_index)
    expected_control_identity = {
        "plan_index": plan_index,
        "sample_id": str(frozen_row["sample_id"]) if frozen_row else None,
        "family": str(frozen_row["family"]) if frozen_row else None,
        "grid_id": str((frozen_row["grid"] or "L1")) if frozen_row else None,
        "input_sha256": str(frozen_row["plan_sha256"]) if frozen_row else None,
    }
    observed_control_identity = {
        "plan_index": row.plan_index,
        "sample_id": row.sample_id,
        "family": row.family,
        "grid_id": row.grid_id,
        "input_sha256": row.input_sha256,
    }
    if frozen_row is None or observed_control_identity != expected_control_identity:
        raise RuntimeError("production row identity differs from the v3 manifest")
    if production_row.sample_id != row.sample_id or production_row.family != row.family:
        raise RuntimeError("control-plane row differs from the production plan")
    case = _case_for_row(context, production_row)
    # Bind the concrete case to the frozen production row even though the
    # closure-v3 record identity intentionally uses the manifest's plan hash.
    runtime_input_sha256 = _production.hash_equivalence_input(
        production_row,
        _production._runtime_input_payload(
            production_row, case, context.resolved_config
        ),
        context.production_contract,
    )
    if len(runtime_input_sha256) != 64:
        raise RuntimeError("production runtime input hash is invalid")
    pair = _execute_production_observations(context, production_row, case)
    errors = tuple(str(error) for error in pair.validation_errors)
    return ProductionObservationPair(
        plan_index=plan_index,
        sample_id=row.sample_id,
        family=row.family,
        candidate_observation=pair.candidate_observation,
        oracle_observation=pair.oracle_observation,
        runtime_input_sha256=runtime_input_sha256,
        candidate_validation_errors=errors,
        oracle_validation_errors=errors,
    )


__all__ = [
    "ProductionAuditContext",
    "ProductionObservationPair",
    "execute_production_row",
    "open_frozen_production_context",
]

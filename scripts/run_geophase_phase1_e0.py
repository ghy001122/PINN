"""Run or validate the independently authorized Phase 1 E0 preflight."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any, Mapping

import numpy as np

from pinnpcm.evaluation.geophase_phase1_e0_runner import (
    E0ContractError,
    authority_hashes,
    build_preflight_plan,
    canonical_sha256,
    execute_preflight,
    finalize_external_stop,
    load_yaml,
    sha256_file,
)
from pinnpcm.physics.geophase_geometry import build_geophase_grid
from pinnpcm.physics.geophase_s2_thermal import (
    build_s2_thermal_fields,
    derive_nominal_s2_source_scale,
    effective_vo2_closure_from_v2_config,
    s2_uniform_mode_identities,
)
from pinnpcm.solvers.geophase_2p5d_fvm import solve_sheet_electrical
from pinnpcm.solvers.geophase_phase1_v2_fvm import solve_s2_thermal_backward_euler
from pinnpcm.solvers.geophase_phase1_v2_implicit import (
    advance_s2_backward_euler,
    build_s2_solver_cache,
    initial_s2_state,
)
from pinnpcm.solvers.geophase_phase1_v2_source_corrected_performance import (
    run_c3_sample,
    task_adapter,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_e0_execution_v1.yaml"
S2_CONFIG_PATH = (
    ROOT / "configs" / "geophase_phase1_v2_s2_reference_source_corrected_v3.yaml"
)
AUTHORIZATION_PATH = (
    ROOT / "outputs" / "tables" / "geophase_phase1_e0" / "execution_authorization.json"
)
OUTPUT_ROOT = ROOT / "outputs" / "tables" / "geophase_phase1_e0" / "runs"
RUNNER_SOURCE_PATH = ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_phase1_e0_runner.py"
CLI_SOURCE_PATH = Path(__file__).resolve()
_THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


def _apply_single_thread_environment() -> None:
    for key, value in _THREAD_ENVIRONMENT.items():
        os.environ[key] = value


def _validate_execution_anchor(config: Mapping[str, Any]) -> dict[str, Any]:
    if not AUTHORIZATION_PATH.is_file():
        raise E0ContractError("E0 execution authorization is not remotely anchored")
    authorization = json.loads(AUTHORIZATION_PATH.read_text(encoding="utf-8"))
    expected = {
        "config_sha256": sha256_file(CONFIG_PATH),
        "runner_source_sha256": sha256_file(RUNNER_SOURCE_PATH),
        "CLI_source_sha256": sha256_file(CLI_SOURCE_PATH),
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise E0ContractError(f"E0 execution authorization {key} drifted")
    anchor = str(authorization.get("code_anchor_commit", ""))
    if anchor != str(config["authorization"]["code_anchor_commit"]):
        raise E0ContractError("E0 code anchor differs between config and authorization")
    if not anchor or anchor == "PENDING_REMOTE_ANCHOR":
        raise E0ContractError("E0 code anchor is not frozen")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", anchor, "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return authorization


def _foundation_checks() -> dict[str, Any]:
    config = load_yaml(S2_CONFIG_PATH)
    grid = build_geophase_grid(config, spatial_level=1)
    fields = build_s2_thermal_fields(grid, config)
    closure = effective_vo2_closure_from_v2_config(config)
    scale = derive_nominal_s2_source_scale(config)
    identities = s2_uniform_mode_identities(grid, fields)
    preflight_gates = config["analytic_source_scale_preflights"]
    gates = config["gates"]

    sigma = np.full(grid.shape, 12.0, dtype=float)
    electrical = solve_sheet_electrical(grid, sigma, 1.0)
    expected_1d = 1.0 - grid.x_centers_m / grid.x_edges_m[-1]
    expected = np.broadcast_to(expected_1d[None, :], grid.shape)
    electrical_l2 = float(
        np.linalg.norm(electrical.potential_V - expected)
        / max(np.linalg.norm(expected), 1.0e-30)
    )
    exact_current = (
        12.0 * grid.thickness_m * grid.y_edges_m[-1] / grid.x_edges_m[-1]
    )
    current_relative_error = abs(electrical.source_current_A - exact_current) / exact_current

    dt_s = 1.0e-8
    delta_K = 1.0e-2
    old_temperature = np.full(grid.shape, fields.ambient_temperature_K)
    target_temperature = old_temperature + delta_K
    source = (
        fields.effective_areal_capacity_J_m2K * delta_K / dt_s
        + fields.vertical_conductance_W_m2K * delta_K
    )
    thermal = solve_s2_thermal_backward_euler(
        grid,
        fields,
        old_temperature,
        np.zeros(grid.shape),
        dt_s,
        external_areal_source_W_m2=source,
    )
    thermal_l2 = float(
        np.linalg.norm(thermal - target_temperature)
        / max(np.linalg.norm(target_temperature), 1.0e-30)
    )

    cache = build_s2_solver_cache(grid, fields)
    step = advance_s2_backward_euler(
        initial_s2_state(grid, closure, fields, config),
        input_voltage_V=1.0,
        dt_s=dt_s,
        grid=grid,
        closure=closure,
        fields=fields,
        config=config,
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=False,
    )
    ledger_maxima = {
        "thermal": float(step.ledgers.thermal.relative_residual),
        "circuit": float(step.ledgers.circuit.relative_residual),
        "combined": float(step.ledgers.combined.relative_residual),
        "device_power": float(step.ledgers.device_power.relative_residual),
    }
    checks = {
        "source_memory_coefficient_positive": scale["nominal_memory_coefficient_J_K"] > 0.0,
        "uniform_capacity_identity": identities["capacity_relative_error"]
        <= float(
            preflight_gates[
                "area_integrated_explicit_plus_memory_coefficient_relative_error_max"
            ]
        ),
        "uniform_conductance_identity": identities["conductance_relative_error"]
        <= float(
            preflight_gates[
                "area_integrated_dc_thermal_conductance_relative_error_max"
            ]
        ),
        "manufactured_electrical": electrical_l2
        <= float(gates["manufactured_electrical_relative_l2_max"]),
        "analytic_current": current_relative_error
        <= float(preflight_gates["uniform_insulating_resistance_relative_error_max"]),
        "terminal_current_balance": electrical.relative_current_imbalance
        <= float(gates["terminal_current_relative_imbalance_max"]),
        "device_power_identity": electrical.relative_power_imbalance
        <= float(gates["device_power_identity_relative_residual_max"]),
        "manufactured_thermal": thermal_l2
        <= float(gates["manufactured_thermal_relative_l2_max"]),
        "thermal_ledger": ledger_maxima["thermal"]
        <= float(gates["thermal_ledger_relative_residual_max"]),
        "circuit_ledger": ledger_maxima["circuit"]
        <= float(gates["circuit_ledger_relative_residual_max"]),
        "combined_ledger": ledger_maxima["combined"]
        <= float(gates["combined_ledger_relative_residual_max"]),
        "step_device_power": ledger_maxima["device_power"]
        <= float(gates["device_power_identity_relative_residual_max"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "metrics": {
            "manufactured_electrical_relative_l2": electrical_l2,
            "analytic_current_relative_error": current_relative_error,
            "manufactured_thermal_relative_l2": thermal_l2,
            "terminal_current_relative_imbalance": electrical.relative_current_imbalance,
            "device_power_relative_imbalance": electrical.relative_power_imbalance,
            "ledger_relative_residuals": ledger_maxima,
        },
        "formal_execution_count": 0,
        "scientific_vote": False,
    }


class _SelectedImplementationAdapter:
    def __init__(self, candidate_identity_sha256: str) -> None:
        self._candidate_identity_sha256 = candidate_identity_sha256
        self._worker_rss: dict[str, Any] | None = None
        self._hooks: dict[str, Any] | None = None

    def measure_worker_rss(self) -> Mapping[str, Any]:
        self._worker_rss = dict(
            task_adapter(
                mode="measure_worker_rss",
                payload={"candidate_identity_sha256": self._candidate_identity_sha256},
            )
        )
        return self._worker_rss

    def _resolved_hooks(self) -> dict[str, Any]:
        if self._worker_rss is None:
            raise E0ContractError("worker RSS must be measured before E0 hooks")
        if self._hooks is None:
            self._hooks = dict(
                task_adapter(
                    mode="readiness_hooks",
                    payload={
                        "equivalence": {
                            "candidate_identity_sha256": self._candidate_identity_sha256
                        },
                        "worker_rss": self._worker_rss,
                    },
                )
            )
        return self._hooks

    def measure_environment(self) -> Mapping[str, Any]:
        return self._resolved_hooks()["measure_launch_environment"]()

    def run_c1(self, remaining_s: float) -> Mapping[str, Any]:
        return self._resolved_hooks()["run_c1"](remaining_s)

    def run_c2(self, remaining_s: float) -> Mapping[str, Any]:
        return self._resolved_hooks()["run_c2"](remaining_s)

    def run_profile_sample(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        result = dict(run_c3_sample(plan))
        if result.get("status") == "PASS" and isinstance(result.get("payload"), Mapping):
            return dict(result["payload"])
        return {
            "status": "FAIL",
            "failure_class": result.get("failure_class", "numerical_integrity"),
            **dict(result.get("payload", {})),
        }

    def build_forecast(
        self,
        samples: tuple[Mapping[str, Any], ...],
        c2: Mapping[str, Any],
        worker_count: int,
    ) -> Mapping[str, Any]:
        completed = tuple({"payload": dict(sample)} for sample in samples)
        return self._resolved_hooks()["build_forecast"](
            completed, c2, worker_count
        )


def validate_only() -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    hashes = authority_hashes(ROOT, config)
    plan = build_preflight_plan(config)
    authorization_ready = False
    authorization_error: str | None = None
    try:
        _validate_execution_anchor(config)
        authorization_ready = True
    except (E0ContractError, subprocess.CalledProcessError) as error:
        authorization_error = str(error)
    return {
        "task_id": config["task_id"],
        "authority_file_count": len(hashes),
        "authority_sha256": canonical_sha256(hashes),
        "preflight_plan_count": len(plan),
        "preflight_plan_sha256": canonical_sha256(plan),
        "authorization_ready": authorization_ready,
        "authorization_error": authorization_error,
        "formal_execution_count": 0,
    }


def run_preflight_worker() -> dict[str, Any]:
    _apply_single_thread_environment()
    config = load_yaml(CONFIG_PATH)
    _validate_execution_anchor(config)
    candidate = next(
        item["sha256"]
        for item in config["authority"]["files"]
        if item["path"].endswith("optimized_candidate_identity.json")
    )


def run_preflight_supervised() -> dict[str, Any]:
    config = load_yaml(CONFIG_PATH)
    _validate_execution_anchor(config)
    run_id = str(config["preflight"]["run_id"])
    registry_root = OUTPUT_ROOT / run_id
    timeout_s = float(config["budgets"]["preflight_wall_clock_s"])
    environment = os.environ.copy()
    environment.update(_THREAD_ENVIRONMENT)
    command = [sys.executable, str(CLI_SOURCE_PATH), "--execute-preflight-worker"]
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return finalize_external_stop(
            registry_root,
            state="E0_PERFORMANCE_ONLY_NO_GO",
            validity="valid_readiness_provenance",
            reason="preflight_CPU_wall_clock_budget_exhausted",
            wall_clock_s=perf_counter() - started,
        )
    if completed.returncode != 0:
        return finalize_external_stop(
            registry_root,
            state="INVALID_E0_EXECUTION",
            validity="invalid",
            reason=(completed.stderr or completed.stdout)[-2000:],
            wall_clock_s=perf_counter() - started,
        )
    return json.loads(completed.stdout)
    return execute_preflight(
        root=ROOT,
        config=config,
        output_root=OUTPUT_ROOT,
        adapter=_SelectedImplementationAdapter(str(candidate)),
        foundation_runner=_foundation_checks,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-only", action="store_true")
    group.add_argument("--execute-preflight", action="store_true")
    group.add_argument("--execute-preflight-worker", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        payload = validate_only()
    elif args.execute_preflight_worker:
        payload = run_preflight_worker()
    else:
        payload = run_preflight_supervised()
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

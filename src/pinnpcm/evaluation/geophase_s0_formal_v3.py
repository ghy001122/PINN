"""Fresh 63-item S0 campaign using controller-v3 trajectories.

The frozen scientific fixtures and evaluator are reused from the S0 science
module.  Its historical campaign control plane is never called.  Every
trajectory, including zero-drive limits and dual-copy controls, is dispatched
through streaming/controller-v3 under a new campaign identity.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from pinnpcm.evaluation.geophase_controller_v3_qualification import (
    _validate_authority,
)
from pinnpcm.evaluation.geophase_s0_direct_physics import (
    ROOT,
    S0ExecutionError,
    apply_single_thread_environment,
    atomic_json,
    formal_plan,
    foundation_payload,
    load_yaml,
    read_canonical_json,
    sha256_file,
    to_builtin,
)
from pinnpcm.evaluation.geophase_s0_formal import (
    _atomic_canonical_gzip,
    _atomic_csv,
    _context,
    _environment_payload,
    _fail_fixture,
    _lim_payload,
    _load_units,
    _mms_payload,
    _publish_registry,
    _trajectory_local_metrics,
    _trajectory_record,
    _utc_now,
    evaluate_completed_units,
)
from pinnpcm.solvers.geophase_phase1_v2_implicit import initial_s2_state
from pinnpcm.solvers.geophase_phase1_v2_streaming_v3 import (
    run_s2_streaming_protocol_v3,
)


_FOUNDATION_GROUPS = {"FAIL", "MMS", "LIM"}
_STAGES = (2, 3, 4, 5, 6, 7)


def _execution_code_hashes() -> dict[str, str]:
    paths = (
        "src/pinnpcm/evaluation/geophase_s0_formal_v3.py",
        "src/pinnpcm/evaluation/geophase_s0_formal.py",
        "src/pinnpcm/solvers/geophase_phase1_v2_controller_v3.py",
        "src/pinnpcm/solvers/geophase_phase1_v2_streaming_v3.py",
    )
    return {path: sha256_file(ROOT / path) for path in paths}


def _run_trajectory_v3(
    unit: Mapping[str, Any],
    *,
    remaining_s: float,
    failure_root: Path,
    overlap_m: float | None = None,
) -> dict[str, Any]:
    level = int(unit["spatial_level"])
    divisor = int(unit["time_divisor"])
    protocol_id = str(unit["protocol_id"])
    unit_id = str(unit["execution_unit_id"])
    grid, fields, closure, cache, scientific = _context(level, overlap_m=overlap_m)
    initial = initial_s2_state(grid, closure, fields, scientific)

    def publish_failure(payload: dict[str, Any]) -> None:
        atomic_json(Path(failure_root) / f"{unit_id}.json", payload)

    result = run_s2_streaming_protocol_v3(
        unit_id,
        initial,
        protocol=scientific["formal_protocols"]["protocols"][protocol_id],
        protocol_id=protocol_id,
        grid=grid,
        closure=closure,
        fields=fields,
        config=scientific,
        time_divisor=divisor,
        final_time_s=2.0e-5,
        maximum_wall_clock_s=max(float(remaining_s), 1.0e-6),
        retain_full_history=False,
        failure_callback=publish_failure,
        cache=cache,
        use_equivalent_optimizations=True,
        use_unit_voltage_scaling=True,
    )
    if not result.protocol_result.completed:
        return {
            "execution_unit_id": unit_id,
            "execution_group": unit["execution_group"],
            "validity": "invalid",
            "status": (
                "PERFORMANCE_STOP"
                if result.protocol_result.stop_reason == "maximum_wall_clock_reached"
                else "INVALID"
            ),
            "scientific_vote": False,
            "local_metrics": {},
            "raw": _trajectory_record(result),
        }
    metrics = _trajectory_local_metrics(result, scientific)
    return {
        "execution_unit_id": unit_id,
        "execution_group": unit["execution_group"],
        "validity": "valid",
        "status": "PASS" if metrics["passed"] else "SCIENTIFIC_FAIL",
        "scientific_vote": True,
        "local_metrics": metrics,
        "raw": _trajectory_record(result),
    }


def _lim_payload_v3(
    unit: Mapping[str, Any], *, remaining_s: float, failure_root: Path
) -> dict[str, Any]:
    if str(unit["fixture_id"]) != "zero_drive_equilibrium":
        return _lim_payload(unit, remaining_s=remaining_s)
    addendum = load_yaml(
        ROOT / "configs/geophase_phase1_v2_execution_addendum_source_corrected_v3.yaml"
    )
    semantics = addendum["group_execution_semantics"]["LIM"]["fixtures"][
        "zero_drive_equilibrium"
    ]
    resolved = dict(unit)
    resolved.update(
        spatial_level=int(semantics["spatial_level"]),
        time_divisor=int(semantics["time_divisor"]),
        protocol_id=str(semantics["protocol"]),
    )
    return _run_trajectory_v3(
        resolved, remaining_s=remaining_s, failure_root=failure_root
    )


def _dual_payload_v3(
    unit: Mapping[str, Any], *, remaining_s: float, failure_root: Path
) -> dict[str, Any]:
    fixture = str(unit["fixture_id"])
    definitions = {
        "A_only_drive": ("transition_probe_12p5V", "zero_drive"),
        "B_only_drive": ("zero_drive", "transition_probe_12p5V"),
        "equal_drive_symmetry": (
            "transition_probe_12p5V",
            "transition_probe_12p5V",
        ),
        "swapped_label_invariance": (
            "transition_probe_12p5V",
            "transition_probe_12p5V",
        ),
    }
    if fixture not in definitions:
        raise S0ExecutionError(f"unknown DUAL0 fixture: {fixture}")
    protocol_a, protocol_b = definitions[fixture]
    base = dict(unit)
    base.update(spatial_level=1, time_divisor=1)
    base["protocol_id"] = protocol_a
    base["execution_unit_id"] = f"{unit['execution_unit_id']}-A"
    started = perf_counter()
    result_a = _run_trajectory_v3(
        base, remaining_s=remaining_s, failure_root=failure_root
    )
    base["protocol_id"] = protocol_b
    base["execution_unit_id"] = f"{unit['execution_unit_id']}-B"
    result_b = _run_trajectory_v3(
        base,
        remaining_s=max(remaining_s - (perf_counter() - started), 1.0e-6),
        failure_root=failure_root,
    )
    status, validity = "PASS", "valid"
    if "PERFORMANCE_STOP" in {result_a["status"], result_b["status"]}:
        status, validity = "PERFORMANCE_STOP", "invalid"
    elif "INVALID" in {result_a["status"], result_b["status"]}:
        status, validity = "INVALID", "invalid"
    elif "SCIENTIFIC_FAIL" in {result_a["status"], result_b["status"]}:
        status = "SCIENTIFIC_FAIL"
    return {
        "execution_unit_id": unit["execution_unit_id"],
        "execution_group": "DUAL0",
        "validity": validity,
        "status": status,
        "scientific_vote": validity == "valid",
        "local_metrics": {"fixture_id": fixture},
        "raw": {"A": result_a, "B": result_b},
    }


def execute_unit_v3(
    unit: Mapping[str, Any], *, remaining_s: float, failure_root: Path
) -> dict[str, Any]:
    group = str(unit["execution_group"])
    started = perf_counter()
    if group == "FAIL":
        payload = _fail_fixture(unit)
    elif group == "MMS":
        payload = _mms_payload(unit)
    elif group == "LIM":
        payload = _lim_payload_v3(
            unit, remaining_s=remaining_s, failure_root=failure_root
        )
    elif group == "REF":
        payload = _run_trajectory_v3(
            unit, remaining_s=remaining_s, failure_root=failure_root
        )
    elif group == "TOP":
        payload = _run_trajectory_v3(
            unit,
            remaining_s=remaining_s,
            overlap_m=float(unit["contact_overlap_m"]),
            failure_root=failure_root,
        )
    elif group == "DUAL0":
        payload = _dual_payload_v3(
            unit, remaining_s=remaining_s, failure_root=failure_root
        )
    else:
        raise S0ExecutionError(f"unsupported formal execution group: {group}")
    payload["wall_clock_s"] = perf_counter() - started
    payload["consumer_evaluation_ids"] = list(unit["consumer_evaluation_ids"])
    payload["controller_id"] = "controller-v3"
    return to_builtin(payload)


def _terminalize(
    *,
    config: Mapping[str, Any],
    output_root: Path,
    registry: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    anchor_commit: str,
) -> dict[str, Any]:
    verdicts, evaluation = evaluate_completed_units(records)
    verdict_sha = _atomic_csv(
        output_root / "evaluation_verdicts.csv",
        verdicts,
        [
            "evaluation_id",
            "evaluation_group",
            "trajectory_id",
            "status",
            "validity",
            "details_json",
        ],
    )
    all_units_valid = len(records) == 60 and all(
        payload["validity"] == "valid" for payload in records.values()
    )
    terminal = (
        "S0_V3_PASS"
        if all_units_valid and evaluation["all_required_pass"]
        else "S0_V3_SCIENTIFIC_FAIL"
    )
    registry.update(
        state=terminal,
        validity="valid",
        scientific_vote=True,
        formal_execution_count=1,
        updated_utc=_utc_now(),
    )
    summary = {
        "schema_version": "geophase_s0_formal_v3_summary_v1",
        "task_id": config["task_id"],
        "campaign_id": registry["campaign_id"],
        "terminal_state": terminal,
        "validity": "valid",
        "scientific_vote": True,
        "formal_execution_count": 1,
        "completed_execution_units": len(records),
        "evaluation": evaluation,
        "qualification_summary_sha256": registry["qualification_summary_sha256"],
        "execution_code_sha256": registry["execution_code_sha256"],
        "unit_sha256": dict(sorted(registry["unit_sha256"].items())),
        "evaluation_verdicts_csv_sha256": verdict_sha,
        "anchor_commit": anchor_commit,
        "created_utc": _utc_now(),
    }
    registry["summary_sha256"] = atomic_json(
        output_root / "s0_v3_summary.json", summary
    )
    _publish_registry(output_root, registry)
    return summary


def _terminalize_foundation_failure(
    *,
    output_root: Path,
    registry: dict[str, Any],
    foundation: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish a valid foundation scientific failure without fabricating units."""

    registry.update(
        state="S0_V3_SCIENTIFIC_FAIL",
        validity="valid",
        scientific_vote=True,
        formal_execution_count=1,
        updated_utc=_utc_now(),
    )
    summary = {
        "schema_version": "geophase_s0_formal_v3_summary_v1",
        "task_id": registry["task_id"],
        "campaign_id": registry["campaign_id"],
        "terminal_state": "S0_V3_SCIENTIFIC_FAIL",
        "validity": "valid",
        "scientific_vote": True,
        "formal_execution_count": 1,
        "completed_execution_units": 0,
        "foundation": to_builtin(foundation),
        "evaluation": {
            "evaluation_items": 63,
            "assessed_items": 0,
            "passed_items": 0,
            "failed_items": 0,
            "unassessed_items": 63,
            "all_required_pass": False,
        },
        "qualification_summary_sha256": registry[
            "qualification_summary_sha256"
        ],
        "execution_code_sha256": registry["execution_code_sha256"],
        "unit_sha256": {},
        "anchor_commit": registry["anchor_commit"],
        "created_utc": _utc_now(),
    }
    registry["summary_sha256"] = atomic_json(
        output_root / "s0_v3_summary.json", summary
    )
    _publish_registry(output_root, registry)
    return summary


def run_formal_campaign_v3(
    *, config_path: Path, output_root: Path, anchor_commit: str
) -> dict[str, Any]:
    apply_single_thread_environment()
    config = load_yaml(config_path)
    authority = _validate_authority(config)
    if len(anchor_commit) != 40 or any(
        character not in "0123456789abcdef" for character in anchor_commit
    ):
        raise S0ExecutionError("S0-v3 anchor must be a lowercase 40-character SHA")
    qualification_path = (
        ROOT / str(config["outputs"]["qualification"]) / "qualification_summary.json"
    )
    qualification = read_canonical_json(qualification_path)
    if qualification["terminal_state"] != "CONTROLLER_V3_QUALIFIED":
        raise S0ExecutionError("S0-v3 requires a qualified controller-v3 summary")
    qualification_sha = sha256_file(qualification_path)
    units = _load_units()
    plan = formal_plan()
    formal = config["formal_s0"]
    output_root = Path(output_root)
    if output_root.exists():
        raise S0ExecutionError("S0-v3 campaign identity already exists")
    output_root.mkdir(parents=True)
    (output_root / "units").mkdir()
    failure_root = output_root / "failures"
    failure_root.mkdir()
    snapshot = deepcopy(config)
    snapshot["identity"]["formal_code_anchor_commit"] = anchor_commit
    snapshot_sha = atomic_json(output_root / "config_snapshot.json", snapshot)
    registry = {
        "schema_version": "geophase_s0_formal_v3_registry_v1",
        "task_id": config["task_id"],
        "campaign_id": config["identity"]["formal_campaign_id"],
        "anchor_commit": anchor_commit,
        "config_snapshot_sha256": snapshot_sha,
        "qualification_summary_sha256": qualification_sha,
        "authority_sha256": authority,
        "execution_code_sha256": _execution_code_hashes(),
        "environment": _environment_payload(),
        "plan_sha256": {
            "dag": plan["dag_sha256"],
            "manifest_csv": plan["manifest_csv_sha256"],
        },
        "state": "RUNNING",
        "validity": "pending",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "completed_unit_ids": [],
        "unit_sha256": {},
        "started_utc": _utc_now(),
        "updated_utc": _utc_now(),
    }
    _publish_registry(output_root, registry)
    foundation = foundation_payload()
    foundation.update(case_id="S0-V3-FORMAL-FOUNDATION", scientific_vote=True)
    atomic_json(output_root / "foundation.json", foundation)
    if foundation["status"] != "PASS":
        return _terminalize_foundation_failure(
            output_root=output_root,
            registry=registry,
            foundation=foundation,
        )

    records: dict[str, Mapping[str, Any]] = {}
    started = perf_counter()
    wall_limit = float(formal["maximum_wall_clock_s"])
    cpu_limit = float(formal["maximum_cpu_time_s"])
    worker_count = int(formal["worker_count"])
    try:
        for stage in _STAGES:
            stage_units = [
                unit for unit in units if int(unit["execution_stage"]) == stage
            ]
            remaining = wall_limit - (perf_counter() - started)
            if remaining <= 0.0:
                raise S0ExecutionError("S0-v3 wall-clock budget exhausted")
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        execute_unit_v3,
                        unit,
                        remaining_s=remaining,
                        failure_root=failure_root,
                    ): unit
                    for unit in stage_units
                }
                for future in as_completed(futures):
                    unit = futures[future]
                    payload = future.result()
                    unit_id = str(unit["execution_unit_id"])
                    hashes = _atomic_canonical_gzip(
                        output_root / "units" / f"{unit_id}.json.gz", payload
                    )
                    records[unit_id] = payload
                    registry["unit_sha256"][unit_id] = hashes
                    registry["completed_unit_ids"] = [
                        str(item["execution_unit_id"])
                        for item in units
                        if str(item["execution_unit_id"]) in records
                    ]
                    registry["updated_utc"] = _utc_now()
                    _publish_registry(output_root, registry)
                    if payload["validity"] != "valid":
                        raise S0ExecutionError(
                            f"S0-v3 unit invalid: {unit_id}: {payload['status']}"
                        )
            aggregate_cpu = sum(
                float(payload["wall_clock_s"]) for payload in records.values()
            )
            if aggregate_cpu > cpu_limit:
                raise S0ExecutionError("S0-v3 aggregate CPU budget exhausted")
            if stage_units and str(stage_units[0]["execution_group"]) in _FOUNDATION_GROUPS:
                if any(
                    records[str(unit["execution_unit_id"])]["status"]
                    == "SCIENTIFIC_FAIL"
                    for unit in stage_units
                ):
                    return _terminalize(
                        config=config,
                        output_root=output_root,
                        registry=registry,
                        records=records,
                        anchor_commit=anchor_commit,
                    )
    except Exception as error:
        registry.update(
            state="INVALID_S0_V3_EXECUTION",
            validity="invalid",
            scientific_vote=False,
            formal_execution_count=0,
            error_type=type(error).__name__,
            error_message=str(error),
            updated_utc=_utc_now(),
        )
        _publish_registry(output_root, registry)
        raise
    return _terminalize(
        config=config,
        output_root=output_root,
        registry=registry,
        records=records,
        anchor_commit=anchor_commit,
    )


__all__ = ["execute_unit_v3", "run_formal_campaign_v3"]

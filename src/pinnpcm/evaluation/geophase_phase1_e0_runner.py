"""Independent E0 control plane for one frozen S2 implementation.

The module owns authority validation, deterministic preflight planning,
content-addressed case publication, and the append-only execution journal.  It
does not import an equivalence comparator or any historical readiness runner.
Numerical work is supplied through a small adapter protocol so the control
plane remains solver-free in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

import yaml


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATES = {
    "PREFLIGHT_PASS",
    "INVALID_E0_EXECUTION",
    "E0_IMPLEMENTATION_FAIL",
    "E0_PERFORMANCE_ONLY_NO_GO",
}


class E0ContractError(RuntimeError):
    """Raised before a scientific vote when the execution contract is invalid."""


class E0Adapter(Protocol):
    def measure_worker_rss(self) -> Mapping[str, Any]: ...

    def measure_environment(self) -> Mapping[str, Any]: ...

    def run_c1(self, remaining_s: float) -> Mapping[str, Any]: ...

    def run_c2(self, remaining_s: float) -> Mapping[str, Any]: ...

    def run_profile_sample(self, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def build_forecast(
        self,
        samples: tuple[Mapping[str, Any], ...],
        c2: Mapping[str, Any],
        worker_count: int,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class E0RegistryView:
    root: Path
    registry: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    published_cases: dict[str, Path]

    @property
    def state(self) -> str:
        return str(self.registry["state"])


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise E0ContractError(f"{path} must contain a YAML mapping")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _flush_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, content: bytes) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    if hashlib.sha256(temporary.read_bytes()).digest() != hashlib.sha256(content).digest():
        temporary.unlink(missing_ok=True)
        raise E0ContractError("atomic write hash verification failed")
    os.replace(temporary, destination)
    _flush_directory(destination.parent)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_write(path, canonical_bytes(payload))


def _append_journal_event(root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    journal = Path(root) / "journal.jsonl"
    if journal.is_file():
        view = load_registry(root)
        sequence = len(view.events)
        previous = view.events[-1]["event_sha256"]
    else:
        sequence = 0
        previous = None
    event = {
        "schema_version": "geophase_phase1_e0_journal_event_v1",
        "sequence": sequence,
        "created_utc": _utc_now(),
        "previous_event_sha256": previous,
        **dict(payload),
    }
    digest = canonical_sha256(event)
    event["event_sha256"] = digest
    encoded = canonical_bytes(event)
    with journal.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return event


def _registry_path(root: Path) -> Path:
    return Path(root) / "registry.json"


def create_registry(
    root: Path,
    *,
    run_id: str,
    task_id: str,
    authority_sha256: Mapping[str, str],
    plan_sha256: str,
) -> E0RegistryView:
    destination = Path(root)
    if destination.exists():
        raise FileExistsError(f"E0 registry already exists: {destination}")
    destination.mkdir(parents=True)
    (destination / "cases").mkdir()
    registry = {
        "schema_version": "geophase_phase1_e0_registry_v1",
        "run_id": run_id,
        "task_id": task_id,
        "state": "PREPARED",
        "validity": "pending",
        "scientific_vote": False,
        "formal_execution_count": 0,
        "invalid_attempt_count": 0,
        "authority_sha256": dict(sorted(authority_sha256.items())),
        "plan_sha256": plan_sha256,
        "created_utc": _utc_now(),
        "updated_utc": _utc_now(),
    }
    atomic_json(_registry_path(destination), registry)
    _append_journal_event(
        destination,
        {"event": "REGISTRY_PREPARED", "state": "PREPARED", "details": {}},
    )
    return load_registry(destination)


def load_registry(root: Path) -> E0RegistryView:
    base = Path(root)
    registry_path = _registry_path(base)
    if not registry_path.is_file():
        raise E0ContractError("E0 registry is missing")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != "geophase_phase1_e0_registry_v1":
        raise E0ContractError("E0 registry schema changed")
    events: list[dict[str, Any]] = []
    previous: str | None = None
    journal = base / "journal.jsonl"
    if journal.is_file():
        for expected, line in enumerate(journal.read_text(encoding="utf-8").splitlines()):
            event = json.loads(line)
            digest = str(event.pop("event_sha256", ""))
            if event.get("sequence") != expected:
                raise E0ContractError("E0 journal sequence is not contiguous")
            if event.get("previous_event_sha256") != previous:
                raise E0ContractError("E0 journal hash chain is broken")
            if canonical_sha256(event) != digest:
                raise E0ContractError("E0 journal event hash mismatch")
            event["event_sha256"] = digest
            events.append(event)
            previous = digest
    if not events:
        raise E0ContractError("E0 journal is empty")
    cases: dict[str, Path] = {}
    for path in sorted((base / "cases").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        digest = str(payload.get("record_sha256", ""))
        unhashed = {key: value for key, value in payload.items() if key != "record_sha256"}
        if canonical_sha256(unhashed) != digest or path.stem != digest:
            raise E0ContractError("E0 case record hash or filename mismatch")
        case_id = str(payload.get("case_id", ""))
        if not case_id or case_id in cases:
            raise E0ContractError("E0 case identity is missing or duplicated")
        cases[case_id] = path
    return E0RegistryView(base, registry, tuple(events), cases)


def _set_registry_state(
    root: Path,
    *,
    state: str,
    validity: str,
    scientific_vote: bool,
    details: Mapping[str, Any],
) -> E0RegistryView:
    view = load_registry(root)
    if view.state in _TERMINAL_STATES:
        raise E0ContractError("terminal E0 registry cannot transition")
    registry = dict(view.registry)
    registry.update(
        {
            "state": state,
            "validity": validity,
            "scientific_vote": bool(scientific_vote),
            "updated_utc": _utc_now(),
        }
    )
    if state == "INVALID_E0_EXECUTION":
        registry["invalid_attempt_count"] = int(
            registry.get("invalid_attempt_count", 0)
        ) + 1
    atomic_json(_registry_path(root), registry)
    _append_journal_event(
        root,
        {"event": "STATE_TRANSITION", "state": state, "details": dict(details)},
    )
    return load_registry(root)


def publish_case(root: Path, *, case_id: str, payload: Mapping[str, Any]) -> Path:
    view = load_registry(root)
    if view.state != "RUNNING":
        raise E0ContractError("E0 case publication requires RUNNING state")
    if case_id in view.published_cases:
        raise E0ContractError(f"E0 case already published: {case_id}")
    record = {
        "schema_version": "geophase_phase1_e0_case_v1",
        "case_id": case_id,
        "payload": dict(payload),
    }
    digest = canonical_sha256(record)
    destination = Path(root) / "cases" / f"{digest}.json"
    atomic_json(destination, {**record, "record_sha256": digest})
    _append_journal_event(
        root,
        {
            "event": "CASE_PUBLISHED",
            "state": "RUNNING",
            "details": {"case_id": case_id, "record_sha256": digest},
        },
    )
    return destination


def build_preflight_plan(config: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    profile = config["preflight"]["profile_matrix"]
    levels = tuple(int(value) for value in profile["spatial_levels"])
    states = tuple(str(value) for value in profile["state_ids"])
    protocols = {str(key): dict(value) for key, value in profile["protocol_by_state"].items()}
    if levels != (1, 2, 4):
        raise E0ContractError("E0 profile levels must be exactly L1/L2/L4")
    if states != ("equilibrium", "legal_critical", "high_conductive"):
        raise E0ContractError("E0 deterministic state order changed")
    rows: list[dict[str, Any]] = []
    index = 0
    for level in levels:
        for state_id in states:
            protocol = protocols[state_id]
            for interval_class in ("base", "floor"):
                row = {
                    "plan_index": index,
                    "sample_id": f"PRE-E0-STEP-L{level}-{state_id}-{interval_class}",
                    "sample_kind": "single_interval",
                    "spatial_level": level,
                    "state_id": state_id,
                    "interval_class": interval_class,
                    "protocol": protocol["protocol_id"],
                    "protocol_V_scale_V": float(protocol["voltage_V"]),
                }
                row["input_sha256"] = canonical_sha256(row)
                rows.append(row)
                index += 1
    for level in levels:
        for state_id in states:
            protocol = protocols[state_id]
            row = {
                "plan_index": index,
                "sample_id": f"PRE-E0-TRAJECTORY-L{level}-{state_id}",
                "sample_kind": "short_trajectory",
                "spatial_level": level,
                "state_id": state_id,
                "protocol": protocol["protocol_id"],
                "protocol_V_scale_V": float(protocol["voltage_V"]),
            }
            row["input_sha256"] = canonical_sha256(row)
            rows.append(row)
            index += 1
    if len(rows) != 27 or [row["plan_index"] for row in rows] != list(range(27)):
        raise E0ContractError("E0 profile plan is not the frozen 18+9 sequence")
    return tuple(rows)


def authority_hashes(root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    workspace = Path(root)
    hashes: dict[str, str] = {}
    for item in config["authority"]["files"]:
        path = workspace / str(item["path"])
        expected = str(item["sha256"])
        if not path.is_file() or not _HEX64.fullmatch(expected):
            raise E0ContractError(f"authority file is missing or malformed: {path}")
        observed = sha256_file(path)
        if observed != expected:
            raise E0ContractError(f"authority hash drift: {item['path']}")
        hashes[str(item["path"])] = observed
    return hashes


def _remaining(deadline: float) -> float:
    value = deadline - perf_counter()
    if value <= 0.0:
        raise TimeoutError("E0 preflight wall-clock budget exhausted")
    return value


def execute_preflight(
    *,
    root: Path,
    config: Mapping[str, Any],
    output_root: Path,
    adapter: E0Adapter,
    foundation_runner: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Execute or resume the single E0 preflight under its immutable run ID."""

    hashes = authority_hashes(root, config)
    plan = build_preflight_plan(config)
    plan_digest = canonical_sha256(plan)
    run_id = str(config["preflight"]["run_id"])
    registry_root = Path(output_root) / run_id
    if not registry_root.exists():
        view = create_registry(
            registry_root,
            run_id=run_id,
            task_id=str(config["task_id"]),
            authority_sha256=hashes,
            plan_sha256=plan_digest,
        )
    else:
        view = load_registry(registry_root)
        if view.registry["authority_sha256"] != dict(sorted(hashes.items())):
            raise E0ContractError("resume authority hashes differ from registry")
        if view.registry["plan_sha256"] != plan_digest:
            raise E0ContractError("resume plan differs from registry")
        if view.state in _TERMINAL_STATES:
            raise E0ContractError("E0 preflight terminal result cannot be rerun")
    if view.state == "PREPARED":
        _set_registry_state(
            registry_root,
            state="RUNNING",
            validity="pending",
            scientific_vote=False,
            details={"resume": False},
        )
    elif view.state == "INTERRUPTED_RESUMABLE":
        _set_registry_state(
            registry_root,
            state="RUNNING",
            validity="pending",
            scientific_vote=False,
            details={"resume": True},
        )
    elif view.state != "RUNNING":
        raise E0ContractError(f"unsupported E0 preflight state: {view.state}")

    started = perf_counter()
    deadline = started + float(config["budgets"]["preflight_wall_clock_s"])
    case_payloads: dict[str, dict[str, Any]] = {}
    for case_id, path in load_registry(registry_root).published_cases.items():
        case_payloads[case_id] = json.loads(path.read_text(encoding="utf-8"))["payload"]

    def run_once(case_id: str, callback: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
        if case_id in case_payloads:
            return case_payloads[case_id]
        _remaining(deadline)
        payload = dict(callback())
        canonical_bytes(payload)
        publish_case(registry_root, case_id=case_id, payload=payload)
        case_payloads[case_id] = payload
        return payload

    try:
        foundation = run_once("PRE-E0-FOUNDATION", foundation_runner)
        if foundation.get("status") != "PASS":
            return _finalize_preflight(
                registry_root,
                state="E0_IMPLEMENTATION_FAIL",
                validity="valid",
                details={"first_failure": "PRE-E0-FOUNDATION"},
                payloads=case_payloads,
                started=started,
            )
        rss = run_once("PRE-E0-WORKER-RSS", lambda: adapter.measure_worker_rss())
        environment = run_once("PRE-E0-ENVIRONMENT", lambda: adapter.measure_environment())
        c1 = run_once("PRE-E0-C1", lambda: adapter.run_c1(_remaining(deadline)))
        if c1.get("status") != "PASS":
            return _finalize_preflight(
                registry_root,
                state="E0_IMPLEMENTATION_FAIL",
                validity="valid",
                details={"first_failure": "PRE-E0-C1"},
                payloads=case_payloads,
                started=started,
            )
        c2 = run_once("PRE-E0-C2", lambda: adapter.run_c2(_remaining(deadline)))
        if c2.get("status") != "PASS":
            return _finalize_preflight(
                registry_root,
                state="E0_IMPLEMENTATION_FAIL",
                validity="valid",
                details={"first_failure": "PRE-E0-C2"},
                payloads=case_payloads,
                started=started,
            )
        profile_results: list[dict[str, Any]] = []
        for row in plan:
            sample = run_once(
                str(row["sample_id"]),
                lambda row=row: adapter.run_profile_sample(row),
            )
            profile_results.append(sample)
            if sample.get("status") != "PASS":
                return _finalize_preflight(
                    registry_root,
                    state="E0_IMPLEMENTATION_FAIL",
                    validity="valid",
                    details={"first_failure": row["sample_id"]},
                    payloads=case_payloads,
                    started=started,
                )
        workers = int(environment.get("physical_core_count") or 1)
        forecast = run_once(
            "PRE-E0-FORECAST",
            lambda: adapter.build_forecast(
                tuple(profile_results), c2, max(1, workers)
            ),
        )
        gates = config["preflight"]["performance_gates"]
        performance_pass = bool(
            float(forecast["unreserved_LPT_makespan_s"])
            <= float(gates["unreserved_LPT_makespan_s_max"])
            and float(forecast["safety_margin_LPT_makespan_s"])
            <= float(gates["safety_margin_LPT_makespan_s_max"])
            and bool(forecast["RSS_gate_pass"])
            and bool(forecast["disk_gate_pass"])
        )
        if not performance_pass:
            return _finalize_preflight(
                registry_root,
                state="E0_PERFORMANCE_ONLY_NO_GO",
                validity="valid_readiness_provenance",
                details={"first_failure": "PRE-E0-FORECAST"},
                payloads=case_payloads,
                started=started,
            )
        return _finalize_preflight(
            registry_root,
            state="PREFLIGHT_PASS",
            validity="valid",
            details={"first_failure": None},
            payloads=case_payloads,
            started=started,
        )
    except TimeoutError as error:
        return _finalize_preflight(
            registry_root,
            state="E0_PERFORMANCE_ONLY_NO_GO",
            validity="valid_readiness_provenance",
            details={"first_failure": "wall_clock_budget", "error": str(error)},
            payloads=case_payloads,
            started=started,
        )
    except (
        E0ContractError,
        FloatingPointError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        return _finalize_preflight(
            registry_root,
            state="INVALID_E0_EXECUTION",
            validity="invalid",
            details={"error_class": type(error).__name__, "error": str(error)},
            payloads=case_payloads,
            started=started,
        )


def _finalize_preflight(
    root: Path,
    *,
    state: str,
    validity: str,
    details: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    started: float,
) -> dict[str, Any]:
    summary = {
        "schema_version": "geophase_phase1_e0_preflight_summary_v1",
        "terminal_state": state,
        "validity": validity,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "completed_case_count": len(payloads),
        "completed_case_ids": sorted(payloads),
        "wall_clock_s": perf_counter() - started,
        **dict(details),
    }
    atomic_json(Path(root) / "preflight_summary.json", summary)
    _set_registry_state(
        root,
        state=state,
        validity=validity,
        scientific_vote=False,
        details={"summary_sha256": sha256_file(Path(root) / "preflight_summary.json")},
    )
    return summary


def mark_interrupted(root: Path, *, reason: str) -> E0RegistryView:
    view = load_registry(root)
    if view.state != "RUNNING":
        raise E0ContractError("only a running E0 registry can be interrupted")
    return _set_registry_state(
        root,
        state="INTERRUPTED_RESUMABLE",
        validity="invalid_interruption",
        scientific_vote=False,
        details={"reason": reason},
    )


def finalize_external_stop(
    root: Path,
    *,
    state: str,
    validity: str,
    reason: str,
    wall_clock_s: float,
) -> dict[str, Any]:
    if state not in {"INVALID_E0_EXECUTION", "E0_PERFORMANCE_ONLY_NO_GO"}:
        raise ValueError("external E0 stop has an invalid terminal state")
    view = load_registry(root)
    if view.state != "RUNNING":
        raise E0ContractError("external E0 stop requires a running registry")
    summary = {
        "schema_version": "geophase_phase1_e0_preflight_summary_v1",
        "terminal_state": state,
        "validity": validity,
        "scientific_vote": False,
        "formal_execution_count": 0,
        "completed_case_count": len(view.published_cases),
        "completed_case_ids": sorted(view.published_cases),
        "wall_clock_s": float(wall_clock_s),
        "first_failure": "external_supervisor",
        "error": reason,
    }
    atomic_json(Path(root) / "preflight_summary.json", summary)
    _set_registry_state(
        root,
        state=state,
        validity=validity,
        scientific_vote=False,
        details={"summary_sha256": sha256_file(Path(root) / "preflight_summary.json")},
    )
    return summary


__all__ = [
    "E0Adapter",
    "E0ContractError",
    "E0RegistryView",
    "atomic_json",
    "authority_hashes",
    "build_preflight_plan",
    "canonical_bytes",
    "canonical_sha256",
    "create_registry",
    "execute_preflight",
    "finalize_external_stop",
    "load_registry",
    "load_yaml",
    "mark_interrupted",
    "publish_case",
    "sha256_file",
]

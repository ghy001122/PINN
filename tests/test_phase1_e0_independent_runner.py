from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from pinnpcm.evaluation.geophase_phase1_e0_runner import (
    E0ContractError,
    build_preflight_plan,
    canonical_sha256,
    create_registry,
    execute_preflight,
    load_registry,
    mark_interrupted,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "geophase_phase1_e0_execution_v1.yaml"
RUNNER_PATH = ROOT / "src" / "pinnpcm" / "evaluation" / "geophase_phase1_e0_runner.py"
CLI_PATH = ROOT / "scripts" / "run_geophase_phase1_e0.py"
AUTHORIZATION_PATH = (
    ROOT / "outputs" / "tables" / "geophase_phase1_e0" / "execution_authorization.json"
)
TERMINAL_RUN_ROOT = (
    ROOT
    / "outputs"
    / "tables"
    / "geophase_phase1_e0"
    / "runs"
    / "E0-PREFLIGHT-20260801-V1"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _config(tmp_path: Path) -> dict[str, Any]:
    authority = tmp_path / "authority.txt"
    authority.write_text("locked\n", encoding="utf-8")
    return {
        "task_id": "TEST-E0",
        "authority": {
            "files": [
                {
                    "path": "authority.txt",
                    "sha256": _sha256(authority),
                }
            ]
        },
        "budgets": {"preflight_wall_clock_s": 60.0},
        "preflight": {
            "run_id": "PRE-E0-TEST",
            "profile_matrix": {
                "spatial_levels": [1, 2, 4],
                "state_ids": ["equilibrium", "legal_critical", "high_conductive"],
                "protocol_by_state": {
                    "equilibrium": {"protocol_id": "zero_drive", "voltage_V": 1.0},
                    "legal_critical": {
                        "protocol_id": "transition_probe_12p5V",
                        "voltage_V": 12.5,
                    },
                    "high_conductive": {
                        "protocol_id": "high_bias_lock_15p8V",
                        "voltage_V": 15.8,
                    },
                },
            },
            "performance_gates": {
                "unreserved_LPT_makespan_s_max": 14400.0,
                "safety_margin_LPT_makespan_s_max": 11520.0,
            },
        },
    }


class StubAdapter:
    def __init__(self, *, c1_status: str = "PASS", interrupt_rss: bool = False) -> None:
        self.c1_status = c1_status
        self.interrupt_rss = interrupt_rss
        self.profile_calls: list[int] = []

    def measure_worker_rss(self) -> Mapping[str, Any]:
        if self.interrupt_rss:
            raise KeyboardInterrupt("injected interruption")
        return {"status": "PASS", "measured_peak_worker_RSS_bytes": 1024}

    def measure_environment(self) -> Mapping[str, Any]:
        return {"status": "PASS", "physical_core_count": 2}

    def run_c1(self, remaining_s: float) -> Mapping[str, Any]:
        assert remaining_s > 0.0
        return {"status": self.c1_status}

    def run_c2(self, remaining_s: float) -> Mapping[str, Any]:
        assert remaining_s > 0.0
        return {"status": "PASS", "forecast_sample_row": {"status": "pass"}}

    def run_profile_sample(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        self.profile_calls.append(int(plan["plan_index"]))
        return {
            "status": "PASS",
            "sample_kind": plan["sample_kind"],
            "spatial_level": plan["spatial_level"],
            "state_id": plan["state_id"],
        }

    def build_forecast(
        self,
        samples: tuple[Mapping[str, Any], ...],
        c2: Mapping[str, Any],
        worker_count: int,
    ) -> Mapping[str, Any]:
        assert len(samples) == 27
        assert c2["status"] == "PASS"
        assert worker_count == 2
        return {
            "unreserved_LPT_makespan_s": 100.0,
            "safety_margin_LPT_makespan_s": 120.0,
            "RSS_gate_pass": True,
            "disk_gate_pass": True,
        }


def _foundation() -> Mapping[str, Any]:
    return {"status": "PASS", "scientific_vote": False}


def test_preregistered_execution_contract_freezes_budget_OOD_and_rescue() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["budgets"]["preflight_wall_clock_s"] == 7200
    assert config["budgets"]["formal_campaign_wall_clock_s"] == 14400
    assert config["budgets"]["C01_total_aggregate_GPU_hours_max"] == 72
    assert config["budgets"]["phase2_data_and_evaluation_cpu_wall_hours_max"] == 24
    assert config["formal_campaign"]["evaluation_items"] == 63
    assert config["formal_campaign"]["unique_execution_units"] == 60
    assert config["formal_campaign"]["legal_reuses"] == 3
    assert config["C01"]["nominal_contact_overlap_nm"] == 20
    assert config["C01"]["geometry_OOD_contact_overlap_nm"] == [10, 30]
    assert config["C01"]["protocol_OOD"] == "pulse_12p5V"
    assert len(config["C01"]["paired_seeds"]) == 5
    assert len(set(config["C01"]["paired_seeds"])) == 5
    assert config["C01"]["scientific_rescue_choose_exactly_one"] is True


def test_execution_authorization_binds_runner_CLI_and_config_bytes() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    authorization = json.loads(AUTHORIZATION_PATH.read_text(encoding="utf-8"))

    assert authorization["config_sha256"] == _sha256(CONFIG_PATH)
    assert authorization["runner_source_sha256"] == _sha256(RUNNER_PATH)
    assert authorization["CLI_source_sha256"] == _sha256(CLI_PATH)
    assert authorization["code_anchor_commit"] == config["authorization"][
        "code_anchor_commit"
    ]
    assert authorization["formal_execution_count"] == 0


def test_terminal_preflight_evidence_is_invalid_and_has_no_scientific_vote() -> None:
    authorization = json.loads(AUTHORIZATION_PATH.read_text(encoding="utf-8"))
    summary = json.loads(
        (TERMINAL_RUN_ROOT / "preflight_summary.json").read_text(encoding="utf-8")
    )
    view = load_registry(TERMINAL_RUN_ROOT)

    assert view.state == "INVALID_E0_EXECUTION"
    assert view.registry["validity"] == "invalid"
    assert view.registry["scientific_vote"] is False
    assert view.published_cases == {}
    assert len(view.events) == 3
    assert summary["completed_case_count"] == 0
    assert summary["formal_execution_count"] == 0
    assert summary["scientific_vote"] is False
    assert summary["error_class"] == "TypeError"
    assert summary["error"] == "Object of type bool_ is not JSON serializable"
    assert authorization["preflight_invocation_count"] == 2
    assert authorization["preflight_invalid_attempt_count"] == 2
    assert authorization["runner_implementation_repair_count"] == 1
    assert authorization["runner_implementation_repair_limit"] == 1


def test_preflight_plan_is_exact_18_plus_9_without_reordering() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    plan = build_preflight_plan(config)

    assert len(plan) == 27
    assert [row["plan_index"] for row in plan] == list(range(27))
    assert sum(row["sample_kind"] == "single_interval" for row in plan) == 18
    assert sum(row["sample_kind"] == "short_trajectory" for row in plan) == 9
    assert len({row["sample_id"] for row in plan}) == 27
    for row in plan:
        unhashed = {key: value for key, value in row.items() if key != "input_sha256"}
        assert row["input_sha256"] == canonical_sha256(unhashed)


def test_runner_does_not_import_historical_equivalence_or_readiness_entrypoints() -> None:
    for path in (RUNNER_PATH, CLI_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert not any("equivalence" in item for item in imported)
        assert not any("runtime_readiness" in item for item in imported)
        assert not any("embedded_controller_readiness" in item for item in imported)


def test_preflight_worker_dispatches_into_independent_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("phase1_e0_cli_regression", CLI_PATH)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    config = {
        "authority": {
            "files": [
                {
                    "path": "optimized_candidate_identity.json",
                    "sha256": "candidate-identity",
                }
            ]
        }
    }
    sentinel = {"terminal_state": "PREFLIGHT_PASS"}
    captured: dict[str, Any] = {}

    monkeypatch.setattr(cli, "_apply_single_thread_environment", lambda: None)
    monkeypatch.setattr(cli, "load_yaml", lambda _path: config)
    monkeypatch.setattr(cli, "_validate_execution_anchor", lambda _config: {})

    def fake_execute_preflight(**kwargs: Any) -> dict[str, str]:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(cli, "execute_preflight", fake_execute_preflight)
    result = cli.run_preflight_worker()

    assert result is sentinel
    assert captured["root"] == cli.ROOT
    assert captured["config"] is config
    assert captured["output_root"] == cli.OUTPUT_ROOT
    assert captured["adapter"]._candidate_identity_sha256 == "candidate-identity"
    assert captured["foundation_runner"] is cli._foundation_checks


def test_stubbed_preflight_pass_requires_every_explicit_profile_case(tmp_path: Path) -> None:
    config = _config(tmp_path)
    adapter = StubAdapter()
    summary = execute_preflight(
        root=tmp_path,
        config=config,
        output_root=tmp_path / "outputs",
        adapter=adapter,
        foundation_runner=_foundation,
    )

    assert summary["terminal_state"] == "PREFLIGHT_PASS"
    assert summary["validity"] == "valid"
    assert summary["scientific_vote"] is False
    assert summary["formal_execution_count"] == 0
    assert adapter.profile_calls == list(range(27))
    view = load_registry(tmp_path / "outputs" / "PRE-E0-TEST")
    assert view.state == "PREFLIGHT_PASS"
    assert len(view.published_cases) == 33
    with pytest.raises(E0ContractError, match="cannot be rerun"):
        execute_preflight(
            root=tmp_path,
            config=config,
            output_root=tmp_path / "outputs",
            adapter=StubAdapter(),
            foundation_runner=_foundation,
        )


def test_interrupted_run_resumes_same_registry_without_republishing_cases(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    registry = tmp_path / "outputs" / "PRE-E0-TEST"
    with pytest.raises(KeyboardInterrupt):
        execute_preflight(
            root=tmp_path,
            config=config,
            output_root=tmp_path / "outputs",
            adapter=StubAdapter(interrupt_rss=True),
            foundation_runner=_foundation,
        )
    before = load_registry(registry)
    assert set(before.published_cases) == {"PRE-E0-FOUNDATION"}
    mark_interrupted(registry, reason="injected process interruption")

    adapter = StubAdapter()
    summary = execute_preflight(
        root=tmp_path,
        config=config,
        output_root=tmp_path / "outputs",
        adapter=adapter,
        foundation_runner=lambda: pytest.fail("published foundation was rerun"),
    )
    assert summary["terminal_state"] == "PREFLIGHT_PASS"
    assert load_registry(registry).registry["run_id"] == "PRE-E0-TEST"


def test_valid_c1_failure_blocks_profile_and_formal_vote(tmp_path: Path) -> None:
    config = _config(tmp_path)
    adapter = StubAdapter(c1_status="FAIL")
    summary = execute_preflight(
        root=tmp_path,
        config=config,
        output_root=tmp_path / "outputs",
        adapter=adapter,
        foundation_runner=_foundation,
    )

    assert summary["terminal_state"] == "E0_IMPLEMENTATION_FAIL"
    assert summary["validity"] == "valid"
    assert summary["scientific_vote"] is False
    assert summary["first_failure"] == "PRE-E0-C1"
    assert adapter.profile_calls == []


def test_journal_and_content_addressed_case_tampering_fail_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    execute_preflight(
        root=tmp_path,
        config=config,
        output_root=tmp_path / "outputs",
        adapter=StubAdapter(),
        foundation_runner=_foundation,
    )
    registry = tmp_path / "outputs" / "PRE-E0-TEST"
    case = next((registry / "cases").glob("*.json"))
    payload = json.loads(case.read_text(encoding="utf-8"))
    payload["payload"]["tampered"] = True
    case.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(E0ContractError, match="hash or filename mismatch"):
        load_registry(registry)


def test_create_registry_rejects_duplicate_identity(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    create_registry(
        root,
        run_id="PRE-E0-ONLY",
        task_id="TEST",
        authority_sha256={"x": "a" * 64},
        plan_sha256="b" * 64,
    )
    with pytest.raises(FileExistsError):
        create_registry(
            root,
            run_id="PRE-E0-ONLY",
            task_id="TEST",
            authority_sha256={"x": "a" * 64},
            plan_sha256="b" * 64,
        )

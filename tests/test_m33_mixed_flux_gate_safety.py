"""Fail-closed protocol tests for M33."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import yaml


def _config() -> dict:
    return yaml.safe_load(Path("configs/m33_feasibility_first_mixed_flux.yaml").read_text(encoding="utf-8"))


def test_single_route_budget_and_gate_contract_are_locked() -> None:
    config = _config()
    training = config["training"]
    assert training["seed"] == 20260715
    assert training["optimizer"] == "Adam"
    assert training["total_steps"] == 1500
    assert training["total_steps"] <= 1.25 * config["baseline_contract"]["adam_steps"]
    assert training["seed_expansion"] == "forbidden"
    assert training["strong_wolfe_lbfgs"] == "forbidden"
    assert training["port_labels"] == "forbidden"
    assert training["hidden_field_labels"] == "forbidden"
    assert config["result_gates"]["all_individual_gates_required"] is True
    assert config["result_gates"]["port_full_trace_nrmse95_max"] == 0.10
    assert config["result_gates"]["residual_rms_max"] == 0.01
    assert config["result_gates"]["interface_flux_rms_max"] == 0.05
    assert config["result_gates"]["global_energy_imbalance_max"] == 0.05
    assert config["result_gates"]["defect_mass_ledger_max"] == 0.01


def test_training_implementation_has_no_label_or_optimizer_search_path() -> None:
    source = Path("scripts/train_m33_mixed_flux.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "LBFGS" not in source
    assert "AdamW" not in source
    assert "port_target" not in names
    assert "field_target" not in names
    assert "expansion_seeds" not in source
    assert "grid_search" not in source
    assert "expected_preflight_only_status" in source
    assert "worktree_allowed = status_lines == [expected_preflight_status]" in source


def test_summary_schema_requires_fail_closed_claim_fields() -> None:
    schema = json.loads(Path("docs/schemas/m33_mixed_flux_summary_v1.schema.json").read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert {"preflight_all_pass", "training_executed", "gates", "status", "positive_forward_claim_allowed"} <= required
    assert schema["properties"]["status"]["enum"] == ["qualified_supported", "failed_but_informative"]


def test_preregistration_and_results_are_separate_artifacts() -> None:
    config = _config()
    assert config["outputs"]["preregistration"] != config["outputs"]["preflight"]
    assert config["outputs"]["preregistration"] != config["outputs"]["final_summary"]
    prereg_path = Path(config["outputs"]["preregistration"])
    if prereg_path.exists():
        prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
        assert prereg["status"] == "locked_before_preflight_and_training"
        assert "metrics" not in prereg

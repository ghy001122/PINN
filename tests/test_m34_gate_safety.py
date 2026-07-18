"""Fail-closed controls for M34 and its conditional corrected run."""

from __future__ import annotations

import ast
from pathlib import Path

import yaml


def _config() -> dict:
    return yaml.safe_load(Path("configs/m34_optimization_contract_audit.yaml").read_text(encoding="utf-8"))


def test_corrected_run_is_single_seed_bounded_and_label_free() -> None:
    config = _config()
    run = config["corrected_run"]
    assert run["seed"] == 20260715
    assert run["total_steps"] == 1500
    assert sum(stage["steps"] for stage in run["causal_schedule"]) == 1500
    assert run["dtype"] == "float64"
    assert run["constraint_contract"] == "stagewise_signed_vector_equality_alm"
    assert run["hidden_field_labels"] == "forbidden"
    assert run["port_labels"] == "forbidden"
    assert run["optimizer_search"] == "forbidden"
    assert run["seed_expansion"] == "forbidden"
    assert config["frozen_inputs"]["sealed_13v_access"] == "forbidden"
    assert len(config["authorization_conditions"]) == 9


def test_training_source_has_no_hidden_label_or_search_path() -> None:
    source = Path("scripts/train_m34_corrected_mixed_flux.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "field_target" not in names
    assert "port_target" not in names
    assert "LBFGS" not in source
    assert "grid_search" not in source
    assert "corrected_training_authorized" in source
    assert "all_nine_conditions" in source


def test_historical_outputs_are_inputs_not_write_targets() -> None:
    config = _config()
    historical = set(config["frozen_inputs"].values())
    outputs = set(config["outputs"].values())
    assert historical.isdisjoint(outputs)
    assert all(not Path(path).name.startswith("m33_") for path in outputs)

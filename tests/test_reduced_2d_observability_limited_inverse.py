from __future__ import annotations

import math
from pathlib import Path

import yaml

from scripts.audit_reduced_2d_observability_limited_inverse import run_observability_audit


def test_reduced_2d_observability_limited_inverse_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/reduced_2d_observability_limited_inverse.yaml").read_text(encoding="utf-8"))
    cfg["nx"] = 12
    cfg["ny"] = 8
    cfg["nt"] = 10
    cfg["noise"] = [0.0]
    cfg["observation_count"] = [8]
    cfg["seeds"] = [2026, 2027]
    cfg["geometries"] = ["localized_hotspot"]
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["claim_gate_figure"] = str(tmp_path / "claim_gate.png")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_observability_audit(path)
    assert summary["all_finite_results"] is True
    assert isinstance(summary["terminal_only_failure_confirmed"], bool)
    assert summary["augmented_observation_2d_low_dim_inverse_allowed"] is True
    assert summary["full_2d_field_recovery_allowed"] is False
    assert summary["minimal_observation_protocol_for_reliable_2d_low_dim_inverse"] is not None
    for value in summary["median_error_by_observation_protocol"].values():
        assert math.isfinite(float(value))
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert "terminal-only" in summary["forbidden_overclaim"]

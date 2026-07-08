from __future__ import annotations

import math
from pathlib import Path

import yaml

from pinnpcm.experiments.port_physical_2d_inverse import run_port_physical_2d_inverse


def test_port_physical_2d_inverse_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/high_risk_claim_ladder.yaml").read_text(encoding="utf-8"))
    cfg["nx"] = 10
    cfg["ny"] = 7
    cfg["nt"] = 8
    cfg["port_physical_2d_steps"] = 2
    cfg["profiles"]["quick"]["geometry"] = ["uniform_strip"]
    cfg["profiles"]["quick"]["rank"] = [2]
    cfg["profiles"]["quick"]["transition_width"] = [0.2]
    cfg["profiles"]["quick"]["noise"] = [0.0]
    cfg["profiles"]["quick"]["seeds"] = [2026]
    cfg["port_physical_2d_outputs"] = {
        "summary_json": str(tmp_path / "summary.json"),
        "cases_csv": str(tmp_path / "cases.csv"),
        "error_by_protocol_figure": str(tmp_path / "error.png"),
        "anchor_placement_figure": str(tmp_path / "anchors.png"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_port_physical_2d_inverse(path, profile="quick")
    assert summary["actual_inverse_mode"] is True
    assert summary["uses_port_physical_observation"] is True
    assert summary["uses_phase_mean_as_terminal_observation"] is False
    assert summary["all_finite_results"] is True
    assert summary["num_cases"] == 10
    assert set(summary["loss_terms"]) == {"L_port_G", "L_sparse_anchor", "L_pde_T", "L_pde_m", "L_bounds", "L_smooth_time"}
    assert set(summary["basis_comparison"]) == {"analytic", "pod"}
    assert "port_plus_fisher_2pct" in summary["anchor_comparison"]
    assert summary["field_recovery_status"] in {"qualified_supported", "failed_but_informative", "forbidden"}
    for group in [summary["median_field_error_by_protocol"], summary["median_port_error_by_protocol"], summary["condition_number_by_protocol"]]:
        for value in group.values():
            assert math.isfinite(float(value))
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert Path(summary["outputs"]["error_by_protocol_figure"]).exists()
    assert Path(summary["outputs"]["anchor_placement_figure"]).exists()

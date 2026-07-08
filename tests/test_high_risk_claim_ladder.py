from __future__ import annotations

import math
from pathlib import Path

import yaml

from pinnpcm.experiments.high_risk_claim_ladder import load_config, run_high_risk_claim_ladder
from pinnpcm.experiments.high_risk_actual_inverse import run_high_risk_claim_ladder_actual_inverse


def test_high_risk_claim_ladder_quick_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/high_risk_claim_ladder.yaml").read_text(encoding="utf-8"))
    assert "quick" in cfg["profiles"]
    assert "extended" in cfg["profiles"]
    cfg["profiles"]["quick"]["geometry"] = ["uniform_strip", "localized_hotspot"]
    cfg["profiles"]["quick"]["rank"] = [2]
    cfg["profiles"]["quick"]["transition_width"] = [0.2, 0.05]
    cfg["profiles"]["quick"]["noise"] = [0.0]
    cfg["profiles"]["quick"]["seeds"] = [2026]
    cfg["outputs"] = {
        "summary_json": str(tmp_path / "summary.json"),
        "cases_csv": str(tmp_path / "cases.csv"),
        "hidden_field_ladder_figure": str(tmp_path / "ladder.png"),
        "observability_protocols_figure": str(tmp_path / "protocols.png"),
        "sensitivity_anchor_map_figure": str(tmp_path / "anchors.png"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_high_risk_claim_ladder(path, profile="quick")
    assert summary["all_finite_results"] is True
    assert summary["extended_profile_configured_only"] is True
    assert summary["num_cases"] == 28
    assert summary["terminal_only_full_field_status"] == "failed_but_informative"
    assert summary["2d_hidden_field_recovery_supported_level"] in {"qualified_supported", "forbidden"}
    assert "terminal_plus_dense_anchors_5pct" in summary["by_observation_protocol"]
    for stats in summary["by_observation_protocol"].values():
        assert math.isfinite(float(stats["median_field_error"]))
        assert math.isfinite(float(stats["median_param_error"]))
        assert "training_mode" in stats
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert Path(summary["outputs"]["sensitivity_anchor_map_figure"]).exists()


def test_high_risk_extended_profile_configured() -> None:
    cfg = load_config(Path("configs/high_risk_claim_ladder.yaml"))
    ext = cfg["profiles"]["extended"]
    assert set(["uniform_strip", "localized_hotspot", "defect_seeded_filament", "lateral_gradient"]).issubset(set(ext["geometry"]))
    assert set([2, 4, 8]).issubset(set(int(v) for v in ext["rank"]))
    assert 0.05 in [float(v) for v in ext["transition_width"]]



def test_high_risk_actual_inverse_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/high_risk_claim_ladder.yaml").read_text(encoding="utf-8"))
    cfg["nx"] = 12
    cfg["ny"] = 8
    cfg["nt"] = 10
    cfg["profiles"]["quick"]["geometry"] = ["uniform_strip", "localized_hotspot"]
    cfg["profiles"]["quick"]["rank"] = [2]
    cfg["profiles"]["quick"]["transition_width"] = [0.2]
    cfg["profiles"]["quick"]["noise"] = [0.0]
    cfg["profiles"]["quick"]["seeds"] = [2026]
    cfg["actual_inverse_outputs"] = {
        "summary_json": str(tmp_path / "actual_summary.json"),
        "cases_csv": str(tmp_path / "actual_cases.csv"),
        "error_by_protocol_figure": str(tmp_path / "actual_error.png"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_high_risk_claim_ladder_actual_inverse(path, profile="quick")
    assert summary["actual_inverse_mode"] is True
    assert summary["all_finite_results"] is True
    assert summary["num_cases"] == 8
    assert summary["terminal_only_field_status"] in {"failed_but_informative", "qualified_supported"}
    assert summary["full_grid_arbitrary_recovery_status"] == "forbidden"
    assert set(summary["loss_terms"]) == {"L_terminal", "L_anchor", "L_rank_prior", "L_smooth_time"}
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert Path(summary["outputs"]["error_by_protocol_figure"]).exists()
    for stats in summary["by_observation_protocol"].values():
        assert stats["actual_inverse_mode"] is True
        assert math.isfinite(float(stats["median_field_error"]))
        assert math.isfinite(float(stats["median_param_error"]))

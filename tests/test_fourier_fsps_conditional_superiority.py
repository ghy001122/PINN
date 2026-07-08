from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_fourier_fsps_conditional_superiority as audit


def test_fourier_fsps_conditional_superiority_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "GAIN_HEATMAP", tmp_path / "heatmap.png")
    cfg = {"fourier_fsps_conditional_superiority": {"geometry": ["uniform_strip"], "transition_width": [0.2, 0.05], "noise": [0.0], "seeds": [2026], "collocation_points": 16, "eval_points": 20, "direct_epochs": 1, "continuation_epochs": 1}}
    path = tmp_path / "config.yaml"
    import yaml
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = audit.run_fourier_fsps_conditional_superiority(path)
    assert summary["all_finite_results"] is True
    assert summary["is_actual_pinn_training"] is True
    assert summary["universal_superiority_status"] == "forbidden"
    assert summary["conditional_benefit_status"] in {"qualified_supported", "failed_but_informative"}
    assert "best_sharp_method" in summary
    for value in summary["sharp_regime_gain_over_vanilla"].values():
        assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()
    assert (tmp_path / "heatmap.png").exists()

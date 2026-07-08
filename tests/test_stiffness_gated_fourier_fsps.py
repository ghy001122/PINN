from __future__ import annotations

import math
from pathlib import Path

import yaml

import scripts.audit_stiffness_gated_fourier_fsps as audit


def test_stiffness_gated_fourier_fsps_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "GAIN_FIGURE", tmp_path / "gain.png")
    cfg = {
        "stiffness_gated_fourier_fsps": {
            "geometry": ["uniform_strip"],
            "transition_width": [0.2, 0.05],
            "noise": [0.0],
            "seeds": [2026],
            "collocation_points": 16,
            "eval_points": 20,
            "direct_epochs": 1,
            "continuation_epochs": 1,
            "chi_c": 2.0,
        }
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = audit.run_stiffness_gated_fourier_fsps(path)
    assert summary["all_finite_results"] is True
    assert summary["is_actual_pinn_training"] is True
    assert summary["universal_superiority_status"] == "forbidden"
    assert summary["stiffness_gated_hybrid_status"] in {"qualified_supported", "failed_but_informative", "forbidden"}
    assert "stiffness_gated_hybrid" in summary["sharp_gain_by_method"]
    assert "stiffness_gated_hybrid" in summary["smooth_degradation_by_method"]
    for group in [summary["sharp_gain_by_method"], summary["smooth_degradation_by_method"]]:
        for value in group.values():
            assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()
    assert (tmp_path / "gain.png").exists()

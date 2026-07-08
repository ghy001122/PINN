from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_integrated_stiffness_stl as audit


def test_integrated_stiffness_stl_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "ERROR_FIGURE", tmp_path / "error.png")
    monkeypatch.setattr(audit, "CONVERGENCE_FIGURE", tmp_path / "conv.png")
    monkeypatch.setattr(audit, "TRANSFER_FIGURE", tmp_path / "transfer.png")
    monkeypatch.setattr(audit, "GRADIENT_FIGURE", tmp_path / "gradient.png")
    monkeypatch.setattr(audit, "IMBALANCE_FIGURE", tmp_path / "imbalance.png")
    cfg = {
        "seeds": [2026],
        "noise": [0.0],
        "target_transition_width": 0.05,
        "hidden_dim": 10,
        "collocation_points": 16,
        "eval_points": 20,
        "direct_epochs": 2,
        "continuation_epochs": 1,
        "stl_low_epochs": 1,
        "stl_transfer_epochs": 1,
        "stl_unfreeze_epochs": 1,
        "lr": 0.02,
    }
    path = tmp_path / "config.yaml"
    path.write_text("integrated_stiffness_stl:\n" + "\n".join(f"  {k}: {v}" for k, v in cfg.items()), encoding="utf-8")
    summary = audit.run_integrated_stiffness_stl(path)
    assert summary["all_finite_results"] is True
    assert summary["actual_stiffness_pinn_training_completed"] is True
    assert summary["seiler_style_multi_head_transfer_implemented"] is True
    assert summary["full_stl_pinn_reproduction_status"] == "forbidden"
    assert "R_T" in summary["residuals"] and "R_m" in summary["residuals"]
    for value in summary["median_error_by_algorithm"].values():
        assert math.isfinite(float(value))
    for key in ["success_rate_by_algorithm", "median_gradient_spike_by_algorithm", "median_residual_imbalance_by_algorithm", "median_convergence_epoch_proxy_by_algorithm"]:
        assert key in summary
        for value in summary[key].values():
            assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "cases.csv").exists()
    assert (tmp_path / "transfer.png").exists()
    assert (tmp_path / "gradient.png").exists()
    assert (tmp_path / "imbalance.png").exists()

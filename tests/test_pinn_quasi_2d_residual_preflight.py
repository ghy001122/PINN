from __future__ import annotations

from pathlib import Path

import yaml

from scripts.audit_pinn_quasi_2d_residual_preflight import run_residual_preflight


def test_quasi_2d_residual_preflight_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/pinn_quasi_2d_residual_preflight.yaml").read_text(encoding="utf-8"))
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["num_points"] = 24
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_residual_preflight(path)
    assert summary["all_residuals_finite"] is True
    assert summary["boundary_losses_finite"] is True
    assert summary["terminal_current_integral_finite"] is True
    assert summary["whether_2d_inverse_claim_allowed"] is False
    assert Path(summary["outputs"]["summary_json"]).exists()

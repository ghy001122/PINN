from __future__ import annotations

import math
from pathlib import Path

import yaml

from scripts.audit_phase_transition_stiffness_continuation import run_stiffness_audit


def test_stiffness_continuation_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/phase_transition_stiffness_continuation_audit.yaml").read_text(encoding="utf-8"))
    cfg["transition_width"] = [4.0, 0.5]
    cfg["T_sw_delta_K"] = [1.0]
    cfg["seeds"] = [2026]
    cfg["num_points"] = 24
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_stiffness_audit(path)
    assert summary["all_finite_results"] is True
    assert summary["whether_stiffness_cliff_claim_supported"] is True
    assert summary["sharpest_width_with_finite_residuals"] == 0.5
    assert math.isfinite(summary["stiffness_cliff_ratio_sharpest_to_widest"])
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert "stiff transfer learning is fully reproduced" in summary["forbidden_claims"]

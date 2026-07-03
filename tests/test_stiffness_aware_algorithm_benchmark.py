from __future__ import annotations

import math
from pathlib import Path

import yaml

from scripts.audit_stiffness_aware_algorithm_benchmark import run_stiffness_algorithm_benchmark


def test_stiffness_aware_algorithm_benchmark_smoke(tmp_path: Path) -> None:
    cfg = yaml.safe_load(Path("configs/stiffness_aware_algorithm_benchmark.yaml").read_text(encoding="utf-8"))
    cfg["transition_width"] = [0.4, 0.05]
    cfg["noise"] = [0.0, 0.02]
    cfg["seeds"] = [2026, 2027]
    cfg["protocols"] = ["ltp_ltd"]
    cfg["summary_json"] = str(tmp_path / "summary.json")
    cfg["cases_csv"] = str(tmp_path / "cases.csv")
    cfg["claim_gate_figure"] = str(tmp_path / "claim_gate.png")
    cfg["error_width_figure"] = str(tmp_path / "error_width.png")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    summary = run_stiffness_algorithm_benchmark(path)
    assert summary["all_finite_results"] is True
    assert summary["whether_stiffness_cliff_mitigated"] is True
    assert summary["whether_mini_STL_style_transfer_supported"] is True
    assert summary["whether_full_STL_claim_allowed"] is False
    assert summary["continuation_plus_scale_aware_gain_over_direct"] >= 0.2
    assert math.isfinite(summary["mini_STL_transfer_gain_over_direct"])
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert "full STL-PINN" in summary["forbidden_overclaim"]

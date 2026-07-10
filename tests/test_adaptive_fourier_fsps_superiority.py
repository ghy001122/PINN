from __future__ import annotations

import math
from pathlib import Path

import scripts.audit_adaptive_fourier_fsps_superiority as audit


def test_adaptive_fourier_fsps_superiority_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audit, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(audit, "CASES_CSV", tmp_path / "cases.csv")
    monkeypatch.setattr(audit, "FIG_PARETO", tmp_path / "pareto.png")
    summary = audit.run_adaptive_fourier_fsps_superiority(geometries=["uniform_strip"], widths=[0.2, 0.05], noise_values=[0.0], seeds=[2026])
    assert summary["is_actual_autograd_training"] is True
    assert summary["universal_superiority_status"] == "forbidden"
    assert summary["adaptive_f_sps_status"] in {"qualified_supported", "failed_but_informative"}
    for group in [summary["sharp_gain_by_method"], summary["smooth_degradation_by_method"], summary["pareto_win_rate_by_method"]]:
        for value in group.values():
            assert math.isfinite(float(value))
    assert (tmp_path / "summary.json").exists()

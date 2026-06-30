from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from scripts.compare_gamma_sub_scalar_baselines import run_scalar_baseline_comparison

FROZEN_FILES = [Path("data/processed/gt_v1_acceptance/gt_triangle.npz"), Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz")]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_scalar_baseline_comparison_smoke(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    summary = run_scalar_baseline_comparison(output_csv=tmp_path / "comparison.csv", report_path=tmp_path / "report.md")
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["all_finite_results"] is True
    assert Path(summary["outputs"]["comparison_csv"]).exists()
    methods = {row["method"] for row in summary["rows"]}
    assert "candidate_grid_scalar_search" in methods
    assert "continuous_scalar_least_squares_refinement" in methods
    assert "existing_constrained_gamma_sub_workflow" in methods
    cases = {row["target_case"] for row in summary["rows"]}
    assert {"nominal_frozen", "offgrid_4p62e8"}.issubset(cases)
    for row in summary["rows"]:
        assert np.isfinite(float(row["relative_error"]))
        assert np.isfinite(float(row["objective_value"]))
        assert row["frozen_inputs_unchanged"] is True
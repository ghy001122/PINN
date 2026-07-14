from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.refine_gamma_sub_continuous import run_continuous_refinement


FROZEN_FILES = [
    Path("data/processed/gt_v1_acceptance/gt_triangle.npz"),
    Path("data/processed/gt_v1_acceptance/obs_triangle_sparse.npz"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_continuous_refinement_smoke_schema_and_resimulation(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    candidates = [4.0e8, 4.5e8, 5.0e8]
    true_gammas = [4.38e8, 4.62e8]
    summary = run_continuous_refinement(
        summary_path=tmp_path / "summary.json",
        cases_csv_path=tmp_path / "cases.csv",
        report_path=tmp_path / "report.md",
        true_gammas=true_gammas,
        observation_counts=[4, 8],
        noise_levels=[0.0, 0.02],
        gamma_candidates=candidates,
        nx=7,
        nt=24,
        maxiter=5,
        seed=2026,
    )
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert summary["offgrid_truths_excluded_from_candidate_grid"] is True
    assert summary["all_refinements_resimulated_non_grid"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["cases_csv"]).exists()
    assert Path(summary["outputs"]["report_md"]).exists()
    assert "synthetic numerical digital-twin" in summary["benchmark"]

    candidate_set = {round(value, 6) for value in candidates}
    assert all(round(value, 6) not in candidate_set for value in true_gammas)
    assert summary["num_cases"] == 8
    assert len(summary["rows"]) == 8

    for row in summary["rows"]:
        for key in [
            "nearest_grid_relative_error",
            "nearest_grid_objective_value",
            "continuous_refined_gamma_sub",
            "continuous_refined_relative_error",
            "continuous_refined_objective_value",
            "continuous_refined_G_loss",
            "continuous_refined_I_loss",
        ]:
            assert np.isfinite(float(row[key]))
        assert int(row["continuous_eval_count"]) > 0
        assert row["refinement_resimulated_non_grid"] is True
        simulated = [round(float(value), 6) for value in row["continuous_simulated_gamma_sub"]]
        assert any(value not in candidate_set for value in simulated)

    saved = json.loads(Path(summary["outputs"]["summary_json"]).read_text(encoding="utf-8"))
    assert saved["frozen_gt_hashes_before"] == saved["frozen_gt_hashes_after"]
    assert saved["all_refinements_resimulated_non_grid"] is True

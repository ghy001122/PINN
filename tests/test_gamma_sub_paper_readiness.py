from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.audit_gamma_sub_paper_readiness import run_paper_readiness_audit


PAPER_DOCS = [
    Path("docs/paper/model_hierarchy_and_claim_boundary.md"),
    Path("docs/paper/equation_variable_registry.md"),
    Path("docs/paper/experiment_to_figure_mapping.md"),
]
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


def test_paper_docs_exist_and_state_synthetic_boundary() -> None:
    for path in PAPER_DOCS:
        text = path.read_text(encoding="utf-8").lower()
        assert "synthetic" in text
        assert "numerical" in text
        assert "digital-twin" in text
    boundary = PAPER_DOCS[0].read_text(encoding="utf-8").lower()
    assert "forbidden claims" in boundary
    assert "not experimental data" in boundary


def test_paper_readiness_smoke_schema_and_frozen_hashes(tmp_path: Path) -> None:
    before = {str(path): _sha256(path) for path in FROZEN_FILES}
    summary = run_paper_readiness_audit(
        summary_path=tmp_path / "summary.json",
        obs_csv_path=tmp_path / "obs.csv",
        offgrid_csv_path=tmp_path / "offgrid.csv",
        report_path=tmp_path / "report.md",
        observation_counts=[4, 8],
        gamma_candidates=[3.0e8, 4.5e8, 6.0e8],
        offgrid_gamma=4.8e8,
        offgrid_n_obs=8,
        nx=7,
        nt=24,
    )
    after = {str(path): _sha256(path) for path in FROZEN_FILES}
    assert before == after
    assert summary["frozen_gt_unchanged"] is True
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["observation_sensitivity_csv"]).exists()
    assert Path(summary["outputs"]["offgrid_summary_csv"]).exists()
    assert Path(summary["outputs"]["report_md"]).exists()

    for key in [
        "benchmark",
        "scope",
        "offgrid",
        "observation_sensitivity",
        "most_dangerous_confounder",
        "offgrid_test_passed",
        "observation_sensitivity_passed",
        "frozen_gt_unchanged",
    ]:
        assert key in summary
    assert "synthetic numerical digital-twin" in summary["benchmark"]
    assert len(summary["observation_sensitivity"]) == 2

    offgrid = summary["offgrid"]
    for key in ["nearest_grid_relative_error", "refined_relative_error", "objective_value", "G_loss", "I_loss"]:
        assert np.isfinite(float(offgrid[key]))
    assert offgrid["success_flag"] is True

    for row in summary["observation_sensitivity"]:
        assert np.isfinite(float(row["nominal_relative_error"]))
        assert np.isfinite(float(row["worst_confounder_relative_error"]))
        assert row["n_obs"] in {4, 8}

    saved = json.loads(Path(summary["outputs"]["summary_json"]).read_text(encoding="utf-8"))
    assert saved["frozen_gt_hashes_before"] == saved["frozen_gt_hashes_after"]
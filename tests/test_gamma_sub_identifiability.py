from pathlib import Path

from scripts.audit_gamma_sub_confounding import run_confounding_audit
from scripts.invert_gamma_sub_with_mismatch import run_mismatch_inversion
from scripts.invert_gamma_sub_v0 import run_inversion
from scripts.scan_gamma_sub_identifiability import run_scan


def test_gamma_sub_scan_smoke(tmp_path: Path) -> None:
    summary = run_scan(
        summary_path=tmp_path / "tables" / "gamma_summary.json",
        figure_dir=tmp_path / "figures",
        gamma_values=[3.5e8, 4.5e8, 6.0e8],
        nx=7,
        nt=30,
        rtol=1.0e-5,
        atol=1.0e-7,
    )

    assert summary["target_gamma_sub"] == 4.5e8
    assert len(summary["scan"]) == 3
    assert "max_delta_T" in summary["local_log_sensitivity"]
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["sensitivity"]).exists()


def test_gamma_sub_inversion_smoke(tmp_path: Path) -> None:
    summary = run_inversion(
        summary_path=tmp_path / "tables" / "gamma_summary.json",
        figure_dir=tmp_path / "figures",
        initial_gammas=[3.0e8, 7.0e8],
        noise_levels=[0.0],
        nx=7,
        nt=30,
        rtol=1.0e-5,
        atol=1.0e-7,
        adam_steps=1,
        lbfgs_maxiter=1,
    )

    stability = summary["inversion"]["stability_summary"]
    assert "clean_best_gamma_sub" in stability
    assert "gamma_sub_stably_invertible" in stability
    assert Path(summary["outputs"]["objective_profile"]).exists()


def test_gamma_sub_confounding_smoke(tmp_path: Path) -> None:
    summary = run_confounding_audit(
        summary_path=tmp_path / "tables" / "confounding.json",
        ranking_path=tmp_path / "tables" / "ranking.csv",
        nx=7,
        nt=30,
        rtol=1.0e-5,
        atol=1.0e-7,
    )

    assert summary["interpretation"]["most_sensitive_parameter"]
    assert len(summary["sensitivity_ranking"]) == 5
    assert Path(summary["outputs"]["summary_json"]).exists()
    assert Path(summary["outputs"]["sensitivity_ranking_csv"]).exists()


def test_gamma_sub_mismatch_smoke(tmp_path: Path) -> None:
    summary = run_mismatch_inversion(
        summary_path=tmp_path / "tables" / "confounding.json",
        noise_levels=[0.0],
        nx=7,
        nt=30,
        rtol=1.0e-5,
        atol=1.0e-7,
        adam_steps=1,
        lbfgs_maxiter=1,
    )

    mismatch = summary["mismatch_inversion"]
    assert "summary" in mismatch
    assert len(mismatch["cases"]) >= 2
    assert "gamma_sub_reliable_under_tested_mismatch" in mismatch["summary"]

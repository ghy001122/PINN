from pathlib import Path

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

from pathlib import Path

from scripts.analyze_pinn_identifiability import analyze


def test_identifiability_analysis_outputs(tmp_path: Path) -> None:
    summary = analyze(
        input_path=Path("data/processed/gt_v1_acceptance/gt_triangle.npz"),
        table_dir=tmp_path / "tables",
        figure_dir=tmp_path / "figures",
        max_lag=2,
    )

    assert summary["n_time"] > 0
    assert summary["n_x"] > 0
    assert "G" in summary["terminal_to_field_correlations"]
    assert "m__sigma" in summary["hidden_field_correlations"]

    outputs = summary["outputs"]
    for key in [
        "summary_json",
        "correlation_csv",
        "correlation_heatmap",
        "spatial_sensitivity",
        "lag_correlation",
    ]:
        assert Path(outputs[key]).exists()

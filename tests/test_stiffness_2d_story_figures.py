from __future__ import annotations

import math
from pathlib import Path

from scripts.build_stiffness_2d_story_figures import build_figures


def test_stiffness_2d_story_figures_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    figure_dir = tmp_path / "figures"
    manifest = build_figures(figure_dir=figure_dir, manifest_path=manifest_path)
    assert manifest_path.exists()
    assert len(manifest["figures"]) == 5
    for fig in manifest["figures"]:
        path = Path(fig["path"])
        if not path.is_absolute():
            path = Path.cwd() / path
        assert path.exists()
        assert path.stat().st_size > 0
        assert "synthetic" in fig["label"]
        assert "not experimental" in fig["label"]
    assert manifest["stiffness_key_results"]["whether_stiffness_cliff_claim_supported"] is True
    assert manifest["stiffness_key_results"]["fourier_gain_not_uniform"] is True
    assert manifest["phase_field_key_results"]["full_field_anchor_not_sparse_port"] is True
    assert math.isfinite(float(manifest["phase_field_key_results"]["median_relative_error_M"]))
    assert manifest["quasi_2d_key_results"]["whether_2d_inverse_claim_allowed"] is False

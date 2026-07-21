"""Fast E1F evidence-schema and digitization tests before the formal vote."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from scripts.run_e1f_qiu_author_anchor import range_normalized_rmse


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/external/qiu_2024_thermal_neuristor/digitized_manifest.json"


def test_digitized_manifest_has_locked_semantics_and_finite_curves() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["raw_experimental_data"] is False
    assert manifest["independent_external_holdout"] is False
    assert manifest["same_paper_development_contamination_risk"] is True
    assert manifest["si_figure_s1_semantics_ambiguous"] is True
    assert len(manifest["curves"]) == 4
    for curve in manifest["curves"]:
        rows = list(
            csv.DictReader((ROOT / curve["csv_path"]).open("r", encoding="utf-8"))
        )
        assert len(rows) == int(curve["point_count"])
        times = np.asarray([float(row["time_us"]) for row in rows])
        assert np.isfinite(times).all()
        assert np.all(np.diff(times) > 0.0)
        assert curve["crop_png_sha256_not_committed"]


def test_range_normalized_rmse_is_zero_for_identity_and_positive_for_shift() -> None:
    reference = np.linspace(-2.0, 3.0, 51)
    assert range_normalized_rmse(reference, reference) == 0.0
    assert range_normalized_rmse(reference + 0.5, reference) > 0.0

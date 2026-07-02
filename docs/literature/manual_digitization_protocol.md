# Manual Digitization Protocol

All external curve data must be provenance-backed. Do not fabricate points.

1. Record source title, year, DOI or URL, figure/table id, axes units, and extraction method.
2. Digitize only if the axis scale and curve identity are unambiguous.
3. Save CSV files under `data/literature/curves/` using the schema required by `configs/literature_curve_ingestion.yaml`.
4. Re-run `scripts/ingest_literature_digitized_curves.py` and `scripts/fit_literature_phase_change_curves_v2.py`.
5. If no numeric provenance exists, keep the item in `data/literature/manual_digitization_queue.csv` and write only a blocked/no-fabrication limitation.

# Data Directory

This project separates data by provenance:

- `raw/`: user-provided or lab raw data.
- `external/`: digitized literature curves. Every file here must be documented in `docs/data_provenance.md`.
- `processed/`: generated synthetic benchmark data from scripts in this repository.

The default Ground Truth files are synthetic benchmark data for algorithm validation. They are not measured experimental data.

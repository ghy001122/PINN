# Data Provenance

This file must be updated whenever new raw, external, or processed data is added.

## `data/raw/`

Reserved for user-provided or lab raw data. No raw experimental data has been added in the first engineering version.

## `data/external/`

Reserved for digitized literature curves. Each file must include source paper, figure number, digitization method, date, and operator notes. No digitized literature data has been added in the first engineering version.

## `data/processed/`

Reserved for generated synthetic benchmark data. Files produced by `scripts/run_gt_v1.py` are literature-guided synthetic data for algorithm validation and must not be described as measured experimental data.

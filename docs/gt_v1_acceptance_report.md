# Ground Truth v1.1 Acceptance Report

This is an engineering acceptance record for the literature-guided synthetic Ground Truth benchmark. It is not manuscript text and must not be described as measured experimental data.

## Frozen Configs

- `configs/gt_v1_acceptance_triangle.yaml`
- `configs/gt_v1_acceptance_ltp_ltd.yaml`

## Acceptance Metrics

Triangle main protocol:

- `G_ratio`: 2.915301903395705
- `max_delta_T`: 8.750689766759194 K
- `max_abs_delta_c_v`: 0.00207390149033114
- `max_abs_delta_m`: 0.19195497789296317
- `approximate_iv_loop_area`: 6.241117083184925e-12

LTP/LTD auxiliary protocol:

- `G_ratio`: 1.5395743495626233
- `max_delta_T`: 3.454186084686455 K
- `max_abs_delta_c_v`: 0.0070076698138849675
- `max_abs_delta_m`: 0.07471220898868872
- `normalized_g_vs_pulse.png` confirms potentiation/depression bidirectional modulation.

## Acceptance Criteria

- Triangle protocol shows visible but not excessive I-V hysteresis.
- Triangle protocol gives conductance modulation near 3x.
- Temperature rise remains in the few-K to tens-of-K synthetic benchmark range.
- Defect, temperature, conductive-state, and conductivity fields show visible spatial structure.
- LTP/LTD protocol shows bidirectional potentiation/depression in normalized pulse conductance.

## Generated Data Paths

- `data/processed/gt_v1_acceptance/gt_triangle.npz`
- `data/processed/gt_v1_acceptance/obs_triangle_sparse.npz`
- `data/processed/gt_v1_acceptance/gt_ltp_ltd.npz`
- `data/processed/gt_v1_acceptance/obs_ltp_ltd_sparse.npz`
- `data/processed/gt_v1_acceptance/manifest.json`

## Metrics Paths

- `outputs/tables/gt_v1_acceptance/gt_triangle_metrics.json`
- `outputs/tables/gt_v1_acceptance/gt_ltp_ltd_metrics.json`

## Figure Paths

Triangle:

- `outputs/figures/gt_v1_acceptance/triangle/iv_curve.png`
- `outputs/figures/gt_v1_acceptance/triangle/g_vs_time.png`
- `outputs/figures/gt_v1_acceptance/triangle/delta_defect_map.png`
- `outputs/figures/gt_v1_acceptance/triangle/delta_temperature_map.png`
- `outputs/figures/gt_v1_acceptance/triangle/delta_m_map.png`
- `outputs/figures/gt_v1_acceptance/triangle/sigma_map.png`

LTP/LTD:

- `outputs/figures/gt_v1_acceptance/ltp_ltd/g_vs_time.png`
- `outputs/figures/gt_v1_acceptance/ltp_ltd/normalized_g_vs_pulse.png`
- `outputs/figures/gt_v1_acceptance/ltp_ltd/delta_defect_map.png`
- `outputs/figures/gt_v1_acceptance/ltp_ltd/delta_temperature_map.png`
- `outputs/figures/gt_v1_acceptance/ltp_ltd/delta_m_map.png`

## PINN Data Use

The PINN inverse-identification stage should use:

- Main training set: `data/processed/gt_v1_acceptance/gt_triangle.npz`
- Auxiliary generalization/check set: `data/processed/gt_v1_acceptance/gt_ltp_ltd.npz`

No PINN training is started by this acceptance freeze.

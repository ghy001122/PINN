# PINN inverse v2 F-SPS baseline report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this task: `59872397d4a9c5eadc8c0ba6f67bb0e28ace3b13`
- Implementation commit hash: `19b6f3c1cb2f4a1017f46ff8931413dbfdebb308`

## Scope

This task adds a small-run synthetic numerical digital-twin baseline comparing a legacy-style free `log_sigma` conductivity shortcut with the white-box `vo2_sigma(T, c_v, m)` closure. It is not a formal performance experiment, not real VO2/NbO2 experimental validation, and not evidence that sparse terminal data uniquely recover full hidden fields.

## Changed Files

- `.gitignore`
- `CODEX_CONTEXT.md`
- `configs/pinn_inverse_v2_f_sps_baseline.yaml`
- `scripts/run_pinn_inverse_v2_baseline.py`
- `tests/test_pinn_inverse_v2_baseline.py`
- `outputs/tables/pinn_inverse_v2_f_sps_baseline_summary.json`
- `outputs/tables/pinn_inverse_v2_f_sps_baseline_runs.csv`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/research_strategy/active_phase.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`
- `docs/codex_reports/pinn_inverse_v2_f_sps_baseline_report.md`

## Baseline Design

Both runs use the frozen Ground Truth v1.1 triangle benchmark and sparse terminal observations:

- Target: `data/processed/gt_v1_acceptance/gt_triangle.npz`
- Sparse observations: `data/processed/gt_v1_acceptance/obs_triangle_sparse.npz`
- Config: `configs/pinn_inverse_v2_f_sps_baseline.yaml`
- Runner: `scripts/run_pinn_inverse_v2_baseline.py`
- Summary: `outputs/tables/pinn_inverse_v2_f_sps_baseline_summary.json`
- Runs CSV: `outputs/tables/pinn_inverse_v2_f_sps_baseline_runs.csv`

The two conductivity modes share the same seed, epochs, hidden size, Fourier scales, field-anchor count, terminal observations, and loss weights.

- `free_log_sigma`: uses a trainable positive sigma head as the old surrogate conductivity shortcut.
- `white_box_vo2_sigma`: predicts `T`, `c_v`, and `m`, then computes `sigma = vo2_sigma(T, c_v, m)`.

Dynamic gate and frequency loss are kept disabled. The old v0/v1/v1.1 scripts are not modified or replaced.

## Validation

Validated with the project `.venv` Python 3.11.9 interpreter.

- Targeted command: `.\.venv\Scripts\python.exe -m pytest tests/test_pinn_inverse_v2_baseline.py tests/test_pinn_inverse_v2_smoke.py tests/test_vo2_constitutive.py`
- Targeted result: `8 passed`
- Full command: `.\.venv\Scripts\python.exe -m pytest`
- Full result: `51 passed`
- Baseline command: `.\.venv\Scripts\python.exe scripts\run_pinn_inverse_v2_baseline.py --config configs\pinn_inverse_v2_f_sps_baseline.yaml`
- Baseline result: completed and wrote the summary JSON and runs CSV.

## Result Summary

| run_name | final_loss | relative_G_error | relative_I_error | nrmse_delta_T | nrmse_c_v | nrmse_m | nrmse_sigma | sigma_min | sigma_max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `free_log_sigma` | `0.08363717049360275` | `0.408902714577596` | `0.43039374888349763` | `0.47216525753771105` | `0.3329757906450112` | `0.311927582851063` | `0.17958202213083294` | `0.004308660980314016` | `0.004945037886500359` |
| `white_box_vo2_sigma` | `0.08345235139131546` | `0.4090955992821045` | `0.42799523908857184` | `0.4721508718130579` | `0.33499704314444895` | `0.3034902197486291` | `0.1789054620107825` | `0.004458672367036343` | `0.004738473333418369` |

Both runs produced finite losses and loss decreases over 8 epochs. The white-box closure run used `vo2_sigma=true` and `free_log_sigma=false`; the free-log-sigma run is retained only as a surrogate baseline. The two results are close, so this small-run baseline does not support a performance-superiority claim.

## Boundary Checks

- Modified frozen GT: No.
- Replaced old v0/v1/v1.1 main path: No.
- Committed checkpoints, figures, or large output directories: No.
- Claimed F-SPS-PINN performance superiority: No.
- Claimed real VO2/NbO2 experimental validation: No.
- Claimed sparse-port unique full hidden-field recovery: No.

## Next Step

If this baseline remains stable, run a bounded phase-transition stress test or Fourier on/off ablation. Keep the constrained `gamma_sub` reduced inverse problem as the most defensible paper mainline until F-SPS-PINN has stronger comparative evidence.

# PINN inverse v2 F-SPS smoke report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this task: `d14c6848cbe70275ed815a1940e9056f8d3badca`
- Implementation commit hash: `429d6f0c5a9539aea4b19945c0487c450feb77c4`

## Scope

This task advances the isolated F-SPS-PINN architecture MVP into a minimal smoke-training loop. The result is a synthetic numerical digital-twin smoke test only. It is not a formal performance experiment, not a real-device experiment, and not evidence that sparse port data can uniquely recover full hidden fields.

## Changed Files

- `.gitignore`
- `configs/pinn_inverse_v2_f_sps_smoke.yaml`
- `scripts/train_pinn_inverse_v2_smoke.py`
- `tests/test_pinn_inverse_v2_smoke.py`
- `outputs/tables/pinn_inverse_v2_f_sps_smoke_summary.json`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/project_state/file_inventory.md`

## State Files Synchronized

- `PROJECT_STATE.md`: records that F-SPS-PINN architecture MVP is complete as an isolated unit-tested package and that v2 smoke training is now available.
- `NEXT_ACTIONS.md`: sets the immediate next step to v2 smoke training and keeps the constrained `gamma_sub` line as the defensible paper core.
- `EXPERIMENT_REGISTRY.md`: registers the architecture MVP modules and the v2 smoke pipeline.
- `DATASET_REGISTRY.md`: registers the lightweight v2 smoke summary JSON.
- `FIGURE_REGISTRY.md`: states that no v2 smoke figures were generated or committed.
- `docs/project_state/file_inventory.md`: adds the v2 config, trainer, tests, and report entries.

## Smoke Training Design

- Input target: `data/processed/gt_v1_acceptance/gt_triangle.npz`
- Sparse observation: `data/processed/gt_v1_acceptance/obs_triangle_sparse.npz`
- Config: `configs/pinn_inverse_v2_f_sps_smoke.yaml`
- Trainer: `scripts/train_pinn_inverse_v2_smoke.py`
- Output summary: `outputs/tables/pinn_inverse_v2_f_sps_smoke_summary.json`
- Model path: `StiffAwareMLP` with Fourier-pyramid features.
- Network outputs: `T`, `c_v`, and `m`.
- Conductivity closure: `sigma = vo2_sigma(T, c_v, m)`.
- Free `log_sigma` head: not used.
- Dynamic gate and frequency loss: kept disabled by config flags.

The loss contains sparse-port `G/I` reconstruction, a small optional field-anchor term, and smoothness regularization. This smoke run verifies finite forward/backward/train behavior and white-box sigma closure participation in the training graph.

## Validation

The project Python environment is `.venv\Scripts\python.exe` with Python 3.11.9. This matches the repository requirement `>=3.11,<3.12`.

- Targeted command:
  `.\.venv\Scripts\python.exe -m pytest tests/test_vo2_constitutive.py tests/test_fourier_pyramid.py tests/test_loss_balancer.py tests/test_oscillation_metrics.py tests/test_pinn_inverse_v2_smoke.py`
- Targeted result:
  `17 passed`
- Full command:
  `.\.venv\Scripts\python.exe -m pytest`
- Full result:
  `49 passed`
- Smoke command:
  `.\.venv\Scripts\python.exe scripts\train_pinn_inverse_v2_smoke.py --config configs\pinn_inverse_v2_f_sps_smoke.yaml`
- Smoke result:
  completed and wrote `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`

The current bare shell `python` points to Anaconda base Python 3.12.4, which is outside the repository Python range. After activating the project `.venv`, the required `python -m pytest` command is equivalent to the validated `.venv\Scripts\python.exe -m pytest`.

## Summary Metrics

- `initial_loss`: `0.08348917216062546`
- `final_loss`: `0.08242770284414291`
- `loss_decreased`: `true`
- `finite_loss`: `true`
- `sigma_min`: `0.004415146075189114`
- `sigma_max`: `0.004632454365491867`
- `used_vo2_sigma`: `true`
- `used_free_log_sigma`: `false`
- `epochs`: `3`
- `seed`: `2026`

## Boundary Checks

- Modified frozen GT: No.
- Replaced old v0/v1/v1.1 path: No.
- Used free `log_sigma`: No.
- Claimed F-SPS-PINN performance superiority: No.
- Claimed real VO2/NbO2 experimental validation: No.
- Claimed sparse-port unique full hidden-field recovery: No.

## Next Step

Run a small v2 baseline comparison between the old free `log_sigma` conductivity shortcut and the white-box `vo2_sigma(T, c_v, m)` closure. This should remain a controlled synthetic numerical digital-twin benchmark until formal baselines and ablations are completed.

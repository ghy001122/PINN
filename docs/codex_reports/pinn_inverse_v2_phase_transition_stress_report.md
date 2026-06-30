# F-SPS-PINN v2 Phase-Transition Stress Preflight Report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Commit scope: this report is bundled with the F-SPS-PINN v2 phase-transition stress preflight implementation after history cleanup; use `git log` for the current squashed commit hash.
- Benchmark type: synthetic numerical digital-twin stress preflight only

## Changed Files

- `configs\pinn_inverse_v2_phase_transition_stress.yaml`
- `scripts\run_pinn_inverse_v2_phase_transition_stress.py`
- `tests\test_pinn_inverse_v2_phase_transition_stress.py`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`
- `scripts\run_pinn_inverse_v2_baseline.py`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `CODEX_CONTEXT.md`
- `docs\research_strategy\active_phase.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `RESEARCH_LOG.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\reproducibility.md`
- `.gitignore`

## Stress Case Design

The stress preflight reuses the v2 baseline data loading, model, training loop, frozen-input checks, and metric calculation. It runs only the `white_box_vo2_sigma` path and disables dynamic gate and frequency losses.

Stress cases:

| case | T_c | transition_width | sigma_ins0 | sigma_met0 | intent |
|---|---:|---:|---:|---:|---|
| `mild_transition` | 313.0 | 5.0 | 0.0025 | 0.03 | baseline-like VO2 closure stress |
| `sharp_transition` | 313.0 | 0.75 | 0.0025 | 0.03 | sharper transition stiffness |
| `near_threshold` | 300.5 | 1.0 | 0.0025 | 0.03 | transition threshold near predicted training temperatures |
| `high_contrast` | 313.0 | 2.0 | 0.001 | 0.3 | larger insulating/metallic contrast |

The baseline runner now supports an opt-in `use_temperature_phase_fraction` flag. The phase-transition stress config enables it so `T_c` and `transition_width` affect `vo2_sigma`; existing v2 baseline defaults remain unchanged.

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pinn_inverse_v2_phase_transition_stress.py tests/test_pinn_inverse_v2_baseline.py tests/test_vo2_constitutive.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\run_pinn_inverse_v2_phase_transition_stress.py --config configs\pinn_inverse_v2_phase_transition_stress.yaml
```

Results:

- Targeted tests: `8 passed in 10.19s`.
- Full test suite: `53 passed in 80.28s` with existing third-party matplotlib/pyparsing warnings.
- Stress preflight script: completed; `all_finite_loss=true`, `all_used_vo2_sigma=true`, `all_frozen_inputs_unchanged=true`.

## Key Table Summary

| case | final_loss | relative_G_error | relative_I_error | nrmse_sigma | sigma_dynamic_range |
|---|---:|---:|---:|---:|---:|
| `mild_transition` | 0.08949020504951477 | 0.42666156507013664 | 0.4461685719031997 | 0.18380569851264908 | 1.010512940050241 |
| `sharp_transition` | 0.17876745760440826 | 0.6541468962013739 | 0.6620272150456785 | 0.2502860490249889 | 1.0202085779737933 |
| `near_threshold` | 0.3482680022716522 | 1.0033520810671768 | 1.0152833663449128 | 0.3110244204386709 | 1.0021420938317573 |
| `high_contrast` | 0.25269144773483276 | 0.7970808136413061 | 0.8011396652516292 | 0.29290442824694246 | 1.0138320564948804 |

Outputs:

- `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json`
- `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`

## Boundary Checks

- Modified frozen GT: No.
- Replaced old v0/v1/v1.1 main paths: No.
- Used free `log_sigma` in stress path: No.
- Claimed F-SPS-PINN performance superiority: No.
- Claimed real VO2/NbO2 experimental validation: No.
- Claimed sparse-port unique full hidden-field recovery: No.

## Next Step

If this preflight remains acceptable, the next bounded method-development step is either a Fourier on/off ablation or a dynamic gate smoke test. The constrained `gamma_sub` inversion remains the strongest current paper mainline.

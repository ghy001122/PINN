# F-SPS-PINN v2 Fourier On/Off Ablation Report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this task: `5c7c2f6b0ca8dc832f1066730ae20cab1cd8d99c`
- Benchmark type: synthetic numerical digital-twin Fourier ablation only

## Changed Files

- `configs\pinn_inverse_v2_fourier_ablation.yaml`
- `scripts\run_pinn_inverse_v2_fourier_ablation.py`
- `tests\test_pinn_inverse_v2_fourier_ablation.py`
- `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json`
- `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`
- `src\pinnpcm\pinn\network.py`
- `scripts\run_pinn_inverse_v2_baseline.py`
- `.gitignore`
- `CODEX_CONTEXT.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs\research_strategy\active_phase.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\reproducibility.md`
- `docs\codex_reports\pinn_inverse_v2_fourier_ablation_report.md`

## Ablation Design

The ablation compares only Fourier-pyramid feature usage under the same synthetic sharp-transition stress condition. Both runs use the frozen Ground Truth v1.1 triangle benchmark, the same sparse terminal observations, seed, epochs, field-anchor count, loss weights, and white-box `vo2_sigma` closure.

| run | conductivity_mode | Fourier | stress_case | T_c | transition_width | sigma_ins0 | sigma_met0 |
|---|---|---:|---|---:|---:|---:|---:|
| `vo2_sigma_fourier_off` | `white_box_vo2_sigma` | false | `sharp_transition` | 313.0 | 0.75 | 0.0025 | 0.03 |
| `vo2_sigma_fourier_on` | `white_box_vo2_sigma` | true | `sharp_transition` | 313.0 | 0.75 | 0.0025 | 0.03 |

Dynamic gate, frequency loss, STL, and free `log_sigma` are not used in the main comparison.

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pinn_inverse_v2_fourier_ablation.py tests/test_pinn_inverse_v2_phase_transition_stress.py tests/test_vo2_constitutive.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\run_pinn_inverse_v2_fourier_ablation.py --config configs\pinn_inverse_v2_fourier_ablation.yaml
```

Validation status:

- Targeted tests passed: `8 passed in 18.35s`.
- Full test suite passed: `55 passed in 104.12s` with existing third-party matplotlib/pyparsing warnings.
- Fourier ablation script completed and wrote the summary JSON and runs CSV.

## Key Result Table

| run | final_loss | relative_G_error | relative_I_error | nrmse_delta_T | nrmse_c_v | nrmse_m | nrmse_sigma | sigma_dynamic_range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `vo2_sigma_fourier_off` | 0.17737101018428802 | 0.6509982160898017 | 0.6596275873510091 | 0.47211250988064973 | 0.39587474578254106 | 0.3051101828428313 | 0.24940025054427328 | 1.0061456248628189 |
| `vo2_sigma_fourier_on` | 0.17817334830760956 | 0.6529524166709443 | 0.6607393386460401 | 0.4721668922791489 | 0.36176873917221936 | 0.3119689623087828 | 0.24992714418015055 | 1.022688214827701 |

Both runs produced finite losses and loss decreases. Fourier on does not clearly outperform Fourier off in this small-run result.

## Boundary Checks

- Modified frozen GT: No.
- Replaced old v0/v1/v1.1 main paths: No.
- Claimed F-SPS-PINN performance superiority: No.
- Claimed real VO2/NbO2 experimental validation: No.
- Claimed sparse-port unique full hidden-field recovery: No.
- Claimed phase-transition stiffness is solved: No.

## Current Conclusion Boundary

This is a small-run synthetic numerical Fourier ablation under one stress condition. It supports only a bounded engineering statement: the Fourier switch can be evaluated in the v2 training path, but this specific run does not show a clear advantage from Fourier features.

## Next Step

Because Fourier on is not clearly better here, the conservative next step is to return focus to the constrained `gamma_sub` paper mainline and keep F-SPS-PINN as appendix or future-work evidence unless a later, explicitly authorized small-run shows a robust benefit.

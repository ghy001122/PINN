# Actualized High-Risk Claim Ladder v2 Report

All results in this report are synthetic numerical digital-twin benchmark evidence, not experimental data.

## Repository Snapshot

- Repository: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Baseline commit before this task: `c4835c02f8d42b7fdb89e581b86b56dae2fb667a`
- Final pushed task commit: reported in the final Codex response after Git creates the commit hash. A single Git commit cannot truthfully contain its own final hash because editing the report changes the tree and therefore the hash.
- Task name: `actualize_high_risk_claim_ladder_v2`
- Frozen Ground Truth v1.1 modified: No

## What Was Actualized

1. The 2D high-risk ladder now includes actual low-rank coefficient inversion rather than using `_protocol_error` as a direct field-error heuristic.
2. The Fourier/F-SPS conditional-superiority audit now runs actual reduced PINN training comparisons rather than residual-proxy method multipliers.
3. The integrated stiffness/STL audit was expanded to a 90-case actual-training grid with gradient-spike, residual-imbalance, and convergence-proxy diagnostics.

## Changed Files

- `.gitignore`
- `configs/high_risk_claim_ladder.yaml`
- `src/pinnpcm/experiments/high_risk_actual_inverse.py`
- `scripts/audit_high_risk_claim_ladder.py`
- `scripts/audit_integrated_stiffness_stl.py`
- `scripts/audit_fourier_fsps_conditional_superiority.py`
- `scripts/build_reviewer_defense_matrix.py`
- `tests/test_high_risk_claim_ladder.py`
- `tests/test_integrated_stiffness_stl.py`
- `tests/test_fourier_fsps_conditional_superiority.py`
- `outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json`
- `outputs/tables/high_risk_claim_ladder_actual_inverse_cases.csv`
- `outputs/tables/integrated_stiffness_stl_summary.json`
- `outputs/tables/integrated_stiffness_stl_cases.csv`
- `outputs/tables/fourier_fsps_actual_training_summary.json`
- `outputs/tables/fourier_fsps_actual_training_cases.csv`
- `docs/paper/claim_gate_resolution_matrix.md`
- `docs/paper/final_claim_matrix.md`
- `docs/manuscript/reviewer_defense_matrix.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`

## Actual 2D Inverse Result

The new actual low-rank inverse writes `outputs/tables/high_risk_claim_ladder_actual_inverse_summary.json` and `outputs/tables/high_risk_claim_ladder_actual_inverse_cases.csv`.

Key results:

- `actual_inverse_mode`: `true`
- `num_cases`: `128`
- `all_finite_results`: `true`
- `field_recovery_status`: `forbidden`
- `terminal_only_field_status`: `failed_but_informative`
- `terminal_only_parameter_status`: `qualified_supported`
- Best augmented protocol: `terminal_plus_sparse_anchors_2pct`
- Best median low-rank field error: `0.544268189851365`
- Terminal-only median parameter error: `0.029775671121156505`

Interpretation:

- Actual low-rank field recovery did not clear the success gate.
- Full-grid arbitrary 2D hidden-field recovery remains forbidden.
- Terminal-only data support only low-dimensional parameter wording under strong priors.

## Actual Stiffness/STL Result

The expanded stiffness audit writes `outputs/tables/integrated_stiffness_stl_summary.json` and `outputs/tables/integrated_stiffness_stl_cases.csv`.

Key results:

- `num_cases`: `90`
- `all_finite_results`: `true`
- `actual_stiffness_pinn_training_completed`: `true`
- `continuation_asinh_adaptive_status`: `qualified_supported`
- `seiler_style_multi_head_transfer_implemented`: `true`
- `seiler_style_multi_head_stl_status`: `failed_but_informative`
- Gain over direct:
  - `continuation_plus_asinh`: `0.36308047799714416`
  - `continuation_plus_asinh_plus_adaptive`: `0.37795297711408815`
  - `Seiler_style_multi_head_STL_frozen_trunk`: `-0.12675208187398518`
  - `Seiler_style_multi_head_STL_unfrozen_tail`: `-0.05954255207671333`

Interpretation:

- Continuation/asinh/adaptive residual handling is strengthened as reduced actual-training evidence.
- Seiler-style mechanics are implemented but do not clear the expanded-grid gain gate.
- Full STL-PINN reproduction remains forbidden.

## Actual Fourier/F-SPS Result

The new actual-training audit writes `outputs/tables/fourier_fsps_actual_training_summary.json` and `outputs/tables/fourier_fsps_actual_training_cases.csv`.

Key results:

- `num_cases`: `80`
- `all_finite_results`: `true`
- `is_actual_pinn_training`: `true`
- `best_sharp_method`: `f_sps_sampling`
- `conditional_benefit_status`: `failed_but_informative`
- `universal_superiority_status`: `forbidden`
- Sharp-regime gain over vanilla:
  - `f_sps_sampling`: `0.4391566795808073`
  - `fourier_plus_continuation_asinh`: `0.30614567612459503`
- Smooth-regime degradation:
  - `f_sps_sampling`: `0.8471974813135894`
  - `fourier_plus_continuation_asinh`: `1.5303623589379236`

Interpretation:

- The proxy/multiplier result has been replaced by actual training evidence.
- Sharp/front-regime gains exist for selected methods.
- Smooth-regime degradation blocks a positive conditional-benefit claim in this run.
- Universal F-SPS/Fourier superiority remains forbidden.

## Claim Changes

Upgraded or strengthened:

- Actual low-rank inverse machinery exists and is tested.
- Continuation/asinh/adaptive stiffness mitigation is now supported by expanded actual-training evidence.
- Fourier/F-SPS evidence is no longer proxy-only; it is now actual-training evidence.

Downgraded:

- Heuristic low-rank 2D hidden-field recovery is downgraded to forbidden under actual inverse evidence.
- Seiler-style multi-head STL is downgraded from qualified support to failed-but-informative in the expanded grid.
- Fourier/F-SPS conditional benefit is downgraded to failed-but-informative because smooth-regime degradation offsets sharp/front gains.

Forbidden claims:

- Full arbitrary 2D hidden-field recovery.
- Terminal-only full-field 2D inverse recovery.
- Full STL-PINN reproduction.
- Universal F-SPS/Fourier superiority.
- Experimental validation.

## How Forbidden Claims Could Become Feasible

- Full 2D hidden-field recovery would require actual inverse training with stronger independent observations, sensor-placement evidence, and full-grid validation against non-low-rank targets.
- Full STL-PINN reproduction would require a literature-faithful transfer chain, matched budgets, trunk/tail ablations, and positive gains across transition widths, seeds, and noise levels.
- Fourier/F-SPS superiority would require a predeclared regime split, no material smooth-regime degradation, and matched-budget repeated training that improves both sharp/front and smooth cases.

## Validation

Commands run:

```powershell
.\.venv\Scripts\python.exe scripts\audit_high_risk_claim_ladder.py --profile quick
.\.venv\Scripts\python.exe scripts\audit_integrated_stiffness_stl.py
.\.venv\Scripts\python.exe scripts\audit_fourier_fsps_conditional_superiority.py
.\.venv\Scripts\python.exe -m pytest tests/test_high_risk_claim_ladder.py tests/test_integrated_stiffness_stl.py tests/test_fourier_fsps_conditional_superiority.py
.\.venv\Scripts\python.exe -m pytest tests/test_reduced_2d_phase_transition_forward.py tests/test_reduced_2d_observability_limited_inverse.py tests/test_stiffness_aware_algorithm_benchmark.py tests/test_claim_gate_resolution_matrix.py
.\.venv\Scripts\python.exe -m pytest
```

Results:

- High-risk ladder script: passed; actual inverse summary generated.
- Integrated stiffness/STL script: passed; expanded 90-case summary generated.
- Fourier/F-SPS actual-training script: passed; 80-case summary generated.
- Focused high-risk tests: `5 passed`.
- 2D/claim-gate tests: `4 passed`.
- Full test suite: `136 passed in 170.65s`.

## SCI Value

This pack improves SCI readiness mainly by making the claim ladder more honest and defensible. It adds actual inverse and actual training evidence, but the strongest manuscript line should still remain constrained reduced `gamma_sub` inversion. The new evidence is best used as reviewer-defense, limitations, supplementary evidence, and future-method justification rather than as the main novelty claim.

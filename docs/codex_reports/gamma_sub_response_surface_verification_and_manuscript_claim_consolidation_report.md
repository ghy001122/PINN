# Gamma Sub Response-Surface Verification And Manuscript Claim Consolidation Report

## Scope

Repository: `https://github.com/ghy001122/PINN`
Branch: `main`
Base commit before this task: `1f4207764fd09860d6ed50935a7f31389ba33837`
Final pushed commit hash: recorded in the final response after commit/push, because a commit cannot contain its own final SHA without changing that SHA.

This pack strengthens the synthetic numerical digital-twin manuscript evidence chain. It does not modify frozen Ground Truth v1.1, does not create experimental data, does not claim sparse-port full hidden-field recovery, and does not claim F-SPS-PINN superiority.

## Changed Files

New configs:

- `configs/gamma_sub_response_surface_anchor_verification.yaml`
- `configs/gamma_sub_sequential_protocol_design.yaml`
- `configs/f_sps_balanced_medium_budget_benchmark.yaml`

New scripts:

- `scripts/audit_gamma_sub_response_surface_anchor_verification.py`
- `scripts/audit_gamma_sub_sequential_protocol_design.py`
- `scripts/train_f_sps_balanced_medium_budget_benchmark.py`
- `scripts/build_manuscript_claim_stress_test.py`
- `scripts/build_manuscript_ready_gamma_sub_figures.py`

New tests:

- `tests/test_gamma_sub_response_surface_anchor_verification.py`
- `tests/test_gamma_sub_sequential_protocol_design.py`
- `tests/test_f_sps_balanced_medium_budget_benchmark.py`
- `tests/test_manuscript_claim_stress_test.py`

New lightweight evidence:

- `outputs/tables/gamma_sub_response_surface_anchor_verification_summary.json`
- `outputs/tables/gamma_sub_response_surface_anchor_verification_cases.csv`
- `outputs/tables/gamma_sub_sequential_protocol_design_summary.json`
- `outputs/tables/gamma_sub_sequential_protocol_design_cases.csv`
- `outputs/tables/f_sps_balanced_medium_budget_benchmark_summary.json`
- `outputs/tables/f_sps_balanced_medium_budget_benchmark_cases.csv`
- `outputs/tables/manuscript_claim_stress_test_summary.json`

New manuscript docs:

- `docs/paper/claim_stress_test_matrix.md`
- `docs/paper/proposed_main_figures.md`
- `docs/paper/proposed_tables.md`
- `docs/paper/manuscript_outline_v1.md`

Updated state/evidence-chain files:

- `.gitignore`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `RESEARCH_LOG.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/research_strategy/active_phase.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/reproducibility.md`
- `docs/paper/sci_manuscript_evidence_matrix.md`
- `docs/paper/experiment_to_figure_mapping.md`

Generated but not committed as large/generated artifacts:

- `outputs/figures/manuscript_ready_gamma_sub/main_figure_2_confounding_profile.png`
- `outputs/figures/manuscript_ready_gamma_sub/main_figure_3_recoverability_phase_diagram.png`
- `outputs/figures/manuscript_ready_gamma_sub/main_figure_4_anchor_verification.png`
- `outputs/figures/manuscript_ready_gamma_sub/main_figure_5_protocol_design.png`
- `outputs/figures/manuscript_ready_gamma_sub/main_figure_6_statistical_robustness.png`
- `outputs/figures/manuscript_ready_gamma_sub/appendix_f_sps_balanced_benchmark.png`

## Validation Commands

Official outputs were regenerated with:

```powershell
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_response_surface_anchor_verification.py
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_sequential_protocol_design.py
.\.venv\Scripts\python.exe scripts\train_f_sps_balanced_medium_budget_benchmark.py
.\.venv\Scripts\python.exe scripts\build_manuscript_claim_stress_test.py
.\.venv\Scripts\python.exe scripts\build_manuscript_ready_gamma_sub_figures.py
```

Tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gamma_sub_response_surface_anchor_verification.py tests\test_gamma_sub_sequential_protocol_design.py tests\test_f_sps_balanced_medium_budget_benchmark.py tests\test_manuscript_claim_stress_test.py
.\.venv\Scripts\python.exe -m pytest tests\test_gamma_sub_tsw_dense_profile_likelihood.py tests\test_gamma_sub_recoverability_phase_diagram.py tests\test_gamma_sub_protocol_actual_inversion_validation.py tests\test_gamma_sub_statistical_robustness.py tests\test_f_sps_medium_budget_benchmark.py
.\.venv\Scripts\python.exe -m pytest
```

Results:

- New tests: `7 passed`.
- Key regression tests: `10 passed`.
- Full test suite: `93 passed` with third-party matplotlib/pyparsing warnings.
- `git diff --check`: no whitespace errors; Git only reported line-ending warnings.
- Frozen GT diff check: no modified files under frozen acceptance configs/report/manifest or `src/pinnpcm/physics`.

## Anchor Verification Key Results

- `num_anchor_cases = 60`
- `mean_absolute_discrepancy = 0.05373609469259508`
- `median_absolute_discrepancy = 0.03420116487516757`
- `max_discrepancy = 0.34298978353285103`
- `classification_agreement_rate = 0.8833333333333333`
- `whether_response_surface_is_acceptable_for_manuscript = true`

Interpretation: response-surface phase diagrams are acceptable as manuscript evidence only with explicit qualification. The 2501 dense profile points remain IDW-interpolated from 77 simulator-backed source points; this task did not convert them into 2501 fresh ODE solves.

## Sequential Protocol Design Key Results

Best candidate by response-surface gamma error:

- `candidate_name = multi_pulse_to_ltp_ltd`
- `stage2_gamma_error = 0.07554331565883955`
- `stage1_ridge_width_reduction = 0.55`
- `final_recoverable_le_0p1 = true`
- `improvement_over_best_single = true`
- `improvement_over_ltp_ltd_only = true`

Interpretation: sequential design is promising in this preflight response-surface model, but it is still a hypothesis. It should not be written as experimentally validated or guaranteed protocol superiority.

## Balanced F-SPS Key Results

- `planned_cases = 36`
- `executed_cases = 12`
- `all_executed_finite = true`
- `coverage_by_model = 3` executed cases for each of `free_log_sigma_pinn`, `white_box_vo2_sigma_pinn`, `white_box_vo2_sigma_fourier`, and `f_sps_pinn`
- `coverage_by_epoch = 4` executed cases for each of `20`, `100`, and `300` epochs
- `best_model_by_G_error = white_box_vo2_sigma_fourier`
- `best_model_by_sigma_nrmse = white_box_vo2_sigma_fourier`
- `best_model_by_delta_T_nrmse = white_box_vo2_sigma_fourier`
- `whether_f_sps_improves_over_free_log_sigma = false`
- `whether_f_sps_improves_over_white_box_fourier = false`

Interpretation: balanced coverage fixes the previous 8-case coverage weakness, but it still does not support an F-SPS-PINN superiority claim.

## Claim Stress-Test Summary

The claim stress-test matrix records 7 claims. Each claim includes supporting tables, supporting scripts, strongest numerical result, limitation, forbidden overclaim, and manuscript section.

Supported SCI claims:

- Sparse-port full-field recovery is non-identifiable in the current one-dimensional synthetic benchmark.
- `gamma_sub` recovery is conditionally possible under fixed or tightly bounded priors.
- Wide `T_sw` mismatch is the dominant failure mode.
- Protocol choice affects recoverability; `ltp_ltd` and short/multi-pulse style protocols are useful hypotheses.
- Naive weighted protocol objective did not improve over the best single protocol in the tested case.
- Response-surface phase diagrams can be used only with anchor-verification qualification.

Forbidden claims:

- measured experimental validation;
- real VO2/NbO2 or fabricated memristor validation;
- full 3D device simulation;
- sparse-port unique full hidden-field recovery;
- unconditional joint parameter identifiability;
- all dense response-surface points are simulator-backed ODE solves;
- F-SPS-PINN superiority from current bounded evidence.

## Remaining Gaps

- Sequential protocol design still needs stronger simulator-backed validation if it becomes a main figure claim.
- The response-surface anchor verification supports use with qualification, not exhaustive validation.
- `T_sw` remains the most important confounder and must be fixed or independently calibrated in the main claim.
- F-SPS-PINN remains appendix/future-work evidence unless a separate full-budget method paper is opened.

## Boundary Checks

- Frozen GT modified: No.
- Large artifacts committed: No.
- Generated figures committed: No.
- Synthetic numerical digital-twin boundary preserved: Yes.

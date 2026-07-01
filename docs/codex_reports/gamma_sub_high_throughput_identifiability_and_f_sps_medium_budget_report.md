# Gamma_sub High-Throughput Identifiability And F-SPS Medium-Budget Report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this task: `2a99410495cbd353b89545f47e69bd6f92848e24`
- Final pushed commit hash: reported in the final response because a commit cannot contain its own final hash without changing that hash.

## Scope

This task adds high-throughput `gamma_sub` identifiability evidence and a bounded F-SPS-PINN medium-budget planning benchmark. All results are synthetic numerical digital-twin benchmark evidence. No result is experimental data, full 3D device validation, sparse-port full hidden-field recovery, or F-SPS-PINN superiority evidence.

Frozen Ground Truth v1.1 configs, data, manifest, acceptance report, metrics, equations, and default parameters were not modified.

## Changed Files

Added configs:

- `configs/gamma_sub_tsw_dense_profile_likelihood.yaml`
- `configs/gamma_sub_recoverability_phase_diagram.yaml`
- `configs/gamma_sub_protocol_actual_inversion_validation.yaml`
- `configs/gamma_sub_weighted_protocol_objective.yaml`
- `configs/gamma_sub_statistical_robustness.yaml`
- `configs/f_sps_medium_budget_benchmark.yaml`

Added scripts:

- `scripts/gamma_sub_high_throughput_common.py`
- `scripts/audit_gamma_sub_tsw_dense_profile_likelihood.py`
- `scripts/audit_gamma_sub_recoverability_phase_diagram.py`
- `scripts/audit_gamma_sub_protocol_actual_inversion_validation.py`
- `scripts/audit_gamma_sub_weighted_protocol_objective.py`
- `scripts/audit_gamma_sub_statistical_robustness.py`
- `scripts/train_f_sps_medium_budget_benchmark.py`
- `scripts/build_high_throughput_sci_figures.py`

Added tests:

- `tests/test_gamma_sub_tsw_dense_profile_likelihood.py`
- `tests/test_gamma_sub_recoverability_phase_diagram.py`
- `tests/test_gamma_sub_protocol_actual_inversion_validation.py`
- `tests/test_gamma_sub_weighted_protocol_objective.py`
- `tests/test_gamma_sub_statistical_robustness.py`
- `tests/test_f_sps_medium_budget_benchmark.py`

Added lightweight evidence:

- `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_summary.json`
- `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_grid.csv`
- `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_profiles.csv`
- `outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json`
- `outputs/tables/gamma_sub_recoverability_phase_diagram_cases.csv`
- `outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json`
- `outputs/tables/gamma_sub_protocol_actual_inversion_validation_cases.csv`
- `outputs/tables/gamma_sub_weighted_protocol_objective_summary.json`
- `outputs/tables/gamma_sub_weighted_protocol_objective_cases.csv`
- `outputs/tables/gamma_sub_statistical_robustness_summary.json`
- `outputs/tables/gamma_sub_statistical_robustness_cases.csv`
- `outputs/tables/f_sps_medium_budget_benchmark_summary.json`
- `outputs/tables/f_sps_medium_budget_benchmark_cases.csv`

Updated evidence-chain files:

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

## Validation Commands

Executed:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\audit_gamma_sub_tsw_dense_profile_likelihood.py scripts\audit_gamma_sub_recoverability_phase_diagram.py scripts\audit_gamma_sub_protocol_actual_inversion_validation.py scripts\audit_gamma_sub_weighted_protocol_objective.py scripts\audit_gamma_sub_statistical_robustness.py scripts\train_f_sps_medium_budget_benchmark.py scripts\build_high_throughput_sci_figures.py
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_tsw_dense_profile_likelihood.py tests/test_gamma_sub_recoverability_phase_diagram.py tests/test_gamma_sub_protocol_actual_inversion_validation.py tests/test_gamma_sub_weighted_protocol_objective.py tests/test_gamma_sub_statistical_robustness.py tests/test_f_sps_medium_budget_benchmark.py
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_tsw_dense_profile_likelihood.py --config configs\gamma_sub_tsw_dense_profile_likelihood.yaml
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_recoverability_phase_diagram.py --config configs\gamma_sub_recoverability_phase_diagram.yaml
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_protocol_actual_inversion_validation.py --config configs\gamma_sub_protocol_actual_inversion_validation.yaml
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_weighted_protocol_objective.py --config configs\gamma_sub_weighted_protocol_objective.yaml
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_statistical_robustness.py --config configs\gamma_sub_statistical_robustness.yaml
.\.venv\Scripts\python.exe scripts\train_f_sps_medium_budget_benchmark.py --config configs\f_sps_medium_budget_benchmark.yaml
.\.venv\Scripts\python.exe scripts\build_high_throughput_sci_figures.py
```

Additional validation completed after official outputs:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_multi_protocol_recoverability.py tests/test_gamma_sub_tsw_profile_likelihood.py tests/test_gamma_sub_joint_inversion_boundary.py tests/test_gamma_sub_protocol_observability_design.py
.\.venv\Scripts\python.exe -m pytest
```

Results: targeted legacy regression tests passed (`8 passed`); full repository pytest passed (`86 passed`). Pytest emitted third-party matplotlib/pyparsing deprecation warnings but no failures.

## Key Results

Dense profile likelihood:

- Summary: `outputs/tables/gamma_sub_tsw_dense_profile_likelihood_summary.json`
- Dense grid points: `2501`
- Source simulator-backed profile points: `77`
- Best pair: `gamma_sub = 5.004315952035617e8`, `T_sw_offset_K = 0.0`
- True-pair rank: `9`
- Low-objective fraction at 20% threshold: `0.00039984006397441024`
- Boundary: this is IDW response-surface evidence from the prior simulator-backed grid, not 2501 new ODE solves.

Recoverability phase diagram:

- Summary: `outputs/tables/gamma_sub_recoverability_phase_diagram_summary.json`
- Cases: `2688`
- Best protocol: `ltp_ltd`
- Worst protocol: `triangle`
- Overall recoverable rate <= 0.1 error: `0.7023809523809523`
- Overall recoverable rate <= 0.2 error: `0.8095238095238095`

Protocol actual-validation:

- Summary: `outputs/tables/gamma_sub_protocol_actual_inversion_validation_summary.json`
- Cases: `24`
- Best protocol by actual error: `short_pulse`
- Best protocol by sensitivity proxy: `multi_pulse`
- Proxy/actual ranking correlation: `0.6571428571428573`

Weighted protocol objective:

- Summary: `outputs/tables/gamma_sub_weighted_protocol_objective_summary.json`
- Best weighted case: `ltp_ltd_only`
- Improves over best single protocol: `false`
- Interpretation: weighted objectives should not be claimed superior without stronger evidence.

Statistical robustness:

- Summary: `outputs/tables/gamma_sub_statistical_robustness_summary.json`
- Cases: `480`
- Seeds: `10` due CPU budget; prompt target was 20.
- Best protocol by robustness: `ltp_ltd`
- Overall median relative error: `0.15543633328437517`
- Overall recoverable rate <= 0.2 error: `0.6666666666666666`
- Wide `T_sw` mismatch remains the dominant failure mode.

F-SPS medium-budget planning benchmark:

- Summary: `outputs/tables/f_sps_medium_budget_benchmark_summary.json`
- Planned cases: `45`
- Executed cases: `8`
- Skipped cases: `37`
- All executed losses finite: `true`
- Executed paths include `free_log_sigma_pinn`, `white_box_vo2_sigma_pinn`, `white_box_vo2_sigma_fourier`, and `f_sps_pinn` labels.
- Best executed relative `G` error remains from `free_log_sigma_pinn` in this bounded subset.
- This does not support an F-SPS-PINN superiority claim.

Generated ignored figures:

- `outputs/figures/high_throughput_sci/dense_profile_landscape.png`
- `outputs/figures/high_throughput_sci/profile_uncertainty_intervals.png`
- `outputs/figures/high_throughput_sci/recoverability_phase_diagram.png`
- `outputs/figures/high_throughput_sci/protocol_actual_validation.png`
- `outputs/figures/high_throughput_sci/weighted_protocol_objective.png`
- `outputs/figures/high_throughput_sci/statistical_robustness_boxplot.png`
- `outputs/figures/high_throughput_sci/f_sps_medium_budget_benchmark.png`

## Supported Claims

- The project now has broader synthetic numerical evidence for constrained `gamma_sub` recoverability across protocol, prior-width, observation-count, noise, and seed axes.
- The manuscript should keep `gamma_sub` inversion conditional on fixed or tightly bounded switching/conductivity priors.
- `T_sw` mismatch remains the central reviewer-facing limitation and should be emphasized.
- F-SPS-PINN training paths are executable and testable, but current bounded evidence routes them to appendix/future work.

## Forbidden Claims

- No measured experimental validation.
- No full 3D device simulation.
- No sparse-port unique full hidden-field recovery.
- No unconditional joint identifiability of `gamma_sub`, `T_sw`, `tau_m`, `sigma_on0`, or `eta_A`.
- No F-SPS-PINN, Fourier, dynamic-gate, or white-box VO2 superiority claim from this pack.

## Remaining Gaps

- Dense high-throughput profile is response-surface evidence, not a full 41x61 or 61x81 simulator re-run.
- Statistical robustness used 10 seeds for CPU budget, not the prompt target of 20.
- F-SPS medium-budget executed a bounded subset of the planned 45-case matrix.
- Real experimental validation, 3D device physics, and independent `T_sw` calibration are still outside the current repository evidence.

## Next Recommendation

Move to manuscript figure/table drafting and claim-boundary tightening. Do not expand F-SPS-PINN until the constrained `gamma_sub` manuscript draft is assembled, unless a separate method-development branch is explicitly opened.

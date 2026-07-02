# ODE Spot-Check Manuscript Lock And Quasi-2D Preflight Report

## Repository

- Branch: `main`
- Final commit hash: not embedded in this file because this task is required to be a single final commit; Git commit hashes are content-derived. The exact final SHA is reported in the final Codex response and in GitHub history for the commit containing this report.

## Changed Files

- `.gitignore`
- `DATASET_REGISTRY.md`
- `EXPERIMENT_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `NEXT_ACTIONS.md`
- `PROJECT_STATE.md`
- `RESEARCH_LOG.md`
- `configs/gamma_sub_tsw_tolerance_ode_spotcheck.yaml`
- `configs/gt_quasi_2d_phase_transition_preflight.yaml`
- `configs/pinn_quasi_2d_residual_preflight.yaml`
- `docs/codex_reports/ode_spotcheck_manuscript_lock_and_quasi_2d_preflight_report.md`
- `docs/literature/literature_anchored_quasi_2d_structures.md`
- `docs/literature/manual_digitization_boundary.md`
- `docs/manuscript/conclusion_v1.md`
- `docs/manuscript/discussion_v1.md`
- `docs/manuscript/figure_captions_v1.md`
- `docs/manuscript/introduction_v1.md`
- `docs/manuscript/limitations_v1.md`
- `docs/manuscript/methods_v1.md`
- `docs/manuscript/related_work_v1.md`
- `docs/manuscript/results_v1.md`
- `docs/manuscript/reviewer_defense_matrix.md`
- `docs/manuscript/table_captions_v1.md`
- `docs/manuscript/title_abstract_keywords.md`
- `docs/modeling/quasi_2d_phase_transition_device_model.md`
- `docs/paper/final_claim_matrix.md`
- `docs/paper/final_figure_list.md`
- `docs/paper/final_table_list.md`
- `docs/paper/limitations_locked_v1.md`
- `docs/paper/methods_narrative_locked_v1.md`
- `docs/paper/quasi_2d_extension_claim_boundary.md`
- `docs/paper/results_narrative_locked_v1.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`
- `outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_cases.csv`
- `outputs/tables/gamma_sub_tsw_tolerance_ode_spotcheck_summary.json`
- `outputs/tables/gt_quasi_2d_phase_transition_preflight_summary.json`
- `outputs/tables/pinn_quasi_2d_residual_preflight_summary.json`
- `outputs/tables/quasi_2d_literature_source_registry.json`
- `scripts/audit_gamma_sub_tsw_tolerance_ode_spotcheck.py`
- `scripts/audit_pinn_quasi_2d_residual_preflight.py`
- `scripts/build_reviewer_defense_matrix.py`
- `scripts/run_gt_quasi_2d_phase_transition_preflight.py`
- `tests/test_gamma_sub_tsw_tolerance_ode_spotcheck.py`
- `tests/test_gt_quasi_2d_phase_transition_preflight.py`
- `tests/test_pinn_quasi_2d_residual_preflight.py`
- `tests/test_reviewer_defense_matrix.py`

## Validation Commands

Results: dedicated new tests passed (`5 passed`), prior-pack tests passed (`9 passed`), and full pytest passed (`124 passed`).

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_tsw_tolerance_ode_spotcheck.py tests/test_reviewer_defense_matrix.py tests/test_gt_quasi_2d_phase_transition_preflight.py tests/test_pinn_quasi_2d_residual_preflight.py
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_tsw_calibration_tolerance_sweep.py tests/test_gamma_sub_calibration_protocol_disentanglement.py tests/test_gamma_sub_calibrated_protocol_robustness_final.py tests/test_literature_targeted_curve_extraction_attempt.py
.\.venv\Scripts\python.exe -m pytest
```

## ODE Spot-Check Key Results

- `num_ode_backed_cases`: `270`
- `all_cases_simulator_backed`: `True`
- `all_finite_results`: `True`
- `median_error_by_calibration_error`: `{'0.04': 0.1111111111111111, '0.1': 0.1111111111111111, '0.2': 0.2222222222222222}`
- `success_rate_by_calibration_error`: `{'0.04': 0.8111111111111111, '0.1': 0.8, '0.2': 0.4666666666666667}`
- `whether_0p1K_threshold_supported_by_ode_spotcheck`: `True`
- `whether_response_surface_tolerance_claim_needs_qualification`: `False`

Manuscript sentence: The ODE-backed synthetic spot-check supports the 0.1 K tolerance threshold under the configured <=15% median-error criterion, but it remains a benchmark-specific audit threshold rather than an experimental calibration requirement.

## Manuscript Draft Package

Generated files under `docs/manuscript/` include title/abstract/keywords, introduction, related work, methods, results, discussion, limitations, conclusion, figure captions, table captions, and reviewer-defense matrix.

## Reviewer-Defense Matrix Summary

The matrix covers black-box fitting, full hidden fields, `T_sw` calibration, 0.1 K tolerance, protocol-vs-calibration gain, F-SPS scope, absence of experiment, external-curve blocking, value of 1D synthetic benchmark, relation to FEM/full multiphysics, and quasi-2D preflight limits.

## Literature Source Registry Summary

The quasi-2D structure registry binds: `vo2_phase_field_slab`, `vo2_localized_heater_strip`, `vo2_sin_threshold_switch`, `nbo2_threshold_closure`, and `generic_2d_pinn_phase_change`. Each source is used as model motivation only, not experimental validation.

## Quasi-2D Model Equations And Assumptions

The quasi-2D model uses in-plane electric potential, Joule heating, heat equation with `gamma_sub` substrate sink, phase/order parameter relaxation, optional vacancy drift-diffusion, and terminal current integral. It is thickness-averaged and sparse-port observable only.

## Generated Quasi-2D Benchmark Cases

- Cases: `['uniform_strip', 'localized_hotspot', 'defect_seeded_filament', 'lateral_cooling_gradient']`
- `all_fields_finite`: `True`
- `all_observables_finite`: `True`
- `ready_for_residual_preflight`: `True`

Generated `.npz` arrays and PNG figures are reproducible generated artifacts and are not intended as committed manuscript evidence.

## Residual Preflight Results

- `all_residuals_finite`: `True`
- `boundary_losses_finite`: `True`
- `terminal_current_integral_finite`: `True`
- `whether_ready_for_future_2d_training`: `True`
- `whether_2d_inverse_claim_allowed`: `False`

## Claim Boundary

- Main manuscript claim changed: No.
- Frozen GT modified: No.
- External data fabricated: No.

## Supported SCI Claims

- Port-only full hidden-field recovery is ill-posed in the current synthetic benchmark.
- `gamma_sub` is a reduced inverse target under fixed or tightly bounded priors.
- `T_sw` calibration dominates recoverability; protocol design is secondary and qualified.
- The 0.1 K threshold is a benchmark-specific synthetic audit threshold, supported by ODE spot-check under the configured criterion.
- Quasi-2D preflight is feasible as a supplementary forward/residual extension.

## Forbidden Claims

- Experimental validation.
- Sparse-port unique full hidden-field recovery.
- Unconditional `gamma_sub` identifiability.
- 2D inverse diagnosis solved.
- F-SPS-PINN performance superiority.
- External curve fitting without provenance-backed digitized curve data.

## Remaining Gaps

- Manuscript still needs human polishing and journal-specific formatting.
- External literature curves remain blocked until provenance-backed digitized tables exist.
- Quasi-2D extension is not yet a full training or inverse-identification result.

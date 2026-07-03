# Stiffness Continuation Phase-Field Alignment And Submission Positioning Report

## Repository

- Branch: `main`
- Final commit hash: not embedded in this file because this task is required to be one final commit; Git commit hashes are content-derived. The exact final SHA is reported in the final Codex response and GitHub history.

## Scope

This pack adds supplementary reviewer-defense evidence for a synthetic numerical digital-twin manuscript. It does not modify frozen Ground Truth v1.1, fabricate external data, promote the phase-field smoke benchmark to a main-text core experiment, or claim a full stiff-transfer-learning PINN reproduction.

Google Drive was not accessed because the repository-local prompt, paper registry, and literature digest were sufficient for this bounded implementation.

## Changed Files

- `.gitignore`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `RESEARCH_LOG.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `configs/phase_transition_stiffness_continuation_audit.yaml`
- `configs/phase_field_inverse_alignment_smoke.yaml`
- `scripts/audit_phase_transition_stiffness_continuation.py`
- `scripts/audit_phase_field_inverse_alignment_smoke.py`
- `tests/test_phase_transition_stiffness_continuation.py`
- `tests/test_phase_field_inverse_alignment_smoke.py`
- `outputs/tables/phase_transition_stiffness_continuation_audit_summary.json`
- `outputs/tables/phase_transition_stiffness_continuation_audit_cases.csv`
- `outputs/tables/phase_field_inverse_alignment_smoke_summary.json`
- `outputs/tables/phase_field_inverse_alignment_smoke_cases.csv`
- `docs/paper/journal_positioning_matrix.md`
- `docs/paper/novelty_gap_map.md`
- `docs/paper/sci_two_three_zone_gap_assessment.md`
- `docs/manuscript/related_work_v1.md`
- `docs/manuscript/discussion_v1.md`
- `docs/manuscript/limitations_v1.md`
- `docs/manuscript/reviewer_defense_matrix.md`
- `docs/paper/final_claim_matrix.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`
- `docs/project_state/file_inventory.md`
- `docs/codex_reports/stiffness_continuation_phasefield_alignment_and_submission_positioning_report.md`

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase_transition_stiffness_continuation.py tests/test_phase_field_inverse_alignment_smoke.py
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_tsw_tolerance_ode_spotcheck.py tests/test_gt_quasi_2d_phase_transition_preflight.py tests/test_pinn_quasi_2d_residual_preflight.py tests/test_reviewer_defense_matrix.py
.\.venv\Scripts\python.exe -m pytest
```

## Stiffness Continuation Key Results

- Cases: `180`
- All finite: `True`
- Finite rate by width: `{'0.5': 1.0, '1.0': 1.0, '2.0': 1.0, '3.0': 1.0, '4.0': 1.0}`
- Residual median by width: `{'0.5': 0.24733241647481918, '1.0': 0.071906678378582, '2.0': 0.028638378717005253, '3.0': 0.023035665974020958, '4.0': 0.020793603733181953}`
- Continuation gain by width: `{'0.5': 1.5904571276210493, '1.0': 1.568627480776724, '2.0': 1.5267176767546673, '3.0': 1.4869888295639653, '4.0': 1.4492753201697213}`
- Fourier feature gain by width: `{'0.5': 1.0576589823818656, '1.0': 0.8970262191798665, '2.0': 0.6772014520659121, '3.0': 0.579581392810794, '4.0': 0.5418687144650373}`
- Sharpest width with finite residuals: `0.5`
- Stiffness-cliff claim supported: `True`

Interpretation: the residual proxy rises sharply as transition width narrows, supporting a phase-transition stiffness defense. Continuation is helpful in this preflight. Fourier features are a possible stability aid but are not uniformly beneficial and cannot support a superiority claim.

## Phase-Field Inverse Alignment Key Results

- Cases: `27`
- All finite: `True`
- Median relative error for M: `0.04331110242687686`
- Success rate at relative error <= 0.1: `0.8148148148148148`
- Noise sensitivity: `{'0.0': 0.04309131312689707, '0.01': 0.03330068362918848, '0.03': 0.11477521232942389}`
- Phase-field inverse alignment supported: `True`

Interpretation: the small Allen-Cahn full-field-anchor smoke benchmark supports related-work alignment with phase-field inverse PINN literature. It is not sparse-port inversion and should remain supplementary.

## Journal Positioning Assessment

A third-zone SCI computational/method paper is plausible if the claim remains narrow: sparse-port identifiability audit, target-space reduction, and calibration-gated constrained `gamma_sub` inversion. A second-zone edge submission remains riskier because the repository still lacks real experimental data or provenance-backed external curve fitting.

## Supported SCI Claims

- Phase-transition cliffs are valid residual-stiffness stress tests in supplementary evidence.
- Continuation can be discussed as a stability aid in this preflight.
- The project aligns with phase-field inverse PINN literature at the parameter-inversion paradigm level.
- The main claim remains calibration-gated constrained `gamma_sub` inversion in a one-dimensional synthetic numerical digital-twin benchmark.

## Forbidden Claims

- Full stiff-transfer-learning reproduction.
- F-SPS-PINN or Fourier-feature superiority.
- Phase-field smoke benchmark as main-text sparse-port evidence.
- Experimental validation or direct device replication.
- Sparse-port full hidden-field recovery.

## Remaining Gaps

- Manuscript still needs final figure/table assembly and human polishing.
- External curve fitting remains blocked without provenance-backed digitized numerical data.
- Second-zone edge positioning still needs either real experiment, provenance-backed external curve fit, or a stronger dedicated method paper.

## Frozen GT Modified

No.

## External Data Fabricated

No.

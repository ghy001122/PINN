# Final Figure Literature Lock And Stiffness 2D Story Report

## Repository

- Branch: `main`
- Base commit before this task: `dccdd14e9dbf91b1172e93c5791e26e167f5571c`
- Final commit hash: reported in the final Codex response and GitHub history. A Git commit hash is content-derived and cannot be embedded exactly inside the same single commit that contains this file.

## Scope

This task locks final supplementary figure/story evidence for a synthetic numerical digital-twin manuscript. It does not revise frozen Ground Truth v1.1, fabricate external data, claim F-SPS/Fourier superiority, claim continuation solved stiffness, or alter the main calibration-gated constrained `gamma_sub` line.

## Changed Files

- `.gitignore`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `RESEARCH_LOG.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/literature/drive_and_web_literature_evidence_lock.md`
- `scripts/build_stiffness_2d_story_figures.py`
- `tests/test_stiffness_2d_story_figures.py`
- `outputs/tables/stiffness_2d_story_figure_manifest.json`
- `docs/manuscript/related_work_v1.md`
- `docs/manuscript/results_v1.md`
- `docs/manuscript/discussion_v1.md`
- `docs/manuscript/limitations_v1.md`
- `docs/manuscript/figure_captions_v1.md`
- `docs/manuscript/reviewer_defense_matrix.md`
- `docs/manuscript/abstract_final_candidate.md`
- `docs/manuscript/cover_letter_draft.md`
- `docs/manuscript/submission_checklist.md`
- `docs/paper/final_claim_matrix.md`
- `docs/paper/final_figure_list.md`
- `docs/paper/final_table_list.md`
- `docs/paper/final_submission_figure_table_claim_lock_v2.md`
- `docs/paper/stiffness_and_quasi_2d_storyboard.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`
- `docs/project_state/file_inventory.md`
- `docs/codex_reports/final_figure_literature_lock_and_stiffness_2d_story_report.md`

## Validation Commands And Results

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_stiffness_2d_story_figures.py tests/test_phase_transition_stiffness_continuation.py tests/test_phase_field_inverse_alignment_smoke.py tests/test_gt_quasi_2d_phase_transition_preflight.py tests/test_pinn_quasi_2d_residual_preflight.py tests/test_reviewer_defense_matrix.py
```

Result: `6 passed`.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Result: `127 passed`.

A focused rerun after manifest path normalization also passed: `tests/test_stiffness_2d_story_figures.py` -> `1 passed`.

## GitHub CI Status

No GitHub CI status was returned in the local environment. Validation above is local Windows `.venv` pytest validation.

## Literature Evidence Lock Summary

- Seiler 2025 is locked as Drive-supported rationale for low-stiff to high-stiff continuation / transfer ideas. It does not prove full STL-PINN reproduction.
- Zhao 2025 is locked as Drive-supported phase-field inverse PINN alignment. It does not prove sparse-port phase-field recovery.
- Web sources are locked for phase-change moving-interface PINN and diffuse-interface / enthalpy phase-change background.
- Shi and Chen 2018 is locked for VO2 phase-field/current-driven IMT physical motivation.
- Lee 2024 and Jurj 2026 are locked for compact memristor PINN and physics-regularized surrogate positioning only.

## Stiffness Figure Key Results

- Cases: `180`
- All finite: `True`
- Stiffness cliff ratio sharpest/widest: `11.894639315460832`
- Stiffness cliff supported: `True`
- Fourier gain not uniform: `True`

Generated ignored figures:

- `outputs/figures/stiffness_residual_vs_transition_width.png`
- `outputs/figures/stiffness_continuation_gain_vs_width.png`
- `outputs/figures/stiffness_fourier_gain_caution.png`

## Phase-Field And Quasi-2D Story Key Results

- Phase-field cases: `27`
- Phase-field all finite: `True`
- Median relative M error: `0.04331110242687686`
- Success rate <= 0.1: `0.8148148148148148`
- Quasi-2D forward cases: `4`
- Quasi-2D fields finite: `True`
- Quasi-2D residuals finite: `True`
- 2D inverse claim allowed: `False`

Generated ignored figures:

- `outputs/figures/phase_field_m_true_vs_estimated.png`
- `outputs/figures/phase_field_noise_sensitivity.png`

## Why 2D Remains Supplementary

The quasi-2D results are forward/residual computability checks, not inverse recovery. They increase physical-depth discussion and show a plausible extension path, but sparse-port terminal observations still cannot uniquely recover full 2D hidden fields without additional observability.

## Why Continuation Is Algorithmic Defense But Not Full STL

The stiffness audit shows that narrowing the transition width increases residual stress and that continuation reduces the residual proxy in this lightweight preflight. It does not implement or benchmark a full stiff-transfer-learning curriculum, and Fourier gain is explicitly non-uniform.

## Frozen GT Modified

No.

## External Data Fabricated

No.

## Remaining Gaps For SCI 2/3 Zones

Third-zone SCI: plausible with narrow framing around synthetic sparse-port identifiability, target-space reduction, and calibration-gated `gamma_sub` inversion.

Second-zone edge SCI: still risky because there is no measured device dataset, no provenance-backed external curve fit, no proven F-SPS superiority, and no solved 2D inverse diagnosis.

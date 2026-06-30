# SCI Manuscript Evidence Consolidation Report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this task: `3463a295e29c76a2f518e838a4fe8f4017edac4d`
- Task type: documentation-only manuscript evidence consolidation
- Benchmark type: synthetic numerical digital-twin benchmark only

## Changed Files

- `CODEX_CONTEXT.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `docs/research_strategy/active_phase.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/file_inventory.md`
- `docs/paper/model_hierarchy_and_claim_boundary.md`
- `docs/paper/equation_variable_registry.md`
- `docs/paper/experiment_to_figure_mapping.md`
- `docs/paper/sci_manuscript_evidence_matrix.md`
- `docs/codex_reports/sci_manuscript_evidence_consolidation_report.md`

## Why The Project Shifted To Manuscript Consolidation

The current repository already contains enough synthetic numerical evidence to support a focused method paper on sparse-port inverse identifiability and constrained reduced `gamma_sub` inversion. Additional F-SPS-PINN small-run checks are useful engineering work, but the v2 Fourier ablation did not prove performance superiority. Continuing to expand F-SPS-PINN now would dilute the strongest paper story.

The conservative path is to consolidate the evidence chain, define allowed and forbidden claims, and prepare figure/table routing for a high-quality SCI manuscript.

## Main Paper Claim

The proposed main claim is:

- sparse-port full hidden-field recovery is ill-posed in the current one-dimensional benchmark;
- identifiability-guided target-space reduction is required;
- `gamma_sub` is a conditionally identifiable reduced inverse target when switching, defect, conductivity, and area priors are fixed or tightly bounded;
- `T_sw` is the most dangerous confounder and must be explicitly controlled.

## F-SPS-PINN Placement

F-SPS-PINN architecture MVP, v2 smoke training, v2 small-run baseline, phase-transition stress preflight, and Fourier on/off ablation should be placed in appendix, discussion, or future-work material for the current manuscript.

They should not be used as the main performance claim, and they do not replace the constrained `gamma_sub` manuscript line.

## Validation

Command run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_constrained.py tests/test_gamma_sub_continuous_refinement.py tests/test_pinn_inverse_v2_fourier_ablation.py
```

Result:

- `5 passed in 8.91s`

## Boundary Checks

- Modified frozen Ground Truth v1.1: No.
- New training experiments: No.
- New generated large outputs: No.
- Claimed F-SPS-PINN performance superiority: No.
- Claimed real VO2/NbO2 experimental validation: No.
- Claimed sparse-port unique full hidden-field recovery: No.

## Next Step

Draft the manuscript outline and figure plan from `docs/paper/sci_manuscript_evidence_matrix.md`, keeping constrained `gamma_sub` inversion as the mainline and F-SPS-PINN as supplementary method-development evidence.
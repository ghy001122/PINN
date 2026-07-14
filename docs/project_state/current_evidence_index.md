# Current Evidence Index

This is the compact routing index. It is not a new status dashboard: current status remains in `PROJECT_STATE.md`.

## Locked Mainline

- Evidence lock: commit `d1121e16fa5015a297da468e3e6f0504b9e97d17`.
- Detailed lock: `docs/paper/gamma_sub_evidence_lock.md`.
- Current claim matrix: `docs/paper/final_claim_matrix.md`.
- Final figures/tables: `docs/paper/final_figure_list.md`, `docs/paper/final_table_list.md`.
- Reproduction summary: `outputs/tables/gamma_sub_evidence_lock_summary.json`.
- Quick reproduction: `docs/project_state/reproduction_quickstart.md`.

| Claim block | Status | Primary evidence |
| --- | --- | --- |
| Sparse-port complete hidden-field recovery boundary | `supported` for the frozen configured benchmark | `outputs/tables/pinn_identifiability_summary.json`; Figure 1 |
| Constrained off-grid `gamma_sub` recovery | `qualified_supported` under fixed/tight priors | continuous-refinement JSON/CSV; Figure 2 |
| `T_sw` calibration gate | `qualified_supported` and benchmark-specific | confounding/tolerance/ODE spot-check summaries; Figures 2–3 |
| Conditional robustness and failed wide-prior region | `qualified_supported` | statistical robustness and paper-readiness summaries; Figure 6 |
| Protocol after calibration | `qualified_supported` | 720-case sequential validation; Figure 5 |

## Extension Ledger

| Gate | Status | Boundary |
| --- | --- | --- |
| P0 | `qualified_supported` | reduced synthetic topology/material semantics |
| P1 | `failed_but_informative` | field-anchored cross-family training; interface/scaling gate fails |
| P2 | `failed_but_informative` | local rank/block audit; thermal/full-rank gate fails |
| P3 | `qualified_supported` | local rank `1 -> 3` for a three-parameter conductivity basis only |
| P4 | `forbidden` | no full STL or universal Fourier/F-SPS claim |
| External anchor | `forbidden` until Priority D completes | no repository external fit/holdout artifact yet |

## Current Manuscript Surfaces

- Manuscript fragments: `docs/manuscript/`.
- Reviewer defense: `docs/manuscript/reviewer_defense_matrix.md`.
- Equation authority: `docs/method_equations.md`.
- Parameter provenance: `docs/parameter_prior_registry.md` and `docs/physics/literature_prior_registry.md`.
- Primary-source decision log: `docs/literature/primary_source_decision_log_2026-07-14.md`.
- Current comprehensive audit: `docs/codex_reports/project_history_workflow_innovation_audit_f14c068.md`.

The root registries and `RESEARCH_LOG.md` are cumulative history. Load them only when a specific older run must be traced.

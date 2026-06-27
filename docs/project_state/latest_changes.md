# Latest changes

## Paper-readiness gamma_sub robustness pack

Scope:

- Add manuscript-defense documents for model hierarchy, equation variables, and
  experiment-to-figure mapping.
- Add a lightweight audit for off-grid `gamma_sub` localization and
  observation-count sensitivity.
- Keep frozen Ground Truth v1.1 and existing v0/v1/v1.1, identifiability,
  confounding, and constrained-inversion evidence unchanged.

Changed:

- Added `docs\paper\model_hierarchy_and_claim_boundary.md`.
- Added `docs\paper\equation_variable_registry.md`.
- Added `docs\paper\experiment_to_figure_mapping.md`.
- Added `scripts\audit_gamma_sub_paper_readiness.py`.
- Added `tests\test_gamma_sub_paper_readiness.py`.
- Added `outputs\tables\gamma_sub_paper_readiness_summary.json`.
- Added `outputs\tables\gamma_sub_observation_sensitivity.csv`.
- Added `outputs\tables\gamma_sub_offgrid_summary.csv`.
- Added `docs\gamma_sub_paper_readiness_report.md`.
- Added `docs\codex_reports\gamma_sub_paper_readiness_report.md`.
- Updated project state, registries, and reproducibility notes.

Result:

Off-grid `gamma_sub = 4.62e8` was localized with nearest-grid relative error
`0.025974025974025976` and refined relative error `4.054410066065334e-05`.
Nominal recovery stayed exact for `n_obs = 8, 16, 32, 64`; `T_sw` remained the
most dangerous confounder.

## Recent history index

For complete historical details, use:

- chronological findings: `RESEARCH_LOG.md`
- experiment outputs and runners: `EXPERIMENT_REGISTRY.md`
- dataset and lightweight evidence: `DATASET_REGISTRY.md`
- generated figures: `FIGURE_REGISTRY.md`
- file ownership and reports: `docs\project_state\file_inventory.md`
- stage reports: `docs\codex_reports\`

## Documentation structure cleanup

Scope:

- Reduce repeated status material in the explanatory Markdown files.
- Keep `CODEX_CONTEXT.md` plus `docs\research_strategy\active_phase.md` as the
  low-token first-read pair.
- Keep `docs\research_strategy\context_loading_policy.md` as the complete Tier
  0 through Tier 4 loading rule.
- Do not delete referenced context files without a stronger uniqueness audit.

Changed:

- `PROJECT_STATE.md`: shortened to current phase, frozen benchmark, current
  evidence, boundary, and pointers to registries.
- `docs\project_state\latest_changes.md`: converted from a full historical
  changelog into a recent-change summary plus index.
- `AGENTS.md`: keeps top-level engineering rules and points to the context
  loading policy for detailed Codex workflow.
- `docs\codex_reports\local_codex_context_integration_report.md`: now records
  concrete verification results from the context-integration task.

## Local Codex context workflow integration

Added the low-token context workflow files and compressed literature/reference
notes. Frozen Ground Truth v1.1 files, source code, configs, tests, large
generated data, and generated figures were not modified in that documentation
integration task.
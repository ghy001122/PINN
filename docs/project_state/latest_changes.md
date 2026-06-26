# Latest changes

## Literature-backed constrained gamma_sub inversion

Scope:

- Implement constrained scalar `gamma_sub` inversion under literature-guided and
  engineering-prior bounds.
- Keep `D_v0`, `mu_v0`, frozen Ground Truth v1.1 data, frozen configs, metrics,
  manifest, equations, and default parameters unchanged.
- Use `T_sw`, `tau_m`, `sigma_on0`, and `eta_A` only as bounded confounders in a
  prior-width sweep.

Changed:

- Added `configs\gamma_sub_constrained_inversion.yaml`.
- Added `scripts\invert_gamma_sub_constrained.py`.
- Added `tests\test_gamma_sub_constrained.py`.
- Added `docs\literature_gamma_sub_evidence_chain.md`.
- Added `docs\parameter_prior_registry.md`.
- Added `docs\gamma_sub_constrained_inversion_report.md`.
- Added `docs\codex_reports\gamma_sub_constrained_inversion_report.md`.
- Added `outputs\tables\gamma_sub_constrained_inversion_summary.json`.
- Added `outputs\tables\gamma_sub_prior_width_sweep.csv`.
- Updated project state, registries, and reproducibility notes.

Result:

Clean nominal `gamma_sub` was recovered with relative error `0.0`. The maximum
tested relative error was `1.2222222222222223`, and `T_sw` was the most dangerous
confounder.

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

## Recent history index

For complete historical details, use:

- chronological findings: `RESEARCH_LOG.md`
- experiment outputs and runners: `EXPERIMENT_REGISTRY.md`
- dataset and lightweight evidence: `DATASET_REGISTRY.md`
- generated figures: `FIGURE_REGISTRY.md`
- file ownership and reports: `docs\project_state\file_inventory.md`
- stage reports: `docs\codex_reports\`

## Local Codex context workflow integration

Added:

- `CODEX_CONTEXT.md`
- `docs\research_strategy\active_phase.md`
- `docs\research_strategy\context_loading_policy.md`
- `docs\research_strategy\context_index.md`
- `docs\research_strategy\current_research_handoff.md`
- `docs\research_strategy\codex_workflow_rules.md`
- `docs\research_strategy\next_task_literature_backed_constrained_gamma_sub.md`
- `docs\literature_notes\pinn_phase_change_literature_digest.md`
- `docs\literature_notes\gamma_sub_evidence_digest.md`
- `references\project_sources\README.md`
- `references\papers\PAPER_REGISTRY.md`
- `docs\codex_reports\local_codex_context_integration_report.md`

Modified:

- `AGENTS.md`: adds the Codex low-token context workflow.
- `README.md`: documents the current active phase and first-read files.
- `PROJECT_STATE.md`: updates the current phase and evidence-chain context.
- `NEXT_ACTIONS.md`: records the constrained `gamma_sub` next task and deferred
  method enhancements.
- `RESEARCH_LOG.md`: records the local reference-pack integration.
- `EXPERIMENT_REGISTRY.md`: registers the documentation-only context workflow.
- `DATASET_REGISTRY.md`: records that no raw reference-pack data or large files
  were copied.
- `FIGURE_REGISTRY.md`: records that no figures were generated.
- `docs\project_state\repo_tree.md`, `file_inventory.md`,
  `latest_changes.md`, and `reproducibility.md`: update the state snapshot.

Deleted:

- None.

Frozen Ground Truth v1.1 files, source code, configs, tests, large generated
data, and generated figures were not modified.

# Context Index

## First Read

1. `LIVE_WORKSPACE.md`
2. `CODEX_CONTEXT.md`
3. `docs/research_strategy/active_phase.md`
4. `docs/research_strategy/context_loading_policy.md`

## Current Authority

- `AGENTS.md` and nested instruction files: behavior, ethics, engineering, and evidence rules.
- `PROJECT_GOAL.md`: stable R1/R2/R3 delivery contract.
- `PROJECT_STATE.md`: single current fact snapshot.
- `NEXT_ACTIONS.md`: single active task.
- `docs/research_strategy/pinn_phase_change_q2_sci_execution_guide.md`: complete research strategy, phase ladder, downgrade rules, and writing guide.
- `docs/research_strategy/phase1_e0_single_implementation_physics_validation.md` and `configs/geophase_phase1_e0_single_implementation_physics_validation.yaml`: active zero-computation E0 route and next authorization boundary.
- `docs/research_strategy/phase1_geophase_2p5d_reference_v2_contract.md`: inherited Phase 1-v2 S2 technical contract.
- `configs/geophase_phase1_v2_s2_reference_source_corrected_v3.yaml` and `configs/geophase_phase1_v2_formal_manifest_source_corrected_v3.yaml`: current machine-readable S2 and 63-item scientific-inventory locks.
- `configs/geophase_phase1_s1_diffusive_sensitivity_mve.yaml` and `configs/qiu_same_device_thermal_holdout_audit.yaml`: bounded non-blocking auxiliary contracts.
- `configs/qiu_vo2_phase1_source_contract_v3.yaml`: active Qiu source facts and 15.8 V qualitative high-bias correction; the older source contract is historical.
- `docs/research_strategy/sci_delivery_pipeline.md`: reusable evidence lifecycle.
- `docs/project_state/current_evidence_index.md`: current/historical/candidate/forbidden evidence routing.

## Task Routing

- Physics, equations, materials, geometry, or provenance: load `docs/method_equations.md`, the Phase 1-v2 config/manifest, the source-only contract, and only the relevant physics/provenance files.
- Code or tests: load the applicable nested `AGENTS.md`, config, implementation, and focused tests.
- Claims or manuscript: load `docs/project_prompts/critical_research_mode.md`, `docs/paper/final_claim_matrix.md`, and only the relevant manuscript component.
- Historical reproduction or reviewer defense: use `docs/archive/README.md`, registries, and the named report/artifact. Archived documents never authorize current work.
- Literature: use source decision logs, `references/papers/PAPER_REGISTRY.md`, and only the necessary source note; do not load full papers by default.

## Cumulative Indexes

`RESEARCH_LOG.md`, `EXPERIMENT_REGISTRY.md`, `DATASET_REGISTRY.md`, `FIGURE_REGISTRY.md`, and `docs/codex_reports/` are chronological provenance. Read targeted entries only.

## Durable Context

`docs/research_strategy/durable_project_memory.md` stores stable project facts and pitfalls. `docs/research_strategy/memory_policy.md` governs authority and privacy. Neither overrides current Git evidence or the authority chain.

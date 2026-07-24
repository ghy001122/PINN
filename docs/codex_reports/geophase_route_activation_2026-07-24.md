---
task_name: geophase_route_activation_e0_preregistration_and_consistency_closeout
base_sha: a3095e1928c305ade13a1549cd950c9412a449ad
final_sha: supplied_in_user_handoff_after_single_commit
branch: main
tests:
  - tests/test_geophase_e0_preregistration.py
  - tests/test_project_governance.py
  - scripts/audit_project_governance.py
reproduction_commands:
  - ./.venv/Scripts/python.exe -m pytest tests/test_geophase_e0_preregistration.py tests/test_project_governance.py -q
  - ./.venv/Scripts/python.exe -m pytest -q
  - ./.venv/Scripts/python.exe scripts/audit_project_governance.py
  - git diff --check
frozen_gt_modified: false
evidence_type: documentation
claim_status: supported
supported_claims:
  - the user-authorized route change, live capability inventory, equation contract, E0 preregistration, and governance synchronization exist
forbidden_claims:
  - successful 2.5D reference or GeoPhase PINN
  - architecture or homotopy superiority
  - geometry generalization or observation-quotient recovery
  - Qiu quantitative reproduction or experimental validation
  - VO2-to-NbO2 zero-shot generalization
goal_distance_change: the repository now has one coherent GeoPhase route and a fail-closed E0 starting contract, but no new scientific result
claim_changes:
  - no historical scientific status changed
  - G0-G5 candidate claims were added as forbidden pending direct evidence
new_blockers:
  - the x-y K-state reference solver and its formal evidence do not exist
  - all PINN, inverse, and cross-model work remains upstream-blocked by E0
next_single_priority: implement and validate the independent G0/E0 2.5D reference solver
disposition: continue
---

# GeoPhase Route Activation, E0 Preregistration, And Consistency Closeout

## Scope And Manuscript Use

The task replaced the obsolete submission-lock authorization with the user's
revised requirement: PINN must be a positive core method, phase-transition
physics must drive the method, and the final structure must resolve a real
two-dimensional geometry. The adopted candidate is `GeoPhase-OQ-PINN`, with a
Qiu-inspired x-y VO2 benchmark and a Chen-inspired SnSe/NbO2 auxiliary
cross-model route.

This round is governance, equation, preregistration, and final consistency
work. The 2026-07-25 closeout distinguishes route-specific historical
stops, current-phase execution blocks, future authorization, and manuscript
claim prohibitions. It produces no solver, training, inverse, or
experimental evidence.

## Actual Work And Changed Files

Current authority and routing were synchronized in:

- `AGENTS.md`, `PROJECT_GOAL.md`, `CODEX_CONTEXT.md`, `PROJECT_STATE.md`,
  `NEXT_ACTIONS.md`, and `README.md`;
- `docs/research_strategy/active_phase.md`, `context_index.md`,
  `current_research_handoff.md`, `durable_project_memory.md`,
  `innovation_portfolio.md`, and `legacy_document_index.md`;
- `docs/project_state/current_evidence_index.md` and
  `reproduction_quickstart.md`.

The physical/method contract and fail-closed start were added in:

- `docs/research_strategy/geophase_oq_pinn_execution_contract.md`;
- `docs/method_equations.md`;
- `configs/geophase_e0_2p5d_reference.yaml`;
- `tests/test_geophase_e0_preregistration.py`.

Manuscript, claim, and literature routing were updated in:

- `docs/manuscript/README.md` and `submission_go_no_go.md`;
- `docs/paper/final_claim_matrix.md`, `final_figure_list.md`, and
  `final_table_list.md`;
- `references/papers/PAPER_REGISTRY.md` and
  `docs/literature/primary_source_decision_log_2026-07-14.md`.

`scripts/audit_project_governance.py`, `EXPERIMENT_REGISTRY.md`, and
`RESEARCH_LOG.md` were synchronized with the new phase. Historical v1/v2
manuscripts, old scientific outputs, and frozen GT were not edited.

## Validation And Reproduction

The targeted E0 preregistration tests verify x-y coordinates, reduced vertical
semantics, Qiu/NbO2 separation, explicit synthetic parameter provenance,
passive K-state selection, fail-closed gates, safe output paths, and equation
routing. Project governance checks phase consistency, required files, link
integrity, claim vocabulary, context size, and frozen hashes.

Validation result:

- combined E0 plus governance pytest: 11 passed;
- final full regression: 447 passed in 280.04 s;
- governance audit: pass_with_manual_review, zero failed checks; the only
  manual surfaces are the pre-existing client rule-loading review and mtime
  review, while all eight frozen GT hashes pass;
- low-token context: 23369 / 24576 bytes;
- current-authority scan: no obsolete submission-lock phase ID, no stale
  no-active-experiment instruction, and no old permanent full-PINN closure;
- git diff --check: pass.

No full scientific experiment was needed because no solver, model, or existing
scientific output changed. The formal E0 command is intentionally absent until
the solver implementation and preflight tests exist.

## Evidence And Claim Boundary

The live audit found reusable Qiu geometry/provenance, conservative FVM/ledger,
VO2/NbO2 constitutive, Fourier/interface, and SVD utilities. It also found that
the revised brainstorm overstated the current implementation inventory: live
`main` has no K-state thermal-memory implementation or transition-localized
GeoPhase mixture of experts. The canonical documents now state this explicitly.

The equation/YAML/route existence is `supported` as an implementation-
governance fact. G0--G5 results remain `forbidden`. The constrained
`gamma_sub`, full-PINN failure, M40/M40R, public-source, and submission-replay
statuses remain historical and unchanged.

## Distance To Definition Of Done

The repository moved from a contradictory state--an upload-locked 1D paper
despite a user requirement for positive 2D PINN evidence--to one coherent,
dependency-ordered research route. The remaining distance is still large:
there is no E0 judge, no positive GeoPhase PINN, no OOD result, no sensitivity-
faithful inverse, no NbO2 cross-model result, and no new manuscript draft.

## New Blockers

- G0 must implement an independent x-y FVM/implicit solver and passive K-state
  reduction without sharing PINN residual code.
- Qiu local parameters remain literature-guided/engineering priors, so E0 is a
  synthetic benchmark rather than a calibrated device model.
- G1--G5 remain fail-closed behind the E0 numerical and conservation gates.

## 2026-07-25 Consistency Audit

The final audit corrected three stale governance semantics. The experiment plan
no longer declares that no scientific experiment is active. Old M44/M40/N0/D0
stop decisions are explicitly scoped to their named contracts instead of being
treated as universal bans. The governance audit now checks G0--G5 and the
current phase-scoped authorization markers rather than using P0--P4 metrics as
the primary active-stage consistency test.

This does not weaken claim gates. Positive GeoPhase results, full STL,
terminal-only arbitrary hidden-field recovery, experimental validation, and
device-grade 3D remain forbidden without direct evidence. Directions outside
G0--G5 require a separately activated, bounded, preregistered future phase.

## Next Single Priority And Disposition

Implement the config-locked G0/E0 reference, add behavioral/conservation/
convergence tests, and run the single formal E0 only after preflights pass.
Disposition: `continue`.

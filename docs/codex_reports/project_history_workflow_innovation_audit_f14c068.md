# Project History, Workflow, And Innovation Audit

## Metadata

- Date: 2026-07-14
- Base SHA: `f14c0680dd7a8a0f5c2fe1738587edbb4502eafd`
- Task class: documentation, governance, literature review, and research planning
- New scientific experiment: no
- Evidence types: existing synthetic numerical evidence plus external primary-literature review
- Frozen GT modified: no
- Machine summary: `outputs/tables/project_history_workflow_innovation_audit_summary.json`

## Executive Findings

1. **The project has enough engineering work for a focused computational paper, but not enough neural-algorithm evidence for a high-impact PINN paper.** At the baseline there are 237 Python files and about 26,180 Python lines, but file volume is not scientific contribution. The independent publishable core is five locked claims and six main figures.
2. **The strongest scientific result is the pivot from failed hidden-field inversion to identifiability-guided target reduction.** Constrained `gamma_sub` recovery is defensible only under calibrated or tightly bounded priors.
3. **The largest manuscript logic gap is the word “PINN.”** The successful mainline is numerical forward simulation plus scalar constrained optimization. The neural branches mainly provide negative/bounded evidence. A neural module needs an economic advantage—amortized speed, uncertainty, assimilation, or OOD performance—before it can be a main innovation.
4. **Priority D remains correct, but its claim must be narrower.** The public Nature Communications VO2 source-data package can support a VO2 literature-family fit/holdout anchor. It cannot validate the frozen Nb/NbOx/V2O5/Ni-inspired mainline or an SnSe/NbO2 device.
5. **The workflow had too many shadow authorities.** A dashboard duplicated `PROJECT_STATE`, an obsolete full handoff duplicated current context, old evidence/figure matrices duplicated the evidence lock, and an old generator could overwrite current claim artifacts. These are now retired or removed, and the generator is hard-disabled.

## Historical Research Audit

| Stage | Scientific outcome | Correct manuscript use | Remaining limitation |
| --- | --- | --- | --- |
| Frozen GT v1.1 | reproducible 1D synthetic electrothermal/defect/state benchmark | controlled inverse-method testbed | not measured data or device-grade multiphysics |
| PINN v0/v1/v1.1 | port-only field recovery remains anchor-dependent/underdetermined | motivation and negative ablation | no successful complete hidden-field PINN |
| Identifiability pivot | terminal signals constrain integrated conductance but not arbitrary fields | main novelty: target reduction before inversion | benchmark-specific, not a universal theorem |
| Constrained `gamma_sub` | exact nominal recovery and bounded off-grid/noise cases under fixed priors | reduced inverse main result | strong `T_sw` and nuisance-prior dependence |
| Confounding/calibration | `T_sw` ridge and benchmark-specific tolerance boundary | calibration-first workflow and reviewer defense | approximately 0.1 K is not a real-device requirement |
| Protocol/robustness | 720-case calibrated sequential result passes; broad stress failure retained | conditional robustness and negative boundary | protocol gain is secondary and not globally optimal |
| OASIS/P0–P4 | P0 semantics and P3 low-rank observability survive; P1/P2 fail; P4 blocked | supplement and future-work gates | no validated new neural solver or full-rank inverse |
| Delivery alignment | five claims, six figures, current claim matrix and reviewer-defense package | manuscript assembly foundation | external anchor and coherent full manuscript absent |

## Claim Audit

### Current mainline

- `supported`: sparse-port complete hidden-field recovery boundary for the frozen configured benchmark.
- `qualified_supported`: reduced `gamma_sub` inversion, calibration gate, conditional robustness, and protocol-after-calibration.
- `failed_but_informative`: P1 strict field/interface training, P2 active inverse, and weak cross-material/non-geometric OOD.
- `forbidden`: project experimental validation, arbitrary 2D field recovery, full STL reproduction, universal Fourier/F-SPS superiority, and full device-grade FEM/3D claims.

No scientific status is upgraded in this audit. The external-anchor wording is narrowed: even a successful Priority D result is a VO2 literature-family comparison, not validation of the frozen mainline material stack.

## Multi-Angle Technical Review

### Neural architecture

The current bottleneck is not network width, depth, Fourier features, or a fashionable operator architecture. It is observability plus residual/coordinate scaling. Vanilla architecture churn would add workload without resolving the inverse information deficit.

The only high-value neural addition before submission would be an **amortized probabilistic `gamma_sub` inverse** trained on declared simulator cases and compared with the scalar optimizer on identical noise, prior, off-grid, and OOD holdouts. It earns a main claim only if it provides calibrated uncertainty or a meaningful inference-time advantage without accuracy loss. Otherwise the honest paper is an identifiability-guided physics-informed digital-twin method paper, not a new PINN architecture paper.

### Algorithm implementation

- P1's interface residual `106.15460205078125` makes loss-weight tuning downstream of a semantics/scaling repair.
- One bounded P1 cycle should test named coordinates, physical faces, manufactured solutions, nondimensional residuals, per-term gradients/conflicts, continuation, and only then mortar coupling.
- P2 must reject rank-deficient released blocks before optimization. Local Jacobian recovery is a preflight, not a nonlinear inverse result.
- Full STL requires Seiler-style shared representation, multiple low-stiffness heads, and evaluated high-stiffness transfer. Current mini/continuation proxies do not satisfy this definition.

### Physics equations and constraints

- VO2 branch hysteresis and NbO2 Poole–Frenkel electrothermal runaway must remain separate constitutive kernels.
- Electrical and thermal topologies must remain explicit; a thermal substrate is not an electrical bypass.
- Every interface/energy residual must be independently computed, dimensionally scaled, and behavior-tested.
- The effective `gamma_sub` is a lumped benchmark parameter. It is not a universal thermal conductivity or measured material constant.

### Physical structure

Liu's coplanar NbOx work supports multi-terminal topology as a practical motivation, but the current segmented result is only a local rank gain for center/width/contrast. The next structure experiment must select one explicit coplanar or vertical topology and a low-dimensional dynamic source/channel basis before attempting inversion.

### Practical value

The near-term practical contribution is a decision workflow:

1. audit identifiability before choosing an inverse target;
2. calibrate the dominant switching nuisance;
3. release only a rank-supported parameter block;
4. report success and failed regions separately;
5. use neural inference only when online speed or uncertainty justifies it.

This is useful for planning real measurements, but it is not yet real-device parameter extraction.

### Paper logic

The paper should contain at most four headline contributions:

1. sparse-port hidden-field identifiability boundary;
2. target reduction to an effective thermal-loss parameter;
3. calibration/confounding recoverability map;
4. conditional robustness plus a provenance-backed external literature-family anchor.

P1/P2/P3/P4 belong in a compact supplementary claim ladder. Putting OASIS, STL, F-SPS, Fourier, full-field recovery, and compact export into the main story would make the manuscript look larger but logically weaker.

## Literature-Backed Decisions

The detailed source record is `docs/literature/primary_source_decision_log_2026-07-14.md`.

- Chen et al. support NbO2 Poole–Frenkel/electrothermal control and thermal-resistance engineering, not cross-family parameter copying.
- Qiu et al. support a VO2 branch-hysteresis lumped electrothermal model and also expose uniform-temperature/fitted-channel assumptions.
- Liu et al. support coplanar/multi-terminal motivation, not full-field inverse recovery.
- Zhang, Sipling, Qiu et al. provide public source data, an explicit RC/electrothermal model, code provenance, and CC BY 4.0 terms; this is the safest Priority D source.
- Seiler defines what a real STL experiment must contain.
- Zhao's phase-field inverse uses numerical/full-field information and cannot be cited as evidence for sparse-terminal phase-field recovery.
- Lee/Jurj/Li support compact, physics-regularized, and composable surrogates, while also reinforcing that a field PINN is not automatically the best tool for terminal-output emulation.

## Workflow And Workspace Changes

### New current authorities

- `docs/research_strategy/sci_delivery_pipeline.md`: reusable state machine, run classes, gate card, failure routing, and context hygiene.
- `docs/project_state/current_evidence_index.md`: compact routing to the locked claim/figure artifacts.
- `docs/research_strategy/innovation_portfolio.md`: ranked innovations with exact claim gates.
- `docs/literature/primary_source_decision_log_2026-07-14.md`: source-to-claim decision record.
- `docs/project_state/reproduction_quickstart.md`: current governance, mainline, and full-regression commands.

### Removed or retired redundancy

- Removed the byte-identical duplicate `docs/gamma_sub_continuous_refinement_report.md`; the canonical report remains under `docs/codex_reports/`.
- Removed the corrupt/obsolete full handoff, duplicate dashboard, completed next-task note, old sprint blueprint, redundant latest-changes file, old archive snapshots, superseded evidence/figure matrices, proposed figure/table files, and duplicate paper narrative fragments. Git history retains provenance.
- Retired `scripts/build_final_submission_figures.py` with a hard failure because its old statuses and outputs could overwrite the current evidence lock.
- Marked root registries and the long reproducibility file as cumulative history; daily work uses the compact index/quickstart.

The governance audit now checks a generic active phase ID instead of hard-coded Priority D/P0–P4 repetition, enforces a 24 KiB current-context budget, checks the short handoff, blocks active Markdown duplicates, and verifies the retired generator guard. The current measured context is 18,663 bytes and the handoff pointer is 405 bytes. Cleanup removed 29 tracked files (230,622 bytes); 616 prior tracked files remain and seven new current-authority artifacts are ready to track, for a projected total of 623.

## Ranked Next Research Plan

1. **Priority D — external anchor:** ingest the Nature source-data package immutably, select one fit protocol and one untouched holdout protocol, document units/license/SHA-256, and apply the existing `<=0.20` metric gates.
2. **Priority M — manuscript:** assemble one coherent manuscript and supplement from the locked five-claim/six-figure chain. Delete no negative evidence; route it to the supplement.
3. **Priority B — one P1 rescue:** dimensionless CV/mortar validity repair under the unchanged strict gate; stop after one budget.
4. **Priority C — rank-first inverse design:** time-window/protocol combinations, full-rank released blocks, nonlinear re-simulation, and bootstrap/profile-likelihood coverage.
5. **Optional neural-value gate:** amortized probabilistic `gamma_sub` inference only if the manuscript still needs a positive neural contribution.
6. **Later:** low-rank dynamic multi-terminal inversion, then canonical STL if P1 passes, then compact export after delivery.

## Validation And Round Close

- Governance audit: `pass_with_manual_review`; no failed checks.
- Targeted governance/refinement/paper-readiness tests: `7 passed`.
- `git diff --check`: passed; line-ending notices are non-failures.
- Full CPU suite: `188 passed in 213.32 s`.
- Frozen GT: hashes and mtimes are unchanged from the pre-task baseline.
- Claim changes: no status upgrade/downgrade; external-anchor wording narrowed.
- Distance to goal: workflow ambiguity and literature-selection risk are reduced; external quantitative evidence and complete manuscript remain open.
- Next single priority: Priority D source-data fit/holdout anchor.
- Disposition: `continue`.

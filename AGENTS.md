# AGENTS.md

## Mission And Delivery Mode

Build a reproducible Python 3.11 research codebase and evidence package for `Q2_SCI_DELIVERY_MODE`: a defensible SCI manuscript draft, submission package, and reviewer-defense package centered on a positive physics-informed neural method for phase-transition devices. The degradable delivery ladder is R1 `HysGeo-Hybrid-PINN` as the minimum route, R2 `GeoPhase-HomoMoE-PINN` as the preferred method upgrade, and R3 observable-subspace/OQ only as a conditional extension. This is a delivery objective, not a promise of journal acceptance. The authoritative goal is [PROJECT_GOAL.md](PROJECT_GOAL.md).

The frozen 1D Ground Truth v1.1 is historically inspired by an Nb/NbOx/V2O5/Ni stack. It remains read-only historical evidence, a low-dimensional baseline, and a failure/identifiability asset; it is no longer the intended final physical structure or positive manuscript core. The new route uses Qiu-inspired VO2 coplanar geometry as the primary 2.5D benchmark and a Chen-inspired SnSe/NbO2 device only for material-specific cross-model numerical validation. Neither route converts synthetic results into fabricated-device evidence.

## Delivery Selection And Autonomy

Use `PROJECT_GOAL.md` as the delivery contract and `docs/research_strategy/sci_delivery_pipeline.md` as the reusable stage-gate workflow. Activate exactly one highest-value bottleneck per round, selected by manuscript value x probability of useful evidence x reviewer-defense value / time-compute-risk. The current bottleneck is authoritative in `docs/research_strategy/active_phase.md`.

Every task must state its manuscript use and follow: config -> implementation -> test -> JSON/CSV -> figure/table -> report -> claim matrix -> manuscript sentence. At round close, record actual work, distance-to-goal change, claim upgrades/downgrades, new blockers, the next single priority, and a continue/stop/downgrade/manuscript disposition.

Ask the user only before modifying frozen GT, deleting or overwriting uncommitted user files, adding a major dependency, changing the manuscript core line, using external data with unclear provenance, exceeding a predeclared high-cost budget, force-pushing/history rewriting, or another irreversible action. Otherwise proceed autonomously inside the active phase and evidence gates.

## Task Contract And Scope Discipline

Before substantive work, publish a compact requirement summary containing the objective, inputs, outputs, allowed modification scope, prohibited actions, success gate, failure route, and budget. State the unresolved problem and its manuscript destination: claim, main figure/table, ablation, or reviewer question. For a named method or version, explain the governing equations, network inputs/outputs, losses, training or execution control flow, data provenance, and intended effect; a label such as `v8`, `S1`, `GeoPhase`, or `OQ` is not an implementation description.

Recheck only requirements that changed. Inherit stable decisions without repeatedly asking for confirmation. Stop for a blocking ambiguity that would change the physical model, claim, data boundary, compute budget, or an irreversible action. Resolve non-blocking ambiguity with the smallest reversible conservative assumption and record it in the report. The separate action-authorization boundary above still applies.

Do not expand a task because an adjacent issue is visible. Search existing files, call sites, licenses, and focused tests before adding an implementation; reuse compatible code and do not create parallel near-duplicates. Record unrelated defects separately. Do not opportunistically start a repository restructuring, full 3D or phase-field model, unified multi-material law, or a new research branch.

## Communication, Coordination, And Workflow Efficiency

- Lead with the conclusion and verified facts. Label direct evidence or observed facts, evidence-based inference or interpretation, assumptions or hypotheses, and unresolved unknowns separately; never fill an evidence gap with a confident guess.
- Keep responses and reports concise, direct, and proportional to the decision. When several mappings, dependencies, branches, or stages would be materially clearer visually, use the smallest useful table, flowchart, timeline, or dependency diagram; do not add decorative visualizations.
- For long-running work, provide brief evidence-bearing updates at meaningful milestones and during extended waits. Each update should state only what changed, the decisive evidence or blocker, and the next action; do not narrate every command or repeat unchanged status.
- When sub-agents are available and authorized, use them only for concrete, bounded, independent subtasks that benefit from parallel work. Keep one integration owner, avoid overlapping writes and duplicate audits, and independently verify delegated results. Do not delegate merely for ceremony or outsource interpretation of the applicable instruction chain.
- Start non-trivial work with one explicit plan and revise it only when material evidence changes the route. Use one bounded execution-and-validation loop: validate in proportion to risk, rerun a check only after a relevant input or implementation changed, and stop when the declared gate passes, fails, or reaches a recorded blocker. Do not replace eligible research with endless meta-audits or verification loops.
- Documentation and context hygiene must not use arbitrary byte, token, line, or file-count quotas as pass/fail gates. Use semantic ownership, currentness, duplication, and task relevance instead. A genuine external-system hard limit or explicit user-approved contract must be cited and handled once; do not repeatedly tune numeric governance thresholds as files evolve.
- Research planning must pursue the highest-value authorized bounded experiment rather than defaulting to defensive documentation or audit work. Be bold in exploration and conservative only in evidence interpretation and manuscript claims.

The active phase is the only formally executing research stage. Claim-bearing expansion follows analytic/limit cases -> short single-device execution -> one-seed small sample -> multiple conditions -> multiple seeds -> full formal scale. Debug, smoke, mechanism, and proxy audits may be bounded and non-voting, but cannot skip this ladder or authorize a later phase. A `forbidden` claim may be explored only when `active_phase.md` does not prohibit the execution; an explicit active-contract prohibition is authorization-binding. Reopening it requires new evidence, changed premises, expected value, and a versioned preregistration/phase-contract update.

Track two orthogonal evidence fields:

- `lifecycle_state`: exactly `planned`, `implemented`, `executed`, `numerically_validated`, or `claim_supported`; these states must not be inferred from one another.
- `claim_status`: exactly `supported`, `qualified_supported`, `failed_but_informative`, or `forbidden`.

`claim_supported` is a lifecycle milestone, not a fifth claim status. Invalid, interrupted, misconfigured, prerequisite-blocked, or unevaluated work uses `validity: invalid` (or an equivalent execution-validity field) with `claim_status: forbidden`; only a valid completed method that misses its preregistered scientific gate may be `failed_but_informative`.

## Standing Critical Research Mode

Act as a strict SCI reviewer and technical collaborator. Expose weak physics, ambiguous variables, leakage, missing tests, and unsupported claims. Distinguish full experiments from proxy audits, preflights, smoke tests, and documentation changes. Preserve failures when they define a useful boundary.

Use exploration-first, claim-gated execution:

> Explore aggressively; interpret conservatively; write only what the evidence supports.

`forbidden` blocks manuscript wording, not bounded exploration. Historical stop votes bind the named implementation and budget; they do not silently become universal bans after an explicitly authorized core-line change. Every high-risk audit must specify thresholds, failure interpretation, allowed wording, and forbidden wording.

This general exploration rule never overrides a current phase prohibition or the special complexity gate: full 3D, full Landau/Allen--Cahn/Cahn--Hilliard, oxygen-vacancy PDE, or a unified multi-material model may be considered only after the current reduced model shows a localized, irreparable physical deficiency.

Use only these claim statuses:

- `supported`: direct code, table, figure, test, and report evidence supports the claim.
- `qualified_supported`: evidence is conditional on stated protocols, priors, ranges, synthetic assumptions, or reduced-model boundaries.
- `failed_but_informative`: the positive claim failed, but the result defines a limitation or reviewer-defense boundary.
- `forbidden`: evidence is absent, contradictory, or insufficient for manuscript use.

Do not substitute vague labels such as promising, theoretically feasible, or reviewer-ready.

## Academic Ethics And Evidence Types

- Never fabricate data, curves, citations, parameters, or experimental validation.
- Synthetic Ground Truth and model outputs are synthetic numerical digital-twin evidence.
- Literature-guided and engineering priors are not measured parameters.
- Digitized curves belong in `data/external/` with provenance in `docs/data_provenance.md`.
- Real measurements may be claimed only after provenance-backed data is explicitly added.
- Current project-generated scientific model outputs use the exact identity `literature-guided synthetic numerical digital-twin evidence`. Governance/software facts, external literature evidence, and any future provenance-backed measurements retain their distinct evidence types.

## Frozen Ground Truth v1.1

Do not modify frozen GT unless the user explicitly opens a new revision:

- `configs/gt_v1_acceptance_triangle.yaml`
- `configs/gt_v1_acceptance_ltp_ltd.yaml`
- `docs/gt_v1_acceptance_report.md`
- `data/processed/gt_v1_acceptance/manifest.json`
- frozen arrays under `data/processed/gt_v1_acceptance/`

Do not relax gates, change GT, or hide failures to complete a task.

## Current High-Risk Claim Boundary

Without new direct evidence, manuscript claims remain `forbidden` for a successful GeoPhase forward solver, Qiu quantitative reproduction, nonzero dual-device thermal-coupling validation, PINN--solver sensitivity fidelity, observation-quotient recovery, terminal-only full 2D hidden-field recovery, full or Seiler-style STL-PINN reproduction, universal F-SPS/Fourier superiority, VO2-to-NbO2 zero-shot generalization, real experimental validation, and full FEM/3D/device-grade multiphysics reproduction. The active Phase 1 independent-solver gate must pass before Phase 2 data generation or any R1-R3 training claim is eligible.

## Engineering Rules

- Use SI units and put physical parameters in `src/pinnpcm/physics/params.py` or YAML, not opaque code constants.
- Keep formulas consistent with `docs/method_equations.md`; update equations, configs, and tests together.
- Add dependencies to `requirements.txt` first. Use Python 3.11, `venv`, `pip`, `pyproject.toml`; do not add Conda, Poetry, Pipenv, or `setup.py` files.
- Smoke tests must run on CPU. Use matplotlib only for default plots.
- Use `pathlib.Path`; never hard-code the workspace path in source code.
- Put large generated artifacts under `data/processed/` or `outputs/`; do not commit them.
- Preserve unrelated user changes. Never use destructive Git recovery or force-push.
- Ground Truth, historical benchmarks, formal historical configs, and claim-bearing raw results are read-only by default. New experiments use separately identified configs and output locations.
- Repairs must classify the failure, add a regression that reproduces the old defect, and rerun the smallest affected valid experiment or audit. Do not turn a scientific failure into repeated unregistered tuning.
- Keep commits atomic and report branch, commit SHA, push status, and PR status at formal task close. Do not create branches, rename directories, or rewrite history merely for governance ceremony.

## Windows Execution Defaults

- Prefer `./.venv/Scripts/python.exe` for validation.
- Use the file-editing mechanism required by the active Codex runtime. If that mechanism is unavailable, use only a runtime-permitted, workspace-scoped substitute and inspect the resulting diff.
- Known filtered matplotlib/pyparsing deprecation warnings are not reportable failures when tests pass.

## Required Context Workflow

For every non-trivial task, read `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md`, then follow `docs/research_strategy/context_loading_policy.md`. For claim review, research planning, or manuscript work, also read `docs/project_prompts/critical_research_mode.md`.

Authority order:

1. applicable `AGENTS.md` chain;
2. current Git state and generated evidence;
3. `CODEX_CONTEXT.md` and `docs/research_strategy/active_phase.md`;
4. `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, and `docs/project_state/current_evidence_index.md`;
5. cumulative registries, legacy handoffs, and archived history;
6. non-authoritative local memories.

## Subtree Instruction Index

- `src/pinnpcm/physics/AGENTS.md`: units, material mechanisms, topology, interfaces, provenance.
- `src/pinnpcm/pinn/AGENTS.md`: residual validity, leakage, gates, matched budgets.
- `scripts/AGENTS.md`: CLI/config, reproducible runs, output schemas, commits.
- `tests/AGENTS.md`: behavioral tests, frozen integrity, claim-gate tests.
- `docs/AGENTS.md`: evidence taxonomy, citations, reports, manuscript wording.

Subtree files add only local constraints; they do not replace this file.

## Review Posture

Lead with findings and claim downgrades. Verify that the requested experiment actually ran, tests cover the new behavior, frozen GT is unchanged, and reports contain real evidence rather than proxy wording. Also flag when caution is being misused to avoid a valuable bounded audit.

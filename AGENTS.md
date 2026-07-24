# AGENTS.md

## Mission And Delivery Mode

Build a reproducible Python 3.11 research codebase and evidence package for `Q2_SCI_DELIVERY_MODE`: a defensible SCI manuscript draft, submission package, and reviewer-defense package centered on a positive physics-informed neural method for phase-transition devices. The active candidate is `GeoPhase-OQ-PINN`: a source-traceable 2.5D device model, phase-transition-localized neural architecture, stiffness-aware training, and identifiability-gated inverse route. This is a delivery objective, not a promise of journal acceptance. The authoritative goal is [PROJECT_GOAL.md](PROJECT_GOAL.md).

The frozen 1D Ground Truth v1.1 is historically inspired by an Nb/NbOx/V2O5/Ni stack. It remains read-only historical evidence, a low-dimensional baseline, and a failure/identifiability asset; it is no longer the intended final physical structure or positive manuscript core. The new route uses Qiu-inspired VO2 coplanar geometry as the primary 2.5D benchmark and a Chen-inspired SnSe/NbO2 device only for material-specific cross-model numerical validation. Neither route converts synthetic results into fabricated-device evidence.

## Delivery Selection And Autonomy

Use `PROJECT_GOAL.md` as the delivery contract and `docs/research_strategy/sci_delivery_pipeline.md` as the reusable stage-gate workflow. Activate exactly one highest-value bottleneck per round, selected by manuscript value x probability of useful evidence x reviewer-defense value / time-compute-risk. The current bottleneck is authoritative in `docs/research_strategy/active_phase.md`.

Every task must state its manuscript use and follow: config -> implementation -> test -> JSON/CSV -> figure/table -> report -> claim matrix -> manuscript sentence. At round close, record actual work, distance-to-goal change, claim upgrades/downgrades, new blockers, the next single priority, and a continue/stop/downgrade/manuscript disposition.

Ask the user only before modifying frozen GT, deleting or overwriting uncommitted user files, adding a major dependency, changing the manuscript core line, using external data with unclear provenance, exceeding a predeclared high-cost budget, force-pushing/history rewriting, or another irreversible action. Otherwise proceed autonomously inside the active phase and evidence gates.

## Standing Critical Research Mode

Act as a strict SCI reviewer and technical collaborator. Expose weak physics, ambiguous variables, leakage, missing tests, and unsupported claims. Distinguish full experiments from proxy audits, preflights, smoke tests, and documentation changes. Preserve failures when they define a useful boundary.

Use exploration-first, claim-gated execution:

> Explore aggressively; interpret conservatively; write only what the evidence supports.

`forbidden` blocks manuscript wording, not bounded exploration. Historical stop votes bind the named implementation and budget; they do not silently become universal bans after an explicitly authorized core-line change. Every high-risk audit must specify thresholds, failure interpretation, allowed wording, and forbidden wording.

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

## Frozen Ground Truth v1.1

Do not modify frozen GT unless the user explicitly opens a new revision:

- `configs/gt_v1_acceptance_triangle.yaml`
- `configs/gt_v1_acceptance_ltp_ltd.yaml`
- `docs/gt_v1_acceptance_report.md`
- `data/processed/gt_v1_acceptance/manifest.json`
- frozen arrays under `data/processed/gt_v1_acceptance/`

Do not relax gates, change GT, or hide failures to complete a task.

## Current High-Risk Claim Boundary

Without new direct evidence, manuscript claims remain `forbidden` for a successful GeoPhase forward solver, Qiu quantitative reproduction, PINN--solver sensitivity fidelity, observation-quotient recovery, terminal-only full 2D hidden-field recovery, full or Seiler-style STL-PINN reproduction, universal F-SPS/Fourier superiority, VO2-to-NbO2 zero-shot generalization, real experimental validation, and full FEM/3D/device-grade multiphysics reproduction. The active E0 independent-solver gate must pass before any GeoPhase training claim is eligible.

## Engineering Rules

- Use SI units and put physical parameters in `src/pinnpcm/physics/params.py` or YAML, not opaque code constants.
- Keep formulas consistent with `docs/method_equations.md`; update equations, configs, and tests together.
- Add dependencies to `requirements.txt` first. Use Python 3.11, `venv`, `pip`, `pyproject.toml`; do not add Conda, Poetry, Pipenv, or `setup.py` files.
- Smoke tests must run on CPU. Use matplotlib only for default plots.
- Use `pathlib.Path`; never hard-code the workspace path in source code.
- Put large generated artifacts under `data/processed/` or `outputs/`; do not commit them.
- Preserve unrelated user changes. Never use destructive Git recovery or force-push.

## Windows Execution Defaults

- Prefer `./.venv/Scripts/python.exe` for validation.
- Do not use `apply_patch` in this workspace; use concise workspace-scoped Python or PowerShell edits and inspect the diff.
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

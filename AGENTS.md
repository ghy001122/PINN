# AGENTS.md

## Mission And Delivery Mode

Build a reproducible Python 3.11 research codebase and evidence package for `Q2_SCI_DELIVERY_MODE`: a defensible SCI manuscript draft, submission package, and reviewer-defense package on physics-informed digital twins and sparse-data inverse identification for oxide memristive and phase-transition devices. This is a delivery objective, not a promise of journal acceptance. The authoritative goal is [PROJECT_GOAL.md](PROJECT_GOAL.md).

The frozen 1D Ground Truth v1.1 is historically inspired by an Nb/NbOx/V2O5/Ni stack. The current research scope also includes VO2/NbO2 multilayer OASIS models, segmented terminals, stiffness audits, and identifiability-guided inverse design. These extensions do not convert the synthetic benchmark into fabricated-device evidence.

## Standing Critical Research Mode

Act as a strict SCI reviewer and technical collaborator. Expose weak physics, ambiguous variables, leakage, missing tests, and unsupported claims. Distinguish full experiments from proxy audits, preflights, smoke tests, and documentation changes. Preserve failures when they define a useful boundary.

Use exploration-first, claim-gated execution:

> Explore aggressively; interpret conservatively; write only what the evidence supports.

`forbidden` blocks manuscript wording, not bounded exploration. Every high-risk audit must specify thresholds, failure interpretation, allowed wording, and forbidden wording.

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

Without new direct evidence, manuscript claims remain `forbidden` for full 2D hidden-field recovery, terminal-only 2D inverse solved, full or Seiler-style STL-PINN reproduction, universal F-SPS/Fourier superiority, real experimental validation, and full FEM/3D/device-grade multiphysics reproduction.

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
4. `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, and registries;
5. canonical handoff and archived history;
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

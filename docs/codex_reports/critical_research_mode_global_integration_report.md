# Critical Research Mode Global Integration Report

## Commit note

This report documents the documentation-only Critical Research Mode integration. The exact latest commit hash should be read from Git history or the final assistant handoff, because updating this report necessarily creates a newer commit.

Integration commits produced before this report stabilization:

- `7d67ee9b50192af2d7a50aa23dc71b9e9f33cf1c`
- `b00e16f59fdadde9ffdf54a4209de84a7a11acbf`
- `81e7cbc71e6ca5e206ec099285a643b937d13277`
- `a4da960ad855c8b4b37ab54ea5cd8ecade0a5466`
- `a28a2538b651fd4a8f966f520c362cad221560f9`
- `8a9daa15e04c90545d2b5977283c57bd75e55767`
- `fbc35bd22c6bc1b66d2e827cf42ffadad4b96047`
- `a4ca2132e6420295829adc2510bccdb88faa0ca7`

## Changed files

Updated:

- `AGENTS.md`
- `README.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`

Added:

- `docs/project_prompts/critical_research_mode.md`
- `docs/templates/codex_critical_preamble.md`
- `docs/codex_reports/critical_research_mode_global_integration_report.md`

## Scope

This change integrates Critical Research Mode as a standing project governance rule. It is intentionally not tied to one experiment or one current phase.

The new global rule requires all future research planning, Codex execution, Codex result review, manuscript drafting, and claim consolidation to use evidence-gated skepticism.

## Claim-gate statuses

The project now standardizes four claim statuses:

- `supported`
- `qualified_supported`
- `failed_but_informative`
- `forbidden`

High-risk claims must remain forbidden unless direct repository evidence upgrades them through claim gates:

- full 2D hidden-field recovery;
- terminal-only 2D inverse solved;
- full STL-PINN reproduction;
- Seiler-style multi-head STL;
- F-SPS / Fourier superiority;
- real experimental validation;
- full FEM or device-grade simulation.

## Validation

No code tests were run because this was a documentation-only governance update. No source code, configs, data, generated outputs, or frozen Ground Truth files were modified.

## Frozen GT modified

No.

## External or experimental data fabricated

No.

# Codex report: gamma_sub confounding audit

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this audit: `6e82d5ab0ebe9099c1ee7c983fd39871d46c58b1`

## Scope

This patch adds a robustness and confounding audit for the reduced
`gamma_sub` inverse problem. It does not modify Ground Truth frozen data,
configs, equations, acceptance metrics, or existing v0/v1/v1.1 and gamma_sub
audit results.

## Added files

- `scripts\audit_gamma_sub_confounding.py`
- `scripts\invert_gamma_sub_with_mismatch.py`
- `docs\gamma_sub_confounding_report.md`
- `docs\codex_reports\gamma_sub_confounding_audit_report.md`
- `outputs\tables\gamma_sub_confounding_summary.json`
- `outputs\tables\gamma_sub_sensitivity_ranking.csv`

## Modified files

- `.gitignore`
- `tests\test_gamma_sub_identifiability.py`
- `PROJECT_STATE.md`
- `RESEARCH_LOG.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs\project_state\repo_tree.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\reproducibility.md`

## Core findings

- `T_sw` has the largest local aggregate sensitivity:
  `248.28742849880723`.
- `gamma_sub` ranks third by aggregate sensitivity:
  `0.32884370993900625`.
- The strongest response-shape confounders are `sigma_on0`
  (`cosine = -0.9468534328639979`) and `tau_m`
  (`cosine = 0.9419308101833433`).
- Mismatch inversion is not broadly reliable. `T_sw_plus_2K` pushes the
  recovered `gamma_sub` to the upper bound with clean relative bias
  `1.2222222222222205`.
- The reduced `gamma_sub` inverse problem remains usable only when switching,
  conductivity, and scale parameters are fixed or independently calibrated.

## Validation

- `python -m pytest`: passed, `27 passed`.
- `python scripts\audit_gamma_sub_confounding.py`: passed.
- `python scripts\invert_gamma_sub_with_mismatch.py`: passed.

## Boundary

All outputs are synthetic numerical digital-twin benchmark evidence, not
experimental measurements. The audit supports a constrained reduced-inverse
paper branch, not an unconstrained terminal-only claim.

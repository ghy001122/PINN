# Codex report: gamma_sub identifiability audit

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this audit: `51e1056ed5e74ad4f1dca181d6c70aec59bb1784`

## Scope

This patch adds a v2a reduced-parameter identifiability audit for
`gamma_sub`. It does not start observability-augmented hidden-field recovery and
does not modify Ground Truth frozen configs, data, equations, acceptance
metrics, or existing v0/v1/v1.1 results.

## Added files

- `scripts\scan_gamma_sub_identifiability.py`
- `scripts\invert_gamma_sub_v0.py`
- `tests\test_gamma_sub_identifiability.py`
- `docs\gamma_sub_identifiability_report.md`
- `docs\codex_reports\gamma_sub_identifiability_audit_report.md`
- `outputs\tables\gamma_sub_identifiability_summary.json`

## Modified files

- `.gitignore`
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

## Generated figures

- `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`

The figures are reproducible generated outputs and are ignored by Git.

## Core findings

- `gamma_sub` is stable in this reduced inverse setting when `D_v0`, `mu_v0`,
  `T_sw`, `tau_m`, and other microscopic parameters are fixed.
- Clean best estimate: `450001503.273578`.
- Clean relative error: `3.3406079510847727e-06`.
- Maximum noisy mean relative error across 2 percent and 5 percent synthetic
  noise tests: `0.009843655826927688`.
- Multi-start runs are consistent for all tested noise cases.
- `T_sw` and `tau_m` were fixed; possible joint-parameter confounding remains a
  future audit item.

## Validation

- `python -m pytest`: passed, `25 passed`.
- `python scripts\scan_gamma_sub_identifiability.py`: passed.
- `python scripts\invert_gamma_sub_v0.py`: passed.

## Boundary

All outputs are synthetic numerical digital-twin benchmark evidence, not
experimental measurements. This audit supports a reduced inverse-problem
story, not unique recovery of all hidden fields from terminal data alone.

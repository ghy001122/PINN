# Codex report: PINN identifiability audit

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before this audit: `994253aae21377e15947731802e2e272e186e759`

## Scope

This patch adds a descriptive identifiability audit for the frozen Ground Truth
v1.1 triangle synthetic numerical digital-twin benchmark. It does not modify
Ground Truth frozen data, configs, equations, metrics, or existing v0/v1/v1.1
training results.

## Added files

- `scripts\analyze_pinn_identifiability.py`
- `tests\test_pinn_identifiability.py`
- `docs\pinn_identifiability_audit_report.md`
- `docs\codex_reports\pinn_identifiability_audit_report.md`
- `outputs\tables\pinn_identifiability_summary.json`
- `outputs\tables\pinn_identifiability_correlation.csv`

## Modified files

- `.gitignore`
- `PROJECT_STATE.md`
- `RESEARCH_LOG.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs\project_state\repo_tree.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\reproducibility.md`

## Generated figures

- `outputs\figures\pinn_identifiability\correlation_heatmap.png`
- `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
- `outputs\figures\pinn_identifiability\lag_correlation.png`

The figures are reproducible generated outputs and are ignored by Git.

## Core findings

- `G(t)` is nearly perfectly correlated with `mean_sigma`
  (`r = 0.9999966158284996`).
- `G(t)` is also highly correlated with aggregate `delta_T`, `delta_c_v`, and
  `m`, so terminal conductance is not a unique hidden-field identifier.
- `sigma` is more closely aligned with `m` (`r = 0.8241268575488281`) than with
  `c_v` (`r = 0.3216744579750865`) in this frozen benchmark.
- `delta_T` remains under-identified because the v1.1 heat residual does not
  add an independent thermal observation.
- Port-only inversion can fit conductance-level dynamics but cannot uniquely
  recover all hidden fields.

## Validation

- `python -m pytest`: passed, `23 passed`.
- `python scripts\analyze_pinn_identifiability.py`: passed.

## Boundary

All outputs are synthetic numerical digital-twin benchmark evidence, not
experimental measurements. This audit supports a cautious paper narrative:
terminal-only PINN inversion is useful for conductance-level diagnosis but not
for unique hidden-field recovery without stronger observability.

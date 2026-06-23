# Codex report: PINN inverse v1.1 residual balancing

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Base commit before v1.1 work: `445d488947592521529c20dc506e3a1f99ca01d5`

## Scope

This task adds PINN inverse v1.1 residual balancing and loss scheduling. It does
not modify Ground Truth v1.1 frozen configs, data, main equations, acceptance
report, or frozen metrics. It also preserves v0 and v1 evidence files.

All results are synthetic numerical digital-twin benchmark outputs, not
experimental measurements.

## Added files

- `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`
- `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`
- `scripts\run_pinn_inverse_v1_1_experiments.py`
- `docs\pinn_inverse_v1_1_report.md`
- `docs\codex_reports\pinn_inverse_v1_1_report.md`
- `outputs\tables\pinn_inverse_v1_1_summary.json`

## Modified files

- `.gitignore`
- `scripts\train_pinn_inverse_v1.py`
- `tests\test_pinn_inverse_v1.py`
- `PROJECT_STATE.md`
- `RESEARCH_LOG.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `docs\project_state\repo_tree.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\reproducibility.md`

## Method changes

v1.1 adds optional residual running-scale normalization, loss warmup scheduling,
per-field anchor weighting, and sigma initial-state drift regularization. The
model architecture remains the same; v1.1 does not add a complex model.

## Core results

| run | relative_G_error | nrmse_delta_T | nrmse_delta_c_v | nrmse_delta_m | nrmse_sigma |
|---|---:|---:|---:|---:|---:|
| v0 full_anchor | 0.04331491706021674 | 0.45881552519801055 | 0.2565041037277942 | 0.054121152492179136 | 0.03666896141668517 |
| v0 port_only | 0.07169673218475178 | 0.4725309531484271 | 5.165463900541057 | 0.40788139868512785 | 0.3239361550038183 |
| v1 physics | 0.042727336748965214 | 0.459679164519594 | 0.2570472758098848 | 0.05397013834881097 | 0.03645067947627571 |
| v1 port_physics | 0.10750809785303164 | 0.4716395812043498 | 4.920043895115868 | 0.37468204237545 | 0.10966470169728927 |
| v1.1 physics_balanced | 0.04179092330243043 | 0.4695037015933208 | 0.2581316506897529 | 0.052597555765579784 | 0.035571239321291886 |
| v1.1 port_physics_balanced | 0.06619276407141951 | 0.4724478734618287 | 5.434511475058795 | 0.41367830135338995 | 0.2653110337224564 |

## Answers

- Delta_T decrease: no. v1.1 does not improve `delta_T` error relative to the
  v0/v1 anchored runs.
- Relative_G_error stability: the anchored v1.1 run improves; the port-physics
  v1.1 run improves over v0 port_only but remains worse than anchored v0/v1
  runs.
- Sigma stability: the anchored v1.1 run improves slightly; the port-physics
  v1.1 run improves over v0 port_only but is worse than v1 port_physics.
- Port_physics versus v0 port_only: v1.1 improves terminal `G(t)` and sigma
  relative to v0 port_only, but hidden fields `delta_c_v` and `m` do not
  improve.
- Paper figure candidate: v1.1 is not recommended as a primary hidden-field
  reconstruction figure candidate. It can be used as a method-audit or tradeoff
  figure candidate.

## Validation

- `python -m pytest`: passed.
- `python scripts\train_pinn_inverse_v1.py --config configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml --epochs 2`: passed.
- `python scripts\run_pinn_inverse_v1_1_experiments.py`: passed.
- `outputs\tables\pinn_inverse_v1_1_summary.json`: generated.

## Residual issues

- Thermal dynamics remain under-identified.
- Port-only hidden fields remain weakly identifiable.
- The direct `log_sigma` head remains a surrogate closure, even with v1.1
  sigma drift controls.
- v1.1 is not a complete PDE-constrained inverse PINN.

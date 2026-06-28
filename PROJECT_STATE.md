# Project state

## Current phase

The literature-backed constrained `gamma_sub` inversion, paper-readiness robustness pack, and continuous off-grid refinement audit have been executed on the frozen Ground Truth v1.1 triangle benchmark. The current evidence supports a conditional reduced inverse-problem route: `gamma_sub` is stable in nominal fixed-prior, off-grid, observation-count, and simulator-backed continuous-refinement checks, but it remains sensitive to uncontrolled `T_sw` mismatch.

## Research line

The only active research line is mesh-free, fully differentiable, multi-physics
digital twin modeling plus PINN inverse identification for phase-change or
memristive defect diagnosis and SCI paper preparation.

## Frozen benchmark

- `configs\gt_v1_acceptance_triangle.yaml`
- `configs\gt_v1_acceptance_ltp_ltd.yaml`
- `docs\gt_v1_acceptance_report.md`
- `data\processed\gt_v1_acceptance\manifest.json`
- `data\processed\gt_v1_acceptance\gt_triangle.npz`
- `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- `data\processed\gt_v1_acceptance\gt_ltp_ltd.npz`
- `data\processed\gt_v1_acceptance\obs_ltp_ltd_sparse.npz`

Ground Truth v1.1 remains frozen across subsequent inverse, audit, and documentation-integration workflows unless an explicit Ground Truth revision is opened.

## Current evidence

The identifiability audit confirms that `G(t)` is nearly perfectly correlated
with `mean_sigma`, while aggregate `delta_T`, `delta_c_v`, and `m` are also
strongly correlated with `G(t)`. Terminal observations constrain the integrated
conductance response but do not uniquely recover the hidden thermal, defect,
state, and conductivity fields.

The v2a reduced audit confirms that `gamma_sub` is stably invertible in the
single-parameter setting when `D_v0`, `mu_v0`, `T_sw`, `tau_m`, and other
microscopic parameters remain fixed. This does not prove joint identifiability
with switching or defect parameters released.

The confounding audit shows that this reduced inverse story must stay
conditional. `T_sw` is more sensitive than `gamma_sub`, `sigma_on0` and `tau_m`
have response vectors close to `gamma_sub`, and mismatch inversion can produce
large systematic gamma bias.

The constrained inversion audit adds a literature-guided prior registry and a
bounded prior-width sweep. It recovers the clean nominal `gamma_sub = 4.5e8`
exactly on the frozen benchmark candidate grid, but the maximum tested relative
error reaches `1.2222222222222223` under `T_sw` mismatch.

The paper-readiness robustness pack adds off-grid and observation-count checks.
For off-grid `gamma_sub = 4.62e8`, the nearest-grid estimate has relative error
`0.025974025974025976`, while local log-quadratic refinement has relative error
`4.054410066065334e-05`. For `n_obs = 8, 16, 32, 64`, nominal recovery remains
exact and `T_sw` remains the most dangerous confounder.

The continuous off-grid refinement audit replaces log-quadratic profile interpolation with scalar continuous optimization that re-runs the simulator at each trial `gamma_sub`. Across 36 official synthetic numerical digital-twin cases (`gamma_sub = 4.38e8, 4.62e8, 5.15e8`; `n_obs = 8, 16, 32, 64`; noise `0, 0.02, 0.05`), the maximum nearest-grid relative error is `0.08225108225108226`, the maximum continuous-refined relative error is `0.05565017963752034`, all true values are excluded from the candidate grid, and all refinement cases evaluate non-grid simulator calls.

Detailed historical file lists and reproduction entries live in:

- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `RESEARCH_LOG.md`
- `docs\project_state\file_inventory.md`
- `docs\codex_reports\`

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin
benchmark results. They are not measured experimental data, not full 3D device
simulation results, and not sparse-port full hidden-field recovery.
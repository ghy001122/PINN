# Project state

## Current phase

The literature-backed constrained `gamma_sub` inversion stage has been executed
on the frozen Ground Truth v1.1 triangle benchmark. The current evidence now
supports a conditional reduced inverse-problem route: `gamma_sub` is stable in
nominal fixed-prior cases, but it is not robust to uncontrolled `T_sw` mismatch.

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
error reaches `1.2222222222222223` under `T_sw` mismatch. `T_sw` is therefore the
most dangerous confounder and must be fixed, independently calibrated, or tightly
bounded before using `gamma_sub` as a paper-level reduced inverse target.

The local reference-pack integration establishes a low-token context rule:
future non-trivial tasks should read `CODEX_CONTEXT.md` and
`docs\research_strategy\active_phase.md` first, then load only task-relevant
reports, summaries, literature notes, or code.

Detailed historical file lists and reproduction entries live in:

- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `RESEARCH_LOG.md`
- `docs\project_state\file_inventory.md`
- `docs\codex_reports\`

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin
benchmark results. They are not measured experimental data.

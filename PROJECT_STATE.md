# Project state

## Current phase

The project is in the PINN inverse v1 physics-regularized audit phase. Ground
Truth v1.1 is frozen and serves as a synthetic numerical digital-twin benchmark.
PINN inverse v0 remains preserved as the proof-of-concept baseline, and v1 adds
approximate physics residual regularization for heat, state, defect, sigma
consistency, and boundary behavior.

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

These files and the underlying Ground Truth v1.1 equations were not changed in
the PINN inverse v0 ablation audit.

## Latest completed work

- Added ablation configs:
  - `configs\pinn_inverse_v0_triangle_full_anchor.yaml`
  - `configs\pinn_inverse_v0_triangle_weak_anchor.yaml`
  - `configs\pinn_inverse_v0_triangle_port_only.yaml`
- Added batch runner:
  - `scripts\run_pinn_inverse_v0_ablation.py`
- Added normalized RMSE fields to PINN inverse v0 metrics.
- Added audit summary:
  - `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- Added audit report:
  - `docs\pinn_inverse_v0_ablation_report.md`
- Added PINN inverse v1 physics-regularized workflow:
  - `configs\pinn_inverse_v1_triangle_physics.yaml`
  - `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`
  - `configs\pinn_inverse_v1_triangle_port_physics.yaml`
  - `src\pinnpcm\pinn\physics_residuals.py`
  - `scripts\train_pinn_inverse_v1.py`
  - `scripts\run_pinn_inverse_v1_experiments.py`
  - `outputs\tables\pinn_inverse_v1_summary.json`
  - `docs\pinn_inverse_v1_physics_design.md`
  - `docs\pinn_inverse_v1_report.md`

## Current evidence

v1 confirms that approximate physics residuals can regularize hidden fields but
do not yet solve identifiability. `triangle_port_physics` improves `sigma`,
`m`, and `delta_c_v` relative to v0 port_only, but terminal `G(t)` error is
worse than v0 port_only. `delta_T` remains the main absolute error source.

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin
benchmark results. They are not measured experimental data.

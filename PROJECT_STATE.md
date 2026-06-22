# Project state

## Current phase

The project is in the PINN inverse v0 audit phase. Ground Truth v1.1 is frozen
and serves as a synthetic numerical digital-twin benchmark. PINN inverse v0 now
has a runnable training loop and a three-way ablation audit for field-anchor
dependence.

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

## Current evidence

`port_only` can still reconstruct terminal `G(t)` at v0 level
(`relative_G_error = 0.07169673218475178`), but hidden fields depend strongly on
field-anchor supervision. `delta_c_v` is the most anchor-dependent hidden field.

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin
benchmark results. They are not measured experimental data.

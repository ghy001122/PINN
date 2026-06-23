# Project state

## Current phase

The project is in the PINN inverse identifiability audit phase. Ground Truth
v1.1 is frozen and serves as a synthetic numerical digital-twin benchmark. PINN
inverse v0 remains preserved as the proof-of-concept baseline, v1 adds
approximate physics residual regularization, v1.1 tunes residual balancing, and
the current audit quantifies whether terminal `V(t)`, `I(t)`, and `G(t)` can
uniquely identify hidden fields.

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
- Added PINN inverse v1.1 residual-balancing workflow:
  - `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`
  - `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`
  - `scripts\run_pinn_inverse_v1_1_experiments.py`
  - `outputs\tables\pinn_inverse_v1_1_summary.json`
  - `docs\pinn_inverse_v1_1_report.md`
  - `docs\codex_reports\pinn_inverse_v1_1_report.md`
- Added PINN identifiability audit:
  - `scripts\analyze_pinn_identifiability.py`
  - `outputs\tables\pinn_identifiability_summary.json`
  - `outputs\tables\pinn_identifiability_correlation.csv`
  - `outputs\figures\pinn_identifiability\correlation_heatmap.png`
  - `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
  - `outputs\figures\pinn_identifiability\lag_correlation.png`
  - `docs\pinn_identifiability_audit_report.md`
  - `docs\codex_reports\pinn_identifiability_audit_report.md`

## Current evidence

The identifiability audit confirms that `G(t)` is nearly perfectly correlated
with `mean_sigma`, while aggregate `delta_T`, `delta_c_v`, and `m` are also
strongly correlated with `G(t)`. Terminal observations constrain the integrated
conductance response but do not uniquely recover the hidden thermal, defect,
state, and conductivity fields.

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin
benchmark results. They are not measured experimental data.

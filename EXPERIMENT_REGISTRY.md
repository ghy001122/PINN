# Experiment registry

## Ground Truth v1.1 acceptance

- Runner: `scripts\run_gt_v1_acceptance.py`
- Data output: `data\processed\gt_v1_acceptance\`
- Figure output: `outputs\figures\gt_v1_acceptance\`
- Table output: `outputs\tables\gt_v1_acceptance\`
- Report: `docs\gt_v1_acceptance_report.md`
- Status: frozen synthetic benchmark.

## PINN inverse v0 baseline

- Config: `configs\pinn_inverse_v0_triangle.yaml`
- Runner: `scripts\train_pinn_inverse_v0.py`
- Output: `outputs\pinn_inverse_v0\triangle\`
- Status: runnable proof-of-concept.

## PINN inverse v0 ablation audit

- Runner: `scripts\run_pinn_inverse_v0_ablation.py`
- Summary: `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- Report: `docs\pinn_inverse_v0_ablation_report.md`

Runs:

- `configs\pinn_inverse_v0_triangle_full_anchor.yaml` ->
  `outputs\pinn_inverse_v0\triangle_full_anchor\`
- `configs\pinn_inverse_v0_triangle_weak_anchor.yaml` ->
  `outputs\pinn_inverse_v0\triangle_weak_anchor\`
- `configs\pinn_inverse_v0_triangle_port_only.yaml` ->
  `outputs\pinn_inverse_v0\triangle_port_only\`

Status: completed. Generated training outputs are reproducible and are not
committed, except the lightweight summary JSON.

## PINN inverse v1 physics-regularized audit

- Single-run trainer: `scripts\train_pinn_inverse_v1.py`
- Batch runner: `scripts\run_pinn_inverse_v1_experiments.py`
- Summary: `outputs\tables\pinn_inverse_v1_summary.json`
- Design: `docs\pinn_inverse_v1_physics_design.md`
- Report: `docs\pinn_inverse_v1_report.md`

Runs:

- `configs\pinn_inverse_v1_triangle_physics.yaml` ->
  `outputs\pinn_inverse_v1\triangle_physics\`
- `configs\pinn_inverse_v1_triangle_weak_anchor.yaml` ->
  `outputs\pinn_inverse_v1\triangle_weak_anchor\`
- `configs\pinn_inverse_v1_triangle_port_physics.yaml` ->
  `outputs\pinn_inverse_v1\triangle_port_physics\`

Status: completed as a physics-regularized approximation. Generated training
outputs are reproducible and are not committed, except the lightweight summary
JSON.

## PINN inverse v1.1 residual-balancing audit

- Batch runner: `scripts\run_pinn_inverse_v1_1_experiments.py`
- Summary: `outputs\tables\pinn_inverse_v1_1_summary.json`
- Report: `docs\pinn_inverse_v1_1_report.md`
- Codex report: `docs\codex_reports\pinn_inverse_v1_1_report.md`

Runs:

- `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml` ->
  `outputs\pinn_inverse_v1_1\triangle_physics_balanced\`
- `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml` ->
  `outputs\pinn_inverse_v1_1\triangle_port_physics_balanced\`

Status: completed as a residual-balancing audit. Generated training outputs are
reproducible and are not committed, except the lightweight summary JSON.

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

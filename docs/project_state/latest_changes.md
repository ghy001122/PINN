# Latest changes

## PINN inverse v0 ablation audit

Added:

- `configs\pinn_inverse_v0_triangle_full_anchor.yaml`
- `configs\pinn_inverse_v0_triangle_weak_anchor.yaml`
- `configs\pinn_inverse_v0_triangle_port_only.yaml`
- `scripts\run_pinn_inverse_v0_ablation.py`
- `docs\pinn_inverse_v0_ablation_report.md`
- `outputs\tables\pinn_inverse_v0_ablation_summary.json`
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
- `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md`

Modified:

- `.gitignore`: allows the lightweight ablation summary JSON while continuing
  to ignore large generated outputs.
- `scripts\train_pinn_inverse_v0.py`: adds normalized RMSE metrics based on
  frozen Ground Truth v1.1 acceptance scales.
- `tests\test_pinn_inverse_v0.py`: adds ablation config and smoke-test checks.

Deleted:

- None.

Frozen Ground Truth acceptance files were not modified.

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

## Evidence-chain patch

Added:

- `docs\codex_reports\evidence_chain_patch_report.md`

Modified:

- `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md`: replaced the
  old non-specific commit text with the concrete synced audit commit hash
  `ffad313297c78cfc158e6ae270c3b86639d79e1d`.
- `docs\project_state\repo_tree.md`: aligned the tree snapshot with the actual
  tracked repository structure and documented ignored generated outputs.
- `docs\project_state\file_inventory.md`: documented the evidence-chain report
  and ablation smoke-test path.
- `docs\project_state\reproducibility.md`: documented the ablation smoke-test
  command.
- `scripts\run_pinn_inverse_v0_ablation.py`: added `--smoke-test` without
  changing official ablation metrics.
- `tests\test_pinn_inverse_v0.py`: switched the ablation smoke test to the new
  `--smoke-test` flag.

Deleted:

- None.

## PINN inverse v1 physics residuals

Added:

- `configs\pinn_inverse_v1_triangle_physics.yaml`
- `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`
- `configs\pinn_inverse_v1_triangle_port_physics.yaml`
- `src\pinnpcm\pinn\physics_residuals.py`
- `scripts\train_pinn_inverse_v1.py`
- `scripts\run_pinn_inverse_v1_experiments.py`
- `tests\test_pinn_inverse_v1.py`
- `docs\pinn_inverse_v1_physics_design.md`
- `docs\pinn_inverse_v1_report.md`
- `docs\codex_reports\pinn_inverse_v1_physics_report.md`
- `outputs\tables\pinn_inverse_v1_summary.json`

Modified:

- `.gitignore`: ignores generated v1 training artifacts while allowing the
  lightweight v1 summary JSON.
- Project state and registry files now document the v1 phase and outputs.

Deleted:

- None.

Frozen Ground Truth v1.1 files were not modified.

## PINN inverse v1.1 residual balancing

Added:

- `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`
- `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`
- `scripts\run_pinn_inverse_v1_1_experiments.py`
- `docs\pinn_inverse_v1_1_report.md`
- `docs\codex_reports\pinn_inverse_v1_1_report.md`
- `outputs\tables\pinn_inverse_v1_1_summary.json`

Modified:

- `scripts\train_pinn_inverse_v1.py`: added optional residual running-scale
  balancing, warmup scheduling, per-field anchor weights, and sigma initial
  regularization.
- `tests\test_pinn_inverse_v1.py`: added v1.1 config checks.
- `.gitignore`: ignores generated v1.1 training artifacts while allowing the
  lightweight v1.1 summary JSON.
- Project status and registry files now document v1.1.

Deleted:

- None.

Frozen Ground Truth v1.1 files and existing v0/v1 summaries were not modified.

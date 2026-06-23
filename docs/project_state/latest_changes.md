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

## PINN identifiability audit

Added:

- `scripts\analyze_pinn_identifiability.py`
- `tests\test_pinn_identifiability.py`
- `docs\pinn_identifiability_audit_report.md`
- `docs\codex_reports\pinn_identifiability_audit_report.md`
- `outputs\tables\pinn_identifiability_summary.json`
- `outputs\tables\pinn_identifiability_correlation.csv`

Generated but not committed:

- `outputs\figures\pinn_identifiability\correlation_heatmap.png`
- `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
- `outputs\figures\pinn_identifiability\lag_correlation.png`

Modified:

- `.gitignore`: allows the lightweight identifiability JSON and CSV while
  keeping generated figures ignored.
- `PROJECT_STATE.md`, `RESEARCH_LOG.md`, `NEXT_ACTIONS.md`,
  `EXPERIMENT_REGISTRY.md`, and `FIGURE_REGISTRY.md`: document the
  identifiability audit.
- `docs\project_state\repo_tree.md`, `docs\project_state\file_inventory.md`,
  `docs\project_state\latest_changes.md`, and
  `docs\project_state\reproducibility.md`: update the evidence-chain snapshot.

Deleted:

- None.

Frozen Ground Truth v1.1 files and existing v0/v1/v1.1 results were not
modified.

## v2a gamma_sub identifiability audit

Added:

- `scripts\scan_gamma_sub_identifiability.py`
- `scripts\invert_gamma_sub_v0.py`
- `tests\test_gamma_sub_identifiability.py`
- `docs\gamma_sub_identifiability_report.md`
- `docs\codex_reports\gamma_sub_identifiability_audit_report.md`
- `outputs\tables\gamma_sub_identifiability_summary.json`

Generated but not committed:

- `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`

Modified:

- `.gitignore`: allows the lightweight gamma_sub summary JSON while keeping
  generated figures ignored.
- `PROJECT_STATE.md`, `RESEARCH_LOG.md`, `NEXT_ACTIONS.md`,
  `EXPERIMENT_REGISTRY.md`, `DATASET_REGISTRY.md`, and `FIGURE_REGISTRY.md`:
  document the v2a reduced inverse audit.
- `docs\project_state\repo_tree.md`, `docs\project_state\file_inventory.md`,
  `docs\project_state\latest_changes.md`, and
  `docs\project_state\reproducibility.md`: update the project-state snapshot.

Deleted:

- None.

Frozen Ground Truth v1.1 files and existing v0/v1/v1.1 results were not
modified.

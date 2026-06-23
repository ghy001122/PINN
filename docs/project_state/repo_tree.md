# Repository tree

Current high-level structure:

```text
.
|-- AGENTS.md
|-- configs/
|   |-- gt_v1.yaml
|   |-- gt_v1_acceptance_ltp_ltd.yaml
|   |-- gt_v1_acceptance_triangle.yaml
|   |-- pinn_inverse_v0_triangle.yaml
|   |-- pinn_inverse_v0_triangle_full_anchor.yaml
|   |-- pinn_inverse_v0_triangle_weak_anchor.yaml
|   |-- pinn_inverse_v0_triangle_port_only.yaml
|   |-- pinn_inverse_v1_triangle_physics.yaml
|   |-- pinn_inverse_v1_triangle_weak_anchor.yaml
|   |-- pinn_inverse_v1_triangle_port_physics.yaml
|   |-- pinn_inverse_v1_1_triangle_physics_balanced.yaml
|   |-- pinn_inverse_v1_1_triangle_port_physics_balanced.yaml
|   `-- pinn_v1.yaml
|-- data/
|   |-- README.md
|   `-- processed/
|       `-- .gitkeep
|-- docs/
|   |-- codex_reports/
|   |   |-- gamma_sub_confounding_audit_report.md
|   |   |-- gamma_sub_identifiability_audit_report.md
|   |   |-- evidence_chain_patch_report.md
|   |   |-- pinn_inverse_v0_ablation_audit_report.md
|   |   |-- pinn_inverse_v1_physics_report.md
|   |   |-- pinn_inverse_v1_1_report.md
|   |   `-- pinn_identifiability_audit_report.md
|   |-- project_state/
|   |   |-- file_inventory.md
|   |   |-- latest_changes.md
|   |   |-- repo_tree.md
|   |   `-- reproducibility.md
|   |-- data_provenance.md
|   |-- device_anchor.md
|   |-- experiment_plan.md
|   |-- gamma_sub_confounding_report.md
|   |-- gamma_sub_identifiability_report.md
|   |-- gt_v1_acceptance_report.md
|   |-- method_equations.md
|   |-- pinn_inverse_v0_ablation_report.md
|   |-- pinn_inverse_v1_physics_design.md
|   |-- pinn_inverse_v1_report.md
|   |-- pinn_inverse_v1_1_report.md
|   |-- pinn_identifiability_audit_report.md
|   `-- reviewer_defense.md
|-- outputs/
|   |-- checkpoints/
|   |   `-- .gitkeep
|   |-- figures/
|   |   `-- .gitkeep
|   |-- logs/
|   |   `-- .gitkeep
|   |-- tables/
|   |   |-- .gitkeep
|   |   |-- gamma_sub_confounding_summary.json
|   |   |-- gamma_sub_identifiability_summary.json
|   |   |-- gamma_sub_sensitivity_ranking.csv
|   |   |-- pinn_identifiability_correlation.csv
|   |   |-- pinn_identifiability_summary.json
|   |   |-- pinn_inverse_v0_ablation_summary.json
|   |   |-- pinn_inverse_v1_summary.json
|   |   `-- pinn_inverse_v1_1_summary.json
|   |-- pinn_inverse_v0/
|   |   `-- ignored generated training artifacts
|   |-- pinn_inverse_v1/
|   |   `-- ignored generated training artifacts
|   `-- pinn_inverse_v1_1/
|       `-- ignored generated training artifacts
|-- scripts/
|   |-- analyze_gt_v1.py
|   |-- analyze_pinn_identifiability.py
|   |-- audit_gamma_sub_confounding.py
|   |-- evaluate_v1.py
|   |-- invert_gamma_sub_v0.py
|   |-- invert_gamma_sub_with_mismatch.py
|   |-- plot_gt_v1.py
|   |-- run_gt_v1.py
|   |-- run_gt_v1_acceptance.py
|   |-- run_pinn_inverse_v0_ablation.py
|   |-- run_pinn_inverse_v1_experiments.py
|   |-- run_pinn_inverse_v1_1_experiments.py
|   |-- scan_gt_v1.py
|   |-- scan_gamma_sub_identifiability.py
|   |-- train_pinn_inverse_v0.py
|   |-- train_pinn_inverse_v1.py
|   `-- train_pinn_v1.py
|-- src/
|   `-- pinnpcm/
|       |-- baselines/
|       |-- physics/
|       |-- pinn/
|       |-- utils/
|       `-- visualization/
|-- tests/
|   |-- test_conductivity.py
|   |-- test_data_shapes.py
|   |-- test_electrostatics.py
|   |-- test_gt_profiles.py
|   |-- test_gt_solver_smoke.py
|   |-- test_imports.py
|   |-- test_gamma_sub_identifiability.py
|   |-- test_pinn_identifiability.py
|   |-- test_pinn_inverse_v0.py
|   |-- test_pinn_inverse_v1.py
|   `-- test_voltage_protocols.py
|-- DATASET_REGISTRY.md
|-- EXPERIMENT_REGISTRY.md
|-- FIGURE_REGISTRY.md
|-- NEXT_ACTIONS.md
|-- PROJECT_STATE.md
|-- RESEARCH_LOG.md
|-- README.md
|-- pyproject.toml
`-- requirements.txt
```

Generated large outputs remain under `data\processed\` and `outputs\` and are
not intended for normal Git commits. Committed output artifacts are limited to
lightweight summary JSON files such as
`outputs\tables\pinn_inverse_v0_ablation_summary.json` and
`outputs\tables\pinn_inverse_v1_summary.json`, and
`outputs\tables\pinn_inverse_v1_1_summary.json`,
`outputs\tables\pinn_identifiability_summary.json`, and
`outputs\tables\pinn_identifiability_correlation.csv`, and
`outputs\tables\gamma_sub_identifiability_summary.json`,
`outputs\tables\gamma_sub_confounding_summary.json`, and
`outputs\tables\gamma_sub_sensitivity_ranking.csv`.

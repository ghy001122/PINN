# Repository tree

Current high-level structure:

```text
.
|-- AGENTS.md
|-- CODEX_CONTEXT.md
|-- configs/
|   |-- gt_v1.yaml
|   |-- gt_v1_acceptance_ltp_ltd.yaml
|   |-- gt_v1_acceptance_triangle.yaml
|   |-- gamma_sub_constrained_inversion.yaml
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
|   |   |-- gamma_sub_constrained_inversion_report.md
|   |   |-- evidence_chain_patch_report.md
|   |   |-- documentation_structure_cleanup_report.md
|   |   |-- local_codex_context_integration_report.md
|   |   |-- pinn_inverse_v0_ablation_audit_report.md
|   |   |-- pinn_inverse_v1_physics_report.md
|   |   |-- pinn_inverse_v1_1_report.md
|   |   `-- pinn_identifiability_audit_report.md
|   |-- literature_notes/
|   |   |-- gamma_sub_evidence_digest.md
|   |   `-- pinn_phase_change_literature_digest.md
|   |-- project_state/
|   |   |-- file_inventory.md
|   |   |-- latest_changes.md
|   |   |-- repo_tree.md
|   |   `-- reproducibility.md
|   |-- research_strategy/
|   |   |-- active_phase.md
|   |   |-- codex_workflow_rules.md
|   |   |-- context_index.md
|   |   |-- context_loading_policy.md
|   |   |-- current_research_handoff.md
|   |   `-- next_task_literature_backed_constrained_gamma_sub.md
|   |-- data_provenance.md
|   |-- device_anchor.md
|   |-- experiment_plan.md
|   |-- gamma_sub_confounding_report.md
|   |-- gamma_sub_constrained_inversion_report.md
|   |-- literature_gamma_sub_evidence_chain.md
|   |-- gamma_sub_identifiability_report.md
|   |-- gt_v1_acceptance_report.md
|   |-- method_equations.md
|   |-- parameter_prior_registry.md
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
|   |   |-- gamma_sub_constrained_inversion_summary.json
|   |   |-- gamma_sub_prior_width_sweep.csv
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
|-- references/
|   |-- papers/
|   |   `-- PAPER_REGISTRY.md
|   `-- project_sources/
|       `-- README.md
|-- scripts/
|   |-- analyze_gt_v1.py
|   |-- analyze_pinn_identifiability.py
|   |-- audit_gamma_sub_confounding.py
|   |-- evaluate_v1.py
|   |-- invert_gamma_sub_v0.py
|   |-- invert_gamma_sub_with_mismatch.py
|   |-- invert_gamma_sub_constrained.py
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
|   |-- test_gamma_sub_constrained.py
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

The local reference pack itself is not copied into the repository. Only compact
context, literature digest, and routing files are tracked.

## Literature-Anchored Gamma_Sub Pack Addendum

New top-level additions in this pack:

- `configs/literature_phase_change_parameter_sanity.yaml`
- `configs/literature_curve_fit_external_anchor.yaml`
- `configs/gamma_sub_tsw_calibration_necessity.yaml`
- `configs/gamma_sub_simulator_backed_sequential_protocol_validation.yaml`
- `scripts/audit_literature_phase_change_parameter_sanity.py`
- `scripts/fit_literature_phase_change_curves.py`
- `scripts/audit_gamma_sub_tsw_calibration_necessity.py`
- `scripts/audit_gamma_sub_simulator_backed_sequential_protocol_validation.py`
- `scripts/build_manuscript_style_gamma_sub_figures.py`
- `docs/literature/`
- `data/literature/`

## External Curve And Calibrated Gamma_Sub Workflow Additions

- `configs/literature_curve_ingestion.yaml`
- `configs/literature_curve_fit_external_anchor_v2.yaml`
- `configs/gamma_sub_tsw_calibration_workflow.yaml`
- `configs/gamma_sub_calibrated_sequential_protocol_validation.yaml`
- `scripts/ingest_literature_digitized_curves.py`
- `scripts/fit_literature_phase_change_curves_v2.py`
- `scripts/audit_gamma_sub_tsw_calibration_workflow.py`
- `scripts/audit_gamma_sub_calibrated_sequential_protocol_validation.py`
- `scripts/build_external_anchor_claim_stress_test.py`
- `scripts/build_submission_ready_gamma_sub_figures.py`
- `tests/test_literature_curve_ingestion.py`
- `tests/test_literature_curve_fit_external_anchor_v2.py`
- `tests/test_gamma_sub_tsw_calibration_workflow.py`
- `tests/test_gamma_sub_calibrated_sequential_protocol_validation.py`
- `tests/test_external_anchor_claim_stress_test.py`
- `docs/paper/main_text_results_v1.md`
- `docs/paper/methods_v1.md`
- `docs/paper/limitations_v1.md`
- `docs/paper/abstract_v1.md`
- `docs/paper/title_candidates.md`


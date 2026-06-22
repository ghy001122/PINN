# Repository tree

Current high-level structure:

```text
.
|-- configs/
|   |-- gt_v1.yaml
|   |-- gt_v1_acceptance_ltp_ltd.yaml
|   |-- gt_v1_acceptance_triangle.yaml
|   |-- pinn_inverse_v0_triangle.yaml
|   |-- pinn_inverse_v0_triangle_full_anchor.yaml
|   |-- pinn_inverse_v0_triangle_weak_anchor.yaml
|   |-- pinn_inverse_v0_triangle_port_only.yaml
|   `-- pinn_v1.yaml
|-- data/
|   |-- README.md
|   `-- processed/
|-- docs/
|   |-- gt_v1_acceptance_report.md
|   |-- method_equations.md
|   |-- pinn_inverse_v0_ablation_report.md
|   |-- codex_reports/
|   `-- project_state/
|-- outputs/
|   |-- checkpoints/
|   |-- figures/
|   |-- logs/
|   |-- pinn_inverse_v0/
|   `-- tables/
|-- scripts/
|   |-- run_gt_v1_acceptance.py
|   |-- run_pinn_inverse_v0_ablation.py
|   |-- train_pinn_inverse_v0.py
|   `-- train_pinn_v1.py
|-- src/
|   `-- pinnpcm/
|       |-- physics/
|       |-- pinn/
|       |-- utils/
|       `-- visualization/
|-- tests/
|-- PROJECT_STATE.md
|-- RESEARCH_LOG.md
|-- NEXT_ACTIONS.md
|-- EXPERIMENT_REGISTRY.md
|-- DATASET_REGISTRY.md
|-- FIGURE_REGISTRY.md
|-- pyproject.toml
|-- requirements.txt
`-- README.md
```

Generated large outputs remain under `data\processed\` and `outputs\` and are
not intended for normal Git commits.

# Codex Report: Gamma_Sub Paper-Readiness Robustness Pack

## Scope

Repository: `https://github.com/ghy001122/PINN`

This task adds a paper-readiness robustness pack after commit
`35948ad830410f87dd384ccaedf95c4a410deceb`. All results are synthetic numerical
digital-twin benchmark results. They are not experimental data, not full
three-dimensional device simulations, and not sparse-port full-field recovery.

## Added Files

- `docs/paper/model_hierarchy_and_claim_boundary.md`
- `docs/paper/equation_variable_registry.md`
- `docs/paper/experiment_to_figure_mapping.md`
- `scripts/audit_gamma_sub_paper_readiness.py`
- `tests/test_gamma_sub_paper_readiness.py`
- `outputs/tables/gamma_sub_paper_readiness_summary.json`
- `outputs/tables/gamma_sub_observation_sensitivity.csv`
- `outputs/tables/gamma_sub_offgrid_summary.csv`
- `docs/gamma_sub_paper_readiness_report.md`
- `docs/codex_reports/gamma_sub_paper_readiness_report.md`

## Updated Files

- `.gitignore`
- `PROJECT_STATE.md`
- `RESEARCH_LOG.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`
- `docs/project_state/file_inventory.md`

## Core Results

- Off-grid true `gamma_sub`: `462000000.0`
- Nearest-grid estimate: `450000000.0`
- Nearest-grid relative error: `0.025974025974025976`
- Local refinement estimate: `462018731.3745052`
- Local refinement relative error: `4.054410066065334e-05`
- Observation counts tested: `8`, `16`, `32`, `64`
- Nominal relative error for all observation counts: `0.0`
- Most dangerous confounder across observation-count sensitivity: `T_sw`
- Frozen GT hash check: unchanged

## Paper Readiness Conclusion

The current one-dimensional reduced-order benchmark can support a method-oriented
SCI small paper if the claim is restricted to sparse-port identifiability and
constrained `gamma_sub` inversion under fixed or tightly bounded priors. It does
not support experimental-data claims, complete 3D device simulation claims, or
sparse-port full hidden-field recovery claims.

## Validation

- `python scripts/audit_gamma_sub_paper_readiness.py`: passed.
- `python -m pytest`: recorded after final validation for this task.
- Frozen Ground Truth files were not modified.
- No large binary outputs were added.
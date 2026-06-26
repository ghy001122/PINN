# Codex Report: Literature-Backed Constrained Gamma_Sub Inversion

## Scope

Repository: `https://github.com/ghy001122/PINN`

This task implemented the constrained `gamma_sub` inversion stage. It preserves
frozen Ground Truth v1.1 and prior v0/v1/v1.1 evidence. All results are
synthetic numerical digital-twin benchmark results, not experimental data.

## Added Files

- `configs/gamma_sub_constrained_inversion.yaml`
- `scripts/invert_gamma_sub_constrained.py`
- `tests/test_gamma_sub_constrained.py`
- `docs/literature_gamma_sub_evidence_chain.md`
- `docs/parameter_prior_registry.md`
- `docs/gamma_sub_constrained_inversion_report.md`
- `docs/codex_reports/gamma_sub_constrained_inversion_report.md`
- `outputs/tables/gamma_sub_constrained_inversion_summary.json`
- `outputs/tables/gamma_sub_prior_width_sweep.csv`

## Updated Files

- `.gitignore`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `RESEARCH_LOG.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/project_state/repo_tree.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`

## Metrics

- True `gamma_sub`: `450000000.0`
- Clean nominal estimate: `450000000.0`
- Clean nominal relative error: `0.0`
- Maximum relative error across tested cases: `1.2222222222222223`
- Most dangerous confounder: `T_sw`
- First tested unstable prior width: `0.05`

## Conclusion

The constrained nominal reduced inverse is stable on the frozen synthetic
benchmark, including the tested nominal noise cases. The prior-width sweep shows
that uncontrolled `T_sw` mismatch rapidly destabilizes `gamma_sub` inversion.
The paper claim should therefore be limited to literature-guided or
engineering-prior constrained `gamma_sub` inversion, not unconstrained full
hidden-field recovery.

## Validation

- `python scripts/invert_gamma_sub_constrained.py --config configs/gamma_sub_constrained_inversion.yaml`: passed and generated JSON/CSV evidence.
- `python -m pytest`: recorded after final validation for this task.
- Frozen Ground Truth files were not modified.
- No large binary outputs were added.

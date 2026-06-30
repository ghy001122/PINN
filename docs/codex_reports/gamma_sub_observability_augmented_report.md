# Gamma_Sub Observability-Augmented Audit Codex Report

## Repository

- Repo: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Input commits referenced by task: `b3fbfc58ec23058351e7009e9a2797095faefd4a`, `98b111ab7f1d835a88b0fd9456d983a29e4fc0a9`
- Task type: lightweight synthetic numerical observability audit
- Benchmark type: synthetic numerical digital-twin benchmark only

## Changed Files

- `configs/gamma_sub_observability_augmented.yaml`
- `scripts/audit_gamma_sub_observability_augmented.py`
- `tests/test_gamma_sub_observability_augmented.py`
- `outputs/tables/gamma_sub_observability_augmented_summary.json`
- `outputs/tables/gamma_sub_observability_augmented_cases.csv`
- `docs/gamma_sub_observability_augmented_report.md`
- `docs/codex_reports/gamma_sub_observability_augmented_report.md`
- `CODEX_CONTEXT.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `docs/research_strategy/active_phase.md`
- `docs/paper/sci_manuscript_evidence_matrix.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `RESEARCH_LOG.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/reproducibility.md`
- `.gitignore`

## Audit Design

The audit estimates only `gamma_sub` and keeps frozen Ground Truth v1.1 files read-only. It generates controlled synthetic `T_sw` mismatch targets to test whether minimal extra observability can reduce `gamma_sub` / `T_sw` confounding.

Cases include:

- `port_only_wide_tsw`: terminal `G/I` only under wide `T_sw` mismatch.
- `port_plus_temperature_anchor`: terminal `G/I` plus sparse synthetic temperature anchors with `n_T_anchor = 2, 4, 8`.
- `port_plus_tsw_prior`: terminal `G/I` with wide versus narrow `T_sw` prior width.
- `port_plus_temperature_anchor_and_tsw_prior`: sparse synthetic temperature anchors plus narrow `T_sw` prior.

Temperature anchors are synthetic observability probes from the numerical target. They are not real experimental temperature measurements.

## Key Results

- Port-only wide `T_sw` mismatch relative error: `1.2222222222222223`.
- Best temperature-anchor-only relative error: `1.2222222222222223`.
- Best narrow-`T_sw`-prior relative error: `0.2222222222222222`.
- Best combined relative error: `0.2222222222222222`.
- Temperature anchors alone reduced bias: `False`.
- Narrow `T_sw` prior reduced bias: `True`.
- Frozen inputs unchanged: `True`.

Interpretation: in the current candidate-grid audit, minimal sparse temperature anchors alone do not resolve the wide `T_sw` mismatch bias. Independent or tight `T_sw` prior calibration is the stronger observability requirement.

## Validation

Commands run:

```powershell
.\.venv\Scripts\python.exe scripts\audit_gamma_sub_observability_augmented.py --config configs\gamma_sub_observability_augmented.yaml
.\.venv\Scripts\python.exe -m pytest tests/test_gamma_sub_observability_augmented.py tests/test_gamma_sub_constrained.py tests/test_gamma_sub_continuous_refinement.py
```

Results:

- Audit script completed and wrote `outputs/tables/gamma_sub_observability_augmented_summary.json` and `outputs/tables/gamma_sub_observability_augmented_cases.csv`.
- Targeted tests passed: `5 passed in 4.98s`.

## Boundary Checks

- Modified frozen Ground Truth v1.1: No.
- Added F-SPS-PINN experiments: No.
- Ran large training: No.
- Claimed real experimental validation: No.
- Claimed sparse-port unique full hidden-field recovery: No.

## Manuscript Use

Use this audit as reviewer-defense evidence. It strengthens the paper's central limitation: `gamma_sub` inversion from sparse terminal data remains conditional, and `T_sw` must be independently calibrated or tightly bounded. It does not turn the work into full hidden-field recovery.
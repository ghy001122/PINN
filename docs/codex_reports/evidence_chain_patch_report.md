# Evidence-chain patch report

## Repository

- GitHub repo URL: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Synced audit commit checked before this patch:
  `ffad313297c78cfc158e6ae270c3b86639d79e1d`

## Scope

This patch fixes evidence-chain consistency around the already-synced PINN
inverse v0 ablation audit. It does not redesign the experiment, enter PINN v1,
rerun the official full ablation metrics, or modify Ground Truth v1.1 frozen
configs, frozen data, main equations, acceptance report, or frozen metrics.

## Evidence-chain issues fixed

- Replaced the old non-specific commit text in
  `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md` with the
  concrete synced audit commit hash
  `ffad313297c78cfc158e6ae270c3b86639d79e1d`.
- Confirmed that the root project status files are present and tracked:
  - `PROJECT_STATE.md`
  - `RESEARCH_LOG.md`
  - `NEXT_ACTIONS.md`
  - `EXPERIMENT_REGISTRY.md`
  - `DATASET_REGISTRY.md`
  - `FIGURE_REGISTRY.md`
- Fixed `docs\project_state\repo_tree.md` so it reflects the current tracked
  repository structure, including the committed lightweight ablation summary and
  ignored generated training-output directories.
- Confirmed the new Markdown and YAML files are multi-line, readable files, not
  single-line long-text artifacts.
- Added a dedicated ablation smoke-test path so evidence-chain checks can run
  without overwriting `outputs\tables\pinn_inverse_v0_ablation_summary.json`.

## Files updated by this patch

- `scripts\run_pinn_inverse_v0_ablation.py`
- `tests\test_pinn_inverse_v0.py`
- `docs\codex_reports\pinn_inverse_v0_ablation_audit_report.md`
- `docs\project_state\repo_tree.md`
- `docs\project_state\file_inventory.md`
- `docs\project_state\latest_changes.md`
- `docs\project_state\reproducibility.md`
- `docs\codex_reports\evidence_chain_patch_report.md`

## Verification

- `python -m pytest`: passed.
- `python scripts\run_pinn_inverse_v0_ablation.py --smoke-test`: passed.
- Official ablation metrics were not changed.
- `outputs\tables\pinn_inverse_v0_ablation_summary.json` was preserved as the
  official lightweight evidence JSON.

## Can the project enter PINN v1?

Yes, the evidence chain is now consistent enough to proceed to a PINN v1 design
step. The next phase should still preserve the academic boundary: all current
results are synthetic numerical digital-twin benchmark outputs, not measured
experimental data. PINN v1 should address v0 limitations by replacing or
constraining the direct `sigma(x,t)` surrogate with a more physical
differentiable closure and by adding stronger thermal/state-evolution checks.

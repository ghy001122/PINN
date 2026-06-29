# Experiment registry

## F-SPS-PINN v2 smoke training pipeline

- Config: `configs\pinn_inverse_v2_f_sps_smoke.yaml`
- Script: `scripts\train_pinn_inverse_v2_smoke.py`
- Test: `tests\test_pinn_inverse_v2_smoke.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`
- Report: `docs\codex_reports\pinn_inverse_v2_f_sps_smoke_report.md`

Status: completed as a minimal smoke training loop. It uses Fourier-pyramid features and `sigma = vo2_sigma(T, c_v, m)`, writes a lightweight JSON summary, and does not use the free `log_sigma` path. This is not a formal performance experiment.

## F-SPS-PINN architecture MVP

- VO2-like constitutive closure: `src\pinnpcm\physics\vo2_constitutive.py`
- Fourier pyramid and opt-in MLP: `src\pinnpcm\pinn\network.py`
- Dynamic residual gate: `src\pinnpcm\pinn\loss_balancer.py`
- Differentiable oscillation metrics: `src\pinnpcm\physics\oscillation_metrics.py`
- Tests: `tests\test_vo2_constitutive.py`, `tests\test_fourier_pyramid.py`, `tests\test_loss_balancer.py`, `tests\test_oscillation_metrics.py`
- Report: `docs\codex_reports\f_sps_pinn_architecture_mvp_report.md`

Status: completed as isolated architecture MVP, not a training result.

## Continuous off-grid gamma_sub refinement audit

- Script: `scripts\refine_gamma_sub_continuous.py`
- Test: `tests\test_gamma_sub_continuous_refinement.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_continuous_refinement_summary.json`
- Cases table: `outputs\tables\gamma_sub_continuous_refinement_cases.csv`
- Report: `docs\gamma_sub_continuous_refinement_report.md`
- Codex report: `docs\codex_reports\gamma_sub_continuous_refinement_report.md`

Status: completed as a simulator-backed off-grid scalar refinement audit. The lightweight JSON and CSV are committed evidence. No frozen Ground Truth file was modified.

## Paper-readiness gamma_sub robustness pack

- Script: `scripts\audit_gamma_sub_paper_readiness.py`
- Test: `tests\test_gamma_sub_paper_readiness.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_paper_readiness_summary.json`
- Observation-count table: `outputs\tables\gamma_sub_observation_sensitivity.csv`
- Off-grid table: `outputs\tables\gamma_sub_offgrid_summary.csv`
- Report: `docs\gamma_sub_paper_readiness_report.md`
- Codex report: `docs\codex_reports\gamma_sub_paper_readiness_report.md`

Status: completed as a paper-readiness robustness audit. The lightweight JSON
and CSV are committed evidence. No frozen Ground Truth file was modified.

## Literature-backed constrained gamma_sub inversion

- Config: `configs\gamma_sub_constrained_inversion.yaml`
- Script: `scripts\invert_gamma_sub_constrained.py`
- Test: `tests\test_gamma_sub_constrained.py`
- Input target: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Input sparse observation: `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- Summary: `outputs\tables\gamma_sub_constrained_inversion_summary.json`
- Prior-width sweep: `outputs\tables\gamma_sub_prior_width_sweep.csv`
- Report: `docs\gamma_sub_constrained_inversion_report.md`
- Codex report: `docs\codex_reports\gamma_sub_constrained_inversion_report.md`

Status: completed as a constrained reduced inverse audit. The lightweight JSON
and CSV are committed evidence. No frozen Ground Truth file was modified.

## Local Codex context workflow integration

- Source pack: `E:\pinn_codex_reference_pack`
- Context entry: `CODEX_CONTEXT.md`
- Active phase: `docs\research_strategy\active_phase.md`
- Loading policy: `docs\research_strategy\context_loading_policy.md`
- Handoff: `docs\research_strategy\current_research_handoff.md`
- Report: `docs\codex_reports\local_codex_context_integration_report.md`
- Cleanup report:
  `docs\codex_reports\documentation_structure_cleanup_report.md`

Status: completed as documentation and workflow integration only. No new
experiment, training run, Ground Truth revision, or generated dataset was
created.

## Ground Truth v1.1 acceptance

- Runner: `scripts\run_gt_v1_acceptance.py`
- Data output: `data\processed\gt_v1_acceptance\`
- Figure output: `outputs\figures\gt_v1_acceptance\`
- Table output: `outputs\tables\gt_v1_acceptance\`
- Report: `docs\gt_v1_acceptance_report.md`
- Status: frozen synthetic benchmark.

## PINN inverse v0 baseline

- Config: `configs\pinn_inverse_v0_triangle.yaml`
- Runner: `scripts\train_pinn_inverse_v0.py`
- Output: `outputs\pinn_inverse_v0\triangle\`
- Status: runnable proof-of-concept.

## PINN inverse v0 ablation audit

- Runner: `scripts\run_pinn_inverse_v0_ablation.py`
- Summary: `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- Report: `docs\pinn_inverse_v0_ablation_report.md`

Runs:

- `configs\pinn_inverse_v0_triangle_full_anchor.yaml` ->
  `outputs\pinn_inverse_v0\triangle_full_anchor\`
- `configs\pinn_inverse_v0_triangle_weak_anchor.yaml` ->
  `outputs\pinn_inverse_v0\triangle_weak_anchor\`
- `configs\pinn_inverse_v0_triangle_port_only.yaml` ->
  `outputs\pinn_inverse_v0\triangle_port_only\`

Status: completed. Generated training outputs are reproducible and are not
committed, except the lightweight summary JSON.

## PINN inverse v1 physics-regularized audit

- Single-run trainer: `scripts\train_pinn_inverse_v1.py`
- Batch runner: `scripts\run_pinn_inverse_v1_experiments.py`
- Summary: `outputs\tables\pinn_inverse_v1_summary.json`
- Design: `docs\pinn_inverse_v1_physics_design.md`
- Report: `docs\pinn_inverse_v1_report.md`

Runs:

- `configs\pinn_inverse_v1_triangle_physics.yaml` ->
  `outputs\pinn_inverse_v1\triangle_physics\`
- `configs\pinn_inverse_v1_triangle_weak_anchor.yaml` ->
  `outputs\pinn_inverse_v1\triangle_weak_anchor\`
- `configs\pinn_inverse_v1_triangle_port_physics.yaml` ->
  `outputs\pinn_inverse_v1\triangle_port_physics\`

Status: completed as a physics-regularized approximation. Generated training
outputs are reproducible and are not committed, except the lightweight summary
JSON.

## PINN inverse v1.1 residual-balancing audit

- Batch runner: `scripts\run_pinn_inverse_v1_1_experiments.py`
- Summary: `outputs\tables\pinn_inverse_v1_1_summary.json`
- Report: `docs\pinn_inverse_v1_1_report.md`
- Codex report: `docs\codex_reports\pinn_inverse_v1_1_report.md`

Runs:

- `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml` ->
  `outputs\pinn_inverse_v1_1\triangle_physics_balanced\`
- `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml` ->
  `outputs\pinn_inverse_v1_1\triangle_port_physics_balanced\`

Status: completed as a residual-balancing audit. Generated training outputs are
reproducible and are not committed, except the lightweight summary JSON.

## PINN identifiability audit

- Analyzer: `scripts\analyze_pinn_identifiability.py`
- Input: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Summary: `outputs\tables\pinn_identifiability_summary.json`
- Correlation table: `outputs\tables\pinn_identifiability_correlation.csv`
- Report: `docs\pinn_identifiability_audit_report.md`
- Codex report: `docs\codex_reports\pinn_identifiability_audit_report.md`

Figures:

- `outputs\figures\pinn_identifiability\correlation_heatmap.png`
- `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
- `outputs\figures\pinn_identifiability\lag_correlation.png`

Status: completed as a descriptive identifiability audit. The summary JSON and
CSV are lightweight committed evidence; generated figures are reproducible and
ignored by Git.

## v2a gamma_sub identifiability audit

- Scan script: `scripts\scan_gamma_sub_identifiability.py`
- Inversion script: `scripts\invert_gamma_sub_v0.py`
- Input: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Summary: `outputs\tables\gamma_sub_identifiability_summary.json`
- Report: `docs\gamma_sub_identifiability_report.md`
- Codex report: `docs\codex_reports\gamma_sub_identifiability_audit_report.md`

Figures:

- `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
- `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`

Status: completed as a reduced scalar inverse-problem audit. The summary JSON
is lightweight committed evidence; generated figures are reproducible and
ignored by Git.

## gamma_sub robustness and confounding audit

- Confounding script: `scripts\audit_gamma_sub_confounding.py`
- Mismatch inversion script: `scripts\invert_gamma_sub_with_mismatch.py`
- Input: `data\processed\gt_v1_acceptance\gt_triangle.npz`
- Summary: `outputs\tables\gamma_sub_confounding_summary.json`
- Sensitivity ranking: `outputs\tables\gamma_sub_sensitivity_ranking.csv`
- Report: `docs\gamma_sub_confounding_report.md`
- Codex report: `docs\codex_reports\gamma_sub_confounding_audit_report.md`

Status: completed as a robustness audit. The lightweight JSON and CSV are
committed evidence.

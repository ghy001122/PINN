# Project state

## Current phase

The project is in the literature-backed constrained `gamma_sub` inversion
preparation phase. Ground Truth v1.1 is frozen and serves as a synthetic
numerical digital-twin benchmark. The current work is not a new experiment; it
integrates the local reference pack into a low-token Codex context workflow and
prepares the next constrained reduced inverse-problem step.

## Research line

The only active research line is mesh-free, fully differentiable, multi-physics
digital twin modeling plus PINN inverse identification for phase-change or
memristive defect diagnosis and SCI paper preparation.

## Frozen benchmark

- `configs\gt_v1_acceptance_triangle.yaml`
- `configs\gt_v1_acceptance_ltp_ltd.yaml`
- `docs\gt_v1_acceptance_report.md`
- `data\processed\gt_v1_acceptance\manifest.json`
- `data\processed\gt_v1_acceptance\gt_triangle.npz`
- `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- `data\processed\gt_v1_acceptance\gt_ltp_ltd.npz`
- `data\processed\gt_v1_acceptance\obs_ltp_ltd_sparse.npz`

These files and the underlying Ground Truth v1.1 equations were not changed in
the PINN inverse v0 ablation audit.

## Latest completed work

- Integrated the local reference pack into compact context and research-strategy
  documents:
  - `CODEX_CONTEXT.md`
  - `docs\research_strategy\active_phase.md`
  - `docs\research_strategy\context_loading_policy.md`
  - `docs\research_strategy\context_index.md`
  - `docs\research_strategy\current_research_handoff.md`
  - `docs\research_strategy\codex_workflow_rules.md`
  - `docs\research_strategy\next_task_literature_backed_constrained_gamma_sub.md`
  - `docs\literature_notes\pinn_phase_change_literature_digest.md`
  - `docs\literature_notes\gamma_sub_evidence_digest.md`
  - `references\project_sources\README.md`
  - `references\papers\PAPER_REGISTRY.md`
- Added ablation configs:
  - `configs\pinn_inverse_v0_triangle_full_anchor.yaml`
  - `configs\pinn_inverse_v0_triangle_weak_anchor.yaml`
  - `configs\pinn_inverse_v0_triangle_port_only.yaml`
- Added batch runner:
  - `scripts\run_pinn_inverse_v0_ablation.py`
- Added normalized RMSE fields to PINN inverse v0 metrics.
- Added audit summary:
  - `outputs\tables\pinn_inverse_v0_ablation_summary.json`
- Added audit report:
  - `docs\pinn_inverse_v0_ablation_report.md`
- Added PINN inverse v1 physics-regularized workflow:
  - `configs\pinn_inverse_v1_triangle_physics.yaml`
  - `configs\pinn_inverse_v1_triangle_weak_anchor.yaml`
  - `configs\pinn_inverse_v1_triangle_port_physics.yaml`
  - `src\pinnpcm\pinn\physics_residuals.py`
  - `scripts\train_pinn_inverse_v1.py`
  - `scripts\run_pinn_inverse_v1_experiments.py`
  - `outputs\tables\pinn_inverse_v1_summary.json`
  - `docs\pinn_inverse_v1_physics_design.md`
  - `docs\pinn_inverse_v1_report.md`
- Added PINN inverse v1.1 residual-balancing workflow:
  - `configs\pinn_inverse_v1_1_triangle_physics_balanced.yaml`
  - `configs\pinn_inverse_v1_1_triangle_port_physics_balanced.yaml`
  - `scripts\run_pinn_inverse_v1_1_experiments.py`
  - `outputs\tables\pinn_inverse_v1_1_summary.json`
  - `docs\pinn_inverse_v1_1_report.md`
  - `docs\codex_reports\pinn_inverse_v1_1_report.md`
- Added PINN identifiability audit:
  - `scripts\analyze_pinn_identifiability.py`
  - `outputs\tables\pinn_identifiability_summary.json`
  - `outputs\tables\pinn_identifiability_correlation.csv`
  - `outputs\figures\pinn_identifiability\correlation_heatmap.png`
  - `outputs\figures\pinn_identifiability\spatial_sensitivity.png`
  - `outputs\figures\pinn_identifiability\lag_correlation.png`
  - `docs\pinn_identifiability_audit_report.md`
  - `docs\codex_reports\pinn_identifiability_audit_report.md`
- Added v2a `gamma_sub` identifiability audit:
  - `scripts\scan_gamma_sub_identifiability.py`
  - `scripts\invert_gamma_sub_v0.py`
  - `outputs\tables\gamma_sub_identifiability_summary.json`
  - `outputs\figures\gamma_sub_identifiability\gamma_sub_scan_responses.png`
  - `outputs\figures\gamma_sub_identifiability\gamma_sub_sensitivity.png`
  - `outputs\figures\gamma_sub_identifiability\gamma_sub_temperature_response.png`
  - `outputs\figures\gamma_sub_identifiability\gamma_sub_inversion_multistart.png`
  - `outputs\figures\gamma_sub_identifiability\gamma_sub_objective_profile.png`
  - `docs\gamma_sub_identifiability_report.md`
  - `docs\codex_reports\gamma_sub_identifiability_audit_report.md`
- Added `gamma_sub` robustness and confounding audit:
  - `scripts\audit_gamma_sub_confounding.py`
  - `scripts\invert_gamma_sub_with_mismatch.py`
  - `outputs\tables\gamma_sub_confounding_summary.json`
  - `outputs\tables\gamma_sub_sensitivity_ranking.csv`
  - `docs\gamma_sub_confounding_report.md`
  - `docs\codex_reports\gamma_sub_confounding_audit_report.md`

## Current evidence

The identifiability audit confirms that `G(t)` is nearly perfectly correlated
with `mean_sigma`, while aggregate `delta_T`, `delta_c_v`, and `m` are also
strongly correlated with `G(t)`. Terminal observations constrain the integrated
conductance response but do not uniquely recover the hidden thermal, defect,
state, and conductivity fields.

The v2a reduced audit confirms that `gamma_sub` is stably invertible in the
single-parameter setting when `D_v0`, `mu_v0`, `T_sw`, `tau_m`, and other
microscopic parameters remain fixed. This does not prove joint identifiability
with switching or defect parameters released.

The confounding audit shows that this reduced inverse story must stay
conditional. `T_sw` is more sensitive than `gamma_sub`, `sigma_on0` and `tau_m`
have response vectors close to `gamma_sub`, and mismatch inversion can produce
large systematic gamma bias.

The local reference-pack integration establishes a low-token context rule:
future non-trivial tasks should read `CODEX_CONTEXT.md` and
`docs\research_strategy\active_phase.md` first, then load only task-relevant
reports, summaries, literature notes, or code.

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin
benchmark results. They are not measured experimental data.

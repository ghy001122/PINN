# Project state

## Current phase

F-SPS-PINN architecture MVP is complete as an isolated, unit-tested architecture package. The v2 smoke training pipeline is complete and demonstrates a minimal forward/backward/train loop using the white-box `vo2_sigma(T, c_v, m)` closure on the frozen Ground Truth v1.1 triangle benchmark. The v2 small-run baseline and v2 phase-transition stress preflight are complete as bounded method-development evidence.

The current method-development checkpoint is `F-SPS-PINN v2 Fourier on/off ablation under stress`. It compares `vo2_sigma_fourier_off` and `vo2_sigma_fourier_on` under the same sharp-transition stress condition. This is a small-run synthetic numerical ablation, not a formal performance result.

The most defensible paper line remains the constrained reduced `gamma_sub` inverse problem under fixed or tightly bounded priors. F-SPS-PINN is a method-development path for replacing conductivity shortcuts and testing stiffness-aware training, not a validated full hidden-field recovery claim.

## Research line

The only active research line is mesh-free, fully differentiable, multi-physics digital twin modeling plus PINN inverse identification for phase-change or memristive defect diagnosis and SCI paper preparation.

## Frozen benchmark

- `configs\gt_v1_acceptance_triangle.yaml`
- `configs\gt_v1_acceptance_ltp_ltd.yaml`
- `docs\gt_v1_acceptance_report.md`
- `data\processed\gt_v1_acceptance\manifest.json`
- `data\processed\gt_v1_acceptance\gt_triangle.npz`
- `data\processed\gt_v1_acceptance\obs_triangle_sparse.npz`
- `data\processed\gt_v1_acceptance\gt_ltp_ltd.npz`
- `data\processed\gt_v1_acceptance\obs_ltp_ltd_sparse.npz`

Ground Truth v1.1 remains frozen across subsequent inverse, audit, and documentation-integration workflows unless an explicit Ground Truth revision is opened.

## Current evidence

The identifiability audit confirms that `G(t)` is nearly perfectly correlated with `mean_sigma`, while aggregate `delta_T`, `delta_c_v`, and `m` are also strongly correlated with `G(t)`. Terminal observations constrain the integrated conductance response but do not uniquely recover the hidden thermal, defect, state, and conductivity fields.

The v2a reduced audit confirms that `gamma_sub` is stably invertible in the single-parameter setting when `D_v0`, `mu_v0`, `T_sw`, `tau_m`, and other microscopic parameters remain fixed. This does not prove joint identifiability with switching or defect parameters released.

The confounding audit shows that this reduced inverse story must stay conditional. `T_sw` is more sensitive than `gamma_sub`, `sigma_on0` and `tau_m` have response vectors close to `gamma_sub`, and mismatch inversion can produce large systematic gamma bias.

The constrained inversion audit adds a literature-guided prior registry and a bounded prior-width sweep. It recovers the clean nominal `gamma_sub = 4.5e8` exactly on the frozen benchmark candidate grid, but the maximum tested relative error reaches `1.2222222222222223` under `T_sw` mismatch.

The paper-readiness robustness pack adds off-grid and observation-count checks. For off-grid `gamma_sub = 4.62e8`, the nearest-grid estimate has relative error `0.025974025974025976`, while local log-quadratic refinement has relative error `4.054410066065334e-05`. For `n_obs = 8, 16, 32, 64`, nominal recovery remains exact and `T_sw` remains the most dangerous confounder.

The continuous off-grid refinement audit replaces log-quadratic profile interpolation with scalar continuous optimization that re-runs the simulator at each trial `gamma_sub`. Across 36 official synthetic numerical digital-twin cases (`gamma_sub = 4.38e8, 4.62e8, 5.15e8`; `n_obs = 8, 16, 32, 64`; noise `0, 0.02, 0.05`), the maximum nearest-grid relative error is `0.08225108225108226`, the maximum continuous-refined relative error is `0.05565017963752034`, all true values are excluded from the candidate grid, and all refinement cases evaluate non-grid simulator calls.

The F-SPS-PINN architecture MVP added a VO2-like white-box conductivity closure, opt-in Fourier-pyramid embedding, dynamic residual gate, and differentiable oscillation metrics. These modules passed unit tests and preserve the old free `log_sigma` path as an ablation baseline.

The v2 smoke training pipeline adds `configs\pinn_inverse_v2_f_sps_smoke.yaml` and `scripts\train_pinn_inverse_v2_smoke.py`. It runs a 3-epoch CPU smoke test, reconstructs terminal `G/I` using `sigma = vo2_sigma(T, c_v, m)`, writes `outputs\tables\pinn_inverse_v2_f_sps_smoke_summary.json`, and confirms frozen input hashes and mtimes are unchanged.

The v2 small-run baseline adds `configs\pinn_inverse_v2_f_sps_baseline.yaml` and `scripts\run_pinn_inverse_v2_baseline.py`. It compares `free_log_sigma` and `white_box_vo2_sigma` with the same seed, epochs, anchor count, and sparse terminal observations, writes `outputs\tables\pinn_inverse_v2_f_sps_baseline_summary.json` and `outputs\tables\pinn_inverse_v2_f_sps_baseline_runs.csv`, and confirms frozen input hashes and mtimes are unchanged. The result is not a performance-superiority claim.

The v2 phase-transition stress preflight adds `configs\pinn_inverse_v2_phase_transition_stress.yaml` and `scripts\run_pinn_inverse_v2_phase_transition_stress.py`. It runs `mild_transition`, `sharp_transition`, `near_threshold`, and `high_contrast` cases using `white_box_vo2_sigma` with temperature-derived phase fraction, writes `outputs\tables\pinn_inverse_v2_phase_transition_stress_summary.json` and `outputs\tables\pinn_inverse_v2_phase_transition_stress_cases.csv`, and confirms frozen input hashes and mtimes are unchanged. The result is a stress preflight only, not a performance-superiority claim.

The v2 Fourier ablation adds `configs\pinn_inverse_v2_fourier_ablation.yaml` and `scripts\run_pinn_inverse_v2_fourier_ablation.py`. It compares `vo2_sigma_fourier_off` and `vo2_sigma_fourier_on` under the same sharp-transition stress condition, writes `outputs\tables\pinn_inverse_v2_fourier_ablation_summary.json` and `outputs\tables\pinn_inverse_v2_fourier_ablation_runs.csv`, and confirms frozen input hashes and mtimes are unchanged. Fourier on does not clearly outperform Fourier off in this small-run result.

Detailed historical file lists and reproduction entries live in:

- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `RESEARCH_LOG.md`
- `docs\project_state\file_inventory.md`
- `docs\codex_reports\`

## Boundary

All Ground Truth and PINN results are synthetic, numerical, digital-twin benchmark results. They are not measured experimental data, not full 3D device simulation results, and not sparse-port full hidden-field recovery.

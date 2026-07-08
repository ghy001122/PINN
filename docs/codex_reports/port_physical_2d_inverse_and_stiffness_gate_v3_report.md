# Port-Physical 2D Inverse And Stiffness-Gated Training v3 Report

All results are synthetic numerical digital-twin benchmark evidence, not experimental data.

## Snapshot

- Repository: `https://github.com/ghy001122/PINN`
- Branch: `main`
- Baseline commit before this task: `0ff469426a018aa89c5d20b1cd2181cb372ee10f`
- Final pushed commit: reported in the final Codex response after Git creates the commit hash.
- Frozen Ground Truth v1.1 modified: No
- Experimental data fabricated: No

## Changed Files

- `configs/high_risk_claim_ladder.yaml`
- `src/pinnpcm/experiments/port_physical_2d_inverse.py`
- `scripts/audit_port_physical_2d_inverse.py`
- `scripts/audit_stiffness_gated_fourier_fsps.py`
- `scripts/audit_integrated_stiffness_stl.py`
- `scripts/build_reviewer_defense_matrix.py`
- `tests/test_port_physical_2d_inverse.py`
- `tests/test_stiffness_gated_fourier_fsps.py`
- `tests/test_integrated_stiffness_stl.py`
- `outputs/tables/port_physical_2d_inverse_summary.json`
- `outputs/tables/port_physical_2d_inverse_cases.csv`
- `outputs/tables/stiffness_gated_fourier_fsps_summary.json`
- `outputs/tables/stiffness_gated_fourier_fsps_cases.csv`
- `outputs/tables/integrated_stiffness_stl_summary.json`
- `outputs/tables/integrated_stiffness_stl_cases.csv`
- `.gitignore`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/paper/claim_gate_resolution_matrix.md`
- `docs/paper/final_claim_matrix.md`
- `docs/manuscript/reviewer_defense_matrix.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`

## Port-Physical 2D Inverse

Implemented:

- White-box conductivity: `sigma(T,m)=sigma_ins+(sigma_met-sigma_ins)*clamp(m,eps,1-eps)`.
- Differentiable sheet conductance: `G(t)=mean_{x,y}(sigma(x,y,t))/L_x`.
- Low-rank coefficient optimization for `T` and `m`.
- Loss terms: `L_port_G`, `L_sparse_anchor`, `L_pde_T`, `L_pde_m`, `L_bounds`, `L_smooth_time`.
- Basis comparison: `analytic` vs `pod`.
- Anchor placement: `random_2pct`, `sensitivity_2pct`, `fisher_2pct`, `dense_5pct`.

Official quick-profile result:

- `num_cases`: `320`
- `all_finite_results`: `true`
- `uses_port_physical_observation`: `true`
- `uses_phase_mean_as_terminal_observation`: `false`
- Best protocol: `port_only`
- Best median field error: `0.7692662179470062`
- v2 reference median field error: `0.544268189851365`
- `improves_over_v2_best_actual_inverse`: `false`
- `field_recovery_status`: `forbidden`

Interpretation:

The port-physical observation is more faithful than a phase-mean terminal proxy, but it does not improve 2D hidden-field recovery. This strengthens the observability-boundary argument rather than enabling a stronger 2D inverse claim.

## POD Basis And Fisher Anchors

Basis comparison:

- `analytic` median field error: `0.5118682682514191`
- `pod` median field error: `1.1138866245746613`

Anchor comparison:

- `port_plus_random_2pct` median field error: `0.7815821766853333`
- `port_plus_sensitivity_2pct` median field error: `0.7783682346343994`
- `port_plus_fisher_2pct` median field error: `0.7785263955593109`
- `port_plus_dense_5pct` median field error: `0.7811321914196014`

Interpretation:

POD and Fisher-style anchors do not help in this quick profile. They remain failed-but-informative optimization directions, not positive claims.

## Stiffness-Gated Fourier/F-SPS

Implemented:

- Actual autograd reduced PINN training, not proxy multipliers.
- Stiffness indicator: `chi=max(s*(1-s)/w)=0.25/w`.
- Gate rule: use front-focused/asinh continuation only in stiff regimes; use vanilla branch in smooth regimes.
- Smooth degradation is a negative-control metric.

Official quick-profile result:

- `num_cases`: `96`
- `all_finite_results`: `true`
- `stiffness_gated_hybrid_status`: `qualified_supported`
- `sharp_gain_by_method.stiffness_gated_hybrid`: `0.17299439024092061`
- `smooth_degradation_by_method.stiffness_gated_hybrid`: `0.0`
- `smooth_negative_control_cleared`: `true`
- `universal_superiority_status`: `forbidden`

Interpretation:

The stiffness-gated hybrid fixes the earlier smooth-regime degradation issue in this quick actual-training audit. It supports only condition-limited method-development wording, not universal F-SPS/Fourier superiority.

## STL Repair Audit

Implemented:

- Matched-budget direct baseline.
- Continuation/asinh matched-budget baseline.
- Head-only STL repair after frozen trunk.
- Unfrozen-tail STL repair.
- Trunk/tail ablation through representation drift.

Official result:

- Integrated stiffness/STL cases: `162`
- `stl_repair_mode_implemented`: `true`
- Best repair algorithm: `STL_repair_head_only`
- Best repair gain over matched direct: `-0.14315251294108938`
- `stl_repair_success_rate_improves_over_matched_direct`: `false`
- `stl_repair_status`: `failed_but_informative`
- `full_stl_pinn_reproduction_status`: `forbidden`

Interpretation:

The repair audit did not turn STL into a positive result. It provides a clearer failure mode and a future optimization target.

## Claim Changes

Upgraded:

- Stiffness-gated hybrid: `qualified_supported` as condition-limited synthetic method-development evidence.

Downgraded or kept negative:

- Port-physical 2D field recovery: `forbidden`.
- POD basis benefit: `failed_but_informative`.
- Fisher anchor benefit: `failed_but_informative`.
- STL repair: `failed_but_informative`.

Still forbidden:

- Full arbitrary 2D hidden-field recovery.
- Port-only full-field recovery.
- Full STL-PINN reproduction.
- Universal F-SPS/Fourier superiority.
- Experimental validation.

## Validation

Commands required by the task:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_port_physical_2d_inverse.py tests/test_stiffness_gated_fourier_fsps.py tests/test_integrated_stiffness_stl.py
.\.venv\Scripts\python.exe -m pytest tests/test_high_risk_claim_ladder.py tests/test_fourier_fsps_conditional_superiority.py tests/test_claim_gate_resolution_matrix.py
.\.venv\Scripts\python.exe -m pytest
```

Official scripts run:

```powershell
.\.venv\Scripts\python.exe scripts\audit_port_physical_2d_inverse.py --profile quick
.\.venv\Scripts\python.exe scripts\audit_stiffness_gated_fourier_fsps.py
.\.venv\Scripts\python.exe scripts\audit_integrated_stiffness_stl.py
```

Validation results:

- `tests/test_port_physical_2d_inverse.py tests/test_stiffness_gated_fourier_fsps.py tests/test_integrated_stiffness_stl.py`: `3 passed`.
- `tests/test_high_risk_claim_ladder.py tests/test_fourier_fsps_conditional_superiority.py tests/test_claim_gate_resolution_matrix.py`: `5 passed`.
- Full repository test suite: `138 passed in 101.74s`.

## SCI Impact

This pack improves paper defensibility from three angles:

- Neural algorithm angle: stiffness-gated hybrid converts an unqualified Fourier/F-SPS idea into a condition-gated method-development result.
- Physics-constraint angle: 2D inverse now uses white-box conductivity and port conductance rather than a phase-mean terminal proxy.
- Generalization/claim-boundary angle: port-physical failure, POD failure, Fisher-anchor failure, and STL-repair failure explicitly define what the current evidence cannot support.

The main SCI manuscript claim should remain constrained `gamma_sub` inversion under calibrated/tightly bounded priors. v3 results are best used as supplementary method-development and reviewer-defense evidence.


# Control-Volume Multidomain OASIS And Inverse Repair v10 Report

Branch: `main`

Base commit: `8a4f07ed7c506ccaad2d00b0f10225e0f157553e`

Implementation anchor commit: `d23a576b2d8bb17a1d1f72a0cf81cc457d42e048`

Publish status: v10 implementation was pushed to `main` at `d23a576b2d8bb17a1d1f72a0cf81cc457d42e048`; later handoff/status cleanup commits may follow it in git history.

All results are synthetic numerical digital-twin benchmark evidence, not experimental data. Frozen Ground Truth v1.1 was not modified.

## Physical Semantics

P0 passed as a reduced implementation/activation gate.

- Electrical domain: TE / PCM / optional SnSe barrier / BE.
- Thermal domain: electrical domain plus substrate.
- The substrate `sigma=1e9` bypass was removed.
- VO2 `normalized_activated` and `literature_anchored` profiles are separate. The latter uses the published `Tc=332.8 K`, `w=7.19 K`, `C=145 pF`, and `Rload=12 kOhm` only as reduced literature-shape priors.
- NbO2 primary conduction is field-dependent Poole-Frenkel plus electrothermal feedback. Its phase-fraction multiplier is disabled unless an explicit ablation flag is set.
- The RC protocol integrates `C dVdev/dt=(Vin-Vdev)/RL-Idev`; it is not an imposed sinusoid.
- Threshold and holding voltages are extracted on separate branches. A zero/zero pair cannot pass activation.
- SnSe `k`, `sigma`, thickness, and barrier presence were swept as engineering-prior sensitivity checks.

Profile activation rates were VO2 normalized `1.0`, VO2 literature anchored `1.0`, and NbO2 PF/electrothermal `0.6666666666666666`. This does not constitute quantitative device calibration.

## P1 Control-Volume Multidomain Training

The requested five variants ran for 300 epochs and three seeds. V10 replaces the v9 time-smoothness proxy with electric flux balance, transient thermal energy balance, phase-state, port/circuit, and one-sided interface losses. Non-PCM target conductivity leakage was removed.

Strict full-mortar result:

- median `E_T`: `0.37563055753707886`;
- median `E_m`: `0.06811526417732239`;
- median interface residual: `106.15460205078125`;
- success rate: `0.0`;
- P1 gate: `False`.

Status: `failed_but_informative`. The ordered anchor-driven surrogate remains easier to fit, while the true CV/mortar path exposes residual-scale and boundary-face optimization failures. Loss decrease is not counted as success.

## P2 Protocol Design And Noisy Inverse

Each noisy target is regenerated and re-inverted for noise `[0, 0.02, 0.05]` and 10 seeds. Material families are mechanism-routed rather than forced into one incompatible parameter vector.

- NbO2 selected protocol: `triangle_V1.8_f0.55`; selected Jacobian rank `2` for four parameters. `Rc/Ea` median error is about `0.0594`, but `Rth_eff/tau_th` median error is about `1.313`; coverage also fails.
- VO2 selected protocol: `autonomous_rc`; selected Jacobian rank `1` for five parameters. The `Tc_up/Tc_down/width` local block is low-error, but the thermal block success rate is `0.6`, below the `0.70` gate.
- Overall status: `failed_but_informative`.

The finite candidate search is D/E-optimal within the declared candidate set; it is not a continuous global optimum. Rank-deficient selected candidates are explicitly reported and cannot support a solved inverse claim.

## P3 Multi-Terminal y-z Forward

The new finite-volume solver directly solves `div(sigma grad(phi))=0` with segmented top/side electrode faces, bottom ground, and insulating unassigned boundaries. Terminal currents are boundary-flux integrals.

- uniform-series limit relative error: `7.666968074108158e-12`;
- current-balance error: below `1e-12` in reported cases;
- synthetic local observability rank: single terminal `1`, segmented terminals `3`;
- status: `qualified_supported` for forward/observability implementation only.

No field inversion was run and no 2D hidden-field recovery claim is allowed.

## P4 Algorithms

P1 failed, so canonical Seiler STL, front-aligned adapter/LoRA, and activated-PDE Fourier/F-SPS matched-budget experiments were not run. Their status is `not_run_blocked`; no positive algorithm claim is allowed.

## Generalization

Formal leave-one-geometry, stack, interface range, pulse family, and material family response preflights were run. They use a reduced ridge response model, not a trained OASIS neural operator.

- geometry holdouts: median normalized errors around `0.25-0.31` with high empirical coverage;
- stack, interface, and pulse holdouts: substantially worse and often under-covered;
- cross-material holdouts: errors above `59`, confirming that VO2 and NbO2 cannot share an unqualified constitutive mapping.

Status: `preflight_only`. The defensible design is a shared compositional framework with material-specific constitutive experts.

## Claim Changes

Upgraded:

- electrical/thermal topology separation and mechanism routing: `qualified_supported` as implementation;
- segmented-electrode y-z forward/current integration: `qualified_supported` as implementation.

Downgraded or retained negative:

- v9 P1 loss-decrease gate -> v10 P1 `failed_but_informative`;
- noise-robust terminal inverse -> `failed_but_informative`;
- cross-stack/material generalization -> `failed_but_informative` preflight;
- STL/Fourier/F-SPS -> blocked/forbidden as positive claims;
- full 2D field recovery -> still forbidden.

The main SCI line remains calibration-gated constrained `gamma_sub` inversion under fixed or tightly bounded priors. V10 is supplementary implementation and negative-result evidence.

## Next Research Plan

1. Non-dimensionalize every CV and mortar term with equation-specific characteristic flux, energy, and jump scales. Current interface losses dominate optimization.
2. Use staged training: anchor/port warm start, CV continuation, then interface mortar, with residual-gradient diagnostics and predeclared stop criteria.
3. Evaluate boundary faces explicitly rather than imposing a global hard transform at cell centers; preserve independent layer experts and face fluxes.
4. Reject rank-deficient protocol candidates before inverse optimization. Design within each material family and focus on thermal excitation for `Rth_eff/tau_th`.
5. Upgrade P3 from forward observability to PDE-constrained latent inversion only after P1 passes. Use segmented-terminal Jacobians and holdout fields; do not reopen arbitrary field recovery.
6. Develop compositional generalization within one material family first: leave-one-stack/interface/pulse out, then uncertainty calibration. Cross-family transfer remains exploratory through shared geometry/interface modules plus separate constitutive kernels.
7. Run STL/Fourier/F-SPS only after the strict P1 gate passes; matched-budget algorithm comparisons on a failed base solver would not support a method claim.

## Validation

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_physical_semantics_v10.py tests/test_cv_multidomain_oasis_v10.py tests/test_active_protocol_design_v3.py tests/test_multiterminal_yz_v10.py tests/test_oasis_v10_gates.py tests/test_phase_activated_multilayer_forward.py tests/test_multidomain_oasis_training_v9.py tests/test_active_protocol_identifiability_v2.py tests/test_oasis_v9_gates.py tests/test_multidomain_oasis_pinn.py tests/test_oasis_components.py -q
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Results: targeted/new and key regression tests `28 passed`; full repository `181 passed in 91.70s`; `git diff --check` reported no whitespace errors.

Frozen GT modified: `No`.

Experimental data fabricated: `No`.

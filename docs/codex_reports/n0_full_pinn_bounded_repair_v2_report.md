# N0-R Frozen-GT Compatibility and Bounded Full-PINN Repair Report

Date: 2026-07-17

Base commit: `583cb441687001c7df9a8ee9d4d5cf45258f8efb`

Final commit: recorded in the execution handoff because a commit cannot contain its own hash.

Evidence type: frozen synthetic GT, solver-generated diagnostics, and PINN-predicted outputs. No experimental validation and no VO2 13 V access occurred.

## Executive disposition

N0 remains `failed_but_informative`; the reliable trained full-PINN forward claim remains `forbidden`.

- The frozen FVM is internally conservative: maximum normalized defect-mass, energy, and current ledger errors are `3.197e-16`, `2.684e-16`, and `6.965e-17`.
- The old v1 PINN reverses the frozen teacher's electrical boundary orientation. Frozen GT stores `phi(0,t)=V(t), phi(L,t)=0`, while v1 imposed the opposite orientation with the same `E=-dphi/dx` convention.
- The frozen `nx=31` material mask implies an arithmetic-average face `5.806451613e-10 m` from the declared interface. The `31 -> 63` non-frozen grid diagnostic gives port NRMSE95 `0.001225`, below the N0 port gate but explicitly retained as a continuum-discrete difference.
- A matched-budget dual-domain model was preregistered before training: `5704` parameters versus `5812` for the baseline, fixed-point SHA `80e34ca549d86588d12ffbcde4a304e378197dba602bcccc6e4e7d1ead932731`, config SHA `864b9b4405e801dfe6f352282bfd3554029c3bc814afe6f0bb83c9a8b3119a7c`.
- The fixed seed `20260715` data-free MVE used 1200 causal Adam epochs and one bounded L-BFGS optimizer instance. It failed; neither seed expansion nor sparse-port anchor was run.

## Controlled baseline and repair

| Metric | Gate | Single-global baseline | Dual-domain repair | Disposition |
| --- | ---: | ---: | ---: | --- |
| port_full_trace_nrmse95 | `0.1` | `0.123764` | `0.120358` | **fail** |
| max_heldout_residual_rms | `0.01` | `0.0196303` | `0.0482857` | **fail** |
| max_field_score_only_nrmse95 | `0.25` | `0.442026` | `1.14947` | **fail** |
| max_interface_flux_rms | `0.05` | `0.0963859` | `0.00896502` | **pass** |
| terminal_current_conservation | `0.01` | `1.98749` | `0.519809` | **fail** |
| global_energy_imbalance | `0.05` | `0.961864` | `0.998556` | **fail** |


The repair's held-out residuals are `r_T=0.0270806, r_c=0.0482857, r_m=0.00861596, r_phi=0.00663445`. Its score-only field errors are `T=0.161278, c_v=1.14947, m=0.306662, phi=0.074385, sigma=0.315832`. Exact-interface state errors are `T=0.0150497, c_v=0.00342027, m=0.00837503, phi=0.00530156` and exact-interface flux errors are `current=0.00896502, defect=0.00816083, heat=0.000793683`.

The repair passes `r_phi`, `r_m`, endpoint flux, all exact-interface state/flux gates, finite-state, and physical-bound checks. It fails `r_c`, `r_T`, port, field, terminal-current, and global-energy gates. The defect-mass ledger error is `0.996653`. The worst current window is indices `360:400` with normalized RMSE `0.330800`.

## Root-cause ranking

1. **Local strong-form loss does not guarantee the required global ledgers.** The repaired `r_phi` and exact current-flux interface metrics pass, yet terminal-current conservation is `0.519809` versus `0.01`. Energy imbalance is `0.998556` versus `0.05`. This is the dominant reason an apparently small local residual cannot support a forward claim.
2. **Defect transport is the largest unresolved state block, not simple collocation overfit.** Train/evaluation `r_c` are `0.046022` and `0.048286`; `c_v` score-only NRMSE95 is `1.149469` and defect-mass imbalance is `0.996653`. Similar train/evaluation failures point to formulation/optimization conflict rather than held-out sampling alone.
3. **The repair solves the interface representation defect but not the coupled trajectory.** Maximum exact interface flux RMS falls to `0.008965`, and `phi` field error falls to `0.074385`. However the port error only changes from `0.123764` to `0.120358`. Final gradients retain negative-cosine conflicts, including interface-state versus phase-relaxation.

## Conditional routing and leakage check

- Sparse-port anchor: **not run**. The preregistered route required residual, interface-flux, current, and energy gates to pass first; they did not.
- Seed expansion: **not run**. A single-seed data-free pass was required first.
- Frozen full fields: used only after optimization for scoring.
- N1-N3, SC-LOS, D0b-D0d, EC-OQ, ACAL, AA, TTLD, STL, and dynamic P3: not run.
- VO2 13 V numerical content: not read or unsealed.

## Claim disposition

| Claim | Status | Allowed wording |
| --- | --- | --- |
| Frozen FVM ledger and four manufactured operators are internally consistent | `supported` | No-training numerical audit only |
| v1 PINN electrode orientation conflicts with frozen teacher semantics | `supported` | Implementation root-cause finding |
| Exact dual-domain state/flux traces exist and pass the one-seed local interface gates | `supported` implementation fact / pilot sub-result | No P1, multidomain, or interface-innovation claim |
| Trained full-PINN forward evidence passes frozen GT | `forbidden` | N0 remains `failed_but_informative` |
| PINN sensitivity, quotient inverse, SC-LOS, or experimental validation | `forbidden` | Not run and upstream gates failed |

The distance to the paper goal shortened only in attribution and reproducibility: the teacher/PINN sign conflict, discrete-interface semantics, fixed evaluation set, gradient conflicts, and global-ledger failure are now explicit and hash-locked. It did **not** shorten the positive full-PINN evidence gap.

## Next single recommendation

Do not enter solver-first SC-LOS. If a new execution round is approved, the only high-value continuation is one newly preregistered solver-consistent control-volume/weak-form N0-R2 MVE that trains the face-flux and global conservation ledgers directly on the same fixed diagnostic set. This would be a numerical consistency repair, not a novelty claim, and it must retain the unchanged port/field/residual/conservation gates.

Primary machine evidence:

- `outputs/tables/n0_teacher_equation_compatibility_v1.json`
- `outputs/tables/n0_equation_parity_registry_v1.csv`
- `outputs/tables/n0_global_conservation_audit_v1.json`
- `outputs/tables/full_pinn_n0_baseline_diagnostics_v2.json`
- `outputs/tables/full_pinn_n0_repair_v2_preregistration.json`
- `outputs/tables/full_pinn_n0_repair_data_free_seed_20260715_v2.json`
- `outputs/tables/n0_baseline_repair_gate_comparison_v2.csv`
- `outputs/figures/full_pinn_n0_train_eval_gradient_v2.png`
- `outputs/figures/full_pinn_n0_baseline_repair_gates_v2.png`

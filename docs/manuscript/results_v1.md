# Results V1

All results are synthetic numerical digital-twin evidence, not measured experimental data.

## R1. Sparse-Port Hidden-Field Recovery Boundary

Status: `supported` for the configured benchmark boundary. Terminal conductance is nearly perfectly correlated with mean conductivity (`0.9999966`), yet port-only ablations do not uniquely recover the complete thermal, defect, phase, and conductivity fields. The result supports target reduction, not a universal impossibility theorem.

## R2. Constrained gamma_sub Recovery

Status: `qualified_supported`. With fixed microphysics and nominal confounders, the constrained profile returns \(\hat\gamma_{\mathrm{sub}}=4.5\times10^8\) for the synthetic truth \(4.5\times10^8\). The continuous off-grid audit contains 36 resimulated cases across noise levels `0`, `0.02`, and `0.05` and observation counts `8`, `16`, `32`, and `64`; its maximum refined relative error is `0.05565`.

## R3. T_sw Calibration Gate

Status: `qualified_supported`. The 42-case confounding phase map identifies \(T_{\mathrm{sw}}\) as the dominant nuisance parameter. The response-surface tolerance audit and 270-case ODE spot-check support a benchmark-specific residual-error marker near `0.1 K` under the configured `<=15%` median-error criterion. This is not a real-device calibration requirement.

## R4. Conditional Robustness And Failure Region

Status: `qualified_supported`. Under nominal fixed priors, the seeded robustness audit reports median relative errors near `0.020` for the best/`ltp_ltd` protocol group. Narrow-prior cases remain within the configured `<=20%` boundary, whereas wide \(T_{\mathrm{sw}}\) mismatch fails systematically with median error about `0.816` in the same group. Observation-count and off-grid checks pass within the calibrated region; aggregate averages are not used to hide the failed prior region.

## R5. Protocol Gain After Calibration

Status: `qualified_supported`. Equal-prior disentanglement gives calibration gain `1.1217` and protocol gain `0.0150`, so calibration dominates. The 720-case ODE-backed sequential validation selects `calibrated_multi_pulse_to_ltp_ltd`; it has success rate `1.0` and maximum relative error `0.1111` under calibrated priors. This is the locked Figure 5 result.

A separate 2400-case calibrated-protocol stress audit identifies `calibrated_short_pulse_to_ltp_ltd` as its best candidate but reports worst-case error `0.4444` and explicitly sets `whether_ready_as_main_figure = false`. It is retained as `failed_but_informative` supplementary stress evidence and does not replace Figure 5.

## R6. V10 Extension Gates

- P0: `qualified_supported` reduced electrical/thermal topology separation and mechanism routing.
- P1: `failed_but_informative`; median \(E_T=0.37563\), median \(E_m=0.06812\), median interface residual `106.1546`, success rate `0`.
- P2: `failed_but_informative`; selected NbO2 and VO2 protocols are rank `2/4` and `1/5`, respectively, and thermal blocks fail.
- P3: `qualified_supported` for forward/local observability only; segmented terminals raise the local rank from `1` to `3` for a Gaussian conductivity-profile basis parameterized by center, width, and contrast.
- P4: `forbidden` as a positive v10 claim because P1 fails.

## R7. Public VO2 Source-Reproduction Boundary

Status: `failed_but_informative`. Provenance, hashes and license separation are complete. The author code and SI rewrite agree for dynamic current, temperature and R-T semantics at the declared 10 ns step (NRMSE95 values below `5e-14`). However, the repository SI solver gives a 5 ns versus 2.5 ns full-trace current NRMSE95 of `0.163148`, above the preregistered `0.01` gate. Consequently no calibration was run, no fit lock was created and 13 V remains sealed. This is source-model reproduction evidence, not project experimental validation.

## R8. Complete 1D PINN Contract And Failed MVE

Status: `failed_but_informative` for trained evidence. The architecture contract and constant-equilibrium manufactured test pass, with exact electrical endpoint conditions and zero manufactured normalized residuals. The fixed 1200-epoch single-seed MVE remains outside every training gate: port NRMSE95 is `0.123764` versus `0.10`, while `r_phi`, `r_c`, `r_T`, and `r_m` RMS values are `0.012564`, `0.020203`, `0.019372`, and `0.012172` versus `0.01`. Outputs remain finite and within physical state bounds. This supports an optimization/residual limitation, not a reliable full-PINN claim; N1-N3 were not run.

## R9. Teacher Compatibility And Exact-Trace N0-R Boundary

Status: `supported` for the no-training compatibility audit and `failed_but_informative` for trained evidence. Four non-trivial manufactured cases and reconstructed frozen-FVM mass, energy, and current ledgers pass at roundoff scale. The audit identifies a v1 electrode-orientation conflict and a frozen arithmetic interface face offset of `0.18 dx` from declared `L_int`. A preregistered `5704`-parameter exact-trace split model was compared with the `5812`-parameter baseline. Its seed `20260715` MVE passes all local interface gates but fails port (`0.120358`), held-out defect/thermal residuals (`0.048286/0.027081`), terminal current (`0.519809`), global energy (`0.998556`), and field gates. Sparse-port anchor and seed expansion were therefore not run. N0 remains failed and SC-LOS/N1-N3 remain blocked.

## R10. Solver-Consistent N0-CV-E v3 Final Stop

Status: `supported` for operator/preflight consistency and `failed_but_informative` for trained evidence. The evidence-integrity audit independently reconstructs frozen adjacent-state defect and energy ledgers (`4.03948e-06` and `0.00258234`) and one Radau interval (`1.30271e-07` maximum relative RMS); tampered trajectories fail. All 18 locked preflight checks pass. In float64, analytic electrostatic parity is `2.30787e-08`, CV-RHS parity is `2.12586e-08`, current spread is `3.83609e-16`, and the maximum automatic/central-difference gradient discrepancy is `1.63621e-08`.

The authorized seed `20260715` run reached its single L-BFGS stage after the locked 1200 Adam steps, where a strong-Wolfe closure returned a non-finite loss. The exception occurred before checkpoint serialization or trajectory scoring. All forward, residual, interface, ledger, IC/BC, finite/bounds, and seed-vote result gates are therefore `unassessed_fail_closed`, not zero or passing. No balancing arm, expansion seed, sparse anchor, hyperparameter search, SC-LOS, or N1-N3 stage was run. N0 is closed after this final bounded attempt; the calibrated `gamma_sub` result remains the manuscript mainline.

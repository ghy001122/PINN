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

## R5. Bundled Calibrated-Configuration Performance

Status: `qualified_supported` only for bundled configuration performance. The historical equal-prior disentanglement reports calibration gain `1.1217` and a much smaller protocol-associated difference `0.0150`. In the separate 720-case ODE-backed Figure 5 audit, all six named candidates use the LTP/LTD simulator while waveform amplitude, duration, and calibration-error factor vary together; the implementation does not consume `prior_width_factor`. The named `calibrated_multi_pulse_to_ltp_ltd` bundle has success rate `1.0` and maximum relative error `0.1111` under its configured synthetic conditions. This result does not isolate protocol gain or establish protocol optimality.

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

The historical b380 seed `20260715` run reached its single L-BFGS stage after the locked 1200 Adam steps, where a strong-Wolfe closure returned a non-finite loss. That artifact contains no checkpoint or scoreable `pinn_predicted` trajectory, so all trained-result gates remain `unassessed_fail_closed` for the historical run. Its precise status is `runtime_abort_unassessed`, not scientific-model falsification.

## R11. Instrumented N0 Replay and SID/EC-OQ Discovery Boundary

Status: `failed_but_informative`. A separately preregistered v3r replay completes 1200 Adam steps and produces a scoreable post-Adam trajectory. Parameters, gradients, and Adam moments remain finite, and loss declines from `1.50627e13` to `2.66531e9`. Port NRMSE95 passes narrowly (`0.0955475 <= 0.10`), but `r_c/r_T/r_m` are `0.0226501/56586.4844/4.07622`, interface current/heat/defect scores are `0.0955475/33211.9341/23.8718`, and the energy/defect ledger gate values are `0.999950/1.0`. Five physics or ledger metrics exceed their gates by at least `20x`, making both preregistered recovery choices ineligible. No recovery arm or expansion seed was run.

A serializer-safe diagnostic replay from the same pre-L-BFGS checkpoint reproduces the non-finite strong-Wolfe failure at closure `3`; the first non-finite parameter is `backbone.net.0.weight`. This is optimizer localization, not positive forward evidence. A separate solver-first event-window audit uses `189` forward evaluations but passes derivative agreement in only `3/9` cases (maximum discrepancy `0.648429`). The low-amplitude triangle switch rule spans the full trace, the corrected angle lower bound is `0.49066 deg`, the training-condition ratio is `1.90380 < 10`, and only one protocol is physically stable. The preregistered SID/EC-OQ implementation is rejected and inactive, without declaring the broader hypothesis permanently false. N0 remains stopped, N1-N3 remain forbidden, and calibrated `gamma_sub` remains the manuscript mainline.

## R12. CPCF Semantic Supersession

Status: `failed_but_informative` as a software audit and `forbidden` as frontier evidence. Of 48 rows, 40 are proxy-only and eight combine the same proxy vote with a diagnostic fresh anchor; all operating-point votes use `predicted_relative_error`, so zero rows are fully direct-solver scientific votes. The historical source uses `nx=21`, `nt=160/180`, Radau `1e-5/1e-7`, fifteen gamma candidates and a port-only objective, whereas the anchors use `nx=5`, `nt=24`, Radau `1e-3/1e-5`, five candidates and an added heat residual. Two of three response-surface/simulator protocol mappings have different voltage hashes or no single equivalent waveform. Noise level and seed are confounded, the four-level bootstrap is not an iid seed bootstrap, and two stable nondominated points fail the locked risk gate. CPCF is therefore a non-voting proxy-contract diagnostic; it supports no conclusion about whether a calibration-protocol resource frontier exists.

## R13. CEBA Parity And Abstention Boundary

Status: `supported` for implementation parity and `failed_but_informative` for the boundary hypothesis. Six exact direct-source anchors reproduce best gamma, relative error, classification, objective value/order, waveform hash, and solver hash in all `6/6` cases. Parity uses 36 unique solver trajectories and completes in `29.22 s`. The conditional pilot then scores 72 protocol/observation/noise/seed cases entirely from those cached trajectories, adding zero ODE solves and recording 36 cache hits. Under the locked profile-ambiguity rule, every `delta_T_sw_K=0` condition has abstention rate `1.0`; hence there is no valid lower-success/upper-failure bracket, no `delta_T_sw_star`, and no refinement run. The CEBA configuration claim is rejected without changing its ambiguity or success thresholds.

The semantic audit separates the point decision from that abstention. At `n=32, noise=0.02`, point success/abstention are respectively `1.0/1.0`, `0.0/1.0`, and `0.0/0.0` for triangle at `delta_T_sw_K={0,0.2,2}`, and `1.0/1.0`, `1.0/1.0`, and `0.0/0.0` for LTP/LTD. The retained-class decision reads `true_gamma` and hard-codes the `0.15` class radius, so it remains an oracle diagnostic. Removing the low candidate endpoint changes retained-set membership in `73.33%` of the 30 audited cases; hence the five-percent profile set is also grid-span dependent.

## R14. Simulation-Calibrated Identifiability Set

Status: `failed_but_informative`. M32 pre-registered candidate-specific finite-sample thresholds using 50 calibration seeds and evaluated 50 disjoint held-out seeds for both protocols, observation counts `8/32`, all 15 candidates, and primary noise `0.02`. All 36 required direct-solver trajectories were already cached, so the run added zero ODE solves and zero PINN training runs. Nominal pooled set coverage is `0.93233`; the worst candidate is `4.75e8` with coverage `0.85`; point success is `0.996`; and conditional point accuracy among accepted nominal cases is `0.996`. These nominal gates pass.

The refusal gate fails decisively. At true `gamma_sub=4.5e8`, acceptance is `1.0` at nominal, `0.2 K`, and `2 K` mismatch, while point success falls from `1.0` to `0.375` and then `0.0`. Deleting the pre-registered remote `1.0e9` candidate changes no acceptance/refusal decision, but that stability does not repair the missing mismatch refusal. Therefore SCIS does not support a runtime coverage/refusal certificate and is retained only as a synthetic nominal-coverage plus model-mismatch failure boundary.

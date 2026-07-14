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

## R7. External Evidence Boundary

Status: `forbidden` as a completed validation claim. No provenance-backed digitized external curve is available, and no measured dataset has been added. Literature values remain shape or engineering priors only.
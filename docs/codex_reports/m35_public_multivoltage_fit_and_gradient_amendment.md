# M35 public multi-voltage fit and gradient-semantics amendment

## Scope and evidence boundary

M35 starts from `144aa53de1f6d6f788f61729355b4de45fd9c241` and is a bounded CPU-only round. It does not run PINN training, reopen M34 training, access 13 V numeric content, or alter Frozen GT v1.1. The single scientific target is whether the open public 9/11/15/17 V traces can support a numerically stable thermal-timescale calibration and leave-one-voltage-out (LOVO) bridge while a future 13 V trace remains repository-withheld.

The four evidence semantics remain distinct:

1. source-paper model/code reproduction;
2. repository-side refitting on open public curves;
3. a future repository-withheld, preregistered 13 V cross-voltage evaluation;
4. genuinely independent external validation, which is unavailable here.

Neither source reproduction nor repository refitting is experimental validation performed by this repository.

## D-PREG result

The machine-readable preregistration is `outputs/tables/m35_public_multivoltage_preregistration.json`; its preflight gate passed all 21 checks. The provenance manifest is `data/external/vo2_zhang_2024/multivoltage_prereg_manifest_v1.json` with SHA-256 `99A85C833C051F27E030E79EF965FC37A2CDA29B7DEC93A12555477AD0AB7B5B`.

The registered open curves are:

| Curve | Role | SHA-256 |
|---|---|---|
| R-T, Fig. 1b | fixed constitutive sanity/provenance | `F3C408E98A11ED18659BDF00C443B40F76F5F7DDED7DA46E438ABBEB873850F9` |
| 9 V, Fig. 1c experiment | LOVO fit/holdout | `A8A2F2F6BF43EB49A7CED7E06F6A72E52CFA49B0AEB19119A9AB9834A6ADDF56` |
| 11 V, Fig. 1c experiment | LOVO fit/holdout | `42E29D10EDD707A79A51938C928FCB45B321D1B103114F2CECAB3B5063F18D51` |
| 15 V, Fig. 1c experiment | LOVO fit/holdout | `DD7872C980B982CA32CB459313939B03777769D4C0B42A600C5B97966CF6A923` |
| 17 V, Fig. 1c experiment | LOVO fit/holdout | `B8219F9C5E6A73E9C4526A9A01DDB5281F6CC7755343E6D166B0006D819CD6A6` |

The publisher Source Data archive hash is `E8916E1B0861C7947119C3F175CEB2E625B197BC32B6B5602F1016823222FFE3`. Article, publisher data, Zenodo, and GitHub-code licensing are recorded separately. The two 13 V member names remain metadata-only: `content_read_prelock=false`, `extracted_path=null`, and content `sha256=null`. No 13 V curve value or derived statistic was read.

## Locked source-model contract

The deterministic source-compatible compact model uses

\[
C\,\frac{dV_d}{dt}=\frac{V_{in}-V_d}{R_{load}}-\frac{V_d}{R(T,h)},
\]

\[
C_{th}\,\frac{dT}{dt}=\frac{V_d^2}{R(T,h)}-S_e(T-T_{base}),
\]

with the Zhang et al. hysteretic resistance law, explicit Euler stepping, temperature clipping to 305--370 K, a 0.01 K reversal threshold, initial state `V_d=0`, `T=T_base`, and a history ledger initialized at `T_base-0.1 K`. The reversal ledger is updated before right-hand-side evaluation and the explicit state update.

`S_e` has units W K^-1 whereas the frozen PDE `gamma_sub` has units W m^-3 K^-1. The relation `S_e=gamma_sub V_thermal` is permitted only for an explicitly matched, uniformly lumped geometry. This geometry/material equivalence has not been established. M35 therefore permits only `tau_th=C_th/S_e` as a compact-model coordinate and forbids presenting an `S_e` fit as external validation of `gamma_sub`.

## Fail-closed numerical protocol

- Public traces are evaluated on the publisher time origin with only pretrigger median instrument-zero subtraction; no DTW, phase shift, outlier removal, or observation interpolation is allowed.
- The 9/11/15/17 V LOVO roles, fixed event classifier, full-trace NRMSE, event/QoI metrics, eight deterministic starts, optimizer, parameter bounds, and CPU/forward limits are locked in `configs/m35_public_multivoltage_fit.yaml`.
- The historical D0a `medium_vs_fine_dt_current_nrmse95=0.1631480017203279` failure remains `failed_but_informative`. The new open-voltage operational convergence gate is parallel evidence, not a replacement.
- Both `(log C_th, log S_e)` and `(log tau_th, log S_e)` must pass the preregistered multistep Jacobian rank/stability gate before fitting.
- All starts and all native-time full traces must be reported. A best-start-only selection is forbidden.

## M34-A boundary

M34-A is a post-hoc diagnostic amendment on the immutable M33 checkpoint. It compares the original total objective and a group-normalized objective with float64 central differences, Taylor remainders, and directional VJP parity for 32 fixed module/seed directions. Regardless of its outcome, it cannot change the original M34 authorization failure or authorize corrected training.

## M34-A result

M34-A completed in 33.3 s without training. All 32 fixed module/seed directions were finite and classified as `stable_parity_no_autograd_error`:

| Classification | Direction count |
|---|---:|
| Stable parity; no autograd error | 32 |
| Total-loss-scale finite-difference cancellation | 0 |
| Autograd implementation error supported | 0 |
| No stable step interval / uncertain | 0 |

The normalized-objective Taylor slopes are approximately second order and every module has eight stable directions. This is useful negative diagnosis: the new evidence does not support the proposed gradient-implementation-error explanation, and it also does not support a scale-cancellation explanation under the amended normalized directional test. The only manuscript-safe conclusion remains that the preregistered M34 authorization gate failed. M34-A is post hoc, `scientific_vote=false`, and `training_authorization=false`.

## D-FIT fail-closed result

D-FIT ran exactly eight solver trajectories on the open 9/11/15/17 V data contract and stopped after 20.1 s at the first numerical gate. It did not run the prefit Jacobian, optimization, LOVO multistarts, or any PINN training.

The 5 ns versus 2.5 ns source-compatible solver comparison was:

| Voltage | Current NRMSE95 | Device-voltage NRMSE95 | Activity class | Frequency error | Charge error | Energy error | Gate |
|---:|---:|---:|---|---:|---:|---:|---|
| 9 V | 8994.34545 | 431857.49753 | exact | 0 | 2.27e-6 | 1.10e-6 | fail |
| 11 V | 0.378166 | 0.234287 | exact | 0.001385 | 1.09e-4 | 0.003061 | fail |
| 15 V | 0.452066 | 0.518023 | exact | 0.009685 | 0.001823 | 0.008967 | fail |
| 17 V | 11596391.68903 | 6776521.56388 | exact | 0 | 3.85e-4 | 0.001876 | fail |

All four activity-class, frequency, charge, and energy checks pass. All four current and device-voltage full-trace NRMSE checks fail. At 11/15 V, stable event/QoI summaries coexist with unacceptable raw-time waveform disagreement, consistent with accumulated event-time/phase sensitivity. At quiescent 9/17 V, the enormous range-normalized values expose a near-steady-signal normalization boundary. These are diagnostic interpretations, not a basis for retrospectively changing M35's gate. Raw-time waveform convergence was preregistered as mandatory, so the fit correctly stopped.

The fixed R-T constitutive sanity metric remains NRMSE95 `0.0593809582`; it is not a dynamic-fit result. Historical D0a convergence remains `0.1631480017 > 0.01` and was not overwritten.

No `m35_public_multivoltage_fit_lock.json` exists. Consequently, there is no valid fit lock and no scientific or procedural basis to request 13 V access. The two 13 V members remain unextracted and numerically unaccessed.

## Claim disposition and manuscript use

| Result | Status | Allowed use | Forbidden use |
|---|---|---|---|
| D-PREG provenance/protocol lock | `supported` implementation/provenance fact | Methods/data-provenance and reviewer-defense supplement | Fit, validation, or parameter-estimation evidence |
| M34-A directional parity | `supported` diagnostic fact; original M34 remains `failed_but_informative` | State that the post-hoc test did not support an autograd-error explanation | Reopen training or rewrite the preregistered failure |
| M35 solver convergence | `failed_but_informative` | Numerical limitation and stop-boundary table | Repository refit, quotient superiority, parameter recovery, or external validation |
| Public 13 V | `forbidden` as evaluated evidence | State that it remains sealed | Holdout result, cross-voltage validation, or any derived statistic |

The safe calibration-gated rank-1 synthetic `gamma_sub` result remains the manuscript mainline. M35 adds a defensible public-data provenance contract and a numerical failure boundary, but no positive public-data calibration claim. The full 1D PINN stays as the mandatory architecture scaffold; M35 supplies no trained-forward, sensitivity, inverse, or generalization evidence.

## Targeted novelty watch

Only three near-neighbor hypotheses are retained; none is a novelty claim.

| Candidate | Nearest primary precedent | Actual possible difference | Fatal flaw | Minimum falsification experiment | Stop rule |
|---|---|---|---|---|---|
| Thermal-timescale quotient under voltage protocols | [Zhang et al., Nature Communications 2024](https://doi.org/10.1038/s41467-024-51254-4) already defines metallic, insulating, and thermal time scales and uses a voltage-dependent thermal-neuristor model whose parameters were optimized against experiment. | A repository-side, leakage-controlled LOVO comparison of raw versus quotient coordinates, not the existence of the time scales themselves. | Numerically unconverged event-driven trajectories can manufacture coordinate stability or protocol effects. | Pass a new solver-only raw-time/event-aware convergence gate, then the locked M35 Jacobian and LOVO comparison without 13 V. | Stop the quotient story if solver convergence fails or quotient cross-fold stability is not at least non-inferior to raw coordinates. |
| PINN identifiability analysis | [Kharazmi et al., Nature Computational Science 2021](https://doi.org/10.1038/s43588-021-00158-0) already uses PINNs to study structural/practical identifiability and uncertainty under sparse data. | Branch/protocol-conditioned thermal-neuristor quotients with solver-verified sensitivity fidelity could be application-specific evidence. | Standard PINN-plus-identifiability is not novel, and the repository has no trained-forward or sensitivity-fidelity gate. | Only after a public solver bridge and N0/N1 success, compare independent-solver and PINN Jacobian subspaces at fixed anchors. | Stop the inverse claim if trajectory or Jacobian fidelity fails; retain only the numerical limitation. |
| Multistart/profile identifiability in hybrid neural dynamics | [Giampiccolo et al., npj Systems Biology and Applications 2024](https://doi.org/10.1038/s41540-024-00460-3) already combines mechanistic parameter estimation, global exploration, and local identifiability analysis, and highlights local/initial-condition/computational limitations. | Explicit refusal of unsupported raw VO2 parameters and reporting a physical quotient equivalence class could differ in device context. | Reparameterization can create an apparent stability advantage without adding information; local profiles do not establish global or device-general identifiability. | Complete all preregistered starts and profiles, compare induced-prior-normalized raw/quotient geometry, and require a held-out-voltage benefit. | Stop if the quotient does not improve stability/information/prediction under the locked effect threshold. |

The source paper itself reports fixed 10 ns Euler-Maruyama integration and parameters optimized to reproduce experiment. Therefore 13 V can never be called a strictly independent external holdout for this source family; at most it could later become a repository-withheld, preregistered cross-voltage evaluation.

## Achievements, remaining Q2 gap, and next single priority

### Net achievements

1. The public source/data/license/units/curve-role chain is now hash-locked before fitting, closing the prior leakage and terminology ambiguity.
2. M34's suspected gradient-error explanation was directly tested rather than repeated: 32/32 amended directions show stable parity, so an unsupported causal story has been removed while the original failed gate is preserved.
3. The open-voltage route was falsified at the correct upstream numerical gate with only eight solver evaluations. No compute was wasted on 80 multistarts using an untrusted trajectory geometry.
4. The source-model `S_e` versus frozen-PDE `gamma_sub` dimensional boundary is explicit; M35 cannot be used to claim external validation of the safe synthetic inverse parameter.
5. 13 V remained sealed, so a future cross-voltage evaluation has not been contaminated by this round.

### Distance to a Q2 SCI manuscript

The evidence package is more defensible but not materially closer to a positive public-data or full-PINN result. The manuscript still lacks: (a) a converged public-model forward reference; (b) repository-side public calibration and LOVO evidence; (c) a valid fit lock and 13 V cross-voltage evaluation; (d) trained full-PINN forward fidelity; (e) solver/PINN sensitivity agreement; and (f) quotient inverse evidence. Independent external validation remains absent. The current submit-safe scientific center is still the calibrated synthetic `gamma_sub` boundary plus transparent negative neural/public-model audits.

### Next single priority

Run a newly preregistered solver-only convergence-resolution round. Separate near-zero-range normalization at 9/17 V from event-time dephasing at 11/15 V; compare fixed `2.5/1.25/0.625 ns` steps with an independent event-resolved/adaptive reference; lock absolute instrument-scale floors from the already-open pretrigger traces; retain raw-time waveform convergence as mandatory and use event alignment only diagnostically. If that gate fails, downscope the public route to reproduction/limitation evidence. If it passes, return to the already-defined Jacobian audit and only then consider a new fit preregistration. Do not train a PINN or access 13 V in the convergence round.

## Validation

- Focused evidence/governance tests: `19 passed in 7.87 s`.
- Governance audit: `pass_with_manual_review`, with zero failed checks; frozen-file mtimes and client-side Codex rule loading remain explicit manual-review surfaces.
- Final full repository suite (run exactly once): `320 passed in 118.44 s`.
- Frozen GT SHA-256 checks: pass; no frozen file changed.
- Strict JSON/CSV and fail-closed artifact check: pass.
- Machine-readable closeout: `outputs/tables/prompt35_final_validation.json`.

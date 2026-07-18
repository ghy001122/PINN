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

## Stage disposition at preregistration commit

- D-PREG: `supported` as a provenance/protocol lock; this is not a positive scientific fit result.
- M34-A: pending execution after the preregistration commit; training remains forbidden.
- D-FIT: conditionally authorized only after the preregistration commit and only if solver-convergence and prefit-Jacobian gates pass.
- 13 V: sealed and unaccessed; any later evaluation requires a valid fit lock plus a new explicit user authorization.

Results, claim disposition, novelty watch, manuscript implications, and distance-to-Q2 assessment are appended only after the bounded execution closes.

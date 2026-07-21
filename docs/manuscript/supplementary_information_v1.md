# Supplementary Information

## Calibration-gated inference of an effective heat-loss coordinate from sparse terminal observations in a synthetic phase-change-device benchmark

This document reports the evidence boundaries, audit details, and negative
results supporting the main manuscript. Every project result is synthetic
numerical digital-twin evidence unless explicitly identified as a publisher
source. No project-generated measured device data are present.

## S1. Evidence types and claim gates

The evidence chain distinguishes:

- `synthetic_gt`: frozen numerical benchmark truth;
- `solver_generated`: output of a declared repository simulator;
- `pinn_predicted`: output of a trained neural model;
- `publisher_source`: publisher-hosted article or Supporting Information;
- `digitized_publication_curve`: a derived, provenance-recorded extraction;
- `proxy/preflight/smoke`: an implementation check without scientific vote.

Only `supported`, `qualified_supported`, `failed_but_informative`, and
`forbidden` are used as claim statuses. Missing, non-finite, upstream-ineligible,
or threshold-failing results fail closed. A passing smoke test or finite
residual does not upgrade a scientific claim.

## S2. Frozen benchmark and observation operator

Ground Truth v1.1 contains the one-dimensional fields
\((\phi,c_v,T,m,\sigma)\), terminal observables \((V,I,G)\), and declared
boundary/interface metadata. The four frozen arrays, acceptance configurations,
acceptance report, and manifest are hash-checked by the governance audit. The
positive inverse target is
\(\gamma_{\mathrm{sub}}\), the coefficient multiplying the reduced
substrate-loss term \(-\gamma_{\mathrm{sub}}(T-T_0)\).

The observation operator integrates spatial conductivity through the
one-dimensional series resistance. This explains why terminal conductance is
almost perfectly correlated with mean conductivity while remaining
insufficient to distinguish all internal state decompositions.

## S3. Identifiability and complete-neural failure evidence

The port-only ablation fits integrated quantities much more reliably than the
complete hidden fields. The full neural formulation includes electrical,
defect, thermal, and phase residuals; initial, boundary, and interface losses;
terminal reconstruction; and global defect/energy ledgers. The bounded routes
are not positive solver evidence:

| Route | Evidence | Status | Reason |
|---|---|---|---|
| Initial full-neural MVE | port NRMSE 0.123764; four normalized residual RMS values above 0.01 | `failed_but_informative` | Joint port/residual contract fails |
| Instrumented control-volume replay | port NRMSE 0.0955475 | `failed_but_informative` | Thermal, phase, interface-flux, and global-ledger gates fail |
| Mixed state--flux variant | selected thermal/flux terms improve | `failed_but_informative` | Port, constitutive, PDE, field, interface, ledger, and no-regression gates fail |

These failures justify target reduction in this benchmark. They do not prove a
universal impossibility for every PINN architecture or optimization budget.

## S4. Reduced-inverse audit design

With microphysics fixed, the profile objective releases only
\(\gamma_{\mathrm{sub}}\). The audit sequence is:

1. nominal profile and truth recovery;
2. continuous off-grid refinement across noise and observation counts;
3. joint \((\gamma_{\mathrm{sub}},T_{\mathrm{sw}})\) confounding map;
4. recoverability phase diagram under prior width, noise, count, and protocol;
5. selected fresh simulator anchors for the dense response surface;
6. calibration-tolerance sweep and ODE-backed spot check;
7. calibration--protocol factorial decomposition;
8. statistical and broad stress audits retaining failed cases.

The dense joint surface contains 2501 interpolated locations derived from 77
simulator-backed locations. It is not represented as 2501 independent solves.
The response-surface tolerance study contains 1350 cases; the targeted
simulator-backed spot check contains 270 cases. The continuous off-grid audit
contains 36 cases, and the confounding map contains 42 cases.

## S5. Calibration and protocol decomposition

The bundled calibrated configuration in main Figure 5 contains 720
simulator-backed synthetic cases. Its factors do not isolate protocol. A
separate factorial audit gives:

| Component | Gain |
|---|---:|
| Calibration | 1.1216748795 |
| Protocol | 0.0149556651 |
| Interaction | 0.0014762924 |
| Total | 1.1381068369 |

Accordingly, the allowed statement is that calibration dominates and protocol
is a secondary modifier in the tested design. Protocol optimality and a
protocol-only causal gain are forbidden.

The broader 2400-case simulator-backed stress audit reports a best tested
calibrated short-pulse sequence success rate of 0.9604167 and worst-case
relative error of 0.4444. Because the worst case is large and the source result
explicitly rejects an unqualified main-figure role, this result remains
supplementary.

## S6. LLP source-contract amendment

The public VO\(_2\) source [@qiu2024] prints a reversal-temperature expression
in its Supporting Information. Earlier LLP formulations establish the model
family [@dealmeida2002; @dealmeida2003], while a later explicit electrothermal
comparator provides a separate event-rule formulation [@sena2026]. These
sources are not interchangeable. The audit therefore separates four layers:

| Layer | Contract | Result | Permitted interpretation |
|---|---|---|---|
| A | Literal printed Qiu SI Eq. S3/S4 transcription | Transcription fidelity passes; literal reversal has maximum phase-fraction jump 0.119145 in the audit | Printed-formula sensitivity only |
| B | Analytic inverse of the configured tanh limiting-branch anchor | 4002 branch/grid evaluations; maximum inverse identity error \(3.55\times10^{-15}\); realized reversal-continuity gate passes | The `atanh` term is source-traceable as an analytic anchor inverse |
| C | Sena--de Almeida 2026 explicit electrothermal LLP | Literature comparator only; author code not verified | Later event-rule comparison, not Qiu author intent |
| D | Historical repository implementation | Numerically matches its declared Layer-B contract | Repository implementation history only |

For the configured proximity kernel,
\(P(0)=0.999999997324712\); the deficit
\(2.6752879911384753\times10^{-9}\) is analytic for the printed kernel rather
than a floating-point rounding artifact. The blocking implementation-fidelity
and realized-continuity gates pass. Return-point memory and wiping-out
diagnostics are non-blocking and do not authorize those physical claims.

Executable Qiu author code, complete reversal-event rules, and all numerical
initialization details are unavailable. Therefore neither Layer A nor Layer B
is claimed to reproduce unpublished author intent or code. The earlier E1F
artifact has no scientific vote because its formal contract and a digitized
curve extraction were invalid. The corrected literal-S3 sensitivity study
passes DOP853--Radau parity but fails the clean 12 V source-curve setting gate;
it remains `failed_but_informative` and does not refute general LLP behavior.

## S7. Main-figure provenance

The six main figures are committed as their existing original PNG bytes. They
were not regenerated during manuscript assembly. Their SHA-256 values and
source table hashes are recorded in
`outputs/tables/main_submission_figure_manifest.json`.

Figure 3 contains visually similar protocol rows because the configured audit
finds little isolated protocol effect; this is not a rendering error. Figure 5
is explicitly a bundle result and must not be captioned as protocol-only gain.

## S8. Data availability and replay boundary

The repository versions all text, code, configurations, lightweight JSON/CSV
results, manifests, and the six main figures. Frozen NPZ arrays are a local
asset pack and publisher PDFs are third-party source files that are hash-locked
locally but not redistributed. A local clean-worktree replay therefore requires
copying hash-verified frozen arrays and governance metadata into the detached
validation worktree. Public-clone reproduction without that asset pack is not
claimed. The asset pack can be supplied on reasonable request where policy and
licensing permit.

## S9. Additional forbidden claims

The evidence does not support real experimental validation, unconditional
\(\gamma_{\mathrm{sub}}\) identifiability, complete two-dimensional hidden-field
recovery, terminal-only two-dimensional inverse success, full or Seiler-style
STL-PINN reproduction, universal F-SPS/Fourier superiority, or full
device-grade FEM/3D multiphysics reproduction.

## Supplementary references

References use the shared `references.bib` file.

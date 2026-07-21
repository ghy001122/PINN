# Identifiability-gated physics-informed digital-twin inversion for phase-transition devices

## Abstract

Sparse electrical terminals rarely constrain every internal field and material
parameter of a phase-transition device. We therefore treat identifiability as a
gate before physics-informed inversion. A frozen one-dimensional synthetic
benchmark couples electrical potential, defect state, temperature, conductive
state, boundary/interface conditions, conservation laws, and a terminal
observation operator. A complete physics-informed neural network (PINN)
implements this contract, but its bounded training routes do not jointly pass
the field, residual, interface, and global-ledger gates; no trained full-PINN
success is claimed. The failed full-field audit instead motivates reduction to
the effective thermal-dissipation coordinate \(\gamma_{\mathrm{sub}}\). With
microphysics fixed and switching temperature calibrated or tightly bounded,
the synthetic inverse is conditionally recoverable across noise,
observation-count, and off-grid audits, whereas wider calibration mismatch
defines a reproducible failure region. A source-traceable Qiu VO2
two-dimensional bridge passes repaired static numerical checks but fails its
active-transient source contract. A separately preregistered compact-model
implementation achieves DOP853--Radau parity but fails the 12 V source-figure
gate without refitting. The work supports a fail-closed conclusion: estimate
only coordinates that pass calibration, solver, conservation, and
observability gates, and refuse unsupported full-field, raw-parameter, or
external-validation claims.

**Keywords:** physics-informed neural networks; digital twin; identifiability;
phase-transition device; inverse problem; calibration; fail-closed validation

## 1. Introduction

Phase-transition and memristive devices couple conduction, Joule heating,
transport, internal-state evolution, and heat rejection. Voltage and current
are inexpensive to observe, but many hidden states can produce similar terminal
traces. A low trajectory error therefore does not establish unique parameter
recovery, correct hidden fields, or faithful sensitivities.

This work asks which physical quantity is supported by a sparse observation
operator and under which calibration conditions. The complete PINN is retained
as a common field--physics--observation scaffold, while an independent solver
acts as the judge. The contributions are bounded: (i) a configured hidden-field
recovery boundary that motivates target reduction; (ii) conditional synthetic
recovery of \(\gamma_{\mathrm{sub}}\) after switching-temperature calibration;
and (iii) public-literature audits that expose the boundary between numerical
parity, source-model reproduction, local-PDE transfer, and experimental
validation.

## 2. Methods

### 2.1 Evidence taxonomy and frozen benchmark

Ground Truth v1.1 is a literature-guided synthetic benchmark. Its equations,
parameters, configurations, and arrays are hash-locked. Project-generated
measurements are absent. We distinguish `synthetic_gt`, `solver_generated`,
`pinn_predicted`, publisher source documents, and derived digitized publication
curves.

The frozen state is \((\phi,c_v,T,m)\), with conductivity given by the white-box
closure \(\sigma(c_v,T,m)\). For the one-dimensional series model,

\[
R_A(t)=\sum_i\frac{\Delta x_i}{\sigma_i(t)},\qquad
J(t)=\frac{V_{\mathrm{app}}(t)}{R_A(t)},\qquad I=A_{\mathrm{eff}}J.
\]

Only terminal \(V(t)\), \(I(t)\), and \(G(t)\) enter the sparse inverse. Hidden
fields are used only for post-training synthetic scoring.

### 2.2 Complete PINN and solver-as-judge contract

The complete PINN predicts the declared states, derives conductivity, and
evaluates electrical, defect-transport, thermal, and state-evolution residuals
together with initial conditions, boundaries, interfaces, terminal current,
and global energy/defect ledgers. The thermal balance contains

\[
\rho C_p\partial_tT=-\partial_xq_T+JE-
\gamma_{\mathrm{sub}}(T-T_0).
\]

Success requires terminal, field, held-out residual, interface, and global-
conservation gates simultaneously. Solver outputs are never relabeled as PINN
predictions, and terminal fit alone cannot authorize a sensitivity or inverse
claim.

### 2.3 Identifiability audit and reduced inverse

Terminal-to-field dependence and port-only recovery are audited before
inversion. Failure to recover the configured complete hidden fields motivates
releasing only \(\gamma_{\mathrm{sub}}\), with microphysics fixed and nuisance
coordinates fixed or tightly bounded. This is a benchmark-specific reduction,
not a universal impossibility theorem. The locked objective is

\[
\mathcal J(\gamma_{\mathrm{sub}})=
\operatorname{rRMSE}(\hat G,G)^2+
0.5\operatorname{rRMSE}(\hat I,I)^2+0.01\mathcal R_H.
\]

Candidate profiles, off-grid refinement, noise, observation count, protocol,
and switching-temperature mismatch are evaluated without averaging away the
failed wide-mismatch region.

### 2.4 Qiu source and digitization contract

The external audit uses Qiu et al., *Advanced Materials* (2024), DOI
`10.1002/adma.202306818`. Publisher main and Supporting Information PDFs are
hash-locked but not redistributed. SI Fig. S1 at 12 V is an implementation-
setting curve whose caption does not uniquely identify experiment versus
simulation. Main Fig. 2b at 12.5 V was withheld from model implementation, but
it comes from the same paper and is not an independent external holdout.

Curves were rendered at 600 dpi with explicit pixel-to-axis calibration. Raw
pixel coordinates, crop hashes, observed/interpolated flags, line-width
estimates, and pixel-jitter sensitivity bounds were retained. A post-run source
and visual audit found that the first repository implementation inserted an
unreported inverse-hyperbolic-tangent operation into SI Eq. S3 and that the
Fig. 2b extraction captured legend strokes. The original formal artifact is
therefore `implementation_contract_invalid` and none of its curve errors casts
a scientific vote. A single post-lock correction implements the literal
printed Eq. S3 and uses only the unaffected SI Fig. S1 traces; Fig. 2b remains
invalid/unassessed and is neither simulated nor scored.

### 2.5 Source-equation compact model and local-PDE bridge

The source reports a limiting-loop-proximity resistance law and

\[
\frac{dV_1}{dt}=\frac{V_{\mathrm{in}}}{R_LC}-V_1
\left(\frac{1}{R_{\mathrm{VO2}}C}+\frac{1}{R_LC}\right),
\]

\[
C_{\mathrm{th}}\frac{dT}{dt}=\frac{V_1^2}{R_{\mathrm{VO2}}}
-S_{\mathrm{th}}(T-T_0).
\]

Reported parameters are used without fitting. Because executable author code,
complete numerical initial conditions, reversal updates, and integration
tolerances are unavailable, repository choices are explicit assumptions.
DOP853/Radau parity establishes consistency of the repository equations only.

A separate read-only bridge compares author-fitted device-level lumped
quantities with locked M40/M40R local two-dimensional projections. It is a
parameter-transfer refusal test, not a calibration or another M40 run.

### 2.6 Claim gates

Thresholds are fixed before formal evaluation. Missing, non-finite, invalid, or
upstream-ineligible results fail closed. Status is restricted to `supported`,
`qualified_supported`, `failed_but_informative`, or `forbidden`.

## 3. Results

### 3.1 Hidden-field boundary and calibration-gated inverse

Terminal conductance is almost perfectly correlated with mean conductivity
(`0.9999966`), yet port-only ablations do not recover the complete thermal,
defect, phase, and conductivity fields. With the target reduced and nuisance
coordinates nominal, the constrained profile returns
\(\hat\gamma_{\mathrm{sub}}=4.5\times10^8\) for a truth of
\(4.5\times10^8\). The 36-case continuous off-grid audit covers noise levels
0, 2%, and 5% and observation counts 8, 16, 32, and 64; maximum refined
relative error is `0.05565`.

A 42-case confounding map identifies switching temperature as the dominant
tested nuisance coordinate. The marker near 0.1 K is benchmark-specific under
the configured 15% median-error criterion, not a laboratory specification.
Inside the calibrated/tightly bounded region, the noise, seed, observation-
count, and off-grid gates pass. Wide switching-temperature mismatch fails
systematically, with median error about `0.816` in the best configured protocol
group.

### 3.2 Complete-PINN trained-forward boundary

The architecture and operator/manufactured preflights pass, but every bounded
trained route fails the joint gate. The initial 1200-epoch MVE has port NRMSE
`0.123764 > 0.10` and all four normalized residual RMS values above `0.01`.
An instrumented control-volume replay reaches port NRMSE `0.0955475`, but
thermal, phase, interface-flux, and global-ledger errors remain severe and a
strong-Wolfe trial becomes non-finite. A mixed state--flux variant reduces
selected thermal and flux errors but still fails port, constitutive, PDE,
field, interface, ledger, and no-regression gates. The complete PINN is thus an
architecture and disclosed failure scaffold, not a successful trained solver.

### 3.3 Qiu two-dimensional bridge boundary

M40 passed 12 of 14 E0 checks but failed current and field mesh-convergence
gates. Its sole preregistered repair reduced finest-pair current and fixed-grid
field-p99 changes to `0.00592586` and `0.00847419`, passing all 14 original
numerical checks. The 12 V active run nevertheless left the locked R--T domain
at `360.22494 K` after only `0.0920339 R_LC` of the required `3R_LC` horizon;
coarse/fine current NRMSE was `0.0342127 > 0.02`. This supports a static
numerical implementation fact and a dynamic transfer boundary only.

### 3.4 Qiu compact-model source-equation boundary

The original formal artifact has no scientific vote because both its Eq. S3
implementation and Fig. 2b extraction violated the declared contract. In the
one permitted correction, the literal-S3 implementation achieved
DOP853--Radau agreement with worst waveform NRMSE `2.23216e-7`; activity class,
event count, and event-type sequence also agreed. Against the clean locked
12 V SI extraction, current and voltage range-normalized RMSE were `0.353154`
and `0.815643`, versus a `0.10` gate. The most favorable pixel-jitter
sensitivity-envelope scores, `0.320963` and `0.732598`, also fail. No fit, time
shift, phase alignment, parameter change, or replacement curve was used.

Main Fig. 2b remains `implementation_contract_invalid/unassessed` because its
blue and black traces contain legend pixels. It was not simulated or scored in
the corrective audit and provides neither success nor failure evidence. The
clean SI source-figure failure blocks the conditional effective-coordinate
preflight.

The read-only bridge gives a local/source resistance discrepancy factor of
`2.330233`, with source/local thermal-capacitance, thermal-conductance, and
time-scale ratios `635.5145`, `206`, and `3.085022`. These ratios support refusal
of direct lumped-to-local-PDE transfer; they do not identify the correct local
parameters or rescue M40R.

## 4. Discussion

The positive conclusion is deliberately narrow. In the frozen synthetic
model, identifiability screening changes the inverse question from arbitrary
hidden-field or multi-parameter recovery to a calibrated one-coordinate
estimate. This is useful because wrong-calibration controls and wide-prior
failures are retained. Protocol variation is secondary to calibration and is
not claimed to be globally optimal.

The negative audits prevent three shortcuts. A complete architecture or
correct differentiable operator does not establish a trained physical
solution. A terminal fit does not establish fields, conservation, or parameter
sensitivities. Agreement between two integrators establishes implementation
consistency, not fidelity to unavailable author code or measurements.

The Qiu bridge also shows why author-fitted lumped constants cannot be assigned
silently to a local PDE. Device-level heat capacity and conductance aggregate
electrodes, substrate, geometry, and boundary pathways. Their disagreement
with local projections is evidence against transfer, not a license to tune a
cell or boundary until an external curve is matched.

The supported workflow is therefore fail-closed: audit observability, reduce
the target, calibrate dominant confounders, verify the independent solver,
require field/interface/conservation evidence for neural claims, and refuse
outputs outside the supported region.

## 5. Limitations

1. Positive inverse evidence is synthetic and one-dimensional; no independent
   experimental validation or project-generated measurement is available.
2. \(\gamma_{\mathrm{sub}}\) is an effective benchmark coordinate, not a
   substrate material constant, and its recovery is calibration-conditional.
3. No trained complete-PINN forward, sensitivity, or inverse route passes all
   gates.
4. The Qiu SI lacks a complete executable author contract; exact reproduction
   is forbidden.
5. The Qiu curves are digitized publication data. Fig. 2b is from the same
   paper and its present extraction is invalid because of legend contamination.
6. M40/M40R is not a calibrated active two-dimensional device model; its
   active trajectory exits the source-supported temperature range.
7. The bridge ratios diagnose incompatible aggregation levels but do not
   identify missing spatial parameters or a valid reduced coordinate.
8. Protocol-dependent quotient, PINN sensitivity fidelity, terminal-only 2D
   field recovery, experimental validation, full STL reproduction, universal
   Fourier/F-SPS superiority, and device-grade FEM/3D remain forbidden.

## 6. Conclusion

Sparse-terminal phase-transition inversion is credible only when the requested
quantity is supported by the observation and calibration contract. Target
reduction and switching-temperature calibration enable conditional recovery
of an effective thermal coordinate in the frozen synthetic benchmark, while
wider mismatch defines a stable refusal region. Complete-PINN training,
two-dimensional active transfer, and the public compact-model anchor do not
pass their gates. The resulting evidence boundary is explicit: estimate the
low-dimensional coordinate that is supported and refuse stronger physical,
neural, or external-validation claims until direct evidence exists.

## 7. Code, data, and reproducibility

Configurations, code, tests, JSON/CSV results, figures, reports, and the claim
matrix implement the chain `config -> implementation -> test -> result ->
figure/table -> claim`. Publisher PDFs are hash-locked locally and are not
redistributed where permission is not established. Digitized values are
labeled as derived publication curves. Frozen Ground Truth v1.1 and every
negative formal result remain immutable.

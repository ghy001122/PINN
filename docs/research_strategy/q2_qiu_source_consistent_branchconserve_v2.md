# Q2 Qiu Source-Consistent BranchConserve v2 — Stage A Contract

## Purpose

Stage A asks one bounded question before any new two-dimensional solve: does a
literal, source-traceable implementation of Qiu Supporting Information
equations S1--S7 provide a stable quasistatic domain worth testing with a new
BranchConserve L1 pilot?

The output is an entry decision only. It is not a 2-D physics vote, a Qiu
quantitative reproduction, or a PINN result. `scientific_vote=false` and
`formal_execution_count=0` remain fixed.

## Preserved v1 Evidence

PR #29 and its `STOP_BRANCHCONSERVE_PILOT` result are immutable. Stage A is a
new v2 source audit, not a repair, resume, or reinterpretation of v1. The v1
kernel used an expit scale of `7.193 K` and logarithmic conductivity mixing;
the source major loop instead uses `beta=0.253 K^-1` for steepness and an
additive device-resistance equation.

## Source Equations

For branch metadata \(\delta_\uparrow=+1\) and
\(\delta_\downarrow=-1\), the no-reversal major-loop limit is

\[
F_b(T)=\frac12\left[1+\tanh\left(\beta\left(T_c+\delta_b\frac w2-T\right)\right)\right],
\qquad s_b(T)=1-F_b(T).
\]

The branch midpoints are \(336.3965\,\mathrm K\) on heating and
\(329.2035\,\mathrm K\) on cooling. The equivalent logistic scale is
\(1/(2\beta)=1.97628458498\,\mathrm K\), not \(w=7.193\,\mathrm K\).

Two source roles are kept separate:

\[
R_b^{QS}(T)=R_0e^{E_a/T}F_b(T)+R_m,
\]

\[
R_b^{fil}(T)=R_0e^{E_a/T}F_b(T)+kR_m,
\qquad k=4.90.
\]

S1 is the only candidate for a later production-voting uniform limit. S7 is a
diagnostic dynamic-filament comparator. The direct “beta plus k” patch is
rejected: the two parameters repair different source semantics, and neither
converts v1 logarithmic conductivity mixing into S1.

## Independent 0-D Oracle

The unknowns are \(u=[V_d,T]\). For a fixed source voltage \(V_s\), load
\(R_L\), branch, and resistance role,

\[
\dot V_d=\frac{(V_s-V_d)/R_L-V_d/R_b(T)}{C},
\]

\[
\dot T=\frac{V_d^2/R_b(T)-S_{th}(T-T_0)}{C_{th}}.
\]

Eliminating \(V_d\) gives

\[
V_d=\frac{V_sR_b}{R_L+R_b},
\qquad
h(T)=\frac{V_s^2R_b}{(R_L+R_b)^2}-S_{th}(T-T_0).
\]

All roots are enumerated inside

\[
T_0\le T\le T_0+\frac{V_s^2}{4R_LS_{th}}.
\]

Nested 4097/8193 partitions, sign changes, endpoints, analytic stationary
points, and tangent candidates must produce the same root count and a sorted
Hausdorff temperature difference no larger than \(10^{-8}\,\mathrm K\).
Equilibrium current and power residuals must each be no larger than
\(10^{-12}\).

The analytic local Jacobian is checked against a central-difference Jacobian
to relative Frobenius error \(\le10^{-6}\); every eigenpair has relative
residual \(\le10^{-10}\). With \(\tau_\theta=C_{th}/S_{th}\), stability is
classified using \(\alpha\tau_\theta\), and voting points additionally require
the robust margin \(-\alpha\tau_\theta\ge10^{-2}\).

## Continuous Quasistatic Reachability

The precise label is `continuous_quasistatic_reachable`.

- Heating begins from the unique low, robustly stable root at \(V_s=0\).
- Cooling begins from the unique high-conductive, robustly stable root at
  \(V_s=17\,\mathrm V\), with \(s\ge0.90\).
- The source grid is \(0,0.5,\ldots,17\,\mathrm V\), plus
  \(15.8\,\mathrm V\).
- Predictor-corrector continuation follows only one continuous stable
  component, with deterministic halving down to \(0.015625\,\mathrm V\).
- A marginal, unstable, invalid, or unmatched point terminates reachability.
  Later stable roots are `post_switch_reachability_unresolved`; they do not
  vote.
- \(12.5\,\mathrm V\) is diagnostic-only and is never steady GT.

The forward nondegeneracy gate requires at least five voting biases, a
conductive-state span of at least 0.50, at least two states inside
\([0.1,0.9]\), at least one state \(\ge0.75\), and robust stability at every
voting point. The dual-branch gate additionally requires five common source
voltages and at least two with branch separation \(|s_\uparrow-s_\downarrow|
\ge0.10\).

## Conditional Load Sentinel

If the 12 kΩ S1 oracle lacks a dual-branch domain, the only allowed load
sentinel is \(R_L\in\{3,6,9,12,18,24,36\}\,\mathrm{k}\Omega\). It is a
finite design check, not a fit or continuous optimization. A designed load is
selected by minimum absolute log distance from 12 kΩ, with lower resistance as
the tie-breaker. The 12 kΩ result remains the negative control.

## Terminal Routing

Exactly one result is emitted:

- `A_GO_12K_DUAL_BRANCH_L1`;
- `A_GO_DESIGNED_LOAD_L1`;
- `A_PIVOT_FORWARD_ONLY`;
- `A_STOP_STEADY_ROUTE`;
- `A_INVALID_SOURCE_AUDIT`.

The first three permit only a separately authorized Stage B L1 pilot. They do
not establish 2-D source consistency. Stage A stops after its result PR and
does not run BranchConserve L1, B1/B2, Jacobians, or PINNs.

## Planned Stage B Uniform Limit

If separately authorized, Stage B will use S1 and a VO2-only, ideal-contact
uniform subproblem to determine one L1 geometry factor
\(g_{geom}=G_{port}/\sigma_{test}\) with \(\sigma_{test}=1\,\mathrm{S/m}\).
The production candidate would be

\[
\sigma_{eff}(T,b)=\frac{1}{g_{geom}R_b^{QS}(T)}.
\]

No per-grid renormalization is allowed. Finite electrode/contact effects that
break this scaling stop Stage B. The only permitted name is
`source-model-scale-anchored device-effective conductivity`; intrinsic or
contact-resolved material claims remain forbidden.

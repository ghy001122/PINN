# Phase 1-v2 S2 2.5D Reference Contract

Status: `preregistered_pending_implementation_and_bounded_smoke`

Task ID: `Q2_PHASE1_V2_S2_REFERENCE`

This document is the active Phase 1 numerical contract. It does not report a
solver result. The v6-v8 fixed-bottom material-stack/K-state contract and its
96 planned evaluation items remain immutable historical evidence with
`failed_but_informative` and `planned_not_executed` dispositions. Phase 1-v2
does not reinterpret, overwrite, or execute them.

## 1. Manuscript role and evidence boundary

Phase 1-v2 must build the independent judge for the later R1
`HysGeo-Hybrid-PINN`. The active physical contribution is now:

> a conservative real in-plane electrothermal field coupled to a
> source-scale-preserving, locally distributed, device-effective thermal
> closure.

All evidence is literature-guided synthetic numerical digital-twin evidence.
The model is not a Qiu-device calibration, an intrinsic local-property model,
an experimental validation, or a recovered substrate temperature field.

The active machine-readable contracts are:

- `configs/geophase_phase1_v2_s2_reference.yaml`;
- `configs/geophase_phase1_v2_formal_manifest.yaml`;
- `configs/qiu_same_device_thermal_holdout_audit.yaml`;
- `configs/geophase_phase1_s1_diffusive_sensitivity_mve.yaml`;
- `configs/qiu_vo2_phase1_source_contract.yaml` (source facts only).

No new numerical calculation may precede the pushed preregistration commit.
No formal Phase 1-v2 campaign may run without later, explicit user
authorization tied to its locked commit, config hash, and manifest hash.

## 2. Resolved geometry and fields

The resolved domain is the single VO2 footprint
\(\Omega=[0,L]\times[0,W]\). The active fields are potential \(\phi\),
temperature \(T\), effective conductive-state coordinate \(s\), and
engineering branch memory \(b\). The left and right electrode-overlap masks
are thermal masks only; they do not create a metal electrical shunt.

VO2 storage and in-plane conduction are explicit over the full active plane.
Ti/Au storage and in-plane conduction are explicit only under the electrode
mask. Nonzero interdevice thermal coupling, a full vertical mesh, 3D/FEM, and
recovery of a substrate field are forbidden in Phase 1-v2.

## 3. Electrical, phase, and circuit equations

The in-plane current equation remains

$$
\nabla_\parallel\!\cdot\left(
t_{\rm VO2}\sigma(T,s)\nabla_\parallel\phi\right)=0,
$$

with finite-contact Dirichlet electrodes, electrically insulating remaining
boundaries, conservative harmonic face conductance, and terminal current from
an independent boundary-flux integral. Conductivity is the locked
device-effective white-box logarithmic insulating/metallic mixture; the
nominal metallic endmember uses \(R_m\), never \(kR_m\).

The phase and branch equations and the external source--load--parallel-
capacitance circuit retain the locked v6 continuous semantics. The branch
state holds exactly at zero temperature rate. Free `log_sigma`, source-curve
fitting, and Qiu author-code-reproduction claims are forbidden.

## 4. S2 nominal thermal closure

Let \(\chi_e(x,y)\) be the electrode mask. The explicit areal capacity and
sheet thermal conductance are

$$
C_{\rm plane}^A(x,y)=
\rho_v c_v t_v+
\chi_e\left(\rho_{\rm Ti}c_{\rm Ti}t_{\rm Ti}
+\rho_{\rm Au}c_{\rm Au}t_{\rm Au}\right),
$$

$$
K_\parallel^A(x,y)=
k_vt_v+
\chi_e\left(k_{\rm Ti}t_{\rm Ti}+k_{\rm Au}t_{\rm Au}\right).
$$

For active-plane area \(A=LW\), define these quantities once at the nominal
20 nm contact-overlap geometry:

$$
C_{\rm explicit}=\int_\Omega C_{\rm plane}^A\,dA,
\qquad
C_m=C_\theta-C_{\rm explicit}>0,
$$

$$
c_m^A=\frac{C_m}{A},
\qquad
g_\theta^A=\frac{G_\theta}{A}.
$$

The nominal S2 equation is

$$
\left[C_{\rm plane}^A(x,y)+c_m^A\right]\partial_tT
=\nabla_\parallel\!\cdot\left(K_\parallel^A\nabla_\parallel T\right)
+q_J^A-g_\theta^A(T-T_0).
$$

S2 has no independent vertical-memory temperature. It must not be
implemented by reusing a one-state passive ladder. \(C_\theta\) is interpreted
as the first low-frequency coefficient of the uniform-mode device thermal
admittance, not as a measured material-stack heat capacity. The ledger uses
the capacity present in the actual S2 state equation. For diagnostic clarity
the same storage may be decomposed into explicit-plane and device-effective
closure contributions, but it is counted exactly once.

The exact uniform-mode identities are

$$
\int_\Omega g_\theta^A\,dA=G_\theta,
\qquad
\int_\Omega\left(C_{\rm plane}^A+c_m^A\right)dA=C_\theta.
$$

They validate implementation of the selected closure, not the physical
uniqueness of that closure.

The resulting \(c_m^A\) is frozen during the 10/30 nm contact-overlap audits.
Those audits change only the explicit Ti/Au mask. Re-normalizing \(c_m^A\) to
force the same \(C_\theta\) at every altered geometry is forbidden because it
would hide the very geometry sensitivity being audited. The exact
\(C_\theta\) identity votes only at the nominal geometry.

## 5. S1 non-blocking model-form sensitivity

S1 is not the nominal reference. With

$$
\tau=\frac{3c_m^A}{g_\theta^A},
\qquad
x=\sqrt{s\tau},
$$

the sole authorized analytic sensitivity family is

$$
Y_{\rm S1}(s)=g_\theta^A\frac{x}{\tanh x}
=g_\theta^A+s c_m^A+O(s^2).
$$

The active-work budget is at most 24 h and elapsed budget at most 48 h. A
common positive-real order \(K=2\) is attempted first and common \(K=3\) only
if necessary; mixed orders, higher orders, a second analytic family, and
`S1.1` are forbidden. Moment matching, positive Foster/Cauer elements,
strictly negative real poles, passivity, response errors, and an independent
ledger are mandatory.

Self-fitting success cannot select S1. Without an eligible same-device thermal
holdout, S1 remains a model-form sensitivity regardless of its approximation
quality. With a separately authorized eligible holdout, production selection
additionally requires at least 20% relative improvement over S2, an effect
larger than three times numerical uncertainty, and agreement in at least two
independent observations or windows.

## 6. Bounded same-device source audit

One non-blocking source audit is authorized for at most 4 h. Eligible evidence
is restricted to a directly traceable same-device temperature transient,
multi-frequency complex thermal impedance/admittance, isolatable heat-pulse
decay/ringdown, or an equivalent observation that directly distinguishes a
first-order closure from diffusive memory. Ordinary terminal-current traces,
single-frequency or single-threshold data, different devices, and observations
requiring a joint electrical/phase/thermal refit cannot select S1.

The audit may record locators and eligibility decisions. It may not digitize
or fit a curve. If eligible evidence is found, work stops for separate
authorization. If none is found, S2 remains nominal.

## 7. Numerical implementation and ledgers

The independent judge uses cell-centred conservative FVM, harmonic face sheet
coefficients, implicit backward Euler, independently refined time steps, and
the locked nonlinear/failure-path rules. The S2 thermal block uses a diagonal
cell capacity; contact-mask Ti/Au properties must not be collapsed to a scalar.
The reference solver must not import or reuse a future PINN discrete residual.

Required ledgers are:

1. thermal: Joule power equals S2 stored-energy rate plus vertical and lateral
   outflow;
2. circuit: source power equals load dissipation, capacitor physical-energy
   rate, backward-Euler capacitor dissipation, and device power;
3. combined electrothermal: the same source balance with S2 thermal storage
   and thermal outflows;
4. device identity: independently reconstructed terminal power equals the
   field-integrated Joule power.

Internal lateral face fluxes must cancel pairwise. No-flux boundary outflow is
recorded from boundary faces, not inferred only from a matrix row-sum identity.

Because the mask makes \(C_{\rm plane}^A\) spatially nonuniform, unforced
spatially uniform exponential cooling is not an exact manufactured solution.
The registered uniform-temperature manufactured case must use

$$
q^\star(x,y,t)=
\left[C_{\rm plane}^A(x,y)+c_m^A\right]\dot T^\star(t)
+g_\theta^A[T^\star(t)-T_0],
$$

or an explicitly homogeneous-mask fixture.

## 8. Preregistered verification and formal inventory

The new formal manifest contains 63 evaluation items. The number is derived
from the active S2 model and is not required to match the retired 96-item
inventory. It covers:

- nine manufactured-solution items, including the forced S2 response;
- thirty independent spatial/time refinement items;
- nine contact-overlap QoI audits, with the three nominal trajectories reused
  only where every physical input matches an existing refinement trajectory;
- four zero-coupling duplicate limits;
- five fail-closed controls;
- six analytic/zero-input limits.

Five algebraic S2/source identities are foundation preflights outside the
formal solver inventory. Every required gate in the YAML must pass together. Smoke is non-voting and
may not produce a formal evaluation artifact. The formal execution count is
zero at preregistration and throughout implementation/readiness. A formal run
is a separate future checkpoint.

## 9. Stop rules

- One bounded software repair is allowed only when S2 smoke identifies a
  concrete implementation defect.
- If a correct S2 implementation fails physics, conservation, or convergence,
  the positive 2D route stops and the manuscript downgrades to the retained
  `gamma_sub`/identifiability evidence.
- S1 failure, lack of eligible holdout, or budget exhaustion never blocks S2
  and never triggers another kernel family.
- No gate, case, parameter, or numerical tolerance may be changed after a
  formal Phase 1-v2 execution begins.

## 10. Current claim boundary

Preregistration supports only that the S2 closure, the S1 sensitivity, the
source audit, the 63-item inventory, and their failure rules were declared
before new computation. It does not support Phase 1-v2 success, a successful
PINN, an identified thermal spectrum, Qiu-device reproduction, experimental
validation, intrinsic local parameters, nonzero dual-device coupling, or
full-3D/FEM equivalence.

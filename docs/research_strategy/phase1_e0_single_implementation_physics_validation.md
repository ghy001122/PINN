# Phase 1 E0 Single-Implementation Physics Validation

## Status And Purpose

Task ID: `Q2_PHASE1_E0_SINGLE_IMPLEMENTATION_PHYSICS_VALIDATION`.

Status: contract activated; no E0 numerical preflight or formal execution is
authorized.

This route reopens the Phase 1 scientific question under a new identity. It
does not repair or rerun equivalence-v1, v2, or v3. Its only question is:

> Can one frozen S2 implementation independently pass analytic,
> manufactured, conservation, refinement, topology, trend, and failure-path
> gates strongly enough to serve as the judge for later hybrid PINN work?

Manuscript destination: the reference-solver equations and Figure 2 evidence
required before C01 `HysGeo-Hybrid-PINN`. Passing a bounded preflight would
only make the route eligible to request formal authorization; it would not be
a Phase 1 pass.

## Requirement Contract

### Objective

Activate a direct physical-validation route for the Qiu-inspired real `x-y`
VO2 plane, source-scale-preserving S2 closure, white-box hysteresis, external
RC circuit, terminal flux, and energy ledgers.

### Inputs

- source-corrected S2 configuration and Qiu source contract;
- the unchanged 63-item / 60-execution / 3-reuse scientific manifest;
- one frozen implementation selected before any E0 numerical result;
- the existing controller-v2 and streaming implementation;
- immutable v1/v2/v3 evidence as history only.

### Outputs Of This Activation

- one machine-readable activation configuration;
- this contract;
- current-authority routing updates;
- a focused static regression test;
- no numerical, preflight, formal, dataset, or PINN artifact.

### Allowed Modification Scope

- current routing and evidence-index prose;
- this new config and contract;
- focused static tests;
- corrections to the execution guide where old K-state outputs or nonzero
  coupling conflict with the current S2 contract.

### Prohibited Actions

- repair, reinterpret, stitch, or rerun equivalence-v1/v2/v3;
- create equivalence-v4/v5;
- run C1/C2/C3, E0 preflight, or any of the 63 formal items;
- generate Phase 2 data or train a PINN;
- run inverse, S1/v6-v8, FEM/3D, M44, NbO2, or nonzero coupling;
- change S2 equations, parameters, tolerances, protocols, manifest counts, or
  scientific thresholds;
- modify frozen GT.

### Success Gate

The activation succeeds when all authority files point to this route, the
implementation and 63-item mapping are frozen, failure classes and budgets are
explicit, static tests pass, and `formal_execution_count=0` remains true.

### Failure Route

A documentation, hash, or routing inconsistency blocks activation and is fixed
without numerical work. It is not a scientific failure. No alternative
implementation may be selected after E0 numerical results exist.

### Budget

This activation has zero numerical-solver, training, GPU, and formal budget.
The proposed future non-voting E0 preflight is capped at 7200 s CPU wall time
but remains unauthorized. The inherited formal envelope remains 14400 s until
the user explicitly authorizes a target-machine or budget revision.

## Preserved Terminal History

| Route | Terminal record | Scientific boundary |
| --- | --- | --- |
| strict-equivalence-v1 | `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`, 12/57 | rejects its named strict implementation-equivalence attempt, not S2 physics |
| equivalence-v2 | `VALID_FAIL`, 10/57, record validation | no A/B/C scientific vote; no retry |
| equivalence-v3 | `VALID_FAIL`, 12/57, cardinality validation at plan 11 | no A/B/C scientific vote; no retry |

All three remain immutable. This route is neither a continuation nor a repair
of them.

## Frozen Single Implementation

The selected implementation is the source-corrected performance candidate
originating at commit `1ae2704f6d84a3733d9de58aa23d992aa0c471a5`, tree
`86c32f6d80fa4beedbb83e17b96567591f777555`.

This selection does **not** claim equivalence to PR #8. It will be judged
directly against independent mathematical and physical gates. The PR #8 code
is retained as historical, non-voting context and is not an oracle gate.

The selected solver must remain discretization-independent from future PINN
automatic-differentiation residual code. Switching implementations after any
E0 numerical result is forbidden.

## Physical Contract

The in-plane electrical equation is

\[
\nabla_{\parallel}\cdot
\left(t_{\mathrm{VO_2}}\sigma(T,s,b)
\nabla_{\parallel}\phi\right)=0.
\]

The S2 areal thermal equation is

\[
C_{\mathrm{eff}}^A(x,y)\,\partial_tT
=\nabla_{\parallel}\cdot
\left(K_{\parallel}^A(x,y)\nabla_{\parallel}T\right)
+q_J^A-g_\theta^A(T-T_0).
\]

The conductive state and branch memory retain the locked first-order and
bounded directional closures. The circuit remains

\[
C_p\dot V_d=\frac{V_{\mathrm{in}}-V_d}{R_L}-I_{\mathrm{dev}},
\qquad
I_{\mathrm{dev}}=\int_{\Gamma_e}-t\sigma\nabla\phi\cdot n\,ds.
\]

S2 has no independent vertical state. A later R1 PINN therefore predicts field
states `[phi, T, s, b]` plus circuit state `Vd`; it does not predict `z1,z2`.
Contact resistance and nonzero dual-device coupling remain omitted and
unclaimed.

## Reused Scientific Inventory

No new scientific item is created and no old item is removed.

| Group | Items | Purpose |
| --- | ---: | --- |
| MMS | 9 | manufactured foundations |
| REF | 30 | single-device space/time/event refinement |
| TOP | 9 | contact-overlap QoI audit, including 3 legal reuses |
| DUAL0 | 4 | exactly-zero-coupling duplicate limits |
| FAIL | 5 | fail-closed controls |
| LIM | 6 | analytic and zero-input limits |
| Total | 63 | 60 unique execution units and 3 reuses |

Every item remains `planned_not_executed`. The 15.8 V qualitative locking
probe remains the active high-bias protocol.

## Future E0 Preflight Gate

Fresh authorization is required before executing any of these steps:

1. source-scale, positivity, mask, and uniform-mode identities;
2. analytic and manufactured electrical/thermal limits;
3. current balance, device-power identity, and thermal/circuit/combined ledgers;
4. the locked critical-state C1 fixture;
5. the bounded critical-trajectory C2 fixture;
6. L1/L2/L4 runtime, RSS, rejection/fallback, and makespan forecast.

A complete pass permits only
`READY_TO_REQUEST_FORMAL_CAMPAIGN_AUTHORIZATION`. It does not unlock Phase 2 or
PINN training.

## Failure Classification

| Failure class | Validity and claim status | Required response |
| --- | --- | --- |
| schema, runner, environment, or config defect | `validity: invalid`, `claim_status: forbidden` | no scientific vote; one bounded versioned repair with regression |
| implementation code defect | `validity: invalid`, `claim_status: forbidden` | reproduce defect, repair once, rerun smallest affected preflight |
| complete bounded readiness failure | valid readiness evidence; `failed_but_informative` only for readiness | Phase 1 remains forbidden/unassessed; stop before formal |
| performance/resource-only failure | Phase 1 science remains forbidden/unassessed | request target-machine or budget decision; do not change physics |
| valid formal scientific-gate failure | `failed_but_informative` | preserve results, block Phase 2, follow the versioned downgrade route |

These rules apply prospectively. They do not reclassify the consumed v1/v2/v3
records.

## Route To The Planned Innovations

An E0 formal pass would complete the independent judge for the implemented
`A double-prime + white-box kernel + port/RC/ledger` foundation. It would then
unlock, in order:

1. C01 `HysGeo-Hybrid-PINN`;
2. C06 homotopy-only ablation;
3. C05 transition-localized-expert-only ablation;
4. C11 combined `GeoPhase-HomoMoE-PINN` only after both single modules have
   independent value;
5. C04 solver-first observable-subspace MVE and sensitivity gate before any
   C07/C13/C15 inverse route.

The immediate next checkpoint is only
`Q2_PHASE1_E0_PREFLIGHT_PENDING_FRESH_AUTHORIZATION`.

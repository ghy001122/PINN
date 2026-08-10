# Active Phase

Active phase ID: `Q2_PHASE1F_M1_SELF_CONSISTENT_IMT_CONTRACTION_GATE`

Status: `completed_after_valid_non_single_valued_forward_no_go`

Current checkpoint: `Q2_M1_SELF_CONSISTENT_IMT_CONTRACTION_GATE_V1_VALID_NONUNIQUE_NO_GO`

## Task Contract

- Objective/manuscript destination: determine whether a Qiu-anchored,
  branch-conditioned self-consistent major-loop M1 closure supplies a unique
  steady forward relation and enough contraction headroom to justify any new
  neural question.
- Inputs: the immutable PR #40 result, source-contract `beta=0.253 K^-1`, loop
  width `7.193 K`, `Tc0=332.8 K`, the contact-aware 10 x 25 M1 operator, six
  bounded Stage A voltage conditions, and cold/hot initial fields.
- Outputs: actual fixed-point fields, uniqueness and ledger tables, applicable
  figures, stop-gated contraction/A1-A2 schemas, report, and manuscript route
  evidence map.
- Allowed scope: the independent `self_consistent_major_branch` closure,
  `alpha=0.35`, physical `lambda_J=1`, at most 22 main physical cases, and a
  conditional neural stage only after a passed single-valued headroom gate.
- Prohibited: modifying prescribed-state history, averaging distinct solutions,
  adding hidden labels or network capacity, full hysteresis/minor loops,
  dynamic stability, inverse, MoE, NbO2, threshold movement, or formal OOD.
- Result: 6/6 Stage A cold/hot pairs are finite, converged, and ledger-valid,
  but only heating 0.95 V is unique. The other five pairs differ by
  `0.989--0.994` in T-rise and current; Stage B/C and neural execution are
  correctly ineligible.

Final disposition:

```text
NO_GO_SINGLE_VALUED_IMT_FORWARD_MAP
validity = valid
claim_status = failed_but_informative
scientific_role = diagnostic_non_voting
```

The sole next priority is limitation-manuscript consolidation plus, only under
fresh authorization, a solver-first physical-selection/equilibrium-manifold
contract. Contraction, A1/A2 headroom, formal OOD, and neural-forward rescue
remain ineligible under the current single-valued surrogate contract.

## Preserved PR #40 Contract And Outcome

PR #40 at `a4a20a919dd4eca907269cf0aef351ecdb0c37b3` remains the immutable
`NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES` baseline and was
squash-merged unchanged as `22e3760f1505691f55d5d2366ca7659d7a7723a6`.
Its 36-case geometry data, M2 sentinels, POD/ridge/neural metrics, figures,
checkpoint, report, and interpretation are not modified by this new physical
premise.

## Preserved PR #39 Contract And Outcome

- Objective/manuscript destination: determine whether a network can learn only
  a low-rank M1 thermal initialization while one or two frozen conservative
  projections recover accurate phase-state-conditioned electrothermal fields.
- Inputs: PR #38's frozen 12-case M1 data and 8/2/2 complete-case split; no
  reference dataset regeneration and no validation/test POD leakage.
- Outputs: dense Torch operator parity, train-only POD, one actual latent-model
  training, COLD/A2/N0/N1/N2/NC metrics, timings, predictions, seven figures,
  one checkpoint, and one report.
- Allowed scope: one 2x32 SiLU latent network, rank selected once at 99.9%
  train energy, seed `20260809`, float64, and exactly 1500 Adam steps.
- Prohibited: Frozen GT edits; current-clamp/BranchConserve/NLS/equivalence
  reruns; threshold movement; inverse, MoE, dynamic RC, NbO2, or formal OOD.
- Success gate and routing are frozen in
  `configs/q2_m1_latent_solver_projected_pinn_mve_v1.yaml`.
- Failure route: operator parity or low-rank failure stops before training;
  otherwise the exact Fast-GO/Certified-GO/NO-GO rules bind without threshold
  movement.

## Preserved PR #39 Frozen Scientific Premise

For preserved PR #39, the scientific object was phase-state-conditioned quasi-static
electrothermal fields. M1 uses finite external electrical contact resistance,
contact-corrected vertical thermal conductance, contact/bare in-plane thermal
conductance differences, localized sink, and prescribed state-conditioned
conductivity. Branch and state are protocol/state metadata, not dynamics.

That historical network takes only normalized voltage, branch metadata, prescribed state,
and sink amplitude, and outputs rank-2 POD coefficients. It has no coordinate
input and does not directly predict phi, J, or q. The undamped dense Torch M1
operator supplies electrical and thermal fields, Robin contacts, ports, face
fluxes, Joule partition, and ledgers; COLD/NC retain the frozen 0.35 relaxation.

## Claim Boundary And Preserved History

Operator parity is `supported`; the selected reduced reference is at most
`qualified_supported`; this one-seed MVE is diagnostic/non-voting. It uses all
eight complete train fields for POD and training, so data-free, mesh-free, and
sparse-anchor-only identities are forbidden. Formal superiority, experimental
validation, dynamic hysteresis, inverse recovery, and material transfer remain
`forbidden`.

PR #38 at `19a0a1c23aa27f9bfd7c91df13f5113c7d1ced57` remains the immutable
`NO_GO_M1_RCV_PINN_RESCUE` baseline and was squash-merged unchanged as
`425d485838ac90cb2b7dba36bad409a9ef931b28`. PR #37 and all earlier stops,
dynamic work, equivalence evidence, and Frozen GT remain immutable.

## Executed Outcome And Route

Dense float64 operator parity passed 12/12 cases. Worst phi/T map/current
errors were `2.129e-15`, `8.631e-10`, and `6.083e-15`; worst terminal and sink
ledgers were `2.839e-15` and `2.775e-12`. No reference dataset solve was rerun.

Train-only POD selected rank 2 at cumulative energy `0.999997413`. The sole
2x32 SiLU network completed 1500 steps in `131.94 s`. On the two frozen test
cases N2 mean T-rise/phi/current errors were `5.813e-4`, `3.467e-5`, and
`5.760e-4`; mean fixed-point and sigma defects were `0.013418` and
`6.069e-4`; the worst ledger was `9.040e-14`. N2 passed 1/2 complete cases,
improved mean joint-field score over N0 by `99.828%`, and achieved median
`17.900x` speedup versus COLD. NC did not certify within eight extra updates.
Analytic A2 passed the same fast per-case thresholds on 2/2 test cases and had
lower mean joint-field error than N2; at the time, that GO made formal OOD eligible but
does not establish neural-specific value.
Final disposition:

```text
GO_M1_LATENT_PROJECTION_PINN_MVE
validity = valid
claim_status = qualified_supported
scientific_role = diagnostic_non_voting
scientific_vote = false
```

This prior bounded MVE remains valid and immutable, but the later geometry
admission NO-GO supersedes its formal-OOD eligibility. Do not start formal OOD
or another neural-forward rescue.

# Active Phase

Active phase ID: `Q2_PHASE1E_M1_LATENT_NEURAL_VALUE_GEOMETRY_ADMISSION`

Status: `completed_after_valid_neural_specific_value_no_go`

Current checkpoint: `Q2_M1_LATENT_NEURAL_VALUE_GEOMETRY_ADMISSION_V1_VALID_NO_GO`

## Task Contract

- Objective/manuscript destination: test whether the train-only POD neural
  latent mapper has independent value over analytic A1/A2 and closed-form
  ridge R1/R2 on a true 10/20/30 nm contact-geometry domain.
- Inputs: 36 newly generated M1 cases on the fixed 10 x 25 grid, four bounded
  M2 sentinels, a 20/4/12 train/validation/30-nm-test split, and immutable PR
  #39 history.
- Outputs: matched-budget A1/A2/R1/R2/N1/N2 fields, true look-ahead defects,
  timings, one actual 1500-step seed, POD/ridge/checkpoint/predictions, eight
  figures, tables, and a claim-gated report.
- Allowed scope: one rank-selected 2x32 SiLU mapper at seed `20260809`; two
  additional seeds only after an initial Path H or Path S pass.
- Prohibited: threshold movement, validation/test leakage, PR #39 changes,
  formal OOD, another architecture, inverse, MoE, dynamic RC, or material
  transfer.
- Result: 36/36 M1 gates and 4/4 M2 sentinels pass; POD rank is 2. N1 passes
  11/12 cases but is `42.0%` worse than A1 in mean joint-field score; N2 passes
  12/12 but is `32.5%` worse than A2. Both neural admission paths fail, so the
  two conditional seeds are correctly skipped.

Final disposition:

```text
NO_GO_M1_NEURAL_SPECIFIC_VALUE_A2_OR_RIDGE_DOMINATES
validity = valid
claim_status = failed_but_informative
scientific_role = diagnostic_non_voting
```

The sole next priority is limitation-manuscript consolidation using the M1
conservative operator and analytic A2 as numerical assets. Formal OOD and all
new neural-forward rescue architectures are ineligible.

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

## Frozen Scientific Premise

The scientific object remains phase-state-conditioned quasi-static
electrothermal fields. M1 uses finite external electrical contact resistance,
contact-corrected vertical thermal conductance, contact/bare in-plane thermal
conductance differences, localized sink, and prescribed state-conditioned
conductivity. Branch and state are protocol/state metadata, not dynamics.

The network takes only normalized voltage, branch metadata, prescribed state,
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
lower mean joint-field error than N2; the GO therefore opens formal OOD but
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

# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CC_B_BRANCH_STABILITY_BRACKET_NUMERICAL_STOP`.
- Preserved prior checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Branch-bracket baseline: `22ed32018d5463e171be960beb00710a055a1f13`.
- Result branch: `codex/q2-cc-b-branch-stability-transition-bracket-v1`.
- Parent disposition: `INVALID_CC_B_EXECUTION`.
- Requalification disposition: `PASS_CC_B_STABILITY_REQUALIFICATION`.
- Branch-bracket disposition: `STOP_NUMERICAL_SEMANTICS_NOT_CLOSED`.
- `cc_b_matrix_launch_count=0`; `scientific_vote=false`;
  `formal_execution_count=0`.

## Current-Clamp CC-B Outcome

- The algebraic conductive-channel clamp is implemented; the parent CC-B smoke
  remains immutable `INVALID_CC_B_EXECUTION` with only local 0.2 mA evidence.
- PR #34 validly requalified 0.4 mA as `POSITIVE_UNSTABLE` on L1/L2 k6/k10
  (`max eta=3.375e-7`); this remains a non-voting single-point result.
- The new 26-point L1/k6 bracket has 25 valid equilibrium/spectrum records, but
  heating 0.35 mA hit `CCB_KRYLOV_BUDGET`. Its terminal is invalid; R2/R3 were
  skipped and 19 transverse-mode records remain diagnostic only.
- Uniform, formal matrix, CC-C, GT, and PINN are unexecuted/forbidden; formal
  and matrix counters remain zero.

## Current-Clamp CC-A Outcome

| Item | Result | Evidence boundary |
| --- | --- | --- |
| implementation and focused regression | implemented; `29 passed` | Software and formula-contract fact |
| formal branch/current roots | 14/14 unique, certified, stable, and continuation-connected | Bounded 0-D admission evidence |
| heating branch | 7 points; state span `0.7760256851`; 5 intermediate points | Fixed S1 up-branch metadata only |
| cooling branch | 7 points; state span `0.6754940767`; 6 intermediate points | Externally preconditioned S1 down-branch metadata only |
| common branch separation | 7/7 currents exceed `0.1` | Branch-conditioned; not dynamic switching |
| source-scale mapping | exact algebraic port round trip, max error `1.60e-16` | Device-effective proxy; no 2-D execution |
| CC-B/CC-C/PINN | not executed and unauthorized | `forbidden` / unassessed |

CC-A is valid `qualified_supported` evidence and only makes a separately
authorized CC-B pilot eligible. `scientific_vote=false` and
`formal_execution_count=0` remain unchanged.

The preceding `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED` /
`A_STOP_STEADY_ROUTE` checkpoint remains the immutable terminal state of the
voltage-source-plus-series-load route.

## Historical BranchConserve Batch 1 Outcome

| Item | Result | Evidence boundary |
| --- | --- | --- |
| B0 implementation | implemented; focused tests `25 passed` | Software/contract fact only |
| nominal L1 smoke | PASS | Valid non-voting execution; residual, ledger, and local-stability gates pass at one fixed device voltage |
| heating L1 atlas | 15 in-domain points; 4 initial stable+reachable | Non-voting pilot evidence only |
| cooling 15.8 V endpoint | `STEADY_LOAD_LINE_FAIL` | No contiguous high-conductive bracket under the frozen 33-point scan and solver budgets |
| common source domain | empty | L2 sentinel and Batch 2 ineligible |
| L2/B1/B2/PINN | not executed | `forbidden` / unassessed |

The terminal result is valid `failed_but_informative` numerical-method
evidence.  It is not an S2 physical failure, a Phase 1 vote, or a result about
rank-2 sensitivity or PINN training.  Dynamic solvers/controllers, historical
S0/equivalence evidence, and Frozen GT were not modified.

The intended positive ladder remains R1 `HysGeo-Hybrid-PINN`, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3; all remain `forbidden` and
unassessed.

## Qiu Source-Consistent Stage A Outcome

| Item | Result | Evidence boundary |
| --- | --- | --- |
| source audit | PASS; Qiu S1--S7 parameters, equations, PDF hashes, and source-module parity close | External-source and implementation consistency only |
| direct `beta+k` patch | `REJECT_DIRECT_BETA_K_PATCH` | `beta` and `k` have distinct source roles; v1 mixing semantics remain different |
| 16-case 0-D matrix | valid; all roots/residuals/Jacobians/eigenpairs certified | Bounded lumped source-oracle evidence only |
| 12 kOhm S1 | high-conductive 15.8/17 V algebraic roots are locally unstable; no dual domain | Not a 2-D or dynamic physics vote |
| seven-load sentinel | no load passes dual or nondegenerate forward gate | `failed_but_informative`; no continuous optimization or fitting |
| Stage B/B1/B2/PINN | not executed | `forbidden` / unassessed |

The v2 Stage A result is valid `failed_but_informative` source-oracle
evidence. It does not establish S2/Phase 1 failure, a two-dimensional forward
judge, Qiu quantitative reproduction, or any PINN result. PR #29 remains the
immutable v1 negative result.

Historical S1 science is `forbidden`/unassessed; interruption facts are supported
as infrastructure provenance only and do not vote on the active S2 route.

## Boundary

Do not launch R2/R3, the formal matrix, patterned branches, or any downstream
stage. The only admissible follow-up is a separately preregistered non-voting
telemetry closure for `NOM/heating/0.35 mA/L1`, without changing the solver,
budgets, physics, thresholds, or the 25 preserved valid artifacts.

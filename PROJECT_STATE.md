# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_QIU_SOURCE_CONSISTENT_STAGE_A_STOPPED`.
- Execution base: `main@0877714dbed92d4d43f031fab5032f5cbd56eae8`.
- Result branch: `codex/q2-qiu-source-consistent-branchconserve-v2`.
- Terminal disposition: `A_STOP_STEADY_ROUTE`.
- `scientific_vote=false`; `formal_execution_count=0`.

## Batch 1 Outcome

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

Do not start Stage B, B1/B2, data generation, or training. A future route must
be separately authorized and cannot relabel S7 as an intrinsic/local
production law or tune source/material parameters to manufacture a stable
transition domain.

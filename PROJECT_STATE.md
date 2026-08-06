# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint: `Q2_CURRENT_CLAMP_CC_A_PASSED`.
- PR #30 merge base: `0230b036c271e02f52bc8d4b25f0021eb0d1870b`.
- CC-A code anchor: `230f1e37fbefd88d554d54009db626d175a00444`.
- Result branch: `codex/q2-current-clamp-source-consistent-2p5d-v1`.
- Terminal disposition: `PASS_CC_A_CURRENT_CLAMP_ADMISSION`.
- `scientific_vote=false`; `formal_execution_count=0`.

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

Do not start CC-B/CC-C, data generation, or training without a new explicit
authorization. A future CC-B must validate the source mapping in the 2-D
uniform limit and certify constrained field stability before any ground-truth
dataset. It cannot relabel S7 as an intrinsic/local law or tune source/material
parameters after seeing results.

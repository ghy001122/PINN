# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint:
  `Q2_CONTROLLER_RELEVANCE_B3_VALID_FAIL_FINAL_FORWARD_RESCUE_STOPPED`.
- Execution base: `main@1c9758ef151299a4694b4edcc81dd48feec704ba`.
- Result branch: `codex/controller-relevance-final-forward-rescue`.
- Terminal disposition: `B3_MATCHED_WINDOW_CORRECTNESS_VALID_FAIL`.
- Route: `STOP_FINAL_FORWARD_SOLVER_RESCUE`.

D0, exact-condensed v1, NLS-v1, controller-v2, frozen S2 physics and
protocols, equivalence-v1/v2/v3, historical identities, and Frozen GT remain
unchanged. The intended positive ladder remains C01/R1
`HysGeo-Hybrid-PINN`, conditional C06, preferred R2
`GeoPhase-HomoMoE-PINN`, and conditional R3; no positive rung was executed or
supported.

## Bounded Rescue Outcome

| Stage | Result | Evidence boundary |
| --- | --- | --- |
| R0 | 9 V reached the active floor with nonlinear certification failure; 12.5 V fixture accepted | Production controller semantics; non-voting |
| R1 | contraction gate passed | GM ratio `0.4995588`; step-8 ratio `0.0038959`; spectral radius/max power norm `0.5000018` |
| R2 | both fixed states accepted | 9 V at `0.625 ns`; critical fixture at `0.15625 ns`; all root/integrity/ledger gates pass |
| B3 9 V | port and event gates pass; exact reversal sequence fails | 417 versus 364 reversal records; first direction mismatch at index 11 |
| B3 12.5 V | all matched-window correctness gates pass | current NRMSE `1.1502e-6`; voltage NRMSE `1.4570e-7`; five reversals exact |

The B3 aggregate CPU time was `312.703125 s`; performance timing was not
started because correctness failed. B4, fresh S0, Phase 2, training, and OOD
all remain unexecuted.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| R1 contraction audit | `numerically_validated`; `qualified_supported` | Named floor-terminal context only |
| Safeguarded Anderson R2 | `numerically_validated`; `qualified_supported` | Two fixed controller states only |
| B3 matched windows | `numerically_validated`; `failed_but_informative` | Numerical-method consistency; no physical vote |
| B4/S0 | `planned`; `forbidden` | No cost, full-trajectory, or campaign result |
| Phase 2/C01/C06/R1-R3 | `planned`; `forbidden` | No data, training, baseline, seed, OOD, field, port, event, or ledger result |

`scientific_vote=false` and `formal_execution_count=0`. All generated evidence
is `literature-guided synthetic numerical digital-twin evidence`, not
experimental validation.

S1 science is `forbidden`/unassessed; interruption facts are supported as
infrastructure provenance only.

## Preserved Boundary

Do not change the matched window or reversal rule, relax topology, add another
solver, rerun D0/B2/equivalence, run B4/S0, or bypass S0. The only next decision
is whether to create a separately authorized C04/`gamma_sub`
identifiability-boundary contingency manuscript; that route is not activated
and cannot be described as 2.5D positive-PINN success.

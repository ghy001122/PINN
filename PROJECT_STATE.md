# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Checkpoint:
  `Q2_S0_STOP_INVALID_EXECUTION_AFTER_REPAIR_BUDGET_EXHAUSTED`.
- Base: `main@d1dd6921...`; fresh S0 result evidence: `adf6cc4...` on PR #20.
- The Qiu-inspired VO2 real `x-y` geometry, mask-local Ti/Au terms,
  source-scale-preserving S2 closure, white-box hysteresis, terminal/RC
  coupling, and ledgers are unchanged.
- The 63 evaluations / 60 unique executions / 3 legal reuses are unchanged.
- Frozen GT v1.1 and historical claim-bearing evidence are unchanged.

## Fresh S0 Result

| Run | Terminal | Published units | Interpretation |
| --- | --- | ---: | --- |
| `S0-SMOKE-20260801-V1` | `PASS` | 4/4 | Non-voting software/mechanism smoke. |
| `S0-FORMAL-20260801-V1` | `INVALID_S0_EXECUTION` | 14/60 | Nullable zero-drive LIM axes caused `int(None)`; no global vote. |
| `S0-SMOKE-20260801-V2` | `PASS` | 4/4 | Repaired-code non-voting smoke. |
| `S0-FORMAL-20260801-V2` | `INVALID_S0_EXECUTION` | 25/60 | First nonzero-drive unit hit controller forced-remainder fail-closed before record publication; no global vote. |

The one permitted implementation repair was used between V1 and V2. V2's 25
published records cover 5 FAIL controls, 9 MMS cases, 6 LIM cases, and 5
zero-drive REF cases; their identities and hashes validate and their local
statuses pass. They are partial unit-level provenance, not a completed Phase 1
campaign.

The first unformed unit was
`TRJ-P1V2-REF-quiescent_9V-S1T4`. The remaining 35 units and all aggregate
63-item gates are unassessed. The terminal controller exception is an
execution-integrity boundary, not an S2 physical-law failure.

## Evidence And Claims

| Item | Lifecycle / status | Boundary |
| --- | --- | --- |
| Fresh S0 runner | `implemented`; software fact `supported` | Direct single-implementation path, atomic registries and content-addressed unit records; not a scientific result. |
| Fresh S0 attempts | `executed`; validity `invalid`; claim `forbidden` | V1 14/60, V2 25/60, global scientific vote false, `formal_execution_count=0`. |
| S2/controller software | bounded software evidence `supported` | Historical smoke/C1/C2 and S0 partial units only; no judge qualification. |
| Phase 1-v2 reference result | `forbidden` / unassessed | Requires one complete valid campaign with every required gate passing. |
| Phase 2 and C01/C06 | `forbidden`; not executed | No dataset, training, baseline, OOD, field, port, event, or ledger result. |
| R1/R2/R3 claims | `forbidden` | Require the sequential evidence ladder in `PROJECT_GOAL.md`. |

`formal_execution_count=0`; no valid formal scientific campaign exists. All
new outputs are literature-guided synthetic numerical digital-twin evidence,
not measurements or experimental validation.

## Preserved History

- strict-equivalence-v1: immutable `NO_GO`, 12/57; no S2 physics vote.
- equivalence-v2: immutable `VALID_FAIL`, 10/57; no retry.
- equivalence-v3: immutable `VALID_FAIL`, 12/57; no A/B/C vote; no retry.
- equivalence-v4/v5: forbidden.
- Prior E0: immutable invalid runner provenance, no scientific vote.
- S1 science remains `forbidden`/unassessed; v6-v8 remain historical
  `failed_but_informative` evidence.

## Manuscript Route And Stop

The intended positive route remains C01 `HysGeo-Hybrid-PINN`, followed only
after evidence by C06/C05 and preferred R2 `GeoPhase-HomoMoE-PINN`, then
conditional C11/R3. It is blocked at the reference-judge gate.

No further execution is authorized. A future goal must explicitly reopen the
repair policy and address the nonzero-drive forced-remainder numerical-
integration boundary without changing physics or returning to equivalence.

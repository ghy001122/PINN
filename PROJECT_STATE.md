# Project State

## Authoritative Current Snapshot

- Delivery/phase: `Q2_SCI_DELIVERY_MODE` /
  `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Parent checkpoint:
  `PHASE1_V2_EQUIVALENCE_V2_ONE_SHOT_AUDIT`.
- Strict-equivalence-v1 substate: `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`.
- Metric-validity substate: `GO_VERSIONED_EQUIVALENCE_V2_AUDIT`.
- R1 `HysGeo-Hybrid-PINN` remains the minimum manuscript route; R2
  `GeoPhase-HomoMoE-PINN` is the preferred upgrade; R3 is conditional.
- Phase 1-v2 is a Qiu-inspired single-device VO2 x-y plane with explicit VO2,
  mask-local Ti/Au terms, and the source-scale-preserving S2 closure. Qiu
  quantities constrain device-level uniform-mode coefficients, not a local
  material stack or thermal spectrum.
- S2 anchor `d37745b...`; base config SHA-256 `06004985...`. The 63 formal
  items remain `planned_not_executed`; `formal_execution_count=0`; no formal
  campaign is authorized.
- The solver and `7/7` non-voting smoke cases pass after one historical
  zero-signal audit-metric repair. This is software evidence only.
- Controller-v1 is historical `NO_GO_RUNTIME`; its one-replay diagnostic
  supported the now-consumed single controller revision.
- Controller-v2 C1/C2 passed bounded integrity/parity. C3 stopped at the worker
  backstop with `0/18` intervals and `1/9` trajectories before forecast or
  dormant-runner votes: `NO_GO_RUNTIME_PERFORMANCE_ONLY`.
- Source-corrected v3 anchor `0ebe037...` replaces only the erroneous 15.0 V
  lock probe with qualitative 15.8 V. Its 63/60/3 inventory is unexecuted and
  the old bundle remains immutable.
- Frozen candidate `1ae2704...`/`d3833a4...`/`39044f37...` and harness
  `73f7d7d1...` produced the sole valid strict audit. It fail-fast rejected
  plan 11 after `12/57`: `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`. This rejects
  strict implementation equivalence, not S2 physics; retry is unauthorized.
- Metric validity (`460cbef...`/`5301ce0...`) is qualified
  `GO_VERSIONED_EQUIVALENCE_V2_AUDIT`: `9/9` physical, `6/6` cancellation and
  `13/13` tamper controls passed; it is not an equivalence vote.
- PR #11 mechanically maps 638 templates over 57 rows and passed `21/21` raw
  controls. PR #12 makes the unchanged A/B/C rules record-executable. Both are
  solver-free, preserve strict-v1, and executed zero audit rows.
- Comparator closure v3 preserves every PR #12 identity and adds the narrow
  integrity gates needed to reject common-mode missing dynamic indices,
  common-mode wrong L1/L2/L4 shapes, caller-relabelled row/failure identities,
  and incomplete or reordered terminal plans. It passed clean-checkout CI and
  merged at `85d5c7ba...`. The one-shot runner is anchored at `85c3709...`.
  Its unique attempt completed 10/57 rows and stopped at plan 9 with
  `VALID_FAIL / RECORD_VALIDATION_FAILURE`: the identical candidate/oracle
  interval records carried 91 noncanonical ledger `scale_group` values. Rows
  10..56 remain unassessed; equivalence-v2 count is one and formal count zero.
- The S1 scientific claim is `forbidden`/unassessed; its timeouts are supported
  infrastructure provenance only. The v6-v8 material-stack route remains
  `failed_but_informative` with no formal execution.
- Phase 1 science, Phase 2, R1-R3, nonzero coupling, FEM/3D, and NbO2 remain
  blocked. Frozen GT v1.1 is unchanged. New evidence is synthetic numerical
  digital-twin evidence, not measurement or experimental validation.

## Current Evidence

| Item | Status | Boundary |
| --- | --- | --- |
| Phase 0 governance | `supported` | Repository routing/integrity only. |
| S2/controller software | `supported` bounded software/readiness | 7/7 smoke and C1/C2 integrity pass; C3 has no forecast; 63/60/3 and formal zero. |
| Strict-equivalence-v1 | `failed_but_informative` implementation result | Frozen valid audit stopped at plan 11 after 12/57; S2 science remains unassessed. |
| Metric validity and coverage | `qualified_supported` solver-free audits | 9/9 physical, 6/6 cancellation, 13/13 parent controls; corrected 57-row map and 21/21 raw controls; does not override the one-shot record-validity failure. |
| Equivalence-v2 one-shot | `forbidden` implementation-equivalence claim | `VALID_FAIL` at plan 9 after 10/57 rows; record-validation failure before A/B/C voting; no retry. |
| S1 diffusive model-form claim | `forbidden` / unassessed | No atomic metric, K fit, or scientific vote. |
| S1 interruption provenance | `supported` infrastructure provenance only | Timeouts only. |
| v6-v8 material-stack route | `failed_but_informative` | Retired history; no formal execution. |
| Phase 1-v2 reference result | `forbidden` | Requires every gate in an authorized formal campaign. |
| R1/R2/R3 positive claims | `forbidden` | Require sequential direct evidence. |

## Retained Historical Evidence

- Frozen synthetic 1D GT v1.1 is immutable.
- Constrained `gamma_sub` recovery remains `qualified_supported` only inside
  its named prior/calibration boundary and is the downgrade route.
- Complete-PINN, M40/M40R, M44, OASIS, public-source, and other retained
  outcomes keep their claim-matrix statuses; none validates Phase 1-v2.

## Delivery Boundary

Preserve strict-v1 and the completed one-shot v2 evidence; do not retry,
reinterpret, or optimize either audit. The terminal route is
`STOP_S2_ACTIVATE_GAMMA_SUB`; C1/C2/C3 and formal execution remain blocked.
Only a separate user decision may activate the retained fixed-rank-1
`gamma_sub` plus calibration-gate and identifiability-boundary manuscript route.

Do not rerun S1 or v6-v8; train a PINN; generate Phase 2 data; run inverse;
modify frozen GT; add nonzero coupling; run FEM/3D, M44, or NbO2; or claim
Phase 1/Qiu/experimental success.

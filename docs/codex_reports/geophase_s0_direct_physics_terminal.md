# Fresh S0 Direct-Physics Qualification Terminal Report

## Disposition

`INVALID_S0_EXECUTION / STOP_AFTER_REPAIR_BUDGET_EXHAUSTED`

The fresh S0 route did not form a global physical or scientific verdict. The
independent Phase 1 judge therefore remains unqualified, and Phase 2 data,
C01/vanilla/MLP training, C06, OOD evaluation, figures, and manuscript-positive
PINN claims were not started.

## Task contract and manuscript use

Task:
`Q2_S0_DIRECT_PHYSICS_QUALIFICATION_TO_C01_C06_R1_MANUSCRIPT_EVIDENCE`.

The intended manuscript destination was the independent FVM judge underlying
C01 `HysGeo-Hybrid-PINN`. Inputs were the frozen S2 implementation, source
contract, controller-v2, 63-item manifest, 60-unit DAG, and 3 legal reuses.
Physics, thresholds, protocols, candidate identity, and frozen GT were not
modifiable. A complete valid S0 pass was required before Phase 2 or PINN.

Execution budgets were 1,800 s CPU for smoke and 14,400 s CPU for the formal
campaign, with one process and one BLAS/OpenMP thread. One bounded
implementation repair was allowed; a second repair or retry was forbidden.

## Identity and validation anchors

- Base: `d1dd6921beb5614da7dedfe1e4e481b149309ed4`.
- Initial code anchor: `a2eefcdc0d0cb9badba875d56f588c43158ec5e2`.
- Initial current-head CI: run `30698416347`, success.
- Sole repair anchor: `75a3ee6115c2bb00a0b1c16f5373b37062c0796a`.
- Repaired current-head CI: run `30698686938`, success.
- Immutable result evidence commit: `adf6cc4`.
- Pull request: [#20](https://github.com/ghy001122/PINN/pull/20).
- Selected implementation origin: commit `1ae2704f...`, tree `d3833a4a...`.
- Evidence type: literature-guided synthetic numerical digital-twin evidence;
  not measurement or experimental validation.

The runner is a fresh single-implementation path and imports no old E0,
equivalence, or readiness runner. It atomically publishes registries and
content-addressed canonical gzip unit payloads.

## Actual execution

### Non-voting smoke

Both versioned smoke runs completed 4/4 cases:

- `S0-SMOKE-20260801-V1`: 7.1896 s, `PASS`.
- `S0-SMOKE-20260801-V2`: 7.3371 s, `PASS` after the sole repair.

These checks established bounded software/mechanism behavior only and carried
no scientific vote.

### Formal V1

- Campaign: `S0-FORMAL-20260801-V1`.
- Terminal: `INVALID_S0_EXECUTION`.
- Published: 14/60 units in 8.3872 s.
- Error: `TypeError`, caused by applying `int()` to nullable spatial/time axes
  on the `zero_drive_equilibrium` LIM DAG row.
- Global scientific vote: false.
- `formal_execution_count=0`.

The one permitted repair mechanically resolved the nullable axes from the
frozen execution addendum and added a focused regression. No physics or gate
changed.

### Formal V2

- Campaign: `S0-FORMAL-20260801-V2`.
- Terminal: `INVALID_S0_EXECUTION`.
- Published: 25/60 units in 3028.6337 s.
- Published coverage: 5 FAIL controls, 9 MMS, 6 LIM, and 5 zero-drive REF
  units.
- Every published payload is canonical, content-addressed, registry-bound, and
  locally `PASS`.
- First unpublished unit:
  `TRJ-P1V2-REF-quiescent_9V-S1T4`.
- Trigger: `RuntimeError: controller-v2 forced remainder failed closed`.
- Global scientific vote: false.
- `formal_execution_count=0`.

The controller exception occurred before an auditable nonzero-drive unit
record could be published. It is a fail-closed numerical execution-integrity
boundary, not a physical-law failure and not an A/B/C/equivalence vote. The
remaining 35 units and all dependent 63-item aggregate gates are unassessed.

## Evidence and claim effect

- The fresh runner/control plane is `implemented`.
- Both formal attempts are `executed` with `validity: invalid`.
- The 25 V2 unit records are bounded partial provenance only.
- S0/Phase 1 validity remains `forbidden` / unassessed.
- Runtime feasibility remains `forbidden` / unassessed.
- Phase 2, C01, C06, geometry/protocol OOD, field/port/event/ledger model
  comparisons, and positive R1/R2 claims remain `forbidden` and unexecuted.
- Historical E0 and equivalence-v1/v2/v3 remain immutable.
- Frozen GT v1.1 is unchanged.

No Methods or Results sentence claiming solver qualification or positive PINN
evidence is eligible. The only reviewer-defense statement is that a fresh
direct-physics attempt reached the first nonzero-drive reference unit and
failed closed without being misreported as a scientific result.

## Atomic evidence

- V1 registry:
  `outputs/tables/geophase_s0_direct_physics/formal/S0-FORMAL-20260801-V1/campaign_registry.json`.
- V2 registry:
  `outputs/tables/geophase_s0_direct_physics/formal/S0-FORMAL-20260801-V2/campaign_registry.json`.
- V1/V2 configuration snapshots and foundations are colocated with the
  registries.
- V1 has 14 and V2 has 25 canonical `.json.gz` unit records; the terminal
  evidence test verifies compressed and canonical SHA-256 identities.
- No `s0_summary.json`, 63-item verdict table, Phase 2 dataset, or training
  namespace was published for V2.

## Stop and next highest-value problem

The implementation-repair budget is exhausted. This goal must not repair,
resume, or rerun either attempt.

The next substantive bottleneck is the nonzero-drive forced-remainder
numerical-integration boundary, not equivalence and not PINN architecture. A
future goal would need to preregister a bounded controller/integrator study for
`quiescent_9V-S1T4`, preserve all physics and scientific thresholds, define an
auditable failure disposition, and explicitly authorize a new repair and
execution budget. It may not reuse the 25 partial units as a completed formal
campaign.

## Closeout validation

- Fresh S0 implementation, terminal-evidence, and authority-route tests:
  43 passed.
- Current-head CI includes all three S0 focused test files.
- Governance: zero failed checks; low-context budget 19,410/24,576 bytes.
- Tracked JSON: 293/293 valid.
- Frozen GT: 8/8 SHA-256 identities unchanged.
- Historical evidence manifest: 20/20 current checks passed.
- Staged formatting: passed.
- Current-head CI and merge results are recorded in the PR and final delivery.

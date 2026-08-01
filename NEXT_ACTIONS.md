# Next Actions

## Authoritative Current Queue

- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Active checkpoint:
  `Q2_PHASE1_E0_SINGLE_IMPLEMENTATION_PHYSICS_VALIDATION`.
- Immediate checkpoint:
  `Q2_PHASE1_E0_STOP_SECOND_IMPLEMENTATION_DEFECT`.
- Activation contract:
  `configs/geophase_phase1_e0_single_implementation_physics_validation.yaml`.
- Evidence closeout merge: PR #16 / `06096e7...`.
- The selected implementation, S2 physics, source contract, controller, and
  63/60/3 scientific inventory are frozen.
- `formal_execution_count=0`; formal artifacts are zero.

## Single Next Action

No experiment is authorized. Preserve and merge the terminal invalid E0
provenance. The second runner implementation defect occurred after the sole
permitted repair, before any completed case or scientific vote. Formal E0,
Phase 2, C01, and diagnosis-driven upgrades remain blocked.

Any future attempt to reopen the reference-judge route would require a new goal
that explicitly changes the exhausted repair policy; it cannot be treated as a
continuation, retry, or scientific rescue.

## Locked Historical Routes

- strict-equivalence-v1: immutable 12/57 `NO_GO`; no retry;
- equivalence-v2: immutable 10/57 `VALID_FAIL`; no retry;
- equivalence-v3: immutable 12/57 `VALID_FAIL`; no A/B/C vote; no retry;
- equivalence-v4/v5: forbidden;
- S1: science unassessed and no rerun;
- v6-v8: terminal `failed_but_informative` history;
- frozen GT v1.1: immutable.

## Scope Boundary

Do not repair or rerun E0; run C1/C2/C3, a formal campaign, PINN training,
Phase 2 generation, inverse work, source fitting/digitization, S1/v6-v8, M44,
NbO2, FEM/3D, or nonzero dual-device coupling. Do not change the selected
implementation, S2 equations/parameters, protocols, manifest, or gates.

# Next Actions

## Authoritative Current Queue

- Active phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`.
- Active checkpoint:
  `Q2_PHASE1_E0_SINGLE_IMPLEMENTATION_PHYSICS_VALIDATION`.
- Immediate next checkpoint:
  `Q2_PHASE1_E0_PREFLIGHT_PENDING_FRESH_AUTHORIZATION`.
- Activation contract:
  `configs/geophase_phase1_e0_single_implementation_physics_validation.yaml`.
- Evidence closeout merge: PR #16 / `06096e7...`.
- The selected implementation, S2 physics, source contract, controller, and
  63/60/3 scientific inventory are frozen.
- `formal_execution_count=0`; formal artifacts are zero.

## Single Next Action

Review the zero-computation E0 activation package. If accepted, the next task
requires fresh user authorization for one bounded, non-voting E0 preflight.

That future preflight may evaluate only:

1. source-scale and positive-coefficient identities;
2. analytic/manufactured electrical and thermal limits;
3. current, device-power, thermal, circuit, and combined ledgers;
4. the locked C1 critical state and bounded C2 critical trajectory;
5. L1/L2/L4 runtime, memory, and makespan forecast.

Its maximum CPU wall time is provisionally 7200 s. A pass permits only a
request for formal-campaign authorization. It does not unlock Phase 2 or PINN.

No numerical execution is authorized in the current task.

## Locked Historical Routes

- strict-equivalence-v1: immutable 12/57 `NO_GO`; no retry;
- equivalence-v2: immutable 10/57 `VALID_FAIL`; no retry;
- equivalence-v3: immutable 12/57 `VALID_FAIL`; no A/B/C vote; no retry;
- equivalence-v4/v5: forbidden;
- S1: science unassessed and no rerun;
- v6-v8: terminal `failed_but_informative` history;
- frozen GT v1.1: immutable.

## Scope Boundary

Do not run E0 preflight, C1/C2/C3, a formal campaign, PINN training, Phase 2
generation, inverse work, source fitting/digitization, S1/v6-v8, M44, NbO2,
FEM/3D, or nonzero dual-device coupling. Do not change the selected
implementation, S2 equations/parameters, protocols, manifest, or gates.

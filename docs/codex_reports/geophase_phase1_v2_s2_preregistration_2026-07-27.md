# Phase 1-v2 S2 Preregistration

Date: 2026-07-27

Task: `Q2_PHASE1_V2_S2_REFERENCE`

Base main: `4234e4431a0358dca40f9d9c5b26993d12ce7846`

## Disposition

`PREREGISTERED_NOT_EXECUTED`

This report records a config-only route replacement before any new numerical
calculation. It is not a solver, smoke, source-audit, S1, formal, PINN, inverse,
or validation result.

## Active route

- S2 is the Phase 1-v2 nominal thermal closure.
- VO2 storage/conduction are explicit over the active plane; Ti/Au thermal
  terms occur only under the electrode mask.
- The nominal 20 nm geometry defines
  \(C_m=C_\theta-C_{\rm explicit}>0\), \(c_m^A=C_m/A\), and
  \(g_\theta^A=G_\theta/A\). The derived \(c_m^A\) is frozen for 10/30 nm
  overlap audits so the audits cannot hide geometry sensitivity through
  re-normalization.
- S2 has no independent vertical thermal state.
- The same-device source audit is capped at 4 h and cannot digitize or fit a
  curve.
- S1 is a non-blocking, single-family positive-real sensitivity capped at 24 h
  active work and 48 h elapsed time. It cannot become production in this MVE.

## Locked machine identities

- S2 config SHA-256:
  `0600498590a8c100ec8dee95621719ea655354ec118015868cb07fedf89f85d5`
- Formal-manifest contract SHA-256:
  `54823e83d813ec4acd8df25354b62c38d58be158548414e637282383d1dc14a5`
- Expanded manifest CSV SHA-256:
  `c2b04c31c21e27a21b9ac90d1c9c9edfc05e6ea75dee7bf3b0dad180f8804a89`
- Expanded manifest metadata SHA-256:
  `c5b903997cb0c4d1a9df7c11c2d881bc391d326dfdcccd60d4d0a2d52a25176b`
- S1 MVE contract SHA-256:
  `ea9262ddb8730b183a9335f2e31eb0b172012c2e4b84bcab5c3e39b925d418ca`
- Bounded source-audit contract SHA-256:
  `d4650df081b826ac5e93b82bee10801d4346769738a1c4c5db871d22afbcc206`
- Unchanged Qiu source-only contract SHA-256:
  `857410517d5b955e2018d4b002fcbbe92bb320c451021b49ae27be1351cb1252`

The containing preregistration commit SHA is intentionally not self-embedded.
It is recorded by Git and must be an ancestor of every later Phase 1-v2
numerical artifact.

## Formal inventory

- evaluation items: 63;
- unique execution units: 60;
- exact nominal-overlap trajectory reuses: 3;
- every item status: `planned_not_executed`;
- formal execution count: 0;
- formal execution consumed: false.

The retired v6 96-item manifest remains byte-identical and permanently
`planned_not_executed`; it is not reused by Phase 1-v2.

## Historical integrity

- v6 config SHA-256: `0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1`;
- v7 repair SHA-256: `5ab66fb41b9af6fd605c351a86fa5928712528fcad8c9bc26cc55d18a0a92a18`;
- v8 repair SHA-256: `e047d7963c646cabdec9796a2f227c159750a76170805a6f02021e6fff24b00b`;
- old 96-item CSV SHA-256: `a617284bd8890adcab105851095801b6067307e5c85acfeb9b8a84c8467be045`.

The fixed-bottom material-stack/K-state route remains terminal
`failed_but_informative`. Its v8 pullback depth-frequency failure is not
reinterpreted by S2.

## Authorization boundary

After this preregistration commit is pushed, S2 implementation/focused tests
and bounded non-voting smoke may proceed. The bounded source audit and S1 MVE
may proceed in parallel and may not delay S2. A formal Phase 1-v2 campaign,
Phase 2 dataset generation, PINN training, inverse work, NbO2, nonzero
dual-device coupling, 3D/FEM, source fitting/digitization, and frozen-GT writes
remain unauthorized.

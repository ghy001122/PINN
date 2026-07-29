# Phase 1-v2 source-corrected strict equivalence audit

Final disposition: `NO_GO_EQUIVALENT_PERFORMANCE_REPAIR`.

## Execution identity

- Branch: `codex/phase1-v2-source-corrected-performance-repair`.
- Task-start candidate commit/tree:
  `1ae2704f6d84a3733d9de58aa23d992aa0c471a5` /
  `d3833a4a5dd067dab72c84f15fe2f8e726bd9512`.
- Candidate identity SHA-256:
  `39044f37c983060df48e9915c594f69fbfbeacc60eef9a32bc352bdb5ec25b10`.
- Test-only oracle SHA-256:
  `e1a349ca0275021508cd07da02576adafbbcdae81e122659274769f329016a37`.
- Invalid-launch evidence commit:
  `8e4f787e3b349c1858f53847c9f7f2bc4e712627`.
- Harness erratum commits: `c0523f66f1c7e3a29c65e114e9f5f60c6b9031fc`
  and shallow-checkout-only fix
  `6d8fa8759363132f838e513f911626cae82624c9`; final harness tree
  `0d5bfbb8d97466a98381532b73e5589dfcb9ea09`.
- Harness identity file SHA-256:
  `5f46cebadeea454b29abe4add46320461dec38fcdccede24f65f7efa24b94729`.
- Combined audit identity:
  `73f7d7d1d6fe204f219e9cab323e9fee0073b7531d9930ba9f5e8cbbb92005ef`.
- Harness addendum SHA-256:
  `83d21818ca8254adabcca7ccf13b10ed97aa01780a22343943fcc96674109916`.

The pre-audit [fast validation run 30460063437](https://github.com/ghy001122/PINN/actions/runs/30460063437)
completed with `success` before the numerical audit began.

## Retained invalid launch

The earlier loader launch stopped before planned row 1 because its dynamically
loaded dataclass module was absent from `sys.modules`. It remains supported
infrastructure provenance with `0/57` rows, zero votes, and no numerical
comparison. It is not an equivalence, performance, or S2-physics failure and
was not overwritten by the valid audit.

## Sole valid audit

Exactly one valid frozen-candidate audit was executed. The append-only journal
records `SCHEDULED`, `STARTED`, `NUMERIC_DISPOSITION`, and `COMPLETED`.

| Family | Completed |
| --- | ---: |
| Electrical | 9/9 |
| Single interval | 3/18 |
| Progression | 0/9 |
| Failure topology | 0/21 |
| Total | 12/57 |

The first 11 rows passed. Required fail-fast occurred at plan index `11`,
`EQ-INTERVAL-L1-legal_critical-base`. Its maximum normalized difference was
`1.4757614757614759`, above the locked `1e-12` gate, at
`full_step.lateral.face_to_cell_global_residual_W`. Progression and
failure-topology rows were not reached and cast no vote.

Atomic evidence SHA-256 values:

- summary: `e0df8aad70c57f8c2f37c23d135c2d81964a6783b453d39e0eeef99f30f92574`;
- attempt journal:
  `b3d96151f1e5ec7a2fcadca91c6c45bf9bbd888d01084b6b97a6de625cf6b31c`;
- electrical table:
  `0863beea8d3783e35736d7aa3a5fe7a574107d3b95e34667d29819bfa1b1b05f`;
- interval table:
  `7a9ba6b8282f03e56162921057133279241d11d4c49deace7644152efb6dc897`;
- not-reached progression and failure table schemas:
  `4a6f2533f3304711375d47c15e69bdf4e4c30f08f3833a641bc18bd8282e1a6f`.

## Claim and execution boundary

Lifecycle is `executed`, execution validity is `valid`, and the frozen
optimized implementation-equivalence claim is `failed_but_informative`. The
S2 physical and Phase 1 scientific claims remain `forbidden` and unassessed.
This audit does not show that S2 physics is false.

C1/C2/C3 readiness, runtime forecasting, dormant-runner execution, and formal
evaluation were not run. No retry or further optimization is authorized.
`formal_execution_count=0`; `formal_artifact_count=0`. The source-corrected S2
positive route stops under the locked budget pending explicit activation of
the retained `gamma_sub` plus identifiability-boundary manuscript route.

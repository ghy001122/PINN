# P0 clean-replay portability and asset closure

Date: 2026-07-22

## Outcome

The local clean-replay P0 is technically closed. This round restored and
verified the exact local asset pack, repaired portable historical evidence
identity without rewriting scientific hashes, removed known test side effects,
and converted submission readiness from `CONTENT_NO_GO` to
`CONTENT_GO_UPLOAD_NO_GO`.

No scientific forward, fit, inverse, PINN training, threshold change, or sealed
13 V payload access was performed. The constrained synthetic rank-1
`gamma_sub` result remains the only positive inverse mainline and remains
`qualified_supported` only under its locked calibration and protocol bounds.

## Verified evidence

| Check | Result |
| --- | --- |
| Required local replay assets | `50/50` exact-byte pass: 2 Qiu source PDFs, 6 frozen-GT assets, 6 open Zhang inputs, and 36 CEBA trajectories |
| Zhang sealed record | metadata checks pass; payload access `false` |
| Portable historical locks | `157/157` pass |
| Continuous-refinement source integrity | 36/36 case rows, aggregates, groups, and frozen-hash pair agree; scientific forward runs `0` |
| Targeted portability/readiness tests | pass |
| Detached full pytest | `440 passed in 455.02 s` on the validated code content |
| Governance | `pass_with_manual_review`; no failed check; frozen-GT hashes unchanged |
| Test pollution | historical 14-file rewrite and six unintended figures eliminated; designated validation logs are intentional evidence outputs |
| Readiness | technical content package `true`; journal upload `false`; disposition `CONTENT_GO_UPLOAD_NO_GO` |

The two mixed-newline Windows artifacts retain their original raw SHA-256
locks and separately declare canonical-LF Git identities. Verification accepts
only an exact current Git blob with the registered raw/canonical pair; it does
not normalize JSON values, ordering, whitespace, or numerical text.

## Claim disposition

No claim was upgraded or downgraded. In particular:

- `gamma_sub` remains a synthetic, calibration-gated effective coordinate, not
  a measured material constant;
- trained full-PINN forward, sensitivity, and inverse claims remain
  `failed_but_informative` or `forbidden`;
- M40/M40R dynamic real-device bridging and M41 remain blocked;
- Qiu quantitative external validation and exact author-code reproduction
  remain `forbidden`;
- full 2D hidden-field recovery and experimental validation remain
  `forbidden`.

## Remaining blocker and next action

The remaining blocker is not scientific computation. The project must select a
scope-compatible journal and article type, complete author metadata and
declarations, render and visually inspect that template, and publish only
redistributable artifacts while documenting restricted third-party asset
acquisition. A public standalone replay is not claimed until that archive and
license boundary are complete.

The required disposition is `continue` for upload preparation and `stop` for
new science.

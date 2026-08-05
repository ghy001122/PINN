# Q2 BranchConserve 2D Steady MVE v1 — Batch 1 terminal

## Disposition

```text
STOP_BRANCHCONSERVE_PILOT
validity = valid
scientific_vote = false
formal_execution_count = 0
claim_status = failed_but_informative
batch2_authorized = false
```

Batch 1 implemented and exercised the independent temperature-primary steady
solver, conservative electrical subsolve, fixed-source load line, branch atlas,
matrix-free local-stability certification, and atomic evidence path.  The
nominal L1 smoke passed.  The route stopped before the conditional L2 cost
sentinel because no certified cooling endpoint was found and therefore no
common stable+reachable source-voltage domain exists.

This is non-voting numerical-method evidence.  It is not an S2 or Phase 1
physical failure, does not validate a steady forward judge, and does not unlock
B1/B2, Phase 2, PINN, inverse, or refusal work.

## Final valid run

Run identity: `Q2-BC2D-BATCH1-20260805-V9`.

The nominal L1 smoke used a fixed device voltage of `0.28125 V`; its source
voltage was derived from the certified load mapping (`0.44402789183846336 V`).
It passed with:

- scaled thermal CV residual: `1.0290386598079964e-16`;
- scaled electrical CV residual: `9.006426274602687e-18`;
- fixed-source load residual: `1.286632324943241e-18`;
- all registered ledgers: PASS;
- rightmost spectral abscissa: `-909621.206668572 1/s`;
- stability zero band: `4153.225806451613 1/s`;
- maximum eigenpair relative residual: `7.562729615996744e-10`;
- peak process RSS: `63713280 bytes`.

The heating atlas published 15 in-domain points.  Four belong to the initial
stable+reachable component, at source voltages `0`, `1.597831964196512`,
`3.3587034257476938`, and `6.2003051824262645 V`.  The next two points are
unstable.  Stable re-entry points after that gap remain atlas-only and are
correctly labelled `reachable=false`; negative source/device-voltage points are
rejected before persistence.

## Cooling endpoint stop

The cooling endpoint was required at source voltage `15.8 V`, with a stable
conductive-state coordinate of at least `0.9`.  The deterministic descending
33-point device-voltage scan produced no contiguous high-conductive load-line
sign change:

- high-voltage points through `Vd=1.975 V` failed the registered inner solver
  with `STEADY_NONFINITE_OR_RANGE`;
- the range-legal point at `Vd=1.48125 V` was high-conductive
  (`0.9927188503341788`) but mapped to `Vs=67.46798975705472 V`, above the
  target;
- the next range-legal coarse point at `Vd=0.9875 V` mapped to
  `Vs=2.7557209014914554 V` but had conductive-state coordinate
  `0.3808592241063999`, so it lies outside the required conductive endpoint
  component and cannot bracket the target with the former point;
- a diagnostic high-temperature solve at the intervening Brent trial
  `Vd=1.28413846 V` exhausted the fixed 640 residual-evaluation budget and did
  not certify a root.

The low-conductive point was deliberately not used to manufacture a Brent sign
change across a discontinuous branch jump.  The cooling atlas consequently has
zero certified points, the common reachable domain is empty, and the L2
sentinel is ineligible.

## Implementation defects repaired before the terminal run

Earlier run identities remain local, immutable implementation provenance.  The
repairs were limited to the registered implementation and each received a
focused regression:

1. corrected SciPy LGMRES outer-cycle budget semantics;
2. made central-difference Jv homogeneous and subtracted conservative thermal
   terms without catastrophic cancellation;
3. started the cooling bracket scan from the high-voltage endpoint;
4. used the same termwise directional derivative in matrix-free stability;
5. prevented pseudo-arclength from persisting points outside
   `0 <= Vd <= Vs <= 15.8 V`;
6. allowed leading invalid bracket samples without bridging an invalid gap;
7. enforced the cooling endpoint conductive-component floor during bracketing.

Focused validation: `25 passed`.

## Budget and artifacts

Completed stage telemetry totals `450.25 CPU-s` and `458.65929530002177 wall-s`.
Two interrupted implementation-atlas attempts are each conservatively charged
the full 1800-s batch ceiling, giving upper-bound aggregate accounting of
`4050.25 CPU-s` and `4058.6592953000218 wall-s`, below both 4-hour gates.  No
individual completed stage exceeded 30 minutes.

Compact evidence:

- `outputs/tables/q2_branchconserve_2d_steady_mve_v1/Q2-BC2D-BATCH1-20260805-V9/l1_smoke_summary.json`;
- `outputs/tables/q2_branchconserve_2d_steady_mve_v1/Q2-BC2D-BATCH1-20260805-V9/branch_atlas.csv`;
- `outputs/tables/q2_branchconserve_2d_steady_mve_v1/Q2-BC2D-BATCH1-20260805-V9/l1_atlas_summary.json`;
- `outputs/tables/q2_branchconserve_2d_steady_mve_v1/Q2-BC2D-BATCH1-20260805-V9/nominal_common_reachable_domain.json`;
- `outputs/tables/q2_branchconserve_2d_steady_mve_v1/Q2-BC2D-BATCH1-20260805-V9/batch1_terminal.json`.

Large fields, face fluxes, stability arrays, solver telemetry, and SHA-256
manifests remain under
`data/processed/q2_branchconserve_2d_steady_mve_v1/Q2-BC2D-BATCH1-20260805-V9/`
and are intentionally not committed.

Because V9 ran before the result commit, `batch1_terminal.json` records the
exact worktree-byte SHA-256 values of the configuration and six computational
core files; these hashes, rather than the inherited base Git SHA alone, are the
authoritative V9 computational identity.

## Claim boundary and next action

Allowed wording:

> A non-voting branch-resolved L1 steady-solver pilot was executed on the
> literature-guided synthetic 2.5D device contract; it stopped because the
> frozen branch-conservative 15.8 V cooling-endpoint construction had no
> certified contiguous high-conductive load-line bracket.

Forbidden wording includes S2 validation/failure, stable branch physics,
rank-2 sensitivity, B1/B2 success, PINN success, Qiu quantitative reproduction,
or experimental validation.

Do not approve Batch 2 under this identity.  Any future attempt to replace the
cooling-endpoint construction or equilibrium parameterization requires a new
versioned contract and fresh authorization; it cannot be described as a
continuation of Batch 1.

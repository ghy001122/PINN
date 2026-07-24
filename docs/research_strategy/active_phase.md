# Active Phase

Active phase ID: `Q2_GEOPHASE_E0_REFERENCE_SOLVER_FOUNDATION`

## Objective And Manuscript Use

Establish the only admissible judge for the revised manuscript: an independent,
conservative 2.5D reference solver for a Qiu-inspired coplanar VO2 thermal
neuristor. The solver must use true in-plane x-y geometry, a white-box
electrothermal phase-state closure, passive K-state vertical thermal memory,
finite-contact port integration, RC coupling, and independently evaluated
current and energy ledgers.

This phase can support a methods/equations section and authorize later GeoPhase
PINN work. It cannot itself support a positive PINN, inverse, generalization, or
real-device claim.

## Authorization And Route Change

The user explicitly replaced the former submission-lock core line with a
positive `GeoPhase-OQ-PINN` route. The validated v2 content package remains
historical evidence and a fallback baseline, but it is no longer the selected
manuscript target. The constrained `gamma_sub` result remains
`qualified_supported` historical evidence; no old claim is upgraded.

Canonical detailed contract:
`docs/research_strategy/geophase_oq_pinn_execution_contract.md`.
Preregistered E0 configuration:
`configs/geophase_e0_2p5d_reference.yaml`.

## Live-Workspace Audit

- Reusable: Qiu geometry/provenance and RC contracts; conservative FVM and
  ledger patterns; VO2/NbO2-separated constitutive components; port/circuit,
  Fourier, interface, and SVD/principal-angle utilities; historical failure
  evidence and frozen governance.
- Adapt only: M40/M40R are x-z source-bridge evidence, not the new x-y solver;
  OASIS and old Fourier/continuation modules are baselines, not demonstrated
  GeoPhase innovations.
- Absent and therefore still `forbidden`: an x-y K-state reference solver,
  transition-localized mixture-of-experts, joint phase/Joule homotopy,
  GeoPhase forward training, sensitivity-fidelity loss, observation-quotient
  inverse, refusal head, and NbO2 cross-model run.
- The revised brainstorm's statement that K-state thermal-memory code already
  exists is not true for live `main`; only related reduced thermal components
  and lumped/source models exist.

## E0 Scope And Required Artifacts

Execute only the config-first E0 chain:

1. freeze coordinate, topology, units, boundary/interface, branch-state, and
   energy-ledger contracts;
2. implement the independent x-y finite-volume/implicit solver and passive
   K-state vertical reduction outside the PINN residual implementation;
3. add manufactured, conservation, convergence, limit, passivity, and
   failure-path tests;
4. run one bounded formal E0 after all preflights pass;
5. write JSON/CSV evidence, geometry/field/convergence figures, a task report,
   claim-matrix entry, and an explicit E1 authorization decision.

Planned code placement is additive and preserves historical modules:

- `src/pinnpcm/physics/geophase_2p5d.py`;
- `src/pinnpcm/solvers/geophase_2p5d_fvm.py`;
- `scripts/run_geophase_e0_reference.py`;
- `tests/test_geophase_2p5d_*.py`.

Do not reorganize or rename frozen/historical modules merely for aesthetics.

## Fail-Closed Gates

All thresholds and budgets are authoritative in the E0 YAML. At minimum, E0
must pass manufactured electrical/thermal checks, current imbalance, full
energy ledger, spatial and temporal fine-pair convergence, passive positive
K-state behavior, reduction accuracy against the higher-order thermal
reference, uniform/zero-drive limits, and single/dual-device decoupling limits.
Passing finite-state or conservation checks without convergence does not count.

E1 GeoPhase forward PINN work is authorized only when every required E0 gate
passes in the single formal run. A physics, coordinate, topology, or ledger
defect stops the phase for foundation repair. A complete and valid gate failure
is retained as `failed_but_informative` and blocks E1.

## E0-Scoped Authorization Boundary

During E0, do not run GeoPhase training, architecture comparisons, GPU rental,
geometry OOD, inverse/refusal networks, NbO2 cross-model work,
literature-curve refits, M44 repair, full 3D, full phase field, latent-heat
upgrades, or manuscript result writing.

An E0 pass authorizes only an E1/G1 go/no-go review; it does not automatically
unlock every item above. G2 architecture/homotopy, G3 geometry generalization,
G4 quotient/inverse/refusal, and G5 cross-model work must still be activated
sequentially. Items outside the selected G0--G5 route require a separate
future phase with
preregistered value, budget, thresholds, and failure wording. Historical stop
votes for M44, M40/M40R, N0/M33, and D0 remain binding to those named routes,
but they do not constitute a permanent ban on the distinct GeoPhase program.

## Current Claim Boundary

`supported`: the route-change authorization, live inventory, equation/config
contract, and historical evidence identity. `qualified_supported`: only the
already locked historical constrained `gamma_sub` and other prior sub-results.
GeoPhase forward accuracy, architectural benefit, geometry generalization,
sensitivity fidelity, quotient recovery, refusal, Qiu quantitative
reproduction, NbO2 transfer, and experimental validation remain `forbidden`.

# Phase 1 GeoPhase 2.5D Reference-Solver Contract

## Identity

- Phase: `Q2_PHASE1_2P5D_REFERENCE_SOLVER`
- Status: `preregistered_v5_pending_checkpoint_a_revalidation`
- Manuscript use: independent truth and conservation judge for later R1/R2 work
- Evidence type after execution: literature-guided solver-generated synthetic numerical digital-twin evidence
- Threshold authority: `configs/geophase_phase1_2p5d_reference.yaml`
- Threshold schema: `geophase_phase1_2p5d_reference_v5`
- Source authority: `configs/qiu_vo2_phase1_source_contract.yaml`
- Stage routing: `configs/geo2p5d_stage.yaml`

This contract narrows Phase 1 of the full execution guide. The v5 revision
locks the remaining adaptive-step rejection caps and prior-audit vote rules
before Checkpoint A is revalidated. It records no formal solver result. The
sole formal execution remains blocked until fresh user authorization for
Checkpoint B.

## Source Isolation

Qiu-reported quantities, source-author-fitted lumped quantities, repository engineering priors, unresolved semantics, and withheld-curve restrictions are separated in the source-only contract. Historical M40/M40R/M44 configs may be used only as source locators and failure lessons. Their parameter votes, fields, convergence results, and claim statuses do not transfer into Phase 1.

The Qiu lumped thermal conductance and capacitance describe a device-plus-electrode-plus-substrate equivalent. They are not local material properties or local boundary conductances. Phase 1 uses them only as nominal global scale anchors: one positive factor normalizes the area-integrated regional DC sink, and another normalizes active-plane plus passive-memory storage. Likewise, Qiu's source-author resistance endmembers are mapped analytically to the nominal uniform-film port resistance. These are device-effective source-model normalizations, not repository parameter fits, local measurements, independent validation, or permission to score/digitize the withheld 12.5 V curve.

## Model And Topology Boundary

Resolve one Qiu-inspired coplanar VO2 footprint in the physical x-y plane. The x coordinate is the current path and y is the single-device width. The active plane has three explicit masks:

1. left electrode-covered VO2;
2. bare VO2 channel;
3. right electrode-covered VO2.

The background/interdevice Al2O3 surface is not a resolved Phase 1 field. Bare and electrode-covered VO2 therefore use separately fitted passive K-state thermal impedances. The active-plane VO2 storage is excluded from those fits to prevent double counting. The bare reference contains the Al2O3 substrate branch; the contact-covered reference contains the substrate branch plus a passive Ti/Au overlay branch.

The unnormalized material-stack references determine relative impedance shape and regional contrast only. Their nominal combined conductance is scaled to \(2.06\times10^{-4}\,\mathrm{W\,K^{-1}}\), and their combined memory capacity is scaled so that active VO2 plus memory equals \(4.96\times10^{-11}\,\mathrm{J\,K^{-1}}\). The nominal active-plane contribution is \(1.535\times10^{-14}\,\mathrm{J\,K^{-1}}\) and is subtracted before the memory target is formed. Positive scaling must preserve passivity.

At 325 K, the nominal uniform insulating and metallic endmember conductivities are analytically locked to `39.2883183844845` and `7619.04761904762 S/m`, respectively, so the boundary-integrated uniform limit recovers the same-role Qiu author resistance endmembers. Pointwise use under nonuniform temperature is an explicit effective-closure assumption and cannot support an intrinsic-conductivity claim.

Finite contacts use Dirichlet electrical boundary values. Contact resistance and thermal-boundary resistance are omitted engineering simplifications, not validated interfaces. The model is not a calibrated Qiu device, exact author-code reproduction, full multimaterial interface model, full 3D/FEM model, or experimental validation.

## Dual-Device Boundary

Phase 1 may duplicate the single-device solver only to test zero-coupling behavior, equal-drive symmetry, and label-swap invariance. The coupling coefficient is exactly zero and the reported device spacing is non-voting.

Any nonzero dual-device claim requires a later explicitly activated substrate surface heat field or a high-order independently validated passive nonlocal kernel. That later model must have its own mesh/time convergence, reciprocity, conservation, ledger, and source/provenance gates. A scalar empirical coupling term cannot substitute for those checks.

## Independence Contract

The reference implementation must use conservative cell-centered finite volumes and adaptive implicit backward Euler time integration. Its discrete residual, flux reconstruction, nonlinear solve, and ledger computation must not call or reuse the later PINN residual implementation. Shared continuous equations and parameter YAML are allowed; shared discrete residual code is not.

## Locked Numerical Contract

The formal configuration fixes, before implementation results are seen:

- base grid: 10 by 25 cells over 100 nm by 500 nm, with spatial levels 1, 2, and 4;
- time interval: 0 to 20 microseconds;
- base maximum step: 10 ns; transition maximum step: 0.25 ns; time divisors 1, 2, and 4;
- fixed comparison grid: conservative area restriction to the physical base cells;
- fixed comparison time grid: 0 to 20 microseconds at 5 ns spacing, without post-hoc event alignment;
- protocols: 0, 9, 12, 12.5, and 15 V steps plus one locked 12.5 V pulse;
- initial state: 0 V device voltage, all temperatures at 325 K, heating branch `b=1`, and equilibrium conductive state;
- damped Newton tolerances, damping/Armijo bounds, fail-closed fallback, and linear tolerances;
- state/branch-triggered step halving, a 0.02 transition threshold, four
  rejected trials per accepted step, 1000 rejected trials per case, and
  fail-closed rejection-cap handling;
- K-state fit/evaluation time and frequency grids, response weights, optimizer tolerance, and validation-grid voting;
- algebraic source-scale preflights for both uniform electrical endmembers, global thermal conductance, total capacity, and positive scale factors;
- exact 96-case formal inventory and four-hour CPU ceiling.

Implementations may fail closed or expose a contract defect. They may not tune these values after seeing formal results. A change to this lock requires an explicit protocol revision before the formal execution counter is consumed.

## Metric Contract

All field and port convergence comparisons use the fixed physical space-time grids. For a candidate `u` and fine reference `u_ref`, the configured NRMSE is

\[
\operatorname{NRMSE}(u,u_{ref})=
\frac{\operatorname{RMSE}(u-u_{ref})}
{\max\{\operatorname{RMS}(u_{ref}-u_{ref}(0)),d_{floor}\}}.
\]

The floors are 1 pA for terminal current, 1 mK for temperature rise, and `1e-6` for conductive-state change. A case below its floor cannot pass through a small normalized error; its NRMSE is non-voting and the case is routed to the corresponding absolute analytic-limit gate. Nonfinite values fail closed. Event times are matched as ordered threshold crossings without post-hoc time warping.

## Formal Case Inventory

| Group | Construction | Cases |
| --- | --- | ---: |
| Vertical reference and reduction | 2 regions x 4 orders x 3 response types | 24 |
| Manufactured solutions | 3 problems x 3 refinement levels | 9 |
| Single-device refinement | 6 protocols x 5 independent grid/time pairs | 30 |
| Topology and prior audits | 6 audits x 3 protocols | 18 |
| Decoupled dual-copy limits | four named behavior cases | 4 |
| Fail-closed controls | five named corrupt/nonphysical cases | 5 |
| Analytic limits | six named limits | 6 |
| **Total** | exact, not an estimate | **96** |

The machine-readable axes and case IDs live in the Phase 1 YAML. Adding an undeclared formal case or silently omitting one invalidates the formal run.

## Checkpoint Separation

Checkpoint A may complete the still-unexecuted v5 contract revalidation,
solver implementation, behavior tests, explicitly labelled CPU smoke, locked
96-case manifest, configuration hash, environment manifest, and
preregistration record. Its `formal_execution_count` must remain zero.

Checkpoint B is the sole 96-case formal campaign. It requires fresh user
authorization and must start from the preregistration SHA and configuration
hash emitted by Checkpoint A. The new ledger families are additional metrics
on the existing cases; they do not add cases. After Checkpoint B begins, gates,
case axes, parameters, source semantics, and tolerances are immutable.

## Required Responsibilities

Implementation may add responsibility-based modules only when real behavior is implemented:

- `src/pinnpcm/physics/`: material kernels, source-traceable parameters, region masks, interfaces, and continuous ledgers;
- `src/pinnpcm/solvers/`: independent FVM assembly, implicit stepping, nonlinear convergence, port integration, and refinement comparison;
- `src/pinnpcm/evaluation/`: gate metrics and machine-readable summaries;
- `scripts/`: one config-driven CLI with deterministic CPU smoke/formal modes;
- `tests/`: manufactured, conservation, units, topology, passivity, limits, and failure-path behavior.

Do not create empty inverse, solver, or evaluation placeholders merely to match the eventual architecture.

## Verification Gate

Algebraic source-scale preflights run before any solver case and do not consume the 96-case formal budget. A failure is a contract/implementation error and blocks smoke execution. After those preflights pass, all configured formal gates vote together:

1. manufactured electrical linear-field, thermal source/diffusion, and K-state cases;
2. terminal-current imbalance and the independent identity between terminal
   device power and field-integrated Joule power;
3. separate thermal, circuit, and combined electrothermal ledgers. The
   backward-Euler circuit ledger reports physical capacitor-energy change and
   nonnegative algorithmic capacitor dissipation separately;
4. independent spatial, temporal, and event-time fine-pair convergence;
5. positive K-state capacities/conductances, stable real poles, passivity, and step/impulse/frequency validation against the higher-order reference;
6. zero-drive, uniform-conductivity, cooling, thermal-resistance, RC, and zero-input limits;
7. bare/contact-covered topology audits and contact-overlap audits;
   the 400/800 nm substrate truncation must also pass held-out step/frequency
   response limits, while overlap QoI sensitivity is reported against spatial
   discretization error before any geometry-robust wording;
8. two-copy zero-coupling, symmetry, and label-swap limits;
9. nonfinite nonlinear solve, negative passivity, ledger tamper, and coordinate swap fail closed;
10. preregistered single-device literature-trend checks inside the declared source/prior envelope.

Source-envelope trends are non-voting unless their variation is at least the
estimated numerical noise. These added checks are metrics on existing formal
cases and do not change the 96-case inventory.

Finite output, current balance alone, or a source envelope smaller than discretization error cannot pass Phase 1.

## Execution And Output Contract

Development uses CPU smoke and focused tests. Checkpoint A must stop with
`formal_execution_count=0` after writing its manifests and smoke evidence.
Only after fresh user authorization may Checkpoint B execute the single formal
campaign and write formal JSON/CSV first, then figures/tables and a report. It
may not train a PINN, fit device/literature parameters, run inverse work,
digitize literature curves, modify frozen GT, repair M44, execute NbO2, add
nonzero dual-device coupling, or expand to full 3D. The locked passive K-state
reduction fit is required and is not device calibration.

## Disposition

- Pass: lock the evidence, update the claim matrix with the narrowly supported synthetic single-device reference statement, and activate Phase 2 dataset/split design.
- Fail: preserve all artifacts as `failed_but_informative`, block Phase 2 and R1-R3, and propose one bounded repair or reduction-rejection decision.
- Budget overrun, source ambiguity affecting the model, or contract defect: stop before consuming or repeating the formal execution and request the authority required by `AGENTS.md`.

## Claim Wording

Allowed after a complete pass only: a literature-guided synthetic single-device 2.5D reference benchmark passed its preregistered numerical, conservation, convergence, passivity, topology, limit, and trend gates.

Forbidden: Qiu calibration or exact reproduction, measured-device agreement, complete contact/interface validation, nonzero dual-device thermal-coupling validation, full 3D/FEM validation, successful R1/R2, observation-quotient recovery, PINN sensitivity fidelity, arbitrary terminal-only hidden-field recovery, or cross-material generalization.

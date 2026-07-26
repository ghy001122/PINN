---
task_name: Q2_PHASE1_2P5D_REFERENCE_SOLVER_CHECKPOINT_A
base_sha: 7c0f7d6ee679a3ac802ed4aff302736e194d487d
preregistration_sha: 212a4277bf9cf8afe365d922adefe67bdd7595e1
final_sha: SELF
branch: codex/phase1-2p5d-solver-implementation
tests:
  - focused_checkpoint_a_and_governance: 37 passed
  - full_regression: 477 passed in 296.68 seconds
  - governance: pass_with_manual_review, zero failed checks
reproduction_commands:
  - .\.venv\Scripts\python.exe -m pytest -q tests\test_geophase_phase1_preregistration.py tests\test_geophase_phase1_solver.py tests\test_geophase_phase1_checkpoint_a_evidence.py tests\test_project_governance.py
  - .\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
  - .\.venv\Scripts\python.exe scripts\run_geophase_phase1_reference.py --checkpoint a --preregistration-sha 212a4277bf9cf8afe365d922adefe67bdd7595e1
  - .\.venv\Scripts\python.exe -m pytest -q
  - .\.venv\Scripts\python.exe scripts\validate_tracked_json.py
  - git diff --check
frozen_gt_modified: false
evidence_type: implementation_behavior_tests_and_bounded_nonclaim_smoke
claim_status: supported_software_fact_only_scientific_phase1_claim_forbidden
config_sha256: 0361f609faf56cbc542f07be65abece0b8875aa0f9f8f9ea2539c098d2efdab1
formal_execution_count: 0
formal_case_manifest_count: 96
formal_case_results_generated: 0
current_phase: Q2_PHASE1_2P5D_REFERENCE_SOLVER
current_checkpoint: A_COMPLETE_B_NOT_AUTHORIZED
next_single_priority: user_decision_after_nonvoting_substrate_warning
disposition: stop_before_formal_campaign
---

# GeoPhase Phase 1 Reference Solver Checkpoint A

`final_sha: SELF` denotes the implementation commit containing this
self-referential report. The concrete commit is reported after it is pushed.

## Authorization And Git Boundary

PR #1 was changed from draft to ready only after its head was verified as
`deba657ff2621f1ef2b1aafa9d8d00cbe0347a8d` and its CI run was successful. It
was merged into `main` with merge commit
`7c0f7d6ee679a3ac802ed4aff302736e194d487d`. Implementation occurred only on
`codex/phase1-2p5d-solver-implementation`; no implementation commit was made
directly on `main`.

The final pre-formal authority is schema v6 at preregistration SHA
`212a4277bf9cf8afe365d922adefe67bdd7595e1`. Earlier v4/v5 anchors remain in
history. v5 locked adaptive rejection and prior-audit criteria. Behavior
testing then exposed that the old branch equation forced stationary `b=1`
toward zero, making the locked branch-increment trigger impossible even at the
minimum step. Before any formal run, v6 replaced this with a bounded
rate-activated directional memory that holds exactly at zero temperature rate.
No formal result existed when either revision was made.

## Implemented Checkpoint A Scope

- Conservative cell-centered sheet FVM with harmonic face conductance,
  finite-contact Dirichlet boundaries, insulating non-contact boundaries,
  independently integrated terminal currents, and field/terminal Joule-power
  identity.
- Coupled backward-Euler electrothermal/RC step with matrix-free LGMRES Newton,
  locked Armijo bounds, a real fail-closed fixed-point fallback, and the v5
  adaptive rejection caps.
- Separate bare-VO2 and electrode-covered-VO2 passive vertical thermal
  references and K-state kernels. The contact-covered reference contains the
  Ti/Au overlay; it is not copied into the bare channel.
- K order family fixed at K=1 ablation, K=2/3 candidates, and K=8 high-order
  reference; Checkpoint A did not select a winning K.
- Device-effective VO2 conductivity endpoints with nominal metallic
  `Rm=262.5 ohm`. Qiu S7 `k=4.90` is not multiplied into this endpoint and is
  absent from the 96-case matrix.
- Thermal, circuit, combined electrothermal, and device-power ledgers,
  including backward-Euler capacitor numerical dissipation.
- Manufactured, passivity, limit, coordinate, nonfinite, ledger-tamper,
  zero-coupled duplicate, symmetry, label-exchange, adaptive-rejection, and
  prior-audit evaluator behavior tests.
- Exact 96-case manifest with every row marked `planned_not_executed`.

No PINN was trained. No inverse problem, device/literature fit, Qiu curve
digitization, GPU task, M44 repair, NbO2 task, nonzero dual-device coupling,
formal convergence case, formal K-state fit/selection, formal trend case,
scientific dataset, or Phase 1 figure was produced.

## Bounded Smoke Evidence

The source-scale algebraic preflight passed. On the bounded 10 by 5 smoke
grid, zero-drive temperature drift was `1.1369e-13 K`; the 1 V step produced
device voltage `5.7418e-4 V`, current `2.7619e-8 A`, and maximum temperature
`325.0000000198 K`. The adaptive 2 ns smoke accepted one step, rejected none,
and had maximum state/branch increment `1.0899e-9`. Two zero-coupled copies
had zero temperature difference. These values are non-claim implementation
checks, not formal Phase 1 evidence.

## Pre-Formal Failure Warning

The non-voting substrate-depth evaluator compared the locked 400 and 800 nm
high-order references. The bare-region step/frequency metrics were
`0.00313/0.00608`; the contact-covered metrics were `0.00461/0.12313`.
Therefore the contact-covered frequency value exceeds the future locked limit
`0.05`. Checkpoint A does not cast this formal vote, but an unchanged formal
campaign is at material risk of failing that gate. No threshold, case,
normalization, parameter, or result was changed after observing the warning.

## Evidence And Claim Boundary

Supported: the implementation, behavior tests, source-scale preflight, smoke,
hash identities, ledger artifacts, and 96 planned-case manifest exist.

Forbidden: Phase 1 passed; a converged 2.5D reference judge exists; Qiu was
calibrated or reproduced; contact/substrate truncation was validated; K=2 or
K=3 was selected; nonzero interdevice coupling was modeled; or any positive
PINN, inverse, experimental, FEM/3D, or cross-material result exists.

## Stop Condition

`formal_execution_count=0`. Checkpoint B was not run and remains blocked. The
next user decision must explicitly acknowledge the substrate-depth warning and
choose either the unchanged, one-shot locked formal campaign or a separately
versioned bounded repair before formal execution. Silent gate relaxation is
forbidden.

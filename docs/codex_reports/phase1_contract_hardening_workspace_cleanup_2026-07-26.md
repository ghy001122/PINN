---
task_name: phase1_contract_hardening_and_workspace_cleanup
base_sha: a5c63a16d039b53b92d15a941bacca3e9b9d70f2
final_sha: SELF
branch: codex/phase1-geophase-2p5d-contract-hardening
tests:
  - focused_phase1_and_governance: 15 passed
  - current_phase1_marker: 11 passed, 444 deselected
  - full_regression: 455 passed in 502.64 seconds
  - governance: pass_with_manual_review, zero failed checks
reproduction_commands:
  - .\.venv\Scripts\python.exe -m pytest -q tests\test_geophase_phase1_preregistration.py tests\test_project_governance.py
  - .\.venv\Scripts\python.exe -m pytest -q -m "current and phase1"
  - .\.venv\Scripts\python.exe -m pytest -q
  - .\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
  - .\.venv\Scripts\python.exe scripts\validate_tracked_json.py
  - git diff --check
frozen_gt_modified: false
evidence_type: repository_governance_and_preregistration_only
claim_status: supported
supported_claims:
  - live workspace routing and local archive hygiene are explicit and audited
  - the Phase 1 source, topology, numerical, metric, reduction, and formal-case contracts are preregistered
forbidden_claims:
  - successful Phase 1 solver
  - Qiu calibration or exact reproduction
  - complete contact or multimaterial interface validation
  - nonzero dual-device thermal-coupling validation
  - PINN, inverse, experimental, FEM/3D, or cross-material success
goal_distance_change: Phase 1 moved from an incomplete preregistration to an implementation-ready locked contract; no scientific gate was executed
claim_changes:
  - no scientific claim upgraded
  - nonzero dual-device coupling was explicitly moved outside Phase 1
new_blockers:
  - independent solver implementation and focused preflights remain absent
  - the sole formal run remains blocked until all implementation preflights pass
next_single_priority: implement_and_validate_the_locked_single_device_independent_2p5d_reference_solver
disposition: continue
---

# Phase 1 Contract Hardening And Workspace Cleanup

`final_sha: SELF` denotes the commit containing this self-referential report. The concrete local commit SHA is reported after commit. This round was performed on a phase-scoped branch and was not pushed during the task.

## Scope And Manuscript Use

The work implemented only the corrections identified by the repository review: live-workspace routing, local pollution cleanup, instruction consistency, Phase 1 contract hardening, source isolation, topology/claim correction, current-test organization, and Phase 0 inventory semantics. Its manuscript use is to make the independent reference judge implementable and auditable before any scientific execution.

No solver was implemented or formally run. No PINN training, inverse work, device/literature parameter fit, new curve digitization, GPU work, M44 repair, NbO2 work, or frozen-GT write occurred. The passive K-state reduction fit remains a required future part of the reference solver and is not device calibration.

## Actual Work And Changed Files

- Added `LIVE_WORKSPACE.md`: `E:\Python demo\PINN` is the only live Git checkout; `E:\PINN` is an external archive/reference area; chat-attached sources are a read-only reference layer.
- Removed the literal ignored `%SystemDrive%` Sogou cache tree after verifying that it resolved inside the workspace. It contained two files totaling 37,516,880 bytes and is not recoverable from Git.
- Moved `outputs/archives/PINN_research_context_chat_records_20260724_154259.zip` to `E:\PINN\workspace_archives\` without changing its 167,159,237-byte payload or SHA-256 `568B3F2B1C7867A5CDA4CAD82239C3F0849A71B8C1ADDD9A3C41976E1A126ADE`. The archive is local context only, not evidence and not a replay dependency. Its local ignore exception was removed.
- Removed runtime-specific editing conflicts from the root, scripts, and workflow instructions.
- Added `configs/qiu_vo2_phase1_source_contract.yaml` to separate literature-reported quantities, author-fitted lumped values, engineering priors, unresolved semantics, withheld-curve restrictions, and historical non-inheritance.
- Hardened `configs/geophase_phase1_2p5d_reference.yaml` to v2 with a fixed 10 by 25 base grid, 20-microsecond time horizon, adaptive implicit time-step lock, six protocols, initial state, nonlinear/linear tolerances, fixed physical comparison grids, NRMSE floors and zero-signal routing, K-state fit/evaluation grids and weights, and an exact 96-case inventory.
- Replaced the uniform vertical stack with separate bare-VO2 and electrode-covered-VO2 passive memories, explicitly excluding active VO2 storage from the fitted memory.
- Restricted Phase 1 to a single resolved device. Two independent copies are permitted only for zero-coupling, symmetry, and label-swap behavior tests. Nonzero coupling requires a later explicit substrate surface field or independently validated passive nonlocal kernel.
- Updated equations, the canonical guide, active/current context, claim matrix, manuscript go/no-go, inventory/tree, reproduction/context routing, and governance checks to the same boundary.
- Registered `current` and `phase1` pytest markers without relocating historical tests.
- Marked the 1070-row disposition CSV as an immutable Phase 0 snapshot rather than a live inventory.

## Validation And Reproduction

- Focused Phase 1 plus governance: 15 passed.
- Marker-only current Phase 1: 11 passed, 444 deselected.
- One final full regression: 455 passed in 502.64 seconds.
- Governance: `pass_with_manual_review`, zero failed checks; manual items remain the existing Codex trust/loading review and nonportable mtime review.
- Frozen GT: all eight configured hashes unchanged.
- Structured YAML/JSON parsing and `git diff --check`: passed.

The full regression validates repository compatibility only. It is not Phase 1 solver evidence.

## Evidence And Claim Boundary

Supported now: the workspace routing, cleanup record, source classification, and hardened Phase 1 preregistration exist and pass their static/governance tests.

Still `forbidden`: a successful Phase 1 solver, quantitative Qiu reproduction, measured-device agreement, complete contact/interface validation, nonzero dual-device coupling, positive R1/R2, observation-quotient recovery, PINN sensitivity fidelity, terminal-only arbitrary field recovery, full FEM/3D equivalence, and cross-material transfer.

## Distance To Definition Of Done

The contract ambiguity blocking responsible implementation is closed. The project has not advanced through a scientific gate: the independent solver, preflights, single formal execution, Phase 2 data, baselines, and R1-R3 evidence remain ahead.

## New Blockers

- Phase 1 implementation and focused behavioral preflights do not yet exist.
- The sole formal execution must not start until every preflight passes.
- A nonzero dual-device route has no authorized substrate-field or validated-kernel contract.

## Next Single Priority And Disposition

Implement and validate the locked single-device independent conservative 2.5D FVM/implicit reference solver. Disposition: `continue` within Phase 1; do not start Phase 2, PINN, inverse, or nonzero dual-device coupling.

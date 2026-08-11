# Reproduction Quickstart

## Phase 0 Governance And Frozen Integrity

```powershell
.\.venv\Scripts\python.exe scripts\audit_repository_realignment.py --base-commit 36cbc020869ca483ed1e84eb0326cee11618891c
.\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
.\.venv\Scripts\python.exe scripts\validate_tracked_json.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py tests\test_repository_realignment_audit.py -q
```

The repository realignment audit writes only the disposition CSV and Phase 0 machine summary. It does not run a scientific experiment or modify frozen GT.

## Current Authority And Stored-Evidence Verification

Confirm the current authority chain and validate the stored contracts used by the completed Phase 1H route without launching training, reference solves, or a formal item:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_q2_m1_self_consistent_imt_contraction_gate_v1.py tests\test_q2_m1_protocol_selected_equilibrium_manifold_mve_v1.py tests\test_q2_protocol_manifold_branch_aware_surrogate_mve_v1.py -q
.\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
```

The authoritative current disposition is `NO_GO_PROTOCOL_MANIFOLD_NEURAL_VALUE`; `active_phase.md` and `NEXT_ACTIONS.md` route the next work to limitation/negative-manuscript synthesis. The commands above validate existing contracts and stored evidence only. They do not authorize another seed, formal OOD, a forward-neural rescue, MoE, STL, inverse, dynamic RC, NbO2, or a threshold/architecture search.

## Historical Phase 1-v2 Read-Only Verification

This is the section formerly titled `Active Phase 1-v2 Read-Only Verification`.

The retained S2 preregistration, solver behavior, and controller-v2 evidence can be checked without launching the historical readiness or formal campaign:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_geophase_phase1_v2_preregistration.py tests\test_geophase_phase1_v2_solver.py tests\test_geophase_phase1_v2_smoke_evidence.py tests\test_geophase_phase1_v2_controller_v2_preregistration.py tests\test_geophase_phase1_v2_controller_v2_readiness_evidence.py -q
```

This is replay support for the historical `NO_GO_RUNTIME_PERFORMANCE_ONLY`
checkpoint and its 63 formal evaluation items. It is not the active contract,
does not support a Phase 1 pass or failure, and cannot reopen readiness, formal
Phase 1, Phase 2, or PINN work; do not rerun readiness from this section.

## Locked Historical Evidence

Use the exact config, script, test, and output chain named by `docs/paper/final_claim_matrix.md`, the cumulative registries, and the relevant evidence lock. Do not rerun frozen GT outputs in place or interpret historical evidence as Phase 1/R1 support.

Example constrained-`gamma_sub` integrity check:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gamma_sub_evidence_lock.py tests\test_gamma_sub_continuous_refinement.py tests\test_gamma_sub_calibrated_sequential_protocol_validation.py -q
```

## Full CPU Regression

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Known filtered matplotlib/pyparsing deprecation warnings are not failures when tests pass. Push/PR uses focused read-only validation. Manual full claim-bearing validation uses the trusted replay runner and checks immutable historical blobs.

## Academic Boundary

All project-generated outputs are synthetic numerical digital-twin evidence. External inputs require provenance, license, figure/table identity, units, access date, and SHA-256 before use. No local test is experimental validation or GitHub Actions evidence.

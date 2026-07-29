# Reproduction Quickstart

## Phase 0 Governance And Frozen Integrity

```powershell
.\.venv\Scripts\python.exe scripts\audit_repository_realignment.py --base-commit 36cbc020869ca483ed1e84eb0326cee11618891c
.\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
.\.venv\Scripts\python.exe scripts\validate_tracked_json.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py tests\test_repository_realignment_audit.py -q
```

The repository realignment audit writes only the disposition CSV and Phase 0 machine summary. It does not run a scientific experiment or modify frozen GT.

## Active Phase 1-v2 Read-Only Verification

Validate the current S2 preregistration, implemented solver behavior, controller-v2 evidence contract, and governance without launching readiness or a formal item:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_geophase_phase1_v2_preregistration.py tests\test_geophase_phase1_v2_solver.py tests\test_geophase_phase1_v2_smoke_evidence.py tests\test_geophase_phase1_v2_controller_v2_preregistration.py tests\test_geophase_phase1_v2_controller_v2_readiness_evidence.py -q
.\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
```

The active contract is the Qiu-inspired single-device x-y S2 reference with explicit VO2 and mask-local Ti/Au thermal terms. Its 63 formal evaluation items remain `planned_not_executed` and `formal_execution_count=0`. The solver and seven bounded non-voting smoke cases exist. Controller-v2 C1/C2 integrity passed, but C3 stopped at the worker backstop before a forecast or dormant-runner vote; the current disposition is `NO_GO_RUNTIME_PERFORMANCE_ONLY`.

These commands validate existing software/evidence contracts only. They do not rerun readiness and do not support a Phase 1 scientific pass or failure. No readiness rerun, formal registry/item, Phase 2 data generation, PINN training, inverse work, nonzero coupling, 3D/FEM, M44, or NbO2 execution is authorized. The single pure-equivalence performance opportunity requires fresh user authorization and a versioned contract before use.

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

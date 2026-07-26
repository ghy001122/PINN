# Reproduction Quickstart

## Phase 0 Governance And Frozen Integrity

```powershell
.\.venv\Scripts\python.exe scripts\audit_repository_realignment.py --base-commit 36cbc020869ca483ed1e84eb0326cee11618891c
.\.venv\Scripts\python.exe scripts\audit_project_governance.py --no-write
.\.venv\Scripts\python.exe scripts\validate_tracked_json.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py tests\test_repository_realignment_audit.py -q
```

The repository realignment audit writes only the disposition CSV and Phase 0 machine summary. It does not run a scientific experiment or modify frozen GT.

## Active Phase 1 Contract

Validate the hardened preregistration and source isolation only:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_geophase_phase1_preregistration.py -q
```

The contract locks the single-device region topology, grid/time/protocol schedule, nonlinear tolerances, fixed comparison grids, NRMSE policy, passive K-state fit, and exact 96-case inventory. No formal solver command exists yet. Add the config-driven Phase 1 CLI only with an implemented independent solver and focused tests. Do not invent an entrypoint, generate the formal dataset, add nonzero dual-device coupling, or begin PINN/inverse work.

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

# Reproduction Quickstart

## Governance And Frozen Integrity

```powershell
.\.venv\Scripts\python.exe scripts\audit_project_governance.py
.\.venv\Scripts\python.exe -m pytest tests\test_project_governance.py -q
```

## Locked Mainline

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gamma_sub_evidence_lock.py tests\test_gamma_sub_continuous_refinement.py tests\test_gamma_sub_calibrated_sequential_protocol_validation.py -q
.\.venv\Scripts\python.exe scripts\build_gamma_sub_evidence_lock.py --config configs\gamma_sub_evidence_lock.yaml
```

Exact per-figure builders and inputs are recorded in `docs/paper/final_figure_list.md`. Do not rerun frozen GT outputs in place.

## Full CPU Regression

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Known filtered matplotlib/pyparsing deprecation warnings are not failures when tests pass. There is no repository GitHub Actions workflow, so only local validation may be claimed.

## External Anchor

Priority D must first store an immutable source-data package under `data/external/`, record DOI/license/figure identity/units/access date/SHA-256, and define the fit/holdout split before the fitting script is run. The active gate is in `docs/research_strategy/active_phase.md`.

# External Curve Ingestion And Calibration Workflow Manuscript Report

## Repository

- Repo: https://github.com/ghy001122/PINN
- Branch: main
- Scope: synthetic numerical digital-twin manuscript evidence pack, not experimental validation.

## Changed Files

- `configs/literature_curve_ingestion.yaml`
- `configs/literature_curve_fit_external_anchor_v2.yaml`
- `configs/gamma_sub_tsw_calibration_workflow.yaml`
- `configs/gamma_sub_calibrated_sequential_protocol_validation.yaml`
- `scripts/ingest_literature_digitized_curves.py`
- `scripts/fit_literature_phase_change_curves_v2.py`
- `scripts/audit_gamma_sub_tsw_calibration_workflow.py`
- `scripts/audit_gamma_sub_calibrated_sequential_protocol_validation.py`
- `scripts/build_external_anchor_claim_stress_test.py`
- `scripts/build_submission_ready_gamma_sub_figures.py`
- `tests/test_literature_curve_ingestion.py`
- `tests/test_literature_curve_fit_external_anchor_v2.py`
- `tests/test_gamma_sub_tsw_calibration_workflow.py`
- `tests/test_gamma_sub_calibrated_sequential_protocol_validation.py`
- `tests/test_external_anchor_claim_stress_test.py`
- `data/literature/literature_curve_ingestion_registry.csv`
- `outputs/tables/literature_curve_ingestion_summary.json`
- `outputs/tables/literature_curve_ingestion_cases.csv`
- `outputs/tables/literature_curve_fit_external_anchor_v2_summary.json`
- `outputs/tables/literature_curve_fit_external_anchor_v2_cases.csv`
- `outputs/tables/gamma_sub_tsw_calibration_workflow_summary.json`
- `outputs/tables/gamma_sub_tsw_calibration_workflow_cases.csv`
- `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_summary.json`
- `outputs/tables/gamma_sub_calibrated_sequential_protocol_validation_cases.csv`
- `outputs/tables/external_anchor_claim_stress_test_summary.json`
- `outputs/tables/submission_ready_gamma_sub_figures_summary.json`
- `docs/literature/literature_curve_provenance_notes.md`
- `docs/gamma_sub_tsw_calibration_workflow_report.md`
- `docs/gamma_sub_calibrated_sequential_protocol_validation_report.md`
- `docs/paper/external_anchor_claim_stress_test_matrix.md`
- `docs/paper/main_text_results_v1.md`
- `docs/paper/methods_v1.md`
- `docs/paper/limitations_v1.md`
- `docs/paper/abstract_v1.md`
- `docs/paper/title_candidates.md`
- `docs/codex_reports/external_curve_ingestion_and_calibration_workflow_manuscript_report.md`

State files and registries were also updated: `PROJECT_STATE.md`, `NEXT_ACTIONS.md`, `RESEARCH_LOG.md`, `EXPERIMENT_REGISTRY.md`, `DATASET_REGISTRY.md`, `FIGURE_REGISTRY.md`, `docs/research_strategy/active_phase.md`, `docs/project_state/latest_changes.md`, `docs/project_state/file_inventory.md`, `docs/project_state/reproducibility.md`, `docs/project_state/repo_tree.md`, `docs/paper/sci_manuscript_evidence_matrix.md`, `docs/paper/experiment_to_figure_mapping.md`, and `docs/paper/claim_stress_test_matrix.md`.

## Google Drive And External Curves

Google Drive was accessed through the connected plugin. The folder listing contained PDF literature files but no provenance-backed digitized CSV/Sheet curve tables. Local `data/literature/curves/` also contained no curve CSV files.

- Curve files found: `0`.
- Valid curve files: `0`.
- Total accepted points: `0`.
- Blocked reason: `no_provenance_backed_digitized_curve_csv_found`.
- Ready for external curve fit: `False`.

No literature curve points were fabricated.

## External Curve Fit V2

- Curves fit: `0`.
- Median normalized RMSE: `None`.
- Limitation: `blocked: no provenance-backed digitized curves available`.
- Supports model plausibility: `False`.

The fitting code is ready for logistic `R_T/sigma_T`, threshold-proxy `I_V`, and saturating exponential pulse-conductance curves once provenance-backed digitized data are added.

## T_sw Calibration Workflow

- No-calibration relative error: `0.8309764722472351`.
- Best workflow: `synthetic_probe_calibrated_T_sw`.
- Best calibrated relative error: `0.037771657829419776`.
- Improvement over no calibration: `0.7932048144178153`.
- Minimum tested calibration accuracy needed: `0.04` K.
- Wrong-calibration control relative error: `0.3021732626353582`.

This supports a calibration-before-inversion narrative: constrain `T_sw` before estimating `gamma_sub`.

## Calibrated Sequential Protocol Validation

- Simulator-backed cases: `720`.
- All cases simulator-backed: `True`.
- All finite: `True`.
- Frozen GT unchanged: `True`.
- Best protocol: `calibrated_multi_pulse_to_ltp_ltd`.
- Best protocol success rate: `1.0`.
- Best protocol max error: `0.1111111111111111`.
- Success-rate gain over no calibration: `0.4833333333333333`.
- Success-rate drop under wrong calibration: `0.33333333333333337`.

This is synthetic ODE-backed protocol-design evidence only. It is not an experimentally validated pulse protocol.

## Manuscript Readiness Assessment

The current strongest SCI line is still the constrained reduced `gamma_sub` inverse problem. This pack improves the evidence chain by adding: external-curve no-fabrication handling, T_sw calibration workflow evidence, ODE-backed calibrated sequential protocol validation, claim stress testing, and first-draft manuscript text.

Remaining gap: no real external digitized curves were available, so external-curve fitting cannot be claimed. The manuscript should describe literature priors as literature-guided or engineering priors only.

## Validation

Commands run:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_literature_digitized_curves.py
.\.venv\Scripts\python.exe scriptsit_literature_phase_change_curves_v2.py
.\.venv\Scripts\python.exe scriptsudit_gamma_sub_tsw_calibration_workflow.py
.\.venv\Scripts\python.exe scriptsudit_gamma_sub_calibrated_sequential_protocol_validation.py
.\.venv\Scripts\python.exe scriptsuild_external_anchor_claim_stress_test.py
.\.venv\Scripts\python.exe scriptsuild_submission_ready_gamma_sub_figures.py
```

Dedicated new tests: 9 passed. Related legacy literature/calibration tests: 8 passed. Full test suite: 110 passed in 145.02 s.

## Boundaries

- Modified frozen GT: No.
- Submitted large files: No.
- Experimental data claim: No.
- Full hidden-field recovery claim: No.
- F-SPS-PINN superiority claim: No.


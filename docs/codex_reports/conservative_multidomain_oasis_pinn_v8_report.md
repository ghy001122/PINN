# Conservative Multidomain OASIS-PINN v8 Report

Repository: `https://github.com/ghy001122/PINN`

Branch: `main`

Base commit before task: `4cd4658bc9a2f2e429bfea09c5f1837b3110241e`

Final pushed commit hash is reported by `git rev-parse HEAD` after commit creation; it is not self-embedded in this report because that would change the commit hash.

All results are synthetic numerical digital-twin benchmark evidence, not experimental data. Frozen Ground Truth v1.1 files were not modified. Google Drive was not accessed because the task was fully specified by local `next_prompt24.md` and repository evidence.

## Changed Files

- `.gitignore`
- `CODEX_CONTEXT.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `RESEARCH_LOG.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/research_strategy/active_phase.md`
- `docs/project_state/repo_tree.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`
- `docs/project_state/reproducibility.md`
- `docs/method_equations.md`
- `docs/paper/claim_gate_resolution_matrix.md`
- `docs/paper/final_claim_matrix.md`
- `docs/codex_reports/conservative_multidomain_oasis_pinn_v8_report.md`
- `src/pinnpcm/physics/multilayer_sandwich.py`
- `src/pinnpcm/pinn/oasis_components.py`
- `scripts/audit_conservative_multilayer_forward.py`
- `scripts/audit_multidomain_oasis_pinn.py`
- `scripts/audit_active_protocol_identifiability.py`
- `scripts/audit_oasis_2d_field_resolution.py`
- `scripts/audit_phase_aware_stl_repair.py`
- `scripts/audit_adaptive_fourier_fsps_superiority.py`
- `tests/test_conservative_multilayer_forward.py`
- `tests/test_multidomain_oasis_pinn.py`
- `tests/test_active_protocol_identifiability.py`
- `tests/test_oasis_2d_field_resolution.py`
- `tests/test_phase_aware_stl_repair.py`
- `tests/test_adaptive_fourier_fsps_superiority.py`
- lightweight JSON/CSV evidence under `outputs/tables/` listed in `DATASET_REGISTRY.md`

## P0 Conservative Forward

P0 gate passed: `True`. Energy-balance median: `0.0`. Interface residual median: `6.620044358862851e-17`. Zero-source and manufactured conservation tests passed: `True`.

The v8 conservative path removes the unsupported artificial lateral factor, global sink shortcut, and temperature clipping. It uses explicit per-interface `Rc/Rth`, adaptive substeps, and a semi-implicit thermal solve. This supports only a reduced conservative stack diagnostic, not full FEM or device-grade reproduction.

## Multidomain OASIS-PINN Smoke

Finite loss: `True`. The smoke uses ordered stack encoding, layer experts, hard Dirichlet output transform, interface mortar loss, and a series-stack port solver. This is implementation evidence only, not performance evidence.

## Active Protocol And Sequential Inverse

Best D-optimal protocol: `near_threshold_amplitude_width_sweep`. Best rank: `0`. All-parameter gate: `False`.

Sequential terminal inverse status: `failed_but_informative`. Median relative error: `0.18602728400165358`. Blocked by identifiability gate: `True`.

This is a negative but useful result: terminal observables alone do not activate the tested multidomain parameters strongly enough in the conservative solver.

## 2D Field Resolution

Status: `blocked`. Block reason: `blocked_until_actual_electrode_BC_multi_terminal_solver_is_implemented`. The script refuses positive 2D field-recovery claims until an actual electrode-BC multi-terminal solver exists. It does not use sigma half-means.

## Phase-Aware STL And Fourier/F-SPS

Phase-aware STL repair status: `failed_but_informative`. Best algorithm: `adapter_stl`. Best transfer gain: `0.10802334582762174`. 100-step matched-budget diagnostic run: `True`. Front-coordinate and LoRA-STL are explicitly blocked and not claimed.

Adaptive Fourier/F-SPS uses true Pareto dominance: `True`. Best gated method: `adaptive_f_sps` with status `failed_but_informative`. Universal superiority remains `forbidden`.

## SCI Impact

The v8 pack improves engineering credibility and reviewer-defense boundaries for OASIS-PINN extensions. It does not replace the safer main paper claim. The primary SCI line should remain calibration-gated constrained `gamma_sub` inversion under fixed or tightly bounded priors, with OASIS/F-SPS/STL/2D evidence routed to supplementary discussion unless future claim gates pass.

## Validation

Validation commands were run before final commit:

```powershell
.\.venv\Scripts\python.exe scripts\audit_conservative_multilayer_forward.py
.\.venv\Scripts\python.exe scripts\audit_multidomain_oasis_pinn.py
.\.venv\Scripts\python.exe scripts\audit_active_protocol_identifiability.py
.\.venv\Scripts\python.exe scripts\audit_oasis_2d_field_resolution.py
.\.venv\Scripts\python.exe scripts\audit_phase_aware_stl_repair.py
.\.venv\Scripts\python.exe scripts\audit_adaptive_fourier_fsps_superiority.py
.\.venv\Scripts\python.exe -m pytest tests/test_conservative_multilayer_forward.py tests/test_multidomain_oasis_pinn.py tests/test_active_protocol_identifiability.py tests/test_oasis_2d_field_resolution.py tests/test_phase_aware_stl_repair.py tests/test_adaptive_fourier_fsps_superiority.py tests/test_multilayer_sandwich_device.py tests/test_oasis_components.py
.\.venv\Scripts\python.exe -m pytest
```

Result: target v8 test set passed; full `pytest` passed with 159 tests.

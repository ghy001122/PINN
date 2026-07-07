# Integrated High-Risk Claim Ladder Quick Profile Report

Repository: `https://github.com/ghy001122/PINN`

Branch: `main`

Parent governance commit: `461909d483c718747b25858852179493e70a40f7`

Final commit hash: reported in the final Codex response for this run. This report is part of that commit, so embedding the self hash here would change the hash.

## Scope

This run implements the `integrated_high_risk_claim_ladder_quick_profile` task as bounded synthetic numerical digital-twin claim-gate exploration. It does not modify frozen Ground Truth v1.1, does not claim experimental validation, and does not change the main manuscript line: calibration-gated constrained `gamma_sub` inversion remains the safest core claim.

## Changed Files

- `configs/high_risk_claim_ladder.yaml`
- `src/pinnpcm/experiments/__init__.py`
- `src/pinnpcm/experiments/high_risk_claim_ladder.py`
- `scripts/audit_high_risk_claim_ladder.py`
- `scripts/audit_integrated_stiffness_stl.py`
- `scripts/audit_fourier_fsps_conditional_superiority.py`
- `tests/test_high_risk_claim_ladder.py`
- `tests/test_integrated_stiffness_stl.py`
- `tests/test_fourier_fsps_conditional_superiority.py`
- `scripts/build_reviewer_defense_matrix.py`
- `tests/test_reviewer_defense_matrix.py`
- `outputs/tables/high_risk_claim_ladder_summary.json`
- `outputs/tables/high_risk_claim_ladder_cases.csv`
- `outputs/tables/integrated_stiffness_stl_summary.json`
- `outputs/tables/integrated_stiffness_stl_cases.csv`
- `outputs/tables/fourier_fsps_conditional_superiority_summary.json`
- `outputs/tables/fourier_fsps_conditional_superiority_cases.csv`
- `.gitignore`
- `docs/paper/claim_gate_resolution_matrix.md`
- `docs/paper/final_claim_matrix.md`
- `docs/manuscript/reviewer_defense_matrix.md`
- `PROJECT_STATE.md`
- `NEXT_ACTIONS.md`
- `EXPERIMENT_REGISTRY.md`
- `DATASET_REGISTRY.md`
- `FIGURE_REGISTRY.md`
- `docs/project_state/file_inventory.md`
- `docs/project_state/latest_changes.md`

## Validation Commands

- `./.venv/Scripts/python.exe -m pytest tests/test_high_risk_claim_ladder.py tests/test_integrated_stiffness_stl.py tests/test_fourier_fsps_conditional_superiority.py`
- `./.venv/Scripts/python.exe scripts/audit_high_risk_claim_ladder.py --profile quick`
- `./.venv/Scripts/python.exe scripts/audit_integrated_stiffness_stl.py`
- `./.venv/Scripts/python.exe scripts/audit_fourier_fsps_conditional_superiority.py`

Full test-suite status: `135 passed in 66.57s` via `./.venv/Scripts/python.exe -m pytest`.

## Quick Profile Status

Completed.

- High-risk ladder cases: `224`.
- High-risk ladder finite: `True`.
- Extended profile: configured only, not run.

## 2D Hidden-Field Recovery

- Supported level: `qualified_supported`.
- Best augmented protocol: `terminal_plus_dense_anchors_5pct`.
- Best protocol median field error: `0.08653171328673807`.
- Best protocol success rate: `1.0`.

Allowed wording: protocol-limited low-rank 2D hidden-field reconstruction under augmented observations.

Forbidden wording: sparse terminal data uniquely recover full 2D hidden fields.

## Terminal-Only Rescue

- Terminal-only full-field status: `failed_but_informative`.
- Terminal-only low-dimensional status: `qualified_supported`.

Interpretation: terminal-only full-field recovery remains an observability-boundary negative result. Multi-pulse terminal data can only support low-dimensional inverse wording under strong priors.

## Actual Stiffness Training And STL

- Actual stiffness PINN training completed: `True`.
- Residuals used: `R_T=C_T dT/dt - k_x d2T/dx2 - k_y d2T/dy2 - Q_Joule + gamma_sub(T-T0)` and `R_m=dm/dt - (s(T;T_sw,w)-m)/tau_m`.
- Seiler-style multi-head transfer implemented: `True`.
- Continuation/adaptive status: `qualified_supported`.
- Seiler-style status: `qualified_supported`.
- Frozen-trunk STL gain over direct: `0.36685026479233396`.

Interpretation: reduced benchmark support exists for stiffness-mitigation and Seiler-style mechanics. Full STL-PINN reproduction remains forbidden.

## Fourier/F-SPS Effect

- Conditional benefit status: `qualified_supported`.
- Best sharp/front method: `fourier_plus_continuation_asinh`.
- Best sharp/front gain: `0.33703`.
- Universal superiority status: `forbidden`.

Interpretation: Fourier/F-SPS-style choices are conditionally beneficial in sharp/front regimes in this residual-proxy sweep. Universal superiority remains forbidden.

## Upgraded Claims

- `qualified_supported`: low-rank 2D reconstruction with augmented dense anchors.
- `qualified_supported`: terminal-only low-dimensional inverse under multi-pulse strong-prior conditions.
- `qualified_supported`: actual reduced PINN stiffness mitigation by continuation/asinh/adaptive residual handling.
- `qualified_supported`: Seiler-style shared-trunk multi-head transfer in a reduced benchmark.
- `qualified_supported`: Fourier/F-SPS conditional benefit in sharp/front residual-proxy regimes.

## Failed But Informative Claims

- Terminal-only full 2D hidden-field recovery fails the quick-profile observability ladder.
- Sparse or weak anchors remain insufficient for strong full-field wording.

## Forbidden Claims

- Experimental validation.
- Sparse terminal data uniquely recover full 2D hidden fields.
- Full-grid 2D device inverse recovery is solved.
- Full Seiler et al. STL-PINN reproduction is complete.
- F-SPS/Fourier features are universally superior.

## SCI Workload And Innovation Value

The run adds bounded high-risk evidence that improves supplementary workload and reviewer-defense breadth. It gives the paper a clearer innovation ladder: reduced-target `gamma_sub` remains the main claim; reduced 2D observability, actual stiffness training, Seiler-style transfer mechanics, and conditional Fourier/F-SPS behavior become claim-gated supporting material.

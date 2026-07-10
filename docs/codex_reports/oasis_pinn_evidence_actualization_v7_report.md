# OASIS-PINN Evidence Actualization v7 Report

Repository: `https://github.com/ghy001122/PINN`
Branch: `main`
Base commit before this task: `c29ba2b10641d1b1a856009b47641a78f17f32b3`
Final commit hash: created after this report is staged; the exact hash is reported in the final Codex response for this task.

All results are synthetic numerical digital-twin benchmark evidence. They are not measured experimental data, not device-grade FEM, and not proof of sparse-port full hidden-field recovery.

## Scope

This task actualized the OASIS-PINN supplementary branch by replacing proxy or stub evidence with stricter simulator-backed, residual-computed, and actual-training evidence. Frozen Ground Truth v1.1 files were not modified.

## Changed Files

Core code:

- `src/pinnpcm/physics/multilayer_sandwich.py`
- `src/pinnpcm/pinn/oasis_components.py`
- `src/pinnpcm/experiments/claim_resolution_2d_field.py`

Audit scripts:

- `scripts/audit_multilayer_sandwich_device.py`
- `scripts/audit_terminal_only_active_protocol_rescue.py`
- `scripts/audit_multilayer_sandwich_low_dim_inverse.py`
- `scripts/audit_claim_resolution_2d_field.py`
- `scripts/audit_phase_aware_stl_repair.py`
- `scripts/audit_adaptive_fourier_fsps_superiority.py`

Tests:

- `tests/test_multilayer_sandwich_device.py`
- `tests/test_oasis_components.py`
- `tests/test_terminal_only_active_protocol_rescue.py`
- `tests/test_multilayer_sandwich_low_dim_inverse.py`
- `tests/test_claim_resolution_2d_field.py`
- `tests/test_phase_aware_stl_repair.py`
- `tests/test_adaptive_fourier_fsps_superiority.py`

Documentation/state files were synchronized, including project state, registries, claim matrices, reviewer-defense matrix, method-equation notes, and reproducibility notes.

## Key Evidence Updates

| Audit | v7 result | Interpretation |
| --- | --- | --- |
| Multilayer sandwich forward | `failed_but_informative`; `energy_balance_gate_passed = false`; residuals computed not stubbed | The reduced simulator is useful but not qualified as a boundary-consistent forward benchmark. |
| OASIS port layer | `series_stack` default; `mean_sigma_ablation` ablation-only | The main port path is no longer a mean-sigma shortcut. |
| Terminal-only active protocol rescue | `failed_but_informative`; simulator-backed; sensitivity norms near zero | The prior hand-crafted feature-matrix claim is not accepted as main evidence. |
| Low-dimensional sandwich inverse | `failed_but_informative`; condition numbers reach finite sentinel `1e300` | The simulator-backed inverse is ill-conditioned. |
| 2D field recovery | `forbidden`; holdout POD target; best median field error `0.7805643071194288` | No sparse-terminal or POD/Fisher field-recovery claim is allowed. |
| Phase-aware STL | actual torch smoke; `failed_but_informative` | STL mechanics are implemented but too weak for a positive claim. |
| Adaptive Fourier/F-SPS | best gated method `stiffness_gated_fourier` is `qualified_supported`; `adaptive_f_sps` is `failed_but_informative` | Only condition-limited stiffness-gated Fourier evidence is allowed. Universal superiority remains forbidden. |

## Claim Changes From v6

Downgraded:

- Boundary-aware multilayer forward: from v6 qualified support to v7 failed-but-informative because the energy gate fails.
- Augmented structured 2D field recovery: from v6 qualified support to v7 forbidden under holdout simulator-ensemble POD.
- Active terminal-only low-dimensional inverse: from v6 qualified support to v7 failed-but-informative under simulator-backed terminal observables.
- Low-dimensional sandwich inverse: from v6 qualified support to v7 failed-but-informative under simulator-backed conditioning.

Preserved as negative or limited:

- Phase-aware STL remains failed-but-informative.
- Adaptive/F-SPS universal superiority remains forbidden.

Upgraded only in a bounded way:

- `stiffness_gated_fourier` is condition-limited qualified-supported method-development evidence.

## Validation Commands

Required validation commands for this task:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_multilayer_sandwich_device.py tests/test_oasis_components.py tests/test_terminal_only_active_protocol_rescue.py tests/test_multilayer_sandwich_low_dim_inverse.py tests/test_claim_resolution_2d_field.py tests/test_phase_aware_stl_repair.py tests/test_adaptive_fourier_fsps_superiority.py
.\.venv\Scripts\python.exe -m pytest tests/test_port_physical_2d_inverse.py tests/test_stiffness_gated_fourier_fsps.py tests/test_claim_gate_resolution_matrix.py
.\.venv\Scripts\python.exe -m pytest
```

Validation results: targeted v7 tests passed (`10 passed`), legacy port/stiffness/claim-gate regression tests passed (`3 passed`), and full repository validation passed (`149 passed`).

## Boundary

The v7 results improve scientific rigor mainly by downgrading unsupported claims. They do not replace the constrained `gamma_sub` manuscript core and do not establish experimental validation, full device simulation, terminal-only full-field recovery, full STL-PINN reproduction, or universal F-SPS/Fourier superiority.
